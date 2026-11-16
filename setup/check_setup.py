"""Check that every tool the pipeline needs is installed. Run this first in a new session:

    python setup/check_setup.py

Prints PASS / FAIL / WARN per item with the fix for each failure (details in setup/INSTALL.md).
Exit code 1 if anything FAILed. Changes nothing on the machine.
"""
import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pipeline"))
import config as c  # noqa: E402

fails = 0

def report(level, name, note=""):
    global fails
    fails += level == "FAIL"
    print(f"{level:4s} {name}" + (f"  ->  {note}" if note else ""))

def check(ok, name, fix, warn=False):
    report("PASS" if ok else ("WARN" if warn else "FAIL"), name, "" if ok else fix)

def out(cmd):
    try:
        r = subprocess.run([str(x) for x in cmd], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=180)
        return r.returncode, (r.stdout + r.stderr).strip()
    except Exception as e:
        return 1, str(e)

print("== system ==")
check(sys.version_info[:2] >= (3, 11), f"system Python {sys.version.split()[0]}", "install Python 3.12")
for exe in ("ffmpeg", "ffprobe", "git"):
    check(shutil.which(exe) is not None, exe + " on PATH", "install it and reopen the terminal")
for mod in ("cv2", "numpy", "PIL", "scenedetect", "imagehash"):
    check(importlib.util.find_spec(mod) is not None, "system Python module " + mod,
          "python -m pip install opencv-python numpy pillow scenedetect imagehash")
code, txt = out(["ffmpeg", "-hide_banner", "-filters"])
check("ddagrab" in txt, "ffmpeg screen capture (ddagrab)", "use a full ffmpeg build", warn=True)
enc = c.fast_encoder()[0]
check(enc == "h264_nvenc", f"fast video encoder: {enc}",
      "NVENC unavailable (NVIDIA driver too old for this ffmpeg?); previews use " + enc, warn=True)

print("== GPU Python env ==")
check(c.GPU_PY.is_file(), "GPU env at " + str(c.GPU_PY), "setup/INSTALL.md section 1")
if c.GPU_PY.is_file():
    probe = ("import torch;print('cuda', torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else '')\n"
             "import importlib.util as u\n"
             "for m in ('sam2','transformers','beat_this','demucs','librosa','timm','kornia','einops','cv2'):\n"
             "    print('mod', m, u.find_spec(m) is not None)\n"
             "from huggingface_hub import try_to_load_from_cache as t\n"
             "for r,f in (('facebook/sam2.1-hiera-small','sam2.1_hiera_small.pt'),('depth-anything/Depth-Anything-V2-Small-hf','config.json'),"
             "('depth-anything/Depth-Anything-V2-Base-hf','config.json'),('ZhengPeng7/BiRefNet','config.json')):\n"
             "    print('weights', r, isinstance(t(r, f), str))\n")
    code, txt = out([c.GPU_PY, "-c", probe])
    lines = [l.split() for l in txt.splitlines() if l.split() and l.split()[0] in ("cuda", "mod", "weights")]
    if not lines:
        report("FAIL", "GPU env probe", txt[-300:])
    for l in lines:
        if l[0] == "cuda":
            check(l[1] == "True", "torch sees the GPU: " + " ".join(l[2:]), "reinstall torch with the cu128 index (INSTALL.md 1)")
        elif l[0] == "mod":
            check(l[2] == "True", "GPU env module " + l[1], "INSTALL.md section 1")
        else:
            check(l[2] == "True", "model weights " + l[1], "INSTALL.md section 1 (pre-download block)")
    beat = Path.home() / ".cache/torch/hub/checkpoints/beat_this-final0.ckpt"
    check(beat.is_file(), "model weights beat_this final0", "INSTALL.md section 1 (pre-download block)")

print("== tools and libraries ==")
check(c.RIFE.is_file() and c.RIFE_MODEL.is_dir(), "RIFE + model rife-v4.6", "INSTALL.md section 3")
check(c.ESRGAN.is_file(), "Real-ESRGAN", "INSTALL.md section 3")
check(c.BLENDER.is_file(), "Blender at " + str(c.BLENDER), "install Blender 5.2 or fix BLENDER in pipeline/config.py")
n_sfx = len(list(c.SFX.rglob("*.mp3"))) if c.SFX.is_dir() else 0
check(n_sfx >= 50, f"SFX library ({n_sfx} sounds)", "python pipeline/sfx_fetch.py")
n_norm = len(list(c.SFX_NORM.rglob("*.wav"))) if c.SFX_NORM.is_dir() else 0
check(n_norm >= n_sfx > 0, f"SFX -18 LUFS copies ({n_norm})", "python pipeline/sfx_normalize.py")

print("== Roblox (only needed for Roblox jobs) ==")
rbx = Path.home() / "AppData/Local/Roblox/Versions"
exes = [p.name for p in rbx.rglob("*.exe")] if rbx.is_dir() else []
check(any("RobloxPlayer" in e for e in exes), "Roblox client installed", "install Roblox from roblox.com", warn=True)
check(any("RobloxStudio" in e for e in exes), "Roblox Studio installed", "install Studio from create.roblox.com", warn=True)
check(c.ROBLOX_PROJECT.is_dir(), "Roblox GFX project at " + str(c.ROBLOX_PROJECT),
      "clone roblox-gfx-pipeline there, or fix ROBLOX_PROJECT in pipeline/config.py", warn=True)

print("\n" + ("ALL REQUIRED ITEMS PASS" if not fails else f"{fails} FAILED: fix them before starting a job"))
sys.exit(1 if fails else 0)
