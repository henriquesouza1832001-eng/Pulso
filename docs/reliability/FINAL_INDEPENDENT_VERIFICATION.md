# PULSO — Independent Reliability & Predictive Verification

Data da auditoria: 2026-10-03. Ambiente: Windows, Python 3.14.4, pytest 9.1.1, Node/npm, Worker local e endpoints públicos. Auditoria de código e harness; não houve acesso a segredos nem alteração de produção.

## Identificação e escopo

- `START_SHA`: `ac148489eeae5dafe15bd66559e95e2f42561ad0`
- `MAIN_SHA`: `ac14848` (`origin/main` no início da auditoria)
- Branch de trabalho: `hen`.
- PRs recentes considerados: #84 (chaos/freshness), #85 (runtime/cycle), #86 (breaker), #87 (auth/abuso), #88 (SSRF e write budget), todos mergeados.
- PR #89 estava aberto e não foi considerado parte da `main`.
- O checkout local possuía WIP não commitado de outra campanha (arquivos de engine, Worker e testes). Esses arquivos foram preservados, não foram incluídos neste relatório e não são evidência da `main`.

## Resultado executivo

O núcleo de inteligência situacional está funcional e tem defesas relevantes: falha de fonte é isolada, frescor/qualidade/cobertura agora são conceitos distintos no engine, SSRF possui guard, o ingest é idempotente no harness local e há liveness/readiness e veredito operacional. Isso não demonstra maturidade operacional total nem capacidade preditiva.

O gate científico permanece reprovado por `INSUFFICIENT_DATA`: não há amostra positiva suficiente, Brier Skill estimável, calibração fora do tempo ou shadow resolvido. RT-003 (falsos alarmes da Sentinela em dia normal ruidoso) continua um `FAILED` conhecido na `main`. Compliance, WAF/rate limit e bancos remotos são `BLOCKED_EXTERNAL`/`UNVERIFIED`, não PASS.

## Baseline executado

| Verificação | Resultado real |
|---|---|
| Reliability, replay, temporal, geo, chaos, freshness, breaker, SSRF | 106 passed em 13,71 s |
| Worker completo no checkout compartilhado | 145 passed em 10,45 s; 13 arquivos |
| `npm run typecheck` | PASS |
| `npm run build` / Wrangler dry-run | PASS; warning de chunks >500 kB |
| `npm audit` | 2 moderadas, dev-only (`vitest`/`@vitest/mocker`), correção exige major |
| Python completo | NÃO CONCLUÍDO: 776 itens coletados, execução interrompida pelo limite de 30 s da ferramenta em 11%; checkout estava sujo |
| CI | checks do PR #88 passaram; não é substituto de uma execução limpa desta auditoria |
| Produção | Durante esta campanha: `/api/health` HTTP 200 (`api=ONLINE`, `db=ONLINE`, `stale=false`), `/api/health/live` HTTP 200 e `/api/health/ready` HTTP 200; freshness histórica por fonte e WAF não foram comprovados externamente |

Os testes de storage imprimem erros simulados em stderr de propósito durante injeções de rede/HTTP 500/resposta perdida; os testes passam e isso não é stack exposto ao cliente.

## Findings reproduzidos e correções

### F-001 — leakage de outcome no replay

Estado: `VERIFIED` como regressão corrigida. `test_data_leakage.py` bloqueia `outcome`, `resolved_at` e `resolution`; registry exige cutoff UTC. Residual: campos semanticamente equivalentes a outcome/baseline/driver ainda não têm schema formal por feature.

### F-002 — HTTP 200 não significa frescor

Estado: `PARTIAL`. `source_freshness` e seus testes distinguem `FRESH`, `STALE`, `EMPTY`, `QUIET` e `UNKNOWN`; 200 repetido/velho não é FRESH e falha de transporte não vira zero. O runtime/cycle e `engine-status` já carregam resumo. Ainda falta prova operacional histórica, persistência completa por fonte no ambiente real e série SLO; thresholds são hipóteses.

### F-003 — caos de collectors

Estado: `PARTIAL`. O harness RSS cobre 200, vazio, 204, 301/302, loop, 304, erros HTTP, DNS, conexão, TLS, reset, timeout, truncamento, gzip inválido/bomba, UTF-8/Latin-1, XML/HTML/JSON inválidos, schema drift, payload grande e slow-loris. Coletores oficiais não estão na mesma matriz; redirect cross-host, HTTP/2 e DNS rebinding real permanecem desconhecidos.

### F-004 — SSRF

Estado: `PARTIAL`. O guard bloqueia loopback, RFC1918, CGNAT, link-local/metadata, ULA, multicast, IPs reservados, IPv4-mapped IPv6 e esquemas não HTTP; valida antes de conectar e redireciona com guarda. Há testes reais de loopback e metadata. DNS rebinding contra servidor real, proxy corporativo e toda cadeia de redirect público→privado não foram provados em produção.

### F-005 — circuit breaker

Estado: `PARTIAL`. Há estados CLOSED/OPEN/HALF_OPEN, backoff e estado por fonte no ciclo, com testes puros e integração shadow. `Retry-After` e comportamento sob restart/serviço real não têm prova operacional; não tratar teste unitário como integração.

### F-006 — storage e idempotência

Estado: `PARTIAL`. O harness local cobre falha antes da transação, HTTP 500, resposta perdida após commit e falha no meio do lote; upserts condicionais protegem events, series, forecasts e pulse_history. Turso remoto e binding D1 não foram ensaiados nesta auditoria. Migrations/autoridade de backend continuam parcialmente verificadas.

### F-007 — write budget após resposta perdida

Estado: `PARTIAL`. O commit `ac54820` trata a subcontagem, e o teste reproduz resposta perdida/retry. Ainda falta prova contra Turso real/D1 e demonstração de que nenhuma combinação de 100 retries e falha parcial ultrapassa o limite operacional.

### F-008 — auth e abuso de API

Estado: `PARTIAL`. Há matriz de token ausente/inválido, separação ADMIN/INGEST, Bearer, request ID, limite de 8 MB, JSON/limites e erros controlados nos testes reais da composição do app. WAF/rate limit de Cloudflare, bursts externos, CORS real e audit trail administrativo não foram verificados.

### F-009 — Sentinel NORMAL_DAY

Estado: `FAILED` na `main`. O cenário adversarial histórico reproduz duas investigações em um dia ruidoso normal. O teste é caracterização de falha, não deve ser enfraquecido. Os cenários NORMAL_RAIN, RUSH_HOUR, FOOTBALL, CONCERT, HOLIDAY, NEWS_BURST, SOCIAL_BURST, DUPLICATE_STORM, STALE_SENSOR, API_OUTAGE, GEO_AMBIGUITY, OFFICIAL_DENIAL, CONTRADICTORY_SENSORS, OLD_NEWS_RESURFACE e SCHEDULED_EVENT não formam ainda uma matriz completa na `main`.

### F-010 — provenance/clustering em escala

Estado: `UNVERIFIED`. Há dedup, fingerprints e distinção de publisher/origin no código, mas a `main` não apresenta curva independente para 1/5/10/50/100/1000 republicações nem métricas completas de false merge, false split, drift e resurrection.

### F-011 — geo

Estado: `PARTIAL`. Gazetteer e Geo V2 exigem contexto e abstêm homônimos; corpus editorial anterior mostrou melhora, mas Geo V2 continua atrás de flag e não há corpus histórico independente suficiente para promoção.

### F-012 — forecast/calibração

Estado: `UNVERIFIED`. Snapshot, cutoff, ausência, cobertura, incerteza, abstenção, registry e calibradores versionados existem. Os dados operacionais disponíveis permanecem pequenos e sem positivos suficientes; Brier Skill, calibração, recall/FPR, lead time e comparação V1×V2 não são estimáveis. Não houve tuning nem promoção.

### F-013 — UF sintaticamente válida, semanticamente inválida

Estado: `FAILED` na API pública. Reprodução em produção: `GET /api/pulse/state/ZZ` respondeu `200` com `scope=UF:ZZ`, `score=0`, `alert_level=1`, `label=NORMAL` e timestamp atual. A rota valida apenas duas letras (`^[A-Z]{2}$`), não o conjunto de UFs brasileiras. Esperado: `4xx invalid_uf` ou resposta explicitamente `UNKNOWN`, nunca normalidade sintética. Causa provável: validação de formato sem enumeração de UF. Handoff: plataforma/Worker; adicionar regressão sem tocar no dataset de sinais.

## Scorecard independente

| Área | Estado | Evidência / limite |
|---|---|---|
| Software correctness | `PARTIAL` | 106 focused tests; full Python não terminou em checkout limpo |
| Temporal integrity | `PARTIAL` | replay/cutoff cobertos; schema semântico completo ainda falta |
| Collector resilience | `PARTIAL` | chaos RSS local; oficiais e rede real fora da matriz |
| Freshness | `PARTIAL` | estados e runtime no código; série/produção ainda não provados |
| Coverage | `PARTIAL` | cobertura por família e forecast; propagação operacional não completa |
| Provenance | `UNVERIFIED` | não há cascata medida em escala |
| Dedup | `PARTIAL` | invariantes unitárias; dependência de corpus real |
| Clustering | `UNVERIFIED` | métricas adversariais ausentes |
| Geo | `PARTIAL` | abstention/gazetteer; V2 experimental |
| Baseline/context | `PARTIAL` | fallback/mecanismos; histórico sazonal real insuficiente |
| Anomaly | `PARTIAL` | proteção contra histórico insuficiente; sem validação operacional ampla |
| Confidence | `PARTIAL` | limites e propriedades; volume independente em escala não provado |
| Severity | `PARTIAL` | separado de confidence; impacto vs volume sem corpus completo |
| Sentinela | `FAILED` | RT-003 NORMAL_DAY conhecido |
| Forecast infrastructure | `PARTIAL` | registry/calibrators/shadow existem, sem linha completa de avaliação |
| Predictive evidence | `UNVERIFIED` | `INSUFFICIENT_DATA`, não há skill demonstrado |
| Storage | `PARTIAL` | chaos local; Turso/D1 remoto não ensaiados |
| Idempotency | `PARTIAL` | retry/local batch coberto; backends reais pendentes |
| Security | `PARTIAL` | auth/SSRF/fuzz local; WAF/rate limit não verificados |
| SSRF | `PARTIAL` | IP/scheme/redirect guard; DNS rebinding/proxy desconhecidos |
| API robustness | `FAILED` | `ZZ` retorna NORMAL 200; abuse suite/envelope passam, mas enumeração semântica de UF está ausente |
| Observability | `PARTIAL` | runtime, cycle, readiness e verdict; auditoria externa/freshness histórica faltam |
| Performance | `UNVERIFIED` | sem benchmark controlado 100–100k |
| Compliance | `BLOCKED_EXTERNAL` | revisão humana/termos das fontes não pode ser concluída pelo auditor |
| Operational readiness | `PARTIAL` | deploy/health observados; SLO histórico, WAF e failover faltam |

## Gate de promoção

### Atualização — gate editorial (2026-10-03)

O red-team reproduziu promoção por volume de conteúdo esportivo/editorial (incluindo “Brasil x Índia: onde assistir” e manchetes do Brasileirão). O Engine agora classifica o papel semântico do texto e rejeita clusters compostos apenas por `EDITORIAL_ONLY`/`SCHEDULED_CONTEXT`; sinais com apagão, evacuação, incêndio, interdição ou falha operacional continuam elegíveis. A regressão cobre volumes 10, 50, 100, 500 e 1000, paráfrases com tracking e quatro controles positivos. Resultado: 28/28 focados e 794/794 na suíte Python completa.

Forecast V2: **REPROVADO para promoção**. Exige corpus positivo/negativo real, unidade por evento, holdout temporal, Brier Skill positivo contra baseline, calibração com N suficiente, FPR/recall/lead time, shadow resolvido, rollback e nenhuma regressão por escopo. `UNKNOWN`, abstention e ausência de amostra não são negativos.

## Decisão sobre PULSO 1.0

- **CORE SITUATIONAL INTELLIGENCE:** `PARTIAL` — funcional e defensável em vários invariantes, mas RT-003 e clustering/proveniência sem evidência completa impedem declarar pronto sem ressalvas.
- **OPERATIONAL RELIABILITY:** `PARTIAL` — hardening, health, source runtime, breaker e chaos local existem; WAF, SLO histórico, bancos remotos e compliance permanecem abertos.
- **EXPERIMENTAL FORECAST INFRASTRUCTURE:** `PARTIAL` — infraestrutura de honestidade está funcional e atrás de shadow.
- **REAL PREDICTIVE EVIDENCE:** `UNVERIFIED` / `INSUFFICIENT_DATA` — não há demonstração estatística de skill.

Conclusão: o código suporta um **PULSO 1.0 limitado como inteligência situacional com motor preditivo experimental**, desde que a comunicação pública preserve as ressalvas acima. Não suporta declarar que o PULSO prevê corretamente.

## BLOCKED_EXTERNAL e próximos ataques

1. Configurar e verificar `ADMIN_TOKEN`, WAF/rate limit e audit trail na Cloudflare.
2. Ensaiar Turso remoto, D1 real, migrations e 100 retries após resposta perdida.
3. Persistir/validar série histórica de freshness, coverage e SLO.
4. Corrigir RT-003 sem elevar thresholds de forma que esconda positivos.
5. Medir provenance/clustering com cascatas e eventos genuinamente independentes.
6. Construir corpus histórico temporal e executar ablation/calibração fora do tempo.
7. Auditar dependências Python e histórico Git sem imprimir segredos.
8. Corrigir `GET /api/pulse/state/:uf` para rejeitar UFs inexistentes e adicionar teste de `ZZ`.
