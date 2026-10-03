# SPEC 08 — Tabelas e payload da validação V2

> Para quem implementa a parte compartilhada (migrations em `database/pending/`, ingest, rotas admin, governador). Código puro já existe: `validation/metrics.py`, `shadow_compare.py`, `forecast_registry.py`, `intelligence/driver_validator.py`. Numeração conforme `ENGINE_V2_PLAN.md` §3 (0008, 0009, 0010). Todas `IF NOT EXISTS`, aditivas, **sem índice secundário**, escrita condicional, entrada no `write_budget`.

## 0008 `forecast_registry` (imutável)
```sql
CREATE TABLE IF NOT EXISTS forecast_registry (
  forecast_id   TEXT PRIMARY KEY,   -- o mesmo de forecasts.id
  created_at    TEXT NOT NULL,
  snapshot      TEXT NOT NULL,      -- JSON canônico: features, versões, flags, probabilidade, método, escopo, limiar
  snapshot_hash TEXT NOT NULL       -- sha256 do snapshot
) WITHOUT ROWID;
```
Payload opcional `forecast_registry`: lista de `{forecast_id, created_at, snapshot, snapshot_hash}` (saída de `forecast_registry.build_entry`). **Escrita**: `INSERT OR IGNORE` (imutável); o Engine só envia ids ainda não registrados (`new_entries`). Retenção: 180 dias.

## 0009 `shadow_results`
```sql
CREATE TABLE IF NOT EXISTS shadow_results (
  item_id TEXT PRIMARY KEY,         -- forecast_id (ou event_id) comparado
  scope   TEXT NOT NULL,
  method  TEXT NOT NULL,
  p_v1    REAL NOT NULL,
  p_v2    REAL NOT NULL,
  outcome INTEGER CHECK (outcome IN (0,1)),  -- NULL até resolver
  created_at TEXT NOT NULL
) WITHOUT ROWID;
```
Payload opcional `shadow_results` (`shadow_compare.shadow_row` + `created_at`). **Escrita**: upsert que só preenche `outcome` quando antes era NULL; `p_v1/p_v2` imutáveis. Rota `GET /api/admin/shadow-results?method=&since=` para o Engine ler as linhas resolvidas e rodar `promotion_gate`. Retenção: 90 dias.

## 0010 `driver_registry`
```sql
CREATE TABLE IF NOT EXISTS driver_registry (
  driver TEXT NOT NULL, target TEXT NOT NULL, scope TEXT NOT NULL,
  lag_hours INTEGER NOT NULL, correlation REAL NOT NULL, pairs INTEGER NOT NULL, samples INTEGER NOT NULL,
  brier_without REAL, brier_with REAL,
  state TEXT NOT NULL CHECK (state IN ('CANDIDATE','TESTING','ACTIVE','DEGRADED','DISABLED')),
  reason TEXT NOT NULL, updated_at TEXT NOT NULL,
  PRIMARY KEY (driver, target, scope)
) WITHOUT ROWID;
```
Payload opcional `driver_registry` (`driver_validator.registry_row` + `updated_at`). **Escrita**: só quando `state` ou `reason` mudam, ou a cada 6 h para atualizar métricas. `DISABLED` nunca é sobrescrito pelo Engine. Rota `GET /api/admin/drivers`.

## Governador
Modo `economy`: grava só `shadow_results` com `outcome` resolvido e `driver_registry` com mudança de estado. Modo `critical`: nada destas três tabelas.

## Ordem de uso no ciclo (atrás das flags, pelo dono do pipeline)
1. Ao criar uma previsão: `build_entry(...)` → `payload.forecast_registry` (só novas).
2. Com V2 em shadow: por previsão, `shadow_row(id, scope, method, p_v1, p_v2, outcome=None)`; ao resolver, preencher o desfecho.
3. Periodicamente: ler `shadow-results` resolvidas → `promotion_gate(rows)`; registrar o resultado (e `reasons`) no log do ciclo. Nenhuma flag V2 passa de OFF sem `passed: true`.
