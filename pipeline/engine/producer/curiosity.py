"""MAPA DE CURIOSIDADE: PERGUNTA -> PROMESSA -> DESCOBERTA -> NOVA PERGUNTA -> EXPLICACAO -> CONSEQUENCIA -> NOVA DESCOBERTA.
Valida que as perguntas abrem e fecham 'loops' ao longo do tempo (retencao por progressao real, nao por esconder informacao)."""


def validate(chain, scene_times, total_s, max_gap=75.0):
    """chain: [{pergunta, promessa_cena, resposta_cena, nova_pergunta?}] ; scene_times: {cena: (ini, fim)}. -> (loops, avisos)"""
    loops, warn = [], []
    for c in chain:
        a, b = scene_times.get(c["promessa_cena"]), scene_times.get(c["resposta_cena"])
        if not a or not b:
            warn.append(f"pergunta '{c['pergunta'][:40]}' referencia cena inexistente")
            continue
        if b[0] < a[0]:
            warn.append(f"resposta antes da pergunta: '{c['pergunta'][:40]}'")
        loops.append((a[0], b[0]))
    # tempo sem nenhum loop aberto
    t, worst = 0.0, 0.0
    for s in sorted(set(int(x) for x in range(0, int(total_s), 5))):
        if not any(a <= s <= b for a, b in loops):
            if s - t > worst:
                worst = s - t
        else:
            t = s
    if worst > max_gap:
        warn.append(f"ate {worst:.0f}s seguidos sem pergunta aberta (limite {max_gap:.0f}s)")
    return loops, warn
