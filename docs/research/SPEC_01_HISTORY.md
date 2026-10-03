# SPEC 01 — History: observações agregadas por hora

> Especificação para quem implementa a parte compartilhada (migration, ingest, chamada no pipeline). Passo 1 da ordem em `docs/CURRENT_ENGINE_STATE.md` §7. **Nada aqui foi implementado.**
> Premissas (recomendações aguardando confirmação do dono): histórico só em contagens agregadas, sem conteúdo de terceiros; tabelas compatíveis com Turso e D1; sem NLP novo.

## 1. Objetivo
Dar memória ao motor: contagens por **hora × escopo × categoria × classe de fonte**, base do baseline sazonal (hora × dia da semana), das tendências e do dataset de lead time. Hoje só existe `series` (5 min, por escopo × categoria, sem classe de fonte).

## 2. Tabela proposta (migration `0006_history.sql`, número a confirmar após `git pull`)
```sql
CREATE TABLE IF NOT EXISTS signal_observations (
  scope        TEXT NOT NULL,     -- BR | UF:MG
  category     TEXT NOT NULL,
  source_class TEXT NOT NULL,     -- OFFICIAL | NEWS_HIGH | NEWS_REGIONAL | SOCIAL | ...
  hour         TEXT NOT NULL,     -- início da hora, ISO-8601 UTC (HH:00:00Z)
  signals      INTEGER NOT NULL,  -- sinais distintos (já deduplicados por hash)
  sources      INTEGER NOT NULL,  -- fontes distintas
  duplicates   INTEGER NOT NULL DEFAULT 0, -- cópias descartadas na dedup (base do duplicate_ratio)
  PRIMARY KEY (scope, category, source_class, hour)
) WITHOUT ROWID;
```
Sem índice secundário (cada índice dobra o custo de escrita). Leitura sempre por `scope, category` + faixa de `hour`, coberta pela chave primária.

## 3. Regra de escrita (orçamento do banco)
- Grava **apenas horas fechadas** (hora anterior à atual), **uma vez**. A hora corrente continua vindo de `series`/memória.
- Upsert condicional: só reescreve se `signals`/`sources`/`duplicates` mudarem (chegada tardia de feed lento pode corrigir a hora anterior, no máximo nas 2 horas seguintes).
- Linhas só existem para células com sinal (esparso). Estimativa conservadora: 28 escopos × ≤12 categorias × ≤4 classes é o teto teórico (~1.300 linhas/hora); a prática esparsa é uma fração disso. **Medir com a coleta real antes de ligar** e registrar o número no ADR.
- Passa pelo governador de orçamento: em modo `economy` grava só `scope = BR`; em `critical` não grava (nunca perde evento).
- Retenção: 90 dias (job de limpeza junto da retenção de sinais).

## 4. Payload (campo opcional do IngestBatch, aditivo)
```json
"observations": [
  {"scope":"UF:MG","category":"WEATHER","source_class":"OFFICIAL","hour":"2026-10-03T14:00:00Z","signals":3,"sources":2,"duplicates":1}
]
```
Zod no Worker: `.optional()`, máximo por lote definido (sugestão 2.000). Worker antigo ignora o campo.

## 5. Onde o código novo entra
- Função pura nova, testável sem rede: `build_observations(signals, duplicates_by_hash, now) -> list[dict]` (arquivo novo, ex.: `engine/pulso_engine/research/history.py`; **a ser chamado** em `pipeline.run_once` logo após `build_series`, por quem é dono do pipeline).
- `duplicate_ratio` real: contar descartes em `signals.setdefault(s.hash, s)` do `run_once` (hoje o descarte é silencioso). **Pedido ao dono do pipeline:** devolver essa contagem por hash/fonte.
- Leitura: rota interna `GET /api/admin/observations?scope=&category=&since=` (zod, limite, mais novos primeiro, como `/api/admin/series`).

## 6. Testes exigidos
Hora corrente nunca emitida; reenvio idêntico gera 0 linhas; chegada tardia corrige a hora anterior; escopo `UF:` só quando há `state`; `OTHER` excluída (como em `series`); simulação de 7 dias com contagem de linhas dentro do teto.

## 7. Fora deste passo
Baseline sazonal (passo 2) consome esta tabela; não altera `baseline.py` ainda.
