# Maturidade da plataforma e das operações (campanha CLAUDE B)

> Estado em 2026-10-04. Metodologia: um subsistema só passa de **7,5** com implementação funcionando + testes + testes de falha/adversariais + falha segura + observabilidade + caminho de recuperação + documentação + nenhum P0/P1 conhecido sem mitigação (CI verde sozinho não conta). **HARNESS_VERIFIED** = provado contra um servidor/banco local de teste; **PRODUCTION_VERIFIED** = observado na produção real. Nada abaixo é PRODUCTION_VERIFIED, a menos que dito. Divisão desta campanha: o lado **Engine** da plataforma (coletores, saúde/frescor, conformidade, documentos) foi feito aqui; Worker, Turso/D1, auth/admin, rate limit, CI e deploy são da `claude-hen` e **não foram reavaliados por mim**: constam como "não pontuado aqui" com a referência ao relatório vigente (`docs/reliability/BACKEND_TOTAL_RED_TEAM.md`).

## 1. Placar (o que eu pude comprovar)
| Subsistema | Nota | ≥7,5? | Por quê (evidência) | O que falta para 7,5 |
|---|---|---|---|---|
| **Transporte dos coletores** (RSS) | **7,0** | não | 37 testes de caos contra servidor HTTP local real (`engine/tests/chaos`): 200 fresh/stale/vazio, 204, 301/302, loop de redirect, 304, 403/404/408/429/500/502/503/504, DNS, conexão recusada, TLS errado, reset, timeout, corpo truncado, gzip inválido, bomba de descompressão, UTF-8 inválido, Latin-1, XML malformado, JSON/HTML no lugar de XML, esquema alterado, payload gigante, gotejamento (slow-loris). Invariantes: nunca levanta, nunca FRESH quando falhou, falha de transporte ⇒ frescor UNKNOWN, tempo limitado, uma fonte quebrada não derruba as outras. HARNESS_VERIFIED. | o circuit breaker (`circuit_breaker.py`, testado) **não está ligado** ao ciclo (precisa de estado entre ciclos) e `Retry-After` não é lido do cabeçalho; só RSS foi exercitado (os coletores oficiais têm testes próprios, fora desta matriz); nada PRODUCTION_VERIFIED |
| **Saúde/frescor por fonte** (RT-002) | **6,5** | não | `source_freshness.py` separa **transporte / frescor do conteúdo / qualidade (parse, contagens) / cobertura / evidência**; HTTP 200 com item velho = STALE; 200 com conteúdo repetido = STALE; vazio = EMPTY (ou QUIET em fonte de limiar); transporte falho = UNKNOWN (nunca zero); item sem data não infla o frescor; transições fresh→stale→fresh e offline→recuperação testadas; cobertura por família e p50/p95/máx. Roda em SHADOW no ciclo (`flag SOURCE_FRESHNESS`, só log). | **não persiste nem aparece na API/`engine-status`** (depende do Worker, handoff abaixo); sem série histórica; limiares `stale_after_min` são hipóteses |
| **Conformidade das fontes** | **4,0** | não | mecanismo pronto (`compliance.py`, validação em `config.py`, relatório `COMPLIANCE_REPORT.md`, planilha `REVIEW_WORKSHEET.csv`); **282 ativas: 0 APPROVED, 282 PENDING** (3 revisadas por pessoa sem decisão explícita). Nada é aprovado por script. | revisão humana (**BLOCKED_EXTERNAL**: 238 domínios) |
| **Higiene de segredos** | **6,5** | não | varredura por padrões (chave privada, AWS, tokens GitHub/Slack, Bearer literal, JWT, URL Turso com token) sobre todos os arquivos versionados: **0 achados**. Sem segredo impresso. | não varre o histórico do git nem roda como gate de CI; padrões não provam ausência |
| **Dependências** | **6,0** | não | `npm audit`: **2 moderadas, ambas só de desenvolvimento** (`vitest` direto, `@vitest/mocker` transitivo; "path traversal via mock redirect"; correção por atualização MAJOR para vitest 5.0.3, não aplicada às cegas). Python: `pip-audit` **não instalado** ⇒ UNKNOWN. Nenhuma vulnerabilidade de runtime reportada. | atualizar vitest em PR próprio com testes; rodar auditoria Python no CI |
| **SLO/SLI** | **5,0** | não | `docs/operations/SLO.md`: 10 SLIs, metas iniciais, cada um marcado MEDIDO/PARCIAL/NÃO MEDIDO | série histórica e latência não existem |
| **Runbook de falhas** | **6,5** | não | `docs/operations/FAILURE_RUNBOOK.md` (9 cenários; mapa de estados). Ensaiado apenas no que o harness cobre | nenhum cenário foi exercitado em produção |
| **Retenção** | **5,0** | não | política por classe abaixo; aplicação no banco declarada pelo código do Worker, **não verificada por mim** | verificar a limpeza no banco real |
| Worker/API/auth/admin/rate limit, Turso/D1, idempotência, migrations, CI/deploy | **não pontuado aqui** | — | pertencem à plataforma-Worker (`claude-hen`); estado conforme `BACKEND_TOTAL_RED_TEAM.md`: ingest/storage PARTIAL, API/security MODERATE no código e PARTIAL na borda, observabilidade WEAK; RT-005 residual (D1/Turso remotos, `write_budget`) e RT-007 (segredo admin, WAF) abertos | — |

**Nenhum subsistema que eu avaliei chegou a 7,5.** Os que chegaram mais perto (coletores 7,0; frescor 6,5) dependem de integração que não é minha para fechar (persistência no Worker, estado do breaker entre ciclos).

## 2. Achados novos desta campanha
| # | Achado | Sev. | Estado |
|---|---|---|---|
| F-1 | Item de feed **sem data válida entra com `timestamp` = instante da coleta** (comportamento antigo do coletor RSS); aparece como notícia de "agora" na 1ª leitura | P2 | **mitigado só na saúde** (a fonte não parece FRESH por causa disso); o sinal em si continua entrando; mudar a regra altera eventos: decisão do dono/Engine |
| F-2 | Leitura sem prazo total: um servidor que goteja bytes prendia a thread (timeout é por operação) | P1 | **corrigido** (`FETCH_DEADLINE_S` + leitura incremental `read1`); coberto por `drip` |
| F-3 | `Retry-After` de 429 não é lido (a fonte volta a ser tentada no próximo ciclo de 5 min) | P2 | aberto: o breaker aceita `retry_after_s`, falta o transporte expor o cabeçalho e o estado persistir |
| F-4 | HTTP 304 sem requisição condicional é tratado como OFFLINE | P3 | aceito (não enviamos `If-None-Match`; 304 inesperado é falha) |
| F-5 | 100% das fontes ativas com conformidade PENDING | P1 (compliance) | **BLOCKED_EXTERNAL** (revisão humana) |
| F-6 | `vitest` com 2 vulnerabilidades moderadas (dev-only) | P3 | aberto: upgrade major em PR próprio |

## 3. Retenção (política proposta: coletar muito, guardar pouco, agregar sempre, preservar o importante)
| Classe | Política | Observação |
|---|---|---|
| Bruto do feed (conteúdo de terceiros) | **não guardado** além do sinal normalizado; título + link com atribuição | `display: headline_link` |
| Sinais (`signals`) | 90 dias (`retention_days` por fonte) | só o estritamente necessário |
| Séries e observações agregadas (`series`, `signal_observations`) | observações 90 dias; séries mais longas (só contagens) | agregação sempre preferida |
| Eventos / Pulso (`events`, `pulse_history`) | o histórico útil para baseline/backtest é preservado | |
| Investigações | 30 dias após fechadas | |
| Previsões e registro (`forecasts`, `forecast_registry`, `shadow_results`) | previsões preservadas (base do Brier); registro 180 dias; shadow 90 | imutáveis |
| Saúde de fonte | só o estado atual + detalhe curto; sem série por item | evita cardinalidade |
Aplicação: declarada nas migrations/rotas do Worker; **não verificada em produção** nesta campanha.

## 4. Handoffs
**FROM: CLAUDE-B (engine) → TO: CLAUDE-A (motor)** — contrato de saúde de sensor
- COMMIT: ver PR desta campanha. Testes: `tests/test_source_freshness.py`, `tests/test_pipeline_freshness.py`, `tests/chaos/`.
- CAMPOS (por fonte, `batch["source_freshness"]`): `transport`, `freshness.state` ∈ {FRESH, STALE, EMPTY, QUIET, UNKNOWN}, `freshness.newest_item_age_min`, `freshness.stale_after_min`, `freshness.last_content_advance`, `freshness.content_hash`, `quality.{parse_ok, records, new_records, duplicate_records}`.
- SEMÂNTICA: **UNKNOWN ≠ 0**: sensor fora do ar não é "sem ocorrências"; **STALE ≠ ausente**: existe mas parou; **QUIET** é silêncio legítimo de fonte de limiar; **EMPTY** não é normal. Para `forecast_v2_features`: UNKNOWN/STALE ⇒ `STALE`/`UNAVAILABLE` em `sensor_coverage`; QUIET ⇒ `VALUE_ZERO`.
- COBERTURA: `source_freshness.coverage()` devolve `ready_ratio` por família; usar como `coverage` do snapshot quando fizer sentido.
- Custo/valor por fonte: `new_records` e `duplicate_records` por ciclo são a base de "sinais únicos/fonte/dia" (agregar fora do ciclo; não remover fonte por custo automaticamente).

**FROM: CLAUDE-B (engine) → TO: claude-hen (Worker)** — pedido
- COMPONENT: persistir e expor frescor. DEPENDENCY: campo opcional `source_freshness` no lote (array pequeno, 1 linha por fonte ativa: `source_id, freshness_state, newest_item_age_min, last_content_advance, records, new_records, duplicate_records`), escrita **condicional** (só quando o estado muda ou a cada 6 h), exposto em `engine-status` como `freshness{FRESH,STALE,EMPTY,QUIET,UNKNOWN,p50,p95,max}` por classe. EXPECTED CONTRACT: aditivo; Worker antigo ignora.
- COMPONENT: estado do circuit breaker entre ciclos: 4 colunas em `source_health` (`breaker_state`, `consecutive_failures`, `next_attempt_at`, `opened_count`) lidas no início do ciclo.
- COMPONENT: log de auditoria do admin (route, role, status, request_id; sem token).

**FROM: CLAUDE-B (engine) → TO: CODEX** — por favor ataque
| Componente | Propriedade afirmada | Teste de falha | Atacar |
|---|---|---|---|
| `source_freshness.assess` | HTTP 200 nunca é FRESH com item velho/repetido/sem data; falha de transporte nunca vira zero | `tests/test_source_freshness.py`, `tests/test_pipeline_freshness.py` | feeds com datas futuras, fuso errado, `pubDate` fixo, item novo com data antiga reinserido |
| Coletor RSS | nenhuma falha de rede/conteúdo derruba o ciclo; leitura com prazo total | `tests/chaos/test_collector_chaos.py` | coletores oficiais (INMET, IDAP, INPE...) fora da matriz; HTTP/2, chunked inválido, redirect cross-host |
| `compliance` | nunca APPROVED sem evidência humana | `tests/test_compliance.py` | editar `sources.json` com APPROVED forjado e ver se `config`/`--check` recusam |
| `circuit_breaker` | não insiste, respeita Retry-After, backoff limitado | `tests/test_circuit_breaker.py` | integração (ainda não ligado) |

## 5. BLOCKED_EXTERNAL e desconhecidos restantes
- **BLOCKED_EXTERNAL:** revisão humana das fontes (F-5); criar `ADMIN_TOKEN` e regra de rate limit/WAF na Cloudflare (dono); validação em Turso/D1 remotos (credenciais); renovar `GH_DISPATCH_TOKEN` (vence 31/12/2026).
- **Desconhecido:** latência real da API e série histórica de disponibilidade; custo e bytes por fonte/dia (não medidos); desempenho com 100–100k observações (sem benchmark: não publicar números); auditoria de dependências Python; histórico do git não varrido por segredos.
- **Princípio:** *um sistema só é confiável se percebe quando a própria visão do mundo está degradada*: o ganho desta campanha é o PULSO distinguir "a fonte falou e nada mudou", "a fonte calou" e "não sei", em vez de tratar os três como calmaria.
