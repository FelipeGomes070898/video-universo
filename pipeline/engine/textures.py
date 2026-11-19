"""Texturas procedurais equirretangulares (planetas, aneis, nebulosa)."""
import math
import numpy as np
import cv2
from .noise import fft_noise, smoothstep


def _lerp(a, b, t):
    return a + (b - a) * t[..., None]


def earth(W, H, seed):
    h = 0.65 * fft_noise(W, H, 3.2, seed) + 0.35 * fft_noise(W, H, 2.2, seed + 1)
    lat = (0.5 - (np.arange(H)[:, None] + 0.5) / H) * math.pi
    lat = np.broadcast_to(lat, (H, W))
    land = smoothstep(0.545, 0.575, h)
    desert_n = fft_noise(W, H, 2.6, seed + 2)
    desert = 0.7 * smoothstep(0.52, 0.68, desert_n) * np.exp(-((np.abs(lat) - 0.45) / 0.35) ** 2)
    green = np.array([0.10, 0.28, 0.07], np.float32)
    brown = np.array([0.36, 0.28, 0.17], np.float32)
    sand = np.array([0.66, 0.52, 0.31], np.float32)
    hi = smoothstep(0.62, 0.78, h)
    landc = _lerp(green + 0 * h[..., None], brown, hi)
    landc = _lerp(landc, sand + 0 * landc, np.clip(desert, 0, 1))
    deep = np.array([0.005, 0.03, 0.15], np.float32)
    shallow = np.array([0.03, 0.20, 0.38], np.float32)
    oceanc = _lerp(deep + 0 * h[..., None], shallow, smoothstep(0.40, 0.54, h))
    alb = _lerp(oceanc, landc, land)
    ice = np.clip((np.abs(lat) - 1.18 + (fft_noise(W, H, 2.4, seed + 3) - 0.5) * 0.6) / 0.12, 0, 1)
    alb = _lerp(alb, np.array([0.9, 0.93, 0.97], np.float32) + 0 * alb, ice)
    spec = ((1 - land) * (1 - ice)).astype(np.float32)
    lights_n = fft_noise(W, H, 1.2, seed + 4)
    lights = (smoothstep(0.64, 0.72, lights_n) * land * (1 - ice) * (1 - hi)).astype(np.float32)
    cl = 0.6 * fft_noise(W, H, 2.8, seed + 5) + 0.4 * fft_noise(W, H, 1.8, seed + 6)
    clouds = smoothstep(0.57, 0.78, cl).astype(np.float32)
    return dict(albedo=alb.astype(np.float32), spec=spec, lights=lights, clouds=clouds)


def rocky(W, H, seed, c1=(0.25, 0.25, 0.26), c2=(0.62, 0.61, 0.58), craters=260):
    n = 0.6 * fft_noise(W, H, 2.6, seed) + 0.4 * fft_noise(W, H, 1.8, seed + 5)
    n = np.clip((n - 0.3) / 0.4, 0, 1)
    rng = np.random.default_rng(seed)
    dark = np.zeros((H, W), np.float32)
    rim = np.zeros((H, W), np.float32)
    for _ in range(craters):
        x, y = int(rng.integers(W)), int(rng.integers(H))
        r = int(rng.integers(3, 8) * rng.uniform(0.5, 4.0) * W / 2048 + 2)
        cv2.circle(dark, (x, y), r, 1.0, -1)
        cv2.circle(rim, (x, y), r, 1.0, max(1, r // 6))
    dark = cv2.GaussianBlur(dark, (0, 0), 2.0)
    rim = cv2.GaussianBlur(rim, (0, 0), 1.5)
    alb = _lerp(np.array(c1, np.float32) + 0 * n[..., None], np.array(c2, np.float32), n)
    alb = alb * (1 - 0.35 * dark + 0.30 * rim)[..., None]
    return dict(albedo=np.clip(alb, 0, 1).astype(np.float32))


def gas(W, H, seed, palette, bands=9.0, turbulence=1.0):
    n_low = fft_noise(W, H, 3.0, seed, aniso=1.0)
    n_hi = fft_noise(W, H, 2.2, seed + 1, aniso=8.0)
    n_fine = fft_noise(W, H, 2.0, seed + 2, aniso=14.0)
    lat = np.linspace(-1, 1, H, dtype=np.float32)[:, None]
    v = 0.5 + 0.5 * np.sin(lat * math.pi * bands + (n_low - 0.5) * 7.0 * turbulence)
    v = v + (n_hi - 0.5) * 0.9 + (n_fine - 0.5) * 0.5
    v = np.clip(v, 0, 1)
    pal = np.array(palette, np.float32)
    xs = np.linspace(0, 1, len(pal))
    alb = np.stack([np.interp(v, xs, pal[:, c]) for c in range(3)], -1).astype(np.float32)
    return dict(albedo=alb)


def make_ring_profile(N, seed, color=(0.85, 0.74, 0.55)):
    rng = np.random.default_rng(seed)
    x = np.linspace(0, 1, N)
    base = 0.55 + 0.25 * np.sin(x * 60 + rng.uniform(0, 6)) + 0.2 * np.sin(x * 190 + rng.uniform(0, 6))
    fine = cv2.GaussianBlur(rng.random((1, N)).astype(np.float32), (0, 0), 1.5)[0]
    base = np.clip(base * 0.7 + (fine - 0.5) * 1.2, 0.05, 1)
    alpha = base * smoothstep(0.0, 0.04, x) * smoothstep(1.0, 0.96, x)
    alpha *= 1 - 0.95 * np.exp(-((x - 0.58) / 0.025) ** 2)       # divisao tipo Cassini
    alpha *= 1 - 0.6 * np.exp(-((x - 0.84) / 0.012) ** 2)
    alpha *= np.where(x < 0.18, 0.35, 1.0)                         # anel D/C mais tenue
    tint = 0.75 + 0.25 * fine[:, None]
    rgb = np.array(color, np.float32)[None, :] * tint
    return np.concatenate([np.clip(rgb, 0, 1), alpha[:, None]], 1).astype(np.float32)


def nebula(W, H, seed, palette):
    """Panorama equirretangular de nebulosa + Via Lactea. palette: 3 cores RGB."""
    n1 = fft_noise(W, H, 3.0, seed)
    n2 = fft_noise(W, H, 3.2, seed + 1)
    n3 = fft_noise(W, H, 2.6, seed + 2)
    dust = fft_noise(W, H, 2.0, seed + 3)
    lon = np.linspace(0, 2 * math.pi, W, endpoint=False)[None, :]
    lat = (0.5 - (np.arange(H)[:, None] + 0.5) / H) * math.pi
    band_c = 0.35 * np.sin(lon + 1.0)
    band = np.exp(-((lat - band_c) / 0.22) ** 2).astype(np.float32)
    img = np.zeros((H, W, 3), np.float32) + np.array([0.004, 0.005, 0.012], np.float32)
    for k, (n, col) in enumerate(zip((n1, n2, n3), palette)):
        m = smoothstep(0.52, 0.85, n) * (0.25 + 0.9 * band) * (0.5 + 0.8 * dust)
        img += m[..., None] * np.array(col, np.float32) * 0.45
    img *= (1 - 0.55 * smoothstep(0.55, 0.8, fft_noise(W, H, 2.4, seed + 4)))[..., None] * 0.5 + 0.5
    img += band[..., None] * np.array([0.05, 0.045, 0.06], np.float32) * (0.4 + dust[..., None])
    return np.clip(img, 0, 1.5).astype(np.float32)
