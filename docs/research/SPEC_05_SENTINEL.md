# SPEC 05 — Integração de tendências, anomalia v2 e Sentinela

> Passos 3–5 da ordem de `docs/CURRENT_ENGINE_STATE.md` §7. O código puro já existe; esta spec cobre só o que toca arquivos compartilhados (pipeline, migration, ingest, Worker, workflow).

## 1. Código novo (puro, testado, sem rede)
- `engine/pulso_engine/intelligence/trends.py`: `window_metrics`, `trend_state` (`RISING | STABLE_HIGH | STABLE | FALLING | QUIET | INSUFFICIENT`), `persistence_min`, `trends`.
- `engine/pulso_engine/anomaly.py`: `window_anomaly(count, minutes, base)` e `percentile_rank`; com baseline inválido devolve `status: "BASELINE INSUFICIENTE"` e score 0.
- `engine/pulso_engine/research/sentinel.py`: `detect_candidates`, `should_investigate` (gatilho configurável em `SentinelConfig`), `find_active` (sem pesquisa repetida), `advance` (NEW → INVESTIGATING → RESOLVING → CLOSED; devolve só o que mudou).
- `engine/pulso_engine/radar.py`: `analyze(signals, obs_rows, active, now, cfg, duplicates_by_hash, emerging)`; `main` delega ao `pipeline.main`.

## 2. Integração no pipeline (turno de commit exigido)
Em `pipeline.run_once`, depois de `build_series`/`build_observations` e antes de montar o retorno:
```python
from .radar import analyze
radar = analyze(list(all_signals.values()), obs_rows, active_investigations, now, duplicates_by_hash=dups)
batch["investigations"] = [investigation_dict(i) for i in radar["investigations"]]
```
- `obs_rows`: linhas de `GET /api/admin/observations` (até 6 semanas, escopo BR + UF das categorias ativas). Se a leitura falhar, usar `[]` (o Sentinela fica sem baseline e não afirma anomalia; **não** pular o ciclo).
- `active_investigations`: `GET /api/admin/investigations?status=active`.
- Falha do `analyze` nunca derruba o ciclo: capturar, registrar aviso e seguir sem o campo.

## 3. Migration `0007_investigations.sql` (pending/, como a 0006)
```sql
CREATE TABLE IF NOT EXISTS investigations (
  id               TEXT PRIMARY KEY,   -- inv-<sha1(scope|category|hora de abertura)[:10]>
  scope            TEXT NOT NULL,      -- BR | UF:MG
  category         TEXT NOT NULL,
  status           TEXT NOT NULL CHECK (status IN ('NEW','INVESTIGATING','CORRELATING','WAITING_CONFIRMATION','CONFIRMED','DISPUTED','RESOLVING','CLOSED')),
  started_at       TEXT NOT NULL,
  last_update      TEXT NOT NULL,
  initial_anomaly  REAL NOT NULL,
  anomaly          REAL NOT NULL,
  evidence_count   INTEGER NOT NULL,
  official_confirmation INTEGER NOT NULL DEFAULT 0,
  reasons          TEXT NOT NULL DEFAULT '[]'   -- JSON: por que o Sentinela investigou
);
CREATE INDEX IF NOT EXISTS idx_investigations_status ON investigations (status, last_update);
```
Escrita condicional: só o que `advance` devolveu (mudou). Governador: modo `economy` mantém só abertura/encerramento; `critical` não grava. Retenção: 30 dias após `CLOSED`.

## 4. Payload (aditivo, opcional)
```json
"investigations": [{"id":"inv-ab12cd34ef","scope":"UF:MG","category":"WEATHER","status":"NEW",
  "started_at":"...Z","last_update":"...Z","initial_anomaly":0.73,"anomaly":0.73,"evidence_count":12,
  "official_confirmation":true,"reasons":["anomalia 0.73 (z 2.9, base dow_hour)","sinal oficial"]}]
```
Máximo sugerido por lote: 200. Sem mudança no contrato público (rota interna `/api/admin/*`).

## 5. Rotas internas
`GET /api/admin/investigations?status=active|all&limit=` (mais novas primeiro, zod, limite). Mostra no `/api/admin/overview` o número de investigações ativas.

## 6. Pendências conhecidas (próximos passos)
`CORRELATING`, `WAITING_CONFIRMATION`, `CONFIRMED` e `DISPUTED` são definidos pela validação (passo 7); até lá `advance` só usa NEW, INVESTIGATING, RESOLVING e CLOSED. Termos emergentes (`emerging`) entram quando existir o detector (Fase 2).
