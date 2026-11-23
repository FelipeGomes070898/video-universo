#!/usr/bin/env python3
"""Pre-producao do filme: narracao TTS -> linha do tempo -> project.json + audio mixado + legendas SRT.

  python build_film.py projects/the_wall [--voice am_michael] [--speed 1.0] [--tts-only]
"""
import sys, math, argparse, hashlib, importlib.util, json, os, wave
import numpy as np
from engine.tts import Narrator, split_sentences, SR as TTS_SR
from engine import voice as vc
from engine import mix as mixer

GAP = 0.25


def load_scenes(pdir):
    spec = importlib.util.spec_from_file_location("scenes", os.path.join(pdir, "scenes.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def write_wav(path, a, sr):
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((np.clip(a, -1, 1) * 32767).astype("<i2").tobytes())


def protos_rate(sc, b):
    return sc.BODIES[b['ref']].get('spin_rate', 5.0)


def srt_time(t):
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdir")
    ap.add_argument("--profile", default="documentary", choices=list(vc.PROFILES), help="perfil de voz: sage (senhor sabio) | narrator")
    ap.add_argument("--voice", default=None)
    ap.add_argument("--speed", type=float, default=None)
    ap.add_argument("--audio", default="sober", choices=["sober", "cinematic"], help="sober: sem whooshes, musica baixa (SFX de cena sempre entram)")
    ap.add_argument("--tts-only", action="store_true")
    ap.add_argument("--music-vol", type=float, default=None, help="volume da musica (padrao: 0.36 sober / 0.55 cinematic). Para a voz ficar >= 12 dB acima da musica use ~0.14")
    ap.add_argument("--no-audio", action="store_true", help="so project.json + SRT (sem mixagem)")
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--allow-reuse", action="store_true", help="NAO USAR sem pedido explicito do usuario: ignora a regra de novidade")
    a = ap.parse_args()
    from engine import novelty
    if not novelty.gate(a.pdir, a.allow_reuse):
        sys.exit(2)
    sc = load_scenes(a.pdir)
    out_dir = os.path.join(a.pdir, "output")
    cache = os.path.join(out_dir, "tts_cache")
    os.makedirs(cache, exist_ok=True)
    prof = dict(vc.PROFILES[a.profile])
    if a.voice: prof['voice'] = a.voice
    if a.speed: prof['speed'] = a.speed
    a.voice, a.speed = prof['voice'], prof['speed']
    a.voice = a.voice or getattr(sc, "VOICE", "bm_george")
    a.speed = a.speed or getattr(sc, "SPEED", 0.94)
    nar = Narrator(a.voice, a.speed)
    rng_b = np.random.default_rng(5)

    # ---------- 1) TTS por frase (cache por hash) + linha do tempo
    t = 0.0
    scenes, chunks = [], []
    for sc_i, s in enumerate(sc.SCENES):
        start = t
        t += s.get("pad_before", 0.4)
        sents = []
        for si_, tx in enumerate(split_sentences(s["text"])):
            pl = vc.plan_sentence(tx, first_in_scene=(si_ == 0), prof=prof)
            h = hashlib.sha1(f"{a.voice}|{a.speed}|{pl['speed_mult']:.3f}|{tx}".encode()).hexdigest()[:16]
            f = os.path.join(cache, h + ".npy")
            if os.path.exists(f):
                au = np.load(f)
            else:
                au = nar.sentence(tx, speed=a.speed * pl["speed_mult"])
                np.save(f, au)
            t += pl["pause_before"]
            d = len(au) / TTS_SR
            if pl["breath"]:
                chunks.append((max(t - 0.36, 0), vc.breath(rng_b)))
            sents.append(dict(text=tx, start=t, end=t + d))
            chunks.append((t, au))
            t += d + pl["pause_after"]
            gap_last = pl["pause_after"]
        t += s.get("pad_after", 0.5) - gap_last + s.get("silence", 0.0)
        scenes.append(dict(spec=s, start=start, end=t, sents=sents))
        print(f"{s['id']:11s} {start:7.1f}s -> {t:7.1f}s  ({t - start:5.1f}s, {sum(len(x['text'].split()) for x in sents)} palavras)", flush=True)
    total = t
    print(f"TOTAL narrado: {total:.1f}s = {int(total // 60)}:{total % 60:04.1f}", flush=True)
    if a.tts_only:
        return

    narr = np.zeros(int(total * TTS_SR) + TTS_SR, np.float32)
    for st, au in chunks:
        o = int(st * TTS_SR)
        narr[o:o + len(au)] += au
    npath = os.path.join(out_dir, "narration.wav")
    write_wav(npath, narr[: int(total * TTS_SR)], TTS_SR)

    # ---------- 2) resolve tempos (u | @frase | @@fim da frase)
    import re as _re

    def res(sp, sceneinfo):
        if isinstance(sp, (int, float)):
            return sceneinfo["start"] + float(sp) * (sceneinfo["end"] - sceneinfo["start"])
        m = _re.match(r"^(@@?)(.*?)([+-]\d+(?:\.\d+)?)?$", sp)
        end, key, off = m.group(1) == "@@", m.group(2), float(m.group(3) or 0)
        if key.startswith("#"):
            se = sceneinfo["sents"][int(key[1:])]
            return (se["end"] if end else se["start"]) + off
        for se in sceneinfo["sents"]:
            if key in se["text"]:
                return (se["end"] if end else se["start"]) + off
        raise KeyError(f"trecho '{key}' nao encontrado na cena {sceneinfo['spec']['id']}")

    def rsp(sp, si):
        """resolve tempos dentro de um sprite: keys / env / rot ([spec, ...]) e t0."""
        sp = dict(sp)
        for fld in ("keys", "env", "rot", "fl_env"):
            if fld in sp:
                sp[fld] = [[res(e[0], si), *e[1:]] for e in sp[fld]]
        if isinstance(sp.get("t0"), str):
            sp["t0"] = res(sp["t0"], si)
        return sp

    sfx_list, ev_times = [], []
    pscenes, titles, hud_keys, hud_windows, cards = [], [], [], [], []
    media, credits = [], {}
    for i, si in enumerate(scenes):
        s = si["spec"]
        for b in s.get("bodies", []):                       # 'face': vira a textura (ex.: Grande Mancha Vermelha) para a camera numa frase
            if "face" in b:
                f = b.pop("face")
                tref = res("@" + f["at"], si) + f.get("dt", 2.0)
                need = (0.75 - f["u"]) * 360.0 + f.get("az", 0.0)
                b["spin0"] = (need - b.get("spin_rate", protos_rate(sc, b)) * tref) % 360.0
        for b in s.get("bodies", []):                       # orbita cuja fase e definida num instante da narracao
            o = b.get("orbit")
            if o and "phase_at" in o:
                spec_, ang_ = o.pop("phase_at")
                o["phase"] = ang_ - 2 * math.pi * res(spec_, si) / o["period"]
        cam = sorted([(res(k[0], si), k) for k in s["cam"]], key=lambda x: x[0])
        keys, last = [], -1
        for tk, k in cam:
            tk = max(tk, last + 1e-3)
            keys.append(dict(t=tk, pos=k[1], look=k[2], fov=k[3]))
            last = tk
        keys[0]["t"] = min(keys[0]["t"], si["start"])
        keys[-1]["t"] = max(keys[-1]["t"], si["end"] + 1e-3)
        sd = {k: v for k, v in s.items() if k in ("bodies", "sky", "sky_gain", "sun", "stars", "bloom", "exposure", "fade_in", "fade_out", "bloom_threshold", "terrain", "tp", "tscale", "xfade", "shake", "roll", "craft_amb", "origin")}
        sd.update(id=s["id"], start=si["start"], end=si["end"], cam=keys)
        sd.update({k: s[k] for k in ("role", "chapter", "asset_kind", "intent", "objective") if k in s}, text=s.get("text", ""))   # p/ storyboard, QC e capitulos
        sd["sprites"] = [rsp(x, si) for x in s.get("sprites", [])]
        if "follow" in s:
            fw = s["follow"]
            sd["follow"] = {"sprite": fw["sprite"], "offset": [[res(e[0], si), *e[1:]] for e in fw["offset"]], "look": [[res(e[0], si), *e[1:]] for e in fw["look"]]}
        if "tkeys" in s:
            sd["tkeys"] = [[res(k[0], si), k[1]] for k in s["tkeys"]]
        for e in s.get("sfx", []):
            sfx_list.append((res(e[0], si), (e[1], e[2], e[3])))
            ev_times.append(sfx_list[-1][0])
        prev_xf = pscenes[-1].get("xfade", {}).get("dur", 0.0) if pscenes else 0.0
        if prev_xf:                                             # a camera ja se move durante o crossfade
            keys[0]["t"] = min(keys[0]["t"], si["start"] - prev_xf)
        pscenes.append(sd)
        for cd in s.get("cards", []):                       # quadros/grafico/quiz/mapa/doc/timeline/comparacao
            c0 = res(cd.get("at", 0.0), si) if not isinstance(cd.get("at"), str) else res("@" + cd["at"], si)
            c = {k: v for k, v in cd.items() if k not in ("at", "dur")}
            c.update(start=c0, end=c0 + cd.get("dur", 6.0))
            cards.append(c)
        if s.get("asset_kind", "simulation") != "real" and s.get("badge", False):
            cards.append(dict(kind="badge", label=s.get("asset_kind", "simulation"), start=si["start"] + 0.6, end=min(si["start"] + 4.6, si["end"] - 0.5), fade=0.5))
        for md in s.get("media", []):                        # fotos/videos reais (NASA): src="nasa:<id>" ou caminho local
            md = dict(md)
            src = md.pop("src")
            if src.startswith("free:"):
                from engine import freemedia
                m = freemedia.get(src[5:])
                md.update(path=m["path"], kind=m["kind"], credit=md.get("credit") or m["credit"])
                credits[m["id"]] = f'{m["title"]} - {m["credit"]} - {m.get("landing")}'
            elif src.startswith("nasa:"):
                from engine import nasa
                m = nasa.get(src[5:])
                md.update(path=m["path"], kind=m["kind"], credit=md.get("credit") or m["credit"])
                credits[m["id"]] = f'{m["title"]} - {m["credit"]} - {m["url"]}'
            else:
                md.update(path=src, kind=md.get("kind", "image"))
            _a = lambda v: v if isinstance(v, (int, float)) or v.startswith("@") else "@" + v
            md["start"] = res(_a(md.pop("at")), si)
            md["end"] = res(_a(md.pop("to")), si) if "to" in md else md["start"] + md.pop("dur")
            media.append(md)
            ev_times.append(md["start"])                    # troca de foto/video = evento visual (conta no lint de retencao)
        for lb in s.get("labels", []):
            t0 = res("@" + lb["at"], si) + 0.15
            ev_times.append(t0)
            titles.append(dict(text=lb["text"], sub=lb.get("sub"), start=t0, end=t0 + lb["dur"], fade=lb.get("fade", 0.7), y=lb.get("y", 0.86), size=lb.get("size", 0.05),
                               sub_size=0.026, tracking=0.02))
        if s.get("hud") and s.get("dist"):
            dk = sorted([(res(k[0], si), k[1]) for k in s["dist"]], key=lambda x: x[0])
            dk[0] = (max(dk[0][0], si["start"]) + 0.45 if dk[0][0] <= si["start"] + 1e-6 else dk[0][0], dk[0][1])
            if dk[-1][0] >= si["end"] - 1e-6:
                dk[-1] = (si["end"] - 0.45, dk[-1][1])
            hud_keys += dk
        if s.get("hud"):
            if hud_windows and abs(hud_windows[-1][1] - si["start"]) < 1e-6:
                hud_windows[-1] = (hud_windows[-1][0], si["end"])
            else:
                hud_windows.append((si["start"] + 0.4, si["end"]))
    hud_keys.sort(key=lambda x: x[0])
    hk = []
    for tk, v in hud_keys:
        if hk and tk <= hk[-1][0]:
            tk = hk[-1][0] + 1e-3
        hk.append((tk, v))
    hud_windows = [(a_, b_ - 0.6) for a_, b_ in hud_windows]

    evs = sorted(ev_times + [x["start"] for x in pscenes])
    gaps = [(round(a_), round(b_)) for a_, b_ in zip(evs, evs[1:]) if b_ - a_ > 30]
    print("LINT retencao: " + ("ok, nenhum trecho > 30 s sem evento" if not gaps else f"{len(gaps)} trecho(s) > 30 s sem evento visual/sonoro: {gaps}"), flush=True)

    proj = dict(
        briefing=dict(title=getattr(sc, "TITLE", "The Wall at the End of the Universe"), slug=getattr(sc, "SLUG", "the_wall_at_the_end_of_the_universe"), language="en-US", duration_seconds=round(total, 3),
                      format="16:9", platform="YouTube"),
        seed=7, render=dict(width=1280, height=720, fps=a.fps, crf=18, preset="medium", texture_width=2048, bloom=0.5, grain=0.009,
                            font="/usr/share/fonts/opentype/inter/Inter-Medium.otf"),
        bodies=sc.BODIES, skies=sc.SKIES, scenes=pscenes, titles=titles, cards=cards, media=media, hud=dict(keys=hk, windows=hud_windows))
    json.dump(proj, open(os.path.join(a.pdir, "project.json"), "w"), indent=1)
    if credits:                                                    # creditos das midias da NASA (colar na descricao do video)
        with open(os.path.join(out_dir, "credits.txt"), "w", encoding="utf-8") as f:
            f.write("Image/video credits. NASA items: NASA Image and Video Library (images.nasa.gov); NASA does not endorse this video. Other items: CC0 / public domain / Creative Commons BY via Openverse and Wikimedia Commons (creator / license / source below).\n" + "\n".join(f"- {v}" for v in credits.values()) + "\n")
        print(f"[nasa] {len(credits)} midia(s) com credito -> {out_dir}/credits.txt", flush=True)

    # ---------- 3) SRT
    with open(os.path.join(out_dir, "captions.srt"), "w", encoding="utf-8") as f:
        n = 1
        for si in scenes:
            for se in si["sents"]:
                f.write(f"{n}\n{srt_time(se['start'])} --> {srt_time(se['end'] + 0.1)}\n{se['text']}\n\n")
                n += 1

    if a.no_audio:
        print("project.json pronto (sem mixagem)")
        return
    # ---------- 4) mixagem (musica + whooshes + ducking)
    tmp = os.path.join(out_dir, "tmp_audio")
    os.makedirs(tmp, exist_ok=True)
    hits = []
    if a.audio == "cinematic":                         # modo sobrio (padrao): sem whooshes/impactos
        hits = [(si["start"] - 0.2, "whoosh") for si in scenes[1:]]
        wall = [si for si in scenes if si["spec"]["id"] == "wall"]
        if wall:
            hits.append((wall[0]["start"] - 0.3, "boom"))
    hits = hits + sfx_list
    json.dump(dict(profile=a.profile, voice=a.voice, speed=a.speed, audio=a.audio, music_vol=(a.music_vol if a.music_vol is not None else (0.55 if a.audio == "cinematic" else 0.36)), sfx_hits=[[h[0], h[1]] for h in hits]), open(os.path.join(out_dir, "audio_meta.json"), "w"))
    music = mixer.make_music([(si["start"], si["end"]) for si in scenes], total, tmp, hits)
    mixer.mix(npath, music, total, os.path.join(out_dir, "audio_mix.wav"), tmp, music_vol=a.music_vol if a.music_vol is not None else (0.55 if a.audio == "cinematic" else 0.36))
    print("audio e projeto prontos:", os.path.join(out_dir, "audio_mix.wav"))


if __name__ == "__main__":
    main()
