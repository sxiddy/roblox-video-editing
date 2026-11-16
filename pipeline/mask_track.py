"""Section 3: follow one chosen object through a shot with SAM2 (object wipes, text behind a
subject, 9:16 reframing). Run with the GPU env:

    "C:/Users/Siddharth D/Projects/media-gpu/Scripts/python.exe" pipeline/mask_track.py <clip> --out <matte.mp4> --start 12.0 --end 14.5 --point 960,540 [--point x,y ...] [--neg x,y ...] [--box x1,y1,x2,y2]

Points and boxes are in source pixels on the FIRST frame of the range (get them by looking at that
frame: `ffmpeg -ss 12.0 -i clip -frames:v 1 f.png`). --point marks the object, --neg marks what
to leave out. Writes the matte video (white = object, same size / frame rate as the source range)
and <out>.track.json with a per-frame box, centre and area, used for subject-tracked reframing.
One shot at a time: SAM2 loses the object across a cut. Keep ranges under about 10 s (6 GB VRAM).
"""
import argparse
import os
import json
import shutil
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("TQDM_DISABLE", "1")          # keep model progress bars out of the log
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

import numpy as np
import torch

from config import ffprobe, gray_writer, need_gpu, run

MODEL = "facebook/sam2.1-hiera-small"
WORK_W = 1280   # frames are tracked at this width; the matte is scaled back to the source size

def pairs(vals, n):
    return [[float(x) for x in v.split(",")] for v in vals] if vals else []

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("clip")
    ap.add_argument("--out", required=True)
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--end", type=float)
    ap.add_argument("--point", action="append")
    ap.add_argument("--neg", action="append")
    ap.add_argument("--box")
    a = ap.parse_args()
    if not a.point and not a.box:
        ap.error("give at least one --point x,y or a --box x1,y1,x2,y2")
    dev = need_gpu()
    info = ffprobe(a.clip)
    W, H, fps = info["width"], info["height"], info["fps"]
    end = min(a.end or info["duration"], info["duration"])
    if end - a.start > 12:
        print(f"WARN: {end - a.start:.1f} s is long for 6 GB VRAM; split the shot if this runs out of memory")
    k = min(1.0, WORK_W / W)
    w, h = int(round(W * k / 2)) * 2, int(round(H * k / 2)) * 2
    tmp = Path(tempfile.mkdtemp(prefix="sam2_"))
    try:
        run(["ffmpeg", "-v", "error", "-ss", a.start, "-i", a.clip, "-t", end - a.start, "-an",
             "-vf", f"scale={w}:{h}", "-q:v", "2", "-start_number", "0", tmp / "%05d.jpg"])
        n = len(list(tmp.glob("*.jpg")))
        if n == 0:
            sys.exit("STOP: no frames in that range")
        from sam2.sam2_video_predictor import SAM2VideoPredictor
        pred = SAM2VideoPredictor.from_pretrained(MODEL, device=dev)
        pos, neg = pairs(a.point, 2), pairs(a.neg, 2)
        pts = np.array(pos + neg, dtype=np.float32) * k if pos or neg else None
        lab = np.array([1] * len(pos) + [0] * len(neg), dtype=np.int32) if pos or neg else None
        box = np.array([float(x) for x in a.box.split(",")], dtype=np.float32) * k if a.box else None
        out = Path(a.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        wr = gray_writer(out, w, h, fps, out_size=(W, H))
        track = []
        with torch.inference_mode(), torch.autocast("cuda", dtype=torch.bfloat16):
            state = pred.init_state(video_path=str(tmp), offload_video_to_cpu=True, offload_state_to_cpu=True)
            pred.add_new_points_or_box(state, frame_idx=0, obj_id=1, points=pts, labels=lab, box=box)
            for i, _, logits in pred.propagate_in_video(state):
                m = (logits[0, 0] > 0).cpu().numpy()
                wr.stdin.write((m * 255).astype(np.uint8).tobytes())
                row = {"frame": int(i), "t": round(a.start + i / fps, 4), "area_pct": round(float(m.mean()) * 100, 3)}
                if m.any():
                    ys, xs = np.nonzero(m)
                    x1, y1, x2, y2 = xs.min() / k, ys.min() / k, (xs.max() + 1) / k, (ys.max() + 1) / k
                    row.update(box=[round(float(v), 1) for v in (x1, y1, x2, y2)],
                               centre=[round(float(xs.mean() / k), 1), round(float(ys.mean() / k), 1)])
                track.append(row)
                if i % 10 == 0:
                    print(f"\r{i + 1}/{n} frames", end="", flush=True)
        wr.stdin.close()
        if wr.wait() != 0:
            sys.exit("\nSTOP: writing the matte video failed")
        lost = [r["frame"] for r in track if "box" not in r]
        tj = out.with_suffix(".track.json")
        tj.write_text(json.dumps({"clip": str(a.clip), "start": a.start, "end": round(end, 4), "fps": fps,
                                  "width": W, "height": H, "frames": track}, indent=1), encoding="utf-8")
        areas = [r["area_pct"] for r in track]
        print(f"\n{len(track)} frames, object covers {np.mean(areas):.1f}% on average "
              f"(first {areas[0]:.1f}%, last {areas[-1]:.1f}%), "
              f"peak VRAM {torch.cuda.max_memory_allocated() / 2**30:.1f} GB")
        if lost:
            print(f"WARN: object lost on {len(lost)} frames (first at frame {lost[0]}); "
                  "add points, or split the range at a cut")
        print("out ->", out, "and", tj)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

if __name__ == "__main__":
    main()
