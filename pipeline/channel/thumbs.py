"""Analise visual das miniaturas (heuristicas OpenCV; sem OCR): brilho, contraste, cores, saturacao, densidade de bordas, quantidade de elementos
(cores dominantes), area de texto provavel (regioes claras de alto contraste), presenca de rosto (Haar), legibilidade em tamanho de celular.
IMPORTANTE: a associacao com CTR so vale com impressoes suficientes (ver analyze.MIN_IMPR); com poucos dados e apenas descricao."""
import urllib.request
import numpy as np
import cv2


def load(src):
    if isinstance(src, (bytes, bytearray)):
        data = np.frombuffer(src, np.uint8)
        return cv2.imdecode(data, cv2.IMREAD_COLOR)
    if str(src).startswith("http"):
        with urllib.request.urlopen(urllib.request.Request(src, headers={"User-Agent": "video-universo/1.0"}), timeout=30) as r:
            return load(r.read())
    return cv2.imread(src, cv2.IMREAD_COLOR)


def features(src):
    im = load(src)
    if im is None:
        raise ValueError("imagem ilegivel")
    im = cv2.resize(im, (640, 360), interpolation=cv2.INTER_AREA)
    g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).astype(np.float32)
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV).astype(np.float32)
    b, gr, r = [im[..., i].astype(np.float32) for i in range(3)]
    rg, yb = r - gr, 0.5 * (r + gr) - b
    colorful = float(np.sqrt(rg.std() ** 2 + yb.std() ** 2) + 0.3 * np.sqrt(rg.mean() ** 2 + yb.mean() ** 2))     # Hasler-Susstrunk
    q = (im // 64).reshape(-1, 3)
    codes = q[:, 0] * 16 + q[:, 1] * 4 + q[:, 2]
    hist = np.bincount(codes, minlength=64) / len(codes)
    n_dom = int((np.cumsum(np.sort(hist)[::-1]) < 0.90).sum() + 1)
    edges = cv2.Canny(g.astype(np.uint8), 80, 160)
    bright = (g > 215).astype(np.uint8)                        # texto claro costuma ser a maior regiao brilhante compacta
    n, lab, stats, _ = cv2.connectedComponentsWithStats(bright)
    area = sum(int(s[4]) for s in stats[1:] if s[4] > 150 and s[3] > 25)
    faces = 0
    try:
        casc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        faces = int(len(casc.detectMultiScale(g.astype(np.uint8), 1.2, 5, minSize=(40, 40))))
    except Exception:
        pass
    small = cv2.resize(g, (168, 94), interpolation=cv2.INTER_AREA)
    return dict(brightness=round(float(g.mean()) / 255, 3), contrast=round(float(g.std()) / 255, 3), saturation=round(float(hsv[..., 1].mean()) / 255, 3),
                colorfulness=round(colorful, 1), dominant_colors=n_dom, edge_density=round(float((edges > 0).mean()), 4), text_like_area=round(area / g.size, 3),
                faces=faces, mobile_contrast=round(float(small.std()) / 255, 3))


def describe(f):
    out = []
    out.append("escura" if f["brightness"] < 0.25 else "clara" if f["brightness"] > 0.6 else "luminosidade media")
    out.append("alto contraste" if f["contrast"] > 0.28 else "baixo contraste")
    out.append("poucos elementos" if f["dominant_colors"] <= 8 else "muitos elementos/cores")
    out.append("texto grande provavel" if f["text_like_area"] > 0.08 else "pouco texto detectado")
    out.append("com rosto" if f["faces"] else "sem rosto")
    return ", ".join(out)
