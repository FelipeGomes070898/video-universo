"""DIRETOR DE PUBLICACAO: pontua titulos, monta descricao (capitulos+fontes), tags/hashtags, mapa de palavras e conceitos de thumbnail."""
import re

POWER = re.compile(r"\b(how|why|what|truth|never|first|last|secret|hidden|wall|end|edge|journey|every|ever)\b", re.I)
CLICKBAIT = re.compile(r"\b(you won'?t believe|shocking|insane|destroyed|gone wrong|exposed)\b", re.I)


def score_title(t):
    s, n = 0, []
    L = len(t)
    if 40 <= L <= 70: s += 2; n.append("tamanho ideal")
    elif L < 40: s += 1
    else: n.append("longo (corta no celular)")
    if re.search(r"\d", t): s += 1; n.append("especifico (numero)")
    if POWER.search(t): s += 2; n.append("curiosidade")
    if "?" in t or ":" in t or "—" in t: s += 1; n.append("estrutura")
    if CLICKBAIT.search(t): s -= 3; n.append("CLICKBAIT")
    return s, n


def rank_titles(titles):
    return sorted(({"titulo": t, "pontos": score_title(t)[0], "notas": score_title(t)[1]} for t in titles), key=lambda x: -x["pontos"])


def thumb_concepts(core, question, mystery, scale):
    """5 conceitos que COMPLETAM o titulo (titulo = pergunta; thumb = curiosidade; video = resposta)."""
    return [
        dict(ideia=f"Escala: {core} minusculo diante de {scale}", elemento_principal=scale, expressao="n/a (sem pessoa)", composicao="regra dos tercos, vazio escuro para texto",
             contraste="fundo escuro + 1 ponto quente", texto="3 palavras max", curiosidade=mystery, relacao_titulo="titulo promete o destino; imagem mostra o tamanho do desafio"),
        dict(ideia=f"Pergunta visual: onde esta a resposta? ({question})", elemento_principal="circulo/seta num detalhe quase invisivel", composicao="detalhe pequeno em campo vasto",
             contraste="alto", texto="a propria pergunta, curta", curiosidade="o espectador quer achar o detalhe", relacao_titulo="titulo afirma; imagem desafia"),
        dict(ideia=f"Ponto de virada: antes/depois de {core}", elemento_principal="divisao diagonal", composicao="dois lados com cores opostas", contraste="quente x frio", texto="ANTES/DEPOIS ou numero",
             curiosidade="o que mudou?", relacao_titulo="mostra a consequencia que o titulo sugere"),
        dict(ideia=f"Objeto-simbolo isolado de {core}", elemento_principal="objeto unico, close dramatico", composicao="centro + halo de luz", contraste="silhueta", texto="nenhum ou 1 palavra",
             curiosidade="por que isso importa?", relacao_titulo="complementa sem repetir"),
        dict(ideia=f"Personagem/observador olhando para {scale}", elemento_principal="silhueta de costas", expressao="contemplativa", composicao="figura pequena a esquerda, enorme a direita",
             contraste="contra-luz", texto="2-3 palavras", curiosidade="o que ele ve?", relacao_titulo="transforma o titulo em cena"),
    ]


def build(pub_in, scenes, proj):
    """pub_in: dict do operador (titulos, keywords_main, ... ) -> pacote completo."""
    ch = [(s["start"], s.get("chapter")) for s in scenes if s.get("chapter")]
    chapters = "\n".join(f"{int(t // 60)}:{int(t % 60):02d} {c}" for t, c in ch)
    sources = pub_in.get("fontes", [])
    desc = pub_in["descricao_abertura"] + ("\n\n⏱ CHAPTERS\n" + chapters if chapters else "") + ("\n\nSOURCES\n" + "\n".join(sources) if sources else "")
    desc += "\n\nℹ️ " + pub_in.get("aviso_autenticidade", "")
    kw = pub_in["palavra_principal"]
    return dict(titulos=[r["titulo"] for r in rank_titles(pub_in["titulos"])], ranking=rank_titles(pub_in["titulos"]), thumbnails=pub_in.get("thumbnails") or thumb_concepts(**pub_in["thumb_seed"]),
                descricao=desc, tags=pub_in["tags"], hashtags=pub_in["hashtags"][:5],
                mapa_palavras=dict(principal=kw, secundarias=pub_in.get("secundarias", []), relacionados=pub_in.get("relacionados", []), perguntas=pub_in.get("perguntas", []),
                                   intencoes=pub_in.get("intencoes", []), entidades=pub_in.get("entidades", []), sinonimos=pub_in.get("sinonimos", []), subtemas=pub_in.get("subtemas", [])),
                comentario_fixado=pub_in["comentario_fixado"], capitulos=chapters)
