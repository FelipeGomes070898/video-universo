# Estrategia para o proximo video — 2026-11-23

Dados: 3 video(s), 0 com amostra suficiente. Ultima sincronizacao com o YouTube: 2026-11-23T10:47:31.

- Limite: 3 de 3 videos com amostra insuficiente (<100 views e <1000 impressoes)
- Limite: comparacoes por grupo so valem com n>=3 videos por grupo; abaixo disso sao apenas hipoteses
- Limite: retencao/CTR podem demorar ~2 dias; 24 h e aproximado (granularidade diaria da API)

## 1. O que funcionou nos ultimos videos?  _(confianca: baixa)_

Maior retencao media: Voyager 1 Just Reached One Light-Day From Earth —  (28.2%); We Traveled to the Edge of the Universe — and Hit  (20.8%)

## 2. O que nao funcionou?  _(confianca: baixa)_

queda forte nos 30 s iniciais em 'We Traveled to the Edge of the Universe ' (retem 36.8%); 2 video(s) sem inscritos nem curtidas

## 3. Quais assuntos demonstraram maior potencial?  _(confianca: insuficiente)_

NENHUM tema tem amostra suficiente (n>=3 videos). Recorrentes (hipoteses): escala do universo

## 4. Quais erros devem ser evitados?  _(confianca: baixa)_

canibalizacao: 'We Traveled to the Edge of the Univ' x 'We Traveled to the Edge of the Univ' publicados com 1 dia(s) de diferenca; abertura fraca em 'We Traveled to the Edge of the Univ'

## 5. Como melhorar a introducao?  _(confianca: baixa)_

retencao media aos 30 s: 36.8%. Regra para o proximo video: primeiro evento visual real (foto/video/mapa) em ate 5 s, promessa concreta em ate 15 s, nenhuma explicacao de contexto antes da primeira pergunta; medir de novo aos 30 s.

## 6. Qual abordagem narrativa pode aumentar a retencao?  _(confianca: baixa)_

Estrutura pergunta -> promessa -> descoberta -> nova pergunta (mapa de curiosidade), com 'ponto de virada' a cada ~60-75 s; trechos de explicacao no maximo 45 s sem evento visual. Validar comparando a curva de retencao por capitulo contra o roteiro (retention.map_drops).

## 7. Qual duracao e adequada ao tema e ao historico?  _(confianca: insuficiente)_

sem 2 videos por faixa de duracao: nao ha base para otimizar. Experimento: alternar 8-12 min e 12-16 min e comparar retencao media (avg_view_pct) e tempo de exibicao.

## 8. Que estilo visual e de thumbnail merece ser testado?  _(confianca: insuficiente)_

menos de 2 videos com >= 1000 impressoes: nao da para dizer que uma miniatura e melhor. Plano: teste A/B do Studio com 2-3 miniaturas mudando UMA variavel por vez (texto, cor ou elemento principal), mesma historia/titulo, ate ~1000 impressoes por variante.

## 9. Quais mudancas podem aumentar o tempo de exibicao?  _(confianca: baixa)_

Cortar/encurtar os trechos onde a curva cai (ver quedas por cena em 'channel.py retention'); evitar introducao com contexto; manter evento visual a cada <= 30 s; capitulos com promessa clara. Duracao media atual: We Traveled to the Edge of the: 144s (21%), We Traveled to the Edge of the: 0s (0%), Voyager 1 Just Reached One Lig: 288s (28%).

## 10. Quais oportunidades existem para conquistar novos inscritos?  _(confianca: baixa)_

inscritos/1000 views: We Traveled to the Edge of the 0.0, Voyager 1 Just Reached One Lig 0.0. fontes de trafego principais: RELATED_VIDEO (11 views), SUBSCRIBER (10 views), NO_LINK_OTHER (1 views). Acao: pedir a inscricao no PICO de interesse (apos a maior descoberta), nao so no fim; fixar comentario com pergunta.

## Achados por video (dados reais)

### We Traveled to the Edge of the Universe — and Hit a Wall (10 views)
_curva baseada em ~10 visualizacoes: cada espectador pesa ~10 p.p. (ruido alto)_
- queda de 70 p.p. em 21 s | cena `hook` | frase: "Tell me in the comments: what's the farthest thing you can see from Earth with t" | ultimo evento visual ha 14.8 s
- queda de 10 p.p. em 132 s | cena `venus` | frase: "From here, the numbers start to race." | ultimo evento visual ha 17.5 s
- queda de 10 p.p. em 167 s | cena `mercury` | frase: "And yet, inside craters at the poles that never see sunlight, there's water ice." | ultimo evento visual ha 6.2 s
- roteiro: lacuna visual de 35 s sem evento (6-41 s)
- roteiro: lacuna visual de 31 s sem evento (607-638 s)
- roteiro: trechos repetidos (>=3x): the farthest thing; look at the; at the beam; to get here

### We Traveled to the Edge of the Universe — and Hit a Wall (0 views)
- roteiro: lacuna visual de 48 s sem evento (7-54 s)
- roteiro: lacuna visual de 30 s sem evento (76-106 s)
- roteiro: lacuna visual de 44 s sem evento (115-159 s)
- roteiro: lacuna visual de 30 s sem evento (186-216 s)
- roteiro: lacuna visual de 32 s sem evento (216-248 s)
- roteiro: lacuna visual de 34 s sem evento (287-322 s)
- roteiro: lacuna visual de 33 s sem evento (322-354 s)
- roteiro: lacuna visual de 44 s sem evento (430-474 s)
- roteiro: lacuna visual de 41 s sem evento (582-624 s)
- roteiro: lacuna visual de 33 s sem evento (653-686 s)
- roteiro: lacuna visual de 34 s sem evento (791-825 s)
- roteiro: trechos repetidos (>=3x): the farthest thing; with the naked; the naked eye; look at the
- roteiro: cenas muito longas (>60 s): moon

### Voyager 1 Just Reached One Light-Day From Earth — How It Survived 49 Y (15 views)
_curva baseada em ~15 visualizacoes: cada espectador pesa ~7 p.p. (ruido alto)_
- roteiro: lacuna visual de 38 s sem evento (462-501 s)
- roteiro: lacuna visual de 32 s sem evento (690-722 s)
- roteiro: trechos repetidos (>=3x): one light day; six billion kilometers; uranus and neptune; the solar system

## Estrategia especifica para o proximo video

- **tema**: decisao do usuario com base nos 'temas' acima; evitar repetir tema/titulo de video publicado ha <= 7 dias
- **duracao**: faixa conforme a pergunta 7 (experimento se insuficiente)
- **introducao**: primeiro evento visual real <= 5 s; promessa <= 15 s; sem contexto antes da 1a pergunta | DADO REAL: 'We Traveled to the Edge of the Universe ' perdeu 70 p.p. da audiencia ate 21 s (cena hook, frase "Tell me in the comments: what's the farthest thing you can s...", ultimo evento visual ha 14.8 s), com so ~10 views (ruido alto, mas e a unica evidencia): nao pedir comentario/CTA nem fazer pergunta ao publico nos primeiros 30 s; abrir com imagem real e a promessa
- **titulo**: especifico e concreto (numero/pergunta/objeto), sem promessa falsa; 1 variavel por teste
- **thumbnail**: teste A/B de 2-3 variantes, 1 variavel por vez; texto <= 3 palavras; completar o titulo (nao repetir)
- **medicao**: registrar no banco (channel.py register) e medir em 24 h (dias 0-1), 7 dias e 28 dias; comparar com o video anterior por retencao 30 s, avg_view_pct, CTR (com IC) e inscritos/1000 views

_Nada aqui e conclusao estatistica quando a confianca for baixa/insuficiente: sao hipoteses a testar._
