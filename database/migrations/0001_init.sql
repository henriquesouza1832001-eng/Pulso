-- PULSO schema v2 (Fase 1). Câmeras e trânsito entram em migrations próprias (Fase 2/3).
-- Timestamps em ISO-8601 UTC (TEXT). Nunca alterar produção sem migration correspondente.

CREATE TABLE sources (
  id              TEXT PRIMARY KEY,
  name            TEXT NOT NULL,
  domain          TEXT,
  adapter         TEXT NOT NULL,                     -- rss | api | feed | sitemap | social
  source_class    TEXT NOT NULL CHECK (source_class IN
    ('OFFICIAL','NEWS_HIGH','NEWS_REGIONAL','TRAFFIC_PROVIDER','SOCIAL_VERIFIED','SOCIAL','UNKNOWN')),
  url             TEXT NOT NULL,
  state           TEXT,
  update_interval INTEGER NOT NULL DEFAULT 300,      -- segundos
  enabled         INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE source_health (
  source_id    TEXT PRIMARY KEY REFERENCES sources (id),
  status       TEXT NOT NULL DEFAULT 'UNKNOWN' CHECK (status IN
    ('ONLINE','DEGRADED','RATE_LIMITED','OFFLINE','AUTH_ERROR','UNKNOWN')),
  last_check   TEXT,
  last_success TEXT,
  detail       TEXT
);

CREATE TABLE events (
  id              TEXT PRIMARY KEY,
  title           TEXT NOT NULL,
  summary         TEXT,
  category        TEXT NOT NULL,
  status          TEXT NOT NULL DEFAULT 'DETECTED' CHECK (status IN
    ('DETECTED','DEVELOPING','CONFIRMED','STABLE','RESOLVING','RESOLVED','DISPUTED')),
  latitude        REAL,
  longitude       REAL,
  geo_precision   TEXT,
  geo_confidence  INTEGER,
  state           TEXT,
  city            TEXT,
  severity        INTEGER NOT NULL DEFAULT 0 CHECK (severity BETWEEN 0 AND 100),
  confidence      INTEGER NOT NULL DEFAULT 0 CHECK (confidence BETWEEN 0 AND 100),
  pulse           INTEGER NOT NULL DEFAULT 0 CHECK (pulse BETWEEN 0 AND 100),
  alert_level     INTEGER NOT NULL DEFAULT 1 CHECK (alert_level BETWEEN 1 AND 5),
  score_breakdown TEXT NOT NULL DEFAULT '[]',        -- JSON: ScoreContribution[]
  signal_count    INTEGER NOT NULL DEFAULT 0,
  source_count    INTEGER NOT NULL DEFAULT 0,
  detected_at     TEXT NOT NULL,
  updated_at      TEXT NOT NULL,
  resolved_at     TEXT
);
CREATE INDEX idx_events_updated ON events (updated_at DESC);
CREATE INDEX idx_events_pulse   ON events (pulse DESC);
CREATE INDEX idx_events_state   ON events (state, updated_at DESC);
CREATE INDEX idx_events_status  ON events (status, updated_at DESC);

CREATE TABLE signals (
  id             TEXT PRIMARY KEY,
  source_id      TEXT NOT NULL REFERENCES sources (id),
  source_class   TEXT NOT NULL,
  timestamp      TEXT NOT NULL,
  collected_at   TEXT NOT NULL,
  title          TEXT NOT NULL,
  text           TEXT,
  url            TEXT,
  canonical_url  TEXT,
  author         TEXT,
  category       TEXT NOT NULL,
  latitude       REAL,
  longitude      REAL,
  geo_precision  TEXT,
  geo_confidence INTEGER,
  state          TEXT,
  city           TEXT,
  reliability    INTEGER NOT NULL DEFAULT 50,
  hash           TEXT NOT NULL UNIQUE,               -- deduplicação
  event_id       TEXT REFERENCES events (id)
);
CREATE INDEX idx_signals_time   ON signals (timestamp DESC);
CREATE INDEX idx_signals_event  ON signals (event_id);
CREATE INDEX idx_signals_source ON signals (source_id, timestamp DESC);

CREATE TABLE event_sources (
  event_id     TEXT NOT NULL REFERENCES events (id),
  source_id    TEXT NOT NULL REFERENCES sources (id),
  signal_count INTEGER NOT NULL DEFAULT 1,
  first_seen   TEXT NOT NULL,
  PRIMARY KEY (event_id, source_id)
);

CREATE TABLE locations (
  id        TEXT PRIMARY KEY,
  name      TEXT NOT NULL,
  kind      TEXT NOT NULL CHECK (kind IN ('REGION','STATE','CITY','NEIGHBORHOOD','STREET','POINT')),
  state     TEXT,
  parent_id TEXT REFERENCES locations (id),
  latitude  REAL,
  longitude REAL
);
CREATE INDEX idx_locations_name ON locations (name);

CREATE TABLE keywords (                              -- atualizável sem redeploy
  id      INTEGER PRIMARY KEY AUTOINCREMENT,
  family  TEXT NOT NULL,
  term    TEXT NOT NULL,
  weight  REAL NOT NULL DEFAULT 1.0,
  enabled INTEGER NOT NULL DEFAULT 1,
  UNIQUE (family, term)
);

CREATE TABLE entities (
  id   TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  type TEXT NOT NULL CHECK (type IN
    ('PERSON','ORGANIZATION','LOCATION','POLITICAL_PARTY','GOVERNMENT_BODY','EVENT')),
  UNIQUE (name, type)
);

CREATE TABLE event_entities (
  event_id  TEXT NOT NULL REFERENCES events (id),
  entity_id TEXT NOT NULL REFERENCES entities (id),
  PRIMARY KEY (event_id, entity_id)
);
CREATE INDEX idx_event_entities_entity ON event_entities (entity_id);

CREATE TABLE pulse_history (
  scope        TEXT NOT NULL,                        -- BR | UF:MG | CITY:belo-horizonte
  timestamp    TEXT NOT NULL,
  score        INTEGER NOT NULL,
  alert_level  INTEGER NOT NULL,
  contributors TEXT NOT NULL DEFAULT '[]',           -- JSON
  PRIMARY KEY (scope, timestamp)
);

CREATE TABLE metrics (
  event_id     TEXT NOT NULL REFERENCES events (id),
  timestamp    TEXT NOT NULL,
  signal_count INTEGER NOT NULL,
  source_count INTEGER NOT NULL,
  velocity     REAL NOT NULL DEFAULT 0,
  pulse        INTEGER NOT NULL,
  PRIMARY KEY (event_id, timestamp)
);
