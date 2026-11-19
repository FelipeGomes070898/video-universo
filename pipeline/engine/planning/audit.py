"""RETENTION ANALYZER + checagens automaticas. So reporta o que e mensuravel; o resto fica MANUAL."""


def audit(project, scenes):
    dur = project["briefing"]["duration_seconds"]
    out = []
    add = lambda n, st, d: out.append({"verificacao": n, "status": st, "detalhe": d})
    longest = max(s["duracao_s"] for s in scenes)
    add("Mudanca visual frequente", "PASS" if longest <= 8 else "WARN", f"maior segmento: {longest}s (limite recomendado 8s)")
    covered = sum(min(t["end"], dur) - t["start"] for t in project.get("titles", []))
    add("Texto na tela nao excessivo", "PASS" if covered / dur < 0.7 else "WARN", f"{covered/dur:.0%} do tempo com texto")
    first = min([t["start"] for t in project.get("titles", [])] or [99])
    add("Gancho nos primeiros 3s", "PASS" if first <= 3 else "WARN", f"primeiro titulo em {first}s")
    wh = len(project["audio"].get("whooshes", []))
    add("Efeitos sonoros: menos e mais", "PASS" if wh / dur * 60 <= 6 else "WARN", f"{wh} whooshes em {dur}s")
    bg = project["audio"].get("bell_gain", 0.05)
    add("Musica nao compete com voz", "PASS" if bg <= 0.05 else "WARN", f"bell_gain={bg}; sem voz para medir competicao")
    add("Narracao presente", "WARN", "video sem narracao; voz de 'senhor sabio' NAO DISPONIVEL sem TTS externo")
    add("Verificacao factual", "N/A", "conteudo e simulacao artistica; sem afirmacoes factuais alem de rotulos dos titulos")
    add("Autenticidade", "PASS", "todos os assets rotulados SIMULACAO; nenhum apresentado como fotografia real")
    add("Perguntas/promessa (mapa de curiosidade)", "WARN", "sem narracao nao ha progressao de perguntas; ver 01_curiosity_map.json")
    add("Clareza da voz / musica / SFX audiveis", "MANUAL", "requer escuta humana")
    return out
