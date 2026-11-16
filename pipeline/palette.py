"""Stage A2 step 2: palette facts from footage or brand material.

    python pipeline/palette.py <videos / images / folders...> --out jobs/<job>/style/footage [--k 5]

Writes <out>.json (k dominant colours as hex with their share, mean brightness and saturation, a
look label) and <out>.png (swatch strip). Run it once on the clips and once on the brand material.
The look label is a rough threshold, a starting point for STYLE.md, not a decision.
"""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from config import VIDEO_EXT

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}

def frames(path, max_frames=40):
    """Small BGR frames: the image itself, or up to max_frames spread evenly through a video."""
    if path.suffix.lower() in IMAGE_EXT:
        img = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)   # unicode-safe
        return [img] if img is not None else []
    cap = cv2.VideoCapture(str(path))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    out = []
    for i in np.linspace(0, max(0, total - 1), min(max_frames, max(1, total))).astype(int):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(i))
        ok, f = cap.read()
        if ok:
            out.append(f)
    cap.release()
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("--out", required=True, help="output path without extension")
    ap.add_argument("--k", type=int, default=5)
    a = ap.parse_args()
    files = []
    for p in map(Path, a.inputs):
        files += sorted(f for f in p.rglob("*") if f.suffix.lower() in VIDEO_EXT | IMAGE_EXT) if p.is_dir() else [p]
    px = []
    for f in files:
        for fr in frames(f):
            px.append(cv2.resize(fr, (96, 54), interpolation=cv2.INTER_AREA).reshape(-1, 3))
    if not px:
        raise SystemExit("STOP: no frames read from the inputs")
    bgr = np.concatenate(px).astype(np.uint8)
    hsv = cv2.cvtColor(bgr[None], cv2.COLOR_BGR2HSV)[0]
    lab = cv2.cvtColor(bgr[None], cv2.COLOR_BGR2LAB)[0].astype(np.float32)   # cluster in Lab: closer to the eye
    cv2.setRNGSeed(0)
    _, labels, centres = cv2.kmeans(lab, a.k, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.5),
                                    3, cv2.KMEANS_PP_CENTERS)
    share = np.bincount(labels.ravel(), minlength=a.k) / len(labels)
    cb = cv2.cvtColor(centres.clip(0, 255).astype(np.uint8)[None], cv2.COLOR_LAB2BGR)[0]
    order = np.argsort(share)[::-1]
    colours = [{"hex": "#%02x%02x%02x" % (int(cb[i][2]), int(cb[i][1]), int(cb[i][0])),
                "share": round(float(share[i]), 3)} for i in order]
    luma = float(cv2.cvtColor(bgr[None], cv2.COLOR_BGR2GRAY).mean())
    sat = float(hsv[:, 1].mean())
    look = "dark moody" if luma < 70 else "bright cartoon" if (luma > 110 and sat > 110) else "natural"
    res = {"inputs": [str(f) for f in files], "frames": len(px), "colours": colours,
           "mean_luma_0_255": round(luma, 1), "mean_saturation_0_255": round(sat, 1), "look_guess": look}
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.with_suffix(".json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    strip = np.zeros((120, 1000, 3), np.uint8)
    x = 0
    for i in order:
        w = int(round(share[i] * 1000))
        strip[:, x:x + w] = cb[i]
        x += w
    strip[:, x:] = cb[order[-1]]
    cv2.imencode(".png", strip)[1].tofile(str(out.with_suffix(".png")))
    print(f"{len(files)} files, {len(px)} frames")
    for c in colours:
        print(f"  {c['hex']}  {c['share'] * 100:4.1f}%")
    print(f"brightness {luma:.0f}/255, saturation {sat:.0f}/255 -> {look} (guess)")
    print("wrote", out.with_suffix(".json"), "and", out.with_suffix(".png"))

if __name__ == "__main__":
    main()
