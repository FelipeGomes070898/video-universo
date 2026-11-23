#!/usr/bin/env python3
"""PRODUTORA: liga os modulos de engine/producer ao pipeline de filme (scenes.py -> build_film -> render).
  python produce.py init <slug> --tema "..." [--objetivo ..] [--publico ..] [--plataforma youtube] [--duracao 900] [--idioma en] [--estilo ..]
        cria projects/<slug>/ com brief.json, plan/00_formato.json (formato/ritmo/audio/voz), plan/01_pesquisa_tarefas.json, dossier.json,
        curiosity_chain.json, publication_in.json e um scenes.py modelo -> segue a ordem: PESQUISAR -> MAPA DE CURIOSIDADE -> ROTEIRO -> CENAS
  python produce.py storyboard <slug>   storyboard por cena (tempo, narracao, visual, asset, camera, texto, musica, efeitos, transicao, objetivos) a partir do project.json real
  python produce.py check <slug>        verificacao final (factual, narrativa, visual, audio medido, voz, autenticidade, publicacao) + novidade + rastreabilidade
O motor NAO pesquisa sozinho: a pesquisa e feita pela IA operadora (WebSearch/fontes) e registrada em dossier.json; o QC avisa o que ficou sem fonte."""
import argparse, json, os, sys
from engine.producer import formats, research, curiosity, assets, publication, qc, trace


def _j(p, d=None):
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else d


def _w(p, o):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(o, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


TEMPLATE = '''"""{tema} - roteiro e cenas ESCRITOS DO ZERO (regra: nenhuma cena pode repetir um video anterior; ver CLAUDE.md).
Ordem de trabalho: dossier.json (pesquisa com fontes) -> curiosity_chain.json -> este arquivo. Cada cena declara role/chapter/asset_kind."""
import importlib.util, os
_p = os.path.join(os.path.dirname(__file__), "..", "the_wall_hd", "scenes.py")        # so a biblioteca de corpos/ceus (BODIES/SKIES), nunca cenas
_sp = importlib.util.spec_from_file_location("lib_bodies", _p); _lib = importlib.util.module_from_spec(_sp); _sp.loader.exec_module(_lib)
TITLE = "{tema}"
SLUG = "{slug}"
LY = _lib.LY
BODIES, SKIES = dict(_lib.BODIES), dict(_lib.SKIES)


def sc(i, text, **spec):
    d = dict(id=i, text=" ".join(text), hud=False, sky="deep", xfade={{"dur": 1.2}}, fade_out=0, fade_in=0, pad_after=0.5)
    d.update(spec)
    return d


SCENES = [
    # sc("gancho", ["Frase 1.", "Frase 2."], role="gancho", chapter="Titulo do capitulo", asset_kind="simulation|real|reconstruction|illustration|ai",
    #    cam=[[0, [0, 0, 10], [0, 0, 0], 45], [1, [4, 0, 8], [0, 0, 0], 45]], labels=[dict(at="#1", dur=4, text="TEXTO", sub="", y=0.86)],
    #    media=[dict(src="nasa:<id>", at="#0", dur=8, zoom=[1.0, 1.3])], sfx=[["#2", "thud", 3, 0.4]]),   # roles: gancho | desenvolvimento | virada | conclusao
]
'''


def _strategy_gate(a):
    """Ciclo: analisar o canal ANTES de planejar/roteirizar. Exige analises/estrategia_*.md recente (<= 14 dias): python channel.py sync && python channel.py strategy."""
    from channel import strategy
    ok, path, age = strategy.fresh(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "analises"))
    if ok:
        print(f"[estrategia] usando {path} ({age} dia(s)). LEIA antes de escrever o roteiro.")
        return
    if getattr(a, "sem_estrategia", None):
        print(f"[estrategia] IGNORADA a pedido do usuario: {a.sem_estrategia}")
        return
    sys.exit("BLOQUEADO: nao ha relatorio estrategico do canal recente (analises/estrategia_*.md, <= 14 dias).\n"
             "Rode: python channel.py sync && python channel.py strategy  (ou, sem acesso ao canal: python channel.py seed-manual && python channel.py strategy)\n"
             "Para pular, so com ordem do usuario: --sem-estrategia \"motivo\"")


def init(a):
    _strategy_gate(a)
    d = os.path.join("projects", a.slug)
    brief = dict(title=a.tema, tema=a.tema, objetivo=a.objetivo, publico=a.publico, platform=a.plataforma, duration_seconds=a.duracao,
                 language=a.idioma, estilo=a.estilo, format=a.formato, factual=a.factual)
    if not os.path.exists(os.path.join(d, "brief.json")):
        _w(os.path.join(d, "brief.json"), brief)
    fm = formats.analyze(brief)
    _w(os.path.join(d, "plan", "00_formato.json"), fm)
    _w(os.path.join(d, "plan", "01_pesquisa_tarefas.json"), research.tasks(brief, fm))
    for name, default in (("dossier.json", dict(fatos=[], assets=[], controversias=[], lacunas=[])),
                          ("curiosity_chain.json", [dict(pergunta="", promessa_cena="", resposta_cena="", nova_pergunta="")]),
                          ("publication_in.json", dict(titulos=[], palavra_principal="", tags=[], hashtags=[], descricao_abertura="", fontes=[], aviso_autenticidade="",
                                                       comentario_fixado="", thumb_seed=dict(core="", question="", mystery="", scale="")))):
        if not os.path.exists(os.path.join(d, name)):
            _w(os.path.join(d, name), default)
    sp = os.path.join(d, "scenes.py")
    if not os.path.exists(sp):
        open(sp, "w", encoding="utf-8").write(TEMPLATE.format(tema=a.tema.replace('"', "'"), slug=a.slug))
    print(f"[produce] projeto '{a.slug}' criado. Formato: {fm['formato']} | ritmo {fm['ritmo']} | musica {fm['musica']} | efeitos {fm['efeitos_sonoros']} | voz {fm['perfil_de_voz']} | factual={fm['modo_factual']}")
    print("  PROXIMOS PASSOS (nesta ordem, sem pular):")
    print("  1. PESQUISAR (WebSearch/fontes) seguindo plan/01_pesquisa_tarefas.json; registrar fatos com status+fonte+url em dossier.json")
    print("  2. MAPA DE CURIOSIDADE em curiosity_chain.json (pergunta -> promessa -> descoberta -> nova pergunta -> resposta)")
    print("  3. ROTEIRO + CENAS em scenes.py (imagens reais da NASA/dominio publico: python -m engine.nasa search ...; mapas/cards/linha do tempo/quiz quando ajudarem)")
    print(f"  4. python build_film.py projects/{a.slug} --profile sage|documentary   (voz) ; 5. python produce.py storyboard {a.slug} ; 6. render ; 7. python produce.py check {a.slug}")


def _scene_rows(proj, meta):
    hits = meta.get("sfx_hits", [])
    rows = []
    for s in proj["scenes"]:
        t0, t1 = s["start"], s["end"]
        labs = [t["text"] for t in proj.get("titles", []) if t0 <= t["start"] < t1]
        med = [m for m in proj.get("media", []) if t0 <= m["start"] < t1]
        sps = [sp.get("model") or sp["type"] for sp in s.get("sprites", [])]
        bodies = [b["ref"] for b in s.get("bodies", [])]
        cam = s["cam"]
        mov = f"camera {len(cam)} keys; fov {cam[0].get('fov')}->{cam[-1].get('fov')}"
        sfx = [h[1][0] for h in hits if t0 <= h[0] < t1]
        rows.append(dict(cena=s["id"], tempo=[round(t0, 1), round(t1, 1)], narracao=s.get("text", ""), visual=bodies + sps + (["midia real: " + os.path.basename(m["path"]) for m in med]),
                         tipo_asset=s.get("asset_kind", "simulation") + (" + real(NASA)" if med else ""), movimento=mov, texto_na_tela=labs, musica="ambiente baixa (ducking sob a voz)",
                         efeito_sonoro=sfx or "nenhum (silencio de efeitos)", transicao=("dissolvencia %.1fs" % s["xfade"]["dur"]) if s.get("xfade") else "corte", objetivo_narrativo=s.get("role", "-"),
                         objetivo_retencao=s.get("objective", "mudanca visual/evento a cada <=30 s (LINT do build)")))
    return rows


def storyboard(a):
    d = os.path.join("projects", a.slug)
    proj = _j(os.path.join(d, "project.json"))
    meta = _j(os.path.join(d, "output", "audio_meta.json"), {})
    rows = _scene_rows(proj, meta)
    _w(os.path.join(d, "plan", "02_storyboard.json"), rows)
    with open(os.path.join(d, "plan", "02_storyboard.md"), "w", encoding="utf-8") as f:
        f.write(f"# Storyboard - {a.slug}\n\n")
        for r in rows:
            f.write(f"## {r['cena']}  [{int(r['tempo'][0]//60)}:{int(r['tempo'][0]%60):02d}-{int(r['tempo'][1]//60)}:{int(r['tempo'][1]%60):02d}]\n- **Narracao:** {r['narracao']}\n- **Visual:** {', '.join(map(str, r['visual']))}\n"
                    f"- **Asset:** {r['tipo_asset']} | **Movimento:** {r['movimento']}\n- **Texto na tela:** {r['texto_na_tela'] or '-'}\n- **Musica:** {r['musica']} | **Efeito:** {r['efeito_sonoro']}\n"
                    f"- **Transicao:** {r['transicao']} | **Papel:** {r['objetivo_narrativo']}\n- **Retencao:** {r['objetivo_retencao']}\n\n")
    print(f"[produce] storyboard com {len(rows)} cenas em {d}/plan/02_storyboard.md")


def check(a):
    d = os.path.join("projects", a.slug)
    proj = _j(os.path.join(d, "project.json"))
    brief = _j(os.path.join(d, "brief.json"), dict(title=proj["briefing"]["title"], tema=proj["briefing"]["title"]))
    fm = formats.analyze(brief)
    dossier = _j(os.path.join(d, "dossier.json"), {})
    pin = _j(os.path.join(d, "publication_in.json"), {})
    pub = None
    if pin and pin.get("titulos") and pin.get("descricao_abertura"):
        pub = publication.build(pin, proj["scenes"], proj)
        _w(os.path.join(d, "plan", "05_publication.json"), pub)
    R = qc.run(proj, d, dossier, pub, fm)
    chain = _j(os.path.join(d, "curiosity_chain.json"), [])
    chain = [c for c in chain if c.get("pergunta")]
    times = {s["id"]: (s["start"], s["end"]) for s in proj["scenes"]}
    if chain:
        loops, warn = curiosity.validate(chain, times, proj["briefing"]["duration_seconds"])
        R.append(dict(verificacao="Retencao: mapa de curiosidade", status="PASS" if not warn else "WARN", detalhe=f"{len(loops)} loops de pergunta; " + ("; ".join(warn) or "sem lacunas > 75 s")))
    else:
        R.append(dict(verificacao="Retencao: mapa de curiosidade", status="WARN", detalhe="curiosity_chain.json vazio (preencher antes do roteiro)"))
    try:
        from engine import novelty
        iss = novelty.check(d) if a.slug not in novelty.registry(os.path.dirname(os.path.abspath(__file__))).get("legacy", []) else []
        R.append(dict(verificacao="Novidade (nenhuma cena repete video anterior)", status="PASS" if not iss else "FAIL", detalhe=f"{len(iss)} repeticoes" if iss else "ok"))
    except Exception as e:
        R.append(dict(verificacao="Novidade", status="WARN", detalhe=str(e)[:80]))
    meta = _j(os.path.join(d, "output", "audio_meta.json"), {})
    _w(os.path.join(d, "plan", "07_traceability.json"), trace.build(proj, brief.get("tema", ""), meta, a.slug + ".mp4"))
    qc.write(R, os.path.join(d, "plan", "09_qc"))
    for r in R:
        print(f"  [{r['status']:6}] {r['verificacao']}: {r['detalhe']}")
    print(f"[produce] relatorio em {d}/plan/09_qc.md")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("init")
    i.add_argument("slug"); i.add_argument("--tema", required=True)
    i.add_argument("--objetivo", default=""); i.add_argument("--publico", default=""); i.add_argument("--plataforma", default="youtube")
    i.add_argument("--duracao", type=int, default=None); i.add_argument("--idioma", default="en"); i.add_argument("--estilo", default="")
    i.add_argument("--formato", default="16:9"); i.add_argument("--factual", action="store_true")
    i.add_argument("--sem-estrategia", default=None, help="pula a porta do relatorio estrategico (SO com ordem do usuario; informe o motivo)")
    for n in ("storyboard", "check"):
        sub.add_parser(n).add_argument("slug")
    a = ap.parse_args()
    {"init": init, "storyboard": storyboard, "check": check}[a.cmd](a)


if __name__ == "__main__":
    main()
