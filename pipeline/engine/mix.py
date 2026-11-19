"""Trilha + mixagem final: musica ambiente gerada por scene, whooshes de transicao, ducking sob a voz, loudnorm."""
import os
import subprocess
import tempfile
import wave
import numpy as np
from . import audio

SR = audio.SR
CHORDS = [[55.0, 110.0, 164.81, 220.0, 329.63], [43.65, 87.31, 130.81, 174.61, 261.63], [65.41, 130.81, 196.0, 261.63, 392.0], [49.0, 98.0, 146.83, 196.0, 293.66, 440.0]]


def _read(path):
    with wave.open(path, "rb") as w:
        n = w.getnframes()
        d = np.frombuffer(w.readframes(n), "<i2").astype(np.float32) / 32768.0
        return d.reshape(-1, w.getnchannels())


def _write(path, st):
    with wave.open(path, "wb") as w:
        w.setnchannels(st.shape[1]); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(st, -1, 1) * 32767).astype("<i2").tobytes())


def whoosh(dur, rng, gain=0.5):
    m = int(SR * dur)
    k = np.linspace(0, 1, m)
    x = rng.standard_normal(m)
    spec = np.fft.rfft(x)
    fr = np.fft.rfftfreq(m, 1 / SR)
    cut = 250 + 5200 * k[len(k) // 2]               # filtro fixo; sweep simulado pela envoltoria
    spec *= 1 / (1 + (fr / cut) ** 3)
    y = np.fft.irfft(spec, m)
    y /= np.abs(y).max() + 1e-9
    env = np.sin(np.pi * k ** 1.6) ** 2
    return np.stack([y * env * gain, np.roll(y, 300) * env * gain], 1)


def boom(dur=4.0, gain=0.8):
    m = int(SR * dur)
    t = np.arange(m) / SR
    f = 38 + 30 * np.exp(-t * 3)
    y = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 0.9) * gain
    return np.stack([y, y], 1)


def make_music(scene_bounds, total, tmpdir, hits):
    out = np.zeros((int(SR * total) + SR * 4, 2), np.float32)
    rng = np.random.default_rng(11)
    for i, (s, e) in enumerate(scene_bounds):
        d = (e - s) + 4.0
        cfg = {"chords": [{"t": 0, "notes": CHORDS[i % len(CHORDS)]}], "crossfade": 2.0, "bell_scale": [440, 494, 554, 659, 740, 880, 988], "bell_gain": 0.035,
               "bell_start": 2.0, "reverb_seconds": 2.6, "reverb_mix": 0.4, "fade_in": 2.0, "fade_out": 2.5}
        p = os.path.join(tmpdir, f"m{i}.wav")
        audio.synth(cfg, d, p, seed=20 + i)
        st = _read(p)
        o = max(int((s - 2.0) * SR), 0)
        out[o:o + len(st)] += st[: len(out) - o]
    for t, kind in hits:                              # whooshes entre cenas, impactos e SFX (kind str ou (nome, dur, ganho))
        o = int(t * SR)
        if isinstance(kind, (tuple, list)):
            w = sfx(kind[0], kind[1], kind[2], rng)
        else:
            w = boom() if kind == "boom" else whoosh(1.6 if kind == "whoosh" else 3.2, rng, 0.5 if kind == "whoosh" else 0.7)
        if o < 0:
            continue
        out[o:o + len(w)] += w[: len(out) - o]
    return out[: int(SR * total)]


def mix(narr_wav, music, total, out_wav, tmpdir, music_vol=0.55):
    mpath = os.path.join(tmpdir, "music.wav")
    _write(mpath, music * 0.9 / max(np.abs(music).max(), 1e-6))
    fc = ("[0:a]aresample=44100,highpass=f=75,acompressor=threshold=0.09:ratio=3:attack=5:release=90:makeup=2.2,"
          "equalizer=f=3200:t=q:w=1.0:g=1.8,pan=stereo|c0=c0|c1=c0,asplit=2[v][vs];"
          f"[1:a]volume={music_vol}[m0];[m0][vs]sidechaincompress=threshold=0.015:ratio=9:attack=30:release=700[md];"
          "[v][md]amix=inputs=2:duration=longest:normalize=0,loudnorm=I=-15:TP=-1.5:LRA=9[o]")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", narr_wav, "-i", mpath, "-filter_complex", fc, "-map", "[o]", "-ar", "44100", "-ac", "2",
                    "-t", f"{total:.3f}", out_wav], check=True)


# --------------------------------------------------------------------------- efeitos sonoros procedurais (SFX)
def _band(n, lo, hi, rng):
    x = np.fft.rfft(rng.standard_normal(n))
    fr = np.fft.rfftfreq(n, 1 / SR)
    x *= (1 / (1 + (fr / hi) ** 4)) * (1 / (1 + (lo / np.maximum(fr, 1e-3)) ** 4))
    y = np.fft.irfft(x, n)
    return y / (np.abs(y).max() + 1e-9)


def _env(n, a, r):
    t = np.arange(n) / SR
    d = n / SR
    return np.clip(t / max(a, 1e-3), 0, 1) * np.clip((d - t) / max(r, 1e-3), 0, 1)


def sfx(kind, dur, gain, rng):
    n = int(SR * dur)
    t = np.arange(n) / SR
    if kind == "roar":                      # motores de foguete
        base = _band(n, 50, 2200, rng) * 0.8 + _band(n, 25, 160, rng) * 1.0
        crack = (rng.random(n) > 0.9993).astype(np.float32) * rng.standard_normal(n) * 1.5
        crack = np.convolve(crack, np.exp(-np.arange(300) / 40.0), "same")
        y = (base + crack) * _env(n, 0.8, dur * 0.35) * (0.8 + 0.2 * np.sin(2 * np.pi * 9 * t))
        l, r = y, np.roll(y, 220) * 0.95
    elif kind == "rumble":
        y = _band(n, 18, 110, rng) * _env(n, dur * 0.4, dur * 0.4)
        l, r = y, np.roll(y, 400)
    elif kind == "wind":
        g = 0.55 + 0.45 * np.sin(2 * np.pi * t / 6.5 + rng.uniform(0, 6)) * np.sin(2 * np.pi * t / 11.0)
        y = _band(n, 120, 1400, rng) * g * _env(n, 1.5, 1.5)
        l, r = y, _band(n, 120, 1400, rng) * g * _env(n, 1.5, 1.5)
    elif kind == "static":
        y = _band(n, 800, 9000, rng) * (rng.random(n) > 0.3) * _env(n, 0.05, dur * 0.8)
        l, r = y, np.roll(y, 77)
    elif kind == "hiss":
        y = _band(n, 2500, 10000, rng) * _env(n, 0.08, dur * 0.7)
        l, r = y, np.roll(y, 120)
    elif kind == "beeps":                   # chamadas de radio
        y = np.zeros(n)
        for k in range(int(dur / 0.55)):
            s0 = int(k * 0.55 * SR)
            m = int(0.12 * SR)
            f = 1250 if k % 2 == 0 else 1700
            tt = np.arange(m) / SR
            y[s0:s0 + m] += np.sin(2 * np.pi * f * tt) * np.hanning(m)
        y = y * 0.5 + _band(n, 600, 5000, rng) * 0.04
        l, r = y, y
    elif kind == "heart":
        y = np.zeros(n)
        for k in range(int(dur / 0.95)):
            for off, amp in ((0.0, 1.0), (0.3, 0.7)):
                s0 = int((k * 0.95 + off) * SR)
                m = int(0.18 * SR)
                if s0 + m < n:
                    tt = np.arange(m) / SR
                    y[s0:s0 + m] += np.sin(2 * np.pi * 52 * tt) * np.exp(-tt * 22) * amp
        l, r = y, y
    elif kind == "plasma":                  # sonificacao de ondas de plasma: tom subindo com tremulo (mais denso = mais agudo)
        f = 240 + 900 * (t / dur) ** 1.4 + 18 * np.sin(2 * np.pi * 5.5 * t)
        y = np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.5 + np.sin(2 * np.pi * np.cumsum(f * 2.01) / SR) * 0.18
        y = y * _env(n, 0.6, 0.8) + _band(n, 400, 3000, rng) * 0.03
        l, r = y, np.roll(y, 60)
    elif kind == "thud":
        f = 55 * np.exp(-t * 2.2)
        y = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 1.6) + _band(n, 60, 900, rng) * np.exp(-t * 3.0) * 0.6
        l, r = y, y
    else:
        raise ValueError(kind)
    st = np.stack([l, r], 1).astype(np.float32)
    return st * gain / (np.abs(st).max() + 1e-9)
