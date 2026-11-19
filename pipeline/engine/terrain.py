"""Terreno 3D procedural (campo de altura) com ray-marching em numpy: planicies, crateras, dunas, sombras, nevoa de poeira,
ceu marciano (cor de caramelo, por-do-sol azul) e estrelas a noite. Usado pelas cenas de superficie.

Coordenadas: y para cima, x/z no plano; o mapa e periodico (tile de `size` unidades)."""
import math
import numpy as np
import cv2
from .noise import fft_noise, smoothstep


def _remap(tex, x, z, size, interp=cv2.INTER_LINEAR):
    """amostra bilinear periodica de tex (N,N[,C]) em coordenadas de mundo x,z (arrays 1D)."""
    n = tex.shape[0]
    m = len(x)
    cols = 512
    rows = -(-m // cols)
    mx = np.zeros(rows * cols, np.float32)
    my = np.zeros(rows * cols, np.float32)
    mx[:m] = (x / size * n) % n
    my[:m] = (z / size * n) % n
    out = cv2.remap(tex, mx.reshape(rows, cols), my.reshape(rows, cols), interp, borderMode=cv2.BORDER_WRAP)
    return out.reshape(rows * cols, *tex.shape[2:])[:m]


class Terrain:
    def __init__(self, cfg, N=1024):
        self.cfg = cfg
        self.N = N
        self.size = float(cfg.get("size", 1400.0))
        self.amp = float(cfg.get("amp", 34.0))
        seed = cfg.get("seed", 3)
        rng = np.random.default_rng(seed)
        base = fft_noise(N, N, 3.6, seed)
        mid = fft_noise(N, N, 2.7, seed + 1)
        fine = fft_noise(N, N, 1.9, seed + 2)
        h = (base - 0.5) * 2.2 + (mid - 0.5) * 0.7 + (fine - 0.5) * 0.14
        # dunas: cristas suaves em direcao dominante
        yy, xx = np.mgrid[0:N, 0:N].astype(np.float32)
        ang = cfg.get("dune_angle", 0.5)
        ph = (xx * math.cos(ang) + yy * math.sin(ang)) * (2 * math.pi / cfg.get("dune_wave", 28.0))
        ph = ph + (fft_noise(N, N, 2.4, seed + 3) - 0.5) * 9.0
        dunes = (ph / (2 * math.pi)) % 1.0
        dunes = np.where(dunes < 0.8, dunes / 0.8, (1 - dunes) / 0.2) * 0.07
        dmask = smoothstep(0.46, 0.58, fft_noise(N, N, 2.8, seed + 4))
        h = h + dunes * dmask * cfg.get("dunes", 1.0)
        h = (h - h.min()) / (h.max() - h.min() + 1e-9)
        h = h * self.amp
        # crateras (com rebordo), com envoltoria periodica
        px = self.size / N
        for _ in range(cfg.get("craters", 70)):
            r = rng.uniform(0.008, 0.05) ** 1.0 * N * rng.uniform(0.6, 1.6) / 1.0
            r = max(r, 5.0)
            cx, cy = rng.integers(0, N), rng.integers(0, N)
            R = int(r * 1.6)
            ly, lx = np.mgrid[-R:R + 1, -R:R + 1].astype(np.float32)
            d = np.hypot(lx, ly) / r
            depth = r * px * rng.uniform(0.05, 0.10) * (self.amp / 12.0 + 0.35)
            bowl = -depth * np.clip(1 - d ** 2, 0, 1) ** 0.9
            rim = depth * 0.45 * np.exp(-((d - 1.0) / 0.16) ** 2)
            patch = (bowl + rim * (d > 0.6)).astype(np.float32)
            rows = (cy + np.arange(-R, R + 1)) % N
            colsx = (cx + np.arange(-R, R + 1)) % N
            h[np.ix_(rows, colsx)] += patch
        self.h = h.astype(np.float32)
        self.hmax = float(self.h.max()) + 1.0
        # normais
        gy, gx = np.gradient(self.h, px)
        nrm = np.stack([-gx, np.ones_like(gx), -gy], -1)
        nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True)
        self.nrm = nrm.astype(np.float32)
        # albedo
        pal = cfg.get("palette", {"low": [0.36, 0.17, 0.09], "high": [0.72, 0.46, 0.28], "dark": [0.10, 0.085, 0.08]})
        t = smoothstep(0.15, 0.85, (self.h - self.h.min()) / (self.amp + 1e-6))[..., None]
        alb = np.array(pal["low"], np.float32) * (1 - t) + np.array(pal["high"], np.float32) * t
        dark = smoothstep(0.55, 0.7, fft_noise(N, N, 2.6, seed + 5))[..., None] * cfg.get("dark_rock", 0.7)
        alb = alb * (1 - dark) + np.array(pal["dark"], np.float32) * dark
        grain = (fft_noise(N, N, 0.7, seed + 6) - 0.5) * 0.9
        slope = np.clip(1 - self.nrm[..., 1], 0, 1)[..., None]
        alb = alb * (1 + grain[..., None] * 0.55) * (1 - 0.35 * slope)
        ice = cfg.get("ice")
        if ice:                                              # manchas de gelo/geada
            m = smoothstep(ice["thr"], ice["thr"] + 0.05, fft_noise(N, N, 3.0, seed + 8))[..., None]
            alb = alb * (1 - m) + np.array([0.82, 0.86, 0.9], np.float32) * m
        self.alb = np.clip(alb, 0, 1.2).astype(np.float32)
        # textura de ruido de detalhe (aplicada em tela cheia p/ esconder a suavidade)
        mg = (fft_noise(N, N, 0.9, seed + 11) - 0.5) * 3.2
        gy2, gx2 = np.gradient(cv2.GaussianBlur(mg.astype(np.float32), (0, 0), 0.8))
        self.micro = np.stack([gx2, gy2], -1).astype(np.float32) * 6.0
        self._sky_cache = None

    # ------------------------------------------------------------------ amostragem
    def height(self, x, z, fast=False):
        return _remap(self.h, x, z, self.size, cv2.INTER_LINEAR if fast else cv2.INTER_CUBIC)

    # ------------------------------------------------------------------ ceu
    @staticmethod
    def sky_color(d, L, daylight, k):
        """d: (M,3) direcoes; L: direcao do Sol; k: parametros {horizon, zenith, aureole, haze}."""
        y = np.clip(d[:, 1], 0, 1)[:, None]
        hz = np.array(k["horizon"], np.float32)
        zn = np.array(k["zenith"], np.float32)
        col = hz * (1 - y ** 0.45) + zn * (y ** 0.45)
        cosang = np.clip(d @ L, -1, 1)
        ang = np.arccos(cosang)
        low = np.clip(1.0 - np.abs(L[1]) / 0.35, 0, 1)                       # sol baixo -> aureola azul (por-do-sol marciano)
        blue = np.array(k.get("blue", [0.25, 0.5, 1.0]), np.float32)
        aur = np.exp(-(ang / (0.10 + 0.08 * (1 - low))) ** 2)[:, None]
        col = col + aur * (blue * (0.9 * low + 0.05) + np.array([0.5, 0.3, 0.15], np.float32) * 0.25 * (1 - low))
        tw = math.exp(-((L[1] + 0.03) / 0.10) ** 2)                          # crepusculo: faixa quente/arroxeada no horizonte
        col = col + tw * np.array([0.34, 0.22, 0.28], np.float32) * (1 - y ** 0.4) * k.get("twilight", 1.0)
        col = col + (np.exp(-(ang / 0.006) ** 2) * 30 * (L[1] > -0.02))[:, None] * np.array([1.0, 0.92, 0.82], np.float32) * k.get("disc", 1.0)
        return col * daylight

    # ------------------------------------------------------------------ render
    def render(self, cam, frame_space, p, W, H, scale=0.5):
        """cam: Camera do motor; frame_space: (H,W,3) estrelas/nebulosa (fundo do ceu); p: parametros do instante.
        Retorna (frame, depth)  -- depth em unidades de mundo (inf = ceu)."""
        w, h_ = int(W * scale), int(H * scale)
        o = cam.pos.astype(np.float32)
        X = (np.arange(w, dtype=np.float32) + 0.5 - w / 2) / scale
        Y = (h_ / 2 - (np.arange(h_, dtype=np.float32) + 0.5)) / scale
        f = cam.f
        d = [cam.fwd[i] * f + cam.right[i] * X[None, :] + cam.up[i] * Y[:, None] for i in range(3)]
        n = np.sqrt(d[0] ** 2 + d[1] ** 2 + d[2] ** 2)
        D = np.stack([(d[i] / n).reshape(-1) for i in range(3)], 1).astype(np.float32)
        M = D.shape[0]
        L = np.array(p["sun_dir"], np.float32)
        L /= np.linalg.norm(L)
        daylight = float(smoothstep(-0.16, 0.10, L[1]))
        sky_k = p["sky"]
        fog = p.get("fog", 0.0012)
        dmax = p.get("dmax", 2200.0)
        # --- ray marching
        t = np.full(M, 0.15, np.float32)
        hit = np.zeros(M, bool)
        done = np.zeros(M, bool)
        act = np.arange(M)
        hmax = self.hmax
        up = D[:, 1] > 0
        for it in range(52):
            if len(act) == 0:
                break
            tt = t[act]
            P = o[None, :] + tt[:, None] * D[act]
            hh = self.height(P[:, 0], P[:, 2], fast=True)
            gap = P[:, 1] - hh
            hitm = gap < (0.01 + 0.0015 * tt)
            hit[act[hitm]] = True
            skym = (~hitm) & ((tt > dmax) | ((P[:, 1] > hmax) & up[act]))
            done[act[hitm | skym]] = True
            keep = ~(hitm | skym)
            act = act[keep]
            gap = gap[keep]
            t[act] = t[act] + np.maximum(gap * 0.62, 0.12 + 0.005 * t[act])
        unresolved = ~done
        hit |= unresolved & (t < dmax * 1.5)
        # refinamento
        idx = np.nonzero(hit)[0]
        if len(idx):
            lo = np.maximum(t[idx] - np.maximum(0.12 + 0.004 * t[idx], 0.2), 0.05)
            hi = t[idx].copy()
            for _ in range(7):
                mid = (lo + hi) * 0.5
                P = o[None, :] + mid[:, None] * D[idx]
                above = P[:, 1] > self.height(P[:, 0], P[:, 2])
                lo = np.where(above, mid, lo)
                hi = np.where(above, hi, mid)
            t[idx] = hi
        col = np.zeros((M, 3), np.float32)
        depth = np.full(M, np.inf, np.float32)
        # --- ceu
        sk = np.nonzero(~hit)[0]
        base = cv2.resize(frame_space, (w, h_), interpolation=cv2.INTER_AREA).reshape(-1, 3) * (1 - daylight)
        if len(sk):
            col[sk] = base[sk] + self.sky_color(D[sk], L, daylight, sky_k) * p.get("sky_gain", 1.0)
        # --- terreno
        if len(idx):
            P = o[None, :] + t[idx][:, None] * D[idx]
            nrm = _remap(self.nrm, P[:, 0], P[:, 2], self.size)
            nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-9
            alb = _remap(self.alb, P[:, 0], P[:, 2], self.size)
            mb = _remap(self.micro, P[:, 0], P[:, 2], self.size * 0.25)
            nrm = nrm + np.stack([mb[:, 0], np.zeros(len(mb), np.float32), mb[:, 1]], 1) * (1.0 / (1.0 + t[idx][:, None] * 0.02)) * 0.28
            nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-9
            nl = np.clip(nrm @ L, 0, 1)
            # sombras: marcha em direcao ao Sol
            sh = np.ones(len(idx), np.float32)
            if L[1] > 0.01 and p.get("shadows", True):
                Q0 = P + nrm * 0.25
                s_t = 0.6
                for k in range(14):
                    Q = Q0 + L[None, :] * s_t
                    occ = Q[:, 1] < self.height(Q[:, 0], Q[:, 2], fast=True) - 0.02
                    sh = np.where(occ, 0.0, sh)
                    s_t *= 1.45
            sun_int = p.get("sun_int", 1.0) * daylight ** 0.6
            sun_col = np.array(p.get("sun_color", [1.0, 0.9, 0.78]), np.float32)
            amb = np.array(sky_k["zenith"], np.float32) * (0.35 + 0.65 * nrm[:, 1:2]) * 0.7 * daylight + 0.004
            c = alb * (nl[:, None] * sh[:, None] * sun_col * sun_int * 2.1 + amb)
            # nevoa de poeira (mistura com a cor do horizonte)
            fg = 1 - np.exp(-t[idx] * fog)
            haze = self.sky_color(np.stack([D[idx][:, 0], np.zeros(len(idx), np.float32), D[idx][:, 2]], 1), L, daylight, sky_k)
            c = c * (1 - fg[:, None]) + haze * fg[:, None]
            col[idx] = c
            depth[idx] = t[idx]
        img = col.reshape(h_, w, 3)
        img = cv2.resize(img, (W, H), interpolation=cv2.INTER_CUBIC)
        dep = cv2.resize(depth.reshape(h_, w), (W, H), interpolation=cv2.INTER_NEAREST)
        return np.maximum(img, 0), dep


class GeoTerrain(Terrain):
    """Terreno REAL: DEM (SRTM) + imagem NASA numa regiao (engine/geo.py). cfg: geo='brasil_se', exag (exagero vertical), pad (px de oceano em volta).
    Unidades = km; z positivo = sul; (0,0) = canto noroeste da regiao + margem. A borda do mapa some no oceano (sem repeticao periodica visivel)."""
    def __init__(self, cfg, N=2048):
        from . import geo
        self.cfg = cfg
        g = geo.Grid(cfg["geo"])
        d = geo.load(cfg["geo"])
        N0 = d["dem"].shape[0]
        pad = int(cfg.get("pad", 1024))
        self.grid, self.pad = g, pad
        self.px = float(g.size) / N0
        exag = float(cfg.get("exag", 12.0))
        yy, xx = np.mgrid[0:N0, 0:N0].astype(np.float32)
        edge = np.minimum(np.minimum(xx, N0 - 1 - xx), np.minimum(yy, N0 - 1 - yy))
        w = smoothstep(0.0, 160.0, edge)
        dem = np.maximum(d["dem"], 0.0) / 1000.0 * w
        dem = cv2.GaussianBlur(dem, (0, 0), 0.8)
        rgb = np.power(d["rgb"].astype(np.float32) / 255.0, 2.0) * cfg.get("alb_gain", 1.35)
        ocean = np.array([0.012, 0.07, 0.28], np.float32) * cfg.get("alb_gain", 1.35)
        alb = rgb * w[..., None] + ocean * (1 - w[..., None])
        Nt = N0 + 2 * pad
        h = np.zeros((Nt, Nt), np.float32)
        h[pad:pad + N0, pad:pad + N0] = dem * exag
        A = np.tile(ocean, (Nt, Nt, 1)).astype(np.float32)
        A[pad:pad + N0, pad:pad + N0] = alb
        self.N, self.size = Nt, float(self.px * Nt)
        self.h = h
        self.hmax = float(self.h.max()) + 0.5
        gy, gx = np.gradient(self.h, self.px)
        nrm = np.stack([-gx, np.ones_like(gx), -gy], -1)
        nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True)
        self.nrm = nrm.astype(np.float32)
        self.alb = np.clip(A, 0, 1.3).astype(np.float32)
        self.micro = np.zeros((Nt, Nt, 2), np.float32)
        self._sky_cache = None

    def xz_h(self, lon, lat):
        """(x, z, altura_cena) para um ponto lon/lat -- para tracar rotas rente ao relevo."""
        x, z = self.grid.xz(lon, lat)
        i, j = self.grid.ij(lon, lat)
        hh = float(cv2.remap(self.h, np.array([[i + self.pad]], np.float32), np.array([[j + self.pad]], np.float32), cv2.INTER_LINEAR)[0, 0])
        o = self.pad * self.px
        return x + o, z + o, hh
