"""PUBLICACAO: rascunhos por modelo, derivados do briefing/titulos. Sem dados de busca reais (NAO DISPONIVEL offline)."""


def _mmss(t):
    return f"{int(t)//60}:{int(t)%60:02d}"


def package(project):
    b = project["briefing"]
    t, topic = b["title"], b["topic"]
    kw = b.get("keywords", [])
    main = kw[0] if kw else t
    titles = [t, f"{main.capitalize()}: uma jornada em 3D", f"{main.capitalize()} como você nunca viu", f"Uma viagem de 20 segundos: {main}",
              f"Simulação 3D: {main}", f"{main.capitalize()} em movimento (cinematográfico)", f"Você já imaginou voar sobre isto? {main}",
              f"{main.capitalize()} - curta contemplativo", f"A beleza de: {main}", f"{t} (simulação)"]
    chapters = " · ".join(f"{_mmss(x['start'])} {x['text'].title()}" for x in project.get("titles", []))
    return {
        "aviso": "RASCUNHO por modelos; sem pesquisa de palavras-chave real (NAO DISPONIVEL).",
        "titulos_opcoes": titles,
        "thumbnail_conceitos": [{"ideia": i, "relacao_com_titulo": "completa o titulo com um elemento de curiosidade"} for i in
                                 [f"Quadro mais impactante do video ({main}) com contraste alto", "Close do elemento principal com luz forte",
                                  "Escala: elemento pequeno diante de algo enorme", "Antes/depois da luz mudando", "Texto curto de 2 palavras sobre cena limpa"]],
        "descricao": f"{topic}. Simulação 3D procedural (não são imagens reais). Capítulos: {chapters}.",
        "tags": kw, "hashtags": ["#" + k.replace(" ", "") for k in kw[:3]],
        "mapa_palavras": {"principal": main, "secundarias": kw[1:], "perguntas": [], "entidades": []},
        "comentario_fixado": "Qual cena foi a sua favorita?",
    }
