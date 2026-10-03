# Deploy do PULSO

Runbook para colocar o Worker (API + D1) e o web (SPA) no ar na Cloudflare.
Merge para `main` continua sendo decisão humana via PR — este documento cobre
após o merge (ou a partir da branch que você decidir publicar).

## 0. Pré-requisitos (uma vez por máquina)

```bash
npx wrangler login          # abre o navegador e autentica na conta Cloudflare
```

## 1. Banco D1 de produção (uma vez por conta)

```bash
npx wrangler d1 create pulso
```

Copie o `database_id` retornado para `apps/worker/wrangler.jsonc`
(substituindo o placeholder `00000000-…`).

Depois aplique as migrations e o seed no remoto:

```bash
npm run db:migrate -w @pulso/worker -- --remote
npx wrangler d1 execute pulso --remote --file database/seeds/dev.sql
```

## 2. Secret do coletor

```bash
cd apps/worker
npx wrangler secret put INGEST_TOKEN   # cole o token gerado (nunca versionar)
```

## 3. Origem permitida no CORS

Em `apps/worker/wrangler.jsonc`, ajuste `ALLOWED_ORIGINS` para a URL final do
web (ex.: `https://pulso.pages.dev`), mantendo `http://localhost:5173` para
desenvolvimento — separe por vírgula.

## 4. Publicar a API (Worker)

```bash
cd apps/worker
npx wrangler deploy
```

Anote a URL retornada, ex.: `https://pulso-api.<sua-conta>.workers.dev`.

## 5. Publicar o web (Cloudflare Pages)

O SPA precisa saber a URL da API em tempo de build (`VITE_API_BASE`):

```bash
VITE_API_BASE=https://pulso-api.<sua-conta>.workers.dev npm run build -w @pulso/web
npx wrangler pages deploy apps/web/dist --project-name pulso
```

Alternativa sem linha de comando: conectar o repositório no dashboard do
Pages (build command `npm run build -w @pulso/web`, output `apps/web/dist`,
variável de ambiente `VITE_API_BASE`).

## 6. Verificação pós-deploy

```bash
curl https://pulso-api.<sua-conta>.workers.dev/api/health   # {"api":"ONLINE",...}
curl https://pulso-api.<sua-conta>.workers.dev/api/pulse/br
```

Abrir o Pages e conferir: indicador nacional carregando score real
(`VITE_DEMO` **não** definido em produção = sem dados fictícios).

## Pull request

CI roda em PRs para `main`/`hen` (typecheck + testes + build + engine Python).
Da branch `thig`, abra o PR `thig → main` pela UI do GitHub; merge é humano.
