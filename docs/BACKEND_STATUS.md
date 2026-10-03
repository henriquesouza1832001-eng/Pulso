# PULSO — Estado do backend (documento vivo)

> **Última atualização:** 2026-10-03 · **Responsável pelo backend:** @henriquesouza1832001-eng (branch `hen`)
> Este arquivo é o ponto de entrada de quem entra no backend. **Quem muda algo relevante atualiza este arquivo no mesmo PR** (seções 2, 6, 7 e o registro da seção 10).

## 1. O que é o PULSO (em 30 segundos)
Plataforma brasileira de inteligência situacional em tempo real, a partir de **sinais públicos** (notícias hoje; fontes oficiais e sociais depois). Agrupa sinais em **eventos**, calcula **severidade**, **confiança** e **Pulso Score** (sempre explicável), e a meta é **antecipar** acontecimentos como previsões probabilísticas calibradas, no espírito do "Pizza Index".

Três peças desacopladas:
| Peça | Pasta | Tecnologia | Quem |
|---|---|---|---|
| Engine (inteligência) | `engine/` | Python | backend |
| Worker (API/gateway/cron) | `apps/worker` | Cloudflare Worker + Hono + D1 | backend |
| Web | `apps/web` | React + Vite | outra pessoa (front) |
| Contratos | `packages/shared` + `engine/pulso_engine/models.py` | TypeScript / Python | **combinar antes de mudar** |

Fluxo: `fontes → Engine (coleta, dedup, geo, clusterização, scoring) → POST /api/ingest → Worker → D1 → API pública → Web`.

Leitura obrigatória, nesta ordem: `AGENTS.md` → `docs/architecture/ARCHITECTURE.md` → `docs/architecture/PREDICTION.md` → `docs/COLLECTION_PROTOCOL.md` → `docs/SCORING.md` → `docs/api/API.md`.

## 2. Ambientes e recursos (produção)
| Item | Valor |
|---|---|
| API | https://pulso-api.henriquesouza.workers.dev |
| Web | https://pulso-web.henriquesouza.workers.dev |
| Conta Cloudflare | a do e-mail henriquesouza1832001@gmail.com (ID da conta: `e6bad927b7fcf101fd2d4af6bcf60afa`) |
| Banco D1 | `pulso` (`c0added6-9187-434a-a1d0-559857107e1b`), migrations em `database/migrations` |
| Repositório | github.com/henriquesouza1832001-eng/Pulso |
| Deploy | automático pelo GitHub Actions a cada merge na `main` (`.github/workflows/deploy.yml`) |
| Coleta | workflow `collect.yml`, acionado pelo Cron da Cloudflare a cada 5 min (ver seção 7) |

**Segredos (somente os nomes; nunca valores, nunca no Git):**
| Onde | Nome | Para quê |
|---|---|---|
| Worker (`wrangler secret put`) | `INGEST_TOKEN` | autoriza Engine em `/api/ingest` e `/api/admin/*` |
| Worker | `GH_DISPATCH_TOKEN` | **pendente**: token fino do GitHub (Actions: escrita) para o Cron acionar a coleta |
| GitHub Actions | `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID` | deploy automático |
| GitHub Actions | `PULSO_API_URL`, `PULSO_INGEST_TOKEN` | a coleta enviar lotes ao Worker |
| GitHub Actions | `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT`, `X_BEARER_TOKEN` | **ainda não criados**: sensores sociais (só depois da aprovação; ver `docs/sources/SOURCES.md`) |

Quem precisa de acesso novo: convite como colaborador no GitHub e na conta Cloudflare (Membros). Peça os valores dos segredos a quem os criou; **não** os cole em chats, issues nem PRs.

## 3. Rodando localmente (Windows/PowerShell ou Git Bash)
```
npm install
npm run db:migrate && npm run db:seed          # D1 local + dados FICTÍCIOS
copy apps\worker\.dev.vars.example apps\worker\.dev.vars   # edite INGEST_TOKEN (local)
npm run dev:worker                              # API em :8787
npm run dev:web                                 # Web em :5173 (proxy /api → :8787)
cd engine && py -m pip install -e ".[dev]" && py -m pytest      # 50+ testes
py -m pulso_engine.pipeline                     # rodada simulada (não envia)
```
Enviar ao Worker local: `PULSO_API_URL=http://localhost:8787 PULSO_INGEST_TOKEN=<seu .dev.vars> py -m pulso_engine.pipeline --push`.

Armadilhas conhecidas (Windows): use `py` (o `python` do PATH não funciona); se `wrangler dev` ficar mudo, há servidores antigos presos na porta (encerre pelo PID, ou troque `--port`); nunca aplique `database/seeds/dev.sql` em produção.

## 4. Regras de trabalho (resumo; valem `AGENTS.md` e `CONTRIBUTING.md`)
- **Só existem as branches `main`, `hen`, `thig`, `art`, `isar`. Não criar outras.** Cada pessoa trabalha na sua e abre PR para a `main`. Papel exato de `thig`/`art`/`isar`: *a confirmar com o responsável*.
- Nada de push direto na `main`. CI verde (typecheck, testes Node e Python). Merge dispara o deploy.
- Mudou contrato (`contracts.ts` / `models.py` / `docs/api/API.md`)? Avise o front e atualize os três no mesmo PR.
- Fonte nova só passa pelo **protocolo de coleta** (`config.py` recusa fonte sem os campos obrigatórios).
- Previsão sempre como **probabilidade calibrada**, rotulada, rastreável. Alerta 4–5 nunca vem só de previsão.

## 5. Arquitetura do backend em pontos
- **Worker** (`apps/worker/src`): `routes/` (`health`, `pulse`, `events`, `map` públicas; `ingest` e `admin` com token), `lib/` (auth, cache, dispatch), `scheduled` (cron). Validação com zod; ingest **idempotente** e em **uma instrução por tabela** com `json_each` (o plano gratuito do D1 limita ~50 consultas por requisição; lotes grandes com muitos comandos davam 500).
- **Engine** (`engine/pulso_engine`): `collectors/` (interface `SourceAdapter`; RSS pronto), `processing/` (normalização, geolocalização por gazetteer, clusterização, keywords recarregáveis), `scoring/` (confiança, Pulso, nível 1–5), `series.py`, `baseline.py`, `anomaly.py`, `pipeline.py` (`run_once` + CLI), `client.py`, `config.py` (valida `config/sources.json`).
- **Banco**: `sources`, `source_health`, `signals`, `events`, `event_sources`, `pulse_history`, `series`, `keywords`, `entities`, `locations`, `metrics`. Ver `database/migrations`.
- **Cloudflare** em uso: Workers, D1, Cron Trigger. **Ainda não**: KV, Queues, R2, Durable Objects (entram quando houver necessidade medida; registrar ADR).

## 6. Estado atual (marque ao concluir)
**Pronto e testado**
- [x] Monorepo, CI, deploy automático, Cloudflare (D1, Worker, front)
- [x] Coleta RSS de 5 fontes (Agência Brasil, G1, Folha, CNN Brasil, UOL) com dedup, geo (cidade/estado), clusterização, eventos
- [x] Confiança, Pulso Score explicável, níveis 1–5
- [x] API pública: `/api/pulse/*`, `/api/events`, `/api/events/:id`, `/api/map`, `/api/health`
- [x] Rotas internas: `/api/ingest`, `/api/admin/series`, `/api/admin/overview`
- [x] Histórico em séries (5 min), baseline (EWMA) e anomalia (inválida com < 12 h de dados)
- [x] Protocolo de coleta validado em código; `/api/health` mostra o atraso da coleta
- [x] Testes: 36 Python, 4 do Worker

**Em andamento / aguardando**
- [x] **PR #7** mergeado e publicado em 2026-10-03: séries, baseline, anomalia, rotas admin, Cron Trigger (`*/5 * * * *` registrado), migration `0002` aplicada
- [x] Registro de coletores (`collectors/registry.py`): fonte nova = arquivo novo + uma linha, sem mexer no pipeline
- [x] Adaptadores Reddit/X completos para política BR (busca temática, filtro por categoria, geo, `RATE_LIMITED`/`AUTH_ERROR`, cadência por `interval_s`, modo piloto `--source`); `enabled: false`, sem autorização nem credenciais (ADR 0003)
- [x] Piloto automático no `collect.yml`: liga sozinho quando os secrets sociais existirem, sem envio e sem conteúdo no log
- [ ] Reddit/X: registrar app/contratar plano (com teto de gasto), revisar termos, criar secrets (inicia o piloto), avaliar 48 h e só então `enabled: true` (checklist em `docs/sources/SOURCES.md`)
- [ ] Confirmar cadência do Cron pelos logs de produção: `/api/health` mostra a presença do token, não sucesso do dispatch

## 7. Problemas e limitações conhecidos (seja honesto ao priorizar)
1. **Coleta contínua não está garantida.** O Cron Trigger da Cloudflare aciona `workflow_dispatch`, mas `/api/health` só confirma presença do segredo; validar pelos logs que cada rodada foi aceita e terminou. Sem coleta contínua não há histórico para baseline/previsão.
2. **Clusterização sem estado**: é refeita a cada rodada a partir do que os feeds mostram; o `event_id` pode mudar quando a notícia mais antiga sai do feed (duplicatas por até 24 h). Próxima etapa: clusterização com estado (Engine lê eventos existentes).
3. **Classificação inicial por keywords** gera falsos positivos (ex.: um boletim de vídeos classificado como POLITICS) e perde casos (a mesma história em dois eventos). Calibrar com dados reais.
4. **Conformidade das 5 fontes pendente**: `terms_url`/`reviewed_by` = `PENDENTE` em `engine/config/sources.json` (G1, Folha e CNN sem link de termos verificado). Alguém precisa ler os termos de cada site (coletar RSS, exibir título/link com atribuição, usar em previsões).
5. **Baseline simples**: ainda sem sazonalidade (hora do dia × dia da semana); precisa de semanas de dados.
6. **Token exposto**: um token da Cloudflare foi colado em chat; deve ser **revogado**. O token em uso no GitHub é outro, criado depois.
7. **Previsões não existem ainda** (é o coração do produto).
8. **Sem rate limiting** nem WAF; sem staging separado; sem painel admin protegido por Cloudflare Access (as rotas `/api/admin/*` usam o mesmo token do Engine).

## 8. Roadmap do backend (ordem sugerida)
| # | Item | Estado |
|---|---|---|
| 1 | Coleta confiável a cada 5 min (Cron CF → Actions) | confirmar execuções e sucesso nos logs; `scheduler_configured` indica apenas presença do segredo |
| 2 | Clusterização com estado (ids estáveis) | a fazer |
| 3 | **Previsões**: tabela `forecasts`, API, resolução e pontuação (Brier); NOWCAST primeiro | a fazer |
| 4 | Fontes oficiais (Defesa Civil, INMET, PRF, TSE, IBGE, Banco Central) por API/dados abertos | a fazer (ler termos antes) |
| 5 | Tempo real: SSE em `/api/events/live`; `/api/trending` | a fazer |
| 6 | Painel admin: proteger `/api/admin/*` (Cloudflare Access/token próprio) + definir necessidades com o front | a fazer |
| 7 | `/api/search`, `/api/timeline` | a fazer |
| 8 | Reddit e X (APIs oficiais; nunca confirmam sozinhos) | código pronto e testado (política BR); falta autorização, custo, termos, secrets e piloto de 48 h |
| 9 | Fase 3: câmeras públicas autorizadas, trânsito (Waze só por parceria), visão computacional onde permitido | futuro |
| 10 | Robustez: Queues, KV (cache), rate limiting, staging, observabilidade | conforme a carga |

Fora de escopo por restrição de termos: extrair dados do Google Maps (o mapa de calor é gerado a partir dos **nossos** eventos), raspar X/Instagram/Waze sem API autorizada, câmeras privadas.

## 8.1 Divisão de trabalho

### Primeiros passos de quem entra (≈ 1 h)
1. Pedir convite de colaborador no GitHub e membro na conta Cloudflare; receber os segredos por canal seguro (nunca por chat/PR).
2. `git clone`, `git checkout <sua branch>` e `git pull origin main`. *Qual das branches `thig`/`art`/`isar` é a sua: definir com o responsável.*
3. Ler a lista da seção 1, rodar tudo localmente (seção 3) e deixar `py -m pytest` e `npm run typecheck` verdes.
4. Combinar com o responsável a primeira tarefa (abaixo) e abrir um PR pequeno cedo para validar o fluxo.

### Passos do responsável pelo backend (+ Claude) — núcleo e infraestrutura
| # | Passo | Arquivos principais |
|---|---|---|
| N1 | Criar o token fino do GitHub e rodar `wrangler secret put GH_DISPATCH_TOKEN` (liga a coleta de 5 em 5 min) | `apps/worker/src/lib/dispatch.ts` |
| N2 | **Revogar** o token da Cloudflare que foi exposto em chat | painel Cloudflare |
| N3 | Revisar os termos das 5 fontes RSS e preencher `terms_url`/`reviewed_by` | `engine/config/sources.json` |
| N4 | Clusterização com estado (ids de evento estáveis) | `pipeline.py`, `processing/clustering.py`, `events.py` |
| N5 | **Previsões**: migration `forecasts`, `/api/forecasts`, resolução e pontuação (Brier); NOWCAST primeiro | `database/migrations`, `engine/pulso_engine/forecast*`, `routes/forecasts.ts` |
| N6 | SSE (`/api/events/live`) e `/api/trending` | `apps/worker/src/routes` |
| N7 | Revisar e fazer o merge dos PRs da colega | — |

### Passos de quem está entrando — módulos independentes (baixo conflito)
Ordem sugerida: E1 → E2 (aquecimento) → E3 → E4 → E5.
| # | Passo | Onde mexer (arquivos próprios) | Observações |
|---|---|---|---|
| E1 | Onboarding acima + PR de teste (ex.: corrigir um erro de digitação em doc) | docs | valida acesso, CI e fluxo |
| E2 | **Qualidade da classificação e da geo**: ampliar o gazetteer (mais municípios, bairros conhecidos), ajustar famílias de keywords, reduzir falsos positivos, com testes | `processing/geo.py`, `processing/keywords.json`, `tests/` | exemplos reais ruins estão na seção 7 (itens 2 e 3) |
| E3 | **Coletores de fontes oficiais**, um por PR: INMET (alertas), Defesa Civil, PRF, IBGE, Banco Central | `collectors/official/<fonte>.py` + 1 linha em `collectors/registry.py` + entrada em `config/sources.json` + ficha em `docs/sources/SOURCES.md` | **antes de codar**: ler API/termos/limites e preencher o checklist de `COLLECTION_PROTOCOL.md` §4; teste com feed gravado (sem rede) |
| E4 | `/api/search` e `/api/timeline` | `apps/worker/src/routes/search.ts`, `timeline.ts` (novos) + registrar em `index.ts` | seguir o padrão de `events.ts` (zod, cache, erros) e documentar em `docs/api/API.md` |
| E5 | Proteger `/api/admin/*` (Cloudflare Access ou token próprio) e definir com o front o que o painel precisa | `apps/worker/src/routes/admin.ts` | combinar antes com o responsável |

### Para não pisarmos um no outro
- Cada PR = uma coisa, pequeno, com testes. Arquivos de `N*` e de `E*` são separados de propósito.
- **Migrations**: após `git pull`, numere a sua como a próxima da sequência; se duas pessoas criarem o mesmo número, quem for mergear depois renumera antes do merge. Nunca editar uma migration já aplicada em produção.
- **Contratos** (`contracts.ts`, `models.py`, `API.md`): mudança só com aviso ao front e ao responsável.
- Dúvida de arquitetura → abrir um ADR curto em `docs/decisions/` antes de codar.

## 9. Decisões registradas
`docs/decisions/0001` (monorepo React + Worker + Python) · `0002` (o PULSO prevê qualquer tema, como probabilidade calibrada) · `0003` (Reddit/X como sensores sociais temáticos, nunca confirmação). Decisão nova relevante? Crie `docs/decisions/NNNN-titulo.md` e cite aqui.

## 10. Registro de mudanças (acrescente no topo)
- **2026-10-03** — Coletores Reddit e X (desativados) focados em política BR: busca temática, filtro `categories`, geo, título sem links/@menções, 429/401/403 mapeados na saúde, `interval_s` respeitado (`is_due`), `start_time` no X, modo piloto `--source`, secrets no `collect.yml`, novas keywords de política/protesto. ADR 0003. Piloto automático no `collect.yml` (`--respect-interval`; log só com contagens).
- **2026-10-03** — PR #7 mergeado e em produção (migration `0002`, Cron Trigger, rotas admin). Registro de coletores. Divisão de trabalho e onboarding (seção 8.1).
- **2026-10-03** — Cron Trigger da Cloudflare + `/api/health` com atraso da coleta; histórico em séries, baseline e anomalia; rotas admin; eventos só das últimas 24 h; política de branches (somente 5). 
- **2026-10-02** — Monorepo; Cloudflare (D1, Worker, front); deploy automático; coleta RSS; protocolo de coleta e previsão documentados.
