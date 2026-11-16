"""Section 7 step 6: master the final mix. Static gain to -14 LUFS, limiter ceiling 0.78, then
measure the ENCODED file (never one-pass loudnorm).

    python pipeline/master_audio.py <in: video or audio> <out: .mp4/.mov/.m4a/.wav> [--lufs -14]

If the input has video it is stream-copied; only the audio is re-encoded (AAC 320k, 48 kHz).
The limiter costs a little loudness, so the gain is corrected from the measured output (max 4
passes). Exit code 1 if the encoded file misses -14 +/-0.5 LUFS or true peak > -1.0 dBTP.
"""
import argparse
import sys
from pathlib import Path

from config import ffprobe, loudness, run

CEILING = 0.78   # about -2.2 dBFS sample peak, so AAC overshoot still lands <= -1.0 dBTP

def encode(src, dst, gain_db, has_video):
    # Limit at 192 kHz so inter-sample peaks are caught, then return to 48 kHz.
    af = (f"volume={gain_db:.2f}dB,aresample=192000,"
          f"alimiter=limit={CEILING}:attack=5:release=50:level=false,aresample=48000")
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", src, "-af", af]
    if dst.suffix.lower() == ".wav":
        cmd += ["-vn", "-c:a", "pcm_s24le"]
    else:
        cmd += (["-c:v", "copy"] if has_video else ["-vn"]) + ["-c:a", "aac", "-b:a", "320k"]
        if dst.suffix.lower() in (".mp4", ".mov", ".m4a"):
            cmd += ["-movflags", "+faststart"]
    run(cmd + [dst])

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--lufs", type=float, default=-14.0)
    a = ap.parse_args()
    src, dst = Path(a.src), Path(a.dst)
    if src.resolve() == dst.resolve():
        sys.exit("STOP: output must be a different file from the input")
    info = ffprobe(src)
    if not info["has_audio"]:
        sys.exit("STOP: input has no audio")
    has_video = "width" in info and dst.suffix.lower() in (".mp4", ".mov", ".mkv")
    before = loudness(src)
    print(f"in : {before['lufs']} LUFS, LRA {before['lra']}, true peak {before['true_peak']} dBTP")
    gain = a.lufs - before["lufs"]
    for n in range(1, 5):
        encode(src, dst, gain, has_video)
        m = loudness(dst)
        print(f"pass {n}: gain {gain:+.2f} dB -> {m['lufs']} LUFS, true peak {m['true_peak']} dBTP")
        if abs(m["lufs"] - a.lufs) <= 0.2:
            break
        gain += a.lufs - m["lufs"]
    ok_l, ok_p = abs(m["lufs"] - a.lufs) <= 0.5, m["true_peak"] <= -1.0
    print(("PASS " if ok_l else "FAIL ") + f"loudness {a.lufs} +/-0.5 LUFS")
    print(("PASS " if ok_p else "FAIL ") + "true peak <= -1.0 dBTP")
    if before["lra"] - m["lra"] > 2:
        print(f"WARN: limiter flattened dynamics (LRA {before['lra']} -> {m['lra']}); "
              "lower the mix peaks instead of leaning on the limiter")
    print("out ->", dst)
    sys.exit(0 if ok_l and ok_p else 1)

if __name__ == "__main__":
    main()
