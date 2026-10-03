# Reliability Lab

## Objetivo

O Reliability Lab é uma camada Python isolada para avaliar candidatos V2 sem
chamá-los no pipeline, Worker, API ou interface. Ele não altera flags, scores,
alertas nem previsões públicas. A pergunta que responde é: um candidato
melhora a previsão sem piorar falsos positivos, recall ou calibração?

## Componentes

- `validation/metrics.py`: métricas puras já reutilizadas pela comparação
  shadow (Brier/Brier Skill, log loss, ECE, precision, recall, F1, FPR, FNR,
  cobertura, abstenção, lead time e delay de detecção).
- `validation/replay.py`: relógio e dataset determinísticos. Cada item separa
  `event_time` de `published_at`, `observed_at`, `fetched_at` e
  `confirmed_at`.
- `validation/scenarios.py`: controles sintéticos, começando por
  `normal_weekday`, para medir falsos positivos em dias sem evento relevante.
- `validation/reliability_gate.py`: decisão pura e configurável de promoção.
- `validation/report.py`: relatório serializável de uma avaliação.

## Replay e proteção contra leakage

`ReplayItem.event_time` diz quando algo aconteceu; não é autorização para o
motor conhecer o dado. O item só aparece quando todos os timestamps de
disponibilidade que ele possui já ocorreram. Isso é conservador: um dado
publicado às 17:00, mas obtido pelo PULSO às 17:45, só aparece às 17:45.

O replay nunca usa `datetime.now()`, aleatoriedade ou ordem de `set`. A linha
do tempo é ordenada por timestamp e `item_id`; duas execuções do mesmo dataset
produzem os mesmos snapshots. Os testes cobrem explicitamente o corte das
17:30: sinais anteriores são visíveis, notícia futura e confirmação oficial
futura não são.

## Reliability Gate

Os estágios conceituais são `SHADOW`, `EXPERIMENTAL`, `CANARY`, `ACTIVE` e
`REJECTED`. O gate retorna apenas `PASS`, `FAIL` ou `INSUFFICIENT_DATA`; ele
não muda estágio nem configurações por conta própria.

`ReliabilityGateConfig` concentra os critérios iniciais do plano V2:

- pelo menos 200 amostras;
- melhoria relativa de Brier de pelo menos 5%;
- FPR não piora mais de 10% relativo;
- recall não cai mais de 5% relativo;
- ECE não piora quando a proteção de calibração está ligada.

Menos que 200 amostras resulta obrigatoriamente em `INSUFFICIENT_DATA`.
Melhora de Brier não compensa regressão de FPR, recall ou calibração.

## Relatório

`CandidateModelReport.to_dict()` fornece candidato, amostras, métricas V1 e
candidatas, delta de Brier/Brier skill, resultado e justificativas. O campo
`generated_at` é somente metadado do relatório e não participa da decisão.

## Limitações atuais

O Lab ainda é em memória: não grava shadow results, registry nem timelines e
não executa candidatos reais contra o pipeline. `event_time` dos objetos de
produção ainda não é um contrato separado; os datasets de replay modelam a
distinção sem alterar contratos. Mais cenários adversariais e dados históricos
reais serão necessários antes de qualquer promoção.

## Como executar

```powershell
cd engine
py -m pytest tests/reliability -q
py -m pytest -q
```
