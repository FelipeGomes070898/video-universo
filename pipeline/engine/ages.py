"""Terra ao longo do tempo, em UM plano continuo: a mesma esfera muda de textura (magma -> oceanos -> gelo -> florestas -> cidades
-> deserto), a Lua nasce e se afasta, Theia e o asteroide chegam como corpos dinamicos, e o Sol incha no fim.
Tudo e funcao do tempo t, sem cortes."""
import math
import numpy as np
import cv2
from .film import Film
from . import textures as T
from .noise import fft_noise, smoothstep


def _lerp(a, b, t):
    return a + (b - a) * t[..., None]


def earth_variant(W, H, seed=4, beta=3.2, sea=0.56, land_lo=(0.10, 0.28, 0.07), land_hi=(0.36, 0.28, 0.17), desert=0.7,
                  ocean_deep=(0.005, 0.03, 0.15), ocean_shallow=(0.03, 0.20, 0.38), ice_lat=1.18, ice_global=0.0,
                  cloud_cov=0.62, lights=0.0, super_continent=False):
    if super_continent:
        h = 0.8 * fft_noise(W, H, 4.4, seed) + 0.2 * fft_noise(W, H, 2.6, seed + 1)
    else:
        h = 0.65 * fft_noise(W, H, beta, seed) + 0.35 * fft_noise(W, H, beta - 1.0, seed + 1)
    lat = np.broadcast_to((0.5 - (np.arange(H)[:, None] + 0.5) / H) * math.pi, (H, W))
    land = smoothstep(sea - 0.015, sea + 0.015, h)
    dn = fft_noise(W, H, 2.6, seed + 2)
    des = 0.7 * smoothstep(0.52, 0.68, dn) * np.exp(-((np.abs(lat) - 0.45) / 0.35) ** 2) * desert
    hi = smoothstep(sea + 0.06, sea + 0.22, h)
    landc = _lerp(np.array(land_lo, np.float32) + 0 * h[..., None], np.array(land_hi, np.float32), hi)
    landc = _lerp(landc, np.array([0.66, 0.52, 0.31], np.float32) + 0 * landc, np.clip(des, 0, 1))
    oc = _lerp(np.array(ocean_deep, np.float32) + 0 * h[..., None], np.array(ocean_shallow, np.float32), smoothstep(sea - 0.16, sea - 0.02, h))
    alb = _lerp(oc, landc, land)
    wob = (fft_noise(W, H, 2.4, seed + 3) - 0.5) * 0.6
    ice = np.clip((np.abs(lat) - ice_lat + wob) / 0.12, 0, 1)
    ice = np.maximum(ice, ice_global * np.clip(0.75 + wob * 2, 0, 1))
    alb = _lerp(alb, np.array([0.9, 0.93, 0.97], np.float32) + 0 * alb, ice)
    spec = ((1 - land) * (1 - ice)).astype(np.float32)
    cl = 0.6 * fft_noise(W, H, 2.8, seed + 5) + 0.4 * fft_noise(W, H, 1.8, seed + 6)
    clouds = smoothstep(cloud_cov, cloud_cov + 0.21, cl).astype(np.float32)
    out = dict(albedo=alb.astype(np.float32), spec=spec, clouds=clouds)
    ln = 0.5 * fft_noise(W, H, 1.0, seed + 4) + 0.5 * fft_noise(W, H, 2.2, seed + 7)
    out["lights"] = (smoothstep(0.60, 0.66, ln) * land * (1 - ice) * (1 - hi) * lights).astype(np.float32)
    out["glow"] = np.zeros((H, W), np.float32)
    return out


def magma(W, H, seed=9):
    n = 0.6 * fft_noise(W, H, 2.4, seed) + 0.4 * fft_noise(W, H, 1.6, seed + 1)
    crust = np.clip((n - 0.3) / 0.4, 0, 1)
    alb = _lerp(np.array([0.03, 0.02, 0.02], np.float32) + 0 * n[..., None], np.array([0.16, 0.11, 0.09], np.float32), crust)
    c1 = np.exp(-((fft_noise(W, H, 2.6, seed + 2) - 0.5) / 0.013) ** 2)
    c2 = np.exp(-((fft_noise(W, H, 2.0, seed + 3) - 0.5) / 0.017) ** 2)
    glow = np.clip(c1 + 0.7 * c2 + 0.04 + 0.25 * (1 - crust) ** 3, 0, 1.4).astype(np.float32)
    return dict(albedo=alb.astype(np.float32), spec=np.zeros((H, W), np.float32), clouds=np.zeros((H, W), np.float32),
                lights=np.zeros((H, W), np.float32), glow=glow)


# nome -> funcao geradora (cada textura compartilhada e gerada uma vez)
TEXTURES = {
    "magma": lambda W, H: magma(W, H),
    "steam": lambda W, H: earth_variant(W, H, seed=14, sea=0.99, ocean_deep=(0.10, 0.11, 0.12), ocean_shallow=(0.2, 0.2, 0.2), cloud_cov=0.40, ice_lat=9),
    "waterworld": lambda W, H: earth_variant(W, H, seed=15, sea=0.66, ocean_deep=(0.01, 0.08, 0.2), ocean_shallow=(0.03, 0.2, 0.32), land_lo=(0.2, 0.16, 0.12), land_hi=(0.3, 0.24, 0.18), cloud_cov=0.58, ice_lat=9),
    "archean": lambda W, H: earth_variant(W, H, seed=16, sea=0.60, ocean_deep=(0.03, 0.12, 0.10), ocean_shallow=(0.08, 0.22, 0.16), land_lo=(0.26, 0.2, 0.14), land_hi=(0.4, 0.31, 0.21), desert=0.0, cloud_cov=0.60, ice_lat=9),
    "oxygen": lambda W, H: earth_variant(W, H, seed=17, sea=0.575, ocean_deep=(0.01, 0.06, 0.2), ocean_shallow=(0.04, 0.22, 0.4), land_lo=(0.42, 0.18, 0.09), land_hi=(0.55, 0.26, 0.14), desert=0.0, cloud_cov=0.63),
    "snowball": lambda W, H: earth_variant(W, H, seed=17, sea=0.575, ice_global=1.0, ice_lat=0.1, ocean_deep=(0.6, 0.7, 0.8), ocean_shallow=(0.8, 0.86, 0.92), cloud_cov=0.68),
    "cambrian": lambda W, H: earth_variant(W, H, seed=18, sea=0.55, land_lo=(0.45, 0.38, 0.28), land_hi=(0.52, 0.45, 0.34), desert=0.2, cloud_cov=0.64),
    "carbon": lambda W, H: earth_variant(W, H, seed=19, sea=0.54, land_lo=(0.03, 0.2, 0.04), land_hi=(0.1, 0.3, 0.07), desert=0.0, cloud_cov=0.62),
    "pangaea": lambda W, H: earth_variant(W, H, seed=33, sea=0.52, super_continent=True, land_lo=(0.12, 0.3, 0.08), land_hi=(0.42, 0.3, 0.18), desert=1.2, cloud_cov=0.58),
    "modern": lambda W, H: earth_variant(W, H, seed=4, sea=0.56, lights=0.0, cloud_cov=0.62),
    "iceage": lambda W, H: earth_variant(W, H, seed=4, sea=0.58, ice_lat=0.85, cloud_cov=0.60),
    "city": lambda W, H: earth_variant(W, H, seed=4, sea=0.56, lights=0.7, cloud_cov=0.62),
    "ash": lambda W, H: earth_variant(W, H, seed=33, sea=0.52, super_continent=True, land_lo=(0.12, 0.3, 0.08), land_hi=(0.42, 0.3, 0.18), desert=1.2, cloud_cov=0.36),
    "dark": lambda W, H: earth_variant(W, H, seed=4, sea=0.56, cloud_cov=0.34),
    "future": lambda W, H: earth_variant(W, H, seed=4, sea=0.995, ocean_deep=(0.45, 0.33, 0.2), ocean_shallow=(0.6, 0.45, 0.28), land_lo=(0.6, 0.45, 0.3), cloud_cov=0.74, ice_lat=9),
}


class AgesFilm(Film):
    """project['ages'] = {stages:[{t,stage,tex,atm,cloud_tint,glow_gain,cloud_gain}], xf, spin:[[t,deg/s]], moon:{...}, bodies:[dinamicos], flashes:[...]}"""

    def __init__(self, project, W, H):
        super().__init__(project, W, H)
        self.A = project["ages"]
        self._st_cache = {}
        a = self.A
        self.st = a["stages"]
        self.xf = a.get("xf", 6.0)
        # integral numerica da rotacao (dias curtos no inicio)
        tt = np.arange(0, project["briefing"]["duration_seconds"] + 2, 0.05)
        keys = np.array(a["spin"], float)
        rate = np.interp(tt, keys[:, 0], keys[:, 1])
        self._spin_t, self._spin = tt, np.cumsum(rate) * 0.05
        mk = a.get("moon")
        if mk:
            mt = np.array(mk["keys"], float)                  # t, raio, hot(0..1)
            r = np.interp(tt, mt[:, 0], mt[:, 1])
            w = np.degrees(1.0) * 9.0 * (30.0 / np.maximum(r, 1.0)) ** 1.5           # graus/s, Kepler comprimido
            self._moon_t = tt
            self._moon_ang = np.cumsum(w) * 0.05
        self.tex_w_cache = project["render"].get("texture_width", 2048)

    # -------------------------------------------------------------- texturas de estagio
    def stage_tex(self, key):
        if key not in self._st_cache:
            if len(self._st_cache) >= 3:
                self._st_cache.pop(next(iter(self._st_cache)))
            self._st_cache[key] = TEXTURES[key](self.tex_w, self.tex_h)
        return self._st_cache[key]

    def _weights(self, t):
        """(i, j, w): estagios i->j com peso w de j."""
        st = self.st
        n = len(st)
        for k in range(1, n):
            t1 = st[k]["t"]
            xf = st[k].get("xf", self.xf)
            t0 = t1 - xf
            if t < t0:
                return k - 1, k - 1, 0.0
            if t < t1:
                w = (t - t0) / xf
                return k - 1, k, w * w * (3 - 2 * w)
        return n - 1, n - 1, 0.0

    def _blend_tex(self, i, j, w):
        a = self.stage_tex(self.st[i]["tex"])
        if i == j or w <= 0 or self.st[i]["tex"] == self.st[j]["tex"]:
            return a
        b = self.stage_tex(self.st[j]["tex"])
        if w >= 1:
            return b
        out = {}
        for k in a:
            if k == "albedo":
                out[k] = a[k] * (1 - w) + b[k] * w
            else:
                out[k] = a[k] * (1 - w) + b[k] * w
        return out

    @staticmethod
    def _mix(a, b, w):
        if isinstance(a, (list, tuple)):
            return [x * (1 - w) + y * w for x, y in zip(a, b)]
        return a * (1 - w) + b * w

    # -------------------------------------------------------------- corpos dinamicos
    def _bodies_of(self, s):
        t = self._t
        a = self.A
        i, j, w = self._weights(t)
        si, sj = self.st[i], self.st[j]
        tex = self._blend_tex(i, j, w)
        atm = {k: self._mix(si["atm"][k], sj["atm"][k], w) for k in si["atm"]}
        earth = {**self.protos["earth"], "pos": [0, 0, 0], "atmosphere": atm,
                 "cloud_tint": self._mix(si.get("cloud_tint", [1, 1, 1]), sj.get("cloud_tint", [1, 1, 1]), w),
                 "glow_gain": self._mix(si.get("glow_gain", 0.0), sj.get("glow_gain", 0.0), w),
                 "spin0": float(np.interp(t, self._spin_t, self._spin)), "spin_rate": 0.0, "name": "earth", "clouds": True,
                 "cloud_drift": 0.0}
        cg = self._mix(si.get("cloud_gain", 1.0), sj.get("cloud_gain", 1.0), w)
        if cg != 1.0:
            tex = dict(tex)
            tex["clouds"] = tex["clouds"] * cg
        out = [dict(spec=earth, tex=tex)]
        mk = a.get("moon")
        if mk and t >= mk["keys"][0][0]:
            mt = np.array(mk["keys"], float)
            r = float(np.interp(t, mt[:, 0], mt[:, 1]))
            hot = float(np.interp(t, mt[:, 0], mt[:, 2]))
            ang = float(np.interp(t, self._moon_t, self._moon_ang)) * math.pi / 180.0 + 0.6
            sc = float(np.interp(t, mt[:, 0], mt[:, 3])) if mt.shape[1] > 3 else 1.0
            spec = {**self.protos["moon"], "pos": [math.cos(ang) * r, 0.18 * r * math.sin(ang * 0.7), math.sin(ang) * r], "radius": 2.73 * sc, "name": "moon",
                    "ambient": [0.012 + 0.8 * hot, 0.016 + 0.22 * hot, 0.03 + 0.03 * hot], "spin_rate": 0.0, "spin0": math.degrees(ang) + 180}
            out.append(dict(spec=spec, tex=self.tex_for("moon")))
        for d in a.get("bodies", []):                      # corpos com trajetoria por keyframes [t, x, y, z, raio]
            ks = np.array(d["keys"], float)
            if t < ks[0, 0] or t > ks[-1, 0]:
                continue
            u = np.clip((t - ks[0, 0]) / (ks[-1, 0] - ks[0, 0]), 0, 1)
            v = [float(np.interp(t, ks[:, 0], ks[:, c])) for c in range(1, 5)]
            spec = {**self.protos[d["ref"]], **d.get("over", {}), "pos": v[:3], "radius": v[3], "name": d["ref"]}
            out.append(dict(spec=spec, tex=self.tex_for(d["ref"])))
        return out

    # -------------------------------------------------------------- sprites com envelope temporal
    def _dyn_sprites(self, t):
        return list(self.A.get("sprites", []))             # envelopes sao resolvidos em Film._prep_sprites

    def render(self, t):
        self._t = t
        self._dyn = self._dyn_sprites(t)
        return super().render(t)
