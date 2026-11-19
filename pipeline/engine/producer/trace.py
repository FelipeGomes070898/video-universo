"""RASTREABILIDADE: ideia -> roteiro -> cena -> asset -> prompt -> voz -> audio -> timeline -> render (a partir do project.json real)."""


def build(proj, brief_idea, voice_meta, render_name):
    rows = []
    for s in proj["scenes"]:
        assets = [b["ref"] for b in s.get("bodies", [])] + [sp["type"] + (":" + sp.get("model", "") if sp.get("model") else "") for sp in s.get("sprites", [])]
        rows.append(dict(ideia=brief_idea, roteiro=s.get("text", "")[:80] + "...", cena=s["id"], asset=assets or ["sky:" + s.get("sky", "")],
                         autenticidade=s.get("asset_kind", "simulation"), prompt="N/A (render procedural; ver scenes.py)", voz=voice_meta.get("voice"),
                         audio="narration.wav + music.wav -> audio_mix.wav", timeline=[round(s["start"], 2), round(s["end"], 2)], render=render_name))
    return rows
