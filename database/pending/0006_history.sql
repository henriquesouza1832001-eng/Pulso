-- Passo 1 do Sentinela (docs/research/SPEC_01_HISTORY.md): memória do motor em contagens agregadas por HORA.
-- Só contagens, sem conteúdo de terceiros. Sem índice secundário (cada índice dobra o custo de escrita no banco);
-- a leitura é sempre por (scope, category) + faixa de hora, coberta pela chave primária.
CREATE TABLE IF NOT EXISTS signal_observations (
  scope        TEXT NOT NULL,                -- BR | UF:MG
  category     TEXT NOT NULL,
  source_class TEXT NOT NULL,                -- OFFICIAL | NEWS_HIGH | NEWS_REGIONAL | SOCIAL | ...
  hour         TEXT NOT NULL,                -- início da hora, ISO-8601 UTC (HH:00:00Z)
  signals      INTEGER NOT NULL,             -- sinais distintos (já deduplicados por hash)
  sources      INTEGER NOT NULL,             -- fontes distintas
  duplicates   INTEGER NOT NULL DEFAULT 0,   -- cópias descartadas na deduplicação (base do duplicate_ratio)
  PRIMARY KEY (scope, category, source_class, hour)
) WITHOUT ROWID;
