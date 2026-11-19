#!/usr/bin/env python3
"""Pre-producao: python plan.py projects/<nome>/project.json  ->  projects/<nome>/plan/*"""
import json, os, sys
from engine.planning import analyze, storyboard, audit, publish

VOICE = {"status": "ESPECIFICACAO (sem motor TTS neste ambiente)", "identidade": "senhor sabio",
         "caracteristicas": ["masculina", "grave", "serena", "pausada", "natural, nao robotica"],
         "humanizacao": ["pausas antes de informacao importante", "variacao leve de velocidade", "respiracao sutil", "sem gritar"],
         "mixagem": "voz sempre prioritaria; musica com ducking; SFX baixos"}
CURIOSITY = {"status": "PENDENTE: exige pesquisa real (web/LLM) e roteiro", "estrutura": ["PERGUNTA", "PROMESSA", "DESCOBERTA", "NOVA PERGUNTA", "EXPLICACAO", "CONSEQUENCIA", "NOVA DESCOBERTA"], "itens": []}


def main(path):
    p = json.load(open(path, encoding="utf-8"))
    d = os.path.join(os.path.dirname(path), "plan")
    os.makedirs(d, exist_ok=True)
    scenes, assets, trace = storyboard.build(p)
    rep = audit.audit(p, scenes)
    files = {"00_formato.json": analyze.analyze_format(p["briefing"]), "01_curiosity_map.json": CURIOSITY, "02_storyboard.json": scenes,
             "03_assets.json": assets, "04_retention_audit.json": rep, "05_publication.json": publish.package(p),
             "06_voice_direction.json": VOICE, "07_traceability.json": trace}
    for n, v in files.items():
        json.dump(v, open(os.path.join(d, n), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    with open(os.path.join(d, "08_qa_checklist.md"), "w", encoding="utf-8") as f:
        f.write("# Checklist final\n\n" + "\n".join(f"- [{r['status']}] {r['verificacao']}: {r['detalhe']}" for r in rep) + "\n")
    print("plano em", d)
    for r in rep:
        print(f"  [{r['status']:6}] {r['verificacao']}: {r['detalhe']}")


if __name__ == "__main__":
    main(sys.argv[1])
