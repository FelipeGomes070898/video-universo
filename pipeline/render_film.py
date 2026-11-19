#!/usr/bin/env python3
"""Renderiza o filme em blocos paralelos (CPU) e muxa com a trilha.

  python render_film.py projects/the_wall [--preview] [--workers 4] [--still 12.5 80 ...] [--range 0 60]
"""
import argparse, json, os, subprocess, sys, time
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
import numpy as np
import cv2
cv2.setNumThreads(1)
from multiprocessing import Pool
from PIL import Image

G = {}


def init(proj, W, H, fps):
    from engine.film import Film
    from engine.ages import AgesFilm
    from engine.overlay import Overlay
    from engine.hud import Hud
    from engine.hud_time import TimeHud
    from engine.cards import Cards
    from engine.media import MediaLayer
    cv2.setNumThreads(1)
    G["film"] = (AgesFilm if proj.get("ages") else Film)(proj, W, H)
    G["ov"] = Overlay(proj["titles"], W, H, proj["render"].get("font"))
    G["cards"] = Cards(proj.get("cards", []), W, H)
    G["media"] = MediaLayer(proj.get("media", []), W, H)
    G["hud"] = (TimeHud if proj["hud"].get("kind") == "time" else Hud)(proj["hud"]["keys"], proj["hud"]["windows"], W, H)
    G["fps"], G["W"], G["H"], G["proj"] = fps, W, H, proj


def frame_at(t):
    img = G["film"].render(t)
    img = G["media"].apply(img, t)
    img = G["hud"].apply(img, t)
    img = G["ov"].apply(img, t)
    return G["cards"].apply(img, t)


def do_chunk(task):
    idx, a, b, path = task
    if os.path.exists(path) and os.path.getsize(path) > 1000:
        return idx, path, 0.0
    t0 = time.time()
    W, H, fps = G["W"], G["H"], G["fps"]
    r = G["proj"]["render"]
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
           "-c:v", "libx264", "-preset", r.get("preset", "medium"), "-crf", str(r.get("crf", 18)), "-pix_fmt", "yuv420p", "-g", str(fps * 2), "-an", path + ".tmp.mp4"]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(a, b):
        p.stdin.write(frame_at(i / fps).tobytes())
    p.stdin.close()
    p.wait()
    os.replace(path + ".tmp.mp4", path)
    return idx, path, time.time() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdir")
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--still", type=float, nargs="+")
    ap.add_argument("--range", type=float, nargs=2)
    ap.add_argument("--chunk", type=int, default=240)
    ap.add_argument("--height", type=int, help="altura de saida: 720 (padrao), 1080, 1440 ou 2160 (4K, 3840x2160)")
    ap.add_argument("--out")
    a = ap.parse_args()
    proj = json.load(open(os.path.join(a.pdir, "project.json")))
    r = proj["render"]
    W, H, fps = r["width"], r["height"], r["fps"]
    if a.preview:
        W, H, fps = 640, 360, 12
        r["texture_width"] = 1024
        r["crf"], r["preset"] = 28, "veryfast"
    if a.height and not a.preview:
        H = a.height
        W = int(round(H * 16 / 9 / 2)) * 2
        r["width"], r["height"] = W, H
        r["texture_width"] = 4096 if H >= 1440 else 2048
        r["crf"] = 17 if H >= 1440 else r.get("crf", 18)
        r["preset"] = "medium"
        a.chunk = min(a.chunk, 96) if H >= 1440 else a.chunk
    out_dir = os.path.join(a.pdir, "output")
    tag = "preview" if a.preview else ("final" if not a.height or a.height == 720 else f"final_{a.height}p")
    os.makedirs(out_dir, exist_ok=True)
    if a.still:
        init(proj, W, H, fps)
        for ts in a.still:
            p = os.path.join(out_dir, f"still_{ts:07.2f}.png")
            Image.fromarray(frame_at(ts)).save(p)
            print("salvo", p, flush=True)
        return
    dur = proj["briefing"]["duration_seconds"]
    f0, f1 = (0, int(round(dur * fps))) if not a.range else (int(a.range[0] * fps), int(a.range[1] * fps))
    cdir = os.path.join(out_dir, f"chunks_{tag}")
    os.makedirs(cdir, exist_ok=True)
    tasks = []
    for k, s in enumerate(range(f0, f1, a.chunk)):
        tasks.append((k, s, min(s + a.chunk, f1), os.path.join(cdir, f"c{k:04d}_{s}.mp4")))
    print(f"{f1 - f0} frames em {len(tasks)} blocos, {a.workers} processos, {W}x{H}@{fps}", flush=True)
    t0 = time.time()
    done = 0
    res = {}
    with Pool(a.workers, initializer=init, initargs=(proj, W, H, fps)) as pool:
        for idx, path, el in pool.imap_unordered(do_chunk, tasks):
            done += 1
            res[idx] = path
            print(f"  bloco {idx + 1}/{len(tasks)} ok ({el:.0f}s)  total {time.time() - t0:.0f}s  restantes {len(tasks) - done}", flush=True)
    lst = os.path.join(cdir, "list.txt")
    with open(lst, "w") as f:
        for k in sorted(res):
            f.write(f"file '{os.path.abspath(res[k])}'\n")
    out = a.out or os.path.join(out_dir, f"{proj['briefing']['slug']}.{tag}.mp4")
    vid = os.path.join(cdir, "video_only.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", vid], check=True)
    wav = os.path.join(out_dir, "audio_mix.wav")
    if os.path.exists(wav) and not a.range:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", vid, "-i", wav, "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", out], check=True)
    else:
        os.replace(vid, out)
    print("OK ->", out, f"({time.time() - t0:.0f}s)", flush=True)


if __name__ == "__main__":
    sys.exit(main())
