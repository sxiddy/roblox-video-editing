"""Section 3: depth maps with Depth-Anything-V2 (text behind objects, parallax, depth fog/blur).
Run with the GPU env:

    "C:/Users/Siddharth D/Projects/media-gpu/Scripts/python.exe" pipeline/depth.py <image or video> --out <file> [--model small|base] [--start s --end s]

Image in -> 16-bit grey PNG. Video in -> grey .mp4 with the same size, frame rate and length.
White = near, black = far. Depth is relative (not metres); video values are smoothed over time so
the map does not flicker.
"""
import argparse
import os
import sys
from pathlib import Path

import cv2
os.environ.setdefault("TQDM_DISABLE", "1")          # keep model progress bars out of the log
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

import numpy as np
import torch

from config import VIDEO_EXT, ffprobe, gray_writer, need_gpu

MODELS = {"small": "depth-anything/Depth-Anything-V2-Small-hf", "base": "depth-anything/Depth-Anything-V2-Base-hf"}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", choices=list(MODELS), default="small")
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--end", type=float)
    ap.add_argument("--batch", type=int, default=4)
    a = ap.parse_args()
    dev = need_gpu()
    from transformers import AutoImageProcessor, AutoModelForDepthEstimation
    proc = AutoImageProcessor.from_pretrained(MODELS[a.model])
    model = AutoModelForDepthEstimation.from_pretrained(MODELS[a.model], dtype=torch.float16).to(dev).eval()

    def infer(frames_bgr):
        """List of BGR frames -> float32 array (n, H, W), raw relative depth (bigger = nearer)."""
        h, w = frames_bgr[0].shape[:2]
        x = proc(images=[cv2.cvtColor(f, cv2.COLOR_BGR2RGB) for f in frames_bgr], return_tensors="pt")
        with torch.inference_mode():
            d = model(pixel_values=x["pixel_values"].to(dev, torch.float16)).predicted_depth
            d = torch.nn.functional.interpolate(d[:, None].float(), size=(h, w), mode="bicubic", align_corners=False)
        return d[:, 0].cpu().numpy()

    src, out = Path(a.src), Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if src.suffix.lower() not in VIDEO_EXT:
        img = cv2.imdecode(np.fromfile(str(src), dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            sys.exit("STOP: cannot read " + str(src))
        d = infer([img])[0]
        lo, hi = np.percentile(d, 0.5), np.percentile(d, 99.5)
        d16 = (np.clip((d - lo) / max(hi - lo, 1e-6), 0, 1) * 65535).astype(np.uint16)
        cv2.imencode(".png", d16)[1].tofile(str(out.with_suffix(".png")))
        print("out ->", out.with_suffix(".png"))
        return

    info = ffprobe(src)
    fps, w, h = info["fps"], info["width"], info["height"]
    cap = cv2.VideoCapture(str(src))
    first = int(round(a.start * fps))
    last = int(round(min(a.end or info["duration"], info["duration"]) * fps))
    cap.set(cv2.CAP_PROP_POS_FRAMES, first)
    wr = gray_writer(out, w, h, fps)
    lo = hi = None
    n, batch = 0, []

    def flush():
        nonlocal lo, hi, n
        for d in infer(batch):
            l, u = np.percentile(d, 0.5), np.percentile(d, 99.5)
            lo, hi = (l, u) if lo is None else (0.9 * lo + 0.1 * l, 0.9 * hi + 0.1 * u)   # smooth the range
            wr.stdin.write((np.clip((d - lo) / max(hi - lo, 1e-6), 0, 1) * 255).astype(np.uint8).tobytes())
            n += 1
        batch.clear()

    for _ in range(max(0, last - first)):
        ok, f = cap.read()
        if not ok:
            break
        batch.append(f)
        if len(batch) == a.batch:
            flush()
            print(f"\r{n}/{last - first} frames", end="", flush=True)
    if batch:
        flush()
    cap.release()
    wr.stdin.close()
    if wr.wait() != 0 or n == 0:
        sys.exit("\nSTOP: writing the depth video failed")
    print(f"\n{n} frames, {w}x{h} at {fps} fps, peak VRAM {torch.cuda.max_memory_allocated() / 2**30:.1f} GB")
    print("out ->", out)

if __name__ == "__main__":
    main()
