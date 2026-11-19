"""HUD de linha do tempo: 'anos atras' + relogio de 24 h da historia da Terra."""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from .hud import Hud, _f

EARTH_AGE = 4.54e9


def fmt_years(y):
    if y <= -1e6:
        v = -y
        return f"In {v / 1e9:,.1f} billion years" if v >= 1e9 else f"In {v / 1e6:,.0f} million years"
    if abs(y) < 60:
        return "NOW"
    if y >= 1e9:
        return f"{y / 1e9:,.2f} billion years ago"
    if y >= 1e7:
        return f"{y / 1e6:,.0f} million years ago"
    if y >= 1e6:
        return f"{y / 1e6:,.1f} million years ago"
    if y >= 1000:
        return f"{round(y, -2 if y > 5000 else 0):,.0f} years ago"
    return f"{y:,.0f} years ago"


def fmt_clock(y):
    if y <= 0:
        return "24:00:00"
    sec = (EARTH_AGE - y) / EARTH_AGE * 86400.0
    sec = min(sec, 86399.0)
    return f"{int(sec // 3600):02d}:{int(sec % 3600 // 60):02d}:{int(sec % 60):02d}"


class TimeHud(Hud):
    def __init__(self, keys, windows, W, H):
        super().__init__([(k[0], 1.0) for k in keys], windows, W, H)
        self.tk = np.array([k[0] for k in keys], float)
        self.yk = np.array([k[1] for k in keys], float)          # anos atras (negativo = futuro)

    def years_at(self, t):
        if t <= self.tk[0]:
            return self.yk[0]
        if t >= self.tk[-1]:
            return self.yk[-1]
        i = int(np.searchsorted(self.tk, t, side="right") - 1)
        a = (t - self.tk[i]) / (self.tk[i + 1] - self.tk[i])
        a = a * a * (3 - 2 * a)
        return self.yk[i] + (self.yk[i + 1] - self.yk[i]) * a

    def apply(self, img, t):
        a = self.alpha(t)
        if a <= 0:
            return img
        W, H, u = self.W, self.H, self.u
        y = self.years_at(t)
        sh = int(112 * u)
        layer = Image.new("RGBA", (W, sh), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        x0, y0 = self.pad, int(self.pad * 0.8)
        lab, white = (190, 205, 235, 215), (255, 255, 255, 255)

        def tracked(xx, yy, text, font, fill, track):
            for ch in text:
                d.text((xx, yy), ch, font=font, fill=fill)
                xx += font.getlength(ch) + track

        tracked(x0, y0, "TIME", self.f_lab, lab, 2.2 * u)
        d.text((x0, y0 + int(20 * u)), fmt_years(y), font=self.f_val, fill=white)
        lab2 = "EARTH'S HISTORY AS ONE DAY" if y > 0 else "BEYOND TODAY"
        txt = fmt_clock(y) if y > 0 else "after midnight"
        wl = sum(self.f_lab.getlength(c) + 2.2 * u for c in lab2)
        tracked(W - self.pad - wl, y0, lab2, self.f_lab, lab, 2.2 * u)
        tw = self.f_val.getlength(txt)
        d.text((W - self.pad - tw, y0 + int(20 * u)), txt, font=self.f_val, fill=white)
        by = y0 + int(66 * u)
        frac = float(np.clip((EARTH_AGE - y) / EARTH_AGE, 0, 1))      # barra de progresso das 24 h
        x1 = W - self.pad
        x_0 = x1 - self.beam_w
        d.line([(x_0, by), (x1, by)], fill=(120, 140, 190, 110), width=max(1, int(1.5 * u)))
        d.line([(x_0, by), (x_0 + frac * self.beam_w, by)], fill=(255, 235, 190, 220), width=max(2, int(2.2 * u)))
        glow = layer.filter(ImageFilter.GaussianBlur(4 * u))
        arr = np.asarray(Image.alpha_composite(glow, layer), np.float32) / 255.0
        strip = img[:sh].astype(np.float32) / 255.0
        strip = strip * (1 - 0.38 * a * np.clip(1 - np.arange(sh)[:, None, None] / sh, 0, 1))
        al = arr[..., 3:4] * a
        strip = strip * (1 - al) + arr[..., :3] * al
        out = img.copy()
        out[:sh] = (np.clip(strip, 0, 1) * 255 + 0.5).astype(np.uint8)
        return out
