-- Séries agregadas por escopo x categoria x janela de 5 min. Base do baseline e das previsões.
-- Não guarda conteúdo de terceiros: só contagens, então pode ser retida por mais tempo que os sinais.
CREATE TABLE series (
  scope    TEXT NOT NULL,          -- BR | UF:MG
  category TEXT NOT NULL,
  bucket   TEXT NOT NULL,          -- início da janela de 5 min, ISO-8601 UTC
  signals  INTEGER NOT NULL,       -- sinais PUBLICADOS nessa janela
  sources  INTEGER NOT NULL,       -- fontes distintas nessa janela
  PRIMARY KEY (scope, category, bucket)
);
CREATE INDEX idx_series_bucket ON series (bucket);
