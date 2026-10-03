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

## Rotas internas (Engine e painel admin)
Exigem `Authorization: Bearer <INGEST_TOKEN>` (fail-closed) e nunca são cacheadas. Não fazem parte da API pública.

| Endpoint | Função |
|---|---|
| `POST /api/ingest` | Lote do Engine. Agora aceita `series` (`SeriesPoint[]`): contagem por escopo×categoria×janela de 5 min, gravada com o MAIOR valor já visto e retida por 90 dias. |
| `GET /api/admin/series?hours=48&scope=BR` | Histórico de contagens para o baseline do Engine. |
| `GET /api/admin/signals?hours=24` | Sinais recentes gravados (até 5000), para o Engine agrupar com estado e reaproveitar `event_id`. |
| `GET /api/admin/overview` | Painel: eventos ativos, sinais nas últimas 24 h, último Pulso, e por fonte: estado, último sucesso e volume. |

`GET /api/events` e `GET /api/map` só listam eventos com atividade nas últimas 24 h; o evento antigo continua acessível por `GET /api/events/:id`.
