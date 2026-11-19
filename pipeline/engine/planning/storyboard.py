"""STORYBOARD + ASSETS + RASTREABILIDADE derivados do project.json real (nada inventado)."""
import numpy as np


def _body_at(world, look):
    best, bd = None, 1e18
    for b in world["bodies"]:
        c = np.array(b.get("pos") or b["orbit"]["center"], float)
        d = np.linalg.norm(c - np.array(look))
        if d < bd:
            best, bd = b, d
    return best


def _build_generic(project):
    cam = project["camera"]["keys"]
    titles = project.get("titles", [])
    scenes = []
    for i in range(len(cam) - 1):
        a, b = cam[i], cam[i + 1]
        txt = [t["text"] for t in titles if t["start"] < b["t"] and t["end"] > a["t"]]
        scenes.append({"id": f"S{i+1:02d}", "tempo": [a["t"], b["t"]], "duracao_s": round(b["t"] - a["t"], 2),
                       "narracao": "SEM NARRACAO (nao implementada neste motor)", "visual": "Oceano procedural + ceu/nuvens + gaivotas",
                       "tipo_asset": "SIMULACAO 3D procedural", "plano": "baixo, rente a agua" if b["pos"][1] < 2.5 else "plano aberto",
                       "movimento": "travelling frontal lento", "fov": [a.get("fov"), b.get("fov")], "texto_na_tela": txt,
                       "musica": "pad grave discreto", "efeito_sonoro": "ondas/vento ambiente (sem efeitos pontuais)",
                       "transicao": "movimento continuo de camera (sem corte)", "objetivo_narrativo": "NAO DEFINIDO",
                       "objetivo_retencao": "sol descendo e luz mudando ao longo do tempo"} for i in range(len(cam) - 1))
    assets = [{"id": x, "categoria": "SIMULACAO", "origem": "engine/ocean.py", "autenticidade": "SIMULACAO - nao e filmagem real"} for x in ("A_OCEANO", "A_CEU_NUVENS", "A_GAIVOTAS")]
    assets += [{"id": "A_SOM_MAR", "categoria": "AUDIO SINTETICO", "origem": "engine/audio.py synth_sea", "autenticidade": "SINTETICO"},
               {"id": "A_VOZ", "categoria": "VOZ", "origem": "NAO DISPONIVEL - requer TTS externo", "autenticidade": "PENDENTE"}]
    trace = [{"ideia": project["briefing"]["topic"], "cena": s["id"], "assets": [a["id"] for a in assets[:3]], "prompt": "N/A (render procedural)",
              "voz": "PENDENTE", "audio": "A_SOM_MAR", "timeline": s["tempo"], "render": project["briefing"].get("slug", "video") + ".mp4"} for s in scenes]
    return scenes, assets, trace


def build(project):
    if "bodies" not in project["world"]:
        return _build_generic(project)
    cam = project["camera"]["keys"]
    world = project["world"]
    titles = project.get("titles", [])
    chords = project["audio"]["chords"]
    whooshes = project["audio"].get("whooshes", [])
    notes = project.get("scene_notes", {})
    scenes = []
    for i in range(len(cam) - 1):
        a, b = cam[i], cam[i + 1]
        sid = f"S{i+1:02d}"
        pa, pb, la = np.array(a["pos"], float), np.array(b["pos"], float), np.array(b["look"], float)
        body = _body_at(world, la)
        dist = float(np.linalg.norm(la - pb))
        ratio = dist / body["radius"]
        plano = "close" if ratio < 3 else "plano medio" if ratio < 8 else "plano aberto"
        delta = pb - pa
        fwd = (la - pa) / (np.linalg.norm(la - pa) + 1e-9)
        frontal = abs(float(delta @ fwd)) / (np.linalg.norm(delta) + 1e-9)
        mov = "travelling frontal (aproximacao)" if frontal > 0.7 else "travelling em arco/lateral"
        txt = [t["text"] for t in titles if t["start"] < b["t"] and t["end"] > a["t"]]
        chord = [c for c in chords if c["t"] <= a["t"]][-1]["t"]
        scenes.append({
            "id": sid, "tempo": [a["t"], b["t"]], "duracao_s": round(b["t"] - a["t"], 2),
            "narracao": notes.get(sid, {}).get("narracao", "SEM NARRACAO (nao implementada neste motor)"),
            "visual": f"{body['name']} ({body['texture']['type']})", "tipo_asset": "SIMULACAO 3D procedural",
            "plano": plano, "movimento": mov, "fov": [a.get("fov"), b.get("fov")],
            "texto_na_tela": txt, "musica": f"pad ambiente, acorde iniciado em t={chord}s",
            "efeito_sonoro": [w for w in whooshes if a["t"] <= w["t"] < b["t"]] or "nenhum (silencio de efeitos)",
            "transicao": "movimento continuo de camera (sem corte)",
            "objetivo_narrativo": notes.get(sid, {}).get("objetivo", "NAO DEFINIDO"),
            "objetivo_retencao": "mudanca de corpo celeste/escala a cada segmento",
        })
    assets = [{"id": f"A_{b['name'].upper()}", "categoria": "SIMULACAO", "origem": f"textura procedural tipo {b['texture']['type']} seed {b['texture'].get('seed')}",
               "autenticidade": "SIMULACAO - nao e fotografia real; nao representa dados astronomicos exatos"} for b in world["bodies"]]
    assets += [{"id": "A_NEBULOSA", "categoria": "SIMULACAO", "origem": "ruido FFT", "autenticidade": "SIMULACAO"},
               {"id": "A_ESTRELAS", "categoria": "SIMULACAO", "origem": "campo estelar procedural", "autenticidade": "SIMULACAO"},
               {"id": "A_TRILHA", "categoria": "AUDIO SINTETICO", "origem": "engine/audio.py", "autenticidade": "SINTETICO"},
               {"id": "A_VOZ", "categoria": "VOZ", "origem": "NAO DISPONIVEL - requer TTS externo", "autenticidade": "PENDENTE"}]
    trace = [{"ideia": project["briefing"]["topic"], "cena": s["id"], "assets": [a["id"] for a in assets if a["id"].split("_")[1] in s["visual"].upper()],
              "prompt": "N/A (render procedural)", "voz": "PENDENTE", "audio": "A_TRILHA", "timeline": s["tempo"], "render": "o_espaco_3d.mp4"} for s in scenes]
    return scenes, assets, trace
