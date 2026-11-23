#!/usr/bin/env python3
"""Inteligencia do canal do YouTube (SOMENTE LEITURA). Rodar da pasta pipeline/.
  python channel.py connect [--monetary]     OAuth 2.0 no seu computador (somente leitura; token fora do repositorio)
  python channel.py status | refresh | disconnect   estado / renovar / revogar acesso e apagar token local
  python channel.py sync [--max 100]        coleta canal + videos + Analytics (24 h/7 d/28 d, retencao, trafego, geo, demografia) no banco
  python channel.py analyze                 tabela comparativa + rankings + limites de confianca
  python channel.py thumbs [--dir entregas] analise visual das miniaturas (baixa a miniatura publicada ou usa arquivo local)
  python channel.py retention <video_id> <slug>    quedas da retencao x cena x frase; diagnostico do roteiro (--no-curve: so roteiro)
  python channel.py strategy                gera analises/estrategia_<data>.md (relatorio ANTES de cada producao)
  python channel.py register <slug> [--video-id ..] [--theme ..] [--title ..] [--script ..] [--thumb ..] [--duration ..] [--strategy ..] [--positives ..] [--problems ..] [--recs ..]
  python channel.py history | compare <slugA> <slugB> | export | import | seed-manual | selftest
Modo nuvem (Claude Code): sem token local; o proxy injeta o token (request_credential, host www.googleapis.com, escopos de leitura)."""
import argparse, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from channel import auth, api, collect, analyze as an, strategy, store, thumbs, retention

ANALISES = os.path.join(os.path.dirname(HERE), "analises")
HIST = os.path.join(ANALISES, "historico")


def seed_manual(st):
    j = json.load(open(os.path.join(HERE, "channel", "fixtures", "whyexplained_manual_2026-11-18.json"), encoding="utf-8"))
    for v in j["videos"]:
        st.upsert_video(dict(video_id=v["video_id"], title=v["title"], published_at=v["published_at"], duration_s=v["duration_s"], source="manual_studio_prints"))
        st.add_metrics(v["video_id"], "lifetime", v["metrics"], ts=1763424000, source="manual_studio_prints")
        if v["retention"]:
            st.add_rows("retention", v["video_id"], [(r[0], r[1], None) for r in v["retention"]], ts=1763424000)
        st.add_rows("traffic", v["video_id"], [tuple(t) for t in v["traffic"]], ts=1763424000)
    return len(j["videos"])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    for n in ("connect", "status", "refresh", "disconnect", "analyze", "strategy", "history", "export", "import", "seed-manual", "selftest", "sync", "thumbs", "retention", "register", "compare"):
        sp.add_parser(n)
    p = sp.choices
    p["connect"].add_argument("--monetary", action="store_true")
    p["sync"].add_argument("--max", type=int, default=100)
    p["thumbs"].add_argument("--dir", default=None)
    p["retention"].add_argument("video_id"); p["retention"].add_argument("slug"); p["retention"].add_argument("--no-curve", action="store_true")
    p["compare"].add_argument("a"); p["compare"].add_argument("b")
    p["register"].add_argument("slug")
    for k in ("video-id", "theme", "title", "script", "thumb", "duration", "strategy", "positives", "problems", "recs"):
        p["register"].add_argument("--" + k)
    a = ap.parse_args()
    if a.cmd == "connect":
        print(json.dumps(auth.connect(a.monetary), indent=1)); return
    if a.cmd == "status":
        print(json.dumps(auth.status(), indent=1)); return
    if a.cmd == "refresh":
        auth.refresh(); print(json.dumps(auth.status(), indent=1)); return
    if a.cmd == "disconnect":
        print(json.dumps(auth.disconnect(), indent=1)); return
    if a.cmd == "selftest":
        from channel import selftest; selftest.run(); return
    st = store.Store()
    if a.cmd == "seed-manual":
        print("videos semente:", seed_manual(st))
    elif a.cmd == "sync":
        try:
            print(json.dumps(collect.sync(api.Client(), st, a.max), indent=1))
        except (api.ApiError, auth.AuthError) as e:
            sys.exit(f"ERRO: {e}\n(401/403 = sem autorizacao de leitura; rode 'channel.py connect' ou, na nuvem, request_credential com escopos youtube.readonly + yt-analytics.readonly)")
        if os.path.isdir(HIST):
            st.export_json(HIST)
    elif a.cmd == "analyze":
        A = an.analyze(st)
        print(json.dumps({k: v for k, v in A.items() if k != "videos"}, indent=1, default=str))
        for r in A["videos"]:
            print(f"- {r['title'][:50]:50} views={r['views']:.0f} impr={r['impressions']} ctr={r['ctr']} avg%={r['avg_view_pct']} ret30={r['retention_30s']} conf={r['confianca'] if 'confianca' in r else r['confidence']}")
    elif a.cmd == "thumbs":
        for v in st.q("SELECT video_id,title,thumb_url FROM videos WHERE thumb_url IS NOT NULL"):
            try:
                f = thumbs.features(v["thumb_url"]); print(v["title"][:40], f, "|", thumbs.describe(f))
            except Exception as e:
                print(v["title"][:40], "-> miniatura indisponivel:", e)
        if a.dir:
            for pth in sorted(__import__("glob").glob(os.path.join(a.dir, "*", "thumbnail.jpg"))):
                f = thumbs.features(pth); print(pth, f, "|", thumbs.describe(f))
    elif a.cmd == "retention":
        base = os.path.join(os.path.dirname(HERE), "projects", a.slug)
        pj = os.path.join(base, "project.json")
        srt = next((q for q in (os.path.join(base, "output", "captions.srt"), os.path.join(os.path.dirname(HERE), "entregas", a.slug, "captions.srt")) if os.path.exists(q)), None)
        if not (os.path.exists(pj) and srt):
            sys.exit(f"precisa de {pj} e captions.srt do projeto")
        tl, sr = retention.timeline(pj), retention.parse_srt(srt)
        print("DIAGNOSTICO DO ROTEIRO:"); [print(" -", d) for d in retention.script_diagnostics(tl, sr)]
        if not a.no_curve:
            rows = st.latest_rows("retention", a.video_id)
            if not rows:
                print("sem curva de retencao no banco (ainda nao processada ou indisponivel)")
            else:
                for d in retention.map_drops(an.drops(rows, tl["duration"]), tl, sr):
                    print(f" - queda de {abs(d['delta']) * 100:.0f} p.p. em {d['sec']:.0f}s | cena={d['scene']} | frase=\"{(d['sentence'] or '')[:70]}\" | ult. evento ha {d['seconds_since_last_event']}s")
    elif a.cmd == "strategy":
        print(strategy.write(st, ANALISES))
    elif a.cmd == "register":
        kw = {k: v for k, v in dict(video_id=a.video_id, theme=a.theme, title=a.title, script_path=a.script, thumbnail_path=a.thumb, duration_s=float(a.duration) if a.duration else None,
                                    strategy=a.strategy, positives=a.positives, problems=a.problems, recommendations=a.recs).items() if v is not None}
        st.register_production(a.slug, **kw); print("registrado:", a.slug)
    elif a.cmd == "history":
        for r in st.q("SELECT slug, video_id, theme, title, duration_s, published_at FROM productions ORDER BY created_ts"):
            print(r)
    elif a.cmd == "compare":
        for s in (a.a, a.b):
            pr = (st.q("SELECT * FROM productions WHERE slug=?", (s,)) or [None])[0]
            m = st.latest(pr["video_id"]) if pr and pr["video_id"] else {}
            print(s, {k: m.get(k) for k in ("views", "impressions", "ctr", "averageViewPercentage", "averageViewDuration", "subscribersGained")})
    elif a.cmd == "export":
        st.export_json(HIST); print("exportado para", HIST)
    elif a.cmd == "import":
        st.import_json(HIST); print("importado de", HIST)


if __name__ == "__main__":
    main()
