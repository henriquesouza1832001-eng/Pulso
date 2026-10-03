# Hospedagem na Cloudflare

Conta: a do e-mail henriquesouza1832001@gmail.com (login via `wrangler login`).

| Recurso | Nome | URL / ID |
|---|---|---|
| Worker (API) | `pulso-api` | https://pulso-api.henriquesouza.workers.dev |
| Worker com assets (front React) | `pulso-web` | https://pulso-web.henriquesouza.workers.dev |
| D1 | `pulso` | `c0added6-9187-434a-a1d0-559857107e1b` (identificador, não é segredo) |
| Secret | `INGEST_TOKEN` (no Worker `pulso-api`) | só na Cloudflare; **nunca** no Git |

`preview_urls` está desativado nos dois Workers, para não existirem URLs paralelas sem controle.

## Deploy
```
# API
cd apps/worker && npx wrangler deploy
# Front (compila e publica)
cd apps/web && npm run deploy
# Migrations novas, sempre versionadas em database/migrations
cd apps/worker && npx wrangler d1 migrations apply pulso --remote
```
Nunca aplicar `database/seeds/dev.sql` em produção (dados fictícios).

## Secret de ingestão
O Python Engine envia lotes com `Authorization: Bearer <INGEST_TOKEN>`. Para gerar um novo e atualizar:
```
node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"
npx wrangler secret put INGEST_TOKEN      # em apps/worker; cole o valor
```
No ambiente do Engine, exporte `PULSO_API_URL` e `PULSO_INGEST_TOKEN`. Guarde o valor num gerenciador de senhas. O token em uso foi guardado fora do repositório, na máquina de quem fez o deploy.

## CORS
`ALLOWED_ORIGINS` (em `apps/worker/wrangler.jsonc`) lista as origens do front. Ao trocar o domínio do front, atualize e faça novo deploy da API.

## Pendências de hospedagem
- Domínio próprio (`pulso...`) e ambiente de STAGING separado (outro D1 e Workers `-staging`).
- Deploy automático pelo GitHub Actions a partir da `main` (precisa de `CLOUDFLARE_API_TOKEN` e `CLOUDFLARE_ACCOUNT_ID` nos Secrets do GitHub).
- Regras de WAF e rate limiting no painel da Cloudflare.
- KV para cache de `/api/pulse/br` e `/api/map` quando o tráfego justificar.
- O Python Engine ainda não roda hospedado: precisa de ambiente próprio (container/VM/cron), pois não é um Worker.

## Deploy automático (GitHub Actions)
`.github/workflows/deploy.yml` roda a cada merge na `main`: valida (typecheck, testes Node e Python) → aplica migrations do D1 → publica o Worker → compila e publica o front → confere `/api/health`.

Secrets do repositório necessários:
| Secret | Origem |
|---|---|
| `CLOUDFLARE_ACCOUNT_ID` | já configurado |
| `CLOUDFLARE_API_TOKEN` | criado no painel (modelo "Editar Cloudflare Workers" + D1 Editar), restrito à conta; `gh secret set CLOUDFLARE_API_TOKEN` |
| `PULSO_API_URL`, `PULSO_INGEST_TOKEN` | usados pela coleta agendada (`collect.yml`) |

Rotação: gerar novo token no painel, atualizar o secret e revogar o antigo. Migration que falha interrompe o deploy antes de publicar código novo.

## Agendamento da coleta (Cron Trigger da Cloudflare)
O agendador do GitHub (`schedule`) atrasa de forma imprevisível, então o disparo vem da Cloudflare: o Worker `pulso-api` tem `triggers.crons = ["*/5 * * * *"]` e, a cada 5 min, chama a API do GitHub (`workflow_dispatch` de `collect.yml`). O GitHub só executa o Python Engine. O `schedule` do `collect.yml` fica como reserva.

Necessário (uma vez): um token **fino** do GitHub, só para o repositório Pulso, com permissão **Actions: leitura e escrita**, guardado no Worker:
```
cd apps/worker && npx wrangler secret put GH_DISPATCH_TOKEN
```
Saúde: `GET /api/health` mostra `collection.age_seconds`, `stale` (sem Pulso novo há mais de 15 min) e `scheduler_configured`. Falha de disparo aparece nos logs do Worker (`falha ao acionar coleta`).

## Prévia por branch (antes do merge)
Cada push em `art`, `hen`, `thig` ou `isar` que mexa em `apps/web/**` ou `packages/shared/**` roda `.github/workflows/preview.yml` e publica o front da branch em `https://pulso-web-<branch>.henriquesouza.workers.dev`.
- Worker próprio (`apps/web/preview/worker.js`, `apps/web/wrangler.preview.jsonc`): serve o build e repassa **só** `GET /api/*` público para a API de produção, do lado do servidor (a API não precisa liberar CORS para a prévia). `POST` e `/api/admin/*` respondem 403.
- O front mostra a faixa "PRÉVIA DA BRANCH …" (`VITE_PREVIEW_BRANCH`).
- Usa os mesmos segredos do deploy (`CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`). Para remover uma prévia: `npx wrangler delete --name pulso-web-<branch>`.
