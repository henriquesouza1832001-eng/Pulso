# PULSO — Estado do backend (documento vivo)

> **Última atualização:** 2026-10-03 · **Responsável pelo backend:** @henriquesouza1832001-eng (branch `hen`)
> Este arquivo é o ponto de entrada de quem entra no backend. **Quem muda algo relevante atualiza este arquivo no mesmo PR** (seções 2, 6, 7 e o registro da seção 10).

## 1. O que é o PULSO (em 30 segundos)
Plataforma brasileira de inteligência situacional em tempo real, a partir de **sinais públicos** (notícias e fontes oficiais hoje; redes sociais quando houver acesso às APIs). Agrupa sinais em **eventos**, calcula **severidade**, **confiança** e **Pulso Score** (sempre explicável), e a meta é **antecipar** acontecimentos como previsões probabilísticas calibradas, no espírito do "Pizza Index".

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
| Worker | `GH_DISPATCH_TOKEN` | token fino do GitHub (Actions: leitura e escrita, só o repo Pulso) para o Cron acionar a coleta. **Vence em 31/12/2026**: renovar antes disso (gerar novo, `wrangler secret put GH_DISPATCH_TOKEN`), senão a coleta automática para. |
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
- [x] Coleta de **~112 fontes cadastradas, 104 ONLINE em produção** (confirmado em `/api/health` em 2026-10-03; lista em `docs/sources/CATALOGO_FONTES.md`). As 8 primeiras: RSS de Agência Brasil, G1, Folha, CNN Brasil, UOL, **Agência Senado** e **Agência Câmara** (`OFFICIAL`), e avisos do **INMET** (`OFFICIAL`, só Perigo/Grande Perigo, um evento por UF). Dedup, geo (cidade/estado + gentílicos/assembleias/TRE-UF), clusterização, eventos
- [x] Confiança, Pulso Score explicável, níveis 1–5
- [x] API pública: `/api/pulse/*`, `/api/events`, `/api/events/:id`, `/api/map`, `/api/health`
- [x] Rotas internas: `/api/ingest`, `/api/admin/series`, `/api/admin/overview`
- [x] Histórico em séries (5 min), baseline (EWMA) e anomalia (inválida com < 12 h de dados)
- [x] Protocolo de coleta validado em código; `/api/health` mostra o atraso da coleta
- [x] Testes: 127 Python, 7 do Worker (2026-10-03)
- [x] **Catálogo de ~110 fontes (103 ativas)** com leitor RSS tolerante e coleta paralela; ver `docs/sources/CATALOGO_FONTES.md` (gerado) e ADR 0006. Rodada real medida: ~45 s para 81 fontes
- [x] **Frescor por categoria** no Pulso (o impactante de agora vale mais que o de 12 h atrás) e **qualidade de eventos** (agrupamento sem encadeamento, estado por maioria, publicação criteriosa): de 1793 para 466 eventos na mesma coleta
- [x] **Previsão de volume por categoria** (`signals_<tema>`) + backtest walk-forward; só prevê com histórico (ADR 0006)
- [x] **INPE Queimadas** (`inpe-queimadas`, OFFICIAL): um sinal por UF e por janela de 3 h quando passa de 150 detecções de calor por satélite (calibrado com o dia 2026-10-02: ~25 sinais em 9 estados). Dado numérico e oficial da frente de fogo na temporada seca
- [x] **Banco Central, dólar PTAX** (`bcb-ptax`, OFFICIAL, serviço Olinda): sinal ECONOMY só em choque cambial (≥ 1% ao dia). Fontes de limiar (`inmet-avisos`, `inpe-queimadas`, `bcb-ptax`) levam `quiet_ok`: sem ocorrência a saúde é ONLINE, não DEGRADED
- [x] **Defesa Civil Nacional** (`defesa-civil-idap`, OFFICIAL): alertas CAP oficiais (chuvas intensas, estiagem, corridas de massa...) lidos em fluxo de um feed de ~22 MB; severidade Moderate+ e vigentes (Extreme vira EMERGENCY). Medido: 11 s por leitura, ~5 MB de memória, 24 alertas vigentes na primeira leitura real
- [x] **InfoDengue** (`infodengue-capitais`, OFFICIAL): alerta semanal de dengue nas 27 capitais (nível >= 3). Primeira leitura real: Belo Horizonte em alerta laranja
- [x] **Operação**: `py -m pulso_engine.healthcheck` (e o workflow `healthcheck.yml`, a cada 30 min, que falha e avisa o dono se a coleta parar, o banco cair ou a maioria das fontes ficar OFFLINE), `py -m pulso_engine.audit` (roda cada fonte e mostra itens, frescor, UF e categorias; 102 das 103 ativas entregando em 2026-10-03, só `gov-saude` parada há 99 h) e `docs/RUNBOOK.md` (sintomas, causas e como verificar uma mudança)
- [x] **Orçamento do D1** (ADR 0006): o motor escreve só o que mudou (~40 linhas/ciclo em regime estável, antes ~850) e o Worker aceita 500 fontes por lote (o limite 100 derrubaria a ingestão com 110 fontes)
- [x] Verificação ponta a ponta local (2026-10-03): Worker local + migrações + rodada real do motor com `--push` + `GET /api/health`, `/api/stats`, `/api/events`, `/api/forecasts`, `/api/pulse/states` respondendo corretamente

**Em andamento / aguardando**
- [x] **PR #7** mergeado e publicado em 2026-10-03: séries, baseline, anomalia, rotas admin, Cron Trigger (`*/5 * * * *` registrado), migration `0002` aplicada
- [x] Registro de coletores (`collectors/registry.py`): fonte nova = arquivo novo + uma linha, sem mexer no pipeline
- [x] Adaptadores Reddit/X completos para política BR (busca temática, filtro por categoria, geo, `RATE_LIMITED`/`AUTH_ERROR`, cadência por `interval_s`, modo piloto `--source`); `enabled: false`, sem autorização nem credenciais (ADR 0003)
- [ ] Reddit: abrir pedido de acesso (Responsible Builder Policy exige aprovação prévia desde nov/2025; RSS do Reddit é bloqueado pelo robots.txt)
- [x] **8 fontes ativas** (2026-10-03): 5 RSS + Agência Senado, Agência Câmara e INMET (ativação antecipada, piloto < 48 h, decisão de Arthur266760). O painel "Fontes ativas" acompanha o `sources.json` (`catalog_complete`)
- [x] Clima impactante por estado: coletor oficial `inmet` (avisos Perigo/Grande Perigo, um evento por UF) + `reddit-clima`/`x-clima`; geo com gentílicos/assembleias/TRE; Reddit regional por UF (ADR 0004). Tudo `enabled: false` aguardando revisão
- [x] Piloto automático no `collect.yml`: liga sozinho quando os secrets sociais existirem, sem envio e sem conteúdo no log
- [ ] Reddit/X: registrar app/contratar plano (com teto de gasto), revisar termos, criar secrets (inicia o piloto), avaliar 48 h e só então `enabled: true` (checklist em `docs/sources/SOURCES.md`)
- [ ] Confirmar cadência do Cron pelos logs de produção: `/api/health` mostra a presença do token, não sucesso do dispatch

## 7. Problemas e limitações conhecidos (seja honesto ao priorizar)
1. **Coleta contínua**: Cron Trigger da Cloudflare confirmado em produção em 2026-10-03 (coleta a cada 5 min). `/api/health` só mostra a presença do segredo: acompanhar pelos logs que cada rodada foi aceita e terminou. `GH_DISPATCH_TOKEN` vence em 31/12/2026. Sem coleta contínua não há histórico para baseline/previsão.
2. ~~Clusterização sem estado~~ **Resolvido em 2026-10-03**: o Engine busca os sinais das últimas 24 h (`/api/admin/signals`), agrupa tudo junto e reaproveita o `event_id` existente. Limitação: se dois eventos antigos se fundirem, o menor id vence e o outro fica órfão até sair da lista de 24 h.
3. **Classificação inicial por keywords** gera falsos positivos (a geolocalização teve um bug grave de "para"=Pará, já corrigido; ainda só reconhece capitais e estados) (ex.: um boletim de vídeos classificado como POLITICS) e perde casos (a mesma história em dois eventos). Calibrar com dados reais.
4. **Conformidade pendente em ~95 fontes** (o catálogo foi ativado por decisão do dono, ADR 0006). Item original: `terms_url`/`reviewed_by` = `PENDENTE` em `engine/config/sources.json` (G1, Folha e CNN sem link de termos verificado). Alguém precisa ler os termos de cada site (coletar RSS, exibir título/link com atribuição, usar em previsões).
5. **Baseline simples**: ainda sem sazonalidade (hora do dia × dia da semana); precisa de semanas de dados.
6. **Token exposto**: um token da Cloudflare foi colado em chat; deve ser **revogado**. O token em uso no GitHub é outro, criado depois.
7. **Previsões: v1 NOWCAST do Pulso do Brasil (60 min) e de volume por categoria**, EXPERIMENTAL e sem histórico de acertos ainda. Só começa a prever com ~3,5 h de histórico contínuo do Pulso; precisa de 100 previsões resolvidas para deixar de ser experimental.
13. **Limite do D1 gratuito**: 100 mil escritas e 5 milhões de leituras por dia. Hoje ~12 mil escritas/dia estimadas e ~3–4 milhões de leituras/dia (a leitura é o que mais aperta; ver ADR 0006). Se o plano for gratuito, acompanhar o consumo no painel da Cloudflare nos primeiros dias; a saída é espaçar o ciclo (10 min) ou migrar para o plano pago.
14. **Deploy**: o Worker novo (limite de 500 fontes, `/api/admin/events-digest`) precisa estar publicado antes do primeiro envio do catálogo completo; nos ciclos comuns o motor já manda < 100 fontes, então a janela de risco é só o horário de revisão (minutos 0–4 e 30–34).
9. **Lacunas de cobertura regional**: sem RSS utilizável para SP capital, RJ, MG, PE e CE (os feeds do G1 desses estados estão parados desde ~2018; o do governo de SP está atrás de desafio anti-robô e não será contornado).
10. **GDELT não validado** (429 persistente, consulta vazia) e **X nunca chamado ao vivo** (sem token). Reddit aguarda aprovação. Raspagem de redes sociais e captcha: não implementados.
11. **Limiares heurísticos** (frescor, 25% de semelhança, importância) validados em 1 coleta real e em testes; precisam de recalibração com semanas de dados. O backtest da previsão é **sintético**: prova a mecânica, não a acurácia.
12. **Aviso oficial vigente esfria** (datado pelo início): renovar o frescor enquanto estiver em vigor é próximo passo.
8. **Sem rate limiting** nem WAF; sem staging separado; sem painel admin protegido por Cloudflare Access (as rotas `/api/admin/*` usam o mesmo token do Engine).

## 8. Roadmap do backend (ordem sugerida)
| # | Item | Estado |
|---|---|---|
| 1 | Coleta confiável a cada 5 min (Cron CF → Actions) | **feito** (confirmado em 2026-10-03); acompanhar logs; renovar token até 31/12/2026 |
| 2 | Clusterização com estado (ids estáveis) | **feito** (2026-10-03) |
| 3 | **Previsões**: tabela `forecasts`, API, resolução e pontuação (Brier); NOWCAST primeiro | **v1 feita** (experimental). Faltam EVENT/QUANTITY/OPEN e modelos melhores |
| 4 | Fontes oficiais (Defesa Civil, INMET, PRF, TSE, IBGE, Banco Central) por API/dados abertos | INMET, Agência Senado e Agência Câmara **ativos**; próximos: TSE (candidaturas), dados abertos da Câmara/Senado, Defesa Civil, GDELT (tensões) |
| 5 | Tempo real: SSE em `/api/events/live`; `/api/trending` | a fazer |
| 6 | Painel admin: proteger `/api/admin/*` (Cloudflare Access/token próprio) + definir necessidades com o front | a fazer |
| 7 | `/api/search`, `/api/timeline` | a fazer |
| 9 | **Câmeras ao vivo**: contrato `/api/cameras` + Worker + front; via Windy (precisa de chave gratuita, atribuição e link) ou autorização de órgãos (`docs/sources/CAMERAS.md`) | a fazer, depende da chave |
| 10 | **Revisão de termos** das ~95 fontes ativas (`terms_url`, `reviewed_by`) | a fazer (pessoa) |
| 11 | **Indicadores antecedentes** entre categorias (ex.: aviso de chuva → alagamento/trânsito), adotados só se melhorarem o Brier no backtest; sazonalidade hora × dia da semana | a fazer |
| 12 | Frescor renovado enquanto aviso oficial estiver vigente; fontes regionais para SP/RJ/MG/PE/CE | a fazer |
| 8 | Reddit e X (APIs oficiais; nunca confirmam sozinhos) | código pronto (política e clima por UF); Reddit exige pedido de acesso (Responsible Builder Policy), X exige plano pago com teto de gasto; secrets → piloto automático |
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
| N4 | ~~Clusterização com estado~~ **feito** | `pipeline.py`, `events.py` |
| N5 | **Previsões**: v1 NOWCAST feita; seguir com EVENT, QUANTITY, OPEN e calibração | `database/migrations`, `engine/pulso_engine/forecast*`, `routes/forecasts.ts` |
| N6 | SSE (`/api/events/live`) e `/api/trending` | `apps/worker/src/routes` |
| N7 | Revisar e fazer o merge dos PRs da colega | — |

### Passos de quem está entrando — módulos independentes (baixo conflito)
Ordem sugerida: E1 → E2 (aquecimento) → E3 → E4 → E5.
| # | Passo | Onde mexer (arquivos próprios) | Observações |
|---|---|---|---|
| E1 | Onboarding acima + PR de teste (ex.: corrigir um erro de digitação em doc) | docs | valida acesso, CI e fluxo |
| E2 | **Qualidade da classificação e da geo**: ampliar o gazetteer (mais municípios, bairros conhecidos), ajustar famílias de keywords, reduzir falsos positivos, com testes | `processing/geo.py`, `processing/keywords.json`, `tests/` | exemplos reais ruins estão na seção 7 (itens 2 e 3) |
| E3 | **Coletores de fontes oficiais**, um por PR: ~~INMET (alertas)~~ ✅ feito (`collectors/official/inmet.py` serve de modelo), Defesa Civil, PRF, IBGE, Banco Central, TSE (candidaturas) | `collectors/official/<fonte>.py` + 1 linha em `collectors/registry.py` + entrada em `config/sources.json` + ficha em `docs/sources/SOURCES.md` | **antes de codar**: ler API/termos/limites e preencher o checklist de `COLLECTION_PROTOCOL.md` §4; teste com feed gravado (sem rede) |
| E4 | `/api/search` e `/api/timeline` | `apps/worker/src/routes/search.ts`, `timeline.ts` (novos) + registrar em `index.ts` | seguir o padrão de `events.ts` (zod, cache, erros) e documentar em `docs/api/API.md` |
| E5 | Proteger `/api/admin/*` (Cloudflare Access ou token próprio) e definir com o front o que o painel precisa | `apps/worker/src/routes/admin.ts` | combinar antes com o responsável |

### Para não pisarmos um no outro
- Cada PR = uma coisa, pequeno, com testes. Arquivos de `N*` e de `E*` são separados de propósito.
- **Migrations**: após `git pull`, numere a sua como a próxima da sequência; se duas pessoas criarem o mesmo número, quem for mergear depois renumera antes do merge. Nunca editar uma migration já aplicada em produção.
- **Contratos** (`contracts.ts`, `models.py`, `API.md`): mudança só com aviso ao front e ao responsável.
- Dúvida de arquitetura → abrir um ADR curto em `docs/decisions/` antes de codar.

## 9. Decisões registradas
`docs/decisions/0001` (monorepo React + Worker + Python) · `0002` (o PULSO prevê qualquer tema, como probabilidade calibrada) · `0003` (Reddit/X como sensores sociais temáticos, nunca confirmação) · `0004` (eventos separados por UF; avisos do INMET). Decisão nova relevante? Crie `docs/decisions/NNNN-titulo.md` e cite aqui. · `0005` (filtro de importância e fontes abertas GDELT/Mastodon/USGS) · `0006` (fontes em escala, frescor por categoria e qualidade de eventos) · `0007` (piso de alerta oficial, leitura estrita do Worker e sinalizadores de fonte).

## 10. Registro de mudanças (acrescente no topo)
- **2026-10-03** — **Segunda revisão independente** (6 achados confirmados, todos corrigidos com teste em `tests/test_review_fixes2.py`): (1) um evento gravado que se divide dava o MESMO id a dois grupos (evento duplicado e Pulso em dobro): `assign_event_ids` garante um id por grupo; (2) `is_due` perdia uma janela se a rodada atrasasse: fontes de >= 1 h têm janela de 2 rodadas; (3) nomes de cidade que são pessoa ou palavra ("Marília Mendonça", "picos de calor", "patos", "Olinda Dias", "Timon") só localizam com contexto; (4) "ira", "peru" e "franca" saíram da lista de países estrangeiros (só formas com preposição: "no Peru", "na França"); (5) fonte geográfica nunca é sobrescrita pelo texto na releitura de sinais gravados; (6) baseline esparso (quase só zeros) não vale como "normal". 235 testes Python.
- **2026-10-03** — Defeito achado inspecionando a produção: o alerta extremo de "São Borja/RS" se fundia com os de "Manaus/AM" (evento com estado AM) porque a trava "estados diferentes não se juntam" exigia confiança 60 e a sigla de estado vale 55. Trava passa a 55 e a Defesa Civil/IDAP usa confiança 70 no estado da área oficial. Teste reproduz o caso real. 229 testes Python.
- **2026-10-03** — Piso de nível 3 para alerta oficial de risco extremo (`alert_source` em `sources.json`: INMET e Defesa Civil; categoria EMERGENCY = "Grande Perigo"/"Extreme"), explícito no "POR QUE?" com 0 pontos e sem alterar o score. Na coleta real: 5 eventos de nível 3 (São Borja/RS inundação extrema; Manaus/AM; avisos do INMET agrupados com "Grande Perigo"), sem fadiga de alerta. 227 testes Python.
- **2026-10-03** — BHAZ e UAI (MG) adicionados (lacuna regional de Minas). Novo `docs/PENDENCIAS_DO_DONO.md`: chaves, planos e revisões que só o dono pode fazer (Windy, Reddit, X, Bluesky, termos das fontes, D1, eleição de domingo).
- **2026-10-03** — **Revisão independente de código** (skill `code-review`, nível alto, sobre `engine/pulso_engine`): 5 achados confirmados no código e corrigidos, cada um com teste (`tests/test_review_fixes.py`). (1) uma fonte `metrics_only` ATIVA encerrava a rodada antes do envio: a ingestão pararia em silêncio ao ligar uma; agora envia e só esconde o conteúdo do log. (2) `regeolocate` apagava a geografia que vem da própria fonte (estado de feed regional, INPE, Defesa Civil, USGS...) em sinais já gravados: agora preserva a das fontes geográficas (`GEO_ADAPTERS` + `state`) e continua limpando localização antiga errada das demais. (3) `chunks` descartava sinais de um evento que não foi reenviado: agora vão em partes próprias. (4) erro ao ler o Worker virava "banco vazio" (reenviaria e recriaria tudo): sinais e resumo de eventos são leituras ESTRITAS; Worker indisponível pula o ciclo (exit 0, aviso) e token recusado falha (exit 1). (5) uma fonte nova que falha antes de ser registrada derrubaria o lote por chave estrangeira: as fontes das linhas de saúde enviadas vão junto. 223 testes Python.
- **2026-10-03** — `push_batch` repete até 2 vezes falhas transitórias (rede, 502/503/504) com espera de 2 s e 5 s (a ingestão é idempotente) e passa a mostrar o motivo de uma recusa (`PushError` com o corpo da resposta, nunca o token). 216 testes Python.
- **2026-10-03** — Testes de sistema: `test_cycle_simulation` (vários ciclos contra um Worker de mentira: id de evento estável, nada reescrito sem mudança, matéria velha fora, frescor, fonte nova sobre o mesmo fato) e `test_forecast_loop_simulation` (laço de previsão de ponta a ponta). Previsão com id já aberto não é reenviada. 211 testes Python.
- **2026-10-03** — Precisão da categoria revisada com manchetes reais: acontecimento físico de outro país vira INTERNATIONAL (não conta nas séries brasileiras); `bombeiros`/`resgate`/`atropela` genéricos saem do vocabulário. Na coleta real: +22 sinais INTERNATIONAL e -5 trânsito, -5 saúde, -7 protesto, -4 emergência (falsos positivos ou de fora do Brasil).
- **2026-10-03** — Coletor oficial `infodengue` (alerta de dengue nas 27 capitais, API aberta Fiocruz/FGV; geocódigos validados ao vivo). 114 fontes cadastradas. Docs de API e arquitetura atualizados (mapa de módulos do Engine).
- **2026-10-03** — Produção mostrou 2 fontes OFFLINE: `metsul` (403 do GitHub Actions: bloqueio de IP de nuvem, desligada; não se contorna) e `agencia-camara` (timeout transitório). O coletor passa a repetir UMA vez falhas de rede transitórias (timeout/conexão), nunca erros HTTP.
- **2026-10-03** — Defeito pego pela auditoria: Mastodon, USGS e GDELT recebiam `fetcher=None` do pipeline e quebrariam só ao rodar (o Mastodon, em silêncio); corrigido em `URL_FETCH_ADAPTERS` e travado por `tests/test_registry_contract.py`. USGS ativado. Mastodon continua desligado por medição (sem atividade sobre desastre em português). Bluesky exige credencial.
- **2026-10-03** — Coletor oficial `idap_cap` (alertas da Defesa Civil Nacional, feed CAP de ~22 MB lido em fluxo). 113 fontes cadastradas.
- **2026-10-03** — Coletor oficial `bcb_ptax` (dólar PTAX por Olinda; `api.bcb.gov.br` não resolve DNS no ambiente de teste) e flag `quiet_ok` para fontes de limiar (sem ocorrência = ONLINE, `last_success` marcado). 112 fontes cadastradas.
- **2026-10-03** — Novo coletor oficial `inpe_fires` (focos de calor do INPE por UF, limiar 150 detecções/3 h) ativo; `URL_FETCH_ADAPTERS` centraliza quais adaptadores recebem o `fetcher`. Catálogo regenerado (111 fontes). Banco Central (séries SGS) e GDELT não responderam do ambiente de teste e não foram integrados.
- **2026-10-03** — PR #16 em produção (deploy verde; primeiros ciclos reais: regime estável de ~110 linhas escritas por ciclo com 27 pulsos, 30 sinais, 39 eventos e 9 linhas de série). Operação: `healthcheck` (workflow a cada 30 min), `audit` e `docs/RUNBOOK.md`. A rodada que coincidiu com o deploy falhou (Worker em troca) e a seguinte passou.
- **2026-10-03** — Verificação geral e expansão. ~110 fontes (103 ativas) com leitor RSS tolerante (gzip, RDF, XML sujo) e coleta paralela; frescor por categoria no Pulso; agrupamento sem encadeamento, estado do evento por maioria e publicação criteriosa (1793 → 466 eventos); título decide a categoria; vocabulário ampliado (saúde, economia, infraestrutura, trânsito, segurança, clima, internacional, tecnologia, eventos) com régua de regressão de manchetes; previsão de volume por categoria e backtest; catálogo gerado; lista de câmeras (`CAMERAS.md`). ADR 0006. GDELT não validado; raspagem/captcha não implementados.
- **2026-10-02** — Filtro de importância (`processing/importance.py`: só desastre/vítimas/emergência; descarta fofoca e notícia de outro país) e coletores GDELT, Mastodon (hashtags) e USGS, todos desligados em `sources.json` até a revisão do protocolo. X e INMET já vinham da `art` (ADR 0003/0004) e foram mantidos; meu coletor duplicado foi removido. Ver ADR 0005.
- **2026-10-03** — Estados mais coesos. Geo: siglas de UF com contexto ("Ariquemes, RO", "em SP", "(MG)") e ~150 cidades do interior (precisão `STATE`, nome em `city`; nomes ambíguos como Santos/Contagem/Suzano só com contexto). Coleta real: eventos sem UF 104→92, UFs com notícia 22→24; o restante é nacional/internacional de fato. Front: filtro de estado no feed (clicar numa UF no mapa/lista recorta o feed; opção "nacional/sem UF"), rótulo "nacional"/"internacional" no lugar de "localizando…". Pendência conhecida: evento órfão duplicado após fusão de clusters (ex.: dois "TSE revoga liminar de Garotinho").
- **2026-10-03** — Front (Feed OSINT): paginação numerada (10 por página) no lugar da rolagem infinita; ordem sempre por nível (N5→N1) e depois recência/Pulso; N2+ destacado pela cor do nível; alertas N3+ fixos no topo em todas as páginas; evento clicado no mapa leva ao feed e abre a página onde ele está. Verificado no navegador (Playwright) com dados de produção.
- **2026-10-03** — PR #14 mergeado e em produção: `/api/health` com 8 fontes ONLINE (Agência Senado, Agência Câmara e INMET novos); painel "Fontes ativas" do front sincronizado com `config/sources.json` via `catalog_complete`. PR #12 (Reddit/X, INMET, geo por UF, ADRs 0003/0004) também em produção.
- **2026-10-03** — Ativadas Agência Senado, Agência Câmara e INMET (8 fontes). Ingestão com `catalog_complete` (contrato aditivo): a coleta normal manda o catálogo de fontes ativas e o Worker desativa as ausentes, então `/api/health` e o painel do front acompanham o `config/sources.json`. Verificado com Worker local + D1 (remover, lote parcial, reativar).
- **2026-10-03** — Clima e política por estado: coletor `inmet` (avisos oficiais, só Perigo/Grande Perigo, um sinal por UF), `reddit-clima`/`x-clima`, comunidades regionais do Reddit com UF, geo com gentílicos/assembleias/TRE-UF, clusterização não junta UFs diferentes da mesma fonte, piloto das fontes oficiais no `collect.yml`. ADR 0004.
- **2026-10-03** — RSS da Agência Senado e da Agência Câmara propostos como fontes `OFFICIAL` de política (fichas em `SOURCES.md`). Reddit: confirmado que todo acesso à API exige aprovação prévia; RSS do Reddit descartado (robots.txt).
- **2026-10-03** — Coletores Reddit e X (desativados) focados em política BR: busca temática, filtro `categories`, geo, título sem links/@menções, 429/401/403 mapeados na saúde, `interval_s` respeitado (`is_due`), `start_time` no X, modo piloto `--source`, secrets no `collect.yml`, novas keywords de política/protesto. ADR 0003. Piloto automático no `collect.yml` (`--respect-interval`; log só com contagens).
- **2026-10-03** — PR #11 em produção (previsões v1, correção do "para"=Pará, endpoints do front). Migration `0004`: pico por evento (`peak_alert_level/peak_pulse/peak_at`); `GET /api/history`.
- **2026-10-03** — Revisão do front: `docs/FRONTEND_DATA_MAP.md`. **Bug de geolocalização corrigido** (a preposição "para" virava o estado do Pará; também Acre, Espírito Santo e Belém de Israel) e sinais gravados são regeolocalizados a cada rodada. `delta_2h` só com ponto real. Novos endpoints públicos `/api/pulse/history`, `/api/pulse/states`, `/api/stats`.
- **2026-10-03** — Previsões v1: tabela `forecasts` (migration 0003), `/api/forecasts*`, previsor NOWCAST `pulse_empirical_delta`, resolução automática e Brier, previsão imutável. Rotas internas `/api/admin/pulse-history` e `/api/admin/forecasts/open`.
- **2026-10-03** — Agrupamento com estado (ids de evento estáveis, rodada estável reenvia 0 sinais); `GET /api/admin/signals`; sinais isolados também são gravados; retenção de 90 dias para sinais. Cron da Cloudflare confirmado em produção (coleta a cada 5 min). Token `GH_DISPATCH_TOKEN` vence em 31/12/2026.
- **2026-10-03** — PR #7 mergeado e em produção (migration `0002`, Cron Trigger, rotas admin). Registro de coletores. Divisão de trabalho e onboarding (seção 8.1).
- **2026-10-03** — Cron Trigger da Cloudflare + `/api/health` com atraso da coleta; histórico em séries, baseline e anomalia; rotas admin; eventos só das últimas 24 h; política de branches (somente 5). 
- **2026-10-02** — Monorepo; Cloudflare (D1, Worker, front); deploy automático; coleta RSS; protocolo de coleta e previsão documentados.
