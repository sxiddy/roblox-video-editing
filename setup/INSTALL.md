# Rebuilding the tool setup from scratch

After any install step, run `python setup/check_setup.py` from the project folder. It prints
PASS/FAIL for every tool and names the section below that fixes each FAIL. It changes nothing.
Sections 7 and 8 at the end were added on 2026-11-16.

Everything below was installed on 2026-11-11 on the Windows 11 laptop (i7-13645HX, RTX 4050 6 GB).
Run in Git Bash. Paths assume the user folder `C:/Users/Siddharth D`.

## 1. GPU Python environment (separate from system Python so nothing breaks)
```bash
cd "/c/Users/Siddharth D/Projects"
uv venv media-gpu --python 3.12
uv pip install --python media-gpu/Scripts/python.exe torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
uv pip install --python media-gpu/Scripts/python.exe transformers accelerate opencv-python pillow numpy scipy librosa soundfile demucs "rembg[gpu]" sam2 "beat_this @ git+https://github.com/CPJKU/beat_this.git"
media-gpu/Scripts/python.exe -c "import torch,onnxruntime as o;print(torch.__version__,torch.cuda.is_available(),o.get_available_providers())"
```
Expected: `2.11.0+cu128 True [... 'CUDAExecutionProvider' ...]`.

Model weights (cached on first use; pre-download):
```python
from huggingface_hub import snapshot_download
snapshot_download("facebook/sam2.1-hiera-small")
snapshot_download("depth-anything/Depth-Anything-V2-Small-hf")
snapshot_download("depth-anything/Depth-Anything-V2-Base-hf")
from beat_this.inference import File2Beats; File2Beats(checkpoint_path="final0", device="cuda")
from rembg import new_session; new_session("birefnet-general"); new_session("isnet-general-use")
from demucs.pretrained import get_model; get_model("htdemucs"); get_model("htdemucs_ft")
```

## 2. System Python packages
```bash
python -m pip install scenedetect pedalboard pyloudnorm moderngl auto-editor
```

## 3. GPU binaries (portable, Vulkan)
```bash
mkdir -p "/c/Users/Siddharth D/Projects/media-tools/dl" && cd "/c/Users/Siddharth D/Projects/media-tools/dl"
curl -L -C - -o rife.zip   https://github.com/nihui/rife-ncnn-vulkan/releases/download/20221029/rife-ncnn-vulkan-20221029-windows.zip
curl -L -C - -o esrgan.zip https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-windows.zip
curl -L -C - -o mcprep.zip https://github.com/Moo-Ack-Productions/MCprep/releases/download/3.6.3/MCprep_addon_3.6.3.zip
cd .. && unzip -q -o dl/rife.zip -d . && mv rife-ncnn-vulkan-20221029-windows rife-ncnn-vulkan && unzip -q -o dl/esrgan.zip -d realesrgan-ncnn-vulkan
```
Use:
- `rife-ncnn-vulkan.exe -i <frames_in> -o <frames_out> -m rife-v4.6` (doubles the frame count)
- `realesrgan-ncnn-vulkan.exe -i in.png -o out.png -n realesrgan-x4plus`

## 7. Added on 2026-11-16
```bash
# system Python: perceptual hashing for qc.py
python -m pip install imagehash
# GPU env: BiRefNet's code needs these (matte.py)
uv pip install --python "/c/Users/Siddharth D/Projects/media-gpu/Scripts/python.exe" timm kornia einops
# BiRefNet weights (about 900 MB) for matte.py
"/c/Users/Siddharth D/Projects/media-gpu/Scripts/python.exe" -c "from huggingface_hub import snapshot_download; snapshot_download('ZhengPeng7/BiRefNet', allow_patterns=['*.json','*.py','*.safetensors'])"
# SFX library: CC0 sounds from Openverse, then -18 LUFS copies (run from the project folder)
python pipeline/sfx_fetch.py
python pipeline/sfx_normalize.py
```
Matting must go through `pipeline/matte.py` (torch). rembg is installed but runs on the CPU here:
onnxruntime-gpu 1.31 needs CUDA 13 DLLs and torch ships CUDA 12.8.

## 8. Things only the user can do
- Update the NVIDIA driver to 610 or newer (GeForce app or nvidia.com). ffmpeg 9.0.2's NVENC
  refuses driver 581.86. Until then `config.fast_encoder()` uses Intel Quick Sync.
- Log in to GitHub (`gh auth login`) if `git push` asks for credentials.

## 6. Already present
ffmpeg 9.0.2 full build (NVENC, libplacebo, vidstab), Blender 5.2, yt-dlp, HyperFrames, system
Python 3.12 with torch CPU, opencv, librosa, rembg, mediapipe, moviepy, realesrgan, faster-whisper,
playwright. Source clones with REPO.md cards in `Projects/github-repos/`.
