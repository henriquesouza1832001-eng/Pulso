# ENGINE_AUDIT — o que o motor Python já tem (2026-10-03)

> Primeira entrega do prompt "Evolução segura dos motores preditivos". Feito **lendo o código real** (`engine/pulso_engine/**`, 59 arquivos de teste, `apps/worker`, migrations). Nada aqui é plano de futuro: é o que existe. O plano está em [ENGINE_V2_PLAN.md](ENGINE_V2_PLAN.md). Regra do prompt §71: **não duplicar**; onde já existe equivalente, estender por composição.

## 1. Tabela de capacidades

Legenda de estado: **PROD** = roda no ciclo de produção · **CÓDIGO** = existe e tem teste, mas não está ligado ao pipeline · **PARCIAL** · **NÃO**.

| Capacidade | Já existe? | Arquivo | Estado | V2 necessário? |
|---|---|---|---|---|
| Baseline EWMA (por hora, escopo × categoria) | sim | `baseline.py` (`ewma_baseline`, `hourly_counts`) | PROD: usado por `pipeline.cluster_anomaly` | não; fica como fallback |
| Baseline sazonal (hora × dia da semana, fallback hora, `insufficient`) | sim | `baseline.py` (`seasonal_baseline`, `SeasonalBaseline`) | CÓDIGO + dados acumulando em `signal_observations` (só baseia com semanas de coleta). **Não** usado ainda em `cluster_anomaly` | sim: ligar atrás de flag, registrar `baseline_method/samples/quality`; falta mediana/MAD (hoje média/desvio) |
| Histórico agregado por hora | sim | `research/history.py`, tabela `signal_observations` (migration 0006), rota admin | PROD (envio 2×/hora, só horas fechadas, retenção 90 d) | não |
| Anomalia (z, score 0-1) | sim | `anomaly.py` (`zscore`, `anomaly_score`) | PROD | não; fica como V1 |
| Anomalia por janela + percentil + status `BASELINE INSUFICIENTE` | sim | `anomaly.py` (`window_anomaly`, `percentile_rank`) | CÓDIGO (usado só pelo Sentinela) | parcial: falta separar `anomaly_score` de `anomaly_confidence` e `robust_z` (MAD) |
| Tendência (velocidade, aceleração, estado RISING/FALLING...) | sim | `intelligence/trends.py` | CÓDIGO (usado só pelo radar) | sim: entrar como componente do Pulso, atrás de flag |
| Drivers / indicadores antecedentes | sim | `drivers.py` (correlação defasada) | PROD (só como evidência; **não** altera probabilidade) | sim: validador com ganho de previsão (Brier com × sem) e registro de drivers |
| Tipos de evento e precursores | sim | `processing/event_types.py`, `config/event_types.json` | PROD (evidência nas previsões) | sim: virar `EVENT_SIGNATURE` com lead time medido |
| Clustering lexical com estado | sim | `processing/clustering.py` (Jaccard, ids estáveis) | PROD | não substituir |
| Refino de cluster (entidades, geo, afinidade) | sim | `processing/cluster_refine.py` | CÓDIGO (em desenvolvimento, passo 8) | parcial: zona cinza semântica/embedding fica **adiada** (decisão do dono: NLP pesado só depois de medir) |
| Geolocalização | sim | `processing/geo.py` (cidade/UF/gentílico, ~150 cidades do interior, níveis 70/60/55/50/35) + `processing/geo_v2.py` (gazetteer IBGE dos 5.571 municípios, evidências) | V1 em PROD; V2 integrado atrás de `GEO_V2` (OFF) com estatística em sombra | em andamento: falta amostra rotulada e portão para ligar |
| Importância do texto / ruído / rotina de campanha | sim | `processing/importance.py` | PROD | não |
| Severidade | sim | `events.py` (`stats_for`: base por categoria + corroboração + texto) | PROD | sim: vetor de impacto (V2) em paralelo; hoje depende de categoria → severidade base |
| Confiança | sim | `scoring/confidence.py` | PROD | sim: `publisher ≠ origin`, diversidade de sensores; `contradiction` hoje é sempre 0 |
| Pulso (0-100, explicável) | sim | `scoring/pulse.py` | PROD | parcial: aceleração e dispersão entram depois, com backtest |
| Frescor por categoria | sim | `scoring/pulse.py` (`HALF_LIFE_BY_CATEGORY`) | PROD | não |
| Pulso nacional | **parcial** | `pipeline.build_pulses` (agrega eventos por escopo) | PROD | sim: dispersão geográfica, nº de estados, diversidade (hoje: média/topo) |
| Previsão de Pulso e de volume (Wilson, Brier, resolução) | sim | `forecast.py`, `forecast_surge.py`, tabela `forecasts` | PROD, `EXPERIMENTAL` até 100 resolvidas | parcial: falta `features_snapshot`, `baseline_version`, `feature_version` |
| Registro de previsões (auditoria) | **parcial** | tabela `forecasts` (método, versão, evidência, probabilidade, resolução, Brier) | PROD | sim: snapshot das features e versões para reprodutibilidade |
| Backtest | **parcial** | `backtest.py` (walk-forward **sintético**, referência justa) | CÓDIGO | sim: `backtest_v2` com eventos reais e V1 × V2 |
| Calibração (curva) | parcial | `/api/forecasts/track-record` (bins) | PROD | sim: erro de calibração, log loss, precision/recall/FPR |
| Shadow mode / comparação V1 × V2 | **NÃO** | — | — | **sim** |
| Feature flags | **NÃO** | — | — | **sim** (criada junto com este plano: `engine/pulso_engine/flags.py`) |
| Sentinela (gatilho, investigação com estado, dedup, esfriamento) | sim | `research/sentinel.py`, `radar.py`, `investigations_io.py`, migration 0007 | CÓDIGO + integração em andamento (roda em 1 de cada 3 ciclos; escreve só `investigations`, **não altera Pulso nem alerta**: é "shadow" por natureza) | parcial: faltam information gain e prioridade (anomalia × incerteza × impacto) |
| Query expansion / deep search orçado | sim | `research/query_expansion.py`, `research/deep_search.py` | CÓDIGO (só sinais já coletados; teto de requisições) | parcial |
| Validação / contradições / origem × publisher | sim | `research/validator.py` (`_origins`, `find_contradictions`, `validate`) | CÓDIGO | sim: ligar à confiança V2 |
| Contexto (feriado, jogo, show, eleição) | **NÃO** | — | — | sim (BrasilAPI feriados já validado) |
| Confiabilidade de sensor por desempenho | **NÃO** | — | — | sim (depende de histórico) |
| Information gain | **NÃO** | — | — | sim (fase D) |
| Fingerprint de evento (identidade além do título) | **NÃO** | clustering com estado cobre parte | — | sim |
| Qualidade de dado (completeness, freshness, parse) | **NÃO** | só saúde por fonte | — | sim |
| Saúde de fonte (transporte) | sim | `pipeline.collect`, `healthcheck.py`, `/api/health` | PROD | parcial: separar `transport_health` de `data_freshness`; histórico de uptime/latência |
| Circuit breaker de coletor | **NÃO** | só retry e `interval_s` | — | sim (menor prioridade) |
| Idempotência | sim | upsert por hash/id; `INSERT ... ON CONFLICT ... WHERE` | PROD | não |
| Orçamento de escrita e governador | sim | `apps/worker/src/lib/budget.ts` (ADR 0008) | PROD | não |
| Observabilidade comparativa V1 × V2 | **NÃO** | só `budget` na resposta do ingest | — | sim |

## 2. Desvios do prompt já ocorridos (honestidade)

O prompt (§3, §90) pede **composição** e flags OFF; parte do trabalho dos passos 1 a 8 foi feita antes de o prompt chegar:

1. `baseline.py` e `anomaly.py` **receberam funções novas** (`seasonal_baseline`, `window_anomaly`, `percentile_rank`). É **aditivo e compatível** (nenhuma assinatura existente mudou, os 59 arquivos de teste passam), então o risco é baixo e não vamos reverter. De agora em diante: arquivo novo por composição.
2. Os módulos novos estão em `research/` e `intelligence/trends.py`; o prompt sugere `intelligence/*`. **Não vamos mover** (quebraria imports e testes). Se quiserem os nomes do prompt, reexportar em `intelligence/` sem apagar nada.
3. Não existia mecanismo de feature flag. É o primeiro item do plano.
4. O Sentinela entra no ciclo antes de ter backtest. Isso é aceitável porque **só grava investigações** e nunca muda eventos, Pulso, alertas ou previsões (modo shadow na prática); a promoção para qualquer efeito visível exige o gate do plano.

## 3. Onde está o maior risco de regressão

- `pipeline.run_once` (570 linhas, ponto de integração de tudo): qualquer chamada nova entra com `try/except` e flag.
- Orçamento de escrita do banco: toda tabela nova precisa de escrita condicional e retenção (incidente de 2026-10-03).
- Tempo do ciclo (teto de 8 min; hoje ~40 s).
- Geo: mudar o `geo.py` mexe em eventos e clusters (já houve regressões; ver `test_headline_regression.py`).
