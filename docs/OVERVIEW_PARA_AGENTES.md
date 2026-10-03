# PULSO — visão geral para agentes de IA (Codex, Claude e outros)

> Leia **`AGENTS.md`** (raiz) primeiro; ele é a lista de regras. Este arquivo dá o contexto, o que já foi feito, quem faz o quê e como entregar. Estado em tempo real: `docs/BACKEND_STATUS.md` (documento vivo; confira a data de atualização antes de confiar em qualquer informação).

## 1. Missão do produto
Plataforma brasileira de inteligência situacional: transforma **sinais públicos** em **eventos** geolocalizados com **severidade**, **confiança** e **Pulso Score** explicáveis, e **antecipa** acontecimentos como **previsões probabilísticas calibradas** (no espírito do "Pizza Index"). Frase-guia: *observar, correlacionar, localizar, confirmar, explicar, visualizar.*

### Princípios inegociáveis
1. **Sinal fraco não é fato.** Rede social detecta, não confirma sozinha (teto de confiança 40 só com social).
2. **Severidade ≠ confiança.** São medidas independentes.
3. **Toda previsão é uma probabilidade** com incerteza, evidências, método/versão, rótulo "PREVISÃO", registrada antes do resultado e pontuada depois (Brier). Nunca apresentada como fato. Alerta nível 4–5 nunca vem só de previsão.
4. **Tudo explicável e rastreável**: o score tem decomposição ("POR QUE N?"); todo dado ligado à fonte original.
5. **Só vias autorizadas** de coleta (API oficial, dados abertos, RSS). Sem contornar login/limites/termos; sem scraping de plataformas que proíbem; sem câmeras privadas; sem reconhecimento facial nem perfilamento de indivíduos.
6. **Honestidade estatística**: sem histórico suficiente, não se afirma anomalia (baseline inválido com < 12 h → anomalia 0).
7. **Nenhuma integração é ponto único de falha.** Falha vira `source_health`, não queda.

## 2. Arquitetura
```
Fontes → Engine (Python: coleta, normaliza, dedup, geo, clusteriza, scoring)
       → POST /api/ingest (token) → Worker (Cloudflare) → D1
       → API pública → Web (React, outra pessoa)
Cron da Cloudflare (*/5 min) → workflow_dispatch → GitHub Actions executa o Engine
```
| Pasta | Conteúdo |
|---|---|
| `engine/pulso_engine/` | `collectors/` (`registry.py`, `news/rss.py`), `processing/` (normalizer, geo, clustering, keyword_engine, keywords.json), `scoring/` (confidence, pulse), `series.py`, `baseline.py`, `anomaly.py`, `events.py`, `pipeline.py`, `client.py`, `config.py`, `models.py` |
| `engine/config/sources.json` | fontes (validadas por `config.py` contra o protocolo) |
| `apps/worker/src/` | `routes/` (health, pulse, events, map públicas; ingest, admin com token), `lib/` (auth, cache, dispatch), `index.ts` (fetch + `scheduled`) |
| `database/migrations/` | `0001_init.sql`, `0002_series.sql` |
| `packages/shared/src/contracts.ts` | contratos (espelho: `engine/pulso_engine/models.py`) |
| `apps/web/` | front React (não mexer sem combinar) |
| `docs/` | arquitetura, previsão, protocolo de coleta, scoring, API, fontes, decisões (ADR) |

Em produção: API `https://pulso-api.henriquesouza.workers.dev`, Web `https://pulso-web.henriquesouza.workers.dev`, D1 `pulso`. Deploy automático pelo GitHub Actions a cada merge na `main`.

## 3. O que já está feito (resumo)
Monorepo e CI; Cloudflare (Worker, D1, front) com deploy automático; coleta de ~112 fontes (RSS de imprensa nacional, regional e internacional, e órgãos oficiais; avisos do INMET, focos de calor do INPE e dólar PTAX do Banco Central) em paralelo, com dedup, geo (cidade/estado), clusterização e eventos; confiança, Pulso Score explicável e níveis 1–5; API pública e rotas internas (`/api/ingest`, `/api/admin/series`, `/api/admin/overview`); histórico em séries, baseline (EWMA) e anomalia; protocolo de coleta validado em código; `/api/health` com atraso da coleta; Cron Trigger registrado; registro de coletores; frescor por categoria, eventos com agrupamento e publicação criteriosos, previsões de pulso e de volume por categoria (EXPERIMENTAIS), healthcheck e auditoria de fontes; ~172 testes Python e 7 do Worker. Ver `docs/BACKEND_STATUS.md` (estado vivo) e `docs/RUNBOOK.md` (operação).

## 4. Pendências e riscos (não os esconda ao priorizar)
1. **Coleta contínua ainda não verificada de ponta a ponta.** O `schedule` do GitHub não dispara com confiança; o Cron da Cloudflare foi implementado e o segredo `GH_DISPATCH_TOKEN` foi criado, mas **o disparo automático ainda não foi confirmado**. Sem coleta contínua não há histórico, e sem histórico não há baseline nem previsão.
2. Clusterização **sem estado** (ids de evento podem mudar entre rodadas).
3. Classificação por keywords com falsos positivos; geo só reconhece capitais/estados.
4. Conformidade de ~95 fontes **pendente** (`terms_url`/`reviewed_by` = `PENDENTE`); o catálogo foi ativado por decisão do dono (ADR 0006).
5. Não existem ainda: previsões (`forecasts`), SSE, `/api/trending`, `/api/search`, `/api/timeline`, fontes oficiais/sociais, rate limiting, staging.
6. Limite do D1 gratuito (~50 consultas por requisição): gravações em lote usam `json_each`, uma instrução por tabela. Não volte a um comando por linha.

## 5. Quem faz o quê
| Quem | Faz |
|---|---|
| **Henrique** (dono do backend) + Claude | Confirmar o Cron; revogar o token antigo da Cloudflare; revisar termos das fontes; agrupamento com estado; **previsões** (migration `forecasts`, API, Brier); SSE e trending; revisar e fazer merge dos PRs. |
| **A colega e o seu agente (você, Codex)** | Tarefas E1–E5 abaixo, em branch própria, via PR. |
| **Pessoa do front** | Interface React; consome a API. |

## 6. O que o agente deve fazer (tarefas E1–E5)
Detalhes e critérios de aceite completos: `docs/ONBOARDING_BACKEND.md` §5. Resumo:
- **E1** PR mínimo de validação do fluxo.
- **E2** Melhorar `processing/geo.py` e `processing/keywords.json` com testes de casos reais em `engine/tests/`.
- **E3** Um coletor oficial por PR (INMET, Defesa Civil, PRF, IBGE, Banco Central) em `collectors/official/<fonte>.py` + uma linha em `collectors/registry.py` + `config/sources.json` + ficha em `docs/sources/SOURCES.md`; **leia API/termos antes de codar**; teste sem rede com resposta gravada.
- **E4** `routes/search.ts` e `routes/timeline.ts` no Worker, padrão de `routes/events.ts`, documentando em `docs/api/API.md`.
- **E5** Proteção de `/api/admin/*`: só depois de combinar com o Henrique (ADR).

## 7. Como trabalhar (obrigatório)
1. `git status`, `git branch --show-current`, `git pull origin main`. Trabalhe **somente** na branch da pessoa que o acionou (`thig`, `art` ou `isar`). **Não crie outras branches. Nunca trabalhe na `main`.**
2. Antes de mudar, leia o código vizinho e siga o estilo (comentários em português, validação com zod no Worker, dataclasses no Engine).
3. Não sobrescreva nem apague trabalho de outra pessoa; se houver conflito, adapte ou pergunte.
4. Rode: `cd engine && py -m pytest` e, na raiz, `npm run typecheck`. Verifique o **comportamento real** (suba o Worker local e chame o endpoint), não só "compilou".
5. **Contratos** (`contracts.ts`, `models.py`, `API.md`): não mude sem aviso; se mudar, os três juntos.
6. **Segredos**: nunca commitar `.env`, `.dev.vars`, tokens; nunca imprimir segredos em logs; nunca colar em PR/chat. Se precisar de uma credencial, **peça ao humano**.
7. **Não faça merge na `main`, não faça deploy, não crie recursos na Cloudflare, não rode migrations em produção, não altere secrets.** Isso é do Henrique.
8. Migrations: nova = próximo número da sequência após `git pull`; nunca editar uma já aplicada.
9. Fonte nova: siga `docs/COLLECTION_PROTOCOL.md`. Se a política da fonte não permitir o uso, **pare e informe**, não contorne.
10. Entrega: commits `tipo: descrição`; PR pequeno para a `main` com "o que mudou / como testar / resultado dos testes"; atualize `docs/BACKEND_STATUS.md` (estado e registro de mudanças).

## 8. Definição de pronto
Testes novos e antigos verdes; typecheck verde; comportamento verificado manualmente; docs atualizados; nenhum segredo no diff; PR aberto, não mergeado. Ao reportar, diga com franqueza o que **não** foi testado ou ficou incompleto.

## 9. Quando parar e perguntar
Se a tarefa exigir: credenciais, mudança de contrato, decisão de arquitetura, fonte com termos duvidosos, ação em produção, ou se encontrar código de outra pessoa que conflita. Descreva o bloqueio e a opção que recomenda.
