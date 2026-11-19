# BRIEF — Documentário "Universo" (escalas do cosmos, YouTube)

Fonte de verdade do padrão. Leia este arquivo e o HANDOFF.md antes de qualquer tarefa.
Não releia nem peça o histórico de chats antigos.

## Formato
- Horizontal 16:9, 1920x1080 (1080p), longa duração (v2 atual: 11:14).
- Canal de publicação: WhyExplained (YouTube). Sempre subir como PRIVADO; publicar é decisão do usuário.
- Título em inglês, estilo "If the Sun Were a Football, a Light-Year Would Reach Salvador".
- Miniatura: 16:9, 1920x1080, modelo "split" (diagonal), foto real e texto grande de até 3 palavras (ex.: "1 LIGHT-YEAR").

## Conteúdo visual
- Fotos reais livres em vez de gráficos desenhados: NASA e Openverse/Wikimedia (licenças livres).
- Movimento: zoom e deslocamento suaves sobre as fotos paradas.
- Crédito na tela em cada foto: "Credit: autor / licença".
- Mapas/relevo com imagens reais da NASA.
- Limites conhecidos: Wikimedia Commons bloqueia downloads por script (sem vídeos reais); muitas fotos têm só 1024 px (ficam suaves em tela cheia).

## Áudio
- Narração com a voz do "senhor sábio" (voz já definida no projeto; registrar aqui o nome exato após copiar o motor).
- Trilha com ducking: a voz deve ficar pelo menos 12 dB acima da música (na v2 ficou só 4 dB antes do ducking, corrigir).

## QC (checar antes de entregar)
- Mapa de curiosidade: nenhuma lacuna maior que 75 s (na v2 há uma de 80 s).
- Conferir quadros do vídeo final, comprimir, gerar thumbnail a partir de foto real limpa (não de quadro com moldura).
- Datas incertas entre fontes: evitar citar (ex.: marco de um dia-luz).

## Entrega no Git
- Pasta `entregas/<slug>/` com: vídeo MP4 dividido em partes de ~95 MB (limite do Git) + COMO_JUNTAR.md + checksums, thumbnail.jpg, captions.srt, publicacao.md, credits.txt.
- Créditos: descrição do vídeo com os nomes dos autores; credits.txt completo (autor, licença, link) para comentário fixado.
- Marcar aviso de conteúdo sintético e usar ~24 tags no YouTube.

## Segurança
- Token do YouTube (escopo youtube.upload) vale ~1 h: pedir pelo campo seguro, nunca gravar em arquivo, revogar em myaccount.google.com/permissions.
- Nunca apagar vídeos antigos sem o usuário pedir.
