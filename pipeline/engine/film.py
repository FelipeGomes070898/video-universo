"""Film: renderizador multi-cena. Uma linha do tempo de cenas 3D, cada uma com seu mundo, camera, ceu e sprites.

Reaproveita o Renderer espacial (planetas, aneis, estrelas, bloom) e acrescenta:
  - biblioteca de corpos (texturas procedurais preguicosas, compartilhadas entre cenas)
  - ceus (nebulosas coloridas, fundo cosmico CMB)
  - sprites: galaxias espirais (disco 3D), campo profundo, estrelas (glow), pulsar, buraco negro,
    nuvem de pontos orbitais (satelites) e espaconaves poligonais (ISS, Voyager)
"""
import math
import numpy as np
import cv2
from .renderer import Renderer, _unit
from . import textures as T
from .noise import fft_noise, smoothstep
from .camera import Path, Camera
from .terrain import Terrain, GeoTerrain
from .models import MODELS, polys_from
from .rocket import render_starship


# ----------------------------------------------------------------------------- texturas extras
def galaxy_tex(N, seed, arms=2, kind="spiral", tint=(1.0, 1.0, 1.0)):
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:N, 0:N].astype(np.float32)
    x, y = (x / (N - 1)) * 2 - 1, (y / (N - 1)) * 2 - 1
    r = np.hypot(x, y) + 1e-4
    th = np.arctan2(y, x)
    n1 = fft_noise(N, N, 2.6, seed)
    n2 = fft_noise(N, N, 1.6, seed + 1)
    edge = 1 - smoothstep(0.78, 1.0, r)
    bulge = np.exp(-(r / 0.13) ** 2) * 1.6 + np.exp(-(r / 0.30) ** 2) * 0.35
    if kind == "elliptical":
        dens = np.exp(-(r / 0.32) ** 1.0) * (0.7 + 0.6 * n1)
        col = np.stack([dens * 1.0, dens * 0.82, dens * 0.58], -1)
    else:
        arm = 0.5 + 0.5 * np.cos(arms * (th - np.log(r + 0.03) * 2.6 + (n1 - 0.5) * 2.2))
        armm = arm ** 2.2
        disk = np.exp(-r / 0.38)
        dust = smoothstep(0.55, 0.85, 0.5 + 0.5 * np.cos(arms * (th - np.log(r + 0.03) * 2.6 + 0.55) + (n2 - 0.5) * 3)) * smoothstep(0.1, 0.4, r)
        dens = disk * (0.18 + 1.0 * armm) * (0.55 + 0.9 * n2) * (1 - 0.55 * dust)
        blue = np.array([0.55, 0.72, 1.0], np.float32)
        gold = np.array([1.0, 0.82, 0.55], np.float32)
        mixc = smoothstep(0.05, 0.55, r)[..., None]
        base = gold * (1 - mixc) + blue * mixc
        col = base * dens[..., None] * 0.9
        hii = smoothstep(0.80, 0.93, n1) * armm * smoothstep(0.2, 0.5, r)
        col += hii[..., None] * np.array([1.0, 0.35, 0.55], np.float32) * 0.9
    col += bulge[..., None] * np.array([1.0, 0.86, 0.62], np.float32) * 0.9
    sp = rng.random((N, N)).astype(np.float32)
    stars = (sp > 0.9975).astype(np.float32) * rng.uniform(0.4, 1.2, (N, N)).astype(np.float32) * np.exp(-r / 0.5)
    col += stars[..., None]
    col = col * edge[..., None] * np.array(tint, np.float32)
    return np.clip(col, 0, 3).astype(np.float32)


def cmb_sky(W, H, seed):
    """Mapa de temperatura do fundo cosmico: manchas quentes/frias em paleta Planck."""
    n = 0.5 * fft_noise(W, H, 2.0, seed) + 0.3 * fft_noise(W, H, 1.2, seed + 1) + 0.2 * fft_noise(W, H, 3.0, seed + 2)
    n = np.clip((n - 0.5) / 0.22 * 0.5 + 0.5, 0, 1)
    stops = np.array([0.0, 0.2, 0.4, 0.55, 0.7, 0.85, 1.0])
    pal = np.array([[0.0, 0.02, 0.35], [0.05, 0.25, 0.75], [0.2, 0.6, 0.9], [0.95, 0.85, 0.5], [0.95, 0.55, 0.15], [0.8, 0.2, 0.08], [0.45, 0.03, 0.05]], np.float32)
    img = np.stack([np.interp(n, stops, pal[:, c]) for c in range(3)], -1).astype(np.float32)
    return img * 0.62


def _paint_ellipse(alb, cx, cy, rx, ry, color, strength):
    H, W = alb.shape[:2]
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    dx = ((x / W - cx + 0.5) % 1.0 - 0.5) / rx
    dy = (y / H - cy) / ry
    m = np.clip(1.2 - np.sqrt(dx * dx + dy * dy), 0, 1)[..., None] ** 0.8
    m = cv2.GaussianBlur(m[..., 0], (0, 0), 2.0)[..., None] * strength
    alb[:] = alb * (1 - m) + np.array(color, np.float32) * m


# ----------------------------------------------------------------------------- geometria de naves
_BOX_F = [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (2, 3, 7, 6), (0, 3, 7, 4), (1, 2, 6, 5)]


def _box_vertices(c, s):
    cx, cy, cz = c
    hx, hy, hz = s[0] / 2, s[1] / 2, s[2] / 2
    return np.array([[cx - hx, cy - hy, cz - hz], [cx + hx, cy - hy, cz - hz], [cx + hx, cy + hy, cz - hz], [cx - hx, cy + hy, cz - hz],
                     [cx - hx, cy - hy, cz + hz], [cx + hx, cy - hy, cz + hz], [cx + hx, cy + hy, cz + hz], [cx - hx, cy + hy, cz + hz]], np.float32)


def _rot(yaw, pitch, roll):
    cy, sy, cp, sp, cr, sr = math.cos(yaw), math.sin(yaw), math.cos(pitch), math.sin(pitch), math.cos(roll), math.sin(roll)
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]], np.float32)
    Rx = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]], np.float32)
    Rz = np.array([[cr, -sr, 0], [sr, cr, 0], [0, 0, 1]], np.float32)
    return Ry @ Rx @ Rz


def _disc_poly(c, normal, radius, n=22):
    nrm = np.array(normal, np.float32)
    nrm /= np.linalg.norm(nrm)
    a = np.cross(nrm, [0, 1, 0] if abs(nrm[1]) < 0.9 else [1, 0, 0])
    a /= np.linalg.norm(a)
    b = np.cross(nrm, a)
    ang = np.linspace(0, 2 * math.pi, n, endpoint=False)
    return np.array(c, np.float32) + radius * (np.cos(ang)[:, None] * a + np.sin(ang)[:, None] * b)


CRAFTS = {
    "iss": {
        "boxes": [  # center, size, color
            ((0, 0, 0), (7.0, 0.22, 0.22), (0.62, 0.62, 0.65)),
            ((0, -0.3, 0), (0.55, 0.55, 3.4), (0.85, 0.85, 0.88)),
            ((0, -0.3, 1.9), (0.8, 0.8, 0.9), (0.8, 0.78, 0.74)),
            ((0, -0.3, -1.9), (0.75, 0.75, 0.9), (0.85, 0.85, 0.9)),
            ((-3.0, 0, 0), (1.15, 0.04, 4.6), (0.05, 0.10, 0.36)), ((-1.65, 0, 0), (1.15, 0.04, 4.6), (0.05, 0.10, 0.36)),
            ((3.0, 0, 0), (1.15, 0.04, 4.6), (0.05, 0.10, 0.36)), ((1.65, 0, 0), (1.15, 0.04, 4.6), (0.05, 0.10, 0.36)),
            ((0.9, 0.25, 0), (0.12, 0.7, 2.6), (0.9, 0.9, 0.92)), ((-0.9, 0.25, 0), (0.12, 0.7, 2.6), (0.9, 0.9, 0.92)),
        ],
        "discs": [],
    },
    "voyager": {
        "boxes": [
            ((0, 0, 0), (1.0, 0.62, 1.0), (0.72, 0.68, 0.55)),
            ((0, 0.08, -3.2), (0.07, 0.07, 6.2), (0.75, 0.75, 0.78)),           # boom do magnetometro
            ((1.7, -0.1, -0.5), (3.2, 0.06, 0.06), (0.7, 0.7, 0.72)),            # boom dos RTGs
            ((2.9, -0.1, -0.5), (0.35, 0.35, 1.3), (0.35, 0.33, 0.3)),
            ((-1.2, 0.0, -0.4), (2.4, 0.06, 0.06), (0.7, 0.7, 0.72)),            # boom dos instrumentos
            ((-2.3, 0.0, -0.4), (0.5, 0.5, 0.6), (0.55, 0.55, 0.6)),
            ((0.0, 0.5, -0.3), (0.25, 0.25, 0.5), (0.8, 0.72, 0.4)),             # disco dourado (simplificado)
        ],
        "discs": [((0, 0, 0.55), (0, 0, 1), 1.9, (0.93, 0.93, 0.95)), ((0, 0, 0.62), (0, 0, 1), 1.5, (0.78, 0.78, 0.82)),
                  ((0, 0, 0.69), (0, 0, 1), 0.35, (0.5, 0.5, 0.55))],
    },
    "sat": {
        "boxes": [((0, 0, 0), (1, 1, 1.4), (0.8, 0.75, 0.55)), ((-1.6, 0, 0), (2.0, 0.03, 1.0), (0.05, 0.1, 0.4)), ((1.6, 0, 0), (2.0, 0.03, 1.0), (0.05, 0.1, 0.4))],
        "discs": [],
    },
}


class Film(Renderer):
    def __init__(self, project, W, H):
        self.base = project
        self.W, self.H = W, H
        self.scenes = project["scenes"]
        self.starts = np.array([s["start"] for s in self.scenes])
        self.rng = np.random.default_rng(project.get("seed", 7))
        tw = int(project["render"].get("texture_width", 2048))
        self.tex_w, self.tex_h = tw, tw // 2
        self.protos = project["bodies"]
        self.sky_specs = project["skies"]
        self._tex, self._sky, self._ring, self._gal, self._starcache = {}, {}, {}, {}, {}
        self.paths = [Path(s["cam"], s.get("shake", 0.0), s.get("roll", 0.0), seed=i + 3) for i, s in enumerate(self.scenes)]
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        r = np.hypot((xx - W / 2) / (W / 2), (yy - H / 2) / (H / 2))
        self.vig = (1 - 0.34 * np.clip(r - 0.35, 0, 1) ** 1.6)[..., None].astype(np.float32)
        self.cur = -1

    # ------------------------------------------------------------------ bibliotecas
    def tex_for(self, ref):
        if ref in self._tex:
            return self._tex[ref]
        b = self.protos[ref]
        tx = b["texture"]
        tw, th = self.tex_w, self.tex_h
        kind, seed = tx["type"], tx.get("seed", 1)
        if kind == "earth":
            tex = T.earth(tw, th, seed)
        elif kind == "rocky":
            tex = T.rocky(tw // 2, th // 2, seed, tuple(tx.get("c1", (0.25, 0.25, 0.26))), tuple(tx.get("c2", (0.62, 0.61, 0.58))), tx.get("craters", 260))
        elif kind == "gas":
            tex = T.gas(tw, th, seed, tx["palette"], tx.get("bands", 9.0), tx.get("turbulence", 1.0))
        elif kind == "image":                                  # textura real (ex.: Terra NASA Blue Marble): src='earth_eq' ou caminho
            import cv2 as _cv
            from . import geo as _geo
            src = _geo.earth_equirect() if tx.get("src") == "earth_eq" else tx["src"]
            im = _cv.imread(src)[..., ::-1].astype(np.float32) / 255.0
            tex = dict(albedo=np.power(im, 2.0) * tx.get("gain", 1.25))
        elif kind == "star":
            n = 0.6 * fft_noise(tw // 2, th // 2, 2.2, seed) + 0.4 * fft_noise(tw // 2, th // 2, 1.4, seed + 1)
            n = np.clip((n - 0.3) / 0.4, 0, 1)
            c1, c2 = np.array(tx.get("c1", (0.95, 0.35, 0.05)), np.float32), np.array(tx.get("c2", (1.0, 0.85, 0.45)), np.float32)
            tex = dict(albedo=(c1 * (1 - n[..., None]) + c2 * n[..., None]).astype(np.float32))
        else:
            raise ValueError(kind)
        for sp in tx.get("paint", []):
            _paint_ellipse(tex["albedo"], sp["u"], sp["v"], sp["rx"], sp["ry"], sp["color"], sp.get("strength", 0.9))
        self._tex[ref] = tex
        return tex

    def sky_for(self, name):
        if name in self._sky:
            return self._sky[name]
        s = self.sky_specs[name]
        if s.get("type") == "cmb":
            img = cmb_sky(self.tex_w, self.tex_h, s.get("seed", 5))
        else:
            img = T.nebula(self.tex_w, self.tex_h, s.get("seed", 11), s["palette"])
        self._sky[name] = img
        return img

    def stars_for(self, cfg):
        key = repr(sorted(cfg.items()))
        if key not in self._starcache:
            self._make_stars(cfg)
            self._starcache[key] = (self.far_pos, self.far_b, self.far_c, self.near_S, self.near_pos, self.near_b, self.near_c)
        (self.far_pos, self.far_b, self.far_c, self.near_S, self.near_pos, self.near_b, self.near_c) = self._starcache[key]

    def galaxy_for(self, spec):
        key = (spec.get("seed", 1), spec.get("kind", "spiral"), spec.get("arms", 2), tuple(spec.get("tint", (1, 1, 1))))
        if key not in self._gal:
            self._gal[key] = galaxy_tex(768, key[0], key[2], key[1], key[3])
        return self._gal[key]

    # ------------------------------------------------------------------ cena atual
    def scene_at(self, t):
        return int(np.clip(np.searchsorted(self.starts, t, side="right") - 1, 0, len(self.scenes) - 1))

    def _bodies_of(self, s):
        out = []
        for inst in s.get("bodies", []):
            ref = inst["ref"]
            spec = {**self.protos[ref], **inst}
            spec.setdefault("name", ref)
            B = dict(spec=spec, tex=self.tex_for(ref))
            if spec.get("ring"):
                rg = spec["ring"]
                if ref not in self._ring:
                    self._ring[ref] = T.make_ring_profile(2048, rg.get("seed", 3), tuple(rg.get("color", (0.85, 0.74, 0.55))))
                B["ring_tex"], B["ring_n"] = self._ring[ref], _unit(rg.get("normal", [0, 1, 0]))
            out.append(B)
        return out

    # ------------------------------------------------------------------ sprites
    def _glow(self, frame, cam, sp, t):
        pos = np.array(sp["pos"], np.float32)
        sx, sy, z = cam.project(pos)
        if z[0] <= 0.05:
            return
        sx, sy = float(sx[0]), float(sy[0])
        s = max(cam.f * sp.get("radius", 1.0) / z[0], 1.1) * (self.W / 1280.0 if sp.get("px_scale") else 1.0)
        R = int(min(s * sp.get("reach", 14), max(self.W, self.H)))
        x0, x1, y0, y1 = int(max(sx - R, 0)), int(min(sx + R, self.W)), int(max(sy - R, 0)), int(min(sy + R, self.H))
        if x1 <= x0 or y1 <= y0:
            return
        yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
        dx, dy = xx - sx, yy - sy
        r = np.hypot(dx, dy)
        g = np.exp(-(r / (s * 0.55)) ** 2) * 3.2 + np.exp(-r / (s * 2.2)) * 0.5 + 0.12 / (1 + (r / (s * 7.0)) ** 2)
        if sp.get("spikes"):
            for a in (math.pi / 2, math.pi / 6, -math.pi / 6):
                al = dx * math.cos(a) + dy * math.sin(a)
                pe = -dx * math.sin(a) + dy * math.cos(a)
                g += np.exp(-np.abs(pe) / (s * 0.28 + 0.4)) * 1.1 / (1 + (np.abs(al) / (s * 6)) ** 1.4)
        g = g * (1 - smoothstep(0.55 * R, R, r))
        col = np.array(sp.get("color", (1, 1, 1)), np.float32) * sp.get("gain", 1.0)
        frame[y0:y1, x0:x1] += g[..., None] * col

    def _pulsar(self, frame, cam, sp, t):
        pos = np.array(sp["pos"], np.float32)
        sx, sy, z = cam.project(pos)
        if z[0] <= 0.05:
            return
        sx, sy = float(sx[0]), float(sy[0])
        s = max(cam.f * sp.get("radius", 0.5) / z[0], 2.0)
        R = int(min(s * 60, max(self.W, self.H)))
        x0, x1, y0, y1 = int(max(sx - R, 0)), int(min(sx + R, self.W)), int(max(sy - R, 0)), int(min(sy + R, self.H))
        if x1 <= x0 or y1 <= y0:
            return
        yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
        dx, dy = xx - sx, yy - sy
        r = np.hypot(dx, dy)
        a = t * 2 * math.pi * sp.get("rate", 0.5)
        g = np.exp(-(r / (s * 0.7)) ** 2) * 3.0 + np.exp(-r / (s * 3)) * 0.6
        for k in (0, math.pi):
            ca, sa = math.cos(a + k), math.sin(a + k)
            al = dx * ca + dy * sa
            pe = -dx * sa + dy * ca
            g += np.where(al > 0, np.exp(-(pe / (s * (0.5 + 0.12 * np.abs(al) / s))) ** 2) * np.exp(-al / (s * 16)) * 1.6, 0)
        g = g * (1 - smoothstep(0.55 * R, R, r))
        col = np.array(sp.get("color", (0.6, 0.8, 1.0)), np.float32)
        frame[y0:y1, x0:x1] += g[..., None] * col * (0.8 + 0.2 * math.cos(2 * a))

    def _blackhole(self, frame, cam, sp, t):
        pos = np.array(sp["pos"], np.float32)
        sx, sy, z = cam.project(pos)
        if z[0] <= 0.05:
            return
        sx, sy = float(sx[0]), float(sy[0])
        rs = cam.f * sp["radius"] / z[0]
        R = int(min(rs * 7.5, 2000))
        x0, x1, y0, y1 = int(max(sx - R, 0)), int(min(sx + R, self.W)), int(max(sy - R, 0)), int(min(sy + R, self.H))
        if x1 <= x0 or y1 <= y0:
            return
        yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
        rot = math.radians(sp.get("roll_deg", -12))
        X0, Y0 = (xx - sx) / rs, (yy - sy) / rs
        x = X0 * math.cos(rot) - Y0 * math.sin(rot)
        y = X0 * math.sin(rot) + Y0 * math.cos(rot)
        q = sp.get("incl", 0.2)
        r = np.hypot(x, y) + 1e-5
        rho = np.hypot(x, y / q)
        dop = np.clip(1.0 - 0.55 * x, 0.25, 1.9)
        disc = np.exp(-((rho - 2.5) / 1.9) ** 2) * smoothstep(0.95, 1.2, rho) / np.maximum(rho, 1.0) ** 0.8 * 2.4
        lens_top = np.exp(-((r - 1.30) / 0.22) ** 2) * smoothstep(0.0, 0.85, y / r) * 1.5
        lens_bot = np.exp(-((r - 1.14) / 0.10) ** 2) * smoothstep(-0.2, -0.9, y / r) * 0.7
        ring = np.exp(-((r - 1.03) / 0.03) ** 2) * 2.2
        heat = np.clip((rho - 1.0) / 4.0, 0, 1)[..., None]
        col = (np.array([1.0, 0.86, 0.6], np.float32) * (1 - heat) + np.array([1.0, 0.38, 0.1], np.float32) * heat)
        val = (disc * dop + (lens_top + lens_bot) * dop * 0.9 + ring * dop)[..., None] * col * sp.get("gain", 1.0)
        shadow = smoothstep(0.985, 1.03, r)[..., None]
        v = frame[y0:y1, x0:x1]
        frame[y0:y1, x0:x1] = v * shadow + val * shadow

    def _galaxy(self, frame, cam, sp, t):
        tex = self.galaxy_for(sp)
        C = np.array(sp["pos"], np.float32)
        Rw = float(sp["radius"])
        n = _unit(sp.get("normal", [0.0, 1.0, 0.0]))
        e1 = np.cross(n, [0, 0, 1.0] if abs(n[2]) < 0.9 else [1.0, 0, 0])
        e1 /= np.linalg.norm(e1)
        e2 = np.cross(n, e1)
        spin = sp.get("spin", 0.0) * t
        c, s_ = math.cos(spin), math.sin(spin)
        e1, e2 = e1 * c + e2 * s_, -e1 * s_ + e2 * c
        O = cam.pos
        dist = float(np.linalg.norm(C - O))
        if float((C - O) @ cam.fwd) < -Rw:
            return
        sxc, syc, _ = cam.project(C)
        if dist > Rw * 1.02:
            sr = cam.f * Rw / math.sqrt(max(dist ** 2 - Rw ** 2, 1e-3)) * 1.1
        else:
            sr = max(self.W, self.H)
        x0, x1, y0, y1 = int(max(sxc[0] - sr, 0)), int(min(sxc[0] + sr, self.W)), int(max(syc[0] - sr, 0)), int(min(syc[0] + sr, self.H))
        if x1 <= x0 or y1 <= y0:
            return
        X = (np.arange(x0, x1, dtype=np.float32) + 0.5 - self.W / 2)[None, :]
        Y = (self.H / 2 - (np.arange(y0, y1, dtype=np.float32) + 0.5))[:, None]
        d = [cam.fwd[i] * cam.f + cam.right[i] * X + cam.up[i] * Y for i in range(3)]
        dx, dy, dz = d
        den = dx * n[0] + dy * n[1] + dz * n[2]
        num = float((C - O) @ n)
        with np.errstate(divide="ignore", invalid="ignore"):
            tr = num / den
        ok = (np.abs(den) > 1e-6) & (tr > 0)
        px, py, pz = O[0] + tr * dx - C[0], O[1] + tr * dy - C[1], O[2] + tr * dz - C[2]
        u = (px * e1[0] + py * e1[1] + pz * e1[2]) / Rw
        v = (px * e2[0] + py * e2[1] + pz * e2[2]) / Rw
        ok &= (np.abs(u) < 1) & (np.abs(v) < 1)
        if not ok.any():
            return
        idx = np.nonzero(ok)
        uu, vv = (u[ok] + 1) / 2, (v[ok] + 1) / 2
        samp = self._remap(tex, np.clip(uu, 0, 0.999), np.clip(vv, 0, 0.999))
        view = frame[y0:y1, x0:x1]
        view[idx] += samp * sp.get("gain", 1.0)

    def _deepfield(self, frame, cam, sp, t):
        key = ("df", sp.get("seed", 1), sp.get("count", 400))
        if key not in self._gal:
            r = np.random.default_rng(sp.get("seed", 1))
            n = sp.get("count", 400)
            ext = sp.get("extent", [260, 150, 400])
            P = np.stack([r.uniform(-ext[0], ext[0], n), r.uniform(-ext[1], ext[1], n), r.uniform(60, ext[2], n)], 1).astype(np.float32)
            size = (r.pareto(2.2, n) + 1) * sp.get("size", 0.7)
            ang = r.uniform(0, math.pi, n)
            ratio = r.uniform(0.25, 1.0, n)
            pal = np.array([[1.0, 0.78, 0.5], [0.65, 0.78, 1.0], [1.0, 0.55, 0.4], [0.95, 0.92, 1.0], [1.0, 0.9, 0.6]], np.float32)
            col = pal[r.choice(len(pal), n, p=[0.25, 0.3, 0.15, 0.1, 0.2])] * r.uniform(0.5, 1.4, n)[:, None]
            self._gal[key] = (P, size.astype(np.float32), ang, ratio, col)
        P, size, ang, ratio, col = self._gal[key]
        rel = P - cam.pos
        z = rel @ cam.fwd
        sxs = self.W / 2 + cam.f * (rel @ cam.right) / np.maximum(z, 1e-3)
        sys_ = self.H / 2 - cam.f * (rel @ cam.up) / np.maximum(z, 1e-3)
        sc = cam.f * size / np.maximum(z, 1e-3)
        for i in np.nonzero(z > 5)[0]:
            s = max(float(sc[i]), 0.9)
            R = int(min(s * 4 + 2, 80))
            sx, sy = sxs[i], sys_[i]
            if sx < -R or sx > self.W + R or sy < -R or sy > self.H + R:
                continue
            x0, x1, y0, y1 = int(max(sx - R, 0)), int(min(sx + R + 1, self.W)), int(max(sy - R, 0)), int(min(sy + R + 1, self.H))
            if x1 <= x0 or y1 <= y0:
                continue
            yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
            dx, dy = xx - sx, yy - sy
            ca, sa = math.cos(ang[i]), math.sin(ang[i])
            a_ = dx * ca + dy * sa
            b_ = (-dx * sa + dy * ca) / ratio[i]
            rr = np.hypot(a_, b_) / s
            g = np.exp(-rr * 1.8) * 1.4 + np.exp(-(rr * 3) ** 2) * 1.2
            frame[y0:y1, x0:x1] += g[..., None] * col[i] * sp.get("gain", 1.0) * min(1.0, 0.35 + 0.65 * s / 3)

    def _points(self, frame, cam, sp, t):
        """Nuvem de pontos orbitais (satelites). shell: raio, n, inclinacao, velocidade angular (graus/s)."""
        key = ("pts", repr(sp))
        if key not in self._gal:
            r = np.random.default_rng(sp.get("seed", 1))
            n = sp["n"]
            ph = r.uniform(0, 2 * math.pi, n)
            inc = np.radians(sp.get("inc", 55)) * np.ones(n) if sp.get("planes", 0) == 0 else np.radians(sp.get("inc", 55)) * np.ones(n)
            node = (np.arange(n) % max(sp.get("planes", 1), 1)) * 2 * math.pi / max(sp.get("planes", 1), 1) if sp.get("planes", 0) else r.uniform(0, 2 * math.pi, n)
            if sp.get("random_inc"):
                inc = np.arccos(r.uniform(-1, 1, n))
            self._gal[key] = (ph, inc, node)
        ph, inc, node = self._gal[key]
        a = ph + math.radians(sp.get("speed", 4.0)) * t
        ca, sa = np.cos(a), np.sin(a)
        x, y0 = sp["radius"] * ca, sp["radius"] * sa
        y1, z1 = y0 * np.cos(inc), y0 * np.sin(inc)
        xx = x * np.cos(node) - z1 * np.sin(node)
        zz = x * np.sin(node) + z1 * np.cos(node)
        pts = np.stack([xx, y1, zz], 1).astype(np.float32) + np.array(sp.get("center", [0, 0, 0]), np.float32)
        sx, sy, z = cam.project(pts)
        m = (z > 0.5) & (sx > 1) & (sx < self.W - 2) & (sy > 1) & (sy < self.H - 2)
        col = np.tile(np.array(sp.get("color", (1, 1, 1)), np.float32) * sp.get("gain", 1.0), (int(m.sum()), 1))
        if m.any():
            self._splat(frame, sx[m], sy[m], col)

    def _default_env(self):
        return {"horizon": [0.04, 0.045, 0.09], "zenith": [0.012, 0.014, 0.035], "ground": [0.03, 0.05, 0.1], "sun_dir": list(self.sun_dir), "sun_col": [1.0, 0.95, 0.85], "sun_int": 1.3}

    def _polys(self, name):
        if name not in self._gal:
            self._gal[name] = polys_from(MODELS[name] if name in MODELS else CRAFTS[name])
        return self._gal[name]

    def _craft(self, frame, cam, sp, t):
        if sp["model"] in ("starship", "starship_legs") and not sp.get("lowpoly"):
            R_ = _rot(math.radians(sp.get("yaw", 0) + sp.get("yaw_rate", 0) * t), math.radians(sp.get("pitch", 0)), math.radians(sp.get("roll", 0)))
            render_starship(self, frame, cam, np.array(sp["pos"], np.float32), float(sp.get("scale", 1.0)), R_, getattr(self, "_envl", self._default_env()),
                            legs=(sp["model"] == "starship_legs"), flame=float(sp.get("fl", 0.0)), gain=float(sp.get("hq_gain", 1.0)), tdepth=getattr(self, "_tdepth", None),
                            tile_dir=math.radians(sp.get("tile_deg", 180.0)))
            return
        polys = self._polys(sp["model"])
        scale = float(sp.get("scale", 1.0))
        pos = np.array(sp["pos"], np.float32)
        R = _rot(math.radians(sp.get("yaw", 0) + sp.get("yaw_rate", 0) * t), math.radians(sp.get("pitch", 0)), math.radians(sp.get("roll", 0)))
        L = self.sun_dir
        cl, ca = getattr(self, "_cl", 1.0), getattr(self, "_ca", 1.0)
        items = []
        for V, col in polys:
            Wv = (V * scale) @ R.T + pos
            nrm = np.cross(Wv[1] - Wv[0], Wv[2] - Wv[0])
            nn = np.linalg.norm(nrm)
            if nn < 1e-9:
                continue
            nrm /= nn
            cen = Wv.mean(0)
            if nrm @ (cam.pos - cen) < 0:
                nrm = -nrm
            lam = max(float(nrm @ L), 0.0) * 1.35 * cl + 0.16 * ca
            items.append((float(np.linalg.norm(cen - cam.pos)), Wv, np.array(col, np.float32) * lam))
        if not items:
            return
        S = int(sp.get("ss", 3 if self.W <= 1920 else 2))           # supersampling das naves (antisserrilhado); ss menor poupa memoria
        canvas = np.zeros((self.H * S, self.W * S, 3), np.float32)
        alpha = np.zeros((self.H * S, self.W * S), np.uint8)
        items.sort(key=lambda p_: -p_[0])
        for _, Wv, colr in items:
            sx, sy, z = cam.project(Wv)
            if (z <= 0.05).any():
                continue
            pts = np.stack([sx * S, sy * S], 1).astype(np.int32)
            cv2.fillConvexPoly(canvas, pts, tuple(float(c) for c in colr[::-1]))
            cv2.fillConvexPoly(alpha, pts, 255, lineType=cv2.LINE_AA)
        a = cv2.resize(alpha, (self.W, self.H), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
        td = getattr(self, "_tdepth", None)
        if td is not None and not sp.get("no_occlude"):          # oclusao pelo terreno (no_occlude: objetos gigantes como estrada/mar)
            dc = float(np.linalg.norm(pos - cam.pos))
            a = a * (td > dc * 0.97 - 2.0)
        img = cv2.resize(canvas, (self.W, self.H), interpolation=cv2.INTER_AREA)[..., ::-1]
        a = a[..., None]
        frame[:] = frame * (1 - a) + img * sp.get("gain", 1.6) * getattr(self, "_cg", 1.0) * a

    # ------------------------------------------------------------------ efeitos novos
    def _flame(self, frame, cam, sp, t):
        """pluma de escape: nucleo branco quente -> amarelo -> laranja -> vermelho, diamantes de choque, halo no bocal."""
        pos = np.array(sp["pos"], np.float32)
        d = _unit(sp.get("dir", [0, -1, 0]))
        L = sp.get("length", 30.0)
        R0 = sp.get("radius", 2.0)
        g0 = sp.get("gain", 1.0)
        fl = 0.9 + 0.1 * math.sin(t * 61.0) * math.sin(t * 23.0 + 1.0)
        N = 40
        for k in range(N):
            u = k / (N - 1.0)
            if u < 0.12:
                col = (1.0, 0.97, 0.88)
            elif u < 0.4:
                f_ = (u - 0.12) / 0.28
                col = (1.0, 0.97 - 0.30 * f_, 0.88 - 0.58 * f_)
            else:
                f_ = min((u - 0.4) / 0.6, 1.0)
                col = (1.0, 0.67 - 0.37 * f_, 0.30 - 0.18 * f_)
            diamond = 0.78 + 0.22 * math.cos(u * 17.0 * math.pi + t * 30.0) ** 2
            rad = R0 * (0.55 + 0.9 * math.sin(math.pi * min(u * 1.1, 1.0)) ** 0.7 * (1 - 0.35 * u))
            g = {"pos": (pos + d * L * u).tolist(), "radius": rad * 0.30, "reach": 6, "color": list(col),
                 "gain": g0 * fl * diamond * (1 - u) ** 1.3 * 0.20}
            self._glow(frame, cam, g, t)
        self._glow(frame, cam, {"pos": (pos + d * R0 * 0.5).tolist(), "radius": R0 * 1.3, "reach": 10, "color": [1.0, 0.62, 0.3], "gain": g0 * 0.20 * fl}, t)
        self._glow(frame, cam, {"pos": pos.tolist(), "radius": R0 * 0.45, "reach": 8, "color": [1.0, 0.95, 0.85], "gain": g0 * 0.7 * fl}, t)

    def _dustburst(self, frame, cam, sp, t):
        t0 = sp.get("t0", 0.0)
        tau = t - t0
        if tau < 0:
            return
        key = ("dust", sp.get("seed", 1), sp.get("n", 2500))
        if key not in self._gal:
            r = np.random.default_rng(sp.get("seed", 1))
            n = sp.get("n", 2500)
            self._gal[key] = (r.uniform(0, 2 * math.pi, n), r.uniform(0.2, 1.0, n) ** 0.7, r.uniform(0.3, 1.0, n))
        ang, spd, lift = self._gal[key]
        o = np.array(sp["pos"], np.float32)
        v = sp.get("speed", 40.0)
        rr = v * spd * (1 - np.exp(-tau / 1.6)) * 1.6
        pts = np.stack([o[0] + rr * np.cos(ang), o[1] + sp.get("lift", 6.0) * lift * (1 - np.exp(-tau / 1.2)) * (1 + 0.8 * np.exp(-rr / 20.0)), o[2] + rr * np.sin(ang)], 1)
        sx, sy, z = cam.project(pts.astype(np.float32))
        m = (z > 0.5) & (sx > 1) & (sx < self.W - 2) & (sy > 1) & (sy < self.H - 2)
        if m.any():
            col = np.tile(np.array(sp.get("color", [0.75, 0.5, 0.32]), np.float32) * sp.get("gain", 1.0) * 0.5, (int(m.sum()), 1))
            self._splat(frame, sx[m], sy[m], col)

    def _motes(self, frame, cam, sp, t):
        key = ("motes", sp.get("seed", 1), sp.get("n", 900))
        if key not in self._gal:
            r = np.random.default_rng(sp.get("seed", 1))
            self._gal[key] = r.uniform(-0.5, 0.5, (sp.get("n", 900), 3)).astype(np.float32)
        P = self._gal[key]
        box = float(sp.get("box", 60.0))
        w = np.array(sp.get("wind", [6.0, 0.4, 2.0]), np.float32)
        rel = ((P * box + w * t + box / 2) % box) - box / 2 + (cam.pos * 0) + np.array([0, box * 0.15, 0], np.float32)
        pts = rel + cam.pos + cam.fwd * box * 0.35
        sx, sy, z = cam.project(pts.astype(np.float32))
        m = (z > 0.5) & (sx > 1) & (sx < self.W - 2) & (sy > 1) & (sy < self.H - 2)
        if m.any():
            col = np.tile(np.array(sp.get("color", [0.8, 0.55, 0.35]), np.float32) * sp.get("gain", 0.5), (int(m.sum()), 1))
            self._splat(frame, sx[m], sy[m], col)

    def _stream(self, frame, cam, sp, t):
        """particulas fluindo ao longo de um eixo (particulas solares, vento solar)."""
        key = ("stream", sp.get("seed", 1), sp.get("n", 600))
        if key not in self._gal:
            r = np.random.default_rng(sp.get("seed", 1))
            n = sp.get("n", 600)
            self._gal[key] = (r.uniform(0, 1, n), r.normal(0, 1, (n, 2)), r.uniform(0.6, 1.4, n))
        u0, off, spd = self._gal[key]
        a = np.array(sp["from"], np.float32)
        b = np.array(sp["to"], np.float32)
        dv = b - a
        ax = dv / np.linalg.norm(dv)
        e1 = np.cross(ax, [0, 1, 0]) if abs(ax[1]) < 0.9 else np.cross(ax, [1, 0, 0])
        e1 /= np.linalg.norm(e1)
        e2 = np.cross(ax, e1)
        u = (u0 + t * sp.get("speed", 0.35) * spd) % 1.0
        pts = a[None, :] + dv[None, :] * u[:, None] + (e1[None, :] * off[:, :1] + e2[None, :] * off[:, 1:2]) * sp.get("spread", 20.0)
        sx, sy, z = cam.project(pts.astype(np.float32))
        m = (z > 0.5) & (sx > 1) & (sx < self.W - 2) & (sy > 1) & (sy < self.H - 2)
        if m.any():
            col = np.tile(np.array(sp.get("color", [1.0, 0.8, 0.4]), np.float32) * sp.get("gain", 3.0), (int(m.sum()), 1))
            self._splat(frame, sx[m], sy[m], col)

    def _path(self, frame, cam, sp, t):
        """linha/orbita pontilhada; sp['frac'] = fracao desenhada (0..1)."""
        n = sp.get("n", 360)
        frac = float(sp.get("frac", 1.0))
        u = np.linspace(0, frac, max(int(n * frac), 2))
        if sp.get("kind", "ellipse") == "poly":                    # polilinha (ex.: rota sobre o relevo): pts [[x,y,z],...], desenhada ate 'frac'
            P_ = np.array(sp["pts"], np.float32)
            seg = np.linalg.norm(np.diff(P_, axis=0), axis=1)
            cum = np.concatenate([[0], np.cumsum(seg)]) / max(seg.sum(), 1e-9)
            uu = np.linspace(0, frac, max(int(sp.get("n", 600) * frac), 2))
            pts = np.stack([np.interp(uu, cum, P_[:, c]) for c in range(3)], 1)
        elif sp.get("kind", "ellipse") == "line":
            A, B = np.array(sp["a"], np.float32), np.array(sp["b"], np.float32)
            pts = A[None, :] + (B - A)[None, :] * u[:, None]
        else:
            c = np.array(sp.get("c", [0, 0, 0]), np.float32)
            ang = sp.get("a0", 0.0) + (sp.get("a1", 2 * math.pi) - sp.get("a0", 0.0)) * u
            x, z = sp["a"] * np.cos(ang), sp["b"] * np.sin(ang)
            rot = sp.get("rotate", 0.0)
            pts = np.stack([c[0] + x * math.cos(rot) - z * math.sin(rot), np.full_like(x, c[1]), c[2] + x * math.sin(rot) + z * math.cos(rot)], 1)
        sx, sy, z = cam.project(pts.astype(np.float32))
        m = (z > 0.5) & (sx > 1) & (sx < self.W - 2) & (sy > 1) & (sy < self.H - 2)
        if m.any():
            col = np.tile(np.array(sp.get("color", [0.6, 0.8, 1.0]), np.float32) * sp.get("gain", 1.0), (int(m.sum()), 1))
            self._splat(frame, sx[m], sy[m], col)
        if sp.get("pulse") and len(pts) > 2:                      # cabeca luminosa na ponta do trecho
            e = pts[-1]
            self._glow(frame, cam, {"pos": e.tolist(), "radius": sp.get("pulse_r", 1.0), "color": sp.get("color", [0.8, 0.9, 1.0]), "gain": sp.get("pulse", 2.0), "reach": 8}, t)

    # ------------------------------------------------------------------ pos-processamento por cena
    def _post_scene(self, frame, t, s):
        W, H = self.W, self.H
        br = np.maximum(cv2.resize(frame, (W // 4, H // 4), interpolation=cv2.INTER_AREA) - s.get("bloom_threshold", 0.85), 0)
        k = max(W / 1280.0, 1.0)                                  # bloom proporcional a resolucao (4K = halo do mesmo tamanho relativo)
        bloom = cv2.GaussianBlur(br, (0, 0), 3 * k) + cv2.GaussianBlur(br, (0, 0), 10 * k) * 1.2 + cv2.GaussianBlur(br, (0, 0), 28 * k) * 1.6
        frame += cv2.resize(bloom, (W, H), interpolation=cv2.INTER_LINEAR) * s.get("bloom", self.base["render"].get("bloom", 0.5))
        img = 1 - np.exp(-frame * s.get("exposure", 1.25))
        img = np.power(np.clip(img, 0, 1), 0.92)
        img *= self.vig
        img += self.rng.normal(0, self.base["render"].get("grain", 0.009), (H, W, 1)).astype(np.float32)
        fi, fo = s.get("fade_in", 0.45), s.get("fade_out", 0.45)
        k = min(1.0, (t - s["start"]) / fi if fi > 0 else 1.0, (s["end"] - t) / fo if fo > 0 else 1.0)
        return np.clip(img * max(k, 0.0), 0, 1)

    # ------------------------------------------------------------------ API
    # ------------------------------------------------------------------ cena: parametros dinamicos
    @staticmethod
    def _lerp_tree(a, b, w):
        if isinstance(a, dict):
            return {k: Film._lerp_tree(a[k], b.get(k, a[k]), w) for k in a}
        if isinstance(a, (list, tuple)):
            return [Film._lerp_tree(x, y, w) for x, y in zip(a, b)]
        if isinstance(a, bool) or not isinstance(a, (int, float)):
            return a
        return a + (b - a) * w

    def _tparams(self, s, t):
        base = s.get("tp", {})
        ks = s.get("tkeys")
        if not ks:
            return base
        ts = [k[0] for k in ks]
        if t <= ts[0]:
            return self._merge(base, ks[0][1])
        if t >= ts[-1]:
            return self._merge(base, ks[-1][1])
        i = int(np.searchsorted(ts, t, side="right") - 1)
        w = (t - ts[i]) / (ts[i + 1] - ts[i])
        w = w * w * (3 - 2 * w)
        A, B = self._merge(base, ks[i][1]), self._merge(base, ks[i + 1][1])
        return self._lerp_tree(A, B, w)

    @staticmethod
    def _merge(base, over):
        out = {k: (dict(v) if isinstance(v, dict) else v) for k, v in base.items()}
        for k, v in over.items():
            if isinstance(v, dict) and isinstance(out.get(k), dict):
                out[k] = {**out[k], **v}
            else:
                out[k] = v
        return out

    def terrain_for(self, cfg):
        key = repr(sorted(cfg.items()))
        if key not in self._gal:
            self._gal[key] = GeoTerrain(cfg) if cfg.get("geo") else Terrain(cfg, N=int(cfg.get("res", 2048)))
        return self._gal[key]

    def _prep_sprites(self, sprites, t):
        out = []
        for sp in sprites:
            sp = dict(sp)
            ks = sp.get("keys")
            if ks:
                a = np.array(ks, float)
                if t < a[0, 0]:
                    continue
                if t > a[-1, 0]:
                    if not sp.get("persist"):
                        continue
                    sp["pos"] = a[-1, 1:4].tolist()
                else:
                    sp["pos"] = [float(np.interp(t, a[:, 0], a[:, c])) for c in (1, 2, 3)]
            rk = sp.get("rot")
            if rk:
                a = np.array(rk, float)
                sp["yaw"], sp["pitch"], sp["roll"] = [float(np.interp(t, a[:, 0], a[:, c])) for c in (1, 2, 3)]
            fe = sp.get("fl_env")
            if fe:
                e_ = np.array(fe, float)
                sp["fl"] = float(np.interp(t, e_[:, 0], e_[:, 1], left=e_[0, 1] if sp.get("env_hold", True) else 0.0, right=e_[-1, 1]))
            ev = sp.get("env")
            if ev:
                e = np.array(ev, float)
                k = float(np.interp(t, e[:, 0], e[:, 1], left=e[0, 1] if sp.get("env_hold") else 0.0, right=e[-1, 1] if sp.get("env_hold") else 0.0))
                if sp.get("env_as") == "frac":
                    sp["frac"] = k
                    if k <= 0.002:
                        continue
                else:
                    if k <= 0.002:
                        continue
                    sp["gain"] = sp.get("gain", 1.0) * k
            out.append(sp)
        return out

    # ------------------------------------------------------------------ render de uma cena
    def _render_scene(self, i, t):
        s = self.scenes[i]
        self.stars_for(s.get("stars", {"far": 7000, "near": 2500, "cube": 160}))
        sun = s.get("sun", {"dir": [-0.8, 0.25, 0.35], "intensity": 0.0})
        pos, look, fov, roll = self.paths[i].at(t)
        fl = s.get("follow")
        if fl:                                                    # camera presa a um sprite (nave) com deslocamentos por keyframe
            spf = self._prep_sprites([s["sprites"][fl["sprite"]]], t)
            if spf:
                pp = np.array(spf[0]["pos"], np.float32)
                def _ik(ks):
                    a_ = np.array(ks, float)
                    return np.array([np.interp(t, a_[:, 0], a_[:, c]) for c in (1, 2, 3)], np.float32)
                pos, look = pp + _ik(fl["offset"]), pp + _ik(fl["look"])
        terr = s.get("terrain")
        if terr and s.get("origin"):                              # origem do cenario: desloca camera/objetos p/ uma area plana do mapa
            ox, oz = s["origin"]
            pos = pos + np.array([ox, 0, oz], np.float32)
            look = look + np.array([ox, 0, oz], np.float32)
        if terr and terr.get("agl", True):                        # alturas da camera relativas ao solo
            tr0 = self.terrain_for(terr)
            pos = pos.copy()
            look = look.copy()
            pos[1] += float(tr0.height(np.array([pos[0]], np.float32), np.array([pos[2]], np.float32))[0])
            look[1] += float(tr0.height(np.array([look[0]], np.float32), np.array([look[2]], np.float32))[0])
        cam = Camera(pos, look, self.W, self.H, fov, roll)
        self._tdepth = None
        self._cl, self._ca, self._cg = 1.0, 1.0, 0.78
        frame = np.zeros((self.H, self.W, 3), np.float32)
        if terr:
            tp = self._tparams(s, t)
            L = _unit(tp["sun_dir"])
            daylight = float(smoothstep(-0.16, 0.10, L[1]))
            self.sun_dir = L
            self.sun_col = np.array(tp.get("sun_color", [1.0, 0.9, 0.78]), np.float32)
            self._cl = tp.get("sun_int", 1.0) * daylight ** 0.6 * 1.0
            sk_ = tp["sky"]
            self._envl = {"horizon": [c_ * (0.15 + 0.85 * daylight) for c_ in sk_["horizon"]], "zenith": [c_ * (0.1 + 0.9 * daylight) for c_ in sk_["zenith"]],
                          "ground": [0.50 * (0.05 + 0.95 * daylight * tp.get("sun_int", 1.0)), 0.30 * (0.05 + 0.95 * daylight * tp.get("sun_int", 1.0)), 0.18 * (0.05 + 0.95 * daylight * tp.get("sun_int", 1.0))],
                          "sun_dir": list(L), "sun_col": list(tp.get("sun_color", [1.0, 0.9, 0.78])), "sun_int": float(tp.get("sun_int", 1.0)) * daylight ** 0.6 * 1.4}
            self._ca = max(0.25 + 0.75 * daylight, s.get("craft_amb", 0.0))
            self._cg = 1.0
            self.p = {"world": {"sun": {"intensity": 0.0}, "nebula_gain": s.get("sky_gain", 1.0)}, "render": self.base["render"]}
            if daylight < 0.97:
                self.neb = self.sky_for(s.get("sky", "home"))
                self._nebula(frame, cam)
                self._stars(frame, cam)
            tr = self.terrain_for(terr)
            frame, self._tdepth = tr.render(cam, frame, tp, self.W, self.H, scale=s.get("tscale", 0.6))
            sprites = self._prep_sprites(s.get("sprites", []) + getattr(self, "_dyn", []), t)
            if s.get("origin"):
                for sp in sprites:
                    if "pos" in sp:
                        sp["pos"] = [sp["pos"][0] + s["origin"][0], sp["pos"][1], sp["pos"][2] + s["origin"][1]]
            for sp in sprites:                                       # objetos 'ground': y relativo ao solo
                if sp.get("ground"):
                    x_, z_ = sp["pos"][0], sp["pos"][2]
                    sp["pos"] = [x_, sp["pos"][1] + float(tr.height(np.array([x_], np.float32), np.array([z_], np.float32))[0]), z_]
            for sp in sprites:
                if sp["type"] in ("glow", "flame", "dustburst", "motes", "stream", "path", "points"):
                    getattr(self, "_" + sp["type"])(frame, cam, sp, t)
            for sp in sprites:
                if sp["type"] == "craft":
                    self._craft(frame, cam, sp, t)
            self._tdepth = None
            return (self._post_scene(frame, t, s) * 255 + 0.5).astype(np.uint8)
        self.sun_dir = _unit(sun["dir"])
        self.sun_col = np.array(sun.get("color", [1.0, 0.95, 0.85]), np.float32)
        self.p = {"world": {"sun": sun, "nebula_gain": s.get("sky_gain", 1.0)}, "render": self.base["render"]}
        self._envl = {**self._default_env(), "sun_dir": list(self.sun_dir), "sun_int": 1.4}
        self.neb = self.sky_for(s.get("sky", "home"))
        self._nebula(frame, cam)
        if s.get("stars", {}).get("far", 1) != 0:
            self._stars(frame, cam)
        sprites = self._prep_sprites(s.get("sprites", []) + getattr(self, "_dyn", []), t)
        for sp in sprites:
            if sp["type"] in ("galaxy", "deepfield", "glow", "pulsar", "blackhole", "points", "flame", "dustburst", "motes", "stream", "path"):
                getattr(self, "_" + sp["type"])(frame, cam, sp, t)
        if sun.get("intensity", 0) > 0:
            self._sun(frame, cam)
        bodies = self._bodies_of(s)
        for B in sorted(bodies, key=lambda B: -np.linalg.norm(self._body_pos(B["spec"], t) - cam.pos)):
            self._body(frame, cam, B, t)
        for sp in sprites:
            if sp["type"] == "craft":
                self._craft(frame, cam, sp, t)
        return (self._post_scene(frame, t, s) * 255 + 0.5).astype(np.uint8)

    def render(self, t):
        i = self.scene_at(t)
        s = self.scenes[i]
        img = self._render_scene(i, t)
        xf = s.get("xfade")
        if xf and i + 1 < len(self.scenes) and t > s["end"] - xf["dur"]:
            a = (t - (s["end"] - xf["dur"])) / xf["dur"]
            a = a * a * (3 - 2 * a)
            img2 = self._render_scene(i + 1, t)
            mix = img.astype(np.float32) * (1 - a) + img2.astype(np.float32) * a
            tint = xf.get("tint")
            if tint:                                              # poeira / flash cobrindo a transicao
                pk = math.sin(math.pi * a) ** 1.5 * xf.get("tint_amt", 0.5)
                mix = mix * (1 - pk) + np.array(tint, np.float32) * 255 * pk
            img = np.clip(mix + 0.5, 0, 255).astype(np.uint8)
        return img
