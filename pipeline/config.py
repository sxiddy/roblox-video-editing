"""Shared paths for every pipeline script. Change paths here only."""
import os
import subprocess
import sys
from pathlib import Path

HOME = Path("C:/Users/Siddharth D")
PROJECT = Path(__file__).resolve().parent.parent          # the Video Editing folder
JOBS = PROJECT / "jobs"
GPU_PY = HOME / "Projects/media-gpu/Scripts/python.exe"    # torch CUDA env
TOOLS = HOME / "Projects/media-tools"
RIFE = TOOLS / "rife-ncnn-vulkan/rife-ncnn-vulkan.exe"
ESRGAN = TOOLS / "realesrgan-ncnn-vulkan/realesrgan-ncnn-vulkan.exe"
JMC2OBJ = TOOLS / "jmc2obj/jMc2Obj-128.jar"
LIB = HOME / "Projects/media-library"
SFX = LIB / "sfx"                 # originals; use SFX_NORM (-18 LUFS copies) in edits
SFX_NORM = LIB / "sfx_norm"
MC_SOUNDS = LIB / "mc_sounds"
SKINS = LIB / "skins"
RIFE_MODEL = TOOLS / "rife-ncnn-vulkan/rife-v4.6"
BLENDER = Path("C:/Program Files/Blender Foundation/Blender 5.2/blender.exe")
MC = Path(os.environ.get("APPDATA", str(HOME / "AppData/Roaming"))) / ".minecraft"
ROBLOX_PROJECT = HOME / "Projects/gfx and animation roblox blender"

VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".avi"}

def run(cmd, **kw):
    """Run a command, return CompletedProcess with text output. Raises on failure."""
    r = subprocess.run([str(c) for c in cmd], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", **kw)
    if r.returncode != 0:            # show the tool's own error, not just an exit code
        raise RuntimeError(f"{Path(str(cmd[0])).name} failed (exit {r.returncode}):\n{r.stderr.strip()[-1500:]}")
    return r

def ffprobe(path):
    """Width, height, fps, duration, has_audio for a media file."""
    import json
    out = run(["ffprobe", "-v", "error", "-show_entries",
               "stream=codec_type,width,height,r_frame_rate:format=duration",
               "-of", "json", path]).stdout
    d = json.loads(out)
    info = {"duration": float(d["format"]["duration"]), "has_audio": False}
    for s in d["streams"]:
        if s["codec_type"] == "video" and "width" not in info:
            n, m = s["r_frame_rate"].split("/")
            info.update(width=s["width"], height=s["height"], fps=round(float(n) / float(m), 3))
        if s["codec_type"] == "audio":
            info["has_audio"] = True
    return info

def loudness(path):
    """Integrated LUFS, LRA and true peak (dBTP) of a file's audio, measured with ffmpeg ebur128."""
    import re
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-vn", "-af",
                        "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace").stderr
    tail = r[r.rfind("Summary:"):]
    g = lambda pat: float(re.search(pat, tail).group(1))
    return {"lufs": g(r"I:\s+(-?[\d.]+) LUFS"), "lra": g(r"LRA:\s+(-?[\d.]+) LU"),
            "true_peak": g(r"Peak:\s+(-?[\d.]+) dBFS")}

def gray_writer(out, w, h, fps, out_size=None):
    """ffmpeg process that takes raw 8-bit grey frames (w x h) on stdin and writes a matte video.
    Write frame.tobytes() to .stdin, then close stdin and wait(). out_size=(W, H) rescales."""
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{w}x{h}",
           "-r", str(fps), "-i", "-"]
    if out_size and tuple(out_size) != (w, h):
        cmd += ["-vf", f"scale={out_size[0]}:{out_size[1]}:flags=bicubic"]
    cmd += ["-c:v", "libx264", "-crf", "12", "-preset", "medium", "-pix_fmt", "yuv420p", str(out)]
    return subprocess.Popen(cmd, stdin=subprocess.PIPE)

def fast_encoder():
    """ffmpeg video-encoder arguments for previews and screen capture: NVENC if it works, else
    Intel Quick Sync, else libx264 ultrafast. NVENC fails when the NVIDIA driver is older than this
    ffmpeg build needs (ffmpeg 9 needs driver 610+), so it is tested, not assumed."""
    options = [("h264_nvenc", ["-c:v", "h264_nvenc", "-preset", "p5", "-rc", "constqp", "-qp", "16"]),
               ("h264_qsv", ["-c:v", "h264_qsv", "-global_quality", "16", "-preset", "faster"]),
               ("libx264", ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "14"])]
    for name, args in options:
        r = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=1280x720:r=30", "-frames:v", "5",
                            *args, "-pix_fmt", "yuv420p", "-f", "null", "-"], capture_output=True)
        if r.returncode == 0:
            return name, args
    raise SystemExit("STOP: no working H.264 encoder in ffmpeg")

def need_gpu():
    """Call at the top of GPU scripts. Stops if torch cannot see the GPU."""
    import torch
    if not torch.cuda.is_available():
        sys.exit("STOP: torch has no CUDA. Run this with " + str(GPU_PY))
    print("device:", torch.cuda.get_device_name(0))
    return "cuda"
