"""PESQUISA FACTUAL: esquema do dossie + gerador de tarefas de pesquisa + validacao de fontes.

O codigo NAO pesquisa sozinho (sem acesso a web dentro do motor): ele gera as tarefas/consultas, o operador (IA com WebSearch/fontes)
preenche dossier.json e o QC bloqueia/avisa quando algo factual nao tem fonte ou status.
"""
import json

STATUS = ["confirmado", "consenso", "interpretacao", "hipotese", "controversia", "incerto", "nao_verificado"]
QUESTIONS = ["por que aconteceu?", "como aconteceu?", "como comecou?", "como terminou?", "quem fez?", "qual foi a causa?", "qual foi a consequencia?",
             "o que aconteceria se...?", "qual foi o maior erro?", "o que ninguem percebeu?", "qual e a verdade (e o mito)?", "o que mudou depois?",
             "como funcionava?", "qual era a estrategia?", "qual foi o ponto de virada?", "o que veio antes?", "o que veio depois?"]


def tasks(brief, formato):
    topic = brief.get("tema") or brief.get("topic") or brief.get("title")
    q = [f"{topic}: {x}" for x in QUESTIONS]
    return dict(tema=topic, modo_factual=formato["modo_factual"],
                consultas_busca=[topic, f"{topic} explained", f"{topic} timeline", f"{topic} myths misconceptions", f"{topic} primary sources", f"{topic} what people ask"],
                perguntas_base=q, perguntas_latentes=["que detalhe pouco conhecido muda a interpretacao?", "que consequencia inesperada existe?", "que personagem foi esquecido?",
                                                      "que pequeno evento causou grande efeito?", "que pergunta surge naturalmente no meio da explicacao?"],
                imagens_reais_necessarias="listar em dossier.assets_reais (fonte+licenca) antes de gerar qualquer imagem por IA",
                esquema_fato=dict(id="F01", afirmacao="...", status="|".join(STATUS), fonte="titulo/autor", url="...", data_acesso="AAAA-MM-DD", cenas=["S01"]))


def validate(dossier, factual=True):
    """-> lista de problemas (vazia = ok)."""
    bad = []
    for f in dossier.get("fatos", []):
        if f.get("status") not in STATUS:
            bad.append(f"{f.get('id')}: status invalido")
        if factual and f.get("status") in ("confirmado", "consenso") and not (f.get("fonte") and f.get("url")):
            bad.append(f"{f.get('id')}: marcado '{f.get('status')}' sem fonte/url")
    return bad


def summary(dossier):
    c = {}
    for f in dossier.get("fatos", []):
        c[f.get("status")] = c.get(f.get("status"), 0) + 1
    return c
