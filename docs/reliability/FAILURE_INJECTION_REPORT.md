# Failure Injection Report — 2026-10-03

Autor: `claude-art`. Base: `main` em `e9cbece`. Feito na `art`: o `AGENTS.md` proíbe criar branches. PR aberto **sem merge
automático**.

Nota de sincronização: o roteiro cita "a PR #89 de storage". O #89 é o de relevância editorial (`hen`). O storage foi endurecido
em #85/#86/#88 (estado por fonte, auth/abuso, `write_budget` que nunca subconta), e foi isso que revalidei.

## Resumo

| Área | Status | Evidência |
|---|---|---|
| 1. Storage chaos | **PASS** | matriz existente (rede, 500, ECONNRESET, timeout, lento, perda antes/depois do commit, lote parcial, tabela/coluna ausente, opcional ausente) + novos: **HTTP 429** e **DNS** do banco |
| 2. Idempotência | **PASS** | o mesmo ciclo reenviado **1, 2, 3, 10 e 100 vezes**: nenhuma linha nova e nenhum conteúdo alterado em nenhuma tabela (só o batimento de `source_health`, por desenho) |
| 3. Write budget | **PASS** | 10 ciclos alternando "commit + resposta perdida" e retry: o contador nunca desce e nunca fica abaixo do realmente gravado; dado de produto nunca duplica |
| 4. Freshness | **PASS** / PARTIAL | fresco, velho, repetido, vazio, sem data, offline e recuperação já cobertos; data **futura** nunca vira FRESH (fica UNKNOWN). FI-003 abaixo |
| 5. Runtime / breaker | **PASS** | falha única, rajada, 429 + Retry-After, half-open e recuperação cobertos; em SHADOW o breaker **coleta mesmo aberto** (teste existente) |
| 6. SSRF | **FAIL → corrigido** | FI-001: NAT64 e IPv4-compatível passavam como públicos |
| 7. Health | **PASS** | banco fora (rede, 500, ECONNRESET, **429**, **DNS**): liveness 200, readiness 503; lento = degraded; coleta atrasada = degraded |
| 8. Observability | PARTIAL | último ciclo, duração, fontes previstas/puladas, frescor, cobertura, breakers, esquema, orçamento, investigações: sim. Status explícito de Forecast/Sentinela: não |
| 9. Security regression | **PASS** / FIX | tokens, fail-closed, SQL, limite de 8 MB, Zod já cobertos; **CORS** ganhou testes; FI-002 corrigido |
| Config externa (WAF, rate limit de borda, rotação de segredos) | BLOCKED_EXTERNAL | fora do repositório |

## Defeitos

### FI-001 — SSRF: IPv6 que embute IPv4 interno passava como público (P1, corrigido)

- **Ataque:** destino `64:ff9b::a9fe:a9fe` (NAT64 para 169.254.169.254), `64:ff9b::7f00:1`, `::7f00:1` (IPv4-compatível) e `fec0::1` (site-local).
- **Resultado antes:** `is_public_ip` devolvia `True`. Num runner com DNS64/NAT64 (comum em nuvem IPv6-only), um DNS hostil leva o Engine ao **metadata da nuvem**.
- **Causa raiz:** `ipaddress.is_global` do Python considera `64:ff9b::/96` e `::/96` globais. O guarda só desembrulhava o IPv4 **mapeado** (`::ffff:`).
- **Correção:** `safe_http.is_public_ip` valida o IPv4 embutido em NAT64 e em IPv4-compatível, e recusa site-local. NAT64 para IP **público** continua liberado, sem perda funcional.
- **Prova:**
  - `engine/tests/test_failure_injection.py`: **9 testes falham na versão antiga** e todos passam na nova.
  - Inclui teste no nível do socket: nenhum `connect` chega a IP interno, com userinfo (`user:pass@`), URL codificada (`%31%32%37`), forma decimal/octal/hex (`2130706433`, `0177.0.0.1`, `0x7f.1`) ou resposta DNS mista (público + interno).

### FI-002 — `engine-status` devolvia a mensagem interna do driver (P2, corrigido)

- **Ataque:** banco fora (HTTP 500, DNS, 429) e chamada ao `/api/admin/engine-status`.
- **Resultado antes:** `{"error":"engine_status_failed","detail":"turso_http_500: boom"}`. A mensagem do driver (pode trazer host, tabela, SQL) ia para o chamador, ao contrário do resto do Worker.
- **Correção:** o detalhe vai só para o log com o `request_id`, como no handler global; a resposta leva o código e o `request_id`.
- **Regressão:** `apps/worker/tests/failure-injection.test.ts`.

### FI-003 — frescor com relógio da fonte adiantado (P3, aberto, dono: `claude-hen`)

- **Ataque:** feed com itens datados +10 min (relógio adiantado) e +3 dias.
- **Resultado:** nunca vira FRESH (correto: data futura não prova frescor). Mas:
  - um adiantamento pequeno e comum faz a fonte ficar **UNKNOWN para sempre**, perdendo cobertura;
  - o motivo exibido é "registros sem data de publicação", enganoso, porque a data existe e está no futuro.
- **Causa:** o adaptador limita a data a "agora" (`timestamp == collected_at`), e o frescor trata esse caso como "sem data".
- **Sugestão:** tolerância de alguns minutos para adiantamento e motivo próprio ("data no futuro").

### FI-004 — observações de configuração (P3)

- `ALLOWED_ORIGINS` de produção inclui `http://localhost:5173`. O risco é baixo (sem cookies; ingest exige token), mas é desnecessário em produção.
- `OPERATOR_TOKEN`, citado no roteiro, **não existe**: o Worker tem `INGEST_TOKEN` e `ADMIN_TOKEN`, separados e com teste.
- HTTP 429 do banco vira 500 no ingest. O Engine reenvia no próximo ciclo e a idempotência garante que não duplica. Um 503 com `Retry-After` seria mais preciso, mas não muda a correção.

## O que foi verificado e resistiu

- **Storage:**
  - nada gravado quando a rede cai antes do commit;
  - com a resposta perdida depois do commit, o dado está lá e o reenvio não duplica;
  - lote que falha no meio desfaz tudo;
  - sem tabela ou coluna **opcional**, o produto grava e só o opcional falha;
  - sem tabela de **produto**, 500 sem vazar o nome.
- **Idempotência:** 100 reenvios idênticos não mudam nenhuma linha de `events`, `signals`, `series`, `forecasts`, `forecast_registry`, `shadow_results`, `driver_registry`, `calibrators`, `investigations`, `signal_observations`, `source_runtime`, `engine_cycle` e `pulse_history`.
- **CORS:**
  - só as origens configuradas recebem `Access-Control-Allow-Origin`, com a origem exata e nunca `*`;
  - origem estranha, `null`, domínio-sufixo (`...workers.dev.evil.example`) e caixa diferente não recebem;
  - sem configuração, ninguém recebe (fail-closed);
  - conferido também na API publicada.

## Execução final

| Suíte | Resultado |
|---|---|
| Worker (vitest, todos) | 14 arquivos, **165 testes** passando (eram 145; +20 em `failure-injection.test.ts`) |
| Engine (pytest, todos) | **756 passed, 11 xfailed**, com `NOISE_GATE` desligada e ligada |
| typecheck / build / `wrangler deploy --dry-run` | ok |

Os 11 `xfail` são os defeitos de pontuação do QA anterior (`BACKEND_ADVERSARIAL_QA.md`), sem relação com esta rodada.

## Handoff

- `claude-hen`: FI-003; revisar FI-001 (`safe_http.py`) e FI-002 (`admin.ts`), arquivos de plataforma alterados aqui; FI-004 (`ALLOWED_ORIGINS`, 429 → 503).
- Status explícito de Forecast e Sentinela no `engine-status` (observabilidade PARTIAL): seria feature nova, ficou fora do escopo.
