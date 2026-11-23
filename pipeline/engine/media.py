"""Camada de FOTOS e VIDEOS reais (ex.: acervo da NASA) sobre o filme, com zoom/pan estilo documentario (Ken Burns), fade e credito.
Cada item (resolvido pelo build_film a partir de scenes.py -> media=[...]):
  path, kind ('image'|'video'), start, end, fade (s), zoom [z0, z1] (>=1), pan [[x0, y0], [x1, y1]] (-1..1 da folga), fit ('cover'|'contain'|'auto'),
  mode ('full' | 'inset'), rect [cx, cy, w] (inset, fracoes da tela), opacity, vstart/speed/loop (video), credit (texto), grade {contrast, sat, dim}.
Aplicada no quadro final (depois da cena 3D, antes do HUD/legendas) -> atravessa as dissolvencias entre cenas."""
import math
import os
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont

FD = "/usr/share/fonts/opentype/inter/"


def _ease(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


class MediaLayer:
    def __init__(self, items, W, H):
        self.items, self.W, self.H = sorted(items or [], key=lambda m: m["start"]), W, H
        # DISSOLUCAO REAL: se outro plano comeca logo apos o fim deste (< 1,2 s), este fica opaco ate o seguinte terminar de aparecer
        # (sem 'mergulho' ao preto entre planos consecutivos). Plano final de uma sequencia continua com fade-out normal.
        for i, a in enumerate(self.items):
            a.pop("_end2", None); a.pop("_nofo", None)
            if a.get("mode", "full") != "full":
                continue
            for b in self.items[i + 1:]:
                if b.get("mode", "full") != "full" or b["start"] < a["start"] + 0.5:
                    continue
                if 0 <= b["start"] - a["end"] < 1.2 or (b["start"] < a["end"] and b["start"] >= a["start"] + 0.5):
                    a["_end2"] = max(a["end"], b["start"] + b.get("fade", 0.8))
                    a["_nofo"] = True
                break
        self._img, self._cap, self._last, self._txt = {}, {}, {}, {}

    # ------------------------------------------------------------ fontes
    def _image(self, p):
        if p not in self._img:
            im = cv2.imread(p, cv2.IMREAD_COLOR)
            if im is None:
                im = np.array(Image.open(p).convert("RGB"))[..., ::-1]
            s = max(im.shape[:2])
            if s > 4096:
                im = cv2.resize(im, None, fx=4096.0 / s, fy=4096.0 / s, interpolation=cv2.INTER_AREA)
            self._img[p] = im[..., ::-1].copy()
        return self._img[p]

    def _video(self, it, t):
        p = it["path"]
        if p not in self._cap:
            c = cv2.VideoCapture(p)
            self._cap[p] = dict(c=c, fps=c.get(cv2.CAP_PROP_FPS) or 24.0, n=c.get(cv2.CAP_PROP_FRAME_COUNT) or 1, pos=-1)
        v = self._cap[p]
        dur = v["n"] / v["fps"]
        tv = it.get("vstart", 0.0) + (t - it["start"]) * it.get("speed", 1.0)
        tv = (tv % dur) if it.get("loop", False) else min(max(tv, 0.0), dur - 1.0 / v["fps"])
        fi = int(tv * v["fps"])
        if fi != v["pos"]:
            if not (0 <= fi - v["pos"] <= 3):
                v["c"].set(cv2.CAP_PROP_POS_FRAMES, fi)
                v["pos"] = fi - 1
            ok, fr = False, None
            while v["pos"] < fi:
                ok, fr = v["c"].read()
                v["pos"] += 1
                if not ok:
                    break
            if ok:
                self._last[p] = fr[..., ::-1].copy()
        return self._last.get(p)

    # ------------------------------------------------------------ composicao
    def _credit(self, text, alpha_scale=1.0):
        key = (text, self.W)
        if key not in self._txt:
            H = self.H
            f = ImageFont.truetype(FD + "Inter-Medium.otf", max(int(H * 0.017), 11))
            lay = Image.new("L", (self.W, H), 0)
            d = ImageDraw.Draw(lay)
            tx = "Credit: " + text
            w = d.textlength(tx, font=f)
            d.text((self.W - w - self.W * 0.018 + 1, H * 0.965 + 1), tx, font=f, fill=120)
            d.text((self.W - w - self.W * 0.018, H * 0.965), tx, font=f, fill=235)
            self._txt[key] = np.asarray(lay, np.float32)[..., None] / 255.0
        return self._txt[key]

    def _render_pic(self, src, it, u, W, H):
        """src RGB uint8 -> imagem (H, W, 3) float32 0..255 com zoom/pan; fit cover|contain."""
        h0, w0 = src.shape[:2]
        z0, z1 = it.get("zoom", [1.0, 1.0])
        z = z0 + (z1 - z0) * _ease(u) if it.get("ease", True) else z0 + (z1 - z0) * u
        (px0, py0), (px1, py1) = it.get("pan", [[0, 0], [0, 0]])
        px, py = px0 + (px1 - px0) * u, py0 + (py1 - py0) * u
        fit = it.get("fit", "auto")
        ar_s, ar_d = w0 / h0, W / H
        if fit == "auto":
            fit = "contain" if abs(math.log(ar_s / ar_d)) > math.log(1.35) else "cover"
        if fit == "cover":
            cw, ch = (h0 * ar_d, h0) if ar_s > ar_d else (w0, w0 / ar_d)
            cw, ch = cw / z, ch / z
            cx = w0 / 2 + px * max(w0 - cw, 0) / 2
            cy = h0 / 2 + py * max(h0 - ch, 0) / 2
            x0, y0 = int(max(min(cx - cw / 2, w0 - cw), 0)), int(max(min(cy - ch / 2, h0 - ch), 0))
            crop = src[y0:y0 + max(int(ch), 2), x0:x0 + max(int(cw), 2)]
            return cv2.resize(crop, (W, H), interpolation=cv2.INTER_AREA if crop.shape[1] > W else cv2.INTER_CUBIC).astype(np.float32)
        # contain: fundo desfocado + imagem inteira (com zoom em torno do centro)
        bg_h = max(int(H * 0.12), 8)
        bg = cv2.resize(src, (max(int(bg_h * ar_s), 8), bg_h), interpolation=cv2.INTER_AREA)
        bg = cv2.resize(cv2.GaussianBlur(bg, (0, 0), 3), (W, H), interpolation=cv2.INTER_CUBIC).astype(np.float32) * 0.35
        s = min(W / w0, H / h0) * z
        tw, th = max(int(w0 * s), 2), max(int(h0 * s), 2)
        big = cv2.resize(src, (tw, th), interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_CUBIC)
        ox, oy = int((W - tw) / 2 - px * max(tw - W, 0) / 2), int((H - th) / 2 - py * max(th - H, 0) / 2)
        out = bg.copy()
        xa, ya, xb, yb = max(ox, 0), max(oy, 0), min(ox + tw, W), min(oy + th, H)
        if xb > xa and yb > ya:
            out[ya:yb, xa:xb] = big[ya - oy:yb - oy, xa - ox:xb - ox]
        return out

    def apply(self, img, t):
        if not self.items:
            return img
        out = None
        for it in self.items:
            end_eff = it.get("_end2", it["end"])
            if not (it["start"] <= t <= end_eff):
                continue
            fd = max(min(it.get("fade", 0.8), (it["end"] - it["start"]) / 2.2), 1e-3)
            a_out = 1.0 if it.get("_nofo") else _ease((it["end"] - t) / fd)
            a = min(_ease((t - it["start"]) / fd), a_out) * it.get("opacity", 1.0)
            if a <= 0.002:
                continue
            src = self._video(it, t) if it["kind"] == "video" else self._image(it["path"])
            if src is None:
                continue
            u = (t - it["start"]) / max(it["end"] - it["start"], 1e-3)
            if out is None:
                out = img.astype(np.float32)
            g = it.get("grade", {})
            if it.get("mode", "full") == "full":
                pic = self._render_pic(src, it, u, self.W, self.H)
                if g:
                    pic = (pic - 127.5) * g.get("contrast", 1.0) + 127.5
                    if g.get("sat", 1.0) != 1.0:
                        gr = pic.mean(2, keepdims=True)
                        pic = gr + (pic - gr) * g["sat"]
                    pic = pic * g.get("dim", 1.0)
                vg = it.get("vignette", 0.28)
                if vg:
                    yy, xx = np.mgrid[0:self.H, 0:self.W].astype(np.float32)
                    r = np.hypot((xx / self.W - 0.5) * 1.6, (yy / self.H - 0.5) * 1.1)
                    pic = pic * (1 - vg * np.clip(r - 0.35, 0, 1)[..., None] * 1.4)
                out = out * (1 - a) + np.clip(pic, 0, 255) * a
            else:                                                     # inset: foto/video em moldura sobre a cena 3D
                cx, cy, wf = it.get("rect", [0.74, 0.40, 0.36])
                tw = int(self.W * wf)
                ar = src.shape[1] / src.shape[0]
                th = int(tw / ar)
                tmp = self._render_pic(src, {**it, "fit": "cover"}, u, tw, th)
                x0, y0 = int(self.W * cx - tw / 2), int(self.H * cy - th / 2)
                x1, y1 = min(x0 + tw, self.W), min(y0 + th, self.H)
                x0c, y0c = max(x0, 0), max(y0, 0)
                if x1 > x0c and y1 > y0c:
                    b = 3
                    out[max(y0c - b, 0):y1 + b, max(x0c - b, 0):x1 + b] *= (1 - 0.85 * a)
                    out[max(y0c - b, 0):y1 + b, max(x0c - b, 0):x1 + b] += 235 * 0.85 * a
                    out[y0c:y1, x0c:x1] = out[y0c:y1, x0c:x1] * (1 - a) + tmp[y0c - y0:y1 - y0, x0c - x0:x1 - x0] * a
            if it.get("credit"):
                m = self._credit(it["credit"])
                out = out * (1 - m * 0.9 * a) + 235 * m * 0.9 * a if a > 0.01 else out
        return img if out is None else np.clip(out + 0.5, 0, 255).astype(np.uint8)
