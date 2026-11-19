"""Renderizador de oceano 3D procedural (CPU/numpy): ondas por soma de senoides, Fresnel, reflexo de ceu/nuvens,
glitter do sol, espuma, nevoa de horizonte, gaivotas. Mesma interface do Renderer espacial: render(t)->uint8."""
import math
import numpy as np
import cv2
from .noise import fft_noise, smoothstep
from .camera import Path, Camera

G = 9.81


def _lerp(a, b, s):
    return np.array(a, np.float32) * (1 - s) + np.array(b, np.float32) * s


def _remap(tex, u, v):
    h, w = tex.shape[:2]
    m = len(u)
    cols = 512
    rows = -(-m // cols)
    mx = np.zeros(rows * cols, np.float32)
    my = np.zeros(rows * cols, np.float32)
    mx[:m] = u * w
    my[:m] = v * h
    out = cv2.remap(tex, mx.reshape(rows, cols), my.reshape(rows, cols), cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
    return out.reshape(rows * cols, -1)[:m]


class OceanRenderer:
    def __init__(self, project, W, H):
        self.p, self.W, self.H = project, W, H
        w = project["world"]
        o = w["ocean"]
        cam = project["camera"]
        self.path = Path(cam["keys"], cam.get("shake", 0.0), cam.get("roll", 0.0))
        self.sun_keys = w["sun_keys"]
        self.fog = float(o.get("fog", 0.0018))
        rng = np.random.default_rng(o.get("seed", 5))
        n = int(o.get("waves", 9))
        wind = math.radians(o.get("wind_deg", 15))
        wl = o.get("max_wavelength", 42.0) * 0.62 ** np.arange(n) * rng.uniform(0.85, 1.15, n)
        k = 2 * math.pi / wl
        ang = wind + rng.normal(0, o.get("spread", 0.9), n)
        self.k = k.astype(np.float32)
        self.kx = (k * np.cos(ang)).astype(np.float32)
        self.kz = (k * np.sin(ang)).astype(np.float32)
        self.A = (wl * 0.012 * o.get("steepness", 0.6) * (wl / 42.0) ** 0.25 * rng.uniform(0.6, 1.4, n)).astype(np.float32)
        self.om = (np.sqrt(G * k) * o.get("speed", 1.0)).astype(np.float32)
        self.ph = rng.uniform(0, 2 * math.pi, n).astype(np.float32)
        self.nw = n
        self.atot = float(self.A.sum())
        seed = o.get("seed", 5)
        self.foam_tex = fft_noise(1024, 1024, 2.2, seed + 3)
        c1 = fft_noise(2048, 1024, 3.0, seed + 1, aniso=3.5)
        c2 = fft_noise(2048, 1024, 2.2, seed + 2, aniso=2.0)
        self.cloud = smoothstep(0.50, 0.74, 0.65 * c1 + 0.35 * c2).astype(np.float32)
        self.cloud_drift = o.get("cloud_drift", 0.0015)
        b = w.get("birds", {})
        r2 = np.random.default_rng(b.get("seed", 2))
        nb = int(b.get("count", 7))
        self.birds = [dict(p0=np.array([r2.uniform(-18, 22), r2.uniform(5, 10), r2.uniform(-70, -35)], np.float32),
                           vz=-b.get("speed", 3.6), vx=r2.uniform(-0.5, 0.5), ph=r2.uniform(0, 6.28)) for _ in range(nb)]
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        r = np.hypot((xx - W / 2) / (W / 2), (yy - H / 2) / (H / 2))
        self.vig = (1 - 0.35 * np.clip(r - 0.4, 0, 1) ** 1.6)[..., None].astype(np.float32)
        self.rng = np.random.default_rng(project.get("seed", 7))

    # ---------------------------------------------------------------- sol / ceu
    def _sun(self, t):
        ts = [k["t"] for k in self.sun_keys]
        el = math.radians(float(np.interp(t, ts, [k["elev"] for k in self.sun_keys])))
        az = math.radians(float(np.interp(t, ts, [k["azim"] for k in self.sun_keys])))
        S = np.array([math.sin(az) * math.cos(el), math.sin(el), -math.cos(az) * math.cos(el)], np.float32)
        s = float(np.clip(1 - math.degrees(el) / 22.0, 0, 1))
        return dict(S=S, s=s, hz=_lerp((0.50, 0.66, 0.85), (0.98, 0.42, 0.14), s), zn=_lerp((0.08, 0.26, 0.64), (0.04, 0.08, 0.28), s),
                    sc=_lerp((1.0, 0.95, 0.85), (1.0, 0.55, 0.25), s))

    def _sky(self, dx, dy, dz, t, sun, clouds=True):
        S, hz, zn, sc = sun["S"], sun["hz"], sun["zn"], sun["sc"]
        h = np.clip(dy, 0, 1) ** 0.45
        col = hz[None] * (1 - h)[:, None] + zn[None] * h[:, None]
        mu = dx * S[0] + dy * S[1] + dz * S[2]
        col = col + (np.exp((mu - 1) * 30) * 0.38 + np.exp((mu - 1) * 260) * 1.5)[:, None] * sc[None]
        col = col + (smoothstep(0.99975, 0.99992, mu) * 40)[:, None] * sc[None]
        if clouds:
            lon = (np.arctan2(dz, dx) / (2 * math.pi) + 0.5 + self.cloud_drift * t) % 1.0
            lat = 0.5 - np.arcsin(np.clip(dy, -1, 1)) / math.pi
            a = _remap(self.cloud, lon.astype(np.float32), lat.astype(np.float32))[:, 0] * smoothstep(0.02, 0.2, dy)
            lit = np.exp((mu - 1) * 2.2)
            ccol = np.array([0.10, 0.09, 0.15], np.float32)[None] + sc[None] * (0.95 * lit)[:, None] + hz[None] * 0.18
            col = col * (1 - 0.88 * a)[:, None] + ccol * (0.88 * a)[:, None]
        return col

    # ---------------------------------------------------------------- agua
    def _height(self, px, pz, t, dist, f, nmax=None):
        fp = dist / f
        h = np.zeros_like(px)
        gx = np.zeros_like(px)
        gz = np.zeros_like(px)
        for i in range(nmax or self.nw):
            fade = np.clip(2 - 2 * self.k[i] * fp / math.pi, 0, 1)
            ph = self.kx[i] * px + self.kz[i] * pz - self.om[i] * t + self.ph[i]
            a = self.A[i] * fade
            h += a * np.sin(ph)
            c = a * np.cos(ph)
            gx += self.kx[i] * c
            gz += self.kz[i] * c
        return h, gx, gz

    def _water(self, frame, wi, dx, dy, dz, cam, t, sun):
        O = cam.pos
        S, sc, hz = sun["S"], sun["sc"], sun["hz"]
        td = np.minimum(-O[1] / dy, 5000.0)
        px, pz = O[0] + td * dx, O[2] + td * dz
        h, _, _ = self._height(px, pz, t, td, cam.f, nmax=5)
        td = np.clip(np.minimum((O[1] - h) / -dy, 5000.0), 0.2, 5000.0)
        px, pz = O[0] + td * dx, O[2] + td * dz
        h, gx, gz = self._height(px, pz, t, td, cam.f)
        nl = np.sqrt(gx * gx + 1 + gz * gz)
        nx, ny, nz = -gx / nl, 1 / nl, -gz / nl
        ndv = np.clip(-(nx * dx + ny * dy + nz * dz), 0.02, 1)
        F = 0.02 + 0.98 * (1 - ndv) ** 5
        rx, ry, rz = dx + 2 * ndv * nx, dy + 2 * ndv * ny, dz + 2 * ndv * nz
        ry = np.abs(ry)
        refl = self._sky(rx, ry, rz, t, sun, True)
        hn = np.clip(0.5 + h / (self.atot * 1.6), 0, 1) ** 1.5
        deep, shallow = np.array([0.006, 0.045, 0.085], np.float32), np.array([0.03, 0.30, 0.34], np.float32)
        nsun = np.clip(nx * S[0] + ny * S[1] + nz * S[2], 0, 1)
        body = (deep[None] * (1 - hn)[:, None] + shallow[None] * hn[:, None]) * (hz[None] * 0.55 + sc[None] * (1.4 * nsun)[:, None])
        col = body * (1 - F)[:, None] + refl * F[:, None]
        slope = np.sqrt(gx * gx + gz * gz)
        crest = smoothstep(0.55, 0.95, (h / (self.atot * 0.9)) * 0.6 + slope * 1.4)
        nz_ = _remap(self.foam_tex, ((px * 0.12 + t * 0.01) % 1.0).astype(np.float32), ((pz * 0.12) % 1.0).astype(np.float32))[:, 0]
        foam = crest * smoothstep(0.45, 0.7, nz_) * np.exp(-td * 0.012)
        col = col * (1 - foam)[:, None] + (sc[None] * 0.55 + hz[None] * 0.35) * foam[:, None]
        fog = 1 - np.exp(-td * self.fog)
        haze = self._sky(dx, np.zeros_like(dy), dz, t, sun, False)
        frame[wi] = col * (1 - fog)[:, None] + haze * fog[:, None]

    # ---------------------------------------------------------------- gaivotas
    def _birds(self, frame, cam, t):
        mask = np.zeros((self.H, self.W), np.uint8)
        for i, b in enumerate(self.birds):
            p = b["p0"] + np.array([b["vx"] * t, 0.6 * math.sin(1.1 * t + b["ph"]), b["vz"] * t], np.float32)
            sx, sy, z = cam.project(p)
            if z[0] < 4:
                continue
            s = 0.55 * cam.f / z[0]
            cx, cy = float(sx[0]), float(sy[0])
            if not (-50 < cx < self.W + 50 and -50 < cy < self.H + 50) or s < 2:
                continue
            f = math.sin(t * 4.5 + b["ph"])
            pts = np.array([[cx - s, cy - s * 0.1 + s * 0.45 * f], [cx - s * 0.5, cy - s * 0.28 - s * 0.1 * f], [cx, cy],
                            [cx + s * 0.5, cy - s * 0.28 - s * 0.1 * f], [cx + s, cy - s * 0.1 + s * 0.45 * f]], np.float32)
            cv2.polylines(mask, [np.round(pts).astype(np.int32).reshape(-1, 1, 2)], False, 255, max(1, int(s * 0.14)), cv2.LINE_AA)
        frame *= (1 - 0.85 * (mask.astype(np.float32) / 255.0))[..., None]

    # ---------------------------------------------------------------- pos
    def _post(self, frame, t):
        W, H = self.W, self.H
        r = self.p["render"]
        br = np.maximum(cv2.resize(frame, (W // 4, H // 4), interpolation=cv2.INTER_AREA) - r.get("bloom_threshold", 1.0), 0)
        bloom = cv2.GaussianBlur(br, (0, 0), 3) + cv2.GaussianBlur(br, (0, 0), 10) * 1.2 + cv2.GaussianBlur(br, (0, 0), 28) * 1.6
        frame = frame + cv2.resize(bloom, (W, H), interpolation=cv2.INTER_LINEAR) * r.get("bloom", 0.5)
        img = 1 - np.exp(-frame * 1.2)
        img = np.power(np.clip(img, 0, 1), 0.95) * self.vig
        img += self.rng.normal(0, r.get("grain", 0.008), (H, W, 1)).astype(np.float32)
        fi, fo = r.get("fade_in", 1.0), r.get("fade_out", 1.5)
        dur = self.p["briefing"]["duration_seconds"]
        k = min(1.0, t / fi if fi > 0 else 1.0, (dur - t) / fo if fo > 0 else 1.0)
        return np.clip(img * max(k, 0.0), 0, 1)

    def render(self, t):
        W, H = self.W, self.H
        pos, look, fov, roll = self.path.at(t)
        cam = Camera(pos, look, W, H, fov, roll)
        sun = self._sun(t)
        X = (np.arange(W, dtype=np.float32) + 0.5 - W / 2)[None, :]
        Y = (H / 2 - (np.arange(H, dtype=np.float32) + 0.5))[:, None]
        d = [cam.fwd[i] * cam.f + cam.right[i] * X + cam.up[i] * Y for i in range(3)]
        n = np.sqrt(d[0] ** 2 + d[1] ** 2 + d[2] ** 2)
        dx, dy, dz = [(c / n).ravel() for c in d]
        frame = np.zeros((H * W, 3), np.float32)
        wm = dy < -1e-4
        si, wi = np.flatnonzero(~wm), np.flatnonzero(wm)
        frame[si] = self._sky(dx[si], dy[si], dz[si], t, sun, True)
        if len(wi):
            self._water(frame, wi, dx[wi], dy[wi], dz[wi], cam, t, sun)
        frame = frame.reshape(H, W, 3)
        self._birds(frame, cam, t)
        return (self._post(frame, t) * 255 + 0.5).astype(np.uint8)
