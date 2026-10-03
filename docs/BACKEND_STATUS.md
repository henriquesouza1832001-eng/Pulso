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

Quem precisa de acesso novo: convite como colaborador no GitHub e na conta Cloudflare (Membros). Peça os valores dos segredos a quem os criou; **não** os cole em chats, issues nem PRs.

## 3. Rodando localmente (Windows/PowerShell ou Git Bash)
```
npm install
npm run db:migrate && npm run db:seed          # D1 local + dados FICTÍCIOS
copy apps\worker\.dev.vars.example apps\worker\.dev.vars   # edite INGEST_TOKEN (local)
npm run dev:worker                              # API em :8787
npm run dev:web                                 # Web em :5173 (proxy /api → :8787)
cd engine && py -m pip install -e ".[dev]" && py -m pytest      # 36+ testes
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
- [ ] **PR #7** (hen → main): séries, baseline, anomalia, admin, Cron Trigger. *Ainda sem merge; enquanto isso a migration `0002` e a anomalia não estão em produção.*
- [ ] **Segredo `GH_DISPATCH_TOKEN`** no Worker (sem ele o Cron não aciona a coleta)

## 7. Problemas e limitações conhecidos (seja honesto ao priorizar)
1. **Coleta contínua não está garantida.** O `schedule` do GitHub nunca disparou sozinho (atrasos de mais de 30 min). Solução em curso: Cron Trigger da Cloudflare → `workflow_dispatch`. Enquanto o `GH_DISPATCH_TOKEN` não existir, o Pulso só atualiza quando alguém dispara a coleta manualmente (`gh workflow run collect.yml`). Sem coleta contínua não há histórico, e sem histórico o baseline e a previsão não funcionam.
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
| 1 | Coleta confiável a cada 5 min (Cron CF → Actions) | em andamento (falta o segredo) |
| 2 | Clusterização com estado (ids estáveis) | a fazer |
| 3 | **Previsões**: tabela `forecasts`, API, resolução e pontuação (Brier); NOWCAST primeiro | a fazer |
| 4 | Fontes oficiais (Defesa Civil, INMET, PRF, TSE, IBGE, Banco Central) por API/dados abertos | a fazer (ler termos antes) |
| 5 | Tempo real: SSE em `/api/events/live`; `/api/trending` | a fazer |
| 6 | Painel admin: proteger `/api/admin/*` (Cloudflare Access/token próprio) + definir necessidades com o front | a fazer |
| 7 | `/api/search`, `/api/timeline` | a fazer |
| 8 | Reddit e X (APIs oficiais; perfis pequenos pesam menos e nunca confirmam sozinhos) | a fazer (cadastro, custo e termos) |
| 9 | Fase 3: câmeras públicas autorizadas, trânsito (Waze só por parceria), visão computacional onde permitido | futuro |
| 10 | Robustez: Queues, KV (cache), rate limiting, staging, observabilidade | conforme a carga |

Fora de escopo por restrição de termos: extrair dados do Google Maps (o mapa de calor é gerado a partir dos **nossos** eventos), raspar X/Instagram/Waze sem API autorizada, câmeras privadas.

## 9. Decisões registradas
`docs/decisions/0001` (monorepo React + Worker + Python) · `0002` (o PULSO prevê qualquer tema, como probabilidade calibrada). Decisão nova relevante? Crie `docs/decisions/NNNN-titulo.md` e cite aqui.

## 10. Registro de mudanças (acrescente no topo)
- **2026-10-03** — Cron Trigger da Cloudflare + `/api/health` com atraso da coleta; histórico em séries, baseline e anomalia; rotas admin; eventos só das últimas 24 h; política de branches (somente 5). 
- **2026-10-02** — Monorepo; Cloudflare (D1, Worker, front); deploy automático; coleta RSS; protocolo de coleta e previsão documentados.
