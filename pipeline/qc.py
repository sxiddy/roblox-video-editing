"""Stage F: QC gate on the encoded file (also Stage C: measure a reference with --measure-only).

    python pipeline/qc.py <video.mp4> [--out qc.json] [--measure-only]

Checks: format, loudness (-14 LUFS +/-0.5, true peak <= -1.0 dBTP, LRA >= 7), black frames, frame 0
brightness, ends on picture, shot-length rhythm (no three equal in a row, no single spike), repeated
shots (perceptual hash). Exit code 1 if any check fails. The human checks in MASTER_PLAN Stage F
(text placement, side-by-side with references, full watch) still have to be done by eye.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import cv2
import imagehash
import numpy as np
from PIL import Image
from scenedetect import AdaptiveDetector, detect

from config import ffprobe

def ff_stderr(args):
    return subprocess.run(["ffmpeg", "-hide_banner", "-nostats", *map(str, args)], capture_output=True,
                          text=True, encoding="utf-8", errors="replace").stderr

def frame_at(cap, t, fps):
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(t * fps))
    ok, f = cap.read()
    return f if ok else None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--out")
    ap.add_argument("--measure-only", action="store_true", help="for references: print numbers, no pass/fail")
    a = ap.parse_args()
    v = Path(a.video)
    info = ffprobe(v)
    res = {"file": str(v), **info, "checks": {}}
    C = res["checks"]

    if info["has_audio"]:
        s = ff_stderr(["-i", v, "-af", "ebur128=peak=true", "-f", "null", "-"])
        tail = s[s.rfind("Summary:"):]
        g = lambda pat: float(re.search(pat, tail).group(1))
        res.update(lufs=g(r"I:\s+(-?[\d.]+) LUFS"), lra=g(r"LRA:\s+(-?[\d.]+) LU"),
                   true_peak=g(r"Peak:\s+(-?[\d.]+) dBFS"))
        C["loudness_-14_lufs"] = abs(res["lufs"] + 14) <= 0.5
        C["true_peak_<=_-1dbtp"] = res["true_peak"] <= -1.0
        C["lra_>=_7"] = res["lra"] >= 7
    else:
        C["has_audio"] = False

    s = ff_stderr(["-i", v, "-vf", "blackdetect=d=0.2:pix_th=0.08", "-an", "-f", "null", "-"])
    blacks = [(float(x), float(y)) for x, y in re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", s)]
    res["black_ranges"] = blacks
    C["no_black_mid_video"] = not any(b[0] > 0.5 and b[1] < info["duration"] - 0.5 for b in blacks)
    C["no_long_black_tail"] = not any(b[1] >= info["duration"] - 0.1 and b[1] - b[0] > 1.0 for b in blacks)

    cap = cv2.VideoCapture(str(v))
    f0 = frame_at(cap, 0, info["fps"])
    res["frame0_luma"] = round(float(cv2.cvtColor(f0, cv2.COLOR_BGR2GRAY).mean()), 1)
    C["frame0_bright"] = res["frame0_luma"] >= 40

    scenes = detect(str(v), AdaptiveDetector(adaptive_threshold=3.0, min_scene_len=int(info["fps"] * 0.25)))
    shots = [(s[0].seconds, s[1].seconds) for s in scenes] or [(0, info["duration"])]
    lens = [round(e - s, 2) for s, e in shots]
    res["cuts"] = [round(s, 2) for s, _ in shots[1:]]
    res["shot_lengths"] = lens
    res["median_shot"] = round(float(np.median(lens)), 2)
    res["cuts_per_10s"] = round(len(res["cuts"]) / info["duration"] * 10, 1)
    tol = 2 / info["fps"]
    triple = [i for i in range(len(lens) - 2) if abs(lens[i] - lens[i + 1]) <= tol and abs(lens[i + 1] - lens[i + 2]) <= tol]
    C["no_three_equal_shots_in_a_row"] = not triple
    res["equal_triples_at"] = [round(shots[i][0], 2) for i in triple]
    if len(lens) >= 6:
        common = max(np.histogram(lens, bins=np.arange(0, max(lens) + 0.5, 0.5))[0]) / len(lens)
        C["shot_lengths_varied"] = common <= 0.6
    hashes = []
    for s, e in shots:
        f = frame_at(cap, (s + e) / 2, info["fps"])
        hashes.append(imagehash.phash(Image.fromarray(cv2.cvtColor(f, cv2.COLOR_BGR2RGB))) if f is not None else None)
    cap.release()
    repeats = [(round(shots[i][0], 2), round(shots[j][0], 2)) for i in range(len(hashes))
               for j in range(i + 2, len(hashes)) if hashes[i] is not None and hashes[j] is not None
               and hashes[i] - hashes[j] <= 6]
    res["possible_repeats"] = repeats
    C["no_repeated_shots"] = not repeats
    C["at_least_1080p"] = info["height"] >= 1080

    out = Path(a.out) if a.out else v.with_suffix(".qc.json")
    res["checks"] = C = {k: bool(x) for k, x in C.items()}   # numpy bools are not JSON serialisable
    out.write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(f"{v.name}: {info['width']}x{info['height']} {info['fps']}fps {info['duration']:.2f}s")
    if info["has_audio"]:
        print(f"audio: {res['lufs']} LUFS, LRA {res['lra']}, true peak {res['true_peak']} dBTP")
    print(f"shots: {len(lens)}, median {res['median_shot']}s, {res['cuts_per_10s']} cuts/10s, frame0 luma {res['frame0_luma']}")
    if a.measure_only:
        print("measure-only ->", out)
        return
    for k, ok in C.items():
        print(("PASS " if ok else "FAIL ") + k)
    if repeats:
        print("possible repeats (shot start times):", repeats[:8])
    print("report ->", out)
    sys.exit(0 if all(C.values()) else 1)

if __name__ == "__main__":
    main()
