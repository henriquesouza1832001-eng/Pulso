# SLIs e SLOs iniciais do PULSO

> Metas **iniciais, para começar a medir**, não promessas. Nenhuma foi calibrada com série longa: a primeira tarefa operacional é registrar o SLI e só depois apertar a meta. Onde o SLI ainda não é medido hoje, está marcado `NÃO MEDIDO`. Fonte dos dados: `GET /api/health`, `/api/health/live`, `/api/health/ready`, `/api/admin/engine-status` (operador) e o log do ciclo do Engine (`py -m pulso_engine.pipeline`).

| # | SLI (o que se mede) | Meta inicial (SLO) | Como medir hoje | Estado |
|---|---|---|---|---|
| 1 | **Disponibilidade da API** — respostas não-5xx de `/api/health/live` | 99,0% em 30 dias | verificação externa de `/live` (healthcheck.yml roda a cada 30 min: resolução grossa) | PARCIAL (granularidade de 30 min; sem série de 30 dias guardada) |
| 2 | **Prontidão** — `/api/health/ready` = 200 (inclui banco) | 99,0% em 30 dias | idem | PARCIAL |
| 3 | **Latência da API pública** — p95 de GET público | p95 < 800 ms (borda, cache 15–60 s) | não há coleta de latência | NÃO MEDIDO |
| 4 | **Sucesso do ciclo do Engine** — ciclos terminados / ciclos disparados | 95% em 7 dias | workflow `Coleta` (conclusão por execução) | PARCIAL (derivável do histórico do Actions; sem painel) |
| 5 | **Atraso do ciclo** — idade do último Pulso (BR) | p95 ≤ 10 min; nunca > 15 min (`collection.stale`) | `/api/health` → `collection.age_seconds` | MEDIDO (instantâneo; sem histórico agregado) |
| 6 | **Frescor dos coletores** — idade do item mais novo por fonte (p50/p95/máx) e fração de fontes FRESH | ≥ 70% das fontes ativas FRESH; p95 ≤ limite da classe (`source_freshness.DEFAULT_STALE_AFTER_MIN`) | log do ciclo (`frescor: ...`), `batch["source_freshness"]`; **ainda não persistido no Worker** | MEDIDO NO ENGINE (não exposto na API) |
| 7 | **Sucesso do ingest** — lotes aceitos / enviados | ≥ 99% em 7 dias (sem contar 5xx do storage fora) | resposta do `/api/ingest` no log do Engine | PARCIAL |
| 8 | **Sucesso do storage** — escritas sem erro | ≥ 99,5% | `engine-status.budget`/`rows_today`; erros 5xx do ingest | PARCIAL (sem taxa de erro agregada) |
| 9 | **Persistência de previsões** — previsões criadas que chegam ao `forecasts`/`forecast_registry` | 100% das aceitas pelo ingest | `engine-status` (forecasts, registry, shadow) | MEDIDO (contagens) |
| 10 | **Cobertura de sensores críticos** — fontes OFFICIAL FRESH / OFFICIAL ativas | ≥ 80% | `freshness_coverage` por classe no log do ciclo | MEDIDO NO ENGINE (não exposto) |

## Regras
- **Orçamento de erro** (SLO 99%): ~7 h/mês. Estourou → só correção de confiabilidade até voltar.
- **Medir antes de apertar:** qualquer meta acima só muda com ≥ 14 dias de série real. Nenhuma meta é uma afirmação sobre a produção hoje.
- **O que NÃO é SLO:** acerto de previsão e latência de eventos (são métricas científicas, em `docs/reliability/` e `FORECAST_V2_ENGINEERING.md`).
- **Cardinalidade:** SLIs são por classe de fonte, não por fonte, no painel; por fonte só nos detalhes de diagnóstico.

## Lacunas para fechar (dono: plataforma)
1. Persistir `source_freshness` e `freshness_coverage` (migration + campo opcional do ingest + `engine-status`): ver `docs/maturity/PLATFORM_MATURITY.md` §Handoffs.
2. Guardar a série de `/health` (um registro por ciclo) para calcular 1, 2 e 5 com histórico.
3. Medir latência de GET público (log do Worker com duração por rota, sem payload).
