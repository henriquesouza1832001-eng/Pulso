-- Registro de drivers (docs/engineering/ENGINE_V2_PLAN.md §3, prompt §11): indicador antecedente x alvo x escopo x defasagem.
-- Só um driver ACTIVE pode alterar a probabilidade de uma previsão. O registro guarda evidência estatística, não causalidade.
-- DISABLED é MANUAL e vence tudo: o ingest nunca reativa um driver desligado (a linha só muda por SQL do dono).
CREATE TABLE IF NOT EXISTS driver_registry (
  driver        TEXT NOT NULL,
  target        TEXT NOT NULL,
  scope         TEXT NOT NULL,                    -- BR | UF:MG
  lag_hours     INTEGER NOT NULL,
  correlation   REAL NOT NULL,
  pairs         INTEGER NOT NULL,                 -- horas distintas usadas na correlação
  samples       INTEGER NOT NULL,                 -- previsões resolvidas com e sem o driver
  brier_without REAL,
  brier_with    REAL,
  state         TEXT NOT NULL CHECK (state IN ('CANDIDATE','TESTING','ACTIVE','DEGRADED','DISABLED')),
  reason        TEXT NOT NULL DEFAULT '',
  updated_at    TEXT NOT NULL,
  PRIMARY KEY (driver, target, scope, lag_hours)
) WITHOUT ROWID;
