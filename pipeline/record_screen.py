"""Stage B step 4: record the screen for our own Roblox (or any game) shots.

    python pipeline/record_screen.py --out jobs/<job>/clips/shot01.mp4 [--seconds 20] [--fps 60] [--delay 5] [--monitor 0]

Records the whole monitor, video only (game audio is not used: sound is rebuilt in the edit).
Without --seconds it records until you press Q in this window. --delay gives time to click back
into the game. Put the game in fullscreen at the monitor's native size first.
Minecraft shots are better made with Flashback replays; use this for Roblox and Studio.
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

from config import fast_encoder, ffprobe

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--seconds", type=float)
    ap.add_argument("--fps", type=int, default=60)
    ap.add_argument("--delay", type=float, default=5)
    ap.add_argument("--monitor", type=int, default=0)
    a = ap.parse_args()
    out = Path(a.out)
    if out.exists():
        sys.exit(f"STOP: {out} exists; pick a new name so no take is overwritten")
    out.parent.mkdir(parents=True, exist_ok=True)
    enc_name, enc = fast_encoder()
    print("encoder:", enc_name, flush=True)
    for s in range(int(a.delay), 0, -1):
        print(f"recording in {s}...", flush=True)
        time.sleep(1)
    cmd = ["ffmpeg", "-hide_banner", "-v", "error", "-stats", "-f", "lavfi", "-i",
           f"ddagrab=output_idx={a.monitor}:framerate={a.fps}:draw_mouse=0,hwdownload,format=bgra"]
    if a.seconds:
        cmd += ["-t", str(a.seconds)]
    cmd += [*enc, "-pix_fmt", "yuv420p", "-g", str(a.fps), str(out)]
    print("RECORDING" + (f" for {a.seconds} s" if a.seconds else " (press Q here to stop)"), flush=True)
    r = subprocess.run(cmd)
    if r.returncode != 0 or not out.exists():
        sys.exit("STOP: capture failed (needs Windows 10+ and ffmpeg with the ddagrab filter)")
    i = ffprobe(out)
    print(f"\n{out}: {i['width']}x{i['height']} {i['fps']} fps, {i['duration']:.1f} s")
    if i["height"] < 1080:
        print("WARN: under 1080p; raise the game/monitor resolution")

if __name__ == "__main__":
    main()
