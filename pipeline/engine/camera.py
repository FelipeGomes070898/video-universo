import math
import numpy as np


def _catmull(p0, p1, p2, p3, u):
    return 0.5 * ((2 * p1) + (-p0 + p2) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u * u
                  + (-p0 + 3 * p1 - 3 * p2 + p3) * u ** 3)


class Path:
    """Trilha de camera por keyframes (Catmull-Rom) + tremor/roll suaves."""

    def __init__(self, keys, shake=0.0, roll=0.0, seed=1):
        self.t = np.array([k["t"] for k in keys], float)
        self.pos = np.array([k["pos"] for k in keys], float)
        self.look = np.array([k["look"] for k in keys], float)
        self.fov = np.array([k.get("fov", 60) for k in keys], float)
        self.shake, self.roll = shake, roll
        r = np.random.default_rng(seed)
        self.ph = r.uniform(0, 6.28, 8)

    def _ev(self, arr, t):
        t = float(np.clip(t, self.t[0], self.t[-1]))
        i = min(int(np.searchsorted(self.t, t, side="right") - 1), len(self.t) - 2)
        u = (t - self.t[i]) / (self.t[i + 1] - self.t[i])
        u = u * u * (3 - 2 * u) * 0.35 + u * 0.65          # easing leve
        g = lambda k: arr[min(max(k, 0), len(arr) - 1)]
        return _catmull(g(i - 1), g(i), g(i + 1), g(i + 2), u)

    def at(self, t):
        pos, look = self._ev(self.pos, t), self._ev(self.look, t)
        fov = float(self._ev(self.fov[:, None], t)[0])
        s = self.shake
        pos = pos + s * np.array([math.sin(t * 1.3 + self.ph[0]), math.sin(t * 1.7 + self.ph[1]),
                                  math.sin(t * 1.1 + self.ph[2])])
        look = look + s * 2 * np.array([math.sin(t * 0.9 + self.ph[3]), math.sin(t * 1.4 + self.ph[4]), 0])
        roll = self.roll * math.sin(t * 0.5 + self.ph[5])
        return pos, look, fov, roll


class Camera:
    def __init__(self, pos, look, W, H, fov_deg, roll=0.0):
        f = look - pos
        f = f / np.linalg.norm(f)
        r = np.cross(f, [0, 1, 0])
        r /= np.linalg.norm(r)
        u = np.cross(r, f)
        c, s = math.cos(roll), math.sin(roll)
        self.right = (r * c + u * s).astype(np.float32)
        self.up = (-r * s + u * c).astype(np.float32)
        self.fwd = f.astype(np.float32)
        self.pos = pos.astype(np.float32)
        self.W, self.H = W, H
        self.f = 0.5 * W / math.tan(math.radians(fov_deg) / 2)

    def project(self, pts):
        rel = np.atleast_2d(pts).astype(np.float32) - self.pos
        z = rel @ self.fwd
        zs = np.where(np.abs(z) < 1e-4, 1e-4, z)
        sx = self.W / 2 + self.f * (rel @ self.right) / zs
        sy = self.H / 2 - self.f * (rel @ self.up) / zs
        return sx, sy, z
