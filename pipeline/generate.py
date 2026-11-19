#!/usr/bin/env python3
"""Uso:
  python generate.py projects/space_journey/project.json                 # video completo
  python generate.py projects/space_journey/project.json --preview       # 640x360, 15fps, rapido
  python generate.py projects/space_journey/project.json --still 6.5     # um frame PNG no tempo t
"""
import argparse, json, os, subprocess, sys, time
import numpy as np
from PIL import Image
from engine.renderer import Renderer
from engine.ocean import OceanRenderer
from engine.overlay import Overlay
from engine import audio


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--out")
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--still", type=float, nargs="+")
    ap.add_argument("--no-audio", action="store_true")
    a = ap.parse_args()

    proj = json.load(open(a.project, encoding="utf-8"))
    r = proj["render"]
    W, H, fps = r["width"], r["height"], r["fps"]
    if a.preview:
        W, H, fps = 640, 360, 15
        r["texture_width"] = 1024
    dur = proj["briefing"]["duration_seconds"]
    out_dir = os.path.join(os.path.dirname(a.project) or ".", "output")
    os.makedirs(out_dir, exist_ok=True)
    out = a.out or os.path.join(out_dir, proj["briefing"].get("slug", "video") + (".preview" if a.preview else "") + ".mp4")

    t0 = time.time()
    print(f"[1/4] Construindo mundo (texturas procedurais) {W}x{H}@{fps}...", flush=True)
    rend = (OceanRenderer if proj.get('scene') == 'ocean' else Renderer)(proj, W, H)
    ov = Overlay(proj.get("titles", []), W, H, r.get("font"))
    print(f"      pronto em {time.time()-t0:.1f}s", flush=True)

    if a.still:
        for ts in a.still:
            img = ov.apply(rend.render(ts), ts)
            p = os.path.join(out_dir, f"still_{ts:05.2f}.png")
            Image.fromarray(img).save(p)
            print("salvo", p)
        return

    wav = os.path.join(out_dir, "audio.wav")
    if not a.no_audio:
        print("[2/4] Sintetizando trilha sonora...", flush=True)
        (audio.synth_sea if proj["audio"].get("style") == "sea" else audio.synth)(proj["audio"], dur, wav)

    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(fps), "-i", "-"]
    if not a.no_audio:
        cmd += ["-i", wav]
    cmd += ["-c:v", "libx264", "-preset", r.get("preset", "medium"), "-crf", str(r.get("crf", 18)), "-pix_fmt", "yuv420p"]
    if not a.no_audio:
        cmd += ["-c:a", "aac", "-b:a", "192k", "-ar", "44100"]
    cmd += ["-movflags", "+faststart", "-t", str(dur), out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n = int(round(dur * fps))
    print(f"[3/4] Renderizando {n} frames...", flush=True)
    ts = time.time()
    for i in range(n):
        t = i / fps
        proc.stdin.write(ov.apply(rend.render(t), t).tobytes())
        if i % 20 == 0 or i == n - 1:
            el = time.time() - ts
            eta = el / (i + 1) * (n - i - 1)
            print(f"      frame {i+1}/{n}  decorrido {el:5.0f}s  restante ~{eta:5.0f}s", flush=True)
    proc.stdin.close()
    proc.wait()
    print(f"[4/4] OK -> {out}  (total {time.time()-t0:.0f}s)")


if __name__ == "__main__":
    sys.exit(main())
