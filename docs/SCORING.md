# Scoring

Código: `engine/pulso_engine/scoring/`. O score mede **atividade e sinais públicos detectados**, nunca probabilidade de dano nem veracidade.

## Severidade ≠ Confiança
Um incêndio possivelmente grande com um só relato: severidade 92, confiança 31. Um acidente pequeno confirmado por PRF + imprensa + trânsito: severidade 35, confiança 98. São medidas independentes.

## Confiança (0–100) — `confidence.py`
`10` base `+ min(30, 10·(fontes independentes−1)) + min(20, 7·(tipos de fonte−1)) + 25 se confirmação oficial + 10·consistência geográfica + 5·consistência temporal − 30·contradição − 20·proporção de duplicatas`.
Só redes sociais ("sensor social"): teto de **40**, e o status do evento fica `DETECTED` (nunca `CONFIRMED`, por mais perfis que repitam). Cópias da mesma matéria contam como uma fonte (dedup).

## Pulso Score (0–100) — `pulse.py`
Soma de pontos = peso × componente (0–1). A lista de pontos é o "POR QUE 87?".

| Componente | Peso |
|---|---|
| Severidade | 20 |
| Confiança | 15 |
| Velocidade de sinais | 15 |
| Diversidade de fontes | 15 |
| Anomalia vs. baseline | 15 |
| Recência (decay; meia-vida por categoria, ver Frescor) | 10 |
| Persistência | 5 |
| Alcance geográfico | 5 |

Avisos do INMET: "Grande Perigo" entra como `EMERGENCY` (base 70) e "Perigo" como `WEATHER` (base 55); "Perigo Potencial" não entra por padrão (ADR 0004).

## Frescor: o que é de agora vale mais que o de ontem
O Pulso de um evento é multiplicado por um **fator de frescor** de 0,25 a 1, calculado a partir da idade do sinal mais recente e de uma **meia-vida que depende da categoria** (`HALF_LIFE_BY_CATEGORY` em `scoring/pulse.py`):

| Categoria | Meia-vida |
|---|---|
| Trânsito | 1 h |
| Segurança | 2 h |
| Protesto, eventos | 3 h |
| Emergência, tecnologia | 4 h |
| Clima, infraestrutura | 6 h |
| Economia | 8 h |
| Saúde, política, internacional | 12 h |

`fator = 0,25 + 0,75 · 0,5^(idade / meia-vida)`. O mesmo evento impactante vale muito mais agora do que 12 h atrás (os pontos de **todos** os componentes são escalados, e o "POR QUE N?" continua somando o score). O piso de 0,25 existe porque a história não deixa de existir, só pesa pouco. Limitação conhecida: um aviso oficial ainda vigente (ex.: INMET "Grande Perigo" válido o dia todo) é datado pelo início, então esfria mesmo vigente; renovar o frescor enquanto o aviso estiver em vigor é próximo passo.

## Como um sinal vira evento (qualidade)
- **Categoria**: o **título** decide; só se ele não classificar, o resumo entra (uma palavra solta no resumo não vence o título). Acontecimento **físico** (clima, trânsito, segurança, infraestrutura, emergência, saúde, protesto) de **outro país** (cita país estrangeiro e nenhum lugar nem menção ao Brasil) vira `INTERNATIONAL`, para não contar nas séries brasileiras (engarrafamento na Ucrânia, surto na Flórida, protesto na França). Política e economia ficam como estão, pois citam países estrangeiros o tempo todo em assuntos brasileiros. Só vale o lugar **explícito** no texto, não o estado herdado da fonte regional. Termos genéricos foram tirados do vocabulário de emergência (`bombeiros`, `resgate` soltos classificavam "Vasco tem aval dos Bombeiros" e "resgate de saldo em bets"): ficam as formas específicas (`corpo de bombeiros`, `operação de resgate`, `incêndios`...).
- **Entrada**: chamadas de edição de telejornal ("Assista ao JRO2 desta sexta", "Jornal X 2ª Edição de sexta-feira") são descartadas (`normalizer.is_broadcast_listing`, padrões específicos: "Vídeo: Veja os horários de votação" continua sendo notícia). Palavras de enchimento editorial ("veja", "saiba", "entenda", "2026", "eleições", "vídeo"...) não ligam matérias entre si.
- **Agrupamento** (`processing/clustering.py`): a matéria nova precisa se parecer com **pelo menos 25% dos membros** do grupo (e não com um qualquer), para pautas amplas (ex.: eleições) não encadearem centenas de matérias num só "evento". Sinais de **estados diferentes, ambos com lugar explícito no texto**, nunca se juntam. "Explícito" = confiança de geolocalização >= 55: as faixas são cidade 70, nome de estado 60, **sigla com contexto** ("São Borja, RS", "(MG)") 55, gentílico 50 e estado herdado da fonte regional 35 (os dois últimos não travam o agrupamento).
- **Geografia do texto** (`processing/geo.py`): nomes de cidade que também são pessoa, empresa ou palavra ("Marília Mendonça", "picos de calor", "Porto Seguro" seguradora, "Barreiras comerciais", "Santa Maria", "Mauá") só localizam **com contexto** ("em", "prefeitura de"...); "Mato Grosso do Sul" não casa como Mato Grosso; a sigla "MS" com "Saúde"/"Ministério" no texto não é o estado; "Campeonato Paulista", "Atlético Mineiro" etc. não viram lugar; "alemã" não é a Assembleia do MA.
- **Lugar do evento** (`events.event_place`): o estado **majoritário** ponderado pela confiança da geo. Se os sinais se espalham por 4+ estados, ou nenhum estado domina, ou (em grupos de 4+ sinais) menos de 40% deles têm lugar, o evento fica **sem estado** (pauta nacional), e não em um estado arbitrário: um único sinal que cita o Amazonas em meio a 7 fontes não faz da pauta um evento do AM. Grupos pequenos (1 a 3 sinais), o caso comum de notícia local, podem ser definidos por um sinal só.
- **Publicação** (`events.is_publishable`): vira evento o que tem **2+ fontes independentes**; ou fonte **oficial** com categoria; ou notícia isolada de categoria de impacto (clima, emergência, infraestrutura, saúde, segurança, trânsito) cujo **texto** é de impacto (mortes, desabamento...). Uma matéria isolada de política, economia ou internacional espera uma segunda fonte. Medido em coleta real com 81 fontes: de 1793 para 466 eventos.
- **Severidade** (`events.stats_for`): base da categoria + corroboração (4 pontos por fonte extra, até 20) + **impacto do texto** (0,3 × a importância de `processing/importance.py`, ou seja, até ~18 pontos para mortes e desabamentos). Um relato de rotina e um com vítimas na mesma categoria deixam de ter a mesma severidade; entretenimento nunca sobe.
- **Feed regional**: sem lugar no texto, a notícia herda o estado da fonte (`state`), com confiança 35.

## Nível PULSO 1–5
1 Normal · 2 Atenção (score ≥ 30) · 3 Elevado (≥ 55 e confiança ≥ 40) · 4 Crítico (≥ 75, confiança ≥ 70, ≥ 2 fontes independentes) · 5 Emergência (≥ 90, confiança ≥ 85, **fonte oficial** e ≥ 3 fontes independentes). Social isolado nunca passa do nível 3.

**Piso para alerta oficial extremo.** Se o evento contém um alerta de uma **fonte de alerta oficial** (`"alert_source": true` em `sources.json`: hoje o INMET e a Defesa Civil/IDAP) classificado como `EMERGENCY` (INMET "Grande Perigo", Defesa Civil "Extreme"), o nível nunca fica abaixo de **3 (Elevado)**: o próprio órgão já declarou o perigo e o score ainda não o enxerga (a anomalia só existe com 12 h de histórico). O piso **não altera o score**; aparece no "POR QUE?" como um item de 0 pontos ("Alerta oficial de risco extremo (piso nível 3)") e a soma dos pontos continua igual ao score. Comunicado de órgão que não é fonte de alerta, severidade menor e notícia não recebem o piso. O nível 4 e o 5 continuam exigindo confirmação por 2+ e 3+ fontes independentes.

Os limiares são ponto de partida: calibrar com dados reais (ADR a cada mudança).

## Anomalia e baseline (implementado)
`engine/pulso_engine/baseline.py` e `anomaly.py`. O histórico vem de `series` (contagens de 5 min). O baseline é a média e o desvio exponencialmente ponderados (EWMA) das contagens **por hora** do mesmo escopo e categoria, excluindo a hora corrente. Anomalia = `z / 4` limitada a 0–1, com `z` em desvios acima do normal.

Regra de honestidade: com menos de **12 horas** de histórico o baseline é **inválido** e a anomalia vale 0. Também é inválido quando o histórico é **esparso**: é preciso haver sinal em ao menos 6 horas e em 1/3 das horas, porque a hora sem linha vira 0 e um 0 pode ser calmaria **ou** lacuna de coleta (o sistema não distingue). Um "normal" feito quase só de zeros faria 4 sinais parecerem uma anomalia enorme. O sistema nunca afirma que algo é anormal sem saber o que é normal. A anomalia entra no Pulso com peso 15 e aparece no "POR QUE N?".

Limitações conhecidas: o baseline ainda não separa hora do dia e dia da semana (precisa de semanas de dados); e a clusterização é recalculada a cada rodada, então o `event_id` de uma história pode mudar quando a notícia mais antiga sai dos feeds (a solução é clusterização com estado, a próxima etapa).

## Rotina de campanha pesa pouco
Textos de campanha e rotina eleitoral (`importance.ROUTINE`: comício, carreata, caminhada, debate, sabatina, horário eleitoral, pesquisas Datafolha/Quaest/Ipec etc.) são eventos agendados e esperados. Quando TODOS os textos de um evento são rotina e nenhum traz sinal de impacto (tiers A/B) ou de ruptura (`importance.DISRUPTION`: tumulto, ataque, feridos, tiros, bomba...), a severidade fica limitada a `ROUTINE_SEVERITY_CAP` (20). "Comício termina em tumulto com feridos" NÃO é rotina e pontua normalmente.
