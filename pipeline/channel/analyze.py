"""Analise do desempenho. REGRAS: nunca julga so por visualizacoes (considera retencao, tempo de exibicao, CTR com intervalo de confianca, inscritos por
1000 views, contexto/idade do video); amostra pequena => 'insuficiente'/'baixa confianca', nunca conclusao. Metrica ausente na API => fica de fora."""
import math, re
from collections import defaultdict

MIN_IMPR, MIN_VIEWS, MIN_N = 1000, 100, 3       # limiares de confianca (impressoes, views, videos por grupo)
STOP = set("the a an of to in on and or for with is are was were how why what when who from at by as it its this that you your we our i if be do did does into out up".split())


def wilson(k, n, z=1.96):
    if not n:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def confidence(views, impressions):
    if impressions is not None and impressions >= MIN_IMPR:
        return "media" if views >= MIN_VIEWS else "baixa"
    return "baixa" if (views or 0) >= MIN_VIEWS else "insuficiente"


def interp(rows, x, key="watch_ratio"):
    pts = sorted((r["ratio"], r[key]) for r in rows if r.get(key) is not None)
    if not pts:
        return None
    if x <= pts[0][0]:
        return pts[0][1]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x0 <= x <= x1:
            return y0 + (y1 - y0) * (x - x0) / max(x1 - x0, 1e-9)
    return pts[-1][1]


def drops(rows, duration_s, top=5, min_gap=0.04):
    """maiores quedas da curva de retencao (audienceWatchRatio): lista de dict(sec, ratio, delta, from, to), sem repetir regioes proximas."""
    pts = sorted((r["ratio"], r["watch_ratio"]) for r in rows if r.get("watch_ratio") is not None)
    if len(pts) < 5:
        return []
    ds = []
    for i in range(1, len(pts)):
        j = max(0, i - 3)                              # janela de ~3 pontos (3% do video) para suavizar
        ds.append((pts[i][1] - pts[j][1], pts[i][0], pts[j][1], pts[i][1]))
    out = []
    for d, x, a, b in sorted(ds):
        if d >= -0.02:
            break
        if all(abs(x - o["ratio"]) >= min_gap for o in out):
            out.append(dict(ratio=x, sec=round(x * duration_s, 1), delta=round(d, 3), start=round(a, 3), end=round(b, 3)))
        if len(out) >= top:
            break
    return out


def title_features(t):
    w = re.findall(r"[A-Za-z0-9']+", t)
    return dict(len_chars=len(t), n_words=len(w), has_number=bool(re.search(r"\d", t)), is_question="?" in t, has_dash_or_colon=bool(re.search(r"[—:–-]", t)),
                caps_words=sum(1 for x in w if len(x) > 2 and x.isupper()))


def keywords(t):
    return [x for x in re.findall(r"[a-z]{3,}", t.lower()) if x not in STOP]


def video_table(st, today_ts=None):
    rows = []
    for v in st.q("SELECT * FROM videos ORDER BY published_at"):
        m = st.latest(v["video_id"], "lifetime")
        pub = st.latest(v["video_id"], "public")
        views = m.get("views", pub.get("views"))
        if views is None:
            continue
        impr, ctr = m.get("impressions"), m.get("ctr")
        ret = st.latest_rows("retention", v["video_id"])
        dur = v["duration_s"] or 0
        r30 = interp(ret, 30 / dur) if ret and dur else None
        tr = st.latest_rows("traffic", v["video_id"])
        top_tr = max(tr, key=lambda r: r["views"] or 0)["source"] if tr else None
        rows.append(dict(
            video_id=v["video_id"], title=v["title"], published_at=v["published_at"], duration_s=dur, views=views, impressions=impr, ctr=ctr,
            ctr_ci=(wilson(round(ctr * impr), impr) if (ctr is not None and impr) else None),
            avg_view_s=m.get("averageViewDuration"), avg_view_pct=m.get("averageViewPercentage"), minutes=m.get("estimatedMinutesWatched"),
            subs_net=(m.get("subscribersGained", 0) - m.get("subscribersLost", 0)) if "subscribersGained" in m else None,
            subs_per_1k=(1000 * (m.get("subscribersGained", 0) - m.get("subscribersLost", 0)) / views) if (views and "subscribersGained" in m) else None,
            likes_per_1k=(1000 * m["likes"] / views) if (views and "likes" in m) else None, retention_30s=r30, late_share=m.get("views_after_day28_share"),
            days_with_data=m.get("days_with_data"), d1=st.latest(v["video_id"], "d1").get("views"), d7=st.latest(v["video_id"], "d7").get("views"),
            d28=st.latest(v["video_id"], "d28").get("views"), top_traffic=top_tr, confidence=confidence(views, impr), source=v.get("source")))
    return rows


def _grp(rows, keyfn, metric):
    g = defaultdict(list)
    for r in rows:
        k = keyfn(r)
        if k is not None and r.get(metric) is not None:
            g[k].append(r[metric])
    return {k: dict(n=len(v), mean=sum(v) / len(v)) for k, v in g.items()}


def analyze(st):
    T = video_table(st)
    A = dict(n_videos=len(T), videos=T, notas=[])
    if not T:
        A["notas"].append("sem videos com metricas: rode 'channel.py sync' (ou 'seed-manual')")
        return A
    A["ranking"] = {m: [(r["video_id"], r["title"][:50], round(r[m], 4)) for r in sorted([x for x in T if x.get(m) is not None], key=lambda x: -x[m])[:5]]
                    for m in ("avg_view_pct", "retention_30s", "ctr", "subs_per_1k", "views")}
    # duracao x retencao
    bucket = lambda r: ("<8 min" if r["duration_s"] < 480 else "8-12 min" if r["duration_s"] < 720 else "12-16 min" if r["duration_s"] < 960 else ">=16 min") if r["duration_s"] else None
    A["duracao_vs_retencao_media"] = _grp(T, bucket, "avg_view_pct")
    # titulos
    tf = {r["video_id"]: title_features(r["title"]) for r in T}
    A["titulos"] = {f: _grp(T, lambda r, f=f: tf[r["video_id"]][f], "ctr") for f in ("has_number", "is_question", "has_dash_or_colon")}
    # temas (productions.theme, senao palavras-chave dos titulos)
    th = {p["video_id"]: p["theme"] for p in st.q("SELECT video_id, theme FROM productions WHERE video_id IS NOT NULL AND theme IS NOT NULL")}
    kw = defaultdict(list)
    for r in T:
        for k in ([th[r["video_id"]]] if r["video_id"] in th else set(keywords(r["title"]))):
            kw[k].append(r)
    A["temas"] = {k: dict(n=len(v), views=sum(x["views"] for x in v), subs_per_1k=_mean([x["subs_per_1k"] for x in v]), avg_view_pct=_mean([x["avg_view_pct"] for x in v]))
                  for k, v in kw.items() if len(v) >= 1}
    # trafego agregado
    tg = defaultdict(lambda: [0.0, 0.0])
    for r in T:
        for t in st.latest_rows("traffic", r["video_id"]):
            tg[t["source"]][0] += t["views"] or 0
            tg[t["source"]][1] += t["minutes"] or 0
    A["trafego"] = {k: dict(views=v[0], minutes=v[1]) for k, v in sorted(tg.items(), key=lambda kv: -kv[1][0])}
    A["evergreen"] = [dict(video_id=r["video_id"], title=r["title"], late_share=r["late_share"]) for r in T if r["late_share"] and (r["days_with_data"] or 0) >= 35 and r["late_share"] >= 0.2]
    A["janelas_24h_7d_28d"] = [dict(video_id=r["video_id"], d1=r["d1"], d7=r["d7"], d28=r["d28"]) for r in T if r["d1"] is not None or r["d7"] is not None]
    A["limites"] = [f"{sum(1 for r in T if r['confidence'] == 'insuficiente')} de {len(T)} videos com amostra insuficiente (<{MIN_VIEWS} views e <{MIN_IMPR} impressoes)",
                    f"comparacoes por grupo so valem com n>={MIN_N} videos por grupo; abaixo disso sao apenas hipoteses",
                    "retencao/CTR podem demorar ~2 dias; 24 h e aproximado (granularidade diaria da API)"]
    miss = st.q("SELECT what, COUNT(DISTINCT video_id) n FROM availability WHERE status='indisponivel' GROUP BY what")
    if miss:
        A["metricas_indisponiveis"] = {m["what"]: m["n"] for m in miss}
    return A


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None
