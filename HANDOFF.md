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

## Sessão 2026-11-23 — integração com o canal (somente leitura)
CONCLUÍDO E TESTADO (offline): `pipeline/channel/` + `pipeline/channel.py`; `python channel.py selftest` = 22 verificações OK (GET-only, hosts permitidos, token fora do git, métrica indisponível não inventada, janelas 24 h/7 d/28 d, IC de CTR, retenção × roteiro, export/import, porta da estratégia). Thumbs testado em 1 imagem local. `produce.py init` agora exige relatório estratégico (testado: bloqueia sem relatório, libera com, `--sem-estrategia` pula). Banco semente + `analises/estrategia_2026-11-23.md` + `analises/historico/` gerados.
PRIMEIRO USO REAL (2026-11-23, modo nuvem com token somente leitura): canal WhyExplained (5 inscritos, 3 vídeos) sincronizado. Funcionou: Data API, views, tempo de exibição, % média vista, inscritos, séries diárias → d1/d7/d28, fontes de tráfego, curva de retenção do V1 (-DuVk_uUt8U). Não veio: curva de retenção do V3 e do V2 (volume), país/idade/gênero (volume mínimo), impressões e CTR (HTTP 400 "query not supported" → só pelos prints do Studio). Achado: V1 perde 70 p.p. da audiência até 21 s (cena hook, frase do pedido de comentário; base ~10 views = ruído alto). Vídeos registrados em `productions` (the_wall, the_wall_hd, voyager_one).
NÃO TESTADO: OAuth local (`connect/refresh/disconnect`), download da miniatura publicada, Reporting API (não implementada).

NOTA: a partir desta sessão o código novo (`pipeline/channel/`, `channel.py`, porta de estratégia no `produce.py`) existe SÓ no video-universo; o `pipeline/` aqui passa a ser a fonte da verdade (o ARCHIVE-STUDIO-AI não tem essas mudanças).

## Produção Cassini (2026-11-23) — pronta, NÃO publicada
- Vídeo `cassini_final_dive` (Why NASA Flew Its Own Spacecraft Into Saturn), 10:10, entregue em `entregas/cassini_final_dive/` do ARCHIVE-STUDIO-AI (branch `ccr-1871013c-o689be`, partes de 95 MB + SHA256 conferido) e textos em `entregas/cassini_final_dive/` aqui (roteiro, publicacao, credits, captions). Dossiê (18 fatos com fonte) em `projects/cassini_final_dive/dossier.json` no ARCHIVE-STUDIO-AI. QC: sem FAIL; restam WARN "cena sem corte 61 s (launch)" e MANUAL "voz humana (ouvir)". Registrado em `productions` (sem video_id até publicar).
- Gerado com base em `analises/estrategia_2026-11-23.md` (gancho com mídia real, sem CTA em 30 s, CTA único no pico).

## PENDENTE
- [x] Copiar o pipeline (scripts de render, narração, thumbnail, QC, upload) do repositório ARCHIVE-STUDIO-AI para `pipeline/` aqui. FEITO (49 arquivos; sem tokens; inclui `pipeline/tools/youtube_upload.sh`).
- [x] Copiar roteiro, publicacao.md, credits.txt e captions.srt de `entregas/um_ano_luz_v2/` para `entregas/`. FEITO (só texto: roteiro.md, publicacao.md, credits.txt, captions.srt; sem MP4/áudio/imagens, que seguem no ARCHIVE-STUDIO-AI e no YouTube).
- [x] QC voz 12 dB acima da música: resolvido no Cassini (--music-vol 0.12 = 13 dB). Para a v2 do um_ano_luz ainda vale refazer o áudio. [x] Lacuna do mapa de curiosidade: resolvida no Cassini (loops cobrindo a linha do tempo); v2 do um_ano_luz ainda tem 80 s.
- [ ] A cada análise: autorizar de novo (token ~1 h; nuvem: `request_credential` para `www.googleapis.com` E `youtubeanalytics.googleapis.com`, escopos youtube.readonly + yt-analytics.readonly), `channel.py sync`, `channel.py strategy`. Vídeos com id começando por `-` precisam de `--` antes do id em `channel.py retention`.
- [ ] Após ~48 h de cada vídeo: `sync` + `retention <video_id> <slug>`; depois 7 d e 28 d; registrar com `channel.py register` e `compare`.
- [ ] Implementar busca/recorte de vídeos do YouTube só com licença CC BY (YouTube Data API `videoLicense=creativeCommon`) com registro de origem para os créditos. NÃO existe no pipeline.
- [ ] Usuário: publicar o Cassini (título, descrição, tags, thumbnails A/B, `captions.srt`, comentário fixado com `credits.txt`); depois `channel.py register cassini_final_dive --video-id <id>` e medir em 24 h/7 d/28 d. Escolher a thumbnail A (Saturno) ou B (rosto) no teste A/B do Studio.
- [ ] Usuário: publicar a v2, fixar comentário de créditos, subir captions.srt.

## Notas do pipeline copiado
- Código em `pipeline/` (engine/, build_film.py, render_film.py, make_thumb.py, produce.py, tools/). Rodar a partir de `pipeline/`. Dependências: `requirements.txt` + ffmpeg; TTS baixa o modelo Kokoro na 1ª execução.
- Faltam aqui (ficam no ARCHIVE-STUDIO-AI): `projects/<slug>/scenes.py` dos vídeos, `assets/` (fotos baixadas) e `thumb_history.json`. Reconstrua assets com `python -m engine.freemedia` e `python -m engine.nasa`.
- Regras completas anteriores: seção CLAUDE.md do ARCHIVE-STUDIO-AI (novidade: nenhuma cena pode repetir vídeo anterior, `engine/novelty.py`).

## Como começar um chat novo
"Leia o BRIEF.md e o HANDOFF.md do repositório video-universo. Consulte as análises atualizadas do meu canal no YouTube e continue o projeto seguindo integralmente os padrões, configurações e diretrizes documentados."
