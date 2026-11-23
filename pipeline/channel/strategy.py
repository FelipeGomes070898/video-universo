"""Relatorio estrategico ANTES de cada producao: responde as 10 perguntas com os dados reais do canal (e so com eles). Cada resposta traz evidencia e
CONFIANCA (alta/media/baixa/insuficiente). Sem dados suficientes o relatorio diz isso e propoe um EXPERIMENTO (nao uma conclusao).
Ciclo: analisar -> oportunidades -> planejar -> roteiro -> produzir -> publicar -> medir (24 h/7 d/28 d) -> melhorar. produce.py init exige um
relatorio recente (analises/estrategia_*.md, <= 14 dias) ou --sem-estrategia."""
import datetime as dt, glob, json, os, re, time
from . import analyze as an

MAX_AGE_DAYS = 14


def _pct(x):
    return "n/d" if x is None else f"{100 * x:.1f}%"


def _title_overlap(a, b):
    A, B = set(an.keywords(a)), set(an.keywords(b))
    return len(A & B) / max(1, len(A | B))


def cannibalization(T):
    out = []
    for i, a in enumerate(T):
        for b in T[i + 1:]:
            try:
                d = abs((dt.datetime.fromisoformat(a["published_at"][:19]) - dt.datetime.fromisoformat(b["published_at"][:19])).days)
            except Exception:
                continue
            if d <= 7 and _title_overlap(a["title"], b["title"]) >= 0.4:
                out.append((a["title"], b["title"], d))
    return out


def build(st, thumb_feats=None, today=None):
    A = an.analyze(st)
    T = A["videos"]
    today = today or dt.date.today()
    last = st.q("SELECT MAX(ts) m FROM channel")[0]["m"]
    ans, n = [], len(T)
    ok_conf = [t for t in T if t["confidence"] in ("media", "alta")]

    def add(q, text, evidence, conf):
        ans.append(dict(pergunta=q, resposta=text, evidencia=evidence, confianca=conf))

    # 1 e 2
    rk = A.get("ranking", {})
    best = rk.get("avg_view_pct", [])[:2]
    worst = sorted([t for t in T if t["avg_view_pct"] is not None], key=lambda t: t["avg_view_pct"])[:2]
    c12 = "media" if len(ok_conf) >= MIN_N_ else ("baixa" if n >= 2 else "insuficiente")
    add("1. O que funcionou nos ultimos videos?",
        "Maior retencao media: " + "; ".join(f"{b[1]} ({b[2]:.1f}%)" for b in best) if best else "sem metricas de retencao no banco",
        dict(ranking_ctr=rk.get("ctr", [])[:2], ranking_retencao_30s=rk.get("retention_30s", [])[:2]), c12)
    low30 = [t for t in T if t["retention_30s"] is not None and t["retention_30s"] < 0.5]
    zero_eng = [t for t in T if t["views"] and t["subs_net"] == 0 and (t["likes_per_1k"] or 0) == 0]
    add("2. O que nao funcionou?",
        ("; ".join(f"queda forte nos 30 s iniciais em '{t['title'][:40]}' (retem {_pct(t['retention_30s'])})" for t in low30) or "sem quedas iniciais medidas")
        + ("; " + f"{len(zero_eng)} video(s) sem inscritos nem curtidas" if zero_eng else ""),
        dict(menores_retencoes=[(w["title"][:40], w["avg_view_pct"]) for w in worst]), c12)
    # 3 assuntos
    temas = sorted([kv for kv in A.get("temas", {}).items() if kv[1]["n"] >= 2], key=lambda kv: -(kv[1]["subs_per_1k"] or 0))[:5]     # so assuntos que se repetem em >= 2 videos
    solid = [k for k, v in temas if v["n"] >= an.MIN_N]
    add("3. Quais assuntos demonstraram maior potencial?",
        (f"temas com n>={an.MIN_N}: {', '.join(solid)}" if solid else "NENHUM tema tem amostra suficiente (n>=%d videos)%s" % (an.MIN_N, (". Recorrentes (hipoteses): " + ", ".join(k for k, _ in temas[:3])) if temas else ": ainda nao ha assunto que se repita em 2 videos; a escolha do tema e do usuario, sem base de dados.")),
        dict(temas=temas), "media" if solid else "insuficiente")
    # 4 erros
    can = cannibalization(T)
    errs = [f"canibalizacao: '{a[:35]}' x '{b[:35]}' publicados com {d} dia(s) de diferenca" for a, b, d in can]
    errs += [f"abertura fraca em '{t['title'][:35]}'" for t in low30]
    miss = A.get("metricas_indisponiveis")
    if miss:
        errs.append(f"metricas indisponiveis na API (nao analisar como se existissem): {miss}")
    add("4. Quais erros devem ser evitados?", "; ".join(errs) or "nenhum erro identificavel nos dados atuais", dict(canibalizacao=can), "baixa" if errs else "insuficiente")
    # 5 introducao
    r30 = [t["retention_30s"] for t in T if t["retention_30s"] is not None]
    avg30 = sum(r30) / len(r30) if r30 else None
    add("5. Como melhorar a introducao?",
        (f"retencao media aos 30 s: {_pct(avg30)}. " if avg30 is not None else "retencao aos 30 s ainda indisponivel (esperar ate ~2 dias apos publicar). ")
        + "Regra para o proximo video: primeiro evento visual real (foto/video/mapa) em ate 5 s, promessa concreta em ate 15 s, nenhuma explicacao de contexto antes da primeira pergunta; medir de novo aos 30 s.",
        dict(retention_30s={t["title"][:30]: t["retention_30s"] for t in T}), "baixa" if r30 else "insuficiente")
    # 6 narrativa
    add("6. Qual abordagem narrativa pode aumentar a retencao?",
        "Estrutura pergunta -> promessa -> descoberta -> nova pergunta (mapa de curiosidade), com 'ponto de virada' a cada ~60-75 s; trechos de explicacao no maximo 45 s sem evento visual. "
        "Validar comparando a curva de retencao por capitulo contra o roteiro (retention.map_drops).",
        dict(base="curiosity_chain.json + lint de 30 s do build"), "baixa")
    # 7 duracao
    b = {k: v for k, v in A.get("duracao_vs_retencao_media", {}).items() if v["n"] >= 2}
    if b:
        kbest = max(b, key=lambda k: b[k]["mean"])
        txt = f"faixa com maior retencao media ate agora: {kbest} ({b[kbest]['mean']:.1f}% , n={b[kbest]['n']}). Com poucos videos por faixa isto e apenas uma indicacao."
    else:
        txt = "sem 2 videos por faixa de duracao: nao ha base para otimizar. Experimento: alternar 8-12 min e 12-16 min e comparar retencao media (avg_view_pct) e tempo de exibicao."
    add("7. Qual duracao e adequada ao tema e ao historico?", txt, dict(duracao_vs_retencao=A.get("duracao_vs_retencao_media")), "baixa" if b else "insuficiente")
    # 8 visual/thumbnail
    withc = [t for t in T if t["ctr"] is not None and (t["impressions"] or 0) >= an.MIN_IMPR]
    if len(withc) >= 2:
        hi, lo = max(withc, key=lambda t: t["ctr"]), min(withc, key=lambda t: t["ctr"])
        overlap = hi["ctr_ci"][0] > lo["ctr_ci"][1]
        txt = f"maior CTR: '{hi['title'][:35]}' ({_pct(hi['ctr'])}) x menor: '{lo['title'][:35]}' ({_pct(lo['ctr'])}); intervalos de confianca " + ("SEPARADOS (diferenca provavel)" if overlap else "SOBREPOSTOS (nao ha diferenca comprovada)")
        conf = "media" if overlap else "baixa"
    else:
        txt = (f"menos de 2 videos com >= {an.MIN_IMPR} impressoes: nao da para dizer que uma miniatura e melhor. Plano: teste A/B do Studio com 2-3 miniaturas mudando UMA variavel por vez "
               "(texto, cor ou elemento principal), mesma historia/titulo, ate ~1000 impressoes por variante.")
        conf = "insuficiente"
    if thumb_feats:
        txt += " Caracteristicas visuais (descritivas): " + "; ".join(f"{k[:11]}: {v}" for k, v in list(thumb_feats.items())[:3])
    add("8. Que estilo visual e de thumbnail merece ser testado?", txt, dict(ctr={t["title"][:30]: (t["ctr"], t["impressions"]) for t in T}), conf)
    # 9 tempo de exibicao
    av = [(t["title"][:30], t["avg_view_s"], t["avg_view_pct"]) for t in T if t["avg_view_s"] is not None]
    add("9. Quais mudancas podem aumentar o tempo de exibicao?",
        "Cortar/encurtar os trechos onde a curva cai (ver quedas por cena em 'channel.py retention'); evitar introducao com contexto; manter evento visual a cada <= 30 s; capitulos com promessa clara. "
        + (f"Duracao media atual: {', '.join(f'{a[0]}: {a[1]:.0f}s (' + ('n/d' if a[2] is None else f'{a[2]:.0f}%') + ')' for a in av[:3])}." if av else ""),
        dict(avg_view=av), "baixa" if av else "insuficiente")
    # 10 inscritos
    sp = sorted([t for t in T if t["subs_per_1k"] is not None], key=lambda t: -t["subs_per_1k"])
    tr = list(A.get("trafego", {}).items())[:3]
    add("10. Quais oportunidades existem para conquistar novos inscritos?",
        (f"inscritos/1000 views: {', '.join(f'{t['title'][:30]} {t['subs_per_1k']:.1f}' for t in sp[:2])}. " if sp else "sem dados de inscritos por video. ")
        + (f"fontes de trafego principais: {', '.join(f'{k} ({v['views']:.0f} views)' for k, v in tr)}. " if tr else "")
        + "Acao: pedir a inscricao no PICO de interesse (apos a maior descoberta), nao so no fim; fixar comentario com pergunta.",
        dict(trafego=dict(tr), evergreen=A.get("evergreen")), "baixa" if sp else "insuficiente")

    plan = dict(
        tema="decisao do usuario com base nos 'temas' acima; evitar repetir tema/titulo de video publicado ha <= 7 dias",
        duracao="faixa conforme a pergunta 7 (experimento se insuficiente)",
        introducao="primeiro evento visual real <= 5 s; promessa <= 15 s; sem contexto antes da 1a pergunta",
        titulo="especifico e concreto (numero/pergunta/objeto), sem promessa falsa; 1 variavel por teste", thumbnail="teste A/B de 2-3 variantes, 1 variavel por vez; texto <= 3 palavras; completar o titulo (nao repetir)",
        medicao="registrar no banco (channel.py register) e medir em 24 h (dias 0-1), 7 dias e 28 dias; comparar com o video anterior por retencao 30 s, avg_view_pct, CTR (com IC) e inscritos/1000 views")
    rep = dict(gerado_em=today.isoformat(), ultima_sincronizacao=dt.datetime.fromtimestamp(last).isoformat() if last else None, n_videos=n,
               n_com_amostra_suficiente=len(ok_conf), limites=A.get("limites", []), respostas=ans, estrategia_proximo_video=plan)
    return rep


MIN_N_ = an.MIN_N


def to_markdown(rep):
    L = [f"# Estrategia para o proximo video — {rep['gerado_em']}", "",
         f"Dados: {rep['n_videos']} video(s), {rep['n_com_amostra_suficiente']} com amostra suficiente. Ultima sincronizacao com o YouTube: {rep['ultima_sincronizacao'] or 'NUNCA (so dados manuais/semente)'}.", ""]
    for l in rep["limites"]:
        L.append(f"- Limite: {l}")
    L.append("")
    for a in rep["respostas"]:
        L += [f"## {a['pergunta']}  _(confianca: {a['confianca']})_", "", a["resposta"], ""]
    L += ["## Estrategia especifica para o proximo video", ""] + [f"- **{k}**: {v}" for k, v in rep["estrategia_proximo_video"].items()] + [""]
    L.append("_Nada aqui e conclusao estatistica quando a confianca for baixa/insuficiente: sao hipoteses a testar._")
    return "\n".join(L) + "\n"


def write(st, folder, **kw):
    rep = build(st, **kw)
    os.makedirs(folder, exist_ok=True)
    p = os.path.join(folder, f"estrategia_{rep['gerado_em']}.md")
    open(p, "w", encoding="utf-8").write(to_markdown(rep))
    json.dump(rep, open(p[:-3] + ".json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    st.save_analysis("estrategia", rep)
    return p


def latest_report(folder):
    fs = sorted(glob.glob(os.path.join(folder, "estrategia_*.md")))
    return fs[-1] if fs else None


def fresh(folder, today=None):
    """(ok, caminho, idade_dias) — usado por produce.py init como porta antes de escrever roteiro."""
    p = latest_report(folder)
    if not p:
        return False, None, None
    d = dt.date.fromisoformat(re.search(r"estrategia_(\d{4}-\d{2}-\d{2})", p).group(1))
    age = ((today or dt.date.today()) - d).days
    return age <= MAX_AGE_DAYS, p, age
