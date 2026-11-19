"""Titulos/legendas animados (PIL), pre-renderizados e compostos com fade."""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

FONTS = ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
         "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", "C:/Windows/Fonts/segoeui.ttf",
         "/System/Library/Fonts/Helvetica.ttc"]


def _font(path, size):
    for p in ([path] if path else []) + FONTS:
        if p and os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default(size)


def _tracked(draw, cx, cy, text, font, track, fill):
    widths = [font.getlength(c) for c in text]
    total = sum(widths) + track * (len(text) - 1)
    x = cx - total / 2
    for c, w in zip(text, widths):
        draw.text((x, cy), c, font=font, fill=fill, anchor="lm")
        x += w + track


class Overlay:
    def __init__(self, titles, W, H, font_path=None):
        self.items = []
        for t in titles:
            layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            d = ImageDraw.Draw(layer)
            cy = int(H * t.get("y", 0.5))
            big = _font(font_path, int(H * t.get("size", 0.09)))
            _tracked(d, W / 2, cy, t["text"], big, H * t.get("tracking", 0.02), (255, 255, 255, 255))
            if t.get("sub"):
                sm = _font(font_path, int(H * t.get("sub_size", 0.032)))
                _tracked(d, W / 2, cy + H * t.get("size", 0.09) * 0.95, t["sub"], sm, H * 0.006, (200, 215, 255, 235))
            glow = layer.filter(ImageFilter.GaussianBlur(H * 0.012))
            comp = Image.alpha_composite(glow, layer)
            arr = np.asarray(comp, np.float32) / 255.0
            self.items.append((t["start"], t["end"], t.get("fade", 0.8), arr[..., :3], arr[..., 3:4], t.get("y", 0.5)))
        yy = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
        self.grad = np.clip((yy - 0.62) / 0.38, 0, 1) ** 1.3

    def apply(self, img_u8, t):
        out = None
        for s, e, f, rgb, a, y in self.items:
            if s <= t <= e:
                k = min(1.0, (t - s) / f, (e - t) / f)
                if k <= 0:
                    continue
                if out is None:
                    out = img_u8.astype(np.float32) / 255.0
                if y > 0.7:
                    out = out * (1 - 0.5 * k * self.grad)
                aa = a * k
                out = out * (1 - aa) + rgb * aa
        return img_u8 if out is None else (np.clip(out, 0, 1) * 255 + 0.5).astype(np.uint8)
