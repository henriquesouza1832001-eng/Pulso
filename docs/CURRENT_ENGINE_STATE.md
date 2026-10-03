# CURRENT_ENGINE_STATE — o Motor Python hoje vs. o documento "Motor Python + PULSO Sentinela"

> **Atualização 2026-10-04 — implementação concluída no código (V2 atrás de flags).** Passos 1-14 da ordem do §7 existem como módulos testados: `research/history.py`, `baseline.py` (sazonal), `intelligence/trends.py`, `anomaly.py` (v2), `research/{sentinel,query_expansion,deep_search,validator}.py`, `radar.py`, `processing/cluster_refine.py`, `scoring/pulse.py` (`WEIGHTS_V2`, flag `PULSE_V2`), `forecast_scopes.py`, `calibration.py`, `backtest_events.py`, mais Fase 2 (`intelligence/emerging_terms.py`, `signatures.py`, `config/event_signatures.json`) e `simulation.py` (normal_day, flood_bh, blackout_sp, traffic_collapse_rj). Decisões em `docs/decisions/0009`. **O que falta é operacional, não de código:** ligar cada flag no `pipeline.py` após o portão de promoção (shadow + backtest V1×V2), acumular semanas de histórico (baseline sazonal, calibração, lead time reais), e a revisão de termos das fontes. O diagnóstico abaixo é o de 2026-10-03, antes da implementação.

> **Data:** 2026-10-03 · **Branch:** `hen` · Primeira entrega pedida pelo §76 do documento. Nenhum código foi alterado: este arquivo é só o diagnóstico e a proposta de ordem.
> Fontes lidas: `AGENTS.md`, `docs/BACKEND_STATUS.md`, `docs/architecture/*`, `docs/SCORING.md`, `engine/pulso_engine/**`, `database/migrations`, `apps/worker/src/routes`, `.github/workflows`.

## 1. Resumo (30 segundos)
- O Motor **já é** quase toda a "Fase 1" do documento: coleta (282 fontes ativas), normalização, dedup, keywords, geo, clustering **com estado**, confiança, severidade, Pulso explicável, baseline EWMA, anomalia, séries de 5 min, nowcast com Brier, backtest walk-forward, saúde de fontes e ingestão idempotente.
- **Não existe** o que dá nome ao documento: o **Sentinela** (investigação proativa com estado), deep search, query expansion, validação/contradições, termos emergentes, assinaturas de evento, grafo de sensores, calibração em curva, lead time e o dataset histórico.
- A maior lacuna **estrutural** é a memória: hoje o histórico é só `series` (contagem por escopo × categoria × 5 min). Sem guardar sinais por sensor e métricas por janela, Sentinela, lead time e backtest de eventos não têm base. É a primeira coisa a resolver (item 1 da ordem do §77).
- A maior **restrição** é o orçamento de escrita do banco (ADR 0008; hoje o Worker roda sobre o Turso). Toda tabela nova precisa de escrita condicional.

## 2. Mapa: seção do documento → o que existe

Legenda: ✅ existe e testado · 🟡 parcial · ❌ não existe.

| Seção do documento | Estado | Onde está / o que falta |
|---|---|---|
| §2/§9/§41 Ciclo (`radar_cycle`) | 🟡 | `pipeline.run_once` já faz coletar → dedup → geo → cluster → score → séries → nowcast → payload do ingest. Faltam as etapas Trends/Sentinel/Deep search/Validate. Não há `radar.py`. |
| §8 Coletores por pasta | ✅ | `collectors/{news,official,social}` + `registry.py` + `config/sources.json` (fonte da verdade). Não existem `weather/ traffic/ energy/ internet/ transport/ cameras/` como pastas; clima = INMET, energia = `ons_ear`, câmeras = só catálogo de links (`config/cameras.json`). |
| §47 `SourceAdapter` | ✅ | `collectors/base.py` (`fetch/normalize/run`; saúde calculada no pipeline). A interface não tem `health()` nem `metadata()` próprios: saúde é derivada da exceção/resultado em `run_once.collect`. |
| §45/§46 Saúde e retry | ✅ | Seis estados no contrato (`ONLINE…UNKNOWN`), `RATE_LIMITED` para 429, retry único em erro de rede, `quiet_ok`, agendamento espalhado por fonte, `healthcheck.py`, `audit.py`. Falta circuit breaker e `Retry-After` explícito. |
| §21 Deduplicação | 🟡 | `normalizer.py`: URL canônica + hash do título; clustering descarta cópias de mesma fonte. **Falta** `duplicate_ratio` real (o campo existe em `EventStats`, mas a detecção de republicação por agência/texto semelhante entre fontes é limitada ao Jaccard do título). |
| §15 Keyword engine | ✅ | `processing/keyword_engine.py` + `keywords.json` (recarregável). 12 categorias em vez das 10 "famílias" do documento (`SECURITY, TRAFFIC, WEATHER, INFRASTRUCTURE, PROTEST, POLITICS, ECONOMY, HEALTH, INTERNATIONAL, TECH, EVENT, EMERGENCY`). Não há `FIRE`, `ENERGY`, `TRANSPORT`, `INTERNET` como famílias. |
| §23 Geo | ✅ | `processing/geo.py` (gazetteer: UF, capitais, ~150 cidades), `geo_precision`/`geo_confidence`, nunca inventa precisão. **Falta** bairro, rua, ponto de interesse. |
| §16 Termos emergentes | ❌ | Nada. (`importance.py` filtra impacto; não detecta crescimento de n-grams.) |
| §17/§18 NLP local, embeddings | ❌ | `dependencies = []` (só biblioteca padrão), por decisão. spaCy/scikit/sentence-transformers exigiriam ADR e peso no job do GitHub Actions. |
| §19 Clustering | 🟡 | `processing/clustering.py`: Jaccard de tokens + janela de 12 h + trava de UF; id estável com `assign_event_ids`. **Não é** DBSCAN nem usa distância geográfica/entidades/categoria. Funciona e está calibrado em dado real. |
| §11 Baseline | 🟡 | `baseline.py`: EWMA horária por escopo × categoria; inválido com < 12 h ou histórico esparso. **Falta** hora do dia × dia da semana (já é a limitação 5 do BACKEND_STATUS). |
| §12 Janelas temporais | 🟡 | Séries em 5 min; contagens horárias derivadas. Faltam as janelas 5/15/30/60/180/360/1440 min como métricas e `source_type_count`, `velocity`, `acceleration`, `geographic_density` por janela (hoje velocidade é calculada por evento em `events.stats_for`). |
| §13 Anomalia | 🟡 | `anomaly.py`: z-score / 4, saturado em 0–1; honesto sem baseline. **Falta** percentis, comparação com mesma hora da semana. |
| §14 Trend engine | 🟡 | Só `velocity_per_hour` e `persistence_min` por evento. Falta aceleração, diversidade de fontes por janela, espalhamento geográfico e série de tendências por escopo. |
| §5–§7, §25, §52–§54 Sentinela | ❌ | Não há investigação, estado persistente, gatilho (`should_investigate`) nem deduplicação de investigações. |
| §26/§55/§56/§57 Deep search, query expansion, matriz sensor × evento, grafo | ❌ | Nada. Existe um embrião: `config/event_types.json` (tipos de evento + `raises` + `lead_hours`) e `processing/event_types.py`; `drivers.py` mede correlação defasada entre categorias. Servem de base para assinaturas e grafo. |
| §24 `event_signatures.yaml` | 🟡 | `event_types.json` cobre tipos como `chuva_extrema`, `operacao_policial`... com `terms` e `raises`. Não tem `leading/concurrent/confirming` por tipo de sensor, e os 14 tipos do documento (FLOOD, BLACKOUT…) não coincidem 1 a 1. |
| §27/§28 Validação e contradições | ❌ | `EventStats.contradiction` existe e vale 0 sempre (nenhum código a calcula). Não há registro de evidências contraditórias. |
| §30 Confiança | ✅ | `scoring/confidence.py`; teto 40 para só-social; penalidades de duplicata e contradição existem na fórmula (a contradição não é alimentada, ver acima). |
| §31 Severidade | ✅ | `events.stats_for` (categoria + corroboração + impacto do texto via `importance.py`; rotina de campanha limitada). Não usa "pessoas afetadas/área/duração" estruturados. |
| §32/§33 Pulso Score + "POR QUE?" | ✅ | `scoring/pulse.py`: 8 componentes ponderados (`docs/SCORING.md`), lista de pontos soma o score, frescor por categoria, nível 1–5, piso para alerta oficial. **Falta** componente de *aceleração* e de *diversidade de tipos de sensor* separado de diversidade de fontes. |
| §34/§35 Nowcast | ✅ (v1) | `forecast.py` (Pulso BR, 60 min, empírico + Wilson) e `forecast_surge.py` (volume por categoria/UF). Probabilidade vem de estatística, nunca de LLM. `EXPERIMENTAL` até 100 resolvidas. |
| §36 Calibração | 🟡 | Brier por previsão, `/api/forecasts/track-record` com calibração por método e versão. **Falta** precision/recall/FPR e a curva de calibração persistida (o backtest tem a curva de confiabilidade, mas em memória). |
| §37 Lead time | ❌ | Nada mede "primeiro sensor → grande notícia". Depende do dataset (§39). |
| §38 Backtest de eventos | 🟡 | `backtest.py` é só do previsor de volume (walk-forward, sintético). Não reconstrói T-6h…T+30m de eventos reais. |
| §39 Dataset histórico | ❌ | Não existe tabela `timestamp/location/sensor/signal/category/value/baseline/anomaly/event_id/outcome/lead_time`. |
| §40 GitHub Actions | ✅ (diferente) | Já há coleta de 5 em 5 min, mas **disparada pelo Cron da Cloudflare** via `workflow_dispatch` (o `schedule` do GitHub atrasa/ignora; ver BACKEND_STATUS). `collect.yml` roda `python -m pulso_engine.pipeline --push`. Não existe `radar.yml` nem `pulso_engine.radar`. |
| §42 Queues | ❌ | Decisão registrada: só quando houver necessidade medida. |
| §43 D1 | 🟡 | Tabelas: `sources, source_health, signals, events, event_sources, locations, keywords, entities, event_entities, pulse_history, metrics` (0001), `series` (0002), `forecasts` (0003), picos (0004), `write_budget` (0005 pendente, já no Turso). O ingest **não grava** `entities`, `keywords`, `locations` nem `metrics` (verificado por busca no `ingest.ts`). Não há `forecast_results` (resolução fica na própria linha de `forecasts`), `investigations`, `evidence`, `baselines`, nem `signal_observations`. |
| §44 KV | ❌ | Fora por decisão (ADR 0008 estudou KV como snapshot; não adotado). A API usa cache em `lib/cache.ts`. |
| §48 Protocolo de fontes | ✅ | `config.py` recusa fonte sem os campos do protocolo; `COLLECTION_PROTOCOL.md`; `SOURCES.md`. Pendência humana: revisar termos de ~95 fontes. |
| §49/§50 Social, X | ✅ | Reddit, X, Bluesky, Mastodon prontos e `enabled: false` até autorização/chave; social nunca passa de teto 40 e nunca confirma. X sem API = desligado (equivale a `DISABLED_NO_API`; o estado não existe como valor explícito). |
| §51 Browser automation | ✅ (não usado) | Nada usa; correto. |
| §58 Câmeras | 🟡 | Catálogo de 59 links (`CAMERAS.md`, `/api/cameras`). Sem visão computacional, por desenho. |
| §59 Privacidade | ✅ | Regra do `AGENTS.md`; nenhuma estrutura por indivíduo. |
| §60 Observabilidade | 🟡 | `/api/health`, `/api/stats`, `/api/admin/overview`, `healthcheck.yml`. Não mede anomalias/min, investigações, lead time, falsos positivos. |
| §63 Testes | ✅ | 307 testes Python (inclui simulação de ciclos e do laço de previsão), 27 do Worker. |
| §64 Simulação | 🟡 | `test_cycle_simulation`, `test_forecast_loop_simulation` e `pipeline` sem `--push` (rodada simulada). Faltam os datasets nomeados (`flood_bh.json` etc.) como cenário reproduzível do Sentinela. |
| §65/§66 Fail-safe e EXPERIMENTAL | ✅ | Baseline inválido → anomalia 0; nowcast só com histórico; selo `experimental` na API. Falta a string "DADOS INSUFICIENTES"/"BASELINE INSUFICIENTE" exposta na API (hoje é só ausência/zero). |

## 3. Conflitos entre o documento e a arquitetura atual

1. **Estrutura de pastas (§8).** O documento propõe `intelligence/`, `research/`, `forecasting/`, `storage/`, `workers/`. O repositório tem módulos planos (`baseline.py`, `anomaly.py`, `forecast.py`, `series.py`...) e `processing/`, `scoring/`. Mover quebraria imports, ~307 testes e o `AGENTS.md`. **Proposta:** não reorganizar; criar só os pacotes novos (`research/`, e `intelligence/` apenas para o que for novo: `trends`, `emerging_terms`, `signatures`, `correlation`) e manter os módulos existentes onde estão. O `drivers.py` já é a correlação (§57).
2. **Orçamento de escrita do banco (ADR 0008).** O documento pede dataset por sensor, métricas por janela e investigações. Sem cuidado isso reproduz o incidente de 113 mil escritas/dia. Toda tabela nova precisa de escrita condicional, retenção curta para o detalhe e agregação para o histórico longo; e passa pelo governador `lib/budget.ts` (modos normal/economy/critical).
3. **Disparo.** O documento manda criar `.github/workflows/radar.yml` com `cron */5`. O `schedule` do GitHub já se mostrou pouco confiável aqui; o disparo real é o Cron da Cloudflare em `collect.yml`. **Proposta:** `python -m pulso_engine.radar` entra como o novo ponto de entrada chamado por `collect.yml` (não um segundo workflow, que competiria por `concurrency` e duplicaria a coleta). `pipeline.py` continua com `run_once` como núcleo.
4. **Dependências (§17/§18).** `engine/pyproject.toml` não tem dependências, de propósito, e o job roda `pip install -e engine` a cada 5 min com `timeout-minutes: 8`. sentence-transformers/spaCy aumentariam instalação e tempo. **Proposta:** nada de embeddings na Fase 1; reavaliar com ADR e medição (cache de pip, ou etapa separada em job de menor frequência).
5. **Orçamento de requisições do Deep search (§10/§26).** Hoje o ciclo gasta ~37 s para 282 fontes com no máximo 2 conexões por servidor. Deep search deve ser **orçado** (teto por ciclo, cache de consultas, `robots`/termos de cada fonte pelo protocolo) e usar só fontes já cadastradas; consulta a motores de busca (ex.: Google News RSS) foi usada só para pesquisa de cobertura, **não** é fonte. Qualquer fonte nova de busca passa pelo `COLLECTION_PROTOCOL.md`.
6. **Estados.** O documento define 8 estados de investigação (§53); o contrato de evento tem `EventStatus` (7 valores). São coisas diferentes: investigação é um objeto novo. Não mexer em `EventStatus`.
7. **Contratos.** Qualquer campo novo na API pública (`why detected`, lead time, investigação) é mudança de contrato: mesmo PR atualiza `packages/shared/src/contracts.ts`, `models.py`, `docs/api/API.md` e leva label `contract` (regra do `AGENTS.md`). Preferir campos **aditivos** e rotas internas `/api/admin/*` primeiro.
8. **Política de branches.** O documento não fala de branches, mas a convenção do repositório é só `main`, `hen`, `thig`, `art`, `isar`. Todo o trabalho segue na `hen` com PR para a `main`.
9. **Nowcast "Pulso 3+ em BH".** O documento exemplifica nowcast por cidade. Hoje há nowcast de Pulso BR e volume por categoria/UF; `scope` aceita `UF:XX`, não cidade. Cidade fica para depois do dataset.

## 4. O que reaproveitar (não duplicar)

| Necessidade do documento | Reaproveitar |
|---|---|
| History / janelas | `series.py` (5 min) + `changed_series` (escrita condicional) + `/api/admin/series` |
| Baseline | `baseline.py` (estender para hora × dia da semana sem quebrar `Baseline.valid`) |
| Anomalia | `anomaly.py`; `pipeline.cluster_anomaly` já liga anomalia ao evento |
| Trends | `events.stats_for` (velocidade/persistência) e `forecast_surge.rolling_hour` |
| Assinaturas / sensor graph | `config/event_types.json`, `processing/event_types.py`, `drivers.py` |
| Clustering com estado | `processing/clustering.py` + `pipeline.assign_event_ids` |
| Confiança/Severidade/Pulso | `scoring/confidence.py`, `events.py`, `scoring/pulse.py` |
| Nowcast/Calibração | `forecast.py`, `forecast_surge.py`, `backtest.py`, `/api/forecasts/track-record` |
| Saúde, retry, agendamento | `pipeline.is_due/health_due`, `client.push_batch`, `healthcheck.py`, `audit.py` |
| Envio idempotente | `/api/ingest` (`chunks`, `changed_events`, governador de orçamento) |
| Simulação | `tests/test_cycle_simulation.py` como base dos cenários `flood_bh`, `blackout_sp`... |

## 5. Migrations necessárias (propostas; numerar após `git pull`)

Já usadas: `0001`–`0004`; `0005_write_budget` está em `database/pending/` (aplicada só no Turso). Próximas livres: **`0006`** em diante, confirmando a sequência com a equipe antes de criar.

| Migration | Tabelas / mudanças | Para quê |
|---|---|---|
| `0006_history` | `signal_observations` (agregado por janela × escopo × categoria × tipo de fonte: contagem, fontes, duplicatas, oficial) e `baselines` (escopo × categoria × hora × dia da semana: média, desvio, n) | History + baseline sazonal (itens 1–2 do §77). Só contagens, sem conteúdo de terceiros, retenção longa |
| `0007_investigations` | `investigations` (estado, local, categoria, anomalia inicial, evento ligado, timestamps), `evidence` (investigação, tipo de sensor, fonte, URL, lado: apoia/contradiz/contexto) | Sentinela, validação, contradições (itens 5–7) |
| `0008_event_timeline` | `event_timeline` (evento, instante, sensor, descrição) e colunas de lead time em `events` (ou tabela própria `event_outcomes`) | "Por que o PULSO detectou isso?", lead time, dataset (§39, §62) |
| `0009_forecast_calibration` | `calibration_bins` (método, versão, faixa, previsto, observado, n) | Curva de calibração, precision/recall/FPR (§36) |

Todas: `IF NOT EXISTS`, escrita condicional no Worker e entrada no `write_budget`.

## 6. Endpoints necessários (todos aditivos)

Internos (`/api/admin/*`, token): `GET /baselines`, `GET /investigations`, `GET /signals/observations`.
Ingest: o `IngestBatch` ganha campos **opcionais** `observations`, `investigations`, `evidence`, `timeline` (o Worker antigo os ignora; com `catalog_complete` como precedente).
Públicos (só depois de estabilizar; mudança de contrato): `GET /api/events/:id/why` (linha do tempo da detecção), `GET /api/sentinel` (status resumido), `GET /api/forecasts/track-record` ampliado com precision/recall/FPR e lead time.

## 7. Ordem recomendada de implementação (alinhada ao §77, adaptada ao que existe)

Cada passo = PR pequeno na `hen`, com testes, `docs/BACKEND_STATUS.md` atualizado e ADR quando a decisão for arquitetural.

| # | Passo | Resultado verificável | Depende de |
|---|---|---|---|
| 0 | Este diagnóstico + ADR 0009 ("Sentinela como camada determinística sobre o pipeline, sem reorganizar pastas") | decisão registrada | — |
| 1 | **History** (`0006`, `signal_observations`, métricas de janela 5/15/30/60/180/360/1440 min, `source_type_count`, `duplicate_ratio`) | dados acumulando no banco, dentro do orçamento | — |
| 2 | **Baseline sazonal** (hora × dia da semana, com fallback para o EWMA atual) | `Baseline` continua inválido sem dados; `BASELINE INSUFICIENTE` exposto | 1 + semanas de coleta para ser útil |
| 3 | **Trends** (velocidade, aceleração, diversidade, espalhamento, persistência por escopo) | módulo `intelligence/trends.py` + testes; entra como componente "aceleração" no Pulso (mudança em `SCORING.md`) | 1 |
| 4 | **Anomalia** v2 (percentil e mesma hora da semana, mantendo z) | anomalia por janela, não só por hora | 2, 3 |
| 5 | **Sentinela básico** (`research/sentinel.py`: gatilho configurável, investigação com estado e deduplicação de investigações, só sobre dados já coletados) + `radar.py` como orquestrador chamado pelo `collect.yml` | `0007`; simulação `flood_bh.json` dispara 1 investigação, `normal_day.json` nenhuma | 1–4 |
| 6 | **Query expansion + deep search orçado** (só fontes já cadastradas, teto por ciclo, cache) | consultas geradas por sinônimos de `keywords.json`, teto de requisições testado | 5 |
| 7 | **Validação** (apoia/contradiz/contexto, `contradiction` passa a ser calculado, `official_confirmation` por investigação) | confiança deixa de ter `contradiction` sempre 0 | 6 |
| 8 | **Clustering** v2 (geo + entidades + categoria como critério adicional; DBSCAN só se medir ganho) | régua de manchetes e `test_headline_regression` sem regressão | 7 |
| 9–11 | Confiança, severidade e Pulso: ligar contradição, sensores independentes e aceleração; atualizar `SCORING.md` | "POR QUE N?" continua somando o score | 3, 7 |
| 12 | Nowcast por escopo ampliado | continua `EXPERIMENTAL` | histórico |
| 13 | **Calibração** (`0009`, precision/recall/FPR) | `/track-record` ampliado | previsões resolvidas |
| 14 | **Backtest de eventos + lead time** (`0008`, dataset §39) | relatório T-6h…T+30m de eventos reais | semanas de dados |
| — | Fase 2 do documento (termos emergentes, event signatures `leading/concurrent/confirming`, grafo, Reddit/Bluesky, trânsito, clima) entra junto aos passos 5–8 quando as fontes passarem pelo protocolo | | |

Regras valendo em todos os passos: sem LLM no caminho crítico; nada de probabilidade que não venha de estatística; sem tocar `apps/web`; sem segredos no Git; nenhuma fonte nova sem a ficha em `SOURCES.md`.

## 8. Decisões que preciso do dono antes do passo 1

1. **Raiz do histórico:** aceitar `signal_observations` agregada (só contagens, sem conteúdo) como base do dataset, em vez de guardar cada sinal por sensor? (recomendo agregada: cabe no orçamento do banco.)
2. **`radar.py`:** confirmar que ele será o novo ponto de entrada chamado pelo `collect.yml`, com `pipeline.run_once` mantido como núcleo (recomendado), e não um workflow separado.
3. **Banco:** a coleta roda hoje sobre o Turso. As tabelas novas devem nascer já pensando em Turso e D1 (a camada `TursoDatabase` mantém a mesma superfície).
4. **Dependências de NLP:** adiar spaCy/sentence-transformers para depois de medir o ganho (recomendado).
