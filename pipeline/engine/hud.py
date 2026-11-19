"""HUD documental: contador de distancia + 'raio de luz' (tempo que a luz leva de casa ate aqui)."""
import math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

C_KM_S = 299792.458
LY_KM = 9.4607e12
FONT_DIR = "/usr/share/fonts/opentype/inter/"


def _f(name, size):
    try:
        return ImageFont.truetype(FONT_DIR + name, size)
    except Exception:
        return ImageFont.load_default(size)


def fmt_distance(km):
    ly = km / LY_KM
    if ly >= 0.5:
        if ly >= 1e9:
            return f"{ly / 1e9:,.1f} billion light-years"
        if ly >= 1e6:
            return f"{ly / 1e6:,.1f} million light-years"
        if ly >= 1000:
            return f"{ly:,.0f} light-years"
        return f"{ly:,.2f} light-years" if ly < 100 else f"{ly:,.0f} light-years"
    if km >= 1e12:
        return f"{km / 1e12:,.2f} trillion km"
    if km >= 1e9:
        return f"{km / 1e9:,.2f} billion km"
    if km >= 100:
        return f"{km:,.0f} km"
    return f"{km:,.1f} km"


def fmt_light(km):
    s = km / C_KM_S
    if s < 1e-3:
        return f"{s * 1e6:,.1f} microseconds"
    if s < 1:
        return f"{s * 1e3:,.0f} milliseconds" if s >= 0.01 else f"{s * 1e3:,.1f} milliseconds"
    if s < 60:
        return f"{s:,.2f} seconds"
    if s < 3600:
        return f"{int(s // 60)} min {int(s % 60):02d} s"
    if s < 86400:
        return f"{s / 3600:,.1f} hours" if s < 36000 else f"{s / 3600:,.0f} hours"
    if s < 86400 * 365.25:
        return f"{s / 86400:,.1f} days"
    y = s / (86400 * 365.25)
    if y >= 1e9:
        return f"{y / 1e9:,.1f} billion years"
    if y >= 1e6:
        return f"{y / 1e6:,.1f} million years"
    if y >= 1000:
        return f"{y:,.0f} years"
    return f"{y:,.1f} years"


def _smooth(x):
    return x * x * (3 - 2 * x)


class Hud:
    def __init__(self, keys, windows, W, H):
        """keys: [(t, km)] ordenado; windows: [(t_in, t_out)] em que o HUD aparece."""
        self.t = np.array([k[0] for k in keys], float)
        self.lg = np.log10(np.array([max(k[1], 1e-3) for k in keys], float))
        self.windows = windows
        self.W, self.H = W, H
        u = H / 720.0
        self.u = u
        self.f_lab = _f("Inter-SemiBold.otf", int(12 * u))
        self.f_val = _f("InterDisplay-Medium.otf", int(30 * u))
        self.pad = int(34 * u)
        self.beam_w = int(230 * u)

    def km_at(self, t):
        if t <= self.t[0]:
            return 10 ** self.lg[0]
        if t >= self.t[-1]:
            return 10 ** self.lg[-1]
        i = int(np.searchsorted(self.t, t, side="right") - 1)
        a = (t - self.t[i]) / (self.t[i + 1] - self.t[i])
        span = abs(self.lg[i + 1] - self.lg[i])
        a = _smooth(a) if span > 0.9 else a             # saltos grandes (entre cenas) aceleram e freiam
        return 10 ** (self.lg[i] + (self.lg[i + 1] - self.lg[i]) * a)

    def alpha(self, t):
        a = 0.0
        for t0, t1 in self.windows:
            a = max(a, min(1.0, (t - t0) / 1.0, (t1 - t) / 1.0))
        return max(0.0, a)

    def apply(self, img, t):
        a = self.alpha(t)
        if a <= 0:
            return img
        W, H, u = self.W, self.H, self.u
        km = self.km_at(t)
        sh = int(112 * u)
        layer = Image.new("RGBA", (W, sh), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        x, y = self.pad, int(self.pad * 0.8)

        def tracked(xx, yy, text, font, fill, track):
            for ch in text:
                d.text((xx, yy), ch, font=font, fill=fill)
                xx += font.getlength(ch) + track
            return xx

        lab = (190, 205, 235, 215)
        white = (255, 255, 255, 255)
        tracked(x, y, "DISTANCE FROM EARTH", self.f_lab, lab, 2.2 * u)
        d.text((x, y + int(20 * u)), fmt_distance(km), font=self.f_val, fill=white)
        # raio de luz
        xr = W - self.pad - self.beam_w
        tracked(xr, y, "LIGHT FROM HOME", self.f_lab, lab, 2.2 * u)
        txt = fmt_light(km)
        tw = self.f_val.getlength(txt)
        d.text((W - self.pad - tw, y + int(20 * u)), txt, font=self.f_val, fill=white, anchor="la")
        by = y + int(66 * u)
        d.line([(xr, by), (W - self.pad, by)], fill=(120, 140, 190, 110), width=max(1, int(1.5 * u)))
        ph = (t * 0.55) % 1.0
        for k in range(26):                                   # pulso de luz viajando (cometa)
            pp = ph - k * 0.012
            if pp < 0:
                continue
            al = int(255 * (1 - k / 26) ** 1.6)
            px = xr + pp * self.beam_w
            d.ellipse([px - 2.2 * u, by - 2.2 * u, px + 2.2 * u, by + 2.2 * u], fill=(255, 245, 210, al))
        glow = layer.filter(ImageFilter.GaussianBlur(4 * u))
        comp = Image.alpha_composite(glow, layer)
        arr = np.asarray(comp, np.float32) / 255.0
        strip = img[:sh].astype(np.float32) / 255.0
        shade = 1 - 0.38 * a * np.clip(1 - np.arange(sh)[:, None, None] / sh, 0, 1)   # leve gradiente escuro p/ leitura
        strip = strip * shade
        al = arr[..., 3:4] * a
        strip = strip * (1 - al) + arr[..., :3] * al
        out = img.copy()
        out[:sh] = (np.clip(strip, 0, 1) * 255 + 0.5).astype(np.uint8)
        return out
