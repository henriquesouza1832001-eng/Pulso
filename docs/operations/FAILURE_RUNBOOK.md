# Runbook de falhas

> Leia junto de `docs/RUNBOOK.md` (sintomas gerais) e `docs/engineering/STORAGE_AUTHORITY.md`. Cada seção: **sintoma → como confirmar → o que fazer → o que NÃO fazer**. Nunca cole segredos em chat, issue ou log.

## Mapa de estados (o que cada coisa significa)
| Sinal | Significa | Onde ver |
|---|---|---|
| `/api/health/live` 200 | o Worker respondeu (não toca o banco) | público |
| `/api/health/ready` 200 / 503 | o sistema consegue SERVIR dados; 503 = banco fora (**LIVE ≠ READY**) | público |
| `engine-status.verdict`: ok / degraded / not_ready | veredito agregado do operador | `/api/admin/engine-status` |
| `collection.stale` | sem Pulso novo há > 15 min | `/api/health` |
| fonte `FRESH / STALE / EMPTY / QUIET / UNKNOWN` | frescor do CONTEÚDO, separado do transporte (HTTP 200 ≠ dado novo) | log do ciclo `frescor:`; `source_freshness` |
| transporte `ONLINE / DEGRADED / RATE_LIMITED / OFFLINE / AUTH_ERROR` | só a conexão e a leitura | `source_health` |

## 1. Banco fora (Turso ou D1)
- **Sintoma:** `/ready` 503, `engine-status` not_ready, ciclos do Engine pulam ("Worker indisponível") ou ingest 5xx.
- **Confirmar:** `/api/admin/turso-ping` (operador); painel do provedor.
- **Fazer:** esperar; o ingest é **idempotente** (reenvio seguro) e o Engine pula o ciclo sem reenviar tudo. Se o D1 estourou a cota: reverter `DB_BACKEND` só se o outro banco estiver íntegro (ADR 0008; `STORAGE_AUTHORITY.md`).
- **Não fazer:** apagar dados, editar migration aplicada, rodar `seeds/dev.sql` em produção.

## 2. Coletor ou fonte fora (uma fonte)
- **Sintoma:** fonte `OFFLINE`/`RATE_LIMITED`/`AUTH_ERROR`; freshness `UNKNOWN`.
- **Confirmar:** `py -m pulso_engine.audit` (roda cada fonte) e o detalhe em `source_health`.
- **Fazer:** uma fonte caída não derruba o ciclo (testado: `tests/chaos`). 403/429 a partir do GitHub Actions = bloqueio de IP de nuvem ou limite: **desligar a fonte** (`enabled: false`), nunca contornar, nunca insistir. 429 com `Retry-After`: respeitar (o circuit breaker abre pelo menos esse tempo).
- **Não fazer:** CAPTCHA, proxy, rotação de IP/UA, burlar paywall/robots.

## 3. Tempestade de fontes (muitas fontes falham juntas)
- **Sintoma:** `healthcheck` falha (maioria OFFLINE) ou `ready_ratio` despenca.
- **Causa provável:** rede do runner, DNS, ou um provedor comum (CDN).
- **Fazer:** confirmar no log do ciclo (`frescor: ... UNKNOWN=N`); se for o runner, a próxima rodada se recupera. O sistema **não** trata UNKNOWN como "calmaria": a cobertura fica degradada e as previsões abstêm-se (`INSUFFICIENT_DATA`).
- **Não fazer:** baixar limiares para "sumir" o alarme.

## 4. Sensores parados (STALE) — HTTP 200 sem dado novo
- **Sintoma:** transporte ONLINE e frescor STALE/EMPTY; `new_records=0`.
- **Fazer:** ver `last_content_advance`; se o site mudou de feed/URL, corrigir `sources.json`; se é feed morto (ex.: G1 estados parados desde 2018), `enabled: false` e registrar em `docs/sources/`.
- **Regra:** **parado ≠ zero**: nunca contar como "sem ocorrências".

## 5. Worker com problema / deploy ruim
- **Sintoma:** 5xx em rotas, `request_id` nos erros, healthcheck vermelho logo após um merge.
- **Fazer:** conferir o CI do commit; reverter pelo GitHub (revert do PR, não force push) e deixar o deploy automático republicar. Migrations são aditivas: reverter código não exige reverter tabela.
- **Compatibilidade:** campos novos do lote são opcionais; um Worker antigo ignora campo novo do Engine; um Engine antigo funciona com Worker novo.

## 6. Falha de migration
- **Sintoma:** workflow `Turso schema` vermelho ou coluna/tabela ausente em produção.
- **Fazer:** NÃO editar a migration aplicada: criar a próxima numerada, `IF NOT EXISTS`, aditiva. Verificar em ambiente local antes (`npm run db:migrate`).
- **Se travou no meio:** os statements são `IF NOT EXISTS`, então reaplicar é seguro.

## 7. Incidente de autenticação
- **Sintoma:** acessos indevidos a `/api/admin/*`, ingest com lote estranho, token exposto.
- **Fazer:** **rotacionar** o segredo (`wrangler secret put INGEST_TOKEN` / `ADMIN_TOKEN`, e o secret correspondente do GitHub Actions), revogar o antigo no painel; conferir `request_id`s no log do Worker. Rate limit/WAF é configuração da Cloudflare (**não comprovada aqui**: ver `PLATFORM_MATURITY.md`).
- **Já exposto uma vez:** o token da Cloudflare colado em chat deve estar revogado (pendência do dono).

## 8. Estouro de cota de escrita
- **Sintoma:** ingest 500 / `engine-status.budget.mode` = economy|critical.
- **Fazer:** o governador já reduz escrita; conferir `rows_today`. Em `critical` só eventos críticos passam. Esperar a renovação diária ou aumentar o plano (decisão do dono).
- **Limitação conhecida (A1b):** o `write_budget` pode subestimar se uma resposta se perde.

## 9. Conformidade (fonte com termos que proíbem a coleta)
- **Fazer:** `enabled: false`, registrar o motivo em `compliance_notes` e rodar `py -m pulso_engine.compliance --write`. Nada de APPROVED sem decisão humana.
