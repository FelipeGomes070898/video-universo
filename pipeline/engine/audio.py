"""Trilha ambiente sintetica (pads + sinos + whooshes + reverb) em numpy, sem arquivos externos."""
import wave
import numpy as np

SR = 44100


def _saw(f, t, harm=7):
    return sum(np.sin(2 * np.pi * f * k * t) / k for k in range(1, harm + 1)) * 0.35


def _lp_noise(n, cutoff, rng):
    x = np.fft.rfft(rng.standard_normal(n))
    fr = np.fft.rfftfreq(n, 1 / SR)
    x *= 1 / (1 + (fr / cutoff) ** 4)
    y = np.fft.irfft(x, n)
    return y / (np.abs(y).max() + 1e-9)


def synth(cfg, duration, path, seed=3):
    rng = np.random.default_rng(seed)
    n = int(SR * duration)
    t = np.arange(n) / SR
    L, R = np.zeros(n), np.zeros(n)
    chords = cfg["chords"]
    xf = cfg.get("crossfade", 3.0)
    pad = np.zeros(n)
    for i, ch in enumerate(chords):
        t0 = ch["t"]
        t1 = chords[i + 1]["t"] if i + 1 < len(chords) else duration + xf
        env = np.clip((t - t0) / xf + 1, 0, 1) * np.clip((t1 - t) / xf + 0, 0, 1) if i + 1 < len(chords) else np.clip((t - t0) / xf + 1, 0, 1)
        env = np.where(t < t0 - 0.0, 0, env) if i else np.clip(t / 2.0, 0, 1)
        v = np.zeros(n)
        for j, f in enumerate(ch["notes"]):
            lfo = 0.7 + 0.3 * np.sin(2 * np.pi * (0.07 + 0.03 * j) * t + j)
            v += (_saw(f, t) + _saw(f * 1.004, t) + _saw(f * 0.996, t)) * lfo / (1 + 0.4 * j)
        pad += v * env
    sub = np.sin(2 * np.pi * chords[0]["notes"][0] / 2 * t) * 0.35 * (0.8 + 0.2 * np.sin(2 * np.pi * 0.05 * t))
    pad = pad * 0.18 + sub
    L += pad
    R += np.roll(pad, 220)
    # sinos
    scale = cfg.get("bell_scale", [440, 494, 554, 659, 740, 880, 988, 1108, 1320])
    tt = cfg.get("bell_start", 1.0)
    while tt < duration - 1.5:
        f = float(rng.choice(scale)) * (1 if rng.random() > 0.3 else 2)
        m = int(SR * 4)
        k = np.arange(m) / SR
        b = (np.sin(2 * np.pi * f * k) + 0.4 * np.sin(2 * np.pi * f * 2.76 * k) * np.exp(-k * 3)) * np.exp(-k * 1.6) * cfg.get("bell_gain", 0.05)
        pan = rng.uniform(0.2, 0.8)
        s = int(tt * SR)
        e = min(n, s + m)
        L[s:e] += b[: e - s] * (1 - pan)
        R[s:e] += b[: e - s] * pan
        tt += rng.uniform(0.9, 2.4)
    # whooshes
    for w in cfg.get("whooshes", []):
        m = int(SR * w.get("dur", 2.5))
        k = np.linspace(0, 1, m)
        env = np.sin(np.pi * k) ** 2 * w.get("gain", 0.22)
        nz = _lp_noise(m, w.get("cutoff", 1800), rng) * env
        s = int(w["t"] * SR)
        e = min(n, s + m)
        L[s:e] += nz[: e - s]
        R[s:e] += np.roll(nz, 400)[: e - s]
    # reverb
    ir_n = int(SR * cfg.get("reverb_seconds", 3.0))
    ek = np.exp(-np.arange(ir_n) / SR * 2.2)
    irL, irR = rng.standard_normal(ir_n) * ek, rng.standard_normal(ir_n) * ek
    size = 1 << int(np.ceil(np.log2(n + ir_n)))
    wet = cfg.get("reverb_mix", 0.35)
    for ch, ir in ((L, irL), (R, irR)):
        y = np.fft.irfft(np.fft.rfft(ch, size) * np.fft.rfft(ir, size), size)[:n]
        y /= (np.abs(y).max() + 1e-9) / (np.abs(ch).max() + 1e-9)
        ch *= (1 - wet)
        ch += y * wet
    fade = np.clip(t / cfg.get("fade_in", 1.5), 0, 1) * np.clip((duration - t) / cfg.get("fade_out", 2.5), 0, 1)
    st = np.stack([L * fade, R * fade], 1)
    st *= 0.7 / (np.abs(st).max() + 1e-9)
    pcm = (st * 32767).astype("<i2")
    with wave.open(path, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(pcm.tobytes())
    return path


def _bp(n, lo, hi, rng):
    x = np.fft.rfft(rng.standard_normal(n))
    fr = np.fft.rfftfreq(n, 1 / SR)
    x *= (1 / (1 + (fr / hi) ** 4)) * (1 / (1 + (lo / np.maximum(fr, 1e-3)) ** 4))
    y = np.fft.irfft(x, n)
    return y / (np.abs(y).max() + 1e-9)


def synth_sea(cfg, duration, path, seed=3):
    """Ondas (rumble + arrebentacao + chiado de espuma), vento e pad grave muito discreto."""
    rng = np.random.default_rng(seed)
    n = int(SR * duration)
    t = np.arange(n) / SR
    per = cfg.get("wave_period", 7.5)
    env = (0.5 + 0.5 * np.sin(2 * np.pi * t / per + 0.7 * np.sin(2 * np.pi * t / (per * 2.7)) + 1.0)) ** cfg.get("swell_sharp", 2.0)
    chans = []
    for ch in (0, 1):
        low, mid, hiss = _bp(n, 25, 500, rng), _bp(n, 300, 2500, rng), _bp(n, 2000, 7000, rng)
        x = low * (0.25 + 0.75 * env) * 0.6 + mid * env ** 1.5 * 0.35 + hiss * np.roll(env, int(SR * 0.8)) ** 3 * 0.22
        wind = _bp(n, 150, 900, rng) * (0.4 + 0.6 * (0.5 + 0.5 * np.sin(2 * np.pi * t / 17 + ch))) * cfg.get("wind_gain", 0.18)
        chans.append(x + wind)
    L, R = chans
    pad = sum(_saw(f, t, 5) for f in cfg.get("pad", [110.0, 164.81, 220.0])) * cfg.get("pad_gain", 0.03) * (0.6 + 0.4 * np.sin(2 * np.pi * t / 11))
    L, R = L + pad, R + np.roll(pad, 200)
    fade = np.clip(t / cfg.get("fade_in", 1.5), 0, 1) * np.clip((duration - t) / cfg.get("fade_out", 2.0), 0, 1)
    st = np.tanh(np.stack([L * fade, R * fade], 1) * 1.1)
    st *= 0.7 / (np.abs(st).max() + 1e-9)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes((st * 32767).astype("<i2").tobytes())
    return path
