# Backend Total Red Team / Reliability Campaign

Data de corte: 2026-10-03. HEAD remoto principal: `098327e` (`origin/main`). A análise inclui os PRs #75–#79 já mergeados.

## 1. Executive Summary

O PULSO tem defesas úteis, mas não há evidência para chamá-lo confiável ponta a ponta ou para promover Forecast V2. A campanha confirmou correções de vazamento temporal, hardening de API e idempotência local; ainda há caminhos onde saúde ou inteligência podem apenas parecer corretas. Forecast V2 permanece `SHADOW`/`EXPERIMENTAL`; V1 permanece experimental.

Não houve novo vazamento temporal explorável. A corrupção/idempotência foi reproduzida localmente e corrigida para as tabelas principais, mas o ensaio ainda não cobre o servidor Turso remoto nem o binding D1 real.

### Atualização desde a auditoria anterior

Concluído e já mergeado na `main`: Forecast V2 em shadow; track-record com métricas adicionais; hardening de erros/request ID; limite de ingestão de 8 MB; liveness/readiness; veredito no `engine-status`; upserts condicionais/idempotência; ensaio local de falhas de storage; e suporte a `ADMIN_TOKEN` separado. Não concluído: segredo operacional do admin, WAF/rate limit, `write_budget` atômico após resposta perdida, freshness por conteúdo, cobertura degradada, RT-003/RT-008 e evidência científica do forecast.

## 2. Git State

- Branch de trabalho: `hen`; `origin/main`: `098327e`.
- `git pull --ff-only` estava atualizado.
- Mudanças não commitadas no Worker e `docs/api/API.md` pertencem a `claude-hen` e foram excluídas.
- O commit analisado põe V2 em shadow; não muda alerta público.

## 3. System Map

`source -> collector -> normalização -> dedup/geo/clustering -> evento -> baseline/anomalia -> confidence/severity/pulse -> Sentinela -> forecast -> registry -> ingest Worker -> Turso/D1 -> API`.

## 4. P0 Findings

### PULSO-RT-001 — outcome futuro dentro do replay (corrigido; regressão mantida)

| Campo | Evidência |
|---|---|
| Severity / component | P0 corrigido / replay temporal |
| File | `engine/pulso_engine/validation/replay.py` |
| Observed | `payload` genérico aceitava desfecho e podia otimizar a avaliação. |
| Expected | desfecho e resolução não entram antes do cutoff. |
| Reproduction / test | `engine/tests/reliability/test_data_leakage.py` injeta `outcome`, `resolved_at`, `resolution` e variações. |
| Root cause | payload sem semântica de feature. |
| Suggested fix area | manter deny-list; evoluir para schema versionado de features. |
| Do not modify | outcomes históricos, golden datasets, expected outputs. |

`ReplayItem.available_at` usa o último instante disponível entre publicação, observação, fetch e confirmação. O registry exige `data_cutoff` UTC no snapshot canônico. Campos semanticamente equivalentes a outcome, baseline ou driver futuro ainda não têm schema por feature: risco P1.

## 5. P1 Findings

### PULSO-RT-002 — HTTP 200 pode mascarar conteúdo estagnado

| Campo | Evidência |
|---|---|
| Severity / component | P1 / saúde de fonte e observabilidade |
| File | `engine/pulso_engine/pipeline.py`, `apps/worker/src/routes/health.ts` |
| Observed | `source_health` registra transporte; freshness de conteúdo por fonte não foi provada. Em produção, `/api/health` respondeu 200 com ciclo de 345 s, mas expõe apenas `last_success`, não um estado separado de freshness/cobertura. |
| Expected | `TRANSPORT_HEALTH`, `DATA_FRESHNESS`, `DATA_QUALITY` e `EVENT_EVIDENCE` separados. |
| Reproduction / test | ataque `200` com payload repetido/stale ainda não automatizado ponta a ponta. |
| Root cause | sucesso de fetch não é avanço de `published_at`/hash esperado. |
| Suggested fix area | idade de conteúdo e cobertura até status, Sentinela e forecast. |
| Do not modify | fonte `quiet_ok` não falha só por não emitir evento. |

### PULSO-RT-003 — Sentinela abre investigações em dia ruidoso normal

| Campo | Evidência |
|---|---|
| Severity / component | P1 / Sentinela |
| File | `engine/tests/reliability/test_sentinel_normal_day.py` |
| Observed | 30 sinais/15 min, 120/h histórico, três tipos e nenhum oficial abrem duas investigações. |
| Expected | rotina ruidosa reduz ou justifica investigação; medir precisão e ganho. |
| Reproduction / test | teste citado passa ao confirmar o break. |
| Root cause | diversidade não representa expectedness/contexto suficiente. |
| Suggested fix area | `claude-motor`: baseline/contexto e política de investigação. |
| Do not modify | cenário negativo adversarial. |

### PULSO-RT-004 — Forecast sem evidência científica de skill

| Campo | Evidência |
|---|---|
| Severity / component | P1 / forecast e calibração |
| File | `docs/research/PREDICTIVE_VALIDATION.md`, `engine/pulso_engine/validation/` |
| Observed | produção: 20 resolvidas, 0 positivas, 4 abertas, 4 anuladas; Brier 0,01961455, p média 0,09928 e baseline Brier 0. |
| Expected | Brier Skill fora do tempo, calibração, FPR/recall, lead time e N por horizonte. |
| Reproduction / test | métricas/splits/gate têm testes; não há corpus real COMPLETE nem shadow resolvido. |
| Root cause | faltam positivos, negativos e replay histórico verificável. |
| Suggested fix area | corpus com timestamps, agrupamento por `event_id`, ablation e shadow live. |
| Do not modify | probabilidades/outcomes históricos e métricas ruins. |

Brier absoluto não prova valor: com todos os desfechos negativos a referência é zero e Brier Skill é indefinido. Há sinal de sobreprevisão inicial, mas N=20 não justifica tuning.

### PULSO-RT-005 — autoridade e recuperação de storage não comprovadas

| Campo | Evidência |
|---|---|
| Severity / component | P1 / ingest, Turso/D1 |
| File | `docs/engineering/STORAGE_AUTHORITY.md`, `database/pending/0008-0010.sql` |
| Observed | `storage-chaos.test.ts` cobre rede antes da ação, HTTP 500, resposta perdida após commit e falha no meio do lote; upserts condicionais evitam duplicação nas tabelas principais. |
| Expected | matriz Turso/D1 UP/DOWN, duplicação segura e autoridade demonstrada. |
| Reproduction / test | ensaio local real sobre SQLite/Hrana; Turso remoto e binding D1 ainda não foram exercitados. |
| Root cause | backend remoto e comportamento D1 permanecem fora do harness. `write_budget` ainda pode subestimar após resposta perdida. |
| Suggested fix area | aplicar/validar no backend real; tornar orçamento parte da mesma transação ou reconciliá-lo. |
| Do not modify | migrations aplicadas ou dados de produção. |

### PULSO-RT-006 — fontes não são confiabilidade validada

| Campo | Evidência |
|---|---|
| Severity / component | P1 / proveniência e compliance |
| File | `engine/config/sources.json`, `docs/sources/SOURCES.md` |
| Observed | auditoria anterior: 282 ativas; 9 termos não pendentes e 3 revisadas. |
| Expected | autorização, retenção, exibição, custo e revisão humana por fonte. |
| Reproduction / test | auditoria de configuração; sem nova chamada a fontes. |
| Root cause | catálogo ampliado antes de revisão individual completa. |
| Suggested fix area | revisão humana por fonte ativa. |
| Do not modify | não contornar login, CAPTCHA, paywall, robots ou limites. |

## 6. P2 Findings

### PULSO-RT-007 — hardening administrativo não demonstrado

| Campo | Evidência |
|---|---|
| Severity / component | P2 / Worker e segurança |
| File | `apps/worker/src/routes/ingest.ts`, `/api/admin/*` |
| Observed | Bearer fail-closed, Zod, SQL parametrizado, limite 8 MB, `request_id`, liveness/readiness e testes de menor privilégio. `ADMIN_TOKEN` separado existe no código, mas é opcional e o segredo ainda depende do dono. |
| Expected | least privilege efetivo, rate limit/WAF, audit trail e testes de abuso. |
| Reproduction / test | `hardening.test.ts`, `auth.test.ts` e verificação local; configuração remota/WAF não auditados. |
| Root cause | proteção de borda e criação do segredo são operacionais, não resolvidas pelo Worker. |
| Suggested fix area | criar `ADMIN_TOKEN`/`PULSO_ADMIN_TOKEN`, confirmar `admin_token_separate=true`, configurar rate limit/WAF. |
| Do not modify | segredos e `.dev.vars`. |

### PULSO-RT-008 — métricas de clustering/provenance/performance ausentes

Não há corpus medido para `false_merge_rate`, `false_split_rate`, `duplicate_origin_ratio`, custo por sinal útil, nem p50/p95/p99 em 100--100k observações. Teste unitário verde não prova estabilidade sob syndication ou volume.

## 7. Collector Reliability

Cobertos localmente: 401/403/429 sociais, algumas respostas malformadas, retry transitório e RSS tolerante. Não executados em todos: redirect loop, 204/304, DNS/TLS/read timeout, gzip/chunk truncado, charset inválido, payload gigante, nem recuperação de 1 h/24 h offline. Estado: **PARTIAL**.

## 8. Temporal Integrity

Há regressões para ordenação, futuro escondido e cutoff UTC. O mecanismo cobre publicação 12:00/observação 12:09 contra forecast 12:05; falta ataque por feature para baseline/context/driver futuro.

## 9. Provenance

Há desconto de duplicata e V2 distingue origem/cópia, porém não há cascata medida de 1/5/10/50/100/1000 republicações. Independência continua hipótese, não métrica validada.

## 10. Geo

Geo V2 está desligado. Corpus editorial: 14 manchetes; V1 cidade 1/4, V2 4/4; ambos 0/8 falsa precisão nos negativos inequívocos. V2 abstém 64,29% contra 57,14% V1; Rio Branco é `DISPUTED`. Não é corpus histórico nem autoriza flag.

## 11. Clustering

Há guardas por estados explícitos e IDs estáveis, mas não corpus para false merge, false split, drift e resurrection. Evento órfão pós-fusão continua risco conhecido.

## 12. Baseline/Anomaly

Baseline recusa menos de 12 h e histórico esparso. Ainda não separa hora/dia/feriado/estação por local nem demonstra fallback hierárquico real; `ABSTAIN` é preferível a baseline inventado.

## 13. Confidence/Severity

Teto social, desconto de duplicata e separação de severidade/confiança existem. Faltam ataques quantitativos de spam coordenado e de alto volume/baixo impacto contra baixo volume/alto impacto.

## 14. Sentinela

`NORMAL_DAY` é regressão adversarial permanente (RT-003). Faltam NORMAL_RAIN, RUSH_HOUR, FOOTBALL, CONCERT, HOLIDAY, API_OUTAGE, STALE_SENSOR, DUPLICATE_STORM, GEO_AMBIGUITY, OFFICIAL_DENIAL e sensores contraditórios, com investigações/dia e ganho.

## 15. Forecast/Calibration

V2 acrescenta cutoff, hash, ausência explícita, cobertura, incerteza e abstenção. `STALE_AFTER_MIN=120`, `MIN_COVERAGE=0,25` e prior global 0,05 são hipóteses sem validação. Platt exige N>=200 e dois desfechos; isotônica não existe. Não promover antes de `PREDICTIVE_VALIDATION.md`.

## 16. Storage

`forecast_registry` é imutável por snapshot/hash e `shadow_results` só recebe resolvidos. Economy pode suprimir shadow/driver, reduzindo observabilidade científica. Autoridade e recuperação estão **PARCIALMENTE VERIFICADAS**: falhas e retries foram ensaiados localmente; Turso remoto/D1 real e a contagem atômica de `write_budget` continuam pendentes.

## 17. Worker/API

Ingest possui limites Zod, auth fail-closed e SQL parametrizado. Não houve fuzz para JSON profundo, UTF-8 inválido, NaN/Infinity, cursor, CORS, replay, SSRF e redirect; ausência de falha observada não é cobertura.

## 18. Security

Nenhum segredo foi impresso/adicionado. A revisão limitou-se a código/docs; WAF, configuração remota e logs não foram inspecionados. RT-007 permanece aberto.

## 19. Observability

`engine-status` informa backend, orçamento, investigações, forecasts, registry, shadow e última hora. O hardening separa liveness/readiness e emite veredito; ainda não prova freshness p50/p95/max por fonte ou cobertura degradada por sensor.

## 20. Cost/Performance

Não houve benchmark de CPU/memória, throughput ou custo por fonte. Não publicar números de performance sem carga, ambiente e percentis.

## 21. Test Matrix

| Component | Invariant / attack | Observed | Status | Test file | Severity / owner |
|---|---|---|---|---|---|
| Replay | futuro no cutoff | bloqueado para campos conhecidos | PASS | `test_data_leakage.py` | P0 / Codex |
| Registry | cutoff UTC reproduzível | snapshot canônico | PASS | `test_forecast_registry_cutoff.py` | P0 / Codex |
| Metrics | probabilidade/outcome inválidos | rejeitados | PASS | `test_metrics.py` | P0 / Codex |
| Sentinela | dia normal ruidoso | duas investigações falsas | FAIL caracterizado | `test_sentinel_normal_day.py` | P1 / motor |
| Geo | homônimos/falsa precisão | corpus pequeno; V2 off | PARTIAL | `test_geo_golden_corpus.py` | P1 / hen |
| Forecast | avaliação temporal | gate unitário, sem dataset real | PARTIAL | `test_temporal_splits.py`, `test_reliability_gate.py` | P1 / Codex |
| Source health | 200 stale | sem teste conteúdo stale | FAIL por ausência | — | P1 / hen+motor |
| Storage | timeout/partial D1-Turso | ensaio local passa; Turso/D1 reais pendentes; budget A1b aberto | PARTIAL | `storage-chaos.test.ts` | P1 / hen |
| API/admin | corpo grande, liveness/readiness, abuso/rate limit | hardening inicial passa; segredo/WAF pendentes | PARTIAL | `hardening.test.ts`, `auth.test.ts` | P2 / hen |
| Provenance | cascata de cópias | sem curva medida | FAIL por ausência | — | P1 / motor |

## 22. Reliability Scorecard

| Dimensão | Estado |
|---|---|
| ingest/storage | PARTIAL |
| temporal integrity | MODERATE (campos conhecidos) |
| provenance/clustering | WEAK |
| geo | WEAK; V2 off |
| anomaly/context/confidence | PARTIAL |
| Sentinela | WEAK |
| forecast/calibration | UNVERIFIED |
| API/security | MODERATE no código; PARTIAL na borda |
| observability/recovery | WEAK |

## 23. Promotion Gate

Reprovar V2 enquanto faltar: corpus real positivo/negativo completo, holdout temporal, Brier Skill positivo contra baseline, calibração/FPR/recall/lead time com N, shadow resolvido, reprodução determinística, rollback/storage exercitado e nenhuma regressão crítica. `UNKNOWN` e abstenção não contam como negativo.

## 24. Remaining Unknowns

Não foi possível provar freshness com 200, recuperação no Turso/D1 real, `write_budget` após resposta perdida, independência em escala, clustering, valor incremental de sensores, resistência a abuso/WAF, métricas históricas de forecast, custos ou percentis. São lacunas, não sucessos implícitos.

## 25. Recommended Fix Order

1. Testar 200 stale e propagar cobertura degradada até forecast/status.
2. Corrigir NORMAL_DAY sem enfraquecer seu teste.
3. Corrigir `write_budget` para resposta perdida e validar Turso/D1 reais.
4. Criar `ADMIN_TOKEN`/`PULSO_ADMIN_TOKEN` e aplicar rate limit/WAF.
5. Fechar corpus temporal de positivos e hard negatives; medir V1/V2 por evento.
6. Medir cascatas de proveniência, dedup e clustering antes de alterar pesos.
7. Completar revisão de fontes ativas.

## Handoff

RT-002 e o residual de RT-005 são plataforma (`claude-hen`); RT-003 e RT-008 são engine (`claude-motor`). Codex mantém replay, métricas, datasets e gate; não altera comportamento produtivo de módulos de outros donos.
