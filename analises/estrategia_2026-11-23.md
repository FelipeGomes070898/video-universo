# Estrategia para o proximo video — 2026-11-23

Dados: 3 video(s), 0 com amostra suficiente. Ultima sincronizacao com o YouTube: NUNCA (so dados manuais/semente).

- Limite: 3 de 3 videos com amostra insuficiente (<100 views e <1000 impressoes)
- Limite: comparacoes por grupo so valem com n>=3 videos por grupo; abaixo disso sao apenas hipoteses
- Limite: retencao/CTR podem demorar ~2 dias; 24 h e aproximado (granularidade diaria da API)

## 1. O que funcionou nos ultimos videos?  _(confianca: baixa)_

Maior retencao media: Voyager 1 Just Reached One Light-Day From Earth —  (27.0%); We Traveled to the Edge of the Universe — and Hit  (18.5%)

## 2. O que nao funcionou?  _(confianca: baixa)_

queda forte nos 30 s iniciais em 'We Traveled to the Edge of the Universe ' (retem 40.0%); 3 video(s) sem inscritos nem curtidas

## 3. Quais assuntos demonstraram maior potencial?  _(confianca: insuficiente)_

NENHUM tema tem amostra suficiente (n>=3 videos). Recorrentes (hipoteses): wall

## 4. Quais erros devem ser evitados?  _(confianca: baixa)_

abertura fraca em 'We Traveled to the Edge of the Univ'

## 5. Como melhorar a introducao?  _(confianca: baixa)_

retencao media aos 30 s: 40.0%. Regra para o proximo video: primeiro evento visual real (foto/video/mapa) em ate 5 s, promessa concreta em ate 15 s, nenhuma explicacao de contexto antes da primeira pergunta; medir de novo aos 30 s.

## 6. Qual abordagem narrativa pode aumentar a retencao?  _(confianca: baixa)_

Estrutura pergunta -> promessa -> descoberta -> nova pergunta (mapa de curiosidade), com 'ponto de virada' a cada ~60-75 s; trechos de explicacao no maximo 45 s sem evento visual. Validar comparando a curva de retencao por capitulo contra o roteiro (retention.map_drops).

## 7. Qual duracao e adequada ao tema e ao historico?  _(confianca: insuficiente)_

sem 2 videos por faixa de duracao: nao ha base para otimizar. Experimento: alternar 8-12 min e 12-16 min e comparar retencao media (avg_view_pct) e tempo de exibicao.

## 8. Que estilo visual e de thumbnail merece ser testado?  _(confianca: insuficiente)_

menos de 2 videos com >= 1000 impressoes: nao da para dizer que uma miniatura e melhor. Plano: teste A/B do Studio com 2-3 miniaturas mudando UMA variavel por vez (texto, cor ou elemento principal), mesma historia/titulo, ate ~1000 impressoes por variante.

## 9. Quais mudancas podem aumentar o tempo de exibicao?  _(confianca: baixa)_

Cortar/encurtar os trechos onde a curva cai (ver quedas por cena em 'channel.py retention'); evitar introducao com contexto; manter evento visual a cada <= 30 s; capitulos com promessa clara. Duracao media atual: We Traveled to the Edge of the: 132s (18%), THE WALL: 3s (n/d), Voyager 1 Just Reached One Lig: 282s (27%).

## 10. Quais oportunidades existem para conquistar novos inscritos?  _(confianca: baixa)_

inscritos/1000 views: We Traveled to the Edge of the 0.0, THE WALL 0.0. fontes de trafego principais: YT_SUGGESTED (11 views), YT_CHANNEL (6 views), YT_SEARCH (1 views). Acao: pedir a inscricao no PICO de interesse (apos a maior descoberta), nao so no fim; fixar comentario com pergunta.

## Estrategia especifica para o proximo video

- **tema**: decisao do usuario com base nos 'temas' acima; evitar repetir tema/titulo de video publicado ha <= 7 dias
- **duracao**: faixa conforme a pergunta 7 (experimento se insuficiente)
- **introducao**: primeiro evento visual real <= 5 s; promessa <= 15 s; sem contexto antes da 1a pergunta
- **titulo**: especifico e concreto (numero/pergunta/objeto), sem promessa falsa; 1 variavel por teste
- **thumbnail**: teste A/B de 2-3 variantes, 1 variavel por vez; texto <= 3 palavras; completar o titulo (nao repetir)
- **medicao**: registrar no banco (channel.py register) e medir em 24 h (dias 0-1), 7 dias e 28 dias; comparar com o video anterior por retencao 30 s, avg_view_pct, CTR (com IC) e inscritos/1000 views

_Nada aqui e conclusao estatistica quando a confianca for baixa/insuficiente: sao hipoteses a testar._
