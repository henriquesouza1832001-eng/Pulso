-- Pulso: schema inicial

CREATE TABLE sources (
  id              TEXT PRIMARY KEY,
  name            TEXT NOT NULL,
  domain          TEXT NOT NULL,
  type            TEXT NOT NULL CHECK (type IN ('rss','api','feed','page','scrape')),
  category        TEXT NOT NULL CHECK (category IN ('veiculo','agencia','oficial','regional')),
  url             TEXT NOT NULL,
  state           TEXT,
  trust_level     INTEGER NOT NULL DEFAULT 3 CHECK (trust_level BETWEEN 1 AND 5),
  update_interval INTEGER NOT NULL DEFAULT 300,
  enabled         INTEGER NOT NULL DEFAULT 1,
  last_fetch      INTEGER
);

CREATE TABLE events (
  id            TEXT PRIMARY KEY,
  title         TEXT NOT NULL,
  summary       TEXT,
  category      TEXT,
  state         TEXT,
  created_at    INTEGER NOT NULL,
  updated_at    INTEGER NOT NULL,
  pulso_score   INTEGER NOT NULL DEFAULT 0,
  article_count INTEGER NOT NULL DEFAULT 0,
  source_count  INTEGER NOT NULL DEFAULT 0,
  confirmation  TEXT NOT NULL DEFAULT 'uma_fonte'
    CHECK (confirmation IN ('uma_fonte','multiplas_fontes','fonte_oficial','em_desenvolvimento'))
);
CREATE INDEX idx_events_updated ON events (updated_at DESC);
CREATE INDEX idx_events_score   ON events (pulso_score DESC);
CREATE INDEX idx_events_state   ON events (state, updated_at DESC);

CREATE TABLE articles (
  id           TEXT PRIMARY KEY,
  source_id    TEXT NOT NULL REFERENCES sources (id),
  title        TEXT NOT NULL,
  description  TEXT,
  url          TEXT NOT NULL,
  published_at INTEGER NOT NULL,
  collected_at INTEGER NOT NULL,
  category     TEXT,
  state        TEXT,
  event_id     TEXT REFERENCES events (id),
  hash         TEXT NOT NULL UNIQUE
);
CREATE INDEX idx_articles_published ON articles (published_at DESC);
CREATE INDEX idx_articles_event     ON articles (event_id);
CREATE INDEX idx_articles_source    ON articles (source_id, published_at DESC);

CREATE TABLE entities (
  id   TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  type TEXT NOT NULL CHECK (type IN
    ('PERSON','ORGANIZATION','LOCATION','POLITICAL_PARTY','GOVERNMENT_BODY','EVENT')),
  UNIQUE (name, type)
);

CREATE TABLE article_entities (
  article_id TEXT NOT NULL REFERENCES articles (id),
  entity_id  TEXT NOT NULL REFERENCES entities (id),
  PRIMARY KEY (article_id, entity_id)
);
CREATE INDEX idx_article_entities_entity ON article_entities (entity_id);

CREATE TABLE metrics (
  event_id      TEXT NOT NULL REFERENCES events (id),
  timestamp     INTEGER NOT NULL,
  article_count INTEGER NOT NULL,
  source_count  INTEGER NOT NULL,
  velocity      REAL NOT NULL DEFAULT 0,
  pulso_score   INTEGER NOT NULL,
  PRIMARY KEY (event_id, timestamp)
);
CREATE INDEX idx_metrics_time ON metrics (timestamp DESC);
