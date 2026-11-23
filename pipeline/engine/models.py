"""Modelos poligonais simples (naves, habitat, rover, astronauta) para o renderizador do filme.
Unidades = metros. Cada modelo: boxes, cyls (frustos), spheres, discs. Eixo 'y' = para cima."""
import math
import numpy as np

_BOX_F = [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (2, 3, 7, 6), (0, 3, 7, 4), (1, 2, 6, 5)]

STEEL = (0.80, 0.82, 0.85)
DARK = (0.16, 0.16, 0.18)
WHITE = (0.92, 0.92, 0.94)
PANEL = (0.05, 0.10, 0.36)
GOLD = (0.9, 0.7, 0.2)


def _box(c, s):
    cx, cy, cz = c
    hx, hy, hz = s[0] / 2, s[1] / 2, s[2] / 2
    return np.array([[cx - hx, cy - hy, cz - hz], [cx + hx, cy - hy, cz - hz], [cx + hx, cy + hy, cz - hz], [cx - hx, cy + hy, cz - hz],
                     [cx - hx, cy - hy, cz + hz], [cx + hx, cy - hy, cz + hz], [cx + hx, cy + hy, cz + hz], [cx - hx, cy + hy, cz + hz]], np.float32)


def _ring(c, axis, r, off, seg):
    a = np.linspace(0, 2 * math.pi, seg, endpoint=False)
    cx, cy, cz = c
    if axis == "y":
        return np.stack([cx + r * np.cos(a), np.full(seg, cy + off), cz + r * np.sin(a)], 1)
    if axis == "x":
        return np.stack([np.full(seg, cx + off), cy + r * np.cos(a), cz + r * np.sin(a)], 1)
    return np.stack([cx + r * np.cos(a), cy + r * np.sin(a), np.full(seg, cz + off)], 1)


def _cyl_polys(c, axis, r0, r1, length, color, seg=40, caps=True):
    A = _ring(c, axis, r0, -length / 2, seg)
    B = _ring(c, axis, r1, length / 2, seg)
    out = []
    for k in range(seg):
        j = (k + 1) % seg
        out.append((np.array([A[k], A[j], B[j], B[k]], np.float32), color))
    if caps:
        if r0 > 0.02:
            out.append((A.astype(np.float32), color))
        if r1 > 0.02:
            out.append((B.astype(np.float32), color))
    return out


def _sphere_polys(c, r, color, half=False, lat=12, lon=32):
    out = []
    cx, cy, cz = c
    lat0 = 0 if half else -lat // 2 * 0 - lat
    la = np.linspace(0 if half else -math.pi / 2, math.pi / 2, (lat if half else 2 * lat) + 1)
    lo = np.linspace(0, 2 * math.pi, lon + 1)

    def P(i, j):
        return [cx + r * math.cos(la[i]) * math.cos(lo[j]), cy + r * math.sin(la[i]), cz + r * math.cos(la[i]) * math.sin(lo[j])]

    for i in range(len(la) - 1):
        for j in range(lon):
            out.append((np.array([P(i, j), P(i, j + 1), P(i + 1, j + 1), P(i + 1, j)], np.float32), color))
    return out


def polys_from(m):
    """-> lista de (verts(n,3), color, closed_box_flag)."""
    out = []
    for c, s, col in m.get("boxes", []):
        V = _box(c, s)
        for f in _BOX_F:
            out.append((V[list(f)], col))
    for c, axis, r0, r1, ln, col, *rest in m.get("cyls", []):
        out += _cyl_polys(c, axis, r0, r1, ln, col, max(rest[0] * 2 if rest else 16, 36))
    for c, r, col, *rest in m.get("spheres", []):
        out += _sphere_polys(c, r, col, half=bool(rest and rest[0]))
    for V, col in m.get("polys", []):
        out.append((np.asarray(V, np.float32), col))
    for c, nrm, rad, col in m.get("discs", []):
        n = np.array(nrm, np.float32)
        n /= np.linalg.norm(n)
        a = np.cross(n, [0, 1, 0] if abs(n[1]) < 0.9 else [1, 0, 0])
        a /= np.linalg.norm(a)
        b = np.cross(n, a)
        ang = np.linspace(0, 2 * math.pi, 22, endpoint=False)
        out.append((np.array(c, np.float32) + rad * (np.cos(ang)[:, None] * a + np.sin(ang)[:, None] * b), col))
    return out


def _starship():
    cy = []
    cy.append(((0, 18, 0), "y", 4.5, 4.5, 36, STEEL, 20))
    cy.append(((0, 3, 0), "y", 4.52, 4.52, 6, (0.28, 0.28, 0.30), 20))               # saia escura (escudo termico)
    cy.append(((0, 39, 0), "y", 4.5, 3.4, 6, STEEL, 20))
    cy.append(((0, 44.5, 0), "y", 3.4, 1.9, 5, STEEL, 20))
    cy.append(((0, 48.5, 0), "y", 1.9, 0.3, 3, STEEL, 20))
    for ang in (0, 120, 240):                                                      # motores
        a = math.radians(ang)
        cy.append(((2.0 * math.cos(a), -0.7, 2.0 * math.sin(a)), "y", 1.1, 0.55, 1.6, DARK, 10))
    cy.append(((0, -0.7, 0), "y", 1.3, 0.7, 1.6, DARK, 10))
    boxes = [((6.3, 41, 0), (3.6, 6.2, 0.5), (0.55, 0.57, 0.6)), ((-6.3, 41, 0), (3.6, 6.2, 0.5), (0.55, 0.57, 0.6)),
             ((6.8, 4.5, 0), (4.2, 8.4, 0.5), (0.22, 0.22, 0.24)), ((-6.8, 4.5, 0), (4.2, 8.4, 0.5), (0.22, 0.22, 0.24))]
    return dict(cyls=cy, boxes=boxes)


def _starship_legs():
    m = _starship()
    m["boxes"] = m["boxes"] + [((5.6, -1.2, 0), (0.5, 4.6, 0.5), DARK), ((-5.6, -1.2, 0), (0.5, 4.6, 0.5), DARK),
                               ((0, -1.2, 5.6), (0.5, 4.6, 0.5), DARK), ((0, -1.2, -5.6), (0.5, 4.6, 0.5), DARK)]
    return m


def _base():
    cy = [((0, 0, 0), "y", 6.0, 6.0, 0.4, (0.7, 0.7, 0.72), 18),
          ((15, 0.2, 3), "y", 5.0, 5.0, 0.4, (0.7, 0.7, 0.72), 18),
          ((7.5, 2.0, 1.5), "x", 1.4, 1.4, 10, (0.85, 0.85, 0.88), 12),
          ((-12, 2.2, -4), "x", 1.5, 1.5, 9, (0.85, 0.85, 0.88), 12),
          ((0, 0.4, -13), "y", 2.2, 2.2, 5.0, (0.8, 0.8, 0.84), 14),             # tanque / MOXIE
          ((-6, 5.5, -4), "y", 0.12, 0.12, 11, (0.8, 0.8, 0.8), 6)]               # mastro
    sp = [((0, 0.2, 0), 6.0, (0.9, 0.9, 0.93), True), ((15, 0.2, 3), 5.0, (0.9, 0.9, 0.93), True)]
    boxes = []
    for i in range(4):
        for j in range(3):
            boxes.append(((-30 + i * 7.5, 1.6, 14 + j * 5.2), (6.6, 0.2, 4.4), PANEL))     # campo solar inclinado simplificado
    return dict(cyls=cy, spheres=sp, boxes=boxes, discs=[((-6, 11, -4), (0.2, 1, 0.5), 1.2, (0.9, 0.9, 0.9))])


def _rover():
    cy = []
    for z in (-1.1, 0.0, 1.1):
        for x in (-1.5, 1.5):
            cy.append(((x, 0.5, z), "x", 0.5, 0.5, 0.45, (0.12, 0.12, 0.13), 10))
    cy.append(((0.9, 2.0, 0.9), "y", 0.07, 0.07, 1.8, (0.7, 0.7, 0.72), 6))
    return dict(cyls=cy, boxes=[((0, 1.05, 0), (2.7, 0.8, 3.0), (0.78, 0.78, 0.8)), ((0, 1.65, -0.9), (0.9, 0.5, 0.9), (0.4, 0.4, 0.42))],
                discs=[((0.9, 2.9, 0.9), (0, 0.6, 1), 0.45, (0.9, 0.9, 0.92))])


def _astronaut():
    return dict(boxes=[((0, 1.15, 0), (0.50, 0.70, 0.30), WHITE), ((0, 1.2, -0.28), (0.46, 0.62, 0.26), (0.8, 0.8, 0.82)),
                       ((-0.14, 0.42, 0), (0.2, 0.84, 0.24), WHITE), ((0.14, 0.42, 0), (0.2, 0.84, 0.24), WHITE),
                       ((-0.34, 1.1, 0), (0.14, 0.62, 0.18), WHITE), ((0.34, 1.1, 0), (0.14, 0.62, 0.18), WHITE),
                       ((-0.14, 0.05, 0.05), (0.22, 0.12, 0.34), (0.3, 0.3, 0.32)), ((0.14, 0.05, 0.05), (0.22, 0.12, 0.34), (0.3, 0.3, 0.32))],
                spheres=[((0, 1.78, 0), 0.25, WHITE), ((0, 1.78, 0.1), 0.19, GOLD)])


def _mav():
    return dict(cyls=[((0, 6, 0), "y", 1.5, 1.5, 12, (0.9, 0.9, 0.92), 14), ((0, 13.5, 0), "y", 1.5, 0.3, 3, (0.92, 0.5, 0.2), 14),
                      ((0, -0.4, 0), "y", 0.9, 0.5, 1.0, DARK, 8)],
                boxes=[((1.9, -0.6, 0), (0.3, 3.6, 0.3), DARK), ((-1.9, -0.6, 0), (0.3, 3.6, 0.3), DARK)])


def _probe():
    return dict(boxes=[((0, 0, 0), (1, 1, 1.4), (0.8, 0.75, 0.55)), ((-1.6, 0, 0), (2.0, 0.03, 1.0), PANEL), ((1.6, 0, 0), (2.0, 0.03, 1.0), PANEL)])


def _voyager_hq():
    """Voyager 1: antena parabolica de 3,7 m (frustos empilhados), barramento dourado decagonal, RTGs, bracos, plataforma de cameras, boom do magnetometro, antenas de plasma, disco de ouro. Eixo da antena = +z."""
    GOLDF, WH, GR, DK = (0.80, 0.62, 0.28), (0.90, 0.90, 0.92), (0.62, 0.62, 0.66), (0.22, 0.22, 0.25)
    cy = [((0, 0, 0.62), "z", 0.22, 0.95, 0.20, WH, 20), ((0, 0, 0.80), "z", 0.95, 1.50, 0.16, (0.86, 0.86, 0.89), 20),
          ((0, 0, 0.94), "z", 1.50, 1.85, 0.12, (0.82, 0.82, 0.86), 20),
          ((0, 0, 0.1), "z", 0.72, 0.72, 0.62, GOLDF, 10), ((0, 0, -0.30), "z", 0.55, 0.55, 0.2, (0.45, 0.45, 0.5), 10),
          ((1.55, -0.12, -0.2), "x", 0.17, 0.17, 0.85, DK, 12), ((2.4, -0.12, -0.2), "x", 0.17, 0.17, 0.85, DK, 12), ((3.25, -0.12, -0.2), "x", 0.17, 0.17, 0.85, DK, 12),
          ((-2.75, 0.05, 0.02), "z", 0.13, 0.13, 0.45, DK, 10), ((-2.55, 0.05, 0.02), "z", 0.09, 0.09, 0.5, (0.3, 0.3, 0.34), 10)]
    bx = [((1.1, -0.12, -0.2), (2.2, 0.07, 0.07), GR), ((-1.35, 0.05, -0.3), (2.7, 0.07, 0.07), GR),
          ((-2.7, 0.05, -0.3), (0.6, 0.6, 0.55), (0.55, 0.55, 0.6)),
          ((0, 0.1, -3.9), (0.07, 0.07, 7.2), GR), ((0, 0.1, -3.9), (0.28, 0.02, 7.2), (0.5, 0.5, 0.55)),
          ((2.1, 0.5, -1.0), (4.4, 0.035, 0.035), (0.7, 0.7, 0.75)), ((-2.1, 0.5, -1.2), (4.4, 0.035, 0.035), (0.7, 0.7, 0.75)),
          ((0, 0.42, -0.1), (0.62, 0.05, 0.62), (0.2, 0.2, 0.22)), ((0, 0.22, 0.1), (0.9, 0.12, 0.9), (0.55, 0.5, 0.3))]
    ds = [((0, 0, 1.03), (0, 0, 1), 1.84, (0.60, 0.60, 0.64)), ((0, 0, 0.72), (0, 0, 1), 0.3, (0.3, 0.3, 0.34)), ((0, 0.46, -0.1), (0, 1, 0), 0.33, (0.95, 0.78, 0.25)),
          ((0, 0.47, -0.1), (0, 1, 0), 0.12, (0.5, 0.4, 0.1))]
    return {"cyls": cy, "boxes": bx, "discs": ds}


def _titan3e():
    """Titan IIIE-Centaur (lancou as Voyagers): nucleo, dois SRBs, Centaur e carenagem. Eixo = +y."""
    W, S, D = (0.93, 0.93, 0.95), (0.74, 0.76, 0.8), (0.2, 0.2, 0.22)
    cy = [((0, 17, 0), "y", 1.5, 1.5, 34, W, 20), ((3.0, 15, 0), "y", 1.55, 1.55, 30, W, 20), ((-3.0, 15, 0), "y", 1.55, 1.55, 30, W, 20),
          ((0, 38, 0), "y", 1.5, 1.5, 9, S, 20), ((0, 46, 0), "y", 1.5, 0.5, 8, W, 20), ((0, 0.4, 0), "y", 1.2, 1.2, 1.2, D, 14),
          ((3.0, 0.4, 0), "y", 1.2, 1.2, 1.2, D, 14), ((-3.0, 0.4, 0), "y", 1.2, 1.2, 1.2, D, 14), ((0, 34.4, 0), "y", 1.5, 1.5, 0.6, D, 20)]
    sp = [((3.0, 30.8, 0), 1.55, W, True), ((-3.0, 30.8, 0), 1.55, W, True), ((0, 50.2, 0), 0.5, W, True)]
    return {"cyls": cy, "spheres": sp, "boxes": [((0, 1, 0), (7.2, 0.5, 0.5), D)]}


def _memchip():
    """Placa de memoria: PCB escura, banco de chips e um chip defeituoso (vermelho). Eixo = +z para a camera."""
    bx = [((0, 0, 0), (9.0, 6.0, 0.25), (0.06, 0.12, 0.08))]
    for i in range(4):
        for j in range(3):
            bad = (i == 2 and j == 1)
            bx.append(((-3.1 + i * 2.1, -1.8 + j * 1.8, 0.28), (1.5, 1.1, 0.3), (0.85, 0.12, 0.1) if bad else (0.10, 0.10, 0.12)))
            bx.append(((-3.1 + i * 2.1, -1.8 + j * 1.8, 0.46), (1.1, 0.7, 0.06), (1.0, 0.45, 0.3) if bad else (0.22, 0.22, 0.26)))
    for k in range(18):
        bx.append(((-4.2 + k * 0.5, 2.7, 0.18), (0.35, 0.04, 0.06), (0.8, 0.65, 0.25)))
    return {"boxes": bx}


def _frag(col):
    return {"boxes": [((0, 0, 0), (1.3, 0.9, 0.5), col), ((0, 0, 0.27), (0.9, 0.5, 0.06), (1.0, 0.9, 0.6))]}


def _cassini_hq():
    """Cassini orbiter (+ Huygens): antena de 4 m (frustos brancos), corpo com manta dourada, Huygens na lateral, boom do magnetometro, antenas RPWS, 3 RTGs, pacote de instrumentos. Eixo da antena = +z. Ilustracao/simulacao (nao e foto)."""
    WH, GOLD, GR, DK = (0.92, 0.92, 0.94), (0.66, 0.52, 0.28), (0.62, 0.62, 0.66), (0.20, 0.20, 0.23)
    cy = [((0, 0, 3.0), "z", 0.35, 1.2, 0.5, WH, 24), ((0, 0, 3.4), "z", 1.2, 2.0, 0.35, (0.88, 0.88, 0.9), 24),
          ((0, 0, 0.6), "z", 1.15, 1.15, 3.4, GOLD, 16), ((0, 0, -1.6), "z", 1.0, 1.0, 1.0, (0.55, 0.45, 0.25), 16),
          ((2.05, 0, 0.4), "z", 0.9, 0.9, 1.6, (0.55, 0.5, 0.42), 20), ((-0.5, -1.15, -1.2), "z", 0.28, 0.28, 1.5, DK, 10),
          ((0.5, -1.15, -1.2), "z", 0.28, 0.28, 1.5, DK, 10), ((0.0, -1.35, -1.2), "z", 0.28, 0.28, 1.5, DK, 10)]
    bx = [((-5.0, 0.4, 0.0), (9.6, 0.1, 0.1), GR), ((0.0, 1.35, -0.9), (4.2, 0.06, 0.06), (0.75, 0.75, 0.8)), ((0.0, 1.35, -0.9), (0.06, 0.06, 4.0), (0.75, 0.75, 0.8)),
          ((-1.1, 0.55, -0.2), (0.9, 0.5, 0.9), GR), ((1.5, -0.5, -1.0), (0.6, 0.6, 0.8), GR)]
    ds = [((0, 0, 3.58), (0, 0, 1), 1.98, (0.62, 0.62, 0.66)), ((0, 0, 2.8), (0, 0, 1), 0.34, (0.3, 0.3, 0.34))]
    return {"cyls": cy, "boxes": bx, "discs": ds}


MODELS = {"starship": _starship(), "starship_legs": _starship_legs(), "base": _base(), "rover": _rover(), "astronaut": _astronaut(), "mav": _mav(), "probe": _probe(), "voyager_hq": _voyager_hq(), "cassini_hq": _cassini_hq(), "titan3e": _titan3e(), "memchip": _memchip(),
          "frag_a": _frag((0.95, 0.65, 0.15)), "frag_b": _frag((0.2, 0.7, 0.95)), "frag_c": _frag((0.5, 0.9, 0.4))}
try:
    from .models_ext import build as _build_ext
    MODELS.update(_build_ext())
except Exception as _e:                                 # modelos extras sao opcionais
    print('[models] extras indisponiveis:', _e)
_CACHE = {}


def model_polys(name):
    if name not in _CACHE:
        _CACHE[name] = polys_from(MODELS[name])
    return _CACHE[name]
