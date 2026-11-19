"""Foguete (Starship) renderizado por pixel: SDF + sphere tracing, aco escovado reflexivo, paineis/soldas, escudo termico preto,
flaps, motores, reflexo do ceu/Sol e luz da chama. Suave (sem facetas) e com antialiasing por distancia minima."""
import math
import numpy as np

H_BODY = 36.0
H_TOT = 50.0
R_BODY = 4.5


def _profile(y):
    r = np.full_like(y, R_BODY)
    t = np.clip((y - H_BODY) / (H_TOT - H_BODY), 0, 1)
    nose = R_BODY * np.clip(1 - t ** 1.75, 0, 1) ** 0.72
    return np.where(y > H_BODY, nose, r)


def _box(P, c, h, rr=0.12):
    q = np.abs(P - np.array(c, np.float32)) - np.array(h, np.float32) + rr
    return np.linalg.norm(np.maximum(q, 0), axis=1) + np.minimum(np.max(q, axis=1), 0) - rr


def _parts(P, legs):
    x, y, z = P[:, 0], P[:, 1], P[:, 2]
    rho = np.sqrt(x * x + z * z)
    body = np.maximum(rho - _profile(np.clip(y, 0, H_TOT)), np.maximum(-y, y - H_TOT))
    def tflap(cx, cy, hx, hy, taper):                          # flap trapezoidal: largura diminui com a altura
        k = 1 - taper * np.clip((y - cy) / hy, -1, 1)
        xs = (np.abs(x) - cx) / np.maximum(k, 0.3)
        q = np.stack([np.abs(xs) - hx + 0.1, np.abs(y - cy) - hy + 0.1, np.abs(z) - 0.3 + 0.1], 1)
        return (np.linalg.norm(np.maximum(q, 0), axis=1) + np.minimum(np.max(q, axis=1), 0) - 0.1) * 0.8
    flap = np.minimum(tflap(6.4, 40.5, 2.1, 3.4, 0.45), tflap(7.0, 6.0, 2.9, 5.3, -0.40))
    eng = np.full_like(x, 1e3)
    for ang in (0, 120, 240):
        a = math.radians(ang)
        cx, cz = 2.0 * math.cos(a), 2.0 * math.sin(a)
        r_ = np.sqrt((x - cx) ** 2 + (z - cz) ** 2)
        eng = np.minimum(eng, np.maximum(r_ - (0.55 + 0.5 * np.clip(-y / 1.7, 0, 1)), np.maximum(-(y + 1.7), y - 0.1)))
    r_ = np.sqrt(x * x + z * z)
    eng = np.minimum(eng, np.maximum(r_ - (0.7 + 0.7 * np.clip(-y / 1.7, 0, 1)), np.maximum(-(y + 1.7), y - 0.1)))
    leg = np.full_like(x, 1e3)
    if legs:
        for c in ((5.4, -1.0, 0), (-5.4, -1.0, 0), (0, -1.0, 5.4), (0, -1.0, -5.4)):
            leg = np.minimum(leg, _box(P, c, (0.28, 2.6, 0.28), 0.05))
    return body, flap, eng, leg


def _sdf(P, legs):
    b, f, e, l = _parts(P, legs)
    return np.minimum(np.minimum(b, f), np.minimum(e, l))


def _hash(a, b):
    return np.modf(np.sin(a * 12.9898 + b * 78.233) * 43758.5453)[0] % 1.0


def _smooth(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def _env(d, env):
    up = d[:, 1:2]
    t = np.clip(up, 0, 1) ** 0.5
    sky = np.array(env["horizon"], np.float32) * (1 - t) + np.array(env["zenith"], np.float32) * t
    gnd = np.array(env["ground"], np.float32) * (0.6 + 0.4 * np.clip(-up, 0, 1))
    col = np.where(up >= 0, sky, gnd)
    L = np.array(env["sun_dir"], np.float32)
    s = np.clip(d @ L, 0, 1)[:, None]
    col = col + (s ** 110) * np.array(env["sun_col"], np.float32) * env["sun_int"] * 11.0 + (s ** 9) * np.array(env["sun_col"], np.float32) * env["sun_int"] * 0.35
    return col


def render_starship(film, frame, cam, pos, scale, R, env, legs=False, flame=0.0, gain=1.0, tdepth=None, tile_dir=3.14159):
    W, H = film.W, film.H
    pos = np.asarray(pos, np.float32)
    cen_obj = np.array([0, 24.0, 0], np.float32)
    cen_w = R @ (cen_obj * scale) + pos
    rad = 31.0 * scale
    sx, sy, z = cam.project(cen_w)
    if z[0] <= 0.1:
        return
    dist = float(np.linalg.norm(cen_w - cam.pos))
    pr = cam.f * rad / max(np.sqrt(max(dist ** 2 - rad ** 2, 1e-3)), 1e-3) * 1.1 if dist > rad * 1.05 else max(W, H)
    x0, x1 = int(max(sx[0] - pr, 0)), int(min(sx[0] + pr, W))
    y0, y1 = int(max(sy[0] - pr, 0)), int(min(sy[0] + pr, H))
    if x1 - x0 < 2 or y1 - y0 < 2:
        return
    X = (np.arange(x0, x1, dtype=np.float32) + 0.5 - W / 2)[None, :]
    Y = (H / 2 - (np.arange(y0, y1, dtype=np.float32) + 0.5))[:, None]
    d = [cam.fwd[i] * cam.f + cam.right[i] * X + cam.up[i] * Y for i in range(3)]
    n_ = np.sqrt(d[0] ** 2 + d[1] ** 2 + d[2] ** 2)
    Dw = np.stack([(d[i] / n_).reshape(-1) for i in range(3)], 1).astype(np.float32)
    h, w = y1 - y0, x1 - x0
    Rt = R.T.astype(np.float32)
    o = (Rt @ (cam.pos - pos)) / scale
    Do = (Dw @ R.astype(np.float32))                      # direcao no espaco do objeto (R.T aplicado a cada vetor-linha)
    # esfera englobante (em unidades do objeto) para iniciar o traco
    c = cen_obj
    oc = o - c
    rb = 31.0
    bq = Do @ oc
    disc = bq * bq - (oc @ oc - rb * rb)
    ok = disc > 0
    t = np.where(ok, np.maximum(-bq - np.sqrt(np.maximum(disc, 0)), 0.0), 0.0).astype(np.float32)
    t_end = np.where(ok, -bq + np.sqrt(np.maximum(disc, 0)), 0.0)
    M = Dw.shape[0]
    hit = np.zeros(M, bool)
    dmin = np.full(M, 1e9, np.float32)
    tmin = t.copy()
    act = np.nonzero(ok)[0]
    px_ang = 1.0 / cam.f
    for it in range(56):
        if len(act) == 0:
            break
        P = o[None, :] + t[act][:, None] * Do[act]
        dd = _sdf(P, legs)
        better = dd < dmin[act]
        dmin[act[better]] = dd[better]
        tmin[act[better]] = t[act][better]
        h_ = dd < (0.004 + px_ang * t[act] * 0.35)
        hit[act[h_]] = True
        t[act] = t[act] + np.maximum(dd * 0.85, 0.01)
        alive = (~h_) & (t[act] < t_end[act])
        act = act[alive]
    # cobertura: hit = 1; quase-acerto = fracao pela distancia minima (antialiasing)
    pxw = px_ang * np.maximum(tmin, 1.0) * 1.2
    cov = np.where(hit, 1.0, np.clip(1.0 - dmin / pxw, 0, 1)) * ok
    sel = np.nonzero(cov > 0.02)[0]
    if len(sel) == 0:
        return
    tt = np.where(hit[sel], t[sel], tmin[sel])
    P = o[None, :] + tt[:, None] * Do[sel]
    e = 0.02
    n = np.stack([_sdf(P + np.array([e, 0, 0], np.float32), legs) - _sdf(P - np.array([e, 0, 0], np.float32), legs),
                  _sdf(P + np.array([0, e, 0], np.float32), legs) - _sdf(P - np.array([0, e, 0], np.float32), legs),
                  _sdf(P + np.array([0, 0, e], np.float32), legs) - _sdf(P - np.array([0, 0, e], np.float32), legs)], 1)
    n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-9
    b, f_, en, lg = _parts(P, legs)
    x, y, zz = P[:, 0], P[:, 1], P[:, 2]
    th = np.arctan2(zz, x)
    # ---- material
    steel = np.array([0.60, 0.62, 0.66], np.float32)
    panel_id = np.floor(y / 1.85)
    alb = np.tile(steel, (len(sel), 1)) * (0.90 + 0.06 * np.sin(y * 41.0 + th * 3.0) + 0.08 * (_hash(panel_id, np.floor(th * 5.0)) - 0.5))[:, None]
    s_ = (y / 1.85) % 1.0
    seam = 1 - _smooth(0.0, 0.03, np.minimum(s_, 1 - s_))
    weld = 1 - _smooth(0.0, 0.05, np.abs(((th * 180 / math.pi) % 12.0) - 6.0) - 5.9 + 0.0)
    weld = np.where(np.abs(((th * 180 / math.pi) % 12.0)) < 0.5, 0.6, 0.0)
    alb *= (1 - 0.40 * seam - 0.18 * weld)[:, None]
    # escudo termico (placas pretas) do lado 'tile_dir', na metade inferior
    dang = np.abs((th - tile_dir + math.pi) % (2 * math.pi) - math.pi)
    tm = (1 - _smooth(1.15, 1.40, dang)) * (1 - _smooth(30.0, 38.0, y)) * (b <= np.minimum(f_, en))
    cu, cv = th * R_BODY / 0.42, y / 0.42
    gu, gv = np.floor(cu), np.floor(cv)
    tile = 0.028 + 0.05 * _hash(gu, gv)
    fu, fv = cu - gu, cv - gv
    gap = 1 - _smooth(0.0, 0.07, np.minimum(np.minimum(fu, 1 - fu), np.minimum(fv, 1 - fv)))
    tcol = (tile * (1 - 0.7 * gap))[:, None] * np.array([1.0, 1.0, 1.05], np.float32)
    alb = alb * (1 - tm[:, None]) + tcol * tm[:, None]
    # janelas
    win = (np.abs(((th * 180 / math.pi) % 36.0) - 18.0) < 3.0) & (np.abs(y - 43.6) < 0.45) & (b <= f_)
    alb = np.where(win[:, None], np.array([0.02, 0.025, 0.03], np.float32), alb)
    # motores / pernas / flaps escuros
    alb = np.where((en < b)[:, None] & (en < f_)[:, None], np.array([0.16, 0.16, 0.17], np.float32), alb)
    alb = np.where((f_ < b)[:, None] & (f_ < en)[:, None], np.array([0.36, 0.37, 0.39], np.float32) * (0.85 + 0.15 * _hash(np.floor(x * 3), np.floor(y * 3)))[:, None], alb)
    # ---- iluminacao
    nw = n @ R.astype(np.float32).T                        # normal no mundo
    Lw = np.array(env["sun_dir"], np.float32)
    nl = np.clip(nw @ Lw, 0, 1)[:, None]
    dview = -Dw[sel]
    ndv = np.clip((nw * dview).sum(1), 0, 1)
    refl = -dview - 2 * (nw * -dview).sum(1, keepdims=True) * nw
    metal = (1 - 0.8 * tm)[:, None]
    fres = (0.04 + 0.96 * (1 - ndv) ** 5)[:, None]
    ec = _env(refl, env)
    rough_spec = (0.25 + 0.55 * metal) * (0.30 + 0.7 * fres)
    sun_col = np.array(env["sun_col"], np.float32) * env["sun_int"]
    amb = _env(nw.astype(np.float32), {**env, "sun_int": 0.0}) * 0.55
    streak = (0.82 + 0.18 * np.sin(th * 53.0 + y * 0.7))[:, None]
    col = alb * (nl * sun_col * 0.85 * (1 - 0.45 * metal) + amb * 0.55) + ec * streak * (0.28 + 0.9 * fres) * (0.9 + 0.5 * metal) * (1 - 0.8 * tm[:, None]) * 1.25
    # luz da chama (laranja) nas partes baixas e voltadas p/ baixo
    if flame > 0:
        glow = flame * np.exp(-np.maximum(y, 0) / 9.0) * (0.45 + 0.55 * np.clip(-n[:, 1], 0, 1) + 0.25 * (1 - ndv))
        col = col + glow[:, None] * np.array([1.0, 0.55, 0.22], np.float32) * 1.3
    img = np.zeros((M, 3), np.float32)
    a = np.zeros(M, np.float32)
    img[sel] = col * gain
    a[sel] = cov[sel]
    if tdepth is not None:                                   # oclusao pelo terreno
        td = tdepth[y0:y1, x0:x1].reshape(-1)
        dc = np.linalg.norm(cen_w - cam.pos)
        a *= (td > dc * 0.9 - rad * 0.3)
    img = img.reshape(h, w, 3)
    a = a.reshape(h, w, 1)
    frame[y0:y1, x0:x1] = frame[y0:y1, x0:x1] * (1 - a) + img * a
