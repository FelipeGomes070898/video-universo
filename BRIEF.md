# BRIEF — Documentário "Universo" (escalas do cosmos, YouTube)

Fonte de verdade do padrão. Leia este arquivo e o HANDOFF.md antes de qualquer tarefa.
Não releia nem peça o histórico de chats antigos.

## Formato
- Horizontal 16:9, 1920x1080 (1080p), longa duração (v2 atual: 11:14).
- Canal de publicação: WhyExplained (YouTube). Sempre subir como PRIVADO; publicar é decisão do usuário.
- Título em inglês, estilo "If the Sun Were a Football, a Light-Year Would Reach Salvador".
- Miniatura: 16:9, 1920x1080, modelo "split" (diagonal), foto real e texto grande de até 3 palavras (ex.: "1 LIGHT-YEAR").

## Conteúdo visual
- REGRA PRINCIPAL: lugares, cidades, paisagens, pessoas e acontecimentos reais usam foto/vídeo real licenciado, não gráficos/3D genéricos; animação 2D (mapas, trajetórias, legendas) e 3D só para o que não existe em foto (fenômenos espaciais, escalas, microscópico). Registrar link, autor, plataforma e licença de cada item (credits.txt).
- Não usar material protegido sem autorização; não contornar DRM/restrições de download; sem licença, buscar alternativa licenciada. Busca/recorte de vídeos do YouTube (CC BY) ainda NÃO implementado (pendente, ver HANDOFF).
- Fotos reais livres em vez de gráficos desenhados. Fontes (`pipeline/engine/freemedia.py`, `pipeline/engine/nasa.py`):
  - NASA Image and Video Library (`images-api.nasa.gov`): crédito "NASA/JPL-Caltech" etc.; "NASA does not endorse this video".
  - Openverse (`api.openverse.org`, agrega Flickr, Wikimedia e rawpixel): só licenças CC0, PDM e CC BY (BY-SA só com `--allow-sa`; BY-NC/ND nunca). `page_size` máx. 20; pausar entre chamadas.
  - Wikimedia Commons (vídeos): sujeito a 429; Pixabay e Pexels bloqueiam acesso por script (403).
  - Mapa 3D: relevo SRTM (AWS Terrain Tiles) + NASA Blue Marble (GIBS) em `pipeline/engine/geo.py`.
- Movimento (`pipeline/engine/media.py`): zoom em ease suave; valores usados no um_ano_luz v2 (38 mídias): maioria 1.0→1.08 até 1.0→1.3, alguns zoom-out (1.1→1.0 e 1.5→1.0); pan opcional `[[x0,y0],[x1,y1]]` em -1..1; `fade` 0.9 s (alguns 0.6 s) entre fotos; vinheta 0.28, `fit="auto"` (fundo desfocado se a foto não é 16:9), moldura `mode="inset"` (ex.: `rect=[0.78,0.36,0.34]`) sobre cenas 3D. Em cena: `media=[dict(src="free:ov:<id>" | "nasa:<id>", at="#k", dur|to=..., zoom=[1.0,1.15])]`.
- Crédito na tela em cada foto: "Credit: autor / licença".
- Mapas/relevo com imagens reais da NASA.
- Limites conhecidos: Wikimedia Commons bloqueia downloads por script (sem vídeos reais); muitas fotos têm só 1024 px (ficam suaves em tela cheia).

## Áudio
- Narração com a voz do "senhor sábio": TTS Kokoro-82M ONNX (offline, modelo `onnx-community/Kokoro-82M-v1.0-ONNX`), voz `am_onyx`, perfil `sage`, velocidade 0.923 (ajustada para fechar a duração; padrão do perfil 0.90), 24 kHz. Alternativa aprovada: perfil `documentary` (`bm_george`, 0.94). Pausas/respiração em `pipeline/engine/voice.py`. QC mede F0 da voz (≤ 125 Hz; am_onyx ≈ 86 Hz).
- Comando: `python build_film.py projects/<slug> --profile sage --speed 0.923` (gera narração, SRT, project.json, áudio).
- Trilha com ducking (`pipeline/engine/mix.py`): música ambiente com `volume=0.55` (música normalizada a 0.9 de pico); sidechain `sidechaincompress=threshold=0.015:ratio=9:attack=30:release=700`; voz com highpass 75 Hz, compressor (threshold 0.09, ratio 3, attack 5, release 90, makeup 2.2) e EQ +1.8 dB em 3,2 kHz; mix final `loudnorm=I=-15:TP=-1.5:LRA=9` (alvo -16..-14 LUFS, pico ≤ -1,5 dBFS). Modo `--audio sober` (padrão): sem whooshes; SFX só os pedidos pela cena (≤ 2/min). Na v2 a voz ficou só 4 dB acima da música antes do ducking (mínimo 12): reduzir `music_vol` (ex.: 0.55 → 0.3).
- Vídeo: 24 fps, 1920x1080, H.264 (CRF 18 no render por blocos de 192 frames, 3 workers; 4 workers estouram a memória).

## QC (checar antes de entregar)
- Mapa de curiosidade: nenhuma lacuna maior que 75 s (na v2 há uma de 80 s).
- Conferir quadros do vídeo final, comprimir, gerar thumbnail a partir de foto real limpa (não de quadro com moldura).
- Datas incertas entre fontes: evitar citar (ex.: marco de um dia-luz).

## Entrega no Git
- Pasta `entregas/<slug>/` com: vídeo MP4 dividido em partes de ~95 MB (limite do Git) + COMO_JUNTAR.md + checksums, thumbnail.jpg, captions.srt, publicacao.md, credits.txt.
- Créditos: descrição do vídeo com os nomes dos autores; credits.txt completo (autor, licença, link) para comentário fixado.
- Marcar aviso de conteúdo sintético e usar ~24 tags no YouTube.

## Upload (YouTube)
- `pipeline/tools/youtube_upload.sh <mp4> <metadata.json> [thumb.jpg]`: privado, retomável, sem token no arquivo (o token é injetado pelo proxy via request_credential, host `www.googleapis.com`). Drive grande: `pipeline/tools/drive_upload.sh`. A thumbnail pela API pode falhar por cota diária (suba pelo Studio).
- Pasta do Drive do usuário: id `1zvlboOsBRSv1icTJDJ2KA0DPaT0M_EmQ` (conector só sobe ≤ 10 MB).

## Segurança
- Token do YouTube (escopo youtube.upload) vale ~1 h: pedir pelo campo seguro, nunca gravar em arquivo, revogar em myaccount.google.com/permissions.
- Nunca apagar vídeos antigos sem o usuário pedir.
