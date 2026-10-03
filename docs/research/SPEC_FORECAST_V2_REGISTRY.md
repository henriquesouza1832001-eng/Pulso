# SPEC — campos do registro do Forecast V2 (para a plataforma)

> Pedido de `claude-hen` (mensagem #57). Fonte: saída de `forecast_v2_model.forecast(...)` e `Snapshot` de `forecast_v2_features.py`. **Append-only**: nova evidência = NOVA linha (trajetória 18% → 27% → 43%), nunca update da anterior. Tudo atrás de flag, em SHADOW; nada disto altera a previsão pública do V1.

## Linha do registro (uma por previsão V2)
| Campo | Tipo | Notas |
|---|---|---|
| `forecast_id` | TEXT | id da previsão V1 correspondente, ou id próprio do V2 |
| `scope` | TEXT | `BR` ou `UF:XX` |
| `target` | TEXT | alvo operacional (ex.: `pulse>=60@60m`, `event_escalation`); nunca previsão política |
| `data_cutoff` | TEXT ISO UTC | instante a partir do qual NADA posterior entra (P0) |
| `model_version` | TEXT | muda se a probabilidade mudar (hoje `heuristic-1`) |
| `feature_version` | TEXT | muda se a semântica de uma feature mudar (hoje `1`) |
| `context_version` | TEXT | feriados/eventos (hoje `none`) |
| `baseline_version` | TEXT | `ewma_v1` \| `seasonal_v1` |
| `calibrator_version` | TEXT NULL | NULL = sem calibrador |
| `snapshot_hash` | TEXT (sha256 hex) | hash do snapshot de features (reprodutibilidade) |
| `raw_probability` | REAL NULL | `0.02..0.98`; NULL se houve abstenção |
| `calibrated_probability` | REAL NULL | só com calibrador; nunca sobrescreve a bruta |
| `probability` | REAL NULL | a que vale (calibrada se houver, senão bruta); NULL em abstenção; **nunca 0 nem 1** |
| `interval_low`, `interval_high` | REAL NULL | |
| `uncertainty` | REAL NULL | 0–1 |
| `coverage` | REAL NULL | razão de sensores esperados disponíveis (NULL = não se aplica) |
| `status` | TEXT | `OK_CALIBRATED` \| `UNCALIBRATED_EXPERIMENTAL` \| `INSUFFICIENT_DATA` |
| `abstention_reason` | TEXT NULL | preenchido só em `INSUFFICIENT_DATA` |
| `prior_level` | TEXT | `cidade/categoria/hora` … `nacional/categoria` \| `global` |
| `prior_rate` | REAL | taxa-base usada |
| `prior_samples` | INTEGER | amostras do nível do prior |
| `uncertainty_reasons` | TEXT (JSON array) | |
| `contributions` | TEXT (JSON) | grupos de evidência e log-odds (correlação, não causa) |
| `missing_evidence_priorities` | TEXT (JSON) | ex.: `{"HYDROLOGY":"HIGH","MORE_NEWS":"LOW"}` |
| `created_at` | TEXT ISO | |

PK sugerida: `(forecast_id, model_version, data_cutoff)`; sem índice secundário (orçamento de escrita). Escrita só de linhas novas (`INSERT OR IGNORE`). Retenção: 180 dias. Tamanho: `contributions` + `reasons` < 2 KB por linha.

## Calibrador (artefato imutável; a plataforma já criou a tabela, só confirmar campos)
`version`, `method` (`platt`), `a`, `b` (REAL), `samples` (INTEGER), `fit_until` (ISO: corte dos dados de ajuste, nunca posterior ao que se prevê), `status` (`candidate`→`active`→`retired`). Só existe com `samples >= 200` e dois desfechos; senão `calibrator_version = NULL` e o status é `UNCALIBRATED_EXPERIMENTAL`.

## Snapshot de features (opcional, para auditoria e para o Codex)
Dict canônico de `Snapshot.content()`: `features{nome:{value,state,age_min,note}}`, `coverage{expected,available,stale,missing,ratio}`, `agreement{active_families,concordant,discordant}`, `excluded_future`. Estados: `VALUE, VALUE_ZERO, MISSING, STALE, UNAVAILABLE, NOT_APPLICABLE`. Guardar só o hash na linha e o conteúdo no `forecast_registry` já existente (limite 8 000 caracteres).

## Rotas
Leitura da trajetória já existe (`/api/admin/forecast-trajectory`): acrescentar `status`, `uncertainty`, `coverage`, `calibrated_probability` e `abstention_reason`. Nada público até o Reliability Gate.
