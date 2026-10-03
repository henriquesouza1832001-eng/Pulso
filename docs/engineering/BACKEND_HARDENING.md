# Hardening do backend (Claude B / plataforma)

Documento vivo da campanha de hardening. Entrada: `docs/reliability/BACKEND_TOTAL_RED_TEAM.md` (Codex). Regra: corrigir a CLASSE de erro, com regressão, sem ligar V2 e sem mexer em golden/validação. O que ainda falta fica em [FALTA_FAZER.md](FALTA_FAZER.md).

## 1. Estado inicial
Rodada iniciada em `hen` com `origin/main` = `217ee42` (PR #74). Worker com auth Bearer fail-closed, Zod e SQL parametrizado; erro sem padrão único; `/api/health` devolvia HTTP 200 mesmo com coleta parada; sem limite de corpo no ingest; `engine-status` só com números crus.

## 2. Findings recebidos
RT-002 (200 mascara conteúdo estagnado), RT-005 (storage sem ensaio de falha), RT-007 (admin/abuso), mais os de engine (RT-003, RT-008) que são do Claude A.

## 3. Reproduzidos
- RT-002 (parte plataforma): reproduzido localmente. Com a base local sem Pulso novo há 251 min, `/api/health` seguia "ONLINE" sem veredito de prontidão.
- RT-007: confirmado por leitura (sem limite de corpo; sem id de requisição; admin usa o token do ingest).
- RT-005: reproduzido por falha induzida (`storage-chaos.test.ts`). Achado: reenvio idêntico regravava `events`, `series`, `forecasts` e `pulse_history` (idempotência fraca + custo de orçamento).

## 4. Causas-raiz
Saúde era medida só por transporte (o banco responde), nunca por prontidão/frescor; erros eram montados rota a rota, sem envelope; nenhum teto de entrada na borda.

## 5. Correções (rodada 1)
| Mudança | Arquivo |
|---|---|
| Envelope de erro uniforme: todo 4xx/5xx JSON ganha `request_id` = cabeçalho `X-Request-Id`; o campo `error` do front não muda; falha interna nunca vaza stack | `apps/worker/src/lib/http.ts` |
| Limite de corpo do ingest: 8 MB, `413` antes de ler | `apps/worker/src/index.ts` |
| Liveness (`/api/health/live`, sem banco) separado de readiness (`/api/health/ready`: `ready` / `degraded` / `not_ready` 503) | `apps/worker/src/routes/health.ts` |
| Veredito para o operador no `engine-status` (`verdict.status` + `verdict.reasons`): banco, latência, idade da coleta, orçamento, enxurrada de investigações | `apps/worker/src/lib/status.ts`, `routes/admin.ts` |

| Upserts condicionais em `events`, `series`, `forecasts`, `pulse_history`: reenvio idêntico não grava (só o batimento de `source_health`, intencional) | `apps/worker/src/routes/ingest.ts` |
| Handler de erro único (`errorHandler`) reutilizado pelo Worker e pelos testes | `apps/worker/src/lib/http.ts` |

| Token de operador separado (`ADMIN_TOKEN`, opcional): rotas de operador só o aceitam quando existe; rotas que o Engine lê aceitam os dois; sem o segredo, comportamento atual (compatível) e `engine-status.admin_token_separate = false` | `apps/worker/src/lib/auth.ts`, `routes/admin.ts` |

## 6. Testes adicionados
`apps/worker/tests/hardening.test.ts` (12): envelope (request_id igual ao cabeçalho, sucesso intocado, id hostil descartado, corpo não-objeto intacto, sem vazamento de stack), limite de corpo (200 dentro, 413 fora), veredito (ok, banco fora = not_ready, coleta atrasada ou inexistente = degraded e não ok, economia/crítico, degradação não rebaixa not_ready, enxurrada). `apps/worker/tests/auth.test.ts` (+6): matriz de menor privilégio por rota e pelo app real (ingest-token = 401 em `/engine-status`, mas passa em `/observations`). `apps/worker/tests/storage-chaos.test.ts` (6, mais helper `tests/helpers/hrana.ts` com injeção de falha): lote limpo; rede cai antes; HTTP 500; resposta perdida depois do commit; limitação do orçamento (visível); falha no meio do lote. Verificação no Worker local: live 200, ready 200 `degraded` com o motivo, 401 e 400 com `request_id`, 9 MB = 413.

## 7. Garantias temporais
Inalteradas nesta rodada (núcleo é do Claude A/Codex). A idade da coleta usa o Pulso nacional mais recente, nunca o relógio da coleta.

## 8. Proveniência · 9. Geo
Sem mudança nesta rodada (engine).

## 10. Storage
Upserts condicionais (ver §5) e ensaio de falha (ver `STORAGE_AUTHORITY.md`). Autoridade: **PARCIALMENTE verificada** — a lógica do Worker e do adaptador foi ensaiada sob falha; o servidor Turso remoto e o binding D1 real não.

## 11. API
Envelope + `request_id`, teto de 8 MB, `live`/`ready`. Sem mudança de campo existente (aditivo).

## 12. Observabilidade
`verdict` no `engine-status`; readiness separada de liveness. Ainda não há p50/p95 de frescor por fonte nem cobertura por sensor.

## 13. Riscos restantes
Ver FALTA_FAZER.md.

## 14. Handoffs ao Codex
Retestar: `/api/health/ready` com banco indisponível (503), 413 no ingest, `request_id` em todo erro, ausência de stack em 500.
