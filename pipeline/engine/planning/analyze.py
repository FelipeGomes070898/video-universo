"""FORMAT ANALYZER: escolhe formato/ritmo/politica de audio por regras (heuristica, sem pesquisa externa)."""
import re

RULES = [  # (formato, palavras-chave, ritmo, musica, sfx)
    ("documentario_historico", r"guerra|batalha|imp[eé]rio|hist[oó]ri|s[eé]culo|revolu", "controlado", "minimalista", "minimos"),
    ("aula_visual", r"ensin|aula|equa[cç]|como funciona|explique|tutorial|conceito", "estavel, visual didatico", "ambiente baixa", "minimos"),
    ("anuncio", r"produto|an[uú]ncio|campanha|marca|promo", "rapido", "marcante", "moderados"),
    ("ficcao_cinematografica", r"conto|fic[cç][aã]o|personagem|trailer|curta", "variavel", "narrativa", "moderados"),
    ("contemplativo_cientifico", r"espa[cç]o|planeta|gal[aá]xia|universo|astronom|cosmos|natureza|oceano", "lento, contemplativo", "ambiente/drone", "minimos"),
]


def analyze_format(brief):
    text = " ".join(str(brief.get(k, "")) for k in ("title", "topic", "objective")).lower()
    best, score = None, 0
    for name, rx, pace, music, sfx in RULES:
        s = len(re.findall(rx, text))
        if s > score:
            best, score = (name, pace, music, sfx), s
    name, pace, music, sfx = best or ("documentario_curto", "controlado", "ambiente baixa", "minimos")
    vertical = brief.get("format") == "9:16" or brief.get("platform", "").lower() in ("tiktok", "reels", "shorts")
    return {
        "formato_escolhido": name + ("_vertical" if vertical else ""),
        "ritmo": pace, "musica": music, "efeitos_sonoros": sfx,
        "justificativa": f"Palavras-chave do briefing pontuaram {score} para '{name}'. Regra-base: menos é mais em audio e efeitos.",
        "metodo": "HEURISTICA POR REGRAS (nao e pesquisa de mercado nem LLM)",
    }
