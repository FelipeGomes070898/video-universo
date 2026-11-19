"""REGRA DE NOVIDADE: todo video novo (ou 'remodelado') e um video COMPLETAMENTE NOVO.
Nenhuma cena pode repetir o roteiro NEM a construcao visual (camera, corpos, sprites, tempo, etc.) de um video anterior.
Compara o projeto contra todos os projetos listados ANTES dele em projects/registry.json.
  python -m engine.novelty projects/<novo>        (tambem roda automatico no build_film.py)"""
import importlib.util, json, os, re, sys

TEXT_SIM_MAX = 0.20      # similaridade de roteiro (trigramas de palavras) por cena
VISUAL_SIM_MAX = 0.45    # similaridade da construcao visual por cena
SAME_SENT_WORDS = 6      # frase identica com >= N palavras = reaproveitada
_SKIP_KEYS = {"text", "id", "labels", "sfx", "titles", "name", "pad_before", "pad_after"}


def _load(pdir):
    p = os.path.join(pdir, "scenes.py")
    spec = importlib.util.spec_from_file_location("scenes_" + os.path.basename(pdir.rstrip("/")), p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _norm(t):
    return re.findall(r"[a-z0-9']+", t.lower())


def _shingles(words, n=3):
    return {tuple(words[i:i + n]) for i in range(max(0, len(words) - n + 1))}


def _flat(o, path=""):
    out = set()
    if isinstance(o, dict):
        for k, v in o.items():
            if k in _SKIP_KEYS:
                continue
            out |= _flat(v, f"{path}/{k}")
    elif isinstance(o, (list, tuple)):
        for i, v in enumerate(o):
            out |= _flat(v, f"{path}[{i}]")
    elif isinstance(o, str):
        if not o.startswith(("@", "#")):
            out.add((path, o))
    elif isinstance(o, float):
        out.add((path, round(o, 2)))
    elif isinstance(o, (int, bool)):
        out.add((path, o))
    return out


def _jac(a, b):
    return len(a & b) / max(1, len(a | b))


def _scenes(pdir):
    try:
        return list(getattr(_load(pdir), "SCENES", []))
    except Exception:
        return []


def registry(root):
    p = os.path.join(root, "projects", "registry.json")
    return json.load(open(p)) if os.path.exists(p) else {"order": [], "legacy": []}


def check(pdir, root=None):
    root = root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    name = os.path.basename(pdir.rstrip("/"))
    reg = registry(root)
    prev = reg["order"][:reg["order"].index(name)] if name in reg["order"] else reg["order"]
    prev = [x for x in prev if x != name]
    mine = _scenes(pdir)
    issues = []
    for pn in prev:
        old = _scenes(os.path.join(root, "projects", pn))
        old_sent = set()
        for s in old:
            for sent in re.split(r"(?<=[.!?])\s+", s.get("text", "")):
                w = _norm(sent)
                if len(w) >= SAME_SENT_WORDS:
                    old_sent.add(" ".join(w))
        old_txt = [(s.get("id"), _shingles(_norm(s.get("text", "")))) for s in old]
        old_vis = [(s.get("id"), _flat(s)) for s in old]
        for s in mine:
            sid = s.get("id")
            for sent in re.split(r"(?<=[.!?])\s+", s.get("text", "")):
                w = _norm(sent)
                if len(w) >= SAME_SENT_WORDS and " ".join(w) in old_sent:
                    issues.append(f"[{pn}] cena '{sid}': frase repetida: \"{sent.strip()[:70]}\"")
            sh, fl = _shingles(_norm(s.get("text", ""))), _flat(s)
            bt = max(((_jac(sh, h), i) for i, h in old_txt), default=(0, None))
            bv = max(((_jac(fl, h), i) for i, h in old_vis), default=(0, None))
            if bt[0] > TEXT_SIM_MAX:
                issues.append(f"[{pn}] cena '{sid}': roteiro {bt[0]:.0%} igual a '{bt[1]}'")
            if bv[0] > VISUAL_SIM_MAX:
                issues.append(f"[{pn}] cena '{sid}': construcao visual {bv[0]:.0%} igual a '{bv[1]}' (camera/corpos/sprites/tempos)")
    return issues


def gate(pdir, allow=False):
    """Retorna True se pode seguir. Bloqueia se alguma cena repete um video anterior."""
    name = os.path.basename(pdir.rstrip("/"))
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    reg = registry(root)
    if name in reg.get("legacy", []):
        print(f"[novidade] '{name}' e legado (anterior a regra): nao verificado.")
        return True
    issues = check(pdir, root)
    if not issues:
        if name not in reg["order"]:
            reg["order"].append(name)
            json.dump(reg, open(os.path.join(root, "projects", "registry.json"), "w"), indent=1)
        print(f"[novidade] OK: nenhuma cena repete os {len(reg['order'])} videos anteriores.")
        return True
    print(f"[novidade] BLOQUEADO: {len(issues)} repeticao(oes) de videos anteriores. REGRA: video novo = TODAS as cenas novas (roteiro E visual).", file=sys.stderr)
    for i in issues[:25]:
        print("  -", i, file=sys.stderr)
    if allow:
        print("[novidade] --allow-reuse ativo (so com pedido EXPLICITO do usuario).", file=sys.stderr)
        return True
    return False


if __name__ == "__main__":
    sys.exit(0 if gate(sys.argv[1]) else 1)
