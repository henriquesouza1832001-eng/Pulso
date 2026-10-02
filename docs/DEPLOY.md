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
