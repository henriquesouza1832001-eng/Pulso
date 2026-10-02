# Scoring

Código: `engine/pulso_engine/scoring/`. O score mede **atividade e sinais públicos detectados**, nunca probabilidade de dano nem veracidade.

## Severidade ≠ Confiança
Um incêndio possivelmente grande com um só relato: severidade 92, confiança 31. Um acidente pequeno confirmado por PRF + imprensa + trânsito: severidade 35, confiança 98. São medidas independentes.

## Confiança (0–100) — `confidence.py`
`10` base `+ min(30, 10·(fontes independentes−1)) + min(20, 7·(tipos de fonte−1)) + 25 se confirmação oficial + 10·consistência geográfica + 5·consistência temporal − 30·contradição − 20·proporção de duplicatas`.
Só redes sociais ("sensor social"): teto de **40**. Cópias da mesma matéria contam como uma fonte (dedup).

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
