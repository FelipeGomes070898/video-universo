#!/usr/bin/env python3
"""Gera, a partir de projects/<slug>/ (scenes.py + project.json + assets/*/meta.json), os entregaveis de producao:
  production_breakdown.md  detalhamento cena a cena (cena, timecode, narracao, visual, fonte, URL, prompt de IA, animacao, motion graphics, texto na tela, camera, som, transicao, duracao)
  licensing_report.md      fonte, URL, licenca, credito e uso de CADA asset (+ fontes pesquisadas e limites)
  timeline.edl             linha do tempo exportavel (CMX 3600, 24 fps) dos cortes de midia
Uso: python tools/make_breakdown.py projects/<slug> [--out pasta]      (so descreve o que existe; nao inventa assets)"""
import glob, importlib.util, json, os, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)


def tc(t, fps=24):
    f = int(round(t * fps))
    return f"{f // (fps * 3600):02d}:{f // (fps * 60) % 60:02d}:{f // fps % 60:02d}:{f % fps:02d}"


def mm(t):
    return f"{int(t // 60)}:{int(t % 60):02d}"


def meta_for(path):
    d = os.path.dirname(path)
    cands = glob.glob(os.path.join(d, "meta.json")) + glob.glob(os.path.join(d, os.path.basename(path) + ".meta.json"))
    return json.load(open(cands[0])) if cands else {}


def cam_desc(m):
    z0, z1 = (m.get("zoom") or [1, 1])[:2]
    (x0, y0), (x1, y1) = m.get("pan") or [[0, 0], [0, 0]]
    parts = []
    if abs(z1 - z0) > 0.02:
        parts.append(f"{'push-in' if z1 > z0 else 'pull-out'} {z0:.2f}x->{z1:.2f}x")
    if abs(x1 - x0) > 0.05 or abs(y1 - y0) > 0.05:
        parts.append(f"pan {'left->right' if x1 > x0 else 'right->left' if x1 < x0 else ''}{' vertical' if abs(y1 - y0) > 0.05 else ''}".strip())
    if m.get("kind") == "video":
        parts.append("camera do proprio video")
    return "; ".join(parts) or "plano fixo"


def main():
    pdir = sys.argv[1].rstrip("/")
    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else os.path.join(pdir, "output")
    os.makedirs(out, exist_ok=True)
    proj = json.load(open(os.path.join(pdir, "project.json")))
    sp = importlib.util.spec_from_file_location("scenes_mod", os.path.join(pdir, "scenes.py"))
    sm = importlib.util.module_from_spec(sp)
    cwd = os.getcwd(); os.chdir(HERE); sp.loader.exec_module(sm); os.chdir(cwd)
    spec = {s["id"]: s for s in sm.SCENES}
    media = proj.get("media", [])
    titles, cards = proj.get("titles", []), proj.get("cards", [])
    dur = proj["briefing"]["duration_seconds"]
    L = [f"# Production breakdown — {sm.TITLE}", "", f"Duração {mm(dur)} · 16:9 · 24 fps · render final 1920x1080 · {len(proj['scenes'])} cenas · {len(media)} itens de mídia", ""]
    for n, s in enumerate(proj["scenes"], 1):
        sc = spec[s["id"]]
        a, b = s["start"], s["end"]
        ms = [m for m in media if a - 0.01 <= m["start"] < b]
        tl = [t for t in titles if a - 0.01 <= t["start"] < b]
        cd = [c for c in cards if a - 0.01 <= c["start"] < b]
        src = [f"{os.path.basename(os.path.dirname(m['path'])) if m['kind']=='image' else os.path.basename(m['path'])} ({m['kind']}, {mm(m['start'])}-{mm(m['end'])})" for m in ms]
        urls = []
        for m in ms:
            mt = meta_for(m["path"])
            if mt.get("url") and mt["url"] not in urls:
                urls.append(mt["url"])
        illus = [m for m in ms if "animation" in (m.get("credit") or "").lower() or "illustration" in (m.get("credit") or "").lower() or "concept" in (m.get("credit") or "").lower()]
        sound = [f"trilha 'score' sintetizada (humor {sc.get('mood', 0.5)})"]
        if sc.get("impact"):
            sound.append("impacto grave na entrada da cena")
        if sc.get("impact_at"):
            sound.append("impacto sincronizado a uma frase")
        if sc.get("riser"):
            sound.append("riser crescente até o impacto")
        if sc.get("music_dip"):
            sound.append("SILÊNCIO dramático (música cai a ~5%) durante a frase marcada")
        if sc.get("sfx"):
            sound.append("SFX: " + ", ".join(str(x[1]) for x in sc["sfx"]))
        L += [f"## SCENE {n} — {s['id']}  ({sc.get('chapter', '')})", "",
              f"**SCENE NUMBER:** {n}", f"**TIMECODE:** {tc(a)} – {tc(b)}  ({mm(a)}–{mm(b)})", f"**DURATION:** {b - a:.1f} s",
              f"**NARRATION:** {sc['text']}", "",
              f"**VISUAL DESCRIPTION:** {len(ms)} planos reais/animação NASA em sequência" + (f"; papel narrativo: {sc.get('role')}" if sc.get('role') else "") + ("; contém ilustração/animação rotulada" if illus else "; material fotográfico/vídeo real"),
              f"**SOURCE FOOTAGE:** " + ("; ".join(src) or "—"), f"**SOURCE URL:** " + (" | ".join(urls) or "—"),
              f"**AI IMAGE PROMPT:** não usado nesta cena (as fontes reais cobrem o visual). Prompt reserva para lacunas: \"photorealistic scientific illustration, {sc.get('chapter', '')}, cinematic lighting, volumetric haze, no text\" (rotular como imagem de IA).",
              f"**ANIMATION PROMPT:** " + ("; ".join(sorted({os.path.basename(m['path']) for m in ms if m['kind'] == 'video'})) or "—") + " (animações/visualizações oficiais NASA, recortadas e esticadas à frase)",
              f"**MOTION GRAPHICS:** " + ("; ".join([f"timeline animada '{c.get('title')}'" for c in cd if c.get('kind') == 'timeline'] + [f"card {c.get('kind')}" for c in cd if c.get('kind') != 'timeline']) or "rótulos tipográficos animados" ) + (" + HUD de distância/tempo-luz" if sc.get("hud") else "") + "; Ken Burns (zoom/pan) em fotos; moldura/fade entre planos",
              f"**ON-SCREEN TEXT:** " + (" | ".join(f"{t['text']}" + (f" ({t['sub']})" if t.get('sub') else "") for t in tl) or "—") + " | créditos por foto no canto inferior direito",
              f"**CAMERA MOVEMENT:** " + "; ".join(sorted({cam_desc(m) for m in ms})),
              f"**SOUND DESIGN:** " + "; ".join(sound) + "; drone grave contínuo; narração dominante (música ~13 dB abaixo, ducking)",
              f"**TRANSITION:** dissolução de {sc.get('xfade', {}).get('dur', 1.7)} s para a próxima cena; fade de {ms[0].get('fade') if ms else '—'} s entre planos", ""]
    open(os.path.join(out, "production_breakdown.md"), "w", encoding="utf-8").write("\n".join(L))
    # licensing
    use, order = {}, []
    for m in media:
        k = m["path"]
        if k not in use:
            use[k] = dict(sec=0.0, scenes=set(), credit=m.get("credit"), kind=m["kind"]); order.append(k)
        use[k]["sec"] += m["end"] - m["start"]
        sc_ = next((s["id"] for s in proj["scenes"] if s["start"] - 0.01 <= m["start"] < s["end"]), "")
        use[k]["scenes"].add(sc_)
    R = [f"# Source and licensing report — {sm.TITLE}", "", "Todo material de mídia vem do acervo da NASA (NASA Image and Video Library e NASA Scientific Visualization Studio). Material da NASA em geral é de domínio público; o SVS/NASA pedem crédito. A NASA não endossa este vídeo. Verifique itens com terceiros antes de reutilizar.", "",
         "| Asset | Tipo | Título | Crédito exigido/usado | Licença | Resolução | Usado em | Segundos | URL de origem |", "|---|---|---|---|---|---|---|---|---|"]
    for k in order:
        mt = meta_for(k); u = use[k]
        res = f"{mt.get('width')}x{mt.get('height')}" if mt.get("width") else ""
        if not res:
            try:
                import cv2
                if u["kind"] == "image":
                    h, w = cv2.imread(k).shape[:2]; res = f"{w}x{h}"
                else:
                    c = cv2.VideoCapture(k); res = f"{int(c.get(3))}x{int(c.get(4))}"
            except Exception:
                res = "?"
        R.append(f"| {mt.get('id') or os.path.basename(k)} | {u['kind']} | {mt.get('title', '')[:60]} | {u['credit'] or mt.get('credit', '')} | {mt.get('license', 'NASA / domínio público (crédito solicitado)')} | {res} | {', '.join(sorted(u['scenes']))} | {u['sec']:.0f} | {mt.get('url', '')} |")
    R += ["", "## Fontes pesquisadas e resultado", "- NASA Image and Video Library (images.nasa.gov): usada (fotos, vídeos).", "- NASA Scientific Visualization Studio (svs.gsfc.nasa.gov): usada (filme da Grand Finale, animações de Encélado, descida do Huygens, imagem do Webb).",
          "- ESA/Webb (esawebb.org): acessível; a imagem do Webb usada vem do SVS/STScI (crédito: NASA, ESA, CSA, STScI e equipe). Licença ESA/Webb: CC BY 4.0 (verificar página do item).",
          "- NASA Earth Observatory: não relevante para este tema.", "- Mixkit: acessível; nenhum vídeo usado (estoque genérico não representaria os fatos; evitado de propósito).",
          "- Pexels e Pixabay: BLOQUEIAM acesso automatizado (HTTP 403); nada usado.", "- Wikimedia Commons: API limita requisições (HTTP 429); nada usado.",
          "- YouTube: nenhum trecho de terceiros usado.", "", "## Limites desta produção",
          "- Imagens por IA: o conector disponível só devolve miniatura (198x112); a imagem completa fica no Canva e NÃO entrou no vídeo.",
          "- Saída em 1920x1080 (render em CPU; 4K não suportado neste ambiente, e a maior parte das fontes tem 720p–1080p).", "- Trilha e SFX são sintetizados proceduralmente (não é orquestra real); voz é TTS (Kokoro).", ""]
    open(os.path.join(out, "licensing_report.md"), "w", encoding="utf-8").write("\n".join(R))
    # EDL
    E = [f"TITLE: {sm.TITLE}", "FCM: NON-DROP FRAME", ""]
    for i, m in enumerate(sorted(media, key=lambda x: x["start"]), 1):
        name = os.path.basename(os.path.dirname(m["path"])) if m["kind"] == "image" else os.path.basename(m["path"])
        v0 = m.get("vstart", 0.0) if m["kind"] == "video" else 0.0
        v1 = v0 + (m["end"] - m["start"]) * (m.get("speed", 1.0) if m["kind"] == "video" else 1.0)
        E += [f"{i:03d}  AX       V     C        {tc(v0)} {tc(v1)} {tc(m['start'])} {tc(m['end'])}", f"* FROM CLIP NAME: {name}", f"* SOURCE: {m['path']}" + (f" (speed {m.get('speed', 1.0):.2f}x)" if m['kind'] == 'video' else " (still: zoom/pan)"), ""]
    open(os.path.join(out, "timeline.edl"), "w", encoding="utf-8").write("\n".join(E))
    print("gerados:", [os.path.join(out, f) for f in ("production_breakdown.md", "licensing_report.md", "timeline.edl")])


if __name__ == "__main__":
    main()
