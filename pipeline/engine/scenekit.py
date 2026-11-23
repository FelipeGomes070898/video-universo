"""Ferramentas para ESCREVER cenas (nao sao cenas): sc() cria a cena a partir de linhas do roteiro e converte indices de LINHA em indices de FRASE
(uma linha pode ter 2 frases); M() cria um item de midia real. Uso em projects/<slug>/scenes.py:  from engine.scenekit import sc, M"""
import re
from .tts import split_sentences as _split


def remap(o, first, last):
    """'#k'/'@#k' = inicio da linha k; '@@#k' = fim da linha k (indices reais de frase)."""
    if isinstance(o, str):
        m = re.match(r"^(@@?)?#(\d+)(.*)$", o)
        if m:
            k = int(m.group(2))
            return (m.group(1) or "") + "#" + str(last[k] if m.group(1) == "@@" else first[k]) + m.group(3)
        return o
    if isinstance(o, dict):
        return {k: (v if k in ("text", "id") else remap(v, first, last)) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [remap(x, first, last) for x in o]
    return o


def sc(i, text, **spec):
    first, last, n = [], [], 0
    for t in text:
        c = len(_split(t))
        first.append(n); last.append(n + c - 1); n += c
    d = dict(id=i, text=" ".join(text), hud=False, sky="void", sky_gain=0.18, xfade={"dur": 1.7}, fade_out=0, fade_in=0, pad_after=0.55,
             cam=[[0, [0, 0, 80], [0, 0, 0], 38], [1, [0, 0, 80], [0, 0, 0], 38]])
    d.update({k: remap(v, first, last) for k, v in spec.items()})
    return d


def M(src, at, to, zoom=(1.0, 1.12), pan=((0, 0), (0, 0)), **kw):
    """src: 'nasa:<id>' | 'svs:<item>/<arquivo>' | 'free:...' | caminho. Video: vstart/speed/loop ou stretch=True (ajusta a velocidade para cobrir at..to inteiro)."""
    d = dict(src=src, at=at, to=to, zoom=list(zoom), pan=[list(pan[0]), list(pan[1])], fade=1.15)
    d.update(kw)
    return d
