"""VERIFICACAO FINAL: tudo que e mensuravel e medido de verdade; o resto vira MANUAL (nunca finge aprovar)."""
import json
import os
import re
import subprocess
import wave
import numpy as np
from . import research, assets
from .. import voice as vc

CLICKBAIT = re.compile(r"\b(you won'?t believe|shocking|insane|destroyed|gone wrong|secret they|nobody tells|exposed)\b", re.I)


def _wav(path):
    with wave.open(path, "rb") as w:
        d = np.frombuffer(w.readframes(w.getnframes()), "<i2").astype(np.float32) / 32768
        return (d.reshape(-1, w.getnchannels()).mean(1) if w.getnchannels() > 1 else d), w.getframerate()


def _lufs(path):
    r = subprocess.run(["ffmpeg", "-nostats", "-i", path, "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True).stderr
    i = re.findall(r"I:\s+(-?[\d.]+) LUFS", r)
    tp = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", r)
    return (float(i[-1]) if i else None), (float(tp[-1]) if tp else None)


def run(proj, pdir, dossier=None, publication=None, formato=None):
    out_dir = os.path.join(pdir, "output")
    R = []
    add = lambda n, st, d: R.append(dict(verificacao=n, status=st, detalhe=d))
    scenes = proj["scenes"]
    total = proj["briefing"]["duration_seconds"]
    dossier = dossier or {}
    # --- factual
    prob = research.validate(dossier, True)
    cnt = research.summary(dossier)
    if not dossier.get("fatos"):
        add("Factual", "WARN", "sem dossier de fatos com fontes; afirmacoes factuais nao rastreadas")
    elif prob:
        add("Factual", "WARN", f"{len(prob)} problema(s): " + "; ".join(prob[:3]))
    else:
        nv = cnt.get("nao_verificado", 0) + cnt.get("incerto", 0)
        add("Factual", "WARN" if nv else "PASS", f"{sum(cnt.values())} fatos {cnt}" + (f"; {nv} sem verificacao independente" if nv else ""))
    # --- narrativa
    roles = [s.get("role") for s in scenes if s.get("role")]
    add("Narrativa (comeco/desenvolvimento/virada/conclusao)", "PASS" if {"gancho", "virada", "conclusao"} <= set(roles) else "WARN", f"papeis declarados: {sorted(set(roles)) or 'nenhum'}")
    # --- visual / ritmo
    durs = [(s["end"] - s["start"], s["id"]) for s in scenes]
    mx = max(durs)
    add("Visual: mudanca de cena", "PASS" if mx[0] <= 45 else "WARN", f"maior cena sem corte: {mx[0]:.0f}s ({mx[1]}); media {np.mean([d for d, _ in durs]):.0f}s")
    txt = proj.get("titles", [])
    cov = sum(t["end"] - t["start"] for t in txt) / total
    add("Texto na tela nao excessivo", "PASS" if cov < 0.5 else "WARN", f"{cov:.0%} do tempo com legenda/titulo")
    didactic = formato and formato.get("formato", "").startswith("aula")
    nq = sum(1 for c in proj.get("cards", []) if c["kind"] == "quiz")
    add("Didatica: exercicios (so em aula)", ("PASS" if nq else "WARN") if didactic else "N/A", f"{nq} quiz(es)")
    # --- retencao
    sents = [(se_t) for se_t in proj.get("titles", [])]
    srt = os.path.join(out_dir, "captions.srt")
    words = 0
    if os.path.exists(srt):
        words = sum(len(l.split()) for l in open(srt, encoding="utf-8") if l.strip() and not l.strip().isdigit() and "-->" not in l)
    add("Ritmo de fala", "PASS" if 110 <= words / (total / 60) <= 185 else "WARN", f"{words / (total / 60):.0f} palavras/min")
    # --- audio medido
    nar, mix = os.path.join(out_dir, "narration.wav"), os.path.join(out_dir, "audio_mix.wav")
    if os.path.exists(mix):
        I, tp = _lufs(mix)
        add("Audio: loudness / pico", "PASS" if I and -17 <= I <= -13 and (tp is None or tp <= -1.0) else "WARN", f"{I} LUFS, true peak {tp} dBFS (alvo -16..-14 LUFS, <= -1 dBFS)")
        mus = os.path.join(out_dir, "tmp_audio", "music.wav")
        if os.path.exists(nar) and os.path.exists(mus):
            a, sa = _wav(nar)
            m, sm = _wav(mus)
            n = min(len(a) // 1000, len(m) // 1840)
            va = np.array([np.sqrt(np.mean(a[i * 1000:(i + 1) * 1000] ** 2)) for i in range(0, len(a) // 1000)])
            speech = va > 0.02
            ma = np.array([np.sqrt(np.mean(m[int(i * 1840):int((i + 1) * 1840)] ** 2)) for i in range(n)])
            ms = ma[: min(len(speech), len(ma))][speech[: min(len(speech), len(ma))]]
            vs = va[: len(ms)] if False else va[speech][: len(ms)]
            db = 20 * np.log10(np.mean(vs) / (np.mean(ms) * 0.36 + 1e-9) + 1e-9)
            add("Audio: voz acima da musica (antes do ducking)", "PASS" if db > 12 else "WARN", f"voz ~{db:.0f} dB acima da musica (min 12 dB; ducking adicional aplicado)")
    else:
        add("Audio", "WARN", "audio_mix.wav ausente")
    meta = json.load(open(os.path.join(out_dir, "audio_meta.json"))) if os.path.exists(os.path.join(out_dir, "audio_meta.json")) else {}
    hits = meta.get("sfx_hits", [])
    add("Efeitos: menos e mais", "PASS" if len(hits) / (total / 60) <= 2 else "WARN", f"{len(hits)} efeitos pontuais em {total / 60:.1f} min (modo audio={meta.get('audio', 'cinematic (legado)')})")
    # --- voz
    if os.path.exists(nar):
        a, sa = _wav(nar)
        f0 = vc.f0_median(a, sa)
        add("Voz: grave (senhor sabio)", "PASS" if 0 < f0 <= 125 else "WARN", f"F0 mediano {f0:.0f} Hz (voz masculina grave <= 125 Hz); perfil={meta.get('profile', 'legado: am_michael')}")
        add("Voz: humana e natural", "MANUAL", "requer escuta humana (respiracao/pausas variaveis aplicadas no perfil sage)")
    # --- autenticidade
    kinds = {}
    for s in scenes:
        kinds[s.get("asset_kind", "simulation")] = kinds.get(s.get("asset_kind", "simulation"), 0) + 1
    unl = [s["id"] for s in scenes if s.get("asset_kind", "simulation") != "real" and not s.get("badge") and not s.get("labelled_in_description", True)]
    add("Autenticidade (reconstrucao nao vira foto)", "PASS" if not unl else "WARN", f"tipos por cena: {kinds}; sem rotulo: {unl or 'nenhum'}")
    ad = assets.validate(dossier.get("assets", []))
    add("Imagens reais: fonte/licenca", "PASS" if not ad else "WARN", "; ".join(ad[:3]) or "ok / nenhuma imagem real usada")
    # --- publicacao
    if publication:
        tl = [t.lower() for t in publication.get("titulos", [])]
        add("Publicacao: >=10 titulos / >=5 thumbnails", "PASS" if len(tl) >= 10 and len(publication.get("thumbnails", [])) >= 5 else "WARN", f"{len(tl)} titulos, {len(publication.get('thumbnails', []))} conceitos")
        cb = [t for t in publication.get("titulos", []) if CLICKBAIT.search(t)]
        add("Publicacao: sem clickbait falso", "PASS" if not cb else "WARN", f"suspeitos: {cb or 'nenhum'}")
        body = " ".join(re.sub(r"[^a-z ]", " ", s.get("text", "").lower()) for s in scenes)
        top = publication["titulos"][0].lower()
        key = [w for w in re.findall(r"[a-z]{5,}", top) if w not in ("traveled", "journey")]
        hit = [w for w in key if w in body]
        add("Publicacao: titulo entregue pelo conteudo", "PASS" if key and len(hit) >= max(1, len(key) // 2) else "WARN", f"termos do titulo presentes na narracao: {hit}/{key}")
    return R


def write(R, path):
    json.dump(R, open(path + ".json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    with open(path + ".md", "w", encoding="utf-8") as f:
        f.write("# Verificacao final\n\n| Verificacao | Status | Detalhe |\n|---|---|---|\n")
        for r in R:
            f.write(f"| {r['verificacao']} | **{r['status']}** | {r['detalhe']} |\n")
