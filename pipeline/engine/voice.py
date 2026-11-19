"""DIRETOR DE NARRACAO: perfil 'senhor sabio' (voz grave, serena, humana) sobre o TTS neural.

- voz: am_onyx (a mais grave do Kokoro; F0 ~86 Hz medido), fala lenta (~0.9)
- humanizacao: pausas e velocidade variam por frase (pergunta, numero, contraste, frase curta/longa),
  respiracao sutil antes de frases longas, sem gritar e sem teatralizar.
"""
import re
import numpy as np

SR = 24000
PROFILES = {
    "documentary": dict(voice="bm_george", speed=0.94, breath=False, pause_base=0.30),     # voz aprovada (britanica, documental)
    "sage": dict(voice="am_onyx", speed=0.90, breath=True, pause_base=0.34),
    "narrator": dict(voice="am_michael", speed=1.0, breath=False, pause_base=0.25),
}
EMPH = re.compile(r"\b(never|nobody|no one|wall|oldest|first|only|forever|silence|alone|everything|nothing)\b", re.I)
NUM = re.compile(r"\b(\d[\d,.]*|hundred|thousand|million|billion|trillion)\b", re.I)


def plan_sentence(text, first_in_scene=False, prof=None):
    """-> dict(speed_mult, pause_before, pause_after, breath)."""
    prof = prof or PROFILES["sage"]
    words = len(text.split())
    sp, pb, pa = 1.0, 0.0, prof["pause_base"]
    if words <= 5:
        sp, pa = 0.93, pa + 0.18                        # frase curta: peso, mais devagar
    if words >= 20:
        sp = 1.03                                        # frase longa: fluxo
    if NUM.search(text):
        sp *= 0.97                                       # numeros: clareza
    if EMPH.search(text):
        sp *= 0.96
    if text.endswith("?"):
        pa += 0.3
    if re.match(r"^(But|And yet|Now|Remember|Think)\b", text):
        pb += 0.22                                       # pausa antes de virada
    if first_in_scene:
        pb += 0.15
    return dict(speed_mult=sp, pause_before=pb, pause_after=pa, breath=bool(prof.get("breath") and (words >= 16 or first_in_scene)))


def breath(rng, dur=0.32, gain=0.022):
    n = int(SR * dur)
    x = rng.standard_normal(n)
    sp = np.fft.rfft(x)
    fr = np.fft.rfftfreq(n, 1 / SR)
    sp *= (1 / (1 + (400 / np.maximum(fr, 1)) ** 3)) * (1 / (1 + (fr / 3800) ** 3))
    y = np.fft.irfft(sp, n)
    y /= np.abs(y).max() + 1e-9
    k = np.linspace(0, 1, n)
    env = np.sin(np.pi * k ** 0.8) ** 2
    return (y * env * gain).astype(np.float32)


def f0_median(a, sr=SR):
    """F0 mediano por autocorrelacao (checagem objetiva da 'voz grave')."""
    fr, hop, out = 2048, 1024, []
    for i in range(0, min(len(a), sr * 40) - fr, hop):
        x = a[i:i + fr]
        if np.abs(x).mean() < 0.01:
            continue
        x = x - x.mean()
        ac = np.correlate(x, x, "full")[fr - 1:]
        lo, hi = int(sr / 250), int(sr / 70)
        j = lo + int(np.argmax(ac[lo:hi]))
        if ac[j] > 0.4 * ac[0]:
            out.append(sr / j)
    return float(np.median(out)) if out else 0.0
