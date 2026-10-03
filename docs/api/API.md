# API do PULSO

Base: Worker `apps/worker`. Contratos de tipo: `packages/shared/src/contracts.ts`. **Não mude um contrato silenciosamente.**

| Endpoint | Cache (`Cache-Control`) | Estado |
|---|---|---|
| `GET /api/health` | `no-store` | ✅ |
| `GET /api/pulse` · `/api/pulse/br` | 10 s (+SWR) | ✅ |
| `GET /api/pulse/state/:uf` | 10 s | ✅ |
| `GET /api/pulse/city/:slug` | 10 s | ✅ |
| `GET /api/events?category=&state=&limit=` | 5 s | ✅ |
| `GET /api/events/:id` (evento + sinais/fontes) | 5 s | ✅ |
| `GET /api/map` (GeoJSON) | 10 s | ✅ |
| `POST /api/ingest` (Engine → Worker, `Authorization: Bearer`) | — | ✅ |
| `/api/events/live` (SSE), `/api/trending`, `/api/signals`, `/api/timeline`, `/api/search`, `/api/cameras`, `/api/traffic`, `/api/news`, `/api/social` | definir por endpoint | ⏳ |

## Convenções
- Erros: `{ "error": "codigo", "detail"?: "..." }` com status HTTP correto.
- Entrada validada com zod; UF `^[A-Z]{2}$`, slug `^[a-z0-9-]{1,80}$`.
- `POST /api/ingest`: fail-closed (sem `INGEST_TOKEN` configurado → 401), idempotente (upsert por `event_id` e `scope+timestamp`).
- Sem dados → `score 0`, nível 1. A API nunca inventa atividade.
- Exemplo de evento: ver `PulsoEvent` (campos `severity`, `confidence`, `pulse`, `alert_level`, `score_breakdown`).

## Dados para o front (públicos)
| Endpoint | Função | Cache |
|---|---|---|
| `GET /api/pulse/history?scope=BR&hours=24` | Série real do Pulso (`points[{timestamp,score,alert_level}]`), máx. 168 h | 30 s |
| `GET /api/pulse/states` | Pulso mais recente de cada UF com atividade (snapshots com mais de 30 min são descartados) | 15 s |
| `GET /api/stats` | Contadores do indicador nacional com a janela correta (`signals_2h`, `active_events`, `states_active`, `alerts`, fontes online) | 15 s |

`delta_2h` em `/api/pulse/*` só é calculado com um ponto real a ±20 min de 2 h atrás; caso contrário vem `null`.

## Previsões (públicas)
| Endpoint | Função | Cache |
|---|---|---|
| `GET /api/forecasts?status=&scope=&limit=` | Previsões (probabilidades, nunca fatos), com `experimental` | 15 s |
| `GET /api/forecasts/:id` | Uma previsão com evidências e, se resolvida, resultado e Brier | 15 s |
| `GET /api/forecasts/track-record` | Histórico de acertos por método e calibração | 60 s |

O front deve exibir sempre o rótulo **PREVISÃO**, a probabilidade com seu intervalo e o selo EXPERIMENTAL quando `experimental` for verdadeiro.

## Rotas internas (Engine e painel admin)
Exigem `Authorization: Bearer <INGEST_TOKEN>` (fail-closed) e nunca são cacheadas. Não fazem parte da API pública.

| Endpoint | Função |
|---|---|
| `POST /api/ingest` | Lote do Engine. Agora aceita `series` (`SeriesPoint[]`): contagem por escopo×categoria×janela de 5 min, gravada com o MAIOR valor já visto e retida por 90 dias. |
| `GET /api/admin/series?hours=48&scope=BR` | Histórico de contagens para o baseline do Engine. |
| `GET /api/admin/signals?hours=24` | Sinais recentes gravados (até 5000), para o Engine agrupar com estado e reaproveitar `event_id`. |
| `GET /api/admin/pulse-history?scope=BR&hours=72` | Série do Pulso: matéria-prima dos previsores e da resolução. |
| `GET /api/admin/forecasts/open` | Previsões abertas, para o Engine resolver as vencidas. |
| `GET /api/admin/overview` | Painel: eventos ativos, sinais nas últimas 24 h, último Pulso, e por fonte: estado, último sucesso e volume. |

`GET /api/events` e `GET /api/map` só listam eventos com atividade nas últimas 24 h; o evento antigo continua acessível por `GET /api/events/:id`.
