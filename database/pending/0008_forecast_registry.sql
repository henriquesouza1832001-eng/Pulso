-- Trilha de auditoria das previsões (docs/engineering/ENGINE_V2_PLAN.md §3, prompt §16/§55): o que o modelo viu quando previu.
-- IMUTÁVEL: uma linha por previsão, gravada uma vez (ON CONFLICT DO NOTHING). O snapshot é texto JSON canônico
-- (features, versões do modelo/features/baseline, flags ativas, probabilidade, método, escopo, limiar) e o hash prova que
-- não foi alterado depois. Sem conteúdo de terceiros. Retenção de 180 dias (a previsão em si fica em `forecasts`).
CREATE TABLE IF NOT EXISTS forecast_registry (
  forecast_id   TEXT PRIMARY KEY,
  created_at    TEXT NOT NULL,
  snapshot      TEXT NOT NULL,
  snapshot_hash TEXT NOT NULL
) WITHOUT ROWID;
