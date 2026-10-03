# Backend Adversarial QA — 2026-10-03

Autor: `claude-art` (QA independente). Base: `main` em `0530004`. Feito na branch `art`: o `AGENTS.md` proíbe criar branches,
então a `test/backend-adversarial` pedida pelo roteiro não foi criada.

Escopo: só testes novos (`engine/tests/test_adversarial_qa.py`) e este relatório. **Nenhum código de produção, limiar, golden
dataset ou teste existente foi alterado.** Os defeitos de política de pontuação são do motor (`claude-motor`) e ficam
registrados, não corrigidos.

## Como ler

- Teste normal = invariante que vale hoje e não pode regredir.
- `xfail(strict=True)` = defeito reproduzido e aberto. Quando o dono corrigir, o teste passa, o `strict` quebra a suíte e o
  marcador tem de ser removido no mesmo PR da correção.
- Os testes fixam as flags no padrão de produção (V2 desligadas).

## Baseline (antes de qualquer alteração)

| Suíte | Resultado | Duração |
|---|---|---|
| `engine` pytest | 660 passed, 0 skipped, 24 warnings (todas: "conformidade pendente em 279 fontes", COLLECTION_PROTOCOL §4) | 21 s |
| `npm run typecheck` | ok | — |
| `npm test` (web/worker/shared) | 13 arquivos, 136 testes, todos passando | — |
| `npm run build` + `wrangler deploy --dry-run` | ok | ~30 s no total |

Depois desta entrega: engine **679 passed, 13 xfailed** (19 invariantes novas + 13 defeitos documentados).

## Resumo por área

| Área | Status | Nota |
|---|---|---|
| Ruído vs incidente (corpus hostil) | **FAIL** | QA-001, QA-002 |
| Duplicatas / independência | **FAIL** | QA-003, QA-004; cópia da mesma fonte e sindicação OK |
| Eventos: false merge | PASS | mesmo assunto em SP e MG fica separado |
| Eventos: false split | **FAIL** | QA-005 (V2 `CLUSTER_REFINE` melhora: 4 → 2 eventos) |
| Eventos: drift / ressurreição | UNVERIFIED | não exercitado com estado gravado nesta rodada |
| Ordem dos sinais | PASS | 4 ordens diferentes, resultado idêntico |
| Datas ruins | PARTIAL | futuro limitado a "agora", 2019 descartado; sem fuso lido como UTC (QA-007) |
| Entradas ruins (título, XML, corpo) | PARTIAL | vazio/truncado vira OFFLINE (QA-006) |
| `HTTP 200 != fresh` | PASS (HTML) / PARTIAL (vazio) | HTML com 200 é DEGRADED; corpo vazio é OFFLINE |
| API / Worker (entrada hostil) | PASS | ver abaixo |
| Storage / idempotência | UNVERIFIED nesta rodada | segue RT-005 (`BACKEND_TOTAL_RED_TEAM.md`) |
| Forecast (invariantes) | UNVERIFIED nesta rodada | RT-001 tem regressão; skill: INSUFFICIENT_DATA (RT-004) |
| Sentinela | UNVERIFIED nesta rodada | segue RT-003 |

## Defeitos

### QA-001 — volume de veículos sozinho leva ruído a N2 (P1, motor)

- **Ataque:** a mesma manchete de futebol, "onde assistir", show ou feriado publicada por 6 veículos.
- **Resultado:** evento `CONFIRMED`, **N2**, Pulso 30. No painel ao vivo de 2026-10-03 apareceu "Brasil x Índia: onde assistir…" como N2.
- **Reprodução:** `test_noise_does_not_reach_n2_by_outlet_volume`.
- **Causa raiz:**
  - `events.is_publishable` publica todo grupo com 2+ fontes, inclusive categoria `OTHER` sem nenhum termo de impacto.
  - `scoring.pulse.alert_level` dá N2 com `score >= 30`, sem nenhum portão de conteúdo.
  - Diversidade de fontes, velocidade e confiança somam 45% do peso, então volume sozinho chega a 30.
  - `importance.NOISE` não tem termos de esporte, agenda ou serviço ("vence", "onde assistir", "escalação", "o que abre e fecha").
- **Risco:** o painel e os briefings (que mostram N2+) se enchem de ruído agendado. É exatamente o "parece certo, está errado".
- **Sugestão ao dono:** um teto de nível para `OTHER` sem impacto (análogo ao `ROUTINE_SEVERITY_CAP` de campanha) e termos de esporte/serviço em `NOISE`. É política de pontuação: precisa do Reliability Gate, não de ajuste silencioso.

### QA-002 — incidentes operacionais reais ficam N1 (P1, motor)

- **Ataque:** com 4 veículos cada:
  - metrô com circulação interrompida;
  - operadora sem internet/celular;
  - caminhoneiros bloqueando a BR-116;
  - tumulto em show com feridos e evacuação.
- **Resultado:** N1, categoria `OTHER` ou `TRAFFIC`, severidade 27 a 52. Com o mesmo volume, futebol pontua 30 e tumulto com feridos 32: diferença de 2 pontos.
- **Reprodução:** `test_operational_incidents_with_four_outlets_reach_n2` e `test_incident_with_injured_outranks_football_at_equal_volume`.
- **Causa raiz:**
  - O classificador e o `importance` casam substantivos ("bloqueio", "interdicao"), não verbos e particípios ("bloqueiam", "interrompida", "paralisada").
  - Não existe vocabulário de telecom ("sem internet", "sem sinal", "fora do ar").
  - "Feridos" + "evacuado" num show cai em `OTHER`, com base de severidade baixa.
- **Risco:** perda de recall justamente nos incidentes urbanos que o PULSO quer pegar. O filtro de ruído do QA-001 **não** pode ser corrigido sem este, senão o recall cai mais.

### QA-003 — repost social idêntico vira fonte independente e confirma o evento (P1, motor)

- **Ataque:** 1 notícia mais 9 reposts com o título idêntico em 9 contas sociais.
- **Resultado:** `source_count=10`, `CONFIRMED`, severidade 100. Com `CONFIDENCE_V2` ligada, nada muda.
- **Reprodução:** `test_identical_social_reposts_do_not_confirm_a_single_story`.
- **Causa raiz:**
  - `stats_for` conta independência por `source_id` distinto.
  - `status_for` confirma com `independent_sources >= 3` desde que nem todas sejam sociais.
  - O texto idêntico só reduz a confiança via `duplicate_ratio`; não reduz a independência.
- **Invariante violada:** `duplicate volume != independent evidence`.

### QA-004 — cópias da mesma fonte inflam o Pulso (P2, motor)

- **Ataque:** 1000 itens da mesma fonte, mesmo título, URLs diferentes.
- **Resultado:**
  - A independência continua 1 e a confiança cai para 5 (correto).
  - Mas a velocidade conta cópias, e o Pulso sobe de 30 para 45.
- **Reprodução:** `test_duplicate_volume_from_one_outlet_does_not_inflate_pulse`.
- **Causa raiz:** `velocity_per_hour` conta sinais, não títulos distintos nem fontes.

### QA-005 — false split: a mesma história redigida de 4 jeitos vira 4 eventos (P2, motor)

- **Ataque:** 4 veículos noticiam o deslizamento em Petrópolis com redações diferentes.
- **Resultado:** 4 eventos de 1 fonte cada (N1, `DETECTED`) em vez de 1 evento confirmado por 4 fontes. Com a V2 `CLUSTER_REFINE`: 2 eventos (3 + 1).
- **Reprodução:** `test_paraphrased_coverage_of_one_story_is_one_event`.
- **Causa raiz:** o agrupamento V1 é por sobreposição de tokens do título, e paráfrases têm pouca sobreposição.
- **Risco:** o evento real perde a corroboração e fica abaixo do ruído do QA-001.

### QA-006 — corpo vazio ou XML truncado vira OFFLINE (P3, plataforma)

- **Ataque:** resposta vazia; XML cortado no meio.
- **Resultado:** `OFFLINE` ("ParseError"), enquanto HTML com 200 vira `DEGRADED`.
- **Por que importa:** o breaker diz que "só falha de TRANSPORTE conta", mas OFFLINE é tratado como transporte. Um feed com conteúdo quebrado abre o breaker como se a rede tivesse caído. Viola o espírito de `missing != normal` / `HTTP 200 != fresh`, porque mistura dimensões.
- **Reprodução:** `test_empty_body_is_content_problem_not_transport_failure`.

### QA-007 — data sem fuso é lida como UTC (P3, coletor; sem teste)

- **Ataque:** `pubDate` sem fuso ("Fri, 02 Oct 2026 19:30:00").
- **Resultado:** interpretado como 19:30Z. Feeds brasileiros costumam publicar em horário de Brasília, então o sinal fica 3 h "mais velho": perde recência e pode sair da janela antes da hora.
- **Por que não virou teste:** depende da convenção de cada fonte. Registro para o dono do coletor decidir (fuso padrão por fonte em `sources.json`).

## O que resistiu (regressão permanente)

- Ruído de um único veículo nunca vira evento.
- Apagão, evacuação por incêndio e enchente com 4 veículos chegam a N2 `CONFIRMED`.
- 1000 cópias da mesma fonte continuam 1 fonte independente, sem `CONFIRMED`, com confiança ≤ 10.
- A mesma URL repetida (inclusive com `utm_*`) é deduplicada.
- Sindicação (título idêntico) tem confiança menor que cobertura independente.
- O mesmo assunto em SP e MG não é fundido.
- A ordem das fontes não muda nada: mesmo `event_id`, nível, Pulso e contagem.
- Timestamp futuro (inclusive ano 9999) é limitado a "agora".
- Notícia de 2019 republicada não entra no estado.
- Título vazio ou só com espaços é descartado; título de 200 mil caracteres é limitado a 300.
- HTML com HTTP 200 é `DEGRADED`, não `ONLINE`.

## API / Worker

Já coberto pela suíte do Worker (`abuse`, `auth`, `hardening`):
- token errado, ausente, cru ou duplicado;
- fail-closed sem segredo;
- SQL como texto literal;
- corpo acima de 8 MB recusado com 413 antes de ler;
- id/slug absurdo ou com byte nulo dá 404/400;
- erro interno sem stack e com `request_id`.

Sondado nesta rodada na API publicada (só GET público): `limit` = `NaN`, `Infinity`, `-1`, `0`, `1e9`, `999999999999`, `abc` ou `%00`, `state` com SQL e `category` com `<script>`.
- Todos dão **400 `invalid_query`**, nenhum 5xx.
- Parâmetro repetido ou desconhecido é ignorado com segurança.

Status: **PASS**. O rate limit continua dependendo da borda (RT-007).

## Não verificado nesta rodada

- Ressurreição de evento encerrado e drift.
- Storage: retry, resposta perdida e lote parcial.
- Invariantes de forecast.
- Volume diário da Sentinela.

Já têm itens abertos no `BACKEND_TOTAL_RED_TEAM.md` (RT-001/003/004/005); não foram retestados aqui. Nada nesta entrega declara o
sistema pronto para produção.

## Handoff

- `claude-motor`: QA-001, QA-002, QA-003, QA-004, QA-005. Corrigir QA-001 junto com QA-002, ou o recall cai.
- `claude-hen`: QA-006.
- Dono dos coletores: QA-007.
