"""DIRETOR VISUAL: intencao da cena -> melhor tipo de visual, com rotulo de autenticidade e SISTEMA DE SUBSTITUICAO."""
INTENT = {  # intencao -> cadeia de preferencia
    "mostrar_pessoa_lugar_objeto_real": ["real_photo", "licensed_photo", "illustration", "reconstruction"],
    "localizacao_movimento_territorio": ["map", "diagram", "card"],
    "evidencia": ["document", "real_photo", "card"],
    "numeros_evolucao": ["chart", "card"],
    "cronologia": ["timeline", "card"],
    "causa_consequencia": ["card", "diagram", "timeline"],
    "comparacao": ["compare", "chart"],
    "verificar_aprendizado": ["quiz", "card"],
    "cena_sem_registro": ["reconstruction", "illustration", "animation", "ai"],
    "fenomeno_inobservavel": ["simulation", "animation", "diagram"],
}
LABEL = {"real_photo": "real", "licensed_photo": "real", "document": "real", "map": "illustration", "chart": "illustration", "timeline": "illustration",
         "card": "illustration", "compare": "illustration", "quiz": "illustration", "diagram": "illustration", "illustration": "illustration",
         "reconstruction": "reconstruction", "animation": "simulation", "simulation": "simulation", "ai": "ai"}


def choose(intent, available):
    """available: set de tipos que o operador tem. Retorna (tipo, rotulo, tentativas)."""
    tried = []
    for t in INTENT.get(intent, ["card"]):
        tried.append(t)
        if t in available:
            return t, LABEL[t], tried
    return "card", "illustration", tried + ["card(fallback)"]
