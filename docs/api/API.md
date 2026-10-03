# API do PULSO

Base: Worker `apps/worker`. Contratos de tipo: `packages/shared/src/contracts.ts`. **Não mude um contrato silenciosamente.**

| Endpoint | Cache (`Cache-Control`) | Estado |
|---|---|---|
| `GET /api/health` | `no-store` | ✅ |
| `GET /api/health/live` | `no-store` | ✅ liveness: o Worker responde (não toca o banco) |
| `GET /api/health/ready` | `no-store` | ✅ readiness: `ready`, `degraded` (200, com `reasons`: coleta atrasada etc.) ou `not_ready` (**503**, banco fora) |
| `GET /api/pulse` · `/api/pulse/br` | 10 s (+SWR) | ✅ |
| `GET /api/pulse/state/:uf` | 10 s | ✅ |
| `GET /api/pulse/city/:slug` | 10 s | ✅ |
| `GET /api/events?category=&state=&limit=` | 5 s | ✅ |
| `GET /api/events/:id` (evento + sinais/fontes) | 5 s | ✅ |
| `GET /api/map` (GeoJSON) | 10 s | ✅ |
| `POST /api/ingest` (Engine → Worker, `Authorization: Bearer`) | — | ✅ |
| `/api/events/live` (SSE), `/api/trending`, `/api/signals`, `/api/timeline`, `/api/search`, `/api/cameras`, `/api/traffic`, `/api/news`, `/api/social` | definir por endpoint | ⏳ |

## Convenções
- Rotas `/api/admin/*`: Bearer `INGEST_TOKEN`; se o segredo opcional `ADMIN_TOKEN` existir, as rotas de OPERADOR (`engine-status`, `overview`, `turso-ping`, `calibrators`, `forecast-registry`, `forecast-trajectory`, `drivers`, `shadow-results`) só aceitam ele, e as que o Engine lê (`series`, `signals`, `observations`, `investigations`, `events-digest`, `pulse-history`, `forecasts/open`) aceitam os dois.
- Erros: `{ "error": "codigo", "detail"?: "...", "request_id": "..." }` com status HTTP correto. `request_id` é o mesmo do cabeçalho `X-Request-Id` (presente em TODA resposta; o chamador pode enviar o seu, 8–64 caracteres `[A-Za-z0-9._-]`) e liga a resposta ao log do Worker. Falha interna é sempre `500 internal_error`, sem stack. `POST /api/ingest` acima de 8 MB responde `413 payload_too_large`.
- Entrada validada com zod; UF `^[A-Z]{2}$`, slug `^[a-z0-9-]{1,80}$`.
- `POST /api/ingest`: fail-closed (sem `INGEST_TOKEN` configurado → 401), idempotente (upsert por `event_id` e `scope+timestamp`).
- Sem dados → `score 0`, nível 1. A API nunca inventa atividade.
- Exemplo de evento: ver `PulsoEvent` (campos `severity`, `confidence`, `pulse`, `alert_level`, `score_breakdown`).

## Dados para o front (públicos)
| Endpoint | Função | Cache |
|---|---|---|
| `GET /api/pulse/history?scope=BR&hours=24` | Série real do Pulso (`points[{timestamp,score,alert_level}]`), máx. 168 h | 30 s |
| `GET /api/pulse/states` | Pulso mais recente de cada UF com atividade (snapshots com mais de 30 min são descartados) | 15 s |
| `GET /api/history?min_level=3&days=30&limit=20` | Histórico de inteligência: momentos de nível alto. `entries[]` mistura `kind: "event"` (pico do evento: `level`, `peak_pulse`, `date`) e `kind: "national"` (episódio do Pulso nacional: início, fim, duração, pico). Usa o PICO guardado, não o nível atual (que decai) | 60 s |
| `GET /api/stats` | Contadores do indicador nacional com a janela correta (`signals_2h`, `active_events`, `states_active`, `alerts`, fontes online) | 15 s |
| `GET /api/cameras` | Catálogo de câmeras (`CameraFeed[]`): `id`, `label`, `city`, `state` (UF ou `BR`), `provider`, `attribution`, `page_url` (clique leva à origem), `preview` (`{type: "iframe"|"hls", url}` do PRÓPRIO provedor, ou `null` = só cartão com link), `lat`/`lon` (ou `null`). Estático, sem banco; o PULSO é só o placeholder e nunca retransmite o vídeo | 300 s |

`delta_2h` em `/api/pulse/*` só é calculado com um ponto real a ±20 min de 2 h atrás; caso contrário vem `null`.

## Previsões (públicas)
| Endpoint | Função | Cache |
|---|---|---|
| `GET /api/forecasts?status=&scope=&limit=` | Previsões (probabilidades, nunca fatos), com `experimental` | 15 s |
| `GET /api/forecasts/:id` | Uma previsão com evidências e, se resolvida, resultado e Brier | 15 s |
| `GET /api/forecasts/track-record` | Histórico de acertos por método e calibração (Brier, skill, faixas, e por método: `precision`, `recall`, `false_positive_rate` no corte `cutoff` = 0,5 e `calibration_error` (ECE); `null` quando não há amostra) | 60 s |

A métrica (`metric`) de uma previsão diz o que ela prevê: `pulse` (Pulso do Brasil) ou `signals_<categoria>` (volume de sinais de um tema, em minúsculas: `signals_weather`, `signals_traffic`, `signals_politics`...), com escopo `BR` ou `UF:xx`. As previsões de volume trazem em `evidence` o volume atual, o baseline, o histórico usado e `leading_indicators` (categorias que costumam subir antes e estão acima do normal agora; são **contexto**, não alteram a probabilidade). Nenhuma mudança de contrato: `metric` já era texto livre `[a-z_]{1,40}`.

O front deve exibir sempre o rótulo **PREVISÃO**, a probabilidade com seu intervalo e o selo EXPERIMENTAL quando `experimental` for verdadeiro.

## Rotas internas (Engine e painel admin)
Exigem `Authorization: Bearer <INGEST_TOKEN>` (fail-closed) e nunca são cacheadas. Não fazem parte da API pública. Limites do lote de `POST /api/ingest`: até 500 fontes, 200 eventos, 500 sinais, 200 pulsos, 200 linhas de saúde, 3000 linhas de série e 200 previsões.

| Endpoint | Função |
|---|---|
| `POST /api/ingest` | Lote do Engine. Campo opcional `catalog_complete` (padrão `false`): quando `true`, `sources` é o catálogo completo de fontes ativas e o Worker marca `enabled = 0` nas que não vierem (somem de `/api/health` e do painel "Fontes ativas"); fonte que volta a vir é reativada. Aceita `series` (`SeriesPoint[]`): contagem por escopo×categoria×janela de 5 min, gravada com o MAIOR valor já visto e retida por 90 dias. Aceita `observations` (`ObservationPoint[]`, até 2.000 por lote): histórico agregado por HORA × escopo × categoria × classe de fonte (`signals`, `sources`, `duplicates`), só horas fechadas, gravado com o MAIOR valor já visto (reenvio idêntico não grava nada), retido por 90 dias; em modo `economy` do governador só `BR`, em `critical` nada. Aceita `investigations` (`InvestigationPoint[]`, até 200 por lote): só as investigações do Sentinela que MUDARAM, gravadas só se algo mudou (`started_at` e `initial_anomaly` nunca são reescritos); em `economy` só `NEW` e `CLOSED`, em `critical` nada; retenção de 30 dias depois de `CLOSED`. Aceita, opcionais, `forecast_registry` (trilha de auditoria imutável da previsão: snapshot JSON + sha256; até 200), `shadow_results` (V1 × V2 × desfecho, só linhas resolvidas e imutáveis por item+método; até 500) e `driver_registry` (drivers validados; um driver `DISABLED` nunca é reativado pelo ingest; até 200). Em modo `economy` do governador só `forecast_registry` continua; em `critical` nada. Retenção de 180 dias. Também aceita `source_runtime` (`SourceRuntimeRow[]`, até 400: estado de frescor e de circuit breaker por fonte, só o que mudou ou o batimento periódico; só avança no tempo) e `engine_cycle` (resumo do último ciclo; uma linha `latest`), gravados em lote **à parte e best-effort**: se falharem, o dado de verdade já está salvo e a resposta traz `observability: "failed"` (`ok` | `skipped` | `failed`). Também aceita `calibrators` (`CalibratorArtifact[]`, até 20): artefato de calibração versionado, **imutável** (uma linha por versão; só o `status` evolui `candidate → active → retired`, e `retired` é terminal); `artifact` é JSON de até 20 KB. |
| `GET /api/admin/series?hours=48&scope=BR` | Histórico de contagens para o baseline do Engine. |
| `GET /api/admin/observations?hours=336&scope=&category=` | Histórico agregado por hora (mais novas primeiro, até 20 000 por padrão): base do baseline sazonal e das tendências. |
| `GET /api/admin/investigations?status=active\|all&limit=200` | Investigações do Sentinela (`active` = não encerradas), mais recentes primeiro. `reasons` é um JSON com os motivos. O Engine reconstrói o estado a partir daqui. |
| `GET /api/admin/engine-status` | Painel do motor numa chamada: banco realmente em uso, orçamento de escrita do dia e modo do governador, investigações ativas, previsões abertas/resolvidas, linhas do registro de previsões, `shadow_results` (o que o portão de promoção conta; mínimo 200), drivers ativos e a última hora do histórico agregado. |
| `GET /api/admin/calibrators?status=active` | Calibradores versionados (artefato e status). O Engine usa só o `active`. |
| `GET /api/admin/forecast-trajectory?scope=BR&metric=signals_weather&hours=48` | Trajetória das previsões do escopo e da métrica (cada ponto é uma previsão imutável, mais `p_v2_shadow` quando existe): como evoluíram e como terminaram. |
| `GET /api/admin/source-runtime` | Estado por fonte (frescor, transporte, circuit breaker). O Engine lê o breaker daqui no início do ciclo. |
| `GET /api/admin/shadow-results?method=&scope=&limit=` | V1 × V2 × desfecho (mais novas primeiro): entrada do portão de promoção. |
| `GET /api/admin/drivers?state=ACTIVE` | Registro de drivers antecedentes e seu estado. |
| `GET /api/admin/forecast-registry?hours=72` / `?forecast_id=fc-...` | Ids já registrados (o Engine envia só o que falta) / entrada completa para reproduzir uma previsão. |
| `GET /api/admin/signals?hours=24` | Sinais recentes gravados (até 10 000, **os mais novos primeiro**), para o Engine agrupar com estado e reaproveitar `event_id`. |
| `GET /api/admin/events-digest?hours=24` | Resumo dos eventos gravados (`event_id`, `pulse`, `alert_level`, `status`, `signal_count`, `source_count`). O Engine só reenvia o que é novo ou mudou (limite de escrita do D1; ver ADR 0006). |
| `GET /api/admin/pulse-history?scope=BR&hours=72` | Série do Pulso: matéria-prima dos previsores e da resolução. |
| `GET /api/admin/forecasts/open` | Previsões abertas, para o Engine resolver as vencidas. |
| `GET /api/admin/overview` | Painel: eventos ativos, sinais nas últimas 24 h, último Pulso, e por fonte: estado, último sucesso e volume. |

`GET /api/events` e `GET /api/map` só listam eventos com atividade nas últimas 24 h; o evento antigo continua acessível por `GET /api/events/:id`.
