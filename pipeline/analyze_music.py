"""Stage D: measure a song and score it against the plan's music rules. Run with the GPU env:

    "C:/Users/Siddharth D/Projects/media-gpu/Scripts/python.exe" pipeline/analyze_music.py <song> [--target 50] [--bpm 80 110] [--out music.json]

Prints BPM, beats/downbeats, energy sections, drops, a score out of 6, and the song window that puts
the biggest drop at ~45% of the target runtime.
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

import librosa
import numpy as np

from config import need_gpu

def loudness(path):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af",
                        "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace").stderr
    tail = r[r.rfind("Summary:"):]
    g = lambda pat: float(re.search(pat, tail).group(1))
    return {"lufs": g(r"I:\s+(-?[\d.]+) LUFS"), "lra": g(r"LRA:\s+(-?[\d.]+) LU"),
            "true_peak": g(r"Peak:\s+(-?[\d.]+) dBFS")}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("song")
    ap.add_argument("--target", type=float, default=50, help="video runtime in seconds")
    ap.add_argument("--bpm", type=float, nargs=2, default=None, help="theme BPM range")
    ap.add_argument("--out")
    a = ap.parse_args()
    dev = need_gpu()
    from beat_this.inference import Audio2Beats
    # Decode through ffmpeg so every container works (soundfile cannot read .m4a).
    sr = 22050
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(a.song), "-vn", "-ac", "1", "-ar", str(sr),
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    y = np.frombuffer(raw, dtype=np.float32).copy()
    if len(y) < sr:
        raise SystemExit(f"STOP: no audio decoded from {a.song}")
    beats, downbeats = Audio2Beats(checkpoint_path="final0", device=dev)(y, sr)
    beats, downbeats = np.asarray(beats), np.asarray(downbeats)
    bpm = float(60 / np.median(np.diff(beats)))
    dur = len(y) / sr
    hop = sr // 2                                           # 0.5 s energy steps
    rms = librosa.feature.rms(y=y, frame_length=hop * 2, hop_length=hop)[0]
    db = 20 * np.log10(np.maximum(rms, 1e-6))
    t = np.arange(len(db)) * 0.5
    win = 8                                                 # 4 s before vs 4 s after
    jump = np.array([db[i:i + win].mean() - db[max(0, i - win):i].mean() if i >= win and i + win <= len(db)
                     else 0 for i in range(len(db))])
    drops = []
    for i in np.argsort(jump)[::-1]:
        if jump[i] < 4:
            break
        tt = float(downbeats[np.argmin(np.abs(downbeats - t[i]))]) if len(downbeats) else float(t[i])
        if all(abs(tt - d["time"]) > 8 for d in drops):
            drops.append({"time": round(tt, 2), "jump_db": round(float(jump[i]), 1)})
        if len(drops) == 4:
            break
    loud = float(np.percentile(db, 90))
    quiet = [(float(t[i])) for i in range(len(db)) if db[i] < loud - 8]
    quiet_share = len(quiet) / len(db)
    lm = loudness(a.song)

    best = drops[0] if drops else None
    start = 0.0
    if best:
        start = max(0.0, best["time"] - 0.45 * a.target)
        start = float(downbeats[np.argmin(np.abs(downbeats - start))]) if len(downbeats) else start
    end = min(dur, start + a.target)
    if len(downbeats):
        end = float(downbeats[np.argmin(np.abs(downbeats - end))])

    checks = {
        "bpm_in_range": (a.bpm is None) or (a.bpm[0] <= bpm <= a.bpm[1]) or (a.bpm[0] <= bpm / 2 <= a.bpm[1])
                        or (a.bpm[0] <= bpm * 2 <= a.bpm[1]),
        "clear_drop_6db": bool(best and best["jump_db"] >= 6),
        "has_quiet_section": quiet_share >= 0.08,
        "long_enough": dur >= a.target + 5,
        "dynamic_lra_8": lm["lra"] >= 8,
        "drop_fits_window": bool(best and best["time"] - start >= 6 and end - best["time"] >= 8),
    }
    res = {"file": str(a.song), "duration": round(dur, 2), "bpm": round(bpm, 1),
           "beats": [round(float(b), 3) for b in beats], "downbeats": [round(float(b), 3) for b in downbeats],
           "energy_db_per_half_second": [round(float(x), 1) for x in db],
           "drops": drops, "quiet_share": round(quiet_share, 2), **lm,
           "suggested_window": {"start": round(start, 2), "end": round(end, 2),
                                "drop_at_video_time": round(best["time"] - start, 2) if best else None},
           "checks": checks, "score": int(sum(checks.values())),
           "licence": "FILL IN", "credit_line": "FILL IN", "source_url": "FILL IN"}
    out = Path(a.out) if a.out else Path(a.song).with_suffix(".music.json")
    out.write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(f"{Path(a.song).name}: {dur:.0f}s, {bpm:.0f} BPM, {len(downbeats)} bars, "
          f"{lm['lufs']} LUFS, LRA {lm['lra']}")
    print("drops:", drops)
    print("window:", res["suggested_window"])
    for k, v in checks.items():
        print(("PASS " if v else "FAIL ") + k)
    print(f"score {res['score']}/6 -> {out}")

if __name__ == "__main__":
    main()
