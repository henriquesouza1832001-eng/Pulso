-- Passo 5 do Sentinela (docs/research/SPEC_05_SENTINEL.md): investigações proativas com estado.
-- Escrita condicional (só o que mudou) e retenção de 30 dias depois de CLOSED. `last_anomalous_at` é guardado porque o
-- esfriamento (RESOLVING -> CLOSED) depende da última atividade ANORMAL, não da última atualização.
CREATE TABLE IF NOT EXISTS investigations (
  id                    TEXT PRIMARY KEY,   -- inv-<sha1(scope|category|hora de abertura)[:10]>
  scope                 TEXT NOT NULL,      -- BR | UF:MG
  category              TEXT NOT NULL,
  status                TEXT NOT NULL CHECK (status IN ('NEW','INVESTIGATING','CORRELATING','WAITING_CONFIRMATION','CONFIRMED','DISPUTED','RESOLVING','CLOSED')),
  started_at            TEXT NOT NULL,
  last_update           TEXT NOT NULL,
  last_anomalous_at     TEXT,
  initial_anomaly       REAL NOT NULL,
  anomaly               REAL NOT NULL,
  evidence_count        INTEGER NOT NULL,
  official_confirmation INTEGER NOT NULL DEFAULT 0,
  reasons               TEXT NOT NULL DEFAULT '[]'  -- JSON: por que o Sentinela investigou
);
CREATE INDEX IF NOT EXISTS idx_investigations_status ON investigations (status, last_update);
