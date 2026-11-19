"""Modelos extras (poligonais, unidades = metros): bola de futebol, pessoa, planetas em escala, Se/cidade, aviao, carro, piramides,
Coliseu, caravela, dinossauros. Estilizados e honestos: sao SIMULACAO/RECONSTRUCAO, nao fotografias."""
import math
import numpy as np

W, G = (0.93, 0.93, 0.94), (0.5, 0.5, 0.52)


def _ball(col_fn, n_lat=14, n_lon=28):
    """esfera r=1 (lat/long) com cor por faceta."""
    polys = []
    for i in range(n_lat):
        a0, a1 = math.pi * i / n_lat - math.pi / 2, math.pi * (i + 1) / n_lat - math.pi / 2
        for j in range(n_lon):
            b0, b1 = 2 * math.pi * j / n_lon, 2 * math.pi * (j + 1) / n_lon
            P = [(math.cos(a) * math.cos(b), math.sin(a), math.cos(a) * math.sin(b)) for a, b in ((a0, b0), (a0, b1), (a1, b1), (a1, b0))]
            c = np.mean(P, 0)
            polys.append((np.array(P, np.float32), col_fn(c / (np.linalg.norm(c) + 1e-9))))
    return {"polys": polys}


def _football():
    t = (1 + 5 ** 0.5) / 2
    V = np.array([(0, 1, t), (0, -1, t), (0, 1, -t), (0, -1, -t), (1, t, 0), (-1, t, 0), (1, -t, 0), (-1, -t, 0), (t, 0, 1), (-t, 0, 1), (t, 0, -1), (-t, 0, -1)], float)
    V /= np.linalg.norm(V, axis=1, keepdims=True)
    return _ball(lambda c: (0.06, 0.06, 0.07) if (V @ c).max() > math.cos(0.34) else (0.95, 0.95, 0.96), 36, 72)


def _planet(base, band=None, ring=None):
    def f(c):
        if band:
            k = 0.5 + 0.5 * math.sin(c[1] * band)
            return tuple(np.array(base) * (0.75 + 0.35 * k))
        return base
    m = _ball(f, 10, 20)
    if ring:
        m["discs"] = [((0, 0, 0), (0.17, 1, 0.05), 2.3, ring), ((0, 0.001, 0), (0.17, 1, 0.05), 1.6, (0.1, 0.1, 0.1))]
    return m


def _earth():
    def f(c):
        n = math.sin(c[0] * 5.0 + 1) * math.sin(c[2] * 4.0) + 0.5 * math.sin(c[1] * 9.0 + c[0] * 3.0)
        return (0.25, 0.5, 0.25) if n > 0.45 else (0.12, 0.32, 0.8)
    return _ball(f, 12, 24)


def _human():
    sk, sh, pa = (0.78, 0.58, 0.46), (0.2, 0.4, 0.75), (0.15, 0.15, 0.2)
    return {"cyls": [((0.1, 0.42, 0), "y", 0.07, 0.06, 0.84, pa, 8), ((-0.1, 0.42, 0.05), "y", 0.07, 0.06, 0.84, pa, 8), ((0, 1.12, 0), "y", 0.2, 0.17, 0.62, sh, 10),
                     ((0.27, 1.15, 0), "y", 0.05, 0.05, 0.55, sh, 8), ((-0.27, 1.15, 0.05), "y", 0.05, 0.05, 0.55, sh, 8)],
            "spheres": [((0, 1.62, 0), 0.11, sk)]}


def _city(seed, R=900, far=3200):
    """quarteiroes ao redor da Praca da Se (vazio central 150x130 m) + Catedral + Palacio da Justica; densidade decai com a distancia."""
    rng = np.random.default_rng(seed)
    bx = []
    pitch = 95.0
    for gx in range(-int(far / pitch), int(far / pitch) + 1):
        for gz in range(-int(far / pitch), int(far / pitch) + 1):
            x, z = gx * pitch, gz * pitch
            d = math.hypot(x, z)
            if abs(x) < 110 and abs(z) < 100:
                continue
            if abs(x) < 210 and -50 < z < 190:                               # Palacio e Catedral
                continue
            if d > far:
                continue
            p = 0.92 if d < R else max(0.05, 0.9 * math.exp(-(d - R) / 900))
            if rng.random() > p:
                continue
            w, l = rng.uniform(22, 50), rng.uniform(22, 50)
            h = float(np.clip(rng.lognormal(3.2, 0.55), 9, 130) * (1.0 if d < R else 0.55))
            g = rng.uniform(0.55, 0.85)
            col = (g, g * rng.uniform(0.9, 1.0), g * rng.uniform(0.82, 0.98))
            bx.append(((x + rng.uniform(-6, 6), h / 2, z + rng.uniform(-6, 6)), (w, h, l), col))
    return bx


def _se():
    st, dome, pink, grn = (0.66, 0.63, 0.58), (0.35, 0.65, 0.58), (0.86, 0.62, 0.52), (0.18, 0.5, 0.2)
    bx = [((0, 15, 115), (46, 30, 111), st), ((0, 12, 115), (76, 24, 34), st),                # nave e transepto
          ((-15, 30, 62), (11, 60, 11), st), ((15, 30, 62), (11, 60, 11), st),                 # torres
          ((-140, 18, 20), (120, 36, 130), pink), ((-70, 5, 8), (0.1, 0.1, 0.1), pink)]        # Palacio da Justica
    cy = [((-15, 72, 62), "y", 5.5, 0.4, 28, (0.4, 0.55, 0.5), 10), ((15, 72, 62), "y", 5.5, 0.4, 28, (0.4, 0.55, 0.5), 10), ((0, 40, 120), "y", 13, 13, 18, st, 16)]
    sp = [((0, 49, 120), 15, dome, True)]
    for sx in (-1, 1):                                                                         # jardins da praca
        bx.append(((sx * 38, 0.15, -15), (30, 0.3, 40), grn))
    bx.append(((0, 6, -5), (3, 12, 3), (0.8, 0.8, 0.82)))                                       # Marco Zero (estilizado)
    return {"boxes": bx, "cyls": cy, "spheres": sp}


def _airliner():
    return {"cyls": [((0, 0, 0), "z", 2.9, 2.9, 62, W, 14), ((0, 0, 33), "z", 2.9, 0.6, 7, W, 14)], "boxes": [((0, -0.4, 4), (62, 0.7, 9), (0.85, 0.85, 0.88)), ((0, 5.5, -29), (1, 10, 8), (0.2, 0.3, 0.8)),
                                                                          ((0, 1.5, -29), (18, 0.5, 6), (0.85, 0.85, 0.88)), ((-14, -2.6, 6), (4, 3.2, 8), G), ((14, -2.6, 6), (4, 3.2, 8), G)]}


def _car():
    return {"boxes": [((0, 0.7, 0), (1.8, 0.7, 4.4), (0.8, 0.12, 0.1)), ((0, 1.3, -0.2), (1.6, 0.6, 2.2), (0.75, 0.82, 0.9))],
            "cyls": [((sx * 0.9, 0.32, sz * 1.4), "x", 0.32, 0.32, 0.25, (0.08, 0.08, 0.08), 10) for sx in (-1, 1) for sz in (-1, 1)]}


def _pyr(b, h, col):
    a = [(-b, 0, -b), (b, 0, -b), (b, 0, b), (-b, 0, b)]
    ap = (0, h, 0)
    return [(np.array([a[i], a[(i + 1) % 4], ap], np.float32), col) for i in range(4)]


def _pyramids():
    return {"polys": _pyr(115, 146, (0.86, 0.72, 0.45)) + [(p[0] + np.array([260, 0, 140], np.float32), p[1]) for p in _pyr(107, 136, (0.84, 0.7, 0.44))] +
            [(p[0] + np.array([480, 0, 280], np.float32), p[1]) for p in _pyr(52, 65, (0.84, 0.7, 0.44))], "boxes": [((0, -1, 0), (2400, 2, 2400), (0.86, 0.74, 0.5))]}


def _colosseum():
    bx = []
    for i in range(96):
        a = 2 * math.pi * i / 96
        x, z = 94 * math.cos(a), 78 * math.sin(a)
        for k in range(4):
            bx.append(((x, 6 + 12 * k, z), (11, 12, 3.2), (0.82 - 0.03 * k, 0.72 - 0.03 * k, 0.55)))
    return {"boxes": bx}


def _caravel():
    return {"boxes": [((0, 1.0, 0), (6, 2.2, 22), (0.4, 0.25, 0.13)), ((0, 4, -8), (5, 5, 5), (0.42, 0.27, 0.14)), ((0, 12, 3.2), (11, 11, 0.4), (0.93, 0.92, 0.85)),
                      ((0, 11, -5), (7, 8, 0.4), (0.93, 0.92, 0.85)), ((0, 12, 3.55), (2.2, 2.2, 0.1), (0.75, 0.1, 0.1))],
            "cyls": [((0, 10, 3), "y", 0.3, 0.25, 20, (0.35, 0.22, 0.12), 6), ((0, 9, -5), "y", 0.25, 0.2, 15, (0.35, 0.22, 0.12), 6)]}


def _dino(kind):
    sk, dk, bl = (0.50, 0.55, 0.34), (0.40, 0.44, 0.27), (0.62, 0.6, 0.45)
    sp, cy = [], []
    if kind == "sauro":
        for k in range(3):                                                    # corpo
            sp.append(((0, 6.6, -2.6 + 2.6 * k), 2.6 - 0.15 * abs(k - 1), sk))
        for k in range(14):                                                   # pescoco em curva suave
            t = k / 13.0
            sp.append(((0, 7.4 + 8.8 * t ** 0.9, 3.8 + 7.0 * t ** 1.2), 1.25 - 0.6 * t, sk if k % 2 else bl))
        sp.append(((0, 16.5, 11.2), 0.75, sk))                                # cabeca
        for k in range(16):                                                   # cauda longa afilando
            t = k / 15.0
            sp.append(((0, 6.2 - 2.2 * t, -5.0 - 12.0 * t), 1.9 * (1 - t) + 0.25, dk))
        cy = [((sx * 1.5, 3.0, sz * 3.0), "y", 0.8, 0.7, 6.0, dk, 10) for sx in (-1, 1) for sz in (-1, 1)]
        return {"spheres": sp, "cyls": cy}
    for k in range(3):
        sp.append(((0, 2.4, -1.0 + 1.1 * k), 0.8 - 0.1 * abs(k - 1), sk))
    for k in range(6):
        sp.append(((0, 3.0 + 0.35 * k, 1.9 + 0.35 * k), 0.38 - 0.03 * k, sk))
    sp.append(((0, 5.1, 4.2), 0.34, sk))
    for k in range(10):
        t = k / 9.0
        sp.append(((0, 2.3 - 0.9 * t, -2.0 - 4.2 * t), 0.55 * (1 - t) + 0.1, dk))
    cy = [((sx * 0.45, 1.2, 0.2), "y", 0.28, 0.16, 2.4, dk, 10) for sx in (-1, 1)]
    return {"spheres": sp, "cyls": cy}


def _road():
    """estrada em segmentos de 100 m (poligonos gigantes sao descartados quando a camera fica 'dentro' deles)."""
    bx = []
    for z in range(-6000, 6000, 100):
        bx.append(((0, 0.05, z + 50), (9, 0.1, 99.5), (0.14, 0.14, 0.16)))
        bx.append(((0, 0.12, z + 25), (0.3, 0.05, 6), (0.9, 0.85, 0.4)))
        bx.append(((0, 0.12, z + 75), (0.3, 0.05, 6), (0.9, 0.85, 0.4)))
        for sx in (-1, 1):
            bx.append(((sx * 4.9, 0.4, z + 50), (0.12, 0.8, 0.12), (0.9, 0.9, 0.9)))
    return {"boxes": bx}


def _sea():
    return {"boxes": [((x, 0.05, z), (399, 0.3, 399), (0.1, 0.28, 0.5)) for x in range(-3000, 3001, 400) for z in range(-3000, 3001, 400)]}


def build():
    M = {"football": _football(), "human": _human(), "se": _se(), "city_sp": {"boxes": _city(11)}, "airliner": _airliner(), "car": _car(), "pyramids": _pyramids(),
         "colosseum": _colosseum(), "road": _road(), "sea": _sea(), "caravel": _caravel(), "sauropod": _dino("sauro"), "theropod": _dino("thero"),
         "ball_sun": _planet((1.0, 0.8, 0.3)), "ball_earth": _earth(), "ball_jup": _planet((0.85, 0.7, 0.52), band=14), "ball_sat": _planet((0.9, 0.8, 0.58), band=10, ring=(0.8, 0.7, 0.52)),
         "ball_nep": _planet((0.25, 0.4, 0.9)), "ball_ura": _planet((0.5, 0.8, 0.85)), "ball_pluto": _planet((0.7, 0.62, 0.55)), "ball_merc": _planet((0.6, 0.58, 0.56)),
         "ball_ven": _planet((0.9, 0.75, 0.45)), "ball_mars": _planet((0.8, 0.38, 0.22))}
    return M
