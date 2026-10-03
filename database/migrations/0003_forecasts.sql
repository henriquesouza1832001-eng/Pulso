-- Previsões: probabilidade calibrada, registrada ANTES do resultado e pontuada depois (docs/architecture/PREDICTION.md).
-- A previsão em si é imutável: só os campos de resolução podem mudar (garantido no upsert do /api/ingest).
CREATE TABLE forecasts (
  id              TEXT PRIMARY KEY,
  kind            TEXT NOT NULL CHECK (kind IN ('NOWCAST','EVENT','QUANTITY','OPEN')),
  question        TEXT NOT NULL,
  scope           TEXT NOT NULL,                 -- BR | UF:MG
  metric          TEXT NOT NULL,                 -- ex.: pulse (Pulso do escopo)
  comparator      TEXT NOT NULL CHECK (comparator IN ('gte','lte')),
  threshold       REAL NOT NULL,
  method          TEXT NOT NULL,
  method_version  TEXT NOT NULL,
  probability     REAL NOT NULL CHECK (probability > 0 AND probability < 1),  -- nunca 0 nem 1
  interval_low    REAL NOT NULL,
  interval_high   REAL NOT NULL,
  horizon_minutes INTEGER NOT NULL,
  created_at      TEXT NOT NULL,
  resolves_at     TEXT NOT NULL,
  evidence        TEXT NOT NULL DEFAULT '{}',    -- JSON: o que sustentou a previsão
  status          TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','resolved','void')),
  outcome         INTEGER CHECK (outcome IN (0,1)),
  observed_value  REAL,
  resolved_at     TEXT,
  brier           REAL
);
CREATE INDEX idx_forecasts_status_resolves ON forecasts (status, resolves_at);
CREATE INDEX idx_forecasts_method_status   ON forecasts (method, status);
CREATE INDEX idx_forecasts_created         ON forecasts (created_at DESC);
