"""BANCO DE ASSETS com licenca/fonte/autenticidade. Imagem real exige fonte+licenca; nunca vira 'IA' sem rotulo."""
import json
import os

KINDS = ["real", "illustration", "reconstruction", "simulation", "ai"]
LICENSES_OK = ["public-domain", "cc0", "cc-by", "cc-by-sa", "licensed", "own", "procedural"]


def load(path):
    return json.load(open(path, encoding="utf-8")) if os.path.exists(path) else []


def validate(items, base="."):
    out = []
    for a in items:
        if a.get("autenticidade") not in KINDS:
            out.append(f"{a.get('id')}: autenticidade invalida")
        if a.get("autenticidade") == "real" and not (a.get("fonte") and a.get("licenca") in LICENSES_OK):
            out.append(f"{a.get('id')}: imagem REAL sem fonte/licenca valida")
        if a.get("path") and not os.path.exists(os.path.join(base, a["path"])):
            out.append(f"{a.get('id')}: arquivo ausente {a['path']}")
    return out


def credits(items):
    return [f"{a['id']}: {a.get('credito') or a.get('fonte')} ({a.get('licenca')})" for a in items if a.get("autenticidade") == "real"]
