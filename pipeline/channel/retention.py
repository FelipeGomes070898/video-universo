"""Cruza a curva de retencao com o roteiro e a linha do tempo (project.json + captions.srt): associa quedas/subidas a cena, frase e eventos visuais,
e diagnostica o proprio roteiro (introducao lenta, frases longas, repeticoes, lacunas sem mudanca visual). Retencao real so existe apos a publicacao;
o diagnostico do roteiro (sem curva) pode rodar ANTES de publicar."""
import json, os, re
from collections import Counter


def parse_srt(path):
    out = []
    for blk in re.split(r"\n\s*\n", open(path, encoding="utf-8").read().strip()):
        ln = blk.strip().splitlines()
        if len(ln) >= 3 and "-->" in ln[1]:
            a, b = ln[1].split("-->")
            f = lambda s: (lambda h, m, x: int(h) * 3600 + int(m) * 60 + float(x.replace(",", ".")))(*s.strip().split(":"))
            out.append((f(a), f(b), " ".join(ln[2:])))
    return out


def timeline(project_json):
    p = json.load(open(project_json, encoding="utf-8"))
    ev = sorted([t["start"] for t in p.get("titles", [])] + [m["start"] for m in p.get("media", [])] + [c["start"] for c in p.get("cards", [])])
    return dict(scenes=[dict(id=s["id"], start=s["start"], end=s["end"]) for s in p["scenes"]], events=ev, duration=p["briefing"]["duration_seconds"])


def where(t, tl, srt):
    sc = next((s for s in tl["scenes"] if s["start"] <= t < s["end"]), None)
    sent = next((s for s in srt if s[0] <= t <= s[1] + 0.2), None)
    near = [e for e in tl["events"] if t - 8 <= e <= t + 2]
    last = max([e for e in tl["events"] if e <= t], default=0)
    return dict(scene=sc["id"] if sc else None, sentence=sent[2] if sent else None, events_nearby=len(near), seconds_since_last_event=round(t - last, 1))


def map_drops(drop_list, tl, srt):
    return [dict(d, **where(d["sec"], tl, srt)) for d in drop_list]


def script_diagnostics(tl, srt):
    D = []
    first_ev = min(tl["events"], default=None)
    if first_ev is None or first_ev > 15:
        D.append(f"introducao: primeiro evento visual (texto/midia/quadro) so aos {first_ev if first_ev is None else round(first_ev, 1)} s (meta: <= 15 s)")
    if srt and srt[0][0] > 3:
        D.append(f"narracao so comeca aos {srt[0][0]:.1f} s")
    ev = [0] + tl["events"] + [tl["duration"]]
    for a, b in zip(ev, ev[1:]):
        if b - a > 30:
            D.append(f"lacuna visual de {b - a:.0f} s sem evento ({a:.0f}-{b:.0f} s)")
    for s, e, t in srt:
        if len(t.split()) > 38 or e - s > 15:
            D.append(f"frase longa ({len(t.split())} palavras, {e - s:.0f} s) em {s:.0f} s: \"{t[:60]}...\"")
    tri = Counter()
    for _, _, t in srt:
        w = re.findall(r"[a-z']+", t.lower())
        tri.update(zip(w, w[1:], w[2:]))
    rep = [" ".join(k) for k, n in tri.items() if n >= 3]
    if rep:
        D.append("trechos repetidos (>=3x): " + "; ".join(rep[:4]))
    long_sc = [s["id"] for s in tl["scenes"] if s["end"] - s["start"] > 60]
    if long_sc:
        D.append("cenas muito longas (>60 s): " + ", ".join(long_sc))
    return D
