"""Loudness-normalise the SFX library into a sibling folder; the originals are not touched.

    python pipeline/sfx_normalize.py [--lufs -18]

Writes media-library/sfx_norm/<category>/<name>.wav (48 kHz) and sfx_norm/report.json. Gain is
capped so the true peak stays <= -1 dBTP. Sounds too short for a LUFS reading are peak-normalised
to -3 dBFS. Flags in the report (silent, too_short, peak_capped, long) say what to check by ear.
"""
import argparse
import json
import subprocess
import sys

from config import SFX, ffprobe, loudness

AUDIO_EXT = {".mp3", ".wav", ".ogg", ".flac", ".m4a"}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lufs", type=float, default=-18.0)
    a = ap.parse_args()
    dst_root = SFX.parent / "sfx_norm"
    files = sorted(f for f in SFX.rglob("*") if f.suffix.lower() in AUDIO_EXT)
    report = []
    for n, f in enumerate(files, 1):
        row = {"file": str(f), "flags": []}
        try:
            row["duration"] = round(ffprobe(f)["duration"], 2)
            m = loudness(f)
            row.update(lufs_in=m["lufs"], peak_in=m["true_peak"])
            if m["true_peak"] < -60:
                row["flags"].append("silent")
                report.append(row)
                continue
            if m["lufs"] < -60:                       # too short for an integrated reading
                gain = -3.0 - m["true_peak"]
                row["flags"].append("too_short")
            else:
                gain = a.lufs - m["lufs"]
                if m["true_peak"] + gain > -1.0:
                    gain = -1.0 - m["true_peak"]
                    row["flags"].append("peak_capped")
            if row["duration"] > 30:
                row["flags"].append("long")
            out = (dst_root / f.relative_to(SFX)).with_suffix(".wav")
            out.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(f), "-af", f"volume={gain:.2f}dB",
                            "-ar", "48000", "-c:a", "pcm_s16le", str(out)], check=True)
            row.update(gain_db=round(gain, 2), out=str(out))
        except Exception as e:                        # one bad file must not stop the batch
            row["flags"].append("error")
            row["error"] = str(e)[:200]
        report.append(row)
        print(f"{n:3d}/{len(files)} {f.name[:50]:50s} {row.get('gain_db', '-'):>7} dB {','.join(row['flags'])}", flush=True)
    dst_root.mkdir(parents=True, exist_ok=True)
    (dst_root / "report.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    bad = [r for r in report if "error" in r["flags"] or "silent" in r["flags"]]
    print(f"\n{len(report)} files, {len(report) - len(bad)} written to {dst_root}, {len(bad)} silent/error")
    sys.exit(0)

if __name__ == "__main__":
    main()
