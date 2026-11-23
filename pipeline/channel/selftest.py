"""Teste OFFLINE (sem rede e sem token): cliente falso com respostas no formato real das APIs. Verifica coleta -> banco -> analise -> estrategia,
protecoes (GET-only, hosts permitidos, token fora do git, metrica indisponivel nao inventada), cautela estatistica, retencao x roteiro e export/import.
Executar: python channel.py selftest"""
import datetime as dt, json, os, tempfile
from . import api, auth, collect, analyze as an, retention, store, strategy

TODAY = dt.date(2026, 12, 20)


class Fake:
    """Imita Data API v3 e Analytics v2. Videos: A..F; F sem impressoes/CTR (HTTP 400) para testar 'indisponivel'."""
    calls = 0

    def __init__(self, big=False):
        self.big = big
        self.vids = [("vidA", "Why the Sun Is Not Yellow", 600, "2026-10-01T10:00:00Z"), ("vidB", "The Moon Is Moving Away", 700, "2026-10-08T10:00:00Z"),
                     ("vidC", "7 Facts About Mars", 800, "2026-10-15T10:00:00Z"), ("vidD", "The Moon Is Drifting Away From Earth", 900, "2026-10-10T10:00:00Z"),
                     ("vidE", "Inside a Black Hole", 1100, "2026-10-29T10:00:00Z"), ("vidF", "Voyager Without Cameras", 1000, "2026-11-12T10:00:00Z")]

    def get(self, url, params=None, retries=3):
        self.calls += 1
        p = params or {}
        if url.endswith("/channels"):
            return {"items": [{"id": "UC123", "snippet": {"title": "Canal Teste", "description": "d", "publishedAt": "2025-01-01T00:00:00Z", "country": "BR"},
                               "statistics": {"subscriberCount": "321", "videoCount": "6", "viewCount": "9999"}, "contentDetails": {"relatedPlaylists": {"uploads": "UU123"}},
                               "brandingSettings": {"channel": {"keywords": "space"}}, "status": {"privacyStatus": "public"}}]}
        if url.endswith("/playlistItems"):
            return {"items": [{"contentDetails": {"videoId": v[0]}} for v in self.vids]}
        if url.endswith("/videos"):
            return {"items": [{"id": v[0], "snippet": {"title": v[1], "description": "x", "publishedAt": v[3], "thumbnails": {"high": {"url": "https://i.ytimg.com/vi/x/hq.jpg"}}, "tags": ["space"], "categoryId": "28"},
                               "contentDetails": {"duration": f"PT{v[2] // 60}M{v[2] % 60}S"}, "statistics": {"viewCount": "100", "likeCount": "5", "commentCount": "1"}, "status": {"privacyStatus": "public"}} for v in self.vids]}
        vid = p["filters"].split("==")[1]
        k = [v[0] for v in self.vids].index(vid)
        dur = self.vids[k][2]
        met, dim = p["metrics"], p.get("dimensions")
        scale = 50 if self.big else 1
        if "videoThumbnailImpressions" in met:
            if vid == "vidF":
                raise api.ApiError(400, "metric not supported", "badRequest")
            impr = (4000 + 500 * k) * scale if self.big else 150 + 20 * k
            ctr = (0.02 if k % 2 == 0 else 0.07) if self.big else (0.03 + 0.01 * k)
            return {"columnHeaders": [{"name": "videoThumbnailImpressions"}, {"name": "videoThumbnailImpressionsClickRate"}], "rows": [[impr, ctr * 100]]}     # taxa em % (testa normalizacao)
        if dim == "day":
            start = dt.date.fromisoformat(self.vids[k][3][:10])
            n = (TODAY - start).days + 1
            return {"columnHeaders": [{"name": "day"}, {"name": "views"}, {"name": "estimatedMinutesWatched"}, {"name": "subscribersGained"}],
                    "rows": [[(start + dt.timedelta(d)).isoformat(), (30 if d < 2 else 5) * scale, 60 * scale, 1 if d < 3 else 0] for d in range(n)]}
        if dim == "elapsedVideoTimeRatio":
            first_drop = 0.35 + 0.05 * (k % 3)
            return {"columnHeaders": [{"name": "elapsedVideoTimeRatio"}, {"name": "audienceWatchRatio"}, {"name": "relativeRetentionPerformance"}],
                    "rows": [[i / 100, 1 - first_drop * min(i, 8) / 8 - 0.003 * max(0, i - 8) - (0.12 if 50 <= i < 53 else 0) * (1 if i >= 53 else (i - 49) / 4), 0.5] for i in range(0, 101)]}
        if dim == "insightTrafficSourceType":
            return {"columnHeaders": [{"name": "insightTrafficSourceType"}, {"name": "views"}, {"name": "estimatedMinutesWatched"}], "rows": [["YT_SEARCH", 60 * scale, 100], ["YT_SUGGESTED", 40 * scale, 80]]}
        if dim == "country":
            return {"columnHeaders": [{"name": "country"}, {"name": "views"}], "rows": [["BR", 70 * scale], ["US", 20 * scale]]}
        if dim == "ageGroup,gender":
            return {"columnHeaders": [{"name": "ageGroup"}, {"name": "gender"}, {"name": "viewerPercentage"}], "rows": [["age25-34", "male", 41.0]]}
        return {"columnHeaders": [{"name": m} for m in met.split(",")],
                "rows": [[(100 + 10 * k) * scale if m == "views" else (30 + 4 * k) if m == "averageViewPercentage" else 200 + 20 * k if m == "averageViewDuration" else 5 for m in met.split(",")]]}


def ok(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    assert cond, msg


def run():
    # 1) protecoes
    for bad in ("https://example.com/x", "https://www.googleapis.com/drive/v3/files", "http://www.googleapis.com/youtube/v3/channels"):
        try:
            api.Client(token_fn=lambda: None).get(bad); ok(False, "host nao permitido deveria falhar")
        except ValueError:
            pass
    ok(True, "cliente rejeita hosts fora do YouTube (somente leitura, GET)")
    ok(not any(hasattr(api.Client, m) for m in ("post", "put", "delete", "patch")), "cliente nao tem metodos de escrita")
    old = auth.TOKEN_FILE
    try:
        auth.TOKEN_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "token_no_repo.json")
        try:
            auth._guard(); ok(False, "token dentro do repositorio deveria ser recusado")
        except auth.AuthError:
            ok(True, "token/credencial dentro de repositorio git e recusado")
    finally:
        auth.TOKEN_FILE = old
    ok(all(s.endswith("readonly") for s in auth.SCOPES_READ), "escopos padrao sao somente leitura")
    # 2) coleta pequena + metrica indisponivel
    st = store.Store(":memory:")
    r = collect.sync(Fake(), st, today=TODAY)
    ok(r["videos"] == 6 and r["subscribers"] == 321, "sync: canal e 6 videos coletados")
    ok(st.latest("vidA")["ctr"] < 1, "CTR em % normalizado para fracao")
    ok("ctr" not in st.latest("vidF"), "metrica indisponivel (vidF) NAO foi inventada")
    ok(any(x["what"] == "impressoes_ctr" for x in st.q("SELECT * FROM availability")), "indisponibilidade registrada em 'availability'")
    ok(st.latest("vidA", "d7").get("views") == 30 * 2 + 5 * 5, "janela 7 dias somada dos dias 0-6 (diaria)")
    A = an.analyze(st)
    ok(A["n_videos"] == 6 and A["limites"], "analise gera limites de confianca")
    ok(all(v["confidence"] in ("insuficiente", "baixa") for v in A["videos"]), "amostra pequena => confianca insuficiente/baixa (sem conclusoes)")
    rep = strategy.build(st, today=TODAY)
    ok(len(rep["respostas"]) == 10, "relatorio responde as 10 perguntas")
    ok(any("canibalizacao" in a["resposta"] for a in rep["respostas"] if a["pergunta"].startswith("4.")), "detecta canibalizacao (2 videos da Lua em 2 dias)")
    q8 = [a for a in rep["respostas"] if a["pergunta"].startswith("8.")][0]
    ok(q8["confianca"] == "insuficiente", "miniatura: nao declara vencedora com poucas impressoes")
    # 3) amostra grande: diferenca de CTR com IC separado
    st2 = store.Store(":memory:"); collect.sync(Fake(big=True), st2, today=TODAY)
    q8b = [a for a in strategy.build(st2, today=TODAY)["respostas"] if a["pergunta"].startswith("8.")][0]
    ok("SEPARADOS" in q8b["resposta"] and q8b["confianca"] == "media", "amostra grande: IC separados => diferenca provavel (confianca media)")
    # 4) retencao x roteiro
    rows = st.latest_rows("retention", "vidA")
    d = an.drops(rows, 600)
    ok(len(d) >= 1 and d[0]["delta"] < 0, f"quedas detectadas na curva (maior: {d[0]['delta']} em {d[0]['sec']}s)")
    with tempfile.TemporaryDirectory() as t:
        pj = os.path.join(t, "project.json")
        json.dump(dict(briefing=dict(duration_seconds=600), scenes=[dict(id="gancho", start=0, end=40), dict(id="meio", start=40, end=600)], titles=[dict(start=30, end=34)], media=[], cards=[]), open(pj, "w"))
        srt = os.path.join(t, "c.srt")
        open(srt, "w").write("1\n00:00:05,000 --> 00:00:09,000\nHello there friend.\n\n2\n00:00:50,000 --> 00:01:20,000\n" + "word " * 45 + "\n")
        tl, sr = retention.timeline(pj), retention.parse_srt(srt)
        diag = retention.script_diagnostics(tl, sr)
        ok(any("introducao" in x for x in diag) and any("lacuna" in x for x in diag) and any("frase longa" in x for x in diag), "diagnostico do roteiro: introducao lenta, lacuna visual e frase longa")
        m = retention.map_drops(d, tl, sr)
        ok(all("scene" in x for x in m), "quedas associadas a cena/frase/ultimo evento")
    # 5) historico: registro e export/import
    st.register_production("video_x", video_id="vidA", theme="sol", title="Why the Sun Is Not Yellow", duration_s=600, positives="ok", problems="intro", recommendations=["gancho 5 s"])
    with tempfile.TemporaryDirectory() as t:
        st.export_json(t)
        st3 = store.Store(":memory:"); st3.import_json(t)
        ok(st3.q("SELECT COUNT(*) n FROM productions")[0]["n"] == 1 and st3.q("SELECT COUNT(*) n FROM videos")[0]["n"] == 6, "export/import preserva historico e producoes")
        blob = "".join(open(os.path.join(t, f), encoding="utf-8").read() for f in os.listdir(t))
        ok("Bearer" not in blob and "ya29" not in blob and "refresh_token" not in blob, "exportacao nao contem tokens")
    # 6) porta da estrategia
    with tempfile.TemporaryDirectory() as t:
        ok(strategy.fresh(t)[0] is False, "sem relatorio => produce.py init bloqueia")
        p = strategy.write(st, t, today=TODAY)
        ok(strategy.fresh(t, today=TODAY)[0] is True and strategy.fresh(t, today=TODAY + dt.timedelta(days=30))[0] is False, "relatorio recente libera; velho (>14 d) bloqueia")
    print("\nTODOS OS TESTES PASSARAM")
