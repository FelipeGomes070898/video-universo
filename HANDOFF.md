# HANDOFF — estado do projeto

## Estado atual
- v2 do documentário "1 Light-Year" pronta e enviada ao YouTube como privada (canal WhyExplained, id YCJz1Gl9PPk).
- Entrega em `entregas/um_ano_luz_v2/` na branch `ccr-1871013c-o689be` do repositório ARCHIVE-STUDIO-AI.
- v1 (gráficos) segue privada no canal (id TEDrrwr2VKI). Usuário decide apagar.

## PENDENTE
- [x] Copiar o pipeline (scripts de render, narração, thumbnail, QC, upload) do repositório ARCHIVE-STUDIO-AI para `pipeline/` aqui. FEITO (49 arquivos; sem tokens; inclui `pipeline/tools/youtube_upload.sh`).
- [x] Copiar roteiro, publicacao.md, credits.txt e captions.srt de `entregas/um_ano_luz_v2/` para `entregas/`. FEITO (só texto: roteiro.md, publicacao.md, credits.txt, captions.srt; sem MP4/áudio/imagens, que seguem no ARCHIVE-STUDIO-AI e no YouTube).
- [ ] Corrigir QC: voz 12 dB acima da música; lacuna de 80 s no mapa de curiosidade.
- [ ] Usuário: publicar a v2, fixar comentário de créditos, subir captions.srt.

## Notas do pipeline copiado
- Código em `pipeline/` (engine/, build_film.py, render_film.py, make_thumb.py, produce.py, tools/). Rodar a partir de `pipeline/`. Dependências: `requirements.txt` + ffmpeg; TTS baixa o modelo Kokoro na 1ª execução.
- Faltam aqui (ficam no ARCHIVE-STUDIO-AI): `projects/<slug>/scenes.py` dos vídeos, `assets/` (fotos baixadas) e `thumb_history.json`. Reconstrua assets com `python -m engine.freemedia` e `python -m engine.nasa`.
- Regras completas anteriores: seção CLAUDE.md do ARCHIVE-STUDIO-AI (novidade: nenhuma cena pode repetir vídeo anterior, `engine/novelty.py`).

## Como começar um chat novo
"Leia BRIEF.md e HANDOFF.md do repositório video-universo e continue: <tarefa>".
