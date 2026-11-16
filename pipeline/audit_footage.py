"""Stage B: catalogue every clip.

    python pipeline/audit_footage.py <clips_dir_or_files...> --out jobs/<job>/footage

Writes footage.json (per clip: size, fps, duration, internal cuts, per-second motion / luma /
sharpness, flags, best 3 s windows) and one contact sheet per clip (1 frame per second).
"""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np
from scenedetect import ContentDetector, detect

from config import VIDEO_EXT, ffprobe, run

def per_second(path, fps, duration):
    """Sample 2 frames a second; return per-second motion, luma, sharpness lists."""
    cap = cv2.VideoCapture(str(path))
    step = max(1, int(round(fps / 2)))
    prev, rows, i = None, [], 0
    while True:
        ok = cap.grab()
        if not ok:
            break
        if i % step == 0:
            ok, frame = cap.retrieve()
            if not ok:
                break
            small = cv2.resize(frame, (320, 180), interpolation=cv2.INTER_AREA)
            g = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            sharp = float(cv2.Laplacian(cv2.resize(frame, (640, 360)), cv2.CV_64F).var())
            motion = 0.0
            if prev is not None:
                flow = cv2.calcOpticalFlowFarneback(prev, g, None, 0.5, 3, 15, 3, 5, 1.2, 0)
                motion = float(np.linalg.norm(flow, axis=2).mean())
            rows.append((i / fps, motion, float(g.mean()), sharp))
            prev = g
        i += 1
    cap.release()
    secs = int(np.ceil(duration))
    out = {"motion": [], "luma": [], "sharp": []}
    for s in range(secs):
        r = [x for x in rows if s <= x[0] < s + 1]
        for k, idx in (("motion", 1), ("luma", 2), ("sharp", 3)):
            out[k].append(round(float(np.mean([x[idx] for x in r])), 2) if r else 0.0)
    return out

def best_windows(motion, luma, win=3, n=3):
    """Top n non-overlapping windows by motion, skipping dark ones."""
    scores = []
    for s in range(0, max(1, len(motion) - win + 1)):
        if np.mean(luma[s:s + win]) < 40:
            continue
        scores.append((float(np.mean(motion[s:s + win])), s))
    picked = []
    for sc, s in sorted(scores, reverse=True):
        if all(abs(s - p["start"]) >= win for p in picked):
            picked.append({"start": s, "end": s + win, "motion": round(sc, 2)})
        if len(picked) == n:
            break
    return picked

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    (out / "sheets").mkdir(parents=True, exist_ok=True)
    files = []
    for p in map(Path, a.inputs):
        files += sorted(f for f in p.rglob("*") if f.suffix.lower() in VIDEO_EXT) if p.is_dir() else [p]
    clips = []
    for n, f in enumerate(files, 1):
        info = ffprobe(f)
        stats = per_second(f, info["fps"], info["duration"])
        cuts = [round(s[1].seconds, 2) for s in detect(str(f), ContentDetector(threshold=27))][:-1]
        luma, motion = np.mean(stats["luma"]), np.mean(stats["motion"])
        flags = []
        if luma < 45:
            flags.append("dark")
        if motion < 0.3:
            flags.append("static")
        if np.mean(stats["sharp"]) < 60:
            flags.append("soft")
        if info["height"] < 1080:
            flags.append("low_res")
        sheet = out / "sheets" / f"{n:03d}_{f.stem}.jpg"
        cols = min(10, max(1, int(np.ceil(info["duration"]))))
        run(["ffmpeg", "-v", "error", "-y", "-i", f, "-vf",
             f"fps=1,scale=320:-1,tile={cols}x{int(np.ceil(np.ceil(info['duration']) / cols))}",
             "-frames:v", "1", "-q:v", "4", sheet])
        clips.append({"id": n, "file": str(f), **info, "internal_cuts": cuts,
                      "mean_motion": round(float(motion), 2), "mean_luma": round(float(luma), 1),
                      "flags": flags, "best_windows": best_windows(stats["motion"], stats["luma"]),
                      "per_second": stats, "sheet": str(sheet), "tags": []})
        print(f"{n:03d} {f.name:40s} {info['duration']:6.1f}s motion {motion:5.2f} luma {luma:5.1f} {','.join(flags)}")
    (out / "footage.json").write_text(json.dumps(clips, indent=1), encoding="utf-8")
    usable = [c for c in clips if "dark" not in c["flags"]]
    print(f"\n{len(clips)} clips, {len(usable)} usable (not dark), "
          f"{sum(c['duration'] for c in usable):.0f}s usable. Wrote {out / 'footage.json'}")
    print("Next: open the sheets, fill each clip's 'tags' (establishing, hero, detail, proof, "
          "character, transition, ending) and check coverage against the theme's must-have shots.")

if __name__ == "__main__":
    main()
