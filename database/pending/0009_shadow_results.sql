-- Comparação V1 x V2 x desfecho (docs/engineering/ENGINE_V2_PLAN.md §5, prompt §52): base do portão de promoção.
-- Só linhas JÁ RESOLVIDAS (outcome 0 ou 1) e imutáveis (ON CONFLICT DO NOTHING). Chave (item, método): um mesmo evento ou
-- previsão pode ser comparado por métodos diferentes. Sem índice secundário; leitura por método/escopo varre a tabela
-- (pequena: milhares de linhas). Retenção de 180 dias, uma vez por dia.
CREATE TABLE IF NOT EXISTS shadow_results (
  item_id    TEXT NOT NULL,                       -- forecast_id ou event_id
  method     TEXT NOT NULL,
  scope      TEXT NOT NULL,                       -- BR | UF:MG
  p_v1       REAL NOT NULL CHECK (p_v1 >= 0 AND p_v1 <= 1),
  p_v2       REAL NOT NULL CHECK (p_v2 >= 0 AND p_v2 <= 1),
  outcome    INTEGER NOT NULL CHECK (outcome IN (0, 1)),
  created_at TEXT NOT NULL,
  PRIMARY KEY (item_id, method)
) WITHOUT ROWID;
