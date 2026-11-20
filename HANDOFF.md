# HANDOFF — estado do projeto

## Estado atual
- v2 do documentário "1 Light-Year" pronta e enviada ao YouTube como privada (canal WhyExplained, id YCJz1Gl9PPk).
- Entrega em `entregas/um_ano_luz_v2/` na branch `ccr-1871013c-o689be` do repositório ARCHIVE-STUDIO-AI.
- v1 (gráficos) segue privada no canal (id TEDrrwr2VKI). Usuário decide apagar.

## Verificação em 2026-11-20 (feita comparando com o ARCHIVE-STUDIO-AI; nada foi inventado)
- `pipeline/` idêntico ao `space-video-engine` do ARCHIVE-STUDIO-AI nos scripts de render, narração, thumbnail, QC e upload. Não copiados (fora das 5 categorias): `README.md`, `blender/` (cenas-herói Cycles) e `build_ages.py` (vídeo de eras).
- `youtube_upload.sh` só existe aqui (criado a partir do upload feito na sessão; `drive_upload.sh` é idêntico ao da fonte).
- `entregas/um_ano_luz_v2/`: `publicacao.md`, `credits.txt` e `captions.srt` idênticos aos da fonte; `roteiro.md` contém as 139 frases das 28 cenas (conferido contra `projects/um_ano_luz/scenes.py`). Sem MP4, áudio, fotos ou thumbnail.
- Valores técnicos do BRIEF conferidos no código/projeto: voz `am_onyx` perfil `sage` 0.923 (audio_meta.json), 24 fps, CRF 18, ducking/loudnorm/EQ de `engine/mix.py`, 38 mídias com zoom 1.0→1.08–1.3 (+ zoom-outs) e fade 0.6/0.9. Parâmetros do render por blocos (192 frames, 3 workers) vêm da prática da sessão, não de um arquivo de configuração.
- Varredura de segredos (prefixos de tokens do Google/GitHub, Bearer, chaves privadas) no repositório: nada encontrado; sem arquivos de mídia versionados.

## PENDENTE
- [x] Copiar o pipeline (scripts de render, narração, thumbnail, QC, upload) do repositório ARCHIVE-STUDIO-AI para `pipeline/` aqui. FEITO (49 arquivos; sem tokens; inclui `pipeline/tools/youtube_upload.sh`).
- [x] Copiar roteiro, publicacao.md, credits.txt e captions.srt de `entregas/um_ano_luz_v2/` para `entregas/`. FEITO (só texto: roteiro.md, publicacao.md, credits.txt, captions.srt; sem MP4/áudio/imagens, que seguem no ARCHIVE-STUDIO-AI e no YouTube).
- [ ] Corrigir QC: voz 12 dB acima da música; lacuna de 80 s no mapa de curiosidade.
- [ ] Implementar busca/recorte de vídeos do YouTube só com licença CC BY (YouTube Data API `videoLicense=creativeCommon`) com registro de origem para os créditos. NÃO existe no pipeline.
- [ ] Usuário: publicar a v2, fixar comentário de créditos, subir captions.srt.

## Notas do pipeline copiado
- Código em `pipeline/` (engine/, build_film.py, render_film.py, make_thumb.py, produce.py, tools/). Rodar a partir de `pipeline/`. Dependências: `requirements.txt` + ffmpeg; TTS baixa o modelo Kokoro na 1ª execução.
- Faltam aqui (ficam no ARCHIVE-STUDIO-AI): `projects/<slug>/scenes.py` dos vídeos, `assets/` (fotos baixadas) e `thumb_history.json`. Reconstrua assets com `python -m engine.freemedia` e `python -m engine.nasa`.
- Regras completas anteriores: seção CLAUDE.md do ARCHIVE-STUDIO-AI (novidade: nenhuma cena pode repetir vídeo anterior, `engine/novelty.py`).

## Como começar um chat novo
"Leia BRIEF.md e HANDOFF.md do repositório video-universo e continue: <tarefa>".
