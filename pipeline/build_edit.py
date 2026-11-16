"""Stage E: build the video from the edit file. Same file in, same video out, for any game.

    python pipeline/build_edit.py jobs/<job>/edit.json [--preview] [--only-check]

edit.json is the machine copy of EDIT.md (see pipeline/templates/edit.json for every field):
  size, fps, grade      output frame size, frame rate, optional ffmpeg colour filter for every shot
  shots[]               clip, in, out (seconds in the source), optional speed, grade, and
                        transition INTO this shot: "cut" (default) or any ffmpeg xfade name such as
                        fade, fadeblack, fadewhite, hblur (whip), zoomin, wipeleft, slideleft,
                        circleopen, dissolve; transition_s is its length (default 0.3)
  text[]                text, start, end (timeline seconds), font (file), size_pct, x_pct, y_pct,
                        colour, border, fade
  music                 file, start (seconds into the song), gain_db, fade_out
  sfx[]                 file, at (timeline seconds), gain_db
  out                   output file, relative to the edit file

Steps: check the edit against the rules, render every shot, join them, add text, mix music and
SFX, master to -14 LUFS (master_audio.py), run the QC gate (qc.py). Writes <out>.timeline.json with
each shot's start time on the timeline: use those times for text and SFX.
--preview renders 960x540 with the fast encoder; use it until the layout is locked.
--only-check validates and prints the timeline without rendering.
Relative paths in the file are relative to the edit file's folder.
"""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from config import fast_encoder, ffprobe, run

HERE = Path(__file__).resolve().parent
MASTER_ENC = ["-c:v", "libx264", "-crf", "14", "-preset", "medium"]

def esc(p):
    """A path or value made safe inside an ffmpeg filter argument."""
    return "'" + str(p).replace("\\", "/").replace(":", "\\:").replace("'", "\\'") + "'"

def check(edit, base):
    """Validate the edit. Returns (shots with resolved paths and lengths, problems, warnings)."""
    stop, warn, shots, used = [], [], [], []
    if not edit.get("shots"):
        return [], ["no shots in the edit file"], []
    for n, s in enumerate(edit["shots"], 1):
        clip = (base / s["clip"]).resolve() if not Path(s["clip"]).is_absolute() else Path(s["clip"])
        if not clip.is_file():
            stop.append(f"shot {n}: clip not found: {clip}")
            continue
        info = ffprobe(clip)
        a, b, speed = float(s["in"]), float(s["out"]), float(s.get("speed", 1))
        if not (0 <= a < b <= info["duration"] + 0.05):
            stop.append(f"shot {n}: in/out {a}-{b} is outside the clip (0-{info['duration']:.2f})")
        if not 0.1 <= speed <= 8:
            stop.append(f"shot {n}: speed {speed} is outside 0.1 to 8")
        tr = s.get("transition", "cut")
        tr_s = float(s.get("transition_s", 0.3)) if tr != "cut" else 0.0
        length = (b - a) / speed
        if n == 1 and tr != "cut":
            stop.append("shot 1 cannot have a transition into it")
        if tr != "cut" and (length < tr_s * 2 or (shots and shots[-1]["len"] < tr_s * 2)):
            stop.append(f"shot {n}: the {tr_s}s transition is too long for a {length:.2f}s shot")
        for (c, x, y, m) in used:
            if c == clip and a < y and x < b:
                warn.append(f"shot {n} reuses {clip.name} {max(a, x):.2f}-{min(b, y):.2f} already used in shot {m} (each clip once)")
        used.append((clip, a, b, n))
        if speed < 1 and info["fps"] * speed < 30:
            warn.append(f"shot {n}: {speed}x on a {info['fps']} fps clip stutters; make it with slowmo.py first")
        shots.append({"n": n, "clip": clip, "in": a, "out": b, "speed": speed, "len": length,
                      "transition": tr, "transition_s": tr_s, "grade": s.get("grade")})
    lens = [round(s["len"], 2) for s in shots]
    for i in range(len(lens) - 2):
        if abs(lens[i] - lens[i + 1]) < 0.04 and abs(lens[i + 1] - lens[i + 2]) < 0.04:
            warn.append(f"shots {i + 1}-{i + 3} all last {lens[i]}s (never three equal in a row)")
    t = 0.0
    for s in shots:
        s["start"] = round(t - s["transition_s"], 3)
        t = s["start"] + s["len"]
    total = round(t, 3)
    for k, x in enumerate(edit.get("text", []), 1):
        if not 0 <= x["start"] < x["end"] <= total + 0.01:
            stop.append(f"text {k}: {x['start']}-{x['end']} is outside the video (0-{total})")
        if x.get("font") and not (base / x["font"]).is_file() and not Path(x["font"]).is_file():
            stop.append(f"text {k}: font file not found: {x['font']}")
        if len(str(x["text"]).split()) > 6:
            warn.append(f"text {k}: more than 6 words on screen")
    for k, x in enumerate(edit.get("sfx", []), 1):
        if not ((base / x["file"]).is_file() or Path(x["file"]).is_file()):
            stop.append(f"sfx {k}: file not found: {x['file']}")
        elif not 0 <= x["at"] < total:
            stop.append(f"sfx {k}: at {x['at']} is outside the video (0-{total})")
    m = edit.get("music")
    if m:
        mp = base / m["file"] if (base / m["file"]).is_file() else Path(m["file"])
        if not mp.is_file():
            stop.append(f"music: file not found: {m['file']}")
        elif ffprobe(mp)["duration"] - float(m.get("start", 0)) < total:
            stop.append(f"music: only {ffprobe(mp)['duration'] - float(m.get('start', 0)):.1f}s after start, the video is {total}s")
    else:
        warn.append("no music in the edit")
    return shots, stop, warn

def find(base, p):
    return base / p if (base / p).is_file() else Path(p)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("edit")
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--only-check", action="store_true")
    a = ap.parse_args()
    ef = Path(a.edit).resolve()
    base = ef.parent
    edit = json.loads(ef.read_text(encoding="utf-8"))
    W, H = edit.get("size", [1920, 1080])
    fps = edit.get("fps", 60)
    if a.preview:
        W, H = 960, int(round(960 * H / W / 2)) * 2
    shots, stop, warn = check(edit, base)
    total = round(shots[-1]["start"] + shots[-1]["len"], 3) if shots else 0
    print(f"{len(shots)} shots, {total}s, {W}x{H} at {fps} fps")
    for s in shots:
        print(f"  {s['n']:2d}  {s['start']:7.2f}s  len {s['len']:5.2f}  {s['transition']:10s} {s['clip'].name} {s['in']}-{s['out']}"
              + (f" x{s['speed']}" if s["speed"] != 1 else ""))
    for w in warn:
        print("WARN:", w)
    for s in stop:
        print("STOP:", s)
    if stop:
        sys.exit(1)
    if a.only_check:
        print("check passed; nothing rendered")
        return

    out = base / edit.get("out", "renders/edit.mp4")
    if a.preview:
        out = out.with_name(out.stem + "_preview.mp4")
    out.parent.mkdir(parents=True, exist_ok=True)
    enc_name, enc = fast_encoder() if a.preview else ("libx264 crf 14", MASTER_ENC)
    print("encoder:", enc_name)
    tmp = Path(tempfile.mkdtemp(prefix="build_"))
    try:
        # 1. every shot as its own file, already at the output size, frame rate and grade
        parts = []
        for s in shots:
            vf = [f"setpts=(PTS-STARTPTS)/{s['speed']}", f"fps={fps}",
                  f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=lanczos", f"crop={W}:{H}", "setsar=1"]
            for g in (edit.get("grade"), s["grade"]):
                if g:
                    vf.append(g)
            p = tmp / f"s{s['n']:03d}.mp4"
            run(["ffmpeg", "-v", "error", "-y", "-ss", s["in"], "-i", s["clip"], "-t", s["out"] - s["in"], "-an",
                 "-vf", ",".join(vf), "-frames:v", int(round(s["len"] * fps)),
                 "-c:v", "libx264", "-crf", "10", "-preset", "veryfast", "-pix_fmt", "yuv420p", p])
            parts.append(p)
            print(f"\rshot {s['n']}/{len(shots)} rendered", end="", flush=True)
        print()

        # 2. join: cuts with concat, transitions with xfade
        cmd = ["ffmpeg", "-v", "error", "-y"]
        for p in parts:
            cmd += ["-i", p]
        fc = [f"[{i}:v]settb=AVTB[v{i}]" for i in range(len(parts))]
        cur, cur_len = "v0", shots[0]["len"]
        for i, s in enumerate(shots[1:], 1):
            nxt = f"j{i}"
            if s["transition"] == "cut":
                fc.append(f"[{cur}][v{i}]concat=n=2:v=1:a=0,settb=AVTB[{nxt}]")
                cur_len += s["len"]
            else:
                fc.append(f"[{cur}][v{i}]xfade=transition={s['transition']}:duration={s['transition_s']}"
                          f":offset={cur_len - s['transition_s']:.4f},settb=AVTB[{nxt}]")
                cur_len += s["len"] - s["transition_s"]
            cur = nxt

        # 3. text
        for k, x in enumerate(edit.get("text", []), 1):
            tf = tmp / f"t{k}.txt"
            tf.write_text(str(x["text"]), encoding="utf-8")
            f = float(x.get("fade", 0.2))
            S, E = float(x["start"]), float(x["end"])
            alpha = f"if(lt(t,{S + f}),(t-{S})/{f},if(gt(t,{E - f}),({E}-t)/{f},1))" if f > 0 else "1"
            opts = [f"textfile={esc(tf)}", f"fontsize={int(round(H * float(x.get('size_pct', 6)) / 100))}",
                    f"fontcolor={x.get('colour', 'white')}",
                    f"x=w*{float(x.get('x_pct', 50)) / 100}-text_w/2", f"y=h*{float(x.get('y_pct', 50)) / 100}-text_h/2",
                    f"alpha='{alpha}'", f"enable='between(t,{S},{E})'"]
            if x.get("font"):
                opts.append(f"fontfile={esc(find(base, x['font']).resolve())}")
            if x.get("border"):
                opts += [f"borderw={int(round(H * float(x['border']) / 100))}", f"bordercolor={x.get('border_colour', 'black')}"]
            fc.append(f"[{cur}]drawtext={':'.join(opts)}[x{k}]")
            cur = f"x{k}"
        fc.append(f"[{cur}]format=yuv420p[vout]")

        # 4. sound: music bed (or silence) plus SFX at their times
        n_in = len(parts)
        m = edit.get("music")
        if m:
            cmd += ["-ss", float(m.get("start", 0)), "-i", find(base, m["file"])]
            fo = float(m.get("fade_out", 1.5))
            fc.append(f"[{n_in}:a]atrim=0:{total},asetpts=PTS-STARTPTS,aformat=sample_rates=48000:channel_layouts=stereo,"
                      f"volume={float(m.get('gain_db', 0))}dB,afade=t=out:st={max(0, total - fo)}:d={fo}[a0]")
        else:
            cmd += ["-f", "lavfi", "-t", total, "-i", "anullsrc=r=48000:cl=stereo"]
            fc.append(f"[{n_in}:a]anull[a0]")
        mix = ["[a0]"]
        for k, x in enumerate(edit.get("sfx", []), 1):
            cmd += ["-i", find(base, x["file"])]
            fc.append(f"[{n_in + k}:a]aformat=sample_rates=48000:channel_layouts=stereo,volume={float(x.get('gain_db', 0))}dB,"
                      f"adelay={int(round(float(x['at']) * 1000))}:all=1[a{k}]")
            mix.append(f"[a{k}]")
        fc.append(f"{''.join(mix)}amix=inputs={len(mix)}:normalize=0:duration=first,atrim=0:{total}[aout]")
        pre = tmp / "premaster.mp4"
        script = tmp / "graph.txt"
        script.write_text(";\n".join(fc), encoding="utf-8")
        run(cmd + ["-/filter_complex", script, "-map", "[vout]", "-map", "[aout]", "-r", fps, *enc,
                   "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "320k", "-t", total, pre])

        # 5. master the audio, then the QC gate
        if out.exists():
            out.unlink()
        r = subprocess.run([sys.executable, str(HERE / "master_audio.py"), str(pre), str(out)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        print(r.stdout.strip())
        if not out.exists():
            shutil.copyfile(pre, out)
            print("WARN: mastering failed, wrote the unmastered file\n", r.stderr[-400:])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    tl = {"file": str(out), "duration": total, "fps": fps, "size": [W, H],
          "shots": [{"n": s["n"], "start": s["start"], "end": round(s["start"] + s["len"], 3), "clip": s["clip"].name,
                     "in": s["in"], "out": s["out"], "transition": s["transition"]} for s in shots]}
    out.with_suffix(".timeline.json").write_text(json.dumps(tl, indent=1), encoding="utf-8")
    print("out ->", out)
    q = subprocess.run([sys.executable, str(HERE / "qc.py"), str(out), "--out", str(out.with_suffix(".qc.json"))],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    print("--- QC gate ---\n" + "\n".join(l for l in q.stdout.splitlines() if l.startswith(("PASS", "FAIL", "shots", "audio"))))
    if a.preview:
        print("preview only: the 1080p check fails by design. Render without --preview for delivery.")
    sys.exit(q.returncode if not a.preview else 0)

if __name__ == "__main__":
    main()
