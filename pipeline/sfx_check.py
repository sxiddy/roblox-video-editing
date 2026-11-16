"""Screen the normalised SFX library by machine, so only the doubtful sounds need a human ear.
Run with the GPU env:

    "C:/Users/Siddharth D/Projects/media-gpu/Scripts/python.exe" pipeline/sfx_check.py

For every sound in media-library/sfx_norm it uses CLAP (audio-text model) to check that the sound
matches its category folder, and measures how late the sound starts. Writes sfx_norm/check.json and
prints the sounds to listen to. A flag means "listen before using", not "bad"; nothing is deleted.
Flags: wrong_category (its own category is not in CLAP's top 3), weak_match (low similarity),
late_start (over 0.25 s of near-silence before the sound: trim it or it will land off the cut).
"""
import json
import os
import subprocess

os.environ.setdefault("TQDM_DISABLE", "1")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

import numpy as np
import torch

from config import SFX_NORM, need_gpu

MODEL = "laion/clap-htsat-unfused"
SR = 48000
PROMPTS = {
    "ambience": "background ambience of a place, room tone or nature atmosphere",
    "fire": "fire crackling or burning flames",
    "footsteps": "footsteps of someone walking or running",
    "glitch": "digital glitch, static or electronic distortion",
    "impact": "a heavy impact, hit, thud or boom",
    "riser": "a rising tension sound effect building up, a riser",
    "sub_drop": "a deep sub bass drop, low boom falling in pitch",
    "sword": "a sword slash, metal blade clang or swing",
    "ui": "a short user interface click, beep or notification sound",
    "water": "water splashing, flowing, bubbles or waves",
    "whoosh": "a fast whoosh or swoosh of air passing",
    "wind": "wind blowing",
}

def load(path, seconds=10):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-t", str(seconds), "-ac", "1", "-ar", str(SR),
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()

def feats(x):
    x = x if isinstance(x, torch.Tensor) else x.pooler_output
    return torch.nn.functional.normalize(x.float(), dim=-1)

def main():
    dev = need_gpu()
    from transformers import ClapModel, ClapProcessor
    proc = ClapProcessor.from_pretrained(MODEL)
    model = ClapModel.from_pretrained(MODEL).to(dev).eval()
    cats = list(PROMPTS)
    with torch.inference_mode():
        t = proc(text=[PROMPTS[c] for c in cats], return_tensors="pt", padding=True).to(dev)
        text = feats(model.get_text_features(**t))
    files = sorted(SFX_NORM.rglob("*.wav"))
    rows = []
    for f in files:
        cat = f.relative_to(SFX_NORM).parts[0]
        y = load(f)
        row = {"file": str(f), "category": cat, "flags": []}
        if len(y) < SR // 20:
            row["flags"].append("unreadable")
            rows.append(row)
            continue
        peak = float(np.abs(y).max())
        loud = np.nonzero(np.abs(y) > peak * 0.03)[0]          # first sample within 30 dB of the peak
        row["start_s"] = round(float(loud[0]) / SR, 3) if len(loud) else 0.0
        if row["start_s"] > 0.25 and cat not in ("ambience", "riser", "wind"):
            row["flags"].append("late_start")
        with torch.inference_mode():
            try:
                a = proc(audio=y, sampling_rate=SR, return_tensors="pt").to(dev)
            except TypeError:                                   # older transformers name
                a = proc(audios=y, sampling_rate=SR, return_tensors="pt").to(dev)
            sim = (feats(model.get_audio_features(**a)) @ text.T)[0].cpu().numpy()
        order = np.argsort(sim)[::-1]
        row["best_guess"] = [f"{cats[i]} {sim[i]:.2f}" for i in order[:3]]
        if cat in PROMPTS:
            own = float(sim[cats.index(cat)])
            row["own_score"] = round(own, 3)
            if cat not in [cats[i] for i in order[:3]]:
                row["flags"].append("wrong_category")
            elif own < 0.15:
                row["flags"].append("weak_match")
        rows.append(row)
    (SFX_NORM / "check.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    flagged = [r for r in rows if r["flags"]]
    print(f"{len(rows)} sounds checked, {len(flagged)} to listen to, {len(rows) - len(flagged)} look fine")
    for r in flagged:
        name = "/".join(r["file"].replace("\\", "/").split("/")[-2:])
        print(f"  {','.join(r['flags']):26s} {name[:60]:60s} sounds like: {', '.join(r.get('best_guess', [])[:2])}")
    print("report ->", SFX_NORM / "check.json")

if __name__ == "__main__":
    main()
