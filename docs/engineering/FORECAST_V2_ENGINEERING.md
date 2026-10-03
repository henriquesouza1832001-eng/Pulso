# FORECAST V2 — relatório de engenharia (vivo)

> Responsável: `claude-motor`. Briefing: `FORECAST_V2_BRIEF.md`. Codex mede e tenta quebrar; `claude-hen` entrega a plataforma. Estado do V2: **SHADOW / EXPERIMENTAL**; o V1 não foi alterado e nada aqui afeta alerta público.
> Última atualização: 2026-10-04.

## 1. Diagnóstico de partida
- Previsões em produção: 1 método (`pulse_empirical_delta` v1, Pulso do Brasil, 60 min) + volume por categoria. Medição do Codex (2026-10-03): **20 resolvidas, 0 positivos**, Brier de referência 0, skill indefinido. **Não há evidência preditiva e nenhum ajuste de modelo deve ser tunado com N=20.**
- Consequência: nesta fase o trabalho é de **infraestrutura de honestidade** (tempo, ausência, cobertura, incerteza, abstenção), não de acurácia. O que o V2 promete é saber o que não sabe.

## 2. O que existe (arquivos, todos puros e testados)
| Prioridade do briefing | Estado | Onde |
|---|---|---|
| P0 correção temporal | **feito** | `forecast_v2_features.visible_signals`: nada com `timestamp` ou `collected_at` > `data_cutoff`; `excluded_future` sempre declarado; teste de que dado futuro não altera o snapshot |
| P1 snapshot reproduzível | **feito** | `Snapshot` (hash sha256, `feature_version`, `data_cutoff`); mesmo corte + mesmos dados = mesmo hash, independente da ordem |
| P2 missing/stale | **feito** | estados `VALUE, VALUE_ZERO, MISSING, STALE, UNAVAILABLE, NOT_APPLICABLE`; anomalia sem baseline é `MISSING`, nunca 0 |
| P3 cobertura de sensores | **feito** | `sensor_coverage`: esperados (de `event_signatures.json`) x disponíveis x parados (>120 min) x ausentes; razão |
| P4 origem independente | **feito** | `independent_origins_60m`, `copy_ratio_60m` (republicações = 1 origem) |
| P5 concordância entre famílias | **feito** | `family_agreement`: físico/oficial/imprensa/social; social sem físico nem oficial = discordância, que sobe a **incerteza**, não a probabilidade |
| P6 taxa-base / prior | **feito (mecanismo)** | `hierarchical_prior` com fallback registrado (cidade → estado → nacional → global) e `GLOBAL_RATE = 0,05`; **faltam dados reais** para popular os níveis |
| P7 calibração | **feito (mecanismo)** | `raw_probability` ≠ `calibrated_probability`; `fit_platt` só com ≥200 amostras e dois desfechos, `fit_until` registrado; sem isotônica |
| P8 incerteza | **feito** | cobertura, sensor parado, discordância, prior sem amostra, features ausentes, evidência antiga |
| P9 abstenção | **feito** | `INSUFFICIENT_DATA` com `abstention_reason` (sem dados no corte, cobertura < 0,25, dado parado, escopo inválido) |
| P10 novas features | **não** | só depois que o Codex mostrar (ablation) o que falta |

## 3. Decisões e limites
- A probabilidade bruta é **prior + evidência com pesos de configuração** (`forecast_v2_model.WEIGHTS`, `MODEL_VERSION = heuristic-1`). Os pesos NÃO foram aprendidos nem ajustados a nenhum caso; cada um é uma hipótese a medir por ablation pelo Codex. Mudar um peso = nova `model_version`.
- Probabilidade nunca 0 nem 1 (`0,02..0,98`).
- Sem regra por cenário, ID ou manchete. O cenário de 49 posts sociais sem outro sensor é tratado pela regra geral de discordância.
- Regressão logística treinada (próximo candidato do briefing) **não** foi criada: não há dados nem positivos suficientes; `fit_platt` é só a camada de calibração.
- Deliberadamente fora: deep learning, ARIMA, isotônica, modelos por categoria.

## 4. Riscos conhecidos (para o Codex atacar)
1. `STALE_AFTER_MIN = 120` e `MIN_COVERAGE = 0,25` são limiares de partida sem base empírica.
2. Os níveis do prior hierárquico ainda não têm desfechos reais por cidade/hora; na prática o V2 cai em `global` (0,05).
3. As famílias de sensor vêm de `signatures.sensor_of` (heurística por classe/ID de fonte); fonte nova sem mapeamento cai em `news`.
4. `contributions` mostra log-odds por grupo, que são correlação e peso de configuração, não causa.

## 5. Handoff ao Codex (a enviar quando o PR entrar)
```text
HANDOFF  FROM: CLAUDE  TO: CODEX
HYPOTHESIS: snapshot com corte temporal rígido + ausência explícita + abstenção reduz falsos sinais e informa o que não se sabe
CHANGE: forecast_v2_features.py (P0-P5), forecast_v2_model.py (P6-P9)
FEATURES: signals_5/15/60m, acceleration_60m, persistence_min, anomaly_15m, independent_origins_60m, copy_ratio_60m, official_signal_60m, evidence_age_min, coverage, agreement
MODEL_VERSION: heuristic-1   FEATURE_VERSION: 1
EXPECTED BENEFIT: queda de falsos positivos em picos só-sociais e em ondas de republicação; abstenção em vez de chute sem cobertura
EXPECTED FAILURE MODE: abstenção excessiva (MIN_COVERAGE alto), prior global dominando, STALE_AFTER_MIN mal calibrado
FILES: engine/pulso_engine/forecast_v2_features.py, forecast_v2_model.py, anomaly_v2_bridge.py; engine/tests/test_forecast_v2_features.py, test_forecast_v2_model.py
TEST COMMAND: cd engine && py -m pytest tests/test_forecast_v2_features.py tests/test_forecast_v2_model.py -q
```

## 6. Próximos passos
1. Codex: ablation por grupo de feature e calibração fora do tempo sobre o replay (assim que houver positivos).
2. Plataforma: persistir a linha do registro (`docs/research/SPEC_FORECAST_V2_REGISTRY.md`).
3. Ligação no pipeline em SHADOW (flag a criar) gravando o V2 ao lado do V1; nenhuma exibição.
