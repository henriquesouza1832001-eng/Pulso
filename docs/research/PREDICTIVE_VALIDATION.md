# Validação preditiva do PULSO

Data de corte: 2026-10-03. Responsável pela medição: Codex/red team. Este relatório não promove V1 ou V2 e não trata dados sintéticos como evidência operacional.

## Pergunta e target

Target científico proposto para o Forecast V2: `P(event reaches PULSO ALERT >= 3 within horizon)`. Cada horizonte (15, 30, 60, 120 e 360 minutos) é uma tarefa diferente e nunca pode dividir a mesma métrica. A resolução é determinística: `Y=1` se o alvo ocorrer na janela; `Y=0` se a janela se encerrar sem ocorrer; `UNKNOWN` se cobertura, retenção ou timestamps impedirem a resolução. `UNKNOWN` não é negativo.

O V1 hoje prevê variação de Pulso em 60 minutos, não implementa ainda este target de evento. Portanto, qualquer comparação V1/V2 precisa registrar target, `prediction_time`, horizonte, geo, categoria, `data_cutoff`, versões de modelo/features e status.

## Dataset e estado atual

| Fonte | Estado | Uso científico |
|---|---|---|
| Forecasts públicos V1 | 20 resolvidas, 4 abertas, 4 anuladas | fotografia operacional, não amostra suficiente |
| Shadow V1×V2 | 0 linhas resolvidas | não avaliável |
| Golden events | 0 COMPLETE de 9 planejados | não avaliável |
| Negative windows | 0 COMPLETE de 8 planejadas | não avaliável |
| Corpus Geo | 14 manchetes editoriais | só regressão de geolocalização, não previsão |

A fotografia pública de `/api/forecasts/track-record` em 2026-10-03 tem 0 positivos: Brier médio `0,01961455`, probabilidade média `0,09928`, taxa observada `0` e Brier de referência `0`. Logo, Brier Skill é indefinido; Brier absoluto não demonstra skill e há sinal inicial de sobreprevisão. Não calibrar nem ajustar pesos com esta amostra.

## Protocolo de avaliação

`validation.temporal.walk_forward_splits` fornece janelas consecutivas `train → calibration → test`; `final_holdout` reserva o trecho final intocado. Feature selection, limiar, calibrador e pesos usam somente treino/calibração. O holdout final é usado uma vez como exame. A unidade de reamostragem e intervalo de confiança deve ser `event_id`, nunca forecast individual quando houver múltiplos forecasts por evento.

Comparar cada challenger contra: taxa-base, taxa-base sazonal, persistência, anomalia-only, velocidade-only, Pulso atual e V1. Reportar Brier, Brier Skill, log loss, ECE acompanhado de bins/N, precisão, recall, FPR/FNR, cobertura, abstenção e lead time por horizonte. Accuracy não é métrica principal em evento raro.

## Calibração e abstenção

Calibradores (sigmoid/isotonic) só podem ser ajustados na janela de calibração e apenas se melhorarem fora do tempo. Sem amostra suficiente: `UNCALIBRATED_EXPERIMENTAL`. Relatar intercept/slope quando a amostra permitir. A saída deve poder ser `INSUFFICIENT_DATA`, `UNKNOWN` ou `DISPUTED`; medir qualidade contra cobertura, sem esconder abstenções.

## Features e ablações

Inventário a registrar por experimento: baseline, anomalia, velocidade, aceleração, persistência, confiança, severidade, diversidade de origem/sensor, oficial, social, notícias, contexto, saúde/frescor do sensor, geo, fingerprint e drivers. Para cada uma: origem, hora de disponibilidade, missing/stale rate, direção esperada, risco de leakage e custo.

Executar modelo completo, retirada de cada grupo e grupos isolados. Uma feature só é candidata se melhorar consistentemente Brier Skill/calibração/FPR/recall/lead time fora da amostra. Drivers precisam respeitar lag e superar baseline fora do tempo; registrar quantos foram testados para controlar múltiplas comparações.

## Negativos, erros e generalização

Hard negatives obrigatórios: rush hour, chuva normal, feriado, futebol, grande show, notícia viral, manifestação pacífica, pico social, manutenção programada e tempestade sem impacto. Taxonomias: falso alerta (`duplicate_news`, `viral_social`, `scheduled_event`, `weather_without_impact`, `sensor_fault`, `geo_error`, `baseline_error`, `context_error`, `source_outage`, `unknown`) e miss (`missing_sensor`, `late_sensor`, `geo_failure`, `dedup_failure`, `cluster_failure`, `weak_anomaly`, `bad_threshold`, `poor_model`, `unknown`).

Quando houver N suficiente, testar holdout por UF e categoria; não assumir que inundação generaliza para apagão. Medir drift de features/taxa-base/calibração/fonte e estabilidade semanal/mensal.

## Leakage e bloqueios conhecidos

O replay proíbe `outcome`, `resolved_at` e `resolution` no payload; snapshots guardam `data_cutoff` UTC e recusam tempo ingênuo. Restam riscos: schema semântico de features, baseline agregado futuro, contexto/driver futuro e registros de shadow ainda sem amostra. Qualquer vazamento confirmado é P0.

## Conclusão e gate científico

**Conclusão: UNVERIFIED.** O sistema possui mecânica de validação, não evidência de antecipação. V1 e V2 permanecem experimental/shadow. Promoção exige eventos e negativos completos, base rate reportada, Brier Skill positivo contra baseline adequado, calibração aceitável, FPR/recall sem regressão, lead time útil, holdout out-of-time, live shadow e rollback exercitado.

Próxima coleta de dados: obter primeiro evento histórico verificável e primeira janela negativa com `event_time`, `published_at`, `observed_at` e `fetched_at`, mantendo campos desconhecidos vazios em vez de estimados.
