-- Orçamento diário de escrita do D1 (plano gratuito: 100 mil linhas/dia). Ver docs/decisions/0008.
CREATE TABLE IF NOT EXISTS write_budget (
  day  TEXT PRIMARY KEY,           -- dia UTC (a cota zera às 00:00 UTC)
  rows INTEGER NOT NULL DEFAULT 0  -- linhas gravadas pelo ingest naquele dia
);

-- Índices que nenhuma consulta do Worker usa: cada atualização de evento pagava 2 linhas a mais por causa deles.
-- (a lista de eventos filtra por estado/status sobre uma tabela pequena, já limitada por updated_at)
DROP INDEX IF EXISTS idx_events_state;
DROP INDEX IF EXISTS idx_events_status;
