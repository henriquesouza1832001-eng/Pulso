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
| Recência (decay, meia-vida 90 min) | 10 |
| Persistência | 5 |
| Alcance geográfico | 5 |

## Nível PULSO 1–5
1 Normal · 2 Atenção (score ≥ 30) · 3 Elevado (≥ 55 e confiança ≥ 40) · 4 Crítico (≥ 75, confiança ≥ 70, ≥ 2 fontes independentes) · 5 Emergência (≥ 90, confiança ≥ 85, **fonte oficial** e ≥ 3 fontes independentes). Social isolado nunca passa do nível 3.

Os limiares são ponto de partida: calibrar com dados reais (ADR a cada mudança).

## Anomalia e baseline (implementado)
`engine/pulso_engine/baseline.py` e `anomaly.py`. O histórico vem de `series` (contagens de 5 min). O baseline é a média e o desvio exponencialmente ponderados (EWMA) das contagens **por hora** do mesmo escopo e categoria, excluindo a hora corrente. Anomalia = `z / 4` limitada a 0–1, com `z` em desvios acima do normal.

Regra de honestidade: com menos de **12 horas** de histórico o baseline é **inválido** e a anomalia vale 0. O sistema nunca afirma que algo é anormal sem saber o que é normal. A anomalia entra no Pulso com peso 15 e aparece no "POR QUE N?".

Limitações conhecidas: o baseline ainda não separa hora do dia e dia da semana (precisa de semanas de dados); e a clusterização é recalculada a cada rodada, então o `event_id` de uma história pode mudar quando a notícia mais antiga sai dos feeds (a solução é clusterização com estado, a próxima etapa).
