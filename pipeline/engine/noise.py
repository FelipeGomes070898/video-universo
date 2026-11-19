import numpy as np


def fft_noise(w, h, beta=2.0, seed=0, aniso=1.0):
    """Ruido fractal 1/f^beta, periodico (tileable) nos dois eixos. Saida ~[0,1]."""
    rng = np.random.default_rng(seed)
    fx = np.fft.fftfreq(w)[None, :] * aniso
    fy = np.fft.fftfreq(h)[:, None]
    f = np.sqrt(fx ** 2 + fy ** 2)
    f[0, 0] = 1.0
    amp = 1.0 / np.power(f, beta / 2.0)
    amp[0, 0] = 0.0
    spec = (rng.standard_normal((h, w)) + 1j * rng.standard_normal((h, w))) * amp
    n = np.fft.ifft2(spec).real
    n = (n - n.mean()) / (n.std() + 1e-9)
    return np.clip(0.5 + n * 0.18, 0, 1).astype(np.float32)


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)
