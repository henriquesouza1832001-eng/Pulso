# 0008 — Orçamento de escrita do D1: como operar a custo zero

Status: aceito (2026-10-03). Contexto: incidente de 2026-10-03.

## Problema
O plano gratuito do D1 aceita **100 mil linhas escritas por dia** (zera às 00:00 UTC, 21:00 em Brasília). Em 2026-10-03 passamos disso (113.655 em 24 h, confirmado com `wrangler d1 info`), e a partir das 08:40Z toda escrita passou a falhar com HTTP 500: 12 coletas seguidas falharam e o pulso ficou parado. Quando o limite é atingido o D1 recusa as consultas inteiras; não há degradação gradual.

## O que consumia (24 h, `wrangler d1 insights ... --sort-by writes`)
| Tabela | Linhas/dia | Observação |
|---|---|---|
| events | ~58 mil | cada atualização grava a linha + 5 índices; ~84 eventos reenviados por ciclo |
| signals | ~13 mil | ~2,6 mil sinais x (linha + índices) |
| series | ~9 mil | janelas de 5 min |
| event_sources | ~6 mil | recalculado a cada ciclo |
| pulse_history | ~5 mil | 24 escopos por ciclo |
| sources | ~3,7 mil | upsert idêntico a cada ciclo |
| source_health | ~1 mil | |

## Opções avaliadas (todas gratuitas, e o que custam em complexidade)
| Opção | Cota grátis (conferir no site oficial) | Veredito |
|---|---|---|
| **Gastar menos no próprio D1** | 100 mil/dia | **Adotado, primeiro** (abaixo). Zero conta nova, zero risco de dados. |
| **Governador de orçamento** (shed por prioridade) | n/a | **Adotado.** Garante que a cota nunca estoura: o crítico sempre passa. |
| **Turso** (SQLite hospedado) | 10 milhões de linhas escritas/mês (~333 mil/dia), 500 mi lidas, 5 GB, sem cartão | **Reserva.** Compatível com SQL do D1; mas não há JOIN entre bancos: `signals`/`series`/`event_sources` iriam para lá e o detalhe do evento faria 2 consultas. Só se, depois das medidas acima, o uso real ainda encostar no limite. |
| **Workers KV** | 1.000 escritas/dia, 100 mil leituras/dia, 1 GB | Serve para um *snapshot* do estado atual (1 chave por ciclo = 288 escritas/dia), nunca para linhas. Mudança grande no Worker (as rotas de leitura passariam a ler do KV). Guardado como plano C. |
| **Cloudflare R2** | 10 GB, 1 milhão de operações de escrita/mês | Exige cartão de crédito cadastrado mesmo no plano grátis; fora do "sem gastar nada". |
| **Vários bancos D1** | cota é da CONTA, não do banco | Não resolve (a documentação fala em "your account"). |
| **Supabase / Neon (Postgres)** | sem limite de linhas escritas, mas 500 MB e pausa por inatividade (Supabase) | Troca de dialeto SQL (SQLite -> Postgres) e de driver; trabalho grande, sem ganho sobre o Turso para este caso. |
| **Workers Paid (US$ 5/mês)** | 50 milhões de linhas/mês incluídas | Fora de "sem gastar", mas é o seguro mais simples; a decisão é do dono. |

## Decisão (custo zero, em ordem)
1. **Escrever só o que mudou.** `ON CONFLICT DO UPDATE ... WHERE <algo mudou>` em `sources`, `signals` e `event_sources`: linha idêntica não custa escrita (o D1 só conta linhas realmente alteradas).
2. **Remover índices sem uso** (`idx_events_state`, `idx_events_status`; nenhuma consulta do Worker os usa): cada atualização de evento deixa de gravar 2 linhas a mais. Mantivemos `idx_signals_source`, que as contagens por fonte do painel admin usam.
3. **Eventos só reenviados quando relevante** (Engine): Pulso muda >= 8 pontos ou contagem sobe >= 2 e >= 25%.
4. **Governador** (`apps/worker/src/lib/budget.ts`, tabela `write_budget`): o Worker soma `meta.rows_written` de cada ingestão e, conforme o dia, descarta antes de gravar:
   - `normal` (< 60 mil): tudo.
   - `economy` (>= 60 mil): só eventos nível >= 2 (e os sinais deles), série só nacional, saúde só de fontes com problema, sem catálogo.
   - `critical` (>= 85 mil): só nível >= 3, pulso nacional, previsões já resolvidas, nenhuma série.
   O que é crítico nunca se perde, e a resposta do ingest traz `budget: {mode, used_before, written, shed}` para o Engine registrar no log.
5. Reserva de 5 mil linhas para operações fora do ingest (migrations, ajustes).

## Resultado medido (banco local, mesmo Engine)
Primeiro envio: 4.505 linhas (carga inicial). Segundo envio, logo depois: **143 linhas** em regime estável. Projeção em ritmo constante: ~41 mil/dia, menos da metade do limite. Dia de eleição tem mais notícia; o governador existe para esse caso.

## Riscos e limites conhecidos
- O governador reduz detalhe em dia de pico (eventos de nível 1 e séries por UF deixam de ser gravados). É preferível a perder tudo com erro 500.
- A contagem depende de `meta.rows_written` do D1; se a tabela `write_budget` falhar, o ingest segue em modo normal (nunca derruba a coleta).
- O dia do orçamento é UTC, igual ao reset da cota.
- Se mesmo assim o uso real encostar no limite: ligar Turso para `signals`/`series` (nova ADR) ou, no seu critério, Workers Paid.

## Addendum (2026-10-03, 14:20Z): migração para o Turso
O D1 estourou antes de o governador entrar em produção. A saída imediata foi mover o Worker inteiro para o Turso, validada assim:
1. Protocolo Hrana testado no servidor real (GitHub Actions, sem expor segredos): `SELECT`, escrita, upsert, `json_each`, parâmetros `?1` e `batch` com rollback.
2. Camada `TursoDatabase` com a mesma API do D1 + middleware por `DB_BACKEND`; 9 testes novos (mock Hrana com SQLite real).
3. Cópia D1 → Turso (dump do D1 por `wrangler d1 export`, `INSERT OR REPLACE` em lotes) e conferência por tabela.
4. Verificação dos segredos do Worker em produção (`turso-ping`), depois a virada por PR.
Resultado: coleta de volta às 14:15Z, rotas de leitura em ~130 ms.
Aprendizados: (a) `meta.rows_written` do Turso conta só linhas da tabela (não as de índice), então o governador fica mais folgado no Turso; (b) a latência por consulta é maior que a do D1, mas as rotas públicas têm cache; (c) separar os bancos continua possível: basta escolher, por tabela, qual `TursoDatabase`/D1 usar.
