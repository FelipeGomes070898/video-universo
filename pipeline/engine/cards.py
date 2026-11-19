"""Elementos didaticos sobre o video: quadros, linha do tempo, graficos, quiz, documento (destaque/zoom), mapa animado,
comparacao e selo de autenticidade. Cada item: {"kind", "start", "end", ...}. Animacao por progresso p (0..1).

Todos aparecem so quando pedidos pelo roteiro (scenes.py -> "cards") — o motor nao enche o video de elementos.
"""
import math
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

FD = "/usr/share/fonts/opentype/inter/"
ACC = (255, 214, 120)
INK = (255, 255, 255)
SUB = (190, 205, 235)
PANEL = (8, 12, 24, 205)
BADGES = {"real": None, "simulation": "SIMULATION", "reconstruction": "RECONSTRUCTION", "illustration": "ILLUSTRATION", "ai": "AI-GENERATED IMAGE"}


def _f(name, px):
    try:
        return ImageFont.truetype(FD + name, int(px))
    except Exception:
        return ImageFont.load_default(int(px))


def _ease(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def _wrap(d, text, font, maxw):
    out, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if d.textlength(t, font=font) <= maxw:
            cur = t
        else:
            out.append(cur)
            cur = w
    return out + ([cur] if cur else [])


class Cards:
    def __init__(self, items, W, H):
        self.items, self.W, self.H, self.u = items or [], W, H, H / 720.0
        self.fT, self.fB, self.fS = _f("Inter-Bold.otf", 26 * self.u), _f("Inter-Medium.otf", 21 * self.u), _f("Inter-SemiBold.otf", 13 * self.u)
        self.imgs = {}

    # ------------------------------------------------------------ helpers
    def _panel(self, d, box, title=None):
        d.rounded_rectangle(box, radius=int(14 * self.u), fill=PANEL)
        d.rectangle([box[0], box[1] + int(14 * self.u), box[0] + int(4 * self.u), box[3] - int(14 * self.u)], fill=ACC)
        if title:
            d.text((box[0] + 22 * self.u, box[1] + 16 * self.u), title.upper(), font=self.fS, fill=ACC)

    def _img(self, path):
        if path not in self.imgs:
            self.imgs[path] = Image.open(path).convert("RGB")
        return self.imgs[path]

    # ------------------------------------------------------------ kinds
    def _card(self, d, it, p):
        W, H, u = self.W, self.H, self.u
        w = int(W * 0.36)
        x0 = int(W * (0.06 if it.get("side", "left") == "left" else 0.58))
        lines = []
        tmp = ImageDraw.Draw(Image.new("RGB", (4, 4)))
        for b in it.get("bullets", []):
            lines.append(_wrap(tmp, b, self.fB, w - 70 * u))
        h = int(80 * u + sum(len(l) * 28 * u + 10 * u for l in lines))
        y0 = int(H * 0.30)
        self._panel(d, [x0, y0, x0 + w, y0 + h], it.get("title"))
        y = y0 + 52 * u
        n = len(lines)
        for i, l in enumerate(lines):
            a = _ease(p * (n + 1) - i)
            col = tuple(int(c * a) for c in INK) + (int(255 * a),)
            for ln in l:
                d.text((x0 + 26 * u, y), ("• " if ln is l[0] else "   ") + ln, font=self.fB, fill=col)
                y += 28 * u
            y += 10 * u

    def _timeline(self, d, it, p):
        W, H, u = self.W, self.H, self.u
        ev = it["events"]
        x0, x1, y = int(W * 0.13), int(W * 0.90), int(H * 0.72)
        box = [x0 - 24 * u, y - 70 * u, x1 + 24 * u, y + 90 * u]
        self._panel(d, box, it.get("title", "Timeline"))
        d.line([(x0, y), (x1, y)], fill=(120, 140, 190, 200), width=max(2, int(3 * u)))
        prog = _ease(p * 1.15)
        d.line([(x0, y), (x0 + (x1 - x0) * prog, y)], fill=ACC, width=max(2, int(4 * u)))
        for i, e in enumerate(ev):
            fx = i / max(len(ev) - 1, 1)
            on = prog >= fx - 1e-6
            x = x0 + (x1 - x0) * fx
            r = (9 if e.get("key") else 6) * u
            d.ellipse([x - r, y - r, x + r, y + r], fill=ACC if on else (90, 100, 130, 255))
            if on:
                tw = d.textlength(str(e["t"]), font=self.fS)
                d.text((x - tw / 2, y - 34 * u), str(e["t"]), font=self.fS, fill=ACC)
                lab = _wrap(d, e["text"], self.fS, (x1 - x0) / len(ev) * 1.05)
                for j, ln in enumerate(lab[:3]):
                    tw = d.textlength(ln, font=self.fS)
                    d.text((x - tw / 2, y + 16 * u + j * 17 * u), ln, font=self.fS, fill=INK)

    def _chart(self, d, it, p):
        W, H, u = self.W, self.H, self.u
        box = [int(W * 0.12), int(H * 0.2), int(W * 0.88), int(H * 0.82)]
        self._panel(d, box, it.get("title"))
        data = it["data"]
        mx = max(v for _, v in data) * 1.1
        gx0, gx1, gy0, gy1 = box[0] + 60 * u, box[2] - 40 * u, box[3] - 50 * u, box[1] + 70 * u
        d.line([(gx0, gy0), (gx1, gy0)], fill=(120, 140, 190, 220), width=2)
        k = _ease(p * 1.2)
        if it.get("type", "bar") == "bar":
            bw = (gx1 - gx0) / len(data)
            for i, (lab, v) in enumerate(data):
                h = (gy0 - gy1) * v / mx * k
                x = gx0 + i * bw + bw * 0.18
                d.rectangle([x, gy0 - h, x + bw * 0.64, gy0], fill=ACC if i == it.get("highlight", -1) else (120, 170, 255, 235))
                d.text((x, gy0 + 8 * u), lab, font=self.fS, fill=SUB)
                if k > 0.6:
                    d.text((x, gy0 - h - 20 * u), f"{v:,}{it.get('unit', '')}", font=self.fS, fill=INK)
        else:
            pts = [(gx0 + (gx1 - gx0) * i / max(len(data) - 1, 1), gy0 - (gy0 - gy1) * v / mx) for i, (_, v) in enumerate(data)]
            m = max(2, int(1 + (len(pts) - 1) * k) + 1)
            d.line(pts[:m], fill=ACC, width=max(3, int(4 * u)))
            for (lab, v), (x, y) in zip(data[:m], pts[:m]):
                d.ellipse([x - 5 * u, y - 5 * u, x + 5 * u, y + 5 * u], fill=INK)
                d.text((x - 14 * u, gy0 + 8 * u), lab, font=self.fS, fill=SUB)

    def _quiz(self, d, it, p):
        W, H, u = self.W, self.H, self.u
        box = [int(W * 0.14), int(H * 0.2), int(W * 0.86), int(H * 0.8)]
        reveal = p >= it.get("reveal_at", 0.7)
        self._panel(d, box, "PAUSE THE VIDEO" if not reveal else "ANSWER")
        tmp = d
        y = box[1] + 60 * u
        for ln in _wrap(d, it["question"], self.fT, box[2] - box[0] - 80 * u):
            d.text((box[0] + 30 * u, y), ln, font=self.fT, fill=INK)
            y += 34 * u
        y += 14 * u
        for i, o in enumerate(it["options"]):
            ok = reveal and i == it["answer"]
            col = ACC if ok else (INK if not reveal else (110, 120, 150, 255))
            d.text((box[0] + 40 * u, y), f"{'ABCD'[i]}.  {o}", font=self.fB, fill=col)
            y += 34 * u
        if reveal and it.get("explain"):
            y += 8 * u
            for ln in _wrap(d, it["explain"], self.fS, box[2] - box[0] - 80 * u):
                d.text((box[0] + 40 * u, y), ln, font=self.fS, fill=SUB)
                y += 18 * u
        else:
            bw = (box[2] - box[0] - 60 * u) * (1 - p / it.get("reveal_at", 0.7))
            d.rectangle([box[0] + 30 * u, box[3] - 24 * u, box[0] + 30 * u + max(bw, 0), box[3] - 18 * u], fill=ACC)

    def _doc(self, d, base, it, p):
        """documento/foto de evidencia + destaque (retangulo normalizado x,y,w,h) + zoom suave."""
        W, H, u = self.W, self.H, self.u
        img = self._img(it["image"]) if it.get("image") and os.path.exists(it["image"]) else None
        if img is None:
            return
        k = _ease(p * 1.3)
        hx, hy, hw, hh = it["highlight"]
        zoom = 1 + it.get("zoom", 0.6) * k
        iw, ih = img.size
        s = min(W * 0.6 / iw, H * 0.72 / ih)
        cx, cy = (hx + hw / 2) * iw, (hy + hh / 2) * ih
        vw, vh = iw / zoom, ih / zoom
        l = min(max(cx - vw / 2, 0), iw - vw)
        t = min(max(cy - vh / 2, 0), ih - vh)
        crop = img.crop((int(l), int(t), int(l + vw), int(t + vh)))
        tw, th = int(iw * s), int(ih * s)
        crop = crop.resize((tw, th))
        x0, y0 = int(W * 0.5 - tw / 2), int(H * 0.52 - th / 2)
        base.paste(crop, (x0, y0))
        dd = ImageDraw.Draw(base)
        rx0, ry0 = x0 + (hx * iw - l) / vw * tw, y0 + (hy * ih - t) / vh * th
        rx1, ry1 = rx0 + hw * iw / vw * tw, ry0 + hh * ih / vh * th
        dd.rectangle([rx0, ry0, rx1, ry1], outline=ACC + (255,), width=max(3, int(4 * u)))
        dd.rounded_rectangle([x0, y0 + th + 8 * u, x0 + tw, y0 + th + 40 * u], radius=int(8 * u), fill=PANEL)
        cap = it.get("caption", "") + (f"   —   {it['source']}" if it.get("source") else "")
        dd.text((x0 + 12 * u, y0 + th + 14 * u), cap, font=self.fS, fill=SUB)

    def _map(self, d, base, it, p):
        W, H, u = self.W, self.H, self.u
        mw, mh = int(W * 0.7), int(H * 0.74)
        x0, y0 = int(W * 0.15), int(H * 0.16)
        if it.get("image") and os.path.exists(it["image"]):
            m = self._img(it["image"]).resize((mw, mh))
            base.paste(m, (x0, y0))
        else:
            d.rounded_rectangle([x0, y0, x0 + mw, y0 + mh], radius=int(10 * u), fill=(14, 22, 40, 235))
            for g in range(1, 8):
                d.line([(x0 + mw * g / 8, y0), (x0 + mw * g / 8, y0 + mh)], fill=(40, 60, 95, 120))
                d.line([(x0, y0 + mh * g / 8), (x0 + mw, y0 + mh * g / 8)], fill=(40, 60, 95, 120))
        d = ImageDraw.Draw(base, "RGBA")
        P = lambda x, y: (x0 + x * mw, y0 + y * mh)
        for poly in it.get("regions", []):
            d.polygon([P(*q) for q in poly["points"]], fill=tuple(poly.get("color", (120, 170, 255))) + (70,), outline=tuple(poly.get("color", (120, 170, 255))) + (230,))
            if poly.get("label"):
                cx, cy = P(*np.mean(poly["points"], 0))
                d.text((cx - d.textlength(poly["label"], font=self.fS) / 2, cy), poly["label"], font=self.fS, fill=INK)
        for r in it.get("routes", []):
            pts = [P(*q) for q in r["points"]]
            seg = [math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
            tot, run, k = sum(seg), 0.0, _ease(p * 1.2) * sum(seg)
            col = tuple(r.get("color", ACC)) + (255,)
            for i, sl in enumerate(seg):
                if k <= run:
                    break
                f = min((k - run) / sl, 1.0)
                e = (pts[i][0] + (pts[i + 1][0] - pts[i][0]) * f, pts[i][1] + (pts[i + 1][1] - pts[i][1]) * f)
                d.line([pts[i], e], fill=col, width=max(3, int(5 * u)))
                run += sl
            if k > 0:
                a = math.atan2(e[1] - pts[i][1], e[0] - pts[i][0]) if 'e' in dir() else 0
                for s_ in (2.6, -2.6):
                    d.line([e, (e[0] - 16 * u * math.cos(a + s_ / 6 * 1), e[1] - 16 * u * math.sin(a + s_ / 6))], fill=col, width=max(3, int(5 * u)))
        for mk in it.get("markers", []):
            x, y = P(mk["x"], mk["y"])
            d.ellipse([x - 6 * u, y - 6 * u, x + 6 * u, y + 6 * u], fill=ACC + (255,), outline=INK + (255,))
            d.text((x + 10 * u, y - 10 * u), mk["label"], font=self.fS, fill=INK)
        d.text((x0, y0 + mh + 6 * u), it.get("source", "Map: schematic, not to scale"), font=self.fS, fill=SUB)

    def _compare(self, d, it, p):
        W, H, u = self.W, self.H, self.u
        for i, side in enumerate(("left", "right")):
            col = it[side]
            x0 = int(W * (0.08 if i == 0 else 0.52))
            self._panel(d, [x0, int(H * 0.26), x0 + int(W * 0.4), int(H * 0.78)], col["title"])
            y = H * 0.26 + 60 * u
            for j, b in enumerate(col["bullets"]):
                a = _ease(p * (len(col["bullets"]) + 1) - j)
                for ln in _wrap(d, b, self.fB, W * 0.4 - 60 * u):
                    d.text((x0 + 26 * u, y), ln, font=self.fB, fill=tuple(int(c * a) for c in INK) + (int(255 * a),))
                    y += 27 * u
                y += 8 * u

    def _badge(self, d, it, p):
        txt = BADGES.get(it.get("label", "simulation")) or it.get("label")
        if not txt:
            return
        u, W, H = self.u, self.W, self.H
        tw = d.textlength(txt, font=self.fS)
        x1, y1 = W - 28 * u, H - 24 * u
        d.rounded_rectangle([x1 - tw - 22 * u, y1 - 26 * u, x1, y1], radius=int(6 * u), fill=(8, 12, 24, 190), outline=ACC + (200,))
        d.text((x1 - tw - 11 * u, y1 - 21 * u), txt, font=self.fS, fill=ACC)

    # ------------------------------------------------------------ API
    def apply(self, img_u8, t):
        act = [it for it in self.items if it["start"] <= t <= it["end"]]
        if not act:
            return img_u8
        W, H = self.W, self.H
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer, "RGBA")
        amax = 0.0
        for it in act:
            dur = max(it["end"] - it["start"], 1e-3)
            p = (t - it["start"]) / dur
            f = it.get("fade", 0.5)
            a = min(1.0, (t - it["start"]) / f, (it["end"] - t) / f)
            sub = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            sd = ImageDraw.Draw(sub, "RGBA")
            k = it["kind"]
            if k == "doc":
                self._doc(sd, sub, it, p)
            elif k == "map":
                self._map(sd, sub, it, p)
            else:
                getattr(self, "_" + k)(sd, it, p)
            if a < 1:
                sub.putalpha(sub.getchannel("A").point(lambda v, a=a: int(v * max(a, 0))))
            layer = Image.alpha_composite(layer, sub)
        arr = np.asarray(layer, np.float32) / 255.0
        al = arr[..., 3:4]
        out = img_u8.astype(np.float32) / 255.0
        out = out * (1 - al) + arr[..., :3] * al
        return (np.clip(out, 0, 1) * 255 + 0.5).astype(np.uint8)
