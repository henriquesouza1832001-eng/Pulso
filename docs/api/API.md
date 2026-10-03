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
| `GET /api/history?min_level=3&days=30&limit=20` | Histórico de inteligência: momentos de nível alto. `entries[]` mistura `kind: "event"` (pico do evento: `level`, `peak_pulse`, `date`) e `kind: "national"` (episódio do Pulso nacional: início, fim, duração, pico). Usa o PICO guardado, não o nível atual (que decai) | 60 s |
| `GET /api/stats` | Contadores do indicador nacional com a janela correta (`signals_2h`, `active_events`, `states_active`, `alerts`, fontes online) | 15 s |
| `GET /api/cameras` | Catálogo de câmeras (`CameraFeed[]`): `id`, `label`, `city`, `state` (UF ou `BR`), `provider`, `attribution`, `page_url` (clique leva à origem), `preview` (`{type: "iframe"|"hls", url}` do PRÓPRIO provedor, ou `null` = só cartão com link), `lat`/`lon` (ou `null`). Estático, sem banco; o PULSO é só o placeholder e nunca retransmite o vídeo | 300 s |

`delta_2h` em `/api/pulse/*` só é calculado com um ponto real a ±20 min de 2 h atrás; caso contrário vem `null`.

## Previsões (públicas)
| Endpoint | Função | Cache |
|---|---|---|
| `GET /api/forecasts?status=&scope=&limit=` | Previsões (probabilidades, nunca fatos), com `experimental` | 15 s |
| `GET /api/forecasts/:id` | Uma previsão com evidências e, se resolvida, resultado e Brier | 15 s |
| `GET /api/forecasts/track-record` | Histórico de acertos por método e calibração | 60 s |

A métrica (`metric`) de uma previsão diz o que ela prevê: `pulse` (Pulso do Brasil) ou `signals_<categoria>` (volume de sinais de um tema, em minúsculas: `signals_weather`, `signals_traffic`, `signals_politics`...), com escopo `BR` ou `UF:xx`. As previsões de volume trazem em `evidence` o volume atual, o baseline, o histórico usado e `leading_indicators` (categorias que costumam subir antes e estão acima do normal agora; são **contexto**, não alteram a probabilidade). Nenhuma mudança de contrato: `metric` já era texto livre `[a-z_]{1,40}`.

O front deve exibir sempre o rótulo **PREVISÃO**, a probabilidade com seu intervalo e o selo EXPERIMENTAL quando `experimental` for verdadeiro.

## Rotas internas (Engine e painel admin)
Exigem `Authorization: Bearer <INGEST_TOKEN>` (fail-closed) e nunca são cacheadas. Não fazem parte da API pública. Limites do lote de `POST /api/ingest`: até 500 fontes, 200 eventos, 500 sinais, 200 pulsos, 200 linhas de saúde, 3000 linhas de série e 200 previsões.

| Endpoint | Função |
|---|---|
| `POST /api/ingest` | Lote do Engine. Campo opcional `catalog_complete` (padrão `false`): quando `true`, `sources` é o catálogo completo de fontes ativas e o Worker marca `enabled = 0` nas que não vierem (somem de `/api/health` e do painel "Fontes ativas"); fonte que volta a vir é reativada. Aceita `series` (`SeriesPoint[]`): contagem por escopo×categoria×janela de 5 min, gravada com o MAIOR valor já visto e retida por 90 dias. |
| `GET /api/admin/series?hours=48&scope=BR` | Histórico de contagens para o baseline do Engine. |
| `GET /api/admin/signals?hours=24` | Sinais recentes gravados (até 10 000, **os mais novos primeiro**), para o Engine agrupar com estado e reaproveitar `event_id`. |
| `GET /api/admin/events-digest?hours=24` | Resumo dos eventos gravados (`event_id`, `pulse`, `alert_level`, `status`, `signal_count`, `source_count`). O Engine só reenvia o que é novo ou mudou (limite de escrita do D1; ver ADR 0006). |
| `GET /api/admin/pulse-history?scope=BR&hours=72` | Série do Pulso: matéria-prima dos previsores e da resolução. |
| `GET /api/admin/forecasts/open` | Previsões abertas, para o Engine resolver as vencidas. |
| `GET /api/admin/overview` | Painel: eventos ativos, sinais nas últimas 24 h, último Pulso, e por fonte: estado, último sucesso e volume. |

`GET /api/events` e `GET /api/map` só listam eventos com atividade nas últimas 24 h; o evento antigo continua acessível por `GET /api/events/:id`.
