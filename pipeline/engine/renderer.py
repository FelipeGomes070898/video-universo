"""Renderizador 3D por ray-casting em numpy: nebulosa, estrelas, sol, planetas, aneis, pos-processamento."""
import math
import numpy as np
import cv2
from . import textures as T
from .noise import smoothstep
from .camera import Path, Camera


def _unit(v):
    v = np.asarray(v, np.float32)
    return v / np.linalg.norm(v)


class Renderer:
    def __init__(self, project, W, H):
        self.p, self.W, self.H = project, W, H
        w = project["world"]
        self.sun_dir = _unit(w["sun"]["dir"])
        self.sun_col = np.array(w["sun"].get("color", [1.0, 0.95, 0.85]), np.float32)
        cam = project["camera"]
        self.path = Path(cam["keys"], cam.get("shake", 0.0), cam.get("roll", 0.0))
        self.rng = np.random.default_rng(project.get("seed", 7))
        tex_w = int(project["render"].get("texture_width", 2048))
        self.tex_w, self.tex_h = tex_w, tex_w // 2
        self.neb = T.nebula(self.tex_w, self.tex_h, w.get("seed", 11), w.get("nebula", [[0.5, 0.2, 0.8], [0.1, 0.4, 0.7], [0.8, 0.35, 0.15]]))
        self.bodies = []
        for b in w["bodies"]:
            self.bodies.append(self._prep_body(b))
        self._make_stars(w.get("stars", {}))
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        r = np.hypot((xx - W / 2) / (W / 2), (yy - H / 2) / (H / 2))
        self.vig = (1 - 0.38 * np.clip(r - 0.35, 0, 1) ** 1.6)[..., None].astype(np.float32)

    # ------------------------------------------------------------------ setup
    def _prep_body(self, b):
        tw, th = self.tex_w, self.tex_h
        tx = b["texture"]
        kind, seed = tx["type"], tx.get("seed", 1)
        if kind == "earth":
            tex = T.earth(tw, th, seed)
        elif kind == "rocky":
            tex = T.rocky(tw // 2, th // 2, seed, tuple(tx.get("c1", (0.25, 0.25, 0.26))), tuple(tx.get("c2", (0.62, 0.61, 0.58))), tx.get("craters", 260))
        elif kind == "gas":
            tex = T.gas(tw, th, seed, tx["palette"], tx.get("bands", 9.0), tx.get("turbulence", 1.0))
        else:
            raise ValueError("texture.type desconhecido: " + kind)
        out = dict(spec=b, tex=tex)
        if b.get("ring"):
            rg = b["ring"]
            out["ring_tex"] = T.make_ring_profile(2048, rg.get("seed", 3), tuple(rg.get("color", (0.85, 0.74, 0.55))))
            out["ring_n"] = _unit(rg.get("normal", [0, 1, 0]))
        return out

    def _make_stars(self, s):
        rng = np.random.default_rng(5)
        pal = np.array([[0.7, 0.8, 1.0], [1, 1, 1], [1, 0.9, 0.7], [1, 0.7, 0.5]], np.float32)
        nf, nn = int(s.get("far", 7000)), int(s.get("near", 2500))
        d = rng.normal(size=(nf, 3)).astype(np.float32)
        d /= np.linalg.norm(d, axis=1, keepdims=True)
        self.far_pos = d * 5000
        self.far_b = rng.uniform(0.15, 1.0, nf).astype(np.float32) ** 2.2 * 1.6
        self.far_c = pal[rng.choice(4, nf, p=[0.25, 0.4, 0.25, 0.1])]
        self.near_S = float(s.get("cube", 160))
        self.near_pos = rng.uniform(-self.near_S / 2, self.near_S / 2, (nn, 3)).astype(np.float32)
        self.near_b = rng.uniform(0.3, 1.0, nn).astype(np.float32)
        self.near_c = pal[rng.choice(4, nn, p=[0.25, 0.4, 0.25, 0.1])]

    # ------------------------------------------------------------------ helpers
    def _splat(self, frame, sx, sy, col):
        W, H = self.W, self.H
        x0, y0 = np.floor(sx).astype(np.int64), np.floor(sy).astype(np.int64)
        fx, fy = sx - x0, sy - y0
        flat = frame.reshape(-1, 3)
        for dx, dy, wt in ((0, 0, (1 - fx) * (1 - fy)), (1, 0, fx * (1 - fy)), (0, 1, (1 - fx) * fy), (1, 1, fx * fy)):
            xx, yy = x0 + dx, y0 + dy
            ok = (xx >= 0) & (xx < W) & (yy >= 0) & (yy < H)
            idx = yy[ok] * W + xx[ok]
            for c in range(3):
                flat[:, c] += np.bincount(idx, weights=(wt * col[:, c])[ok], minlength=W * H).astype(np.float32)

    def _remap(self, tex, u, v):
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

    def _body_pos(self, b, t):
        o = b.get("orbit")
        if not o:
            return np.array(b["pos"], np.float32)
        a = 2 * math.pi * (t / o["period"]) + o.get("phase", 0.0)
        c = np.array(o["center"], np.float32)
        return c + np.array([math.cos(a) * o["radius"], o.get("y", 0.0), math.sin(a) * o["radius"]], np.float32)

    # ------------------------------------------------------------------ layers
    def _nebula(self, frame, cam):
        W, H = self.W // 2, self.H // 2
        X = (np.arange(W, dtype=np.float32) + 0.5 - W / 2)[None, :]
        Y = (H / 2 - (np.arange(H, dtype=np.float32) + 0.5))[:, None]
        f = cam.f / 2
        d = [cam.fwd[i] * f + cam.right[i] * X + cam.up[i] * Y for i in range(3)]
        n = np.sqrt(d[0] ** 2 + d[1] ** 2 + d[2] ** 2)
        dx, dy, dz = d[0] / n, d[1] / n, d[2] / n
        lon = np.arctan2(dz, dx) / (2 * math.pi) + 0.5
        lat = 0.5 - np.arcsin(np.clip(dy, -1, 1)) / math.pi
        th, tw = self.neb.shape[:2]
        img = cv2.remap(self.neb, (lon * tw).astype(np.float32), (lat * th).astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
        frame += cv2.resize(img, (self.W, self.H), interpolation=cv2.INTER_LINEAR) * self.p["world"].get("nebula_gain", 1.0)

    def _stars(self, frame, cam):
        rel = self.far_pos
        z = rel @ cam.fwd
        ok = z > 1
        sx = cam.W / 2 + cam.f * (rel[ok] @ cam.right) / z[ok]
        sy = cam.H / 2 - cam.f * (rel[ok] @ cam.up) / z[ok]
        col = self.far_c[ok] * self.far_b[ok][:, None]
        m = (sx > 0) & (sx < self.W - 1) & (sy > 0) & (sy < self.H - 1)
        self._splat(frame, sx[m], sy[m], col[m])
        S = self.near_S
        rel = ((self.near_pos - cam.pos + S / 2) % S) - S / 2
        z = rel @ cam.fwd
        ok = z > 0.6
        rel, z = rel[ok], z[ok]
        sx = cam.W / 2 + cam.f * (rel @ cam.right) / z
        sy = cam.H / 2 - cam.f * (rel @ cam.up) / z
        dist = np.linalg.norm(rel, axis=1)
        edge = np.clip((S / 2 - np.abs(rel).max(1)) / 12, 0, 1)
        br = self.near_b[ok] * np.clip(26 / dist, 0, 1.6) * edge
        col = self.near_c[ok] * br[:, None]
        m = (sx > 0) & (sx < self.W - 1) & (sy > 0) & (sy < self.H - 1)
        self._splat(frame, sx[m], sy[m], col[m])

    def _sun(self, frame, cam):
        sx, sy, z = cam.project(cam.pos + self.sun_dir * 1e4)
        if z[0] <= 0:
            return
        sx, sy = float(sx[0]), float(sy[0])
        s = 4
        gw, gh = self.W // s, self.H // s
        X = (np.arange(gw, dtype=np.float32) + 0.5) * s - sx
        Y = (np.arange(gh, dtype=np.float32) + 0.5) * s - sy
        XX, YY = np.meshgrid(X, Y)
        r = np.hypot(XX, YY) / (self.W / 1280.0)
        g = 9.0 * np.exp(-r / 18.0) + 1.1 / (1 + (r / 110.0) ** 2) + 0.9 * np.exp(-np.abs(YY) / (5 * self.W / 1280.0)) * np.exp(-np.abs(XX) / (420 * self.W / 1280.0))
        g = cv2.resize(g, (self.W, self.H), interpolation=cv2.INTER_LINEAR)
        frame += g[..., None] * self.sun_col * self.p["world"]["sun"].get("intensity", 0.7)
        # ghosts de lente
        if 0 <= sx <= self.W and 0 <= sy <= self.H:
            vis = 1 - max(abs(sx - self.W / 2) / (self.W / 2), abs(sy - self.H / 2) / (self.H / 2)) * 0.6
            cx, cy = self.W / 2, self.H / 2
            for k, rad, tint in ((-0.45, 40, (0.4, 0.7, 1.0)), (-0.9, 70, (1.0, 0.6, 0.3)), (0.5, 28, (0.6, 1.0, 0.7)), (1.4, 55, (0.8, 0.5, 1.0))):
                gx, gy = cx + (sx - cx) * k, cy + (sy - cy) * k
                x0, x1 = int(max(gx - rad * 2, 0)), int(min(gx + rad * 2, self.W))
                y0, y1 = int(max(gy - rad * 2, 0)), int(min(gy + rad * 2, self.H))
                if x1 <= x0 or y1 <= y0:
                    continue
                yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
                rr = np.hypot(xx - gx, yy - gy) / rad
                a = np.exp(-((rr - 0.8) / 0.25) ** 2) * 0.05 * vis + np.exp(-rr ** 2 * 4) * 0.02 * vis
                frame[y0:y1, x0:x1] += a[..., None] * np.array(tint, np.float32)

    def _body(self, frame, cam, B, t):
        b, tex = B["spec"], B["tex"]
        W, H = self.W, self.H
        C = self._body_pos(b, t)
        R = float(b["radius"])
        ring = b.get("ring")
        atm = b.get("atmosphere")
        thick = atm.get("thickness", 0.10) if atm else 0.0
        Rb = max(R * (1 + thick * 3), R * ring["outer"] if ring else R)
        O = cam.pos
        oc = O - C
        dist = float(np.linalg.norm(oc))
        zc = float((C - O) @ cam.fwd)
        if dist < R * 1.00003 or zc < -Rb:
            return
        if zc < 0.1 + 0.25 * Rb or dist <= Rb * 1.02:        # camera colada no corpo: cobre a tela toda
            x0, x1, y0, y1 = 0, W, 0, H
        else:
            sxc, syc, _ = cam.project(C)
            sr = cam.f * Rb / math.sqrt(max(dist ** 2 - Rb ** 2, 1e-3)) * 1.08
            x0, x1 = int(max(sxc[0] - sr, 0)), int(min(sxc[0] + sr, W))
            y0, y1 = int(max(syc[0] - sr, 0)), int(min(syc[0] + sr, H))
        if x1 <= x0 or y1 <= y0:
            return
        X = (np.arange(x0, x1, dtype=np.float32) + 0.5 - W / 2)[None, :]
        Y = (H / 2 - (np.arange(y0, y1, dtype=np.float32) + 0.5))[:, None]
        d = [cam.fwd[i] * cam.f + cam.right[i] * X + cam.up[i] * Y for i in range(3)]
        nrm = np.sqrt(d[0] ** 2 + d[1] ** 2 + d[2] ** 2)
        dx, dy, dz = d[0] / nrm, d[1] / nrm, d[2] / nrm
        bb = dx * oc[0] + dy * oc[1] + dz * oc[2]
        cc = float(oc @ oc) - R * R
        disc = bb * bb - cc
        dperp = np.sqrt(np.maximum(R * R - disc, 0))
        cov = np.clip((R - dperp) * cam.f / dist + 0.5, 0, 1) * (bb < 0)
        view = frame[y0:y1, x0:x1]
        L = self.sun_dir
        # ---- glow atmosferico externo
        if atm:
            Rb_ = R * (1 + thick * 3)
            dpe = np.where(bb < 0, dperp, dist)            # camera dentro da atmosfera: raios que se afastam usam a distancia da propria camera (continuo no horizonte)
            g = (((disc < 0) & (bb < 0)) | ((bb >= 0) & (dist < Rb_))) & (dpe < Rb_)
            if g.any():
                h = (dpe[g] - R) / (R * thick)
                bbe = np.where(bb < 0, bb, 0.0)
                qx, qy, qz = oc[0] - bbe[g] * dx[g], oc[1] - bbe[g] * dy[g], oc[2] - bbe[g] * dz[g]
                nl = (qx * L[0] + qy * L[1] + qz * L[2]) / np.maximum(dpe[g], 1e-6)
                lit = 1.0 if b.get("emissive") else np.clip(nl * 0.9 + 0.3, 0, 1)
                glow = np.exp(-3.2 * h) * lit * atm.get("strength", 1.0)
                view[g] += glow[:, None] * np.array(atm["color"], np.float32)
        # ---- esfera
        hit = cov > 0
        tS = np.full(bb.shape, np.inf, np.float32)
        if hit.any():
            dcl = np.maximum(disc[hit], 0)
            t_ = -bb[hit] - np.sqrt(dcl)
            D = np.stack([dx[hit], dy[hit], dz[hit]], 1)
            P = O + t_[:, None] * D
            N = (P - C) / R
            tS[hit] = t_
            nl = N @ L
            tilt = math.radians(b.get("tilt", 0.0))
            spin = math.radians(b.get("spin0", 0.0) + b.get("spin_rate", 5.0) * t)
            ct, st = math.cos(tilt), math.sin(tilt)
            nx, ny = N[:, 0] * ct + N[:, 1] * st, -N[:, 0] * st + N[:, 1] * ct
            nz = N[:, 2]
            cs, sn = math.cos(spin), math.sin(spin)
            rx, rz = nx * cs + nz * sn, -nx * sn + nz * cs
            u = np.arctan2(rz, rx) / (2 * math.pi) + 0.5
            v = 0.5 - np.arcsin(np.clip(ny, -1, 1)) / math.pi
            alb = self._remap(tex["albedo"], u, v)
            lit = np.clip((nl + 0.08) / 1.08, 0, 1) ** 0.9
            amb = np.array(b.get("ambient", [0.012, 0.016, 0.03]), np.float32)
            col = alb * (lit[:, None] * self.sun_col * b.get("light", 1.7)) + alb * amb
            if b.get("emissive"):                       # estrelas: autoluminosas com escurecimento de borda
                mu = np.clip(-(D * N).sum(1), 0, 1)
                col = alb * ((0.30 + 0.70 * mu ** 0.7) * b.get("emit", 2.4))[:, None]
                nl = np.ones_like(nl)
            if "spec" in tex:
                sp = self._remap(tex["spec"], u, v).reshape(-1)
                Hh = L - D
                Hh /= np.linalg.norm(Hh, axis=1, keepdims=True)
                s = np.clip((N * Hh).sum(1), 0, 1) ** 90 * sp * lit * 1.4
                col += s[:, None] * self.sun_col
            if "lights" in tex:
                lg = self._remap(tex["lights"], u, v).reshape(-1) * (1 - smoothstep(-0.12, 0.12, nl))
                col += lg[:, None] * np.array([1.0, 0.75, 0.35], np.float32) * 0.9
            if "clouds" in tex and b.get("clouds", False):
                drift = b.get("cloud_drift", 0.004) * t
                cl = self._remap(tex["clouds"], (u + drift) % 1.0, v).reshape(-1) * 0.85
                cc_col = (lit[:, None] * self.sun_col * 1.5 + 0.02) * np.array(b.get("cloud_tint", [1, 1, 1]), np.float32)
                col = col * (1 - cl[:, None]) + cc_col * cl[:, None]
            if "glow" in tex and b.get("glow_gain", 0) > 0:        # lava / emissao propria (visivel tambem no lado escuro)
                gl = self._remap(tex["glow"], u, v).reshape(-1)
                col += gl[:, None] * np.array(b.get("glow_color", [1.0, 0.38, 0.08]), np.float32) * b["glow_gain"]
            if atm:
                fres = (1 - np.clip(-(D * N).sum(1), 0, 1)) ** 3
                rim = fres * np.clip(nl + 0.25, 0, 1) * atm.get("rim", 1.6)
                col += rim[:, None] * np.array(atm["color"], np.float32)
            cv = cov[hit][:, None]
            view[hit] = view[hit] * (1 - cv) + col * cv
        # ---- aneis
        if ring:
            nr = B["ring_n"]
            den = dx * nr[0] + dy * nr[1] + dz * nr[2]
            num = float((C - O) @ nr)
            with np.errstate(divide="ignore", invalid="ignore"):
                tr = num / den
            ok = (np.abs(den) > 1e-4) & (tr > 0) & (tr < tS)
            if ok.any():
                tr_ = tr[ok]
                px, py, pz = O[0] + tr_ * dx[ok] - C[0], O[1] + tr_ * dy[ok] - C[1], O[2] + tr_ * dz[ok] - C[2]
                rr = np.sqrt(px * px + py * py + pz * pz) / R
                inner, outer = ring["inner"], ring["outer"]
                ok2 = (rr > inner) & (rr < outer)
                if ok2.any():
                    idx = np.nonzero(ok)
                    sel = (idx[0][ok2], idx[1][ok2])
                    x_ = (rr[ok2] - inner) / (outer - inner)
                    rt = B["ring_tex"]
                    ii = np.clip((x_ * (len(rt) - 1)).astype(int), 0, len(rt) - 1)
                    rgb, a = rt[ii, :3], rt[ii, 3:4] * ring.get("opacity", 0.92)
                    bs = px[ok2] * L[0] + py[ok2] * L[1] + pz[ok2] * L[2]
                    cs2 = (px[ok2] ** 2 + py[ok2] ** 2 + pz[ok2] ** 2) - R * R
                    shadow = (bs * bs - cs2 > 0) & (bs < 0)
                    lf = np.where(shadow, 0.03, 1.0)[:, None] * (0.30 + 0.70 * abs(float(nr @ L)))
                    c = rgb * self.sun_col * lf * 1.7 + rgb * 0.01
                    view[sel] = view[sel] * (1 - a) + c * a

    def _post(self, frame, t):
        W, H = self.W, self.H
        br = np.maximum(cv2.resize(frame, (W // 4, H // 4), interpolation=cv2.INTER_AREA) - 0.85, 0)
        bloom = cv2.GaussianBlur(br, (0, 0), 3) + cv2.GaussianBlur(br, (0, 0), 10) * 1.2 + cv2.GaussianBlur(br, (0, 0), 28) * 1.6
        frame += cv2.resize(bloom, (W, H), interpolation=cv2.INTER_LINEAR) * self.p["render"].get("bloom", 0.55)
        img = 1 - np.exp(-frame * 1.25)                         # tonemap suave
        img = np.power(np.clip(img, 0, 1), 0.92)
        img *= self.vig
        img += self.rng.normal(0, self.p["render"].get("grain", 0.010), (H, W, 1)).astype(np.float32)
        fi, fo = self.p["render"].get("fade_in", 1.0), self.p["render"].get("fade_out", 1.5)
        dur = self.p["briefing"]["duration_seconds"]
        k = min(1.0, t / fi if fi > 0 else 1.0, (dur - t) / fo if fo > 0 else 1.0)
        return np.clip(img * max(k, 0.0), 0, 1)

    # ------------------------------------------------------------------ API
    def render(self, t):
        pos, look, fov, roll = self.path.at(t)
        cam = Camera(pos, look, self.W, self.H, fov, roll)
        frame = np.zeros((self.H, self.W, 3), np.float32)
        self._nebula(frame, cam)
        self._stars(frame, cam)
        self._sun(frame, cam)
        order = sorted(self.bodies, key=lambda B: -np.linalg.norm(self._body_pos(B["spec"], t) - cam.pos))
        for B in order:
            self._body(frame, cam, B, t)
        return (self._post(frame, t) * 255 + 0.5).astype(np.uint8)
