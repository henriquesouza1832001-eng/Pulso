# O que falta fazer

Lista honesta do que **não** está pronto. Atualizada no fim de cada rodada. Dono entre colchetes. Status de cada item: ABERTO, EM ANDAMENTO ou DEPENDE (de dados, de decisão ou de outra pessoa).

Última atualização: 2026-10-03, rodada 2 de hardening (plataforma): storage ensaiado sob falha.

## A. Plataforma (Claude B / hen)
| # | O que falta | Status | Por quê importa |
|---|---|---|---|
| A1 | **Ensaio de falha do storage (RT-005), parte remota:** a lógica do Worker/adaptador está ensaiada (rodada 2); falta o servidor Turso real e o binding D1 real (timeout, lote parcial) — só dá com credenciais, em ambiente de teste. | EM ANDAMENTO | A prova local não substitui o banco de verdade. |
| A1b | **`write_budget` gravado depois do lote:** com resposta perdida o orçamento subestima. Mover a contagem para dentro da mesma transação do lote. | ABERTO | Governador otimista por um lote. |
| A2 | **Token administrativo separado (RT-007):** hoje `/api/admin/*` usa o mesmo token do ingest. | ABERTO (código é meu; criar o segredo é do dono) | Menor privilégio: quem escreve lote não deveria ler o painel. |
| A3 | **Rate limit / WAF na borda (RT-007).** | DEPENDE do dono (regra no painel da Cloudflare; Worker sem estado não limita sozinho) | Sem isso, token vazado ou força bruta não encontra freio. |
| A4 | **Trilha de auditoria do admin** (quem leu o quê). | ABERTO | Rotas de diagnóstico expõem dados operacionais. |
| A5 | **Frescor de CONTEÚDO por fonte (RT-002):** fonte com HTTP 200 e conteúdo repetido/parado deve aparecer como STALE, sem virar "normal". Hoje só a idade do Pulso nacional é medida. | ABERTO (engine mede; Worker expõe) | HTTP 200 não é dado novo. |
| A6 | **Cobertura degradada até o forecast e o status:** quais sensores faltam, por escopo. | ABERTO | O operador precisa ver "enxergo pouco", não só um número. |
| A7 | **Retry/backoff com jitter e Retry-After, circuit breaker simples** nos collectors (collector_result padronizado: transporte, frescor, parse, retryable). | ABERTO (engine; combinar com Claude A) | `[]` hoje pode significar saudável, bloqueado ou parse quebrado. |
| A8 | **Fuzz de borda:** JSON profundo, UTF-8 inválido, NaN/Infinity, cursor, CORS, SSRF/redirect. | ABERTO | "Não vi falha" não é cobertura. |
| A9 | **Contrato dos novos campos do registro V2** (probabilidade bruta/calibrada, incerteza, cobertura, abstenção). | DEPENDE do `SPEC_FORECAST_V2_REGISTRY.md` do Claude A | Migration e ingest só depois do desenho. |
| A10 | **Separar D1 (quente) e Turso (frio)** quando a cota do D1 renovar; mover migrations `database/pending/` de volta. | DEPENDE (conferir a cota do D1 às 21:00 BRT) | Hoje tudo roda no Turso. |
| A11 | **Métricas de operação:** duração do ciclo, latência por collector, taxa de erro, p50/p95 de frescor, abstenções. | ABERTO | Hoje há contadores crus. |
| A12 | **Backpressure documentado:** o que o sistema faz quando entra mais do que processa (o governador cobre escrita, não fila). | ABERTO | Degradação precisa ser conhecida. |

## B. Engine (Claude A / motor)
| # | O que falta | Status |
|---|---|---|
| B1 | **Sentinela barulhenta (RT-003):** dia normal ruidoso abre investigações falsas. Contexto/expectedness e política de investigação. | ABERTO |
| B2 | Cenários adversariais: chuva normal, hora do rush, futebol, show, feriado, queda de API, sensor parado, tempestade de duplicatas, geo ambígua, desmentido oficial. | ABERTO |
| B3 | **Proveniência em escala (RT-008):** curva de 1/5/10/50/100/1000 republicações; false merge/split, resurrection. | ABERTO |
| B4 | Baseline com fallback hierárquico real (município → UF → país) e sazonalidade (precisa de ~3 semanas de histórico). | DEPENDE de dados |
| B5 | Forecast V2 P0–P10 completo (entregues P0–P9 em shadow); falta calibração real e o documento de engenharia final. | EM ANDAMENTO |

## C. Validação (Codex)
| # | O que falta | Status |
|---|---|---|
| C1 | Corpus histórico com positivos e *hard negatives* (hoje: 20 previsões resolvidas, todas negativas). | DEPENDE de dados |
| C2 | `PREDICTIVE_VALIDATION.md`, ablation e calibração fora do tempo. | EM ANDAMENTO |
| C3 | Caos de collectors (redirect loop, 204/304, DNS/TLS, gzip truncado, payload gigante, recuperação após 1 h/24 h offline). | ABERTO |

## D. Dono / decisão humana
| # | O que falta | Status |
|---|---|---|
| D1 | Revisão humana de **279 das 282 fontes ativas** (termos, retenção, exibição). | ABERTO |
| D2 | Chaves de Reddit e X (semana que vem); conta e app password do Bluesky. Depois: "Verificar chaves sociais" → piloto de 48 h → PR. | DEPENDE |
| D3 | Chave do Windy para câmeras; miniaturas do Skyline não são possíveis. | DEPENDE |
| D4 | Decisões em aberto de `ENGINE_V2_PLAN.md` §9. | DEPENDE |
| D5 | Adaptador de resultados do TSE, só depois dos primeiros resultados reais (~17h BRT de 2026-10-04). | DEPENDE de dados reais |

## E. Fora do alcance do backend
Frontend (`apps/web`): PR #18 de `isar` ainda aberto.

## Princípios que não mudam
V2 só vira produção por **sombra → canário → prod**, com 200 amostras resolvidas, ganho de Brier ≥ 5% sobre V1 e baseline. Sem previsão política. Probabilidade nunca vem de LLM. Sem segredo no repositório.
