-- Dados FICTÍCIOS apenas para desenvolvimento local. Nunca aplicar em produção.
INSERT OR REPLACE INTO sources (id, name, domain, adapter, source_class, url, state) VALUES
 ('agencia-brasil','Agência Brasil','agenciabrasil.ebc.com.br','rss','NEWS_HIGH','https://agenciabrasil.ebc.com.br/rss/ultimasnoticias/feed.xml',NULL),
 ('prf','Polícia Rodoviária Federal','gov.br/prf','api','OFFICIAL','https://www.gov.br/prf',NULL);
INSERT OR REPLACE INTO source_health (source_id, status, last_check, last_success) VALUES
 ('agencia-brasil','ONLINE',strftime('%Y-%m-%dT%H:%M:%SZ','now'),strftime('%Y-%m-%dT%H:%M:%SZ','now')),
 ('prf','UNKNOWN',NULL,NULL);
INSERT OR REPLACE INTO events (id,title,summary,category,status,latitude,longitude,geo_precision,geo_confidence,state,city,severity,confidence,pulse,alert_level,score_breakdown,signal_count,source_count,detected_at,updated_at) VALUES
 ('ev-dev-1','[DEV] Acidente na BR-381','Dado fictício de desenvolvimento.','TRAFFIC','CONFIRMED',-19.92,-43.94,'STREET',80,'MG','Belo Horizonte',35,98,62,3,
  '[{"key":"confidence","label":"Confiança","points":15},{"key":"sources","label":"Diversidade de fontes","points":14},{"key":"velocity","label":"Velocidade","points":12},{"key":"anomaly","label":"Anomalia","points":11},{"key":"severity","label":"Severidade","points":7},{"key":"recency","label":"Recência","points":3}]',
  9,4,strftime('%Y-%m-%dT%H:%M:%SZ','now','-40 minutes'),strftime('%Y-%m-%dT%H:%M:%SZ','now')),
 ('ev-dev-2','[DEV] Temporal em São Paulo','Dado fictício de desenvolvimento.','WEATHER','DEVELOPING',-23.55,-46.63,'CITY',90,'SP','São Paulo',70,55,48,2,
  '[{"key":"severity","label":"Severidade","points":14},{"key":"velocity","label":"Velocidade","points":12},{"key":"anomaly","label":"Anomalia","points":10},{"key":"confidence","label":"Confiança","points":8},{"key":"sources","label":"Diversidade de fontes","points":4}]',
  5,2,strftime('%Y-%m-%dT%H:%M:%SZ','now','-20 minutes'),strftime('%Y-%m-%dT%H:%M:%SZ','now'));
INSERT OR REPLACE INTO pulse_history (scope,timestamp,score,alert_level,contributors) VALUES
 ('BR',strftime('%Y-%m-%dT%H:%M:%SZ','now','-2 hours'),38,2,'[]'),
 ('BR',strftime('%Y-%m-%dT%H:%M:%SZ','now'),55,3,'[{"scope":"MG","delta":9},{"scope":"SP","delta":8}]');
