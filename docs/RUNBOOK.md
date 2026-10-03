# Runbook de operação do PULSO

Como saber se o sistema está bem, o que fazer quando não está e como verificar uma mudança. Escrito para quem opera o backend (não exige conhecer o código).

## 1. O sistema está bem? (30 segundos)
```
py -m pulso_engine.healthcheck            # lê https://pulso-api.henriquesouza.workers.dev/api/health
```
Imprime "saudável" ou os PROBLEMAS e sai com código 1. O GitHub roda isso a cada 30 min (`.github/workflows/healthcheck.yml`): se o workflow falhar, o dono do repositório é avisado. Regras: API e banco ONLINE; último pulso há menos de 30 min; menos da metade das fontes OFFLINE; ao menos 40% ONLINE entre as que já reportaram; nenhum `AUTH_ERROR`.

Outras leituras públicas: `GET /api/stats` (eventos ativos, sinais em 2 h e 24 h, fontes online), `GET /api/health` (cada fonte e o atraso da coleta), `GET /api/forecasts/track-record` (acerto das previsões).

## 2. Sintomas e o que fazer
| Sintoma | Causa provável | O que fazer |
|---|---|---|
| "coleta parada há N min" | Cron da Cloudflare não disparou, workflow `Coleta` falhou ou o token do GitHub venceu | Abrir a aba Actions > `Coleta`; ver o último erro. Rodar `Run workflow` manualmente. `GH_DISPATCH_TOKEN` vence em 31/12/2026. |
| `Coleta` falha com `PushError ... HTTP 400 invalid_batch` | O Worker recusou o lote (limite do esquema, ex.: fontes por lote) | A própria mensagem do erro traz o motivo (`detail`). O Worker e o Engine precisam estar na mesma versão (o deploy roda a cada merge na `main`). |
| `Coleta` falha uma vez com HTTP 5xx / timeout e some na rodada seguinte | O Worker estava trocando de versão (deploy) ou sobrecarregado | Normal. O Engine já repete até 2 vezes (espera de 2 s e 5 s) e a ingestão é idempotente, então a rodada seguinte se corrige sozinha. Só investigue se persistir por mais de 3 rodadas. |
| `Coleta` imprime "ciclo pulado" (Worker indisponível) | O Worker não respondeu ao ler o estado gravado (rede, 5xx) | Intencional: o Engine não trata "fora do ar" como "banco vazio" (reenviaria tudo). A rodada seguinte recolhe os mesmos itens. Investigue se persistir (o healthcheck avisa). `Coleta` com exit 1 e "Worker recusou o token": token errado/vencido. |
| Fonte OFFLINE | Site fora do ar, bloqueio, feed mudou de endereço | `py -m pulso_engine.audit --source <id>`; se o feed morreu, desligue em `config/sources.json` (`enabled: false`). Não contorne bloqueio. |
| Fonte `RATE_LIMITED` / `AUTH_ERROR` | Cota estourada / credencial inválida | Não insistir. Conferir cota ou rotacionar o secret (`docs/COLLECTION_PROTOCOL.md` §5 e §11). |
| Uma fonte "não roda" em alguma rodada | Normal: cada fonte tem horário próprio dentro do seu `interval_s` (deslocamento estável pelo id, em `pipeline.is_due`), então a carga fica espalhada | Nada a fazer. Para conferir quando uma fonte roda: `py -m pulso_engine.audit --source <id>` roda na hora; o horário vem de `is_due`. |
| Fontes novas aparecem `UNKNOWN` | Normal por até 30 min: a saúde das fontes ONLINE só é gravada a cada 30 min (minutos 0 a 4 e 30 a 34) | Esperar o próximo horário de revisão. |
| Muitos eventos ou poucos eventos de repente | Mudança de fonte ou do vocabulário | `py -m pulso_engine.audit` mostra sinais, eventos e categorias por fonte. |
| D1: "exceeded" / erros de escrita | Limite diário do plano gratuito | Ver `docs/decisions/0006` ("Orçamento do D1"): checar o tamanho do lote; espaçar o ciclo ou migrar para o plano pago. |

## 3. Verificar uma mudança antes de abrir o PR
1. `cd engine && py -m pytest` e, na raiz, `npm run typecheck && npm test && npm run build`.
2. Rodada real, sem enviar nada: `py -m pulso_engine.pipeline` (leva ~45 s com ~100 fontes). Conferir a contagem de sinais e eventos e o topo por Pulso.
3. Se mexeu em ingestão, Worker local: `npm run db:migrate -w @pulso/worker`, `npx wrangler dev --port 8787` (em outro terminal), e `PULSO_API_URL=http://127.0.0.1:8787 PULSO_INGEST_TOKEN=<o de apps/worker/.dev.vars> py -m pulso_engine.pipeline --push` **duas ou três vezes seguidas**: da segunda em diante o lote deve ser pequeno (poucos sinais e eventos). Se voltar a mandar centenas de linhas iguais, o orçamento do D1 estourará em produção.
4. Chamar as rotas: `/api/health`, `/api/stats`, `/api/events`, `/api/forecasts`, `/api/pulse/states`.
5. Mudou contrato? Atualizar `packages/shared/src/contracts.ts`, `engine/pulso_engine/models.py` e `docs/api/API.md` no mesmo PR, com a label `contract`.

## 4. O que NÃO fazer
- Contornar login, captcha, paywall, limite de taxa ou bloqueio de qualquer fonte.
- Reenviar todos os eventos e séries a cada ciclo (limite de escrita do D1).
- Tratar alegação política como fato; publicar previsão sem probabilidade, incerteza e método.
- Commitar `.env`, `.dev.vars`, tokens ou cookies.
