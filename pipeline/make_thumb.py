#!/usr/bin/env python3
"""Miniatura de YouTube a partir de um frame do filme: no MAXIMO 3 palavras, texto grande e legivel no celular.
  python make_thumb.py projects/the_wall 628 "THE WALL" [--accent WALL] [--side left|right] [--out thumb.jpg]"""
import argparse, json, os, sys
os.environ.setdefault("OMP_NUM_THREADS", "2")
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageEnhance


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdir"); ap.add_argument("t", type=float); ap.add_argument("text")
    ap.add_argument("--accent", default=None, help="palavra destacada em amarelo")
    ap.add_argument("--side", default="left", choices=["left", "right", "center"])
    ap.add_argument("--out"); ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--style", default="bold", choices=["auto", "bold", "cinema", "number", "split", "banner"], help="auto: escolhe o proximo modelo diferente do ultimo usado (REGRA: toda thumb nova usa modelo novo) | bold | cinema | number (frase gigante) | split (diagonal) | banner (faixa colorida)")
    ap.add_argument("--sub", default=None, help="subtitulo (estilo cinema)")
    ap.add_argument("--y", type=float, default=0.5)
    ap.add_argument("--base", default=None, help="imagem 1920x1080 de base (ex.: quadro do video final com fotos reais) em vez de renderizar a cena 3D")
    a = ap.parse_args()
    hist_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "thumb_history.json")
    hist = json.load(open(hist_path)) if os.path.exists(hist_path) else []
    ACCENTS = [(255, 214, 0), (0, 229, 255), (255, 72, 72), (130, 255, 130), (255, 150, 40)]
    ORDER = ["bold", "cinema", "number", "split", "banner"]
    last = hist[-1] if hist else {}
    if a.style == "auto":                                   # modelo diferente do ultimo; entre os possiveis, o menos usado recentemente
        recent = [h["style"] for h in hist[-len(ORDER):]]
        cand = [x for x in ORDER if x != last.get("style")]
        a.style = min(cand, key=lambda x: (recent.count(x), recent[::-1].index(x) * -1 if x in recent else -99))
    elif a.style == last.get("style") and not os.environ.get("THUMB_ALLOW_REPEAT"):
        print(f"AVISO: o ultimo video ('{last.get('project')}') ja usou o modelo '{a.style}'. Regra: use outro (ex.: --style auto).", file=sys.stderr)
    ai = (ACCENTS.index(tuple(last["accent"])) + 1) % len(ACCENTS) if last.get("accent") else 0
    ACC = ACCENTS[ai]
    words = a.text.split()
    if a.style in ("bold", "number", "split", "banner") and len(words) > 3:
        sys.exit("No estilo bold a thumb deve ter no maximo 3 palavras (use --style cinema para titulos finos mais longos).")
    import render_film as rf
    proj = json.load(open(os.path.join(a.pdir, "project.json")))
    proj["titles"] = []
    r = proj["render"]
    W, H = 1920, 1080                                    # miniatura 1080p (<2 MB), texturas em alta
    r["texture_width"] = 4096
    rf.init(proj, W, H, r["fps"])
    if a.base:
        img = np.asarray(Image.open(a.base).convert("RGB").resize((W, H)), np.uint8)
    else:
        img = rf.G["film"].render(a.t)                   # sem HUD, sem legendas
    if a.style == "cinema":                              # titulo fino, espacado, com brilho suave (mesmo visual da abertura do filme)
        from engine.overlay import Overlay
        ov = Overlay([dict(text=a.text.upper(), sub=a.sub, start=0, end=1000, fade=0.01, y=a.y, size=0.062 * a.scale, sub_size=0.026, tracking=0.03)], W, H, proj["render"].get("font"))
        out_ = ov.apply(img, 500.0)
        im = Image.fromarray(out_).convert("RGB")
        out = a.out or os.path.join(a.pdir, "output", "thumbnail.jpg")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        im = ImageEnhance.Contrast(im).enhance(1.08)
        im.save(out, quality=94)
        hist.append({"project": os.path.basename(a.pdir.rstrip("/")), "style": "cinema", "t": a.t, "text": a.text, "accent": list(ACC), "out": out})
        json.dump(hist[-40:], open(hist_path, "w"), indent=1)
        print("salvo", out, os.path.getsize(out) // 1024, "KB  modelo: cinema")
        return
    def _record(style, out_path):
        hist.append({"project": os.path.basename(a.pdir.rstrip("/")), "style": style, "t": a.t, "text": a.text, "accent": list(ACC), "out": out_path})
        json.dump(hist[-40:], open(hist_path, "w"), indent=1)

    if a.style in ("number", "split", "banner"):
        font_black = "/usr/share/fonts/opentype/inter/Inter-Black.otf"
        font_med = "/usr/share/fonts/opentype/inter/Inter-Medium.otf"
        base = Image.fromarray(img).convert("RGB")
        base = ImageEnhance.Contrast(ImageEnhance.Color(base).enhance(1.15)).enhance(1.1)
        g = np.asarray(base, np.float32)
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        if a.style == "number":                          # frase/numero gigante no centro, subtitulo fino embaixo
            g = g * 0.55
            sz = int(H * 0.30 * a.scale)
            ft = ImageFont.truetype(font_black, sz)
            while ld.textlength(a.text.upper(), font=ft) > W * 0.92 and sz > 60:
                sz -= 6
                ft = ImageFont.truetype(font_black, sz)
            w = ld.textlength(a.text.upper(), font=ft)
            ld.text(((W - w) / 2 + 5, H * 0.34 + 8), a.text.upper(), font=ft, fill=(0, 0, 0, 220))
            ld.text(((W - w) / 2, H * 0.34), a.text.upper(), font=ft, fill=ACC + (255,), stroke_width=max(2, sz // 45), stroke_fill=(0, 0, 0, 255))
            if a.sub:
                fs = ImageFont.truetype(font_med, int(H * 0.06))
                ws = ld.textlength(a.sub.upper(), font=fs)
                ld.text(((W - ws) / 2, H * 0.34 + sz * 1.12), a.sub.upper(), font=fs, fill=(255, 255, 255, 235))
        elif a.style == "split":                         # metade esquerda escurecida e diagonal colorida, texto em duas linhas
            yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
            edge = W * 0.52 + (yy - H / 2) * 0.35
            left = np.clip((edge - xx) / 40.0, 0, 1)[..., None]
            g = g * (1 - 0.78 * left) + np.array(ACC, np.float32) * 0.0
            band = (np.abs(xx - edge) < 9).astype(np.float32)[..., None]
            g = g * (1 - band) + np.array(ACC, np.float32) * band
            sz = int(H * 0.19 * a.scale)
            ft = ImageFont.truetype(font_black, sz)
            for i, wd in enumerate(words):
                col = ACC if i == len(words) - 1 else (255, 255, 255)
                ld.text((int(W * 0.04) + 4, int(H * 0.28) + i * int(sz * 1.05) + 6), wd.upper(), font=ft, fill=(0, 0, 0, 220))
                ld.text((int(W * 0.04), int(H * 0.28) + i * int(sz * 1.05)), wd.upper(), font=ft, fill=col + (255,))
        else:                                            # banner: faixa colorida na parte de baixo com o texto em preto
            ph = int(H * 0.26)
            g[H - ph:, :, :] = np.array(ACC, np.float32) * 0.95
            sz = int(ph * 0.62 * a.scale)
            ft = ImageFont.truetype(font_black, sz)
            while ld.textlength(a.text.upper(), font=ft) > W * 0.9 and sz > 50:
                sz -= 4
                ft = ImageFont.truetype(font_black, sz)
            w = ld.textlength(a.text.upper(), font=ft)
            ld.text(((W - w) / 2, H - ph + (ph - sz) / 2 - sz * 0.08), a.text.upper(), font=ft, fill=(10, 10, 10, 255))
        im = Image.fromarray(np.clip(g, 0, 255).astype(np.uint8)).convert("RGBA")
        im = Image.alpha_composite(im, layer.filter(ImageFilter.GaussianBlur(8)))
        im = Image.alpha_composite(im, layer).convert("RGB")
        out = a.out or os.path.join(a.pdir, "output", "thumbnail.jpg")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        im.save(out, quality=92)
        _record(a.style, out)
        print("salvo", out, os.path.getsize(out) // 1024, "KB  modelo:", a.style)
        return
    im = Image.fromarray(img).convert("RGB")
    im = ImageEnhance.Contrast(ImageEnhance.Color(im).enhance(1.25)).enhance(1.12)
    # gradiente escuro atras do texto
    g = np.asarray(im, np.float32)
    x = np.linspace(0, 1, W)[None, :, None]
    shade = {"left": np.clip(1 - x / 0.62, 0, 1), "right": np.clip((x - 0.38) / 0.62, 0, 1), "center": np.clip(1 - np.abs(x - 0.5) / 0.4, 0, 1)}[a.side]
    g = g * (1 - 0.55 * shade ** 1.3)
    im = Image.fromarray(np.clip(g, 0, 255).astype(np.uint8))
    font_path = "/usr/share/fonts/opentype/inter/Inter-Black.otf"
    lines = words if len(words) > 1 else words
    size = int(H * 0.25 * a.scale) if len(lines) <= 2 else int(H * 0.2 * a.scale)
    font = ImageFont.truetype(font_path, size)
    d = ImageDraw.Draw(im)
    lh = int(size * 1.02)
    total = lh * len(lines)
    y0 = (H - total) // 2
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    for i, wd in enumerate(lines):
        w = ld.textlength(wd, font=font)
        xx = {"left": int(W * 0.05), "right": int(W * 0.95 - w), "center": int((W - w) / 2)}[a.side]
        col = ACC if (a.accent and wd.strip(".,:").upper() == a.accent.upper()) else (255, 255, 255)
        ld.text((xx + 5, y0 + i * lh + 7), wd, font=font, fill=(0, 0, 0, 200))
        ld.text((xx, y0 + i * lh), wd, font=font, fill=col + (255,), stroke_width=max(2, size // 40), stroke_fill=(0, 0, 0, 255))
    shadow = layer.filter(ImageFilter.GaussianBlur(10))
    im = Image.alpha_composite(Image.alpha_composite(im.convert("RGBA"), shadow), layer).convert("RGB")
    out = a.out or os.path.join(a.pdir, "output", "thumbnail.jpg")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    im.save(out, quality=92)
    hist.append({"project": os.path.basename(a.pdir.rstrip("/")), "style": "bold", "t": a.t, "text": a.text, "accent": list(ACC), "out": out})
    json.dump(hist[-40:], open(hist_path, "w"), indent=1)
    print("salvo", out, os.path.getsize(out) // 1024, "KB  modelo: bold")


if __name__ == "__main__":
    main()
