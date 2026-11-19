"""FORMAT ANALYZER: escolhe formato, ritmo, politica de audio e caixa de ferramentas visuais. Heuristica explicita e extensivel."""
import re

FORMATS = {
    "documentario_historico": dict(rx=r"guerra|batalha|imp[eé]rio|hist[oó]ri|s[eé]culo|revolu|war|battle|empire|history|century|ancient",
                                   pace="controlado", music="minimalista", sfx="minimos", tools=["real_photo", "map", "document", "timeline", "card", "reconstruction"], voice="sage"),
    "aula_visual": dict(rx=r"ensin|aula|equa[cç]|conceito|exerc[ií]cio|teach|lesson|learn|how to|equation|formula|math",
                        pace="estavel", music="ambiente baixa", sfx="minimos", tools=["card", "chart", "diagram", "quiz", "timeline", "compare"], voice="sage"),
    "explicativo_tecnico": dict(rx=r"como funciona|funciona|motor|m[aá]quina|sistema|how does|works|engine|mechanism|circuit",
                                pace="estavel", music="ambiente baixa", sfx="minimos", tools=["diagram", "animation", "card", "compare"], voice="sage"),
    "cientifico_contemplativo": dict(rx=r"espa[cç]o|planeta|gal[aá]xia|universo|astronom|cosmos|natureza|oceano|space|universe|galaxy|planet|ocean",
                                     pace="lento", music="ambiente/drone", sfx="minimos", tools=["simulation", "chart", "card", "timeline"], voice="sage"),
    "investigativo_misterio": dict(rx=r"mist[eé]rio|desaparec|conspira|enigma|investiga|mystery|disappear|secret|unsolved",
                                   pace="tenso e controlado", music="drone discreto", sfx="minimos", tools=["real_photo", "document", "map", "timeline", "card"], voice="sage"),
    "storytelling_empresa": dict(rx=r"empresa|fundador|startup|marca|neg[oó]cio|company|founder|brand|business",
                                 pace="medio", music="minimalista", sfx="minimos", tools=["real_photo", "chart", "timeline", "card"], voice="sage"),
    "anuncio": dict(rx=r"an[uú]ncio|campanha|promo|produto|comprar|advert|campaign|product|buy", pace="rapido", music="marcante", sfx="moderados",
                    tools=["real_photo", "card", "animation"], voice="narrator"),
    "ficcao_cinematografica": dict(rx=r"conto|fic[cç][aã]o|personagem|trailer|curta|short film|fiction|character|story of", pace="variavel", music="narrativa", sfx="moderados",
                                   tools=["illustration", "ai", "animation"], voice="sage"),
    "curiosidades": dict(rx=r"curiosidade|voc[eê] sabia|fatos|facts|did you know|trivia", pace="medio", music="leve", sfx="minimos", tools=["card", "chart", "compare", "quiz"], voice="narrator"),
}
FACTUAL = r"hist[oó]ri|guerra|batalha|ci[eê]ncia|cient[ií]fic|politic|pol[ií]tic|geograf|war|battle|science|history|space|universe|study|research|medical|saude|health"


def analyze(brief):
    text = " ".join(str(brief.get(k, "")) for k in ("title", "tema", "topic", "objective", "objetivo")).lower()
    scores = {n: len(re.findall(f["rx"], text)) for n, f in FORMATS.items()}
    name = max(scores, key=scores.get) if max(scores.values()) > 0 else "explicativo_tecnico"
    f = FORMATS[name]
    plat = str(brief.get("platform", brief.get("plataforma", ""))).lower()
    vertical = plat in ("tiktok", "reels", "shorts", "short", "reel") or brief.get("format") == "9:16"
    dur = brief.get("duration_seconds") or (60 if vertical else 600)
    return dict(formato=name + ("_vertical" if vertical else ""), aspecto="9:16" if vertical else "16:9", duracao_alvo_s=dur,
                ritmo=f["pace"], musica=f["music"], efeitos_sonoros=f["sfx"], caixa_de_ferramentas=f["tools"], perfil_de_voz=f["voice"],
                modo_factual=bool(re.search(FACTUAL, text)) or bool(brief.get("factual")),
                pontuacoes={k: v for k, v in scores.items() if v}, metodo="HEURISTICA por regras (extensivel em FORMATS); nao e LLM",
                justificativa=f"Palavras do briefing pontuaram '{name}' ({scores[name]}). Combine/crie formatos editando FORMATS quando o tema pedir.")
