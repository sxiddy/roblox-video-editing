"""Section 3: clean slow motion with RIFE (GPU, Vulkan). Makes real in-between frames.

    python pipeline/slowmo.py <clip> --out <slow.mp4> [--start 12.0 --end 13.5] [--factor 4]

Takes the chosen part of the clip, multiplies its frame count by --factor (2, 4 or 8) with model
rife-v4.6 and plays it back at the source frame rate, so 1 s becomes --factor seconds. No audio.
Keep the slowed part short (under 3 s of source); RIFE smears fast particles and HUD text.
Output is a libx264 CRF 14 intermediate, not a delivery file.
"""
import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from config import RIFE, RIFE_MODEL, ffprobe, run

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("clip")
    ap.add_argument("--out", required=True)
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--end", type=float)
    ap.add_argument("--factor", type=int, default=4, choices=[2, 4, 8])
    ap.add_argument("--keep-frames", action="store_true")
    a = ap.parse_args()
    if not RIFE.is_file() or not RIFE_MODEL.is_dir():
        sys.exit(f"STOP: RIFE not found at {RIFE} (see setup/INSTALL.md section 3)")
    info = ffprobe(a.clip)
    end = min(a.end if a.end else info["duration"], info["duration"])
    if end - a.start <= 0:
        sys.exit("STOP: --end must be after --start")
    if end - a.start > 6:
        print(f"WARN: {end - a.start:.1f} s of source is long for slow motion; this will take a while")
    tmp = Path(tempfile.mkdtemp(prefix="slowmo_"))
    fin, fout = tmp / "in", tmp / "out"
    fin.mkdir(), fout.mkdir()
    try:
        run(["ffmpeg", "-v", "error", "-ss", a.start, "-i", a.clip, "-t", end - a.start, "-an",
             "-fps_mode", "cfr", fin / "%06d.png"])
        n = len(list(fin.glob("*.png")))
        if n < 2:
            sys.exit("STOP: fewer than 2 frames in that range")
        target = n * a.factor
        # -n sets the exact output frame count (v4 models only); the GPU is used by default (-g 0).
        r = subprocess.run([str(RIFE), "-i", str(fin), "-o", str(fout), "-m", str(RIFE_MODEL),
                            "-n", str(target), "-f", "%06d.png"], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        made = len(list(fout.glob("*.png")))
        if made < target - a.factor:
            sys.exit(f"STOP: RIFE made {made} of {target} frames.\n{r.stderr[-800:]}")
        out = Path(a.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        run(["ffmpeg", "-v", "error", "-y", "-framerate", info["fps"], "-i", fout / "%06d.png",
             "-c:v", "libx264", "-crf", "14", "-preset", "medium", "-pix_fmt", "yuv420p", out])
        o = ffprobe(out)
        print(f"{n} frames -> {made} frames at {info['fps']} fps: {end - a.start:.2f} s became {o['duration']:.2f} s")
        print("out ->", out)
    finally:
        if a.keep_frames:
            print("frames kept in", tmp)
        else:
            shutil.rmtree(tmp, ignore_errors=True)

if __name__ == "__main__":
    main()
