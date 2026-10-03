-- Estado de execução por fonte (RT-002 + circuit breaker) e resumo do último ciclo do Engine (observabilidade).
-- `source_runtime`: UMA linha por fonte, gravada só quando algo MUDA (estado de frescor/transporte/breaker) ou num batimento
-- periódico (decidido pelo Engine), nunca a cada ciclo: cabe no orçamento de escrita (docs/decisions/0008). Os campos numéricos
-- valem "no instante updated_at". Sem chave estrangeira de propósito: o governador pode descartar `sources` em modo economia.
CREATE TABLE IF NOT EXISTS source_runtime (
  source_id            TEXT PRIMARY KEY,
  transport            TEXT NOT NULL,
  freshness_state      TEXT NOT NULL CHECK (freshness_state IN ('FRESH','STALE','EMPTY','QUIET','UNKNOWN','UNAVAILABLE')),
  newest_item_age_min  REAL,
  last_content_advance TEXT,
  records              INTEGER NOT NULL DEFAULT 0 CHECK (records >= 0),
  new_records          INTEGER NOT NULL DEFAULT 0 CHECK (new_records >= 0),
  duplicate_records    INTEGER NOT NULL DEFAULT 0 CHECK (duplicate_records >= 0),
  breaker_state        TEXT NOT NULL DEFAULT 'CLOSED' CHECK (breaker_state IN ('CLOSED','OPEN','HALF_OPEN')),
  consecutive_failures INTEGER NOT NULL DEFAULT 0 CHECK (consecutive_failures >= 0),
  next_attempt_at      TEXT,
  opened_count         INTEGER NOT NULL DEFAULT 0 CHECK (opened_count >= 0),
  breaker_reason       TEXT,
  updated_at           TEXT NOT NULL
) WITHOUT ROWID;

-- `engine_cycle`: UMA linha ('latest'), regravada a cada ciclo só se o ciclo for mais novo (idempotente sob reenvio).
CREATE TABLE IF NOT EXISTS engine_cycle (
  id         TEXT PRIMARY KEY CHECK (id = 'latest'),
  cycle_at   TEXT NOT NULL,
  duration_s REAL,
  summary    TEXT NOT NULL                       -- JSON: contagens, frescor agregado, cobertura por família, flags (sem segredos)
) WITHOUT ROWID;
