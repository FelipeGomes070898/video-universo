"""Narracao neural offline (Kokoro-82M via ONNX). Voz realista em ingles, sem API paga.

Modelo e vozes sao baixados do Hugging Face na primeira execucao (cache em ~/.cache/space_video_engine).
"""
import os
import re
import urllib.request
import numpy as np

CACHE = os.path.expanduser(os.environ.get("SVE_CACHE", "~/.cache/space_video_engine"))
BASE = "https://huggingface.co/onnx-community/Kokoro-82M-v1.0-ONNX/resolve/main"
SR = 24000
DEFAULT_VOICE = "bm_george"      # voz padrao do motor (britanica, documental)
DEFAULT_SPEED = 0.94


def _dl(url, dst):
    if not os.path.exists(dst):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        print("baixando", url, flush=True)
        urllib.request.urlretrieve(url, dst)
    return dst


class Narrator:
    def __init__(self, voice=DEFAULT_VOICE, speed=DEFAULT_SPEED, model="model.onnx"):
        from kokoro_onnx import Kokoro
        mp = _dl(f"{BASE}/onnx/{model}", os.path.join(CACHE, model))
        names = sorted(set([voice, "am_michael", "am_adam", "bm_george", "af_heart"]))
        vp = os.path.join(CACHE, "voices.npz")
        if not os.path.exists(vp) or any(n not in np.load(vp).files for n in names):
            names = sorted(set(names) | (set(np.load(vp).files) if os.path.exists(vp) else set()))
            v = {n: np.fromfile(_dl(f"{BASE}/voices/{n}.bin", os.path.join(CACHE, n + ".bin")), dtype=np.float32).reshape(-1, 1, 256) for n in names}
            np.savez(vp, **v)
        self.k = Kokoro(mp, vp)
        self.voice, self.speed = voice, speed

    def sentence(self, text, speed=None):
        a, sr = self.k.create(text, voice=self.voice, speed=speed or self.speed, lang="en-us")
        assert sr == SR
        return a.astype(np.float32)


def split_sentences(text):
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p for p in parts if p]
