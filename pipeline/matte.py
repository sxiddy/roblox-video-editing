"""Cut the main subject out of its background with BiRefNet (torch, GPU). Run with the GPU env:

    "C:/Users/Siddharth D/Projects/media-gpu/Scripts/python.exe" pipeline/matte.py <image or video> --out <file> [--start s --end s]

Image in -> <out>.png (RGBA cutout) and <out>_mask.png. Video in -> grey matte .mp4 (white = subject)
with the same size, frame rate and length; combine it later with ffmpeg `alphamerge`.
BiRefNet picks the most salient subject by itself. To choose a specific object, or when it picks
the wrong one, use mask_track.py (SAM2) instead. Always check edges for halos before using a cutout.
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

REPO = "ZhengPeng7/BiRefNet"
SIZE = 1024
MEAN = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1)
STD = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--out", required=True)
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--end", type=float)
    a = ap.parse_args()
    dev = need_gpu()
    from transformers import AutoModelForImageSegmentation
    model = AutoModelForImageSegmentation.from_pretrained(REPO, trust_remote_code=True).to(dev).eval().half()
    mean, std = MEAN.to(dev), STD.to(dev)

    def infer(bgr):
        """BGR frame -> uint8 matte (H, W), 255 = subject."""
        h, w = bgr.shape[:2]
        rgb = cv2.cvtColor(cv2.resize(bgr, (SIZE, SIZE), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB)
        x = torch.from_numpy(rgb).to(dev).permute(2, 0, 1)[None].float() / 255
        with torch.inference_mode():
            p = model(((x - mean) / std).half())[-1].sigmoid().float()
            p = torch.nn.functional.interpolate(p, size=(h, w), mode="bilinear", align_corners=False)
        return (p[0, 0].clamp(0, 1) * 255).round().byte().cpu().numpy()

    src, out = Path(a.src), Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if src.suffix.lower() not in VIDEO_EXT:
        img = cv2.imdecode(np.fromfile(str(src), dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            sys.exit("STOP: cannot read " + str(src))
        m = infer(img)
        cut, mask = out.with_suffix(".png"), out.with_name(out.stem + "_mask.png")
        cv2.imencode(".png", np.dstack([img, m]))[1].tofile(str(cut))
        cv2.imencode(".png", m)[1].tofile(str(mask))
        print(f"subject covers {(m > 127).mean() * 100:.1f}% of the frame")
        print("out ->", cut, "and", mask)
        return

    info = ffprobe(src)
    fps, w, h = info["fps"], info["width"], info["height"]
    cap = cv2.VideoCapture(str(src))
    first = int(round(a.start * fps))
    last = int(round(min(a.end or info["duration"], info["duration"]) * fps))
    cap.set(cv2.CAP_PROP_POS_FRAMES, first)
    wr = gray_writer(out, w, h, fps)
    n, area = 0, []
    for _ in range(max(0, last - first)):
        ok, f = cap.read()
        if not ok:
            break
        m = infer(f)
        wr.stdin.write(m.tobytes())
        area.append(float((m > 127).mean()))
        n += 1
        if n % 10 == 0:
            print(f"\r{n}/{last - first} frames", end="", flush=True)
    cap.release()
    wr.stdin.close()
    if wr.wait() != 0 or n == 0:
        sys.exit("\nSTOP: writing the matte video failed")
    print(f"\n{n} frames, subject covers {np.mean(area) * 100:.1f}% on average "
          f"(min {min(area) * 100:.1f}%, max {max(area) * 100:.1f}%), "
          f"peak VRAM {torch.cuda.max_memory_allocated() / 2**30:.1f} GB")
    if min(area) < 0.002:
        print("WARN: some frames have no subject; check the matte before using it")
    print("out ->", out)

if __name__ == "__main__":
    main()
