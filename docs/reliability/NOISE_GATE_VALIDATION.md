# NOISE_GATE — QA closure e validação OFF × ON — 2026-10-03

Autor: `claude-art`. Base: `origin/main` em `d85edd4`, já contida na `art` (o `AGENTS.md` proíbe trabalhar na `main` e criar
branches; a entrega vai no PR da `art`). **A flag `NOISE_GATE` continua DESLIGADA por padrão.** Nada aqui a liga.

Reproduzir: `cd engine && py -m pulso_engine.validation.noise_gate_corpus` (tabela abaixo, ~1 min) e
`py -m pytest tests/test_noise_gate_validation.py` (invariantes, ~30 s).

## Veredito

**READY_FOR_EXTENDED_SHADOW.** Não é `CANDIDATE_FOR_PROMOTION`.

- No corpus, o gate reduz o ruído sem cegar o PULSO: hard negatives com N2+ caem de **95 para 0** (50/50 cenários), e o recall
  dos positivos **sobe** de 16/21 para 20/21. Nenhum positivo que passa com a flag desligada falha com ela ligada. As
  investigações do Sentinela são idênticas nos dois modos (o gate atua em eventos, não em sinais).
- Por que não é candidato a promoção:
  1. **O corpus é sintético e foi usado para ajustar o próprio gate.** Três termos de rotina e quatro operacionais foram
     acrescentados depois de falhas NESTE corpus (ver "Correções"). PASS aqui é avaliação dentro da amostra de treino.
  2. **Não há dado real de shadow.** Com a flag desligada, o gate nem é calculado: "shadow" hoje quer dizer "código atrás de
     flag", não "decisão registrada em produção e comparada depois". Não existe nenhuma medição do gate em tráfego real.
  3. Achados fora do gate seguem abertos e afetam as mesmas métricas (QA-010, QA-011).
- Para virar candidato: registrar, com a flag desligada, o que o gate faria em cada evento real (nível antes/depois, motivo)
  por ≥ 7 dias e revisar à mão uma amostra dos rebaixados (falso negativo?) e dos publicados pelo termo operacional (falso
  positivo?). Critério sugerido: 0 incidentes reais rebaixados de N2+ na amostra revisada.

## 1. Baseline (antes desta rodada)

`engine`: **756 passed, 11 xfailed**, 0 failed, 0 xpassed. Os 11 xfails (`tests/test_adversarial_qa.py`):

| Teste | Achado |
|---|---|
| `test_noise_does_not_reach_n2_by_outlet_volume[futebol]` | QA-001 |
| `test_noise_does_not_reach_n2_by_outlet_volume[feriado]` | QA-001 |
| `test_operational_incidents_with_four_outlets_reach_n2[metro]` | QA-002 |
| `test_operational_incidents_with_four_outlets_reach_n2[telecom]` | QA-002 |
| `test_operational_incidents_with_four_outlets_reach_n2[bloqueio]` | QA-002 |
| `test_operational_incidents_with_four_outlets_reach_n2[tumulto_show]` | QA-002 |
| `test_incident_with_injured_outranks_football_at_equal_volume` | QA-001/002 |
| `test_identical_social_reposts_do_not_confirm_a_single_story` | QA-003 |
| `test_duplicate_volume_from_one_outlet_does_not_inflate_pulse` | QA-004 |
| `test_paraphrased_coverage_of_one_story_is_one_event` | QA-005 |
| `test_empty_body_is_content_problem_not_transport_failure` | QA-006 |

Depois desta rodada: **853 passed, 13 xfailed**, 0 failed, 0 xpassed.

## 2. Fechamento dos xfail

| Achado | Causa-raiz | Dono | Resultado |
|---|---|---|---|
| QA-001..004 | ruído/independência no motor (`events.py`, `importance.py`) | motor | **continuam xfail no modo padrão, por decisão.** A correção existe atrás do `NOISE_GATE`, e os mesmos ataques passam com a flag ligada (`test_gate_*`). Fazer o xfail passar exigiria ligar a flag, o que esta tarefa proíbe. |
| QA-005 | false split: agrupamento V1 só por título exige 3 tokens em comum; as 4 paráfrases de Petrópolis dividem 2. Na V2 `CLUSTER_REFINE`, o título em dateline ("Petrópolis: ...") perdia a primeira palavra, que era o lugar, e ficava sem entidade (4 → 2 eventos). | motor (clustering) | **corrigido na V2** (`cluster_refine.entities` mantém o lugar do dateline): com `CLUSTER_REFINE` vira 1 evento com 4 fontes. Guardas novas: mesma história em outra cidade não funde; outro incidente na mesma cidade não funde. O V1 de produção não foi mexido (baixar o limiar global causaria false merge), então o xfail segue no modo padrão. |
| QA-006 | qualquer exceção do coletor virava OFFLINE, inclusive `ParseError` de corpo vazio/XML quebrado com transporte ok. Achado colateral: `read1` devolve `b""` quando a conexão fecha antes do `Content-Length`, e o corte de transporte chegava ao parser como "XML quebrado" (OFFLINE só por acaso). | plataforma (coletor RSS) | **corrigido.** `FeedContentError` (DEGRADED; o breaker não abre) para vazio/ilegível; `_read_bounded` levanta `ConnectionError` no corte. Matriz de caos: 204, `malformed`, `json-not-xml` → DEGRADED/EMPTY; `truncated` segue OFFLINE. **xfail virou teste normal** (+ XML quebrado, lixo binário, rede caída continua OFFLINE). |

Nenhum teste foi removido, nenhuma asserção enfraquecida, nenhum limiar global alterado, nenhum corpus mudado para passar.
A única expectativa alterada foi a matriz de caos (204/malformed/json-not-xml), porque ela registrava o comportamento antigo
sem justificativa documentada e contradizia o comentário do circuit breaker ("conteúdo vazio com transporte ok NÃO abre o breaker").

## 3–8. Resultado por grupo (mesmo corpus, flag desligada × ligada)

| Grupo | Cenários | PASS OFF | PASS ON | eventos N2+ OFF → ON | eventos OFF → ON | investigações OFF → ON |
|---|---|---|---|---|---|---|
| Hard negatives (10 casos × 10/50/100/500/1000) | 50 | 11 | **50** | 95 → **0** | 117 → 117 | 15 → 15 |
| Positive controls (10 casos × 4/12 + 1 sob ruído) | 21 | 16 | **20** | 20 → 23 | 28 → 31 | 20 → 20 |
| Provenance cascade | 2 | 0 | 0 | 2 → 2 | 2 → 2 | 8 → 8 |
| Event integrity | 6 | 5 | 5 | 5 → 5 | 12 → 12 | 10 → 10 |
| Contradição + sensor velho | 7 | 5 | 5 | 7 → 7 | 8 → 8 | 6 → 6 |

- **Editorial promotion**: o gate **não esconde** o evento de ruído, só põe teto em N1 (Normal); a contagem de eventos não
  muda (117). O que some é a promoção para N2+ (Atenção). "Onde assistir" nem vira evento (PR #89, já em produção).
- **Duplicate inflation / independent origins**: ver §6.
- **Sentinela**: idêntico nos dois modos. Hard negatives abrem 15 investigações (trânsito de pico 2, chuva 1, apostas 1 por
  volume), e o gate não as cobre (QA-014, shadow).
- **Incident recall**: 16/21 → 20/21. O gate recupera "evacuação em show" e "bloqueio de rodovia" com 4 veículos (QA-002) e
  "pane nos trens após show", que em produção some inteiro (QA-012). O único positivo que falha nos dois modos é QA-010.

### 6. Proveniência: 1 origem oficial → 5 publishers (paráfrase) → 50 sites (cópia + sufixo) → 1000 reposts

| Métrica | sem reposts OFF / ON | com 1000 reposts OFF / ON |
|---|---|---|
| sinais | 56 / 56 | 1056 / 1056 |
| duplicate_count (mesma fonte + título) | 0 / 0 | 400 / 400 |
| publisher_count (não sociais) | 56 / 56 | 56 / 56 |
| origin_count (grupos de quase-cópia) | 6 / 6 | 6 / 6 |
| independent_origin_count | 6 / 6 | 6 / 6 |
| sensor_family_count | 3 / 3 | 4 / 4 |
| **fontes independentes do evento** | 56 / 56 | **256 / 56** |
| confiança | 94 / 94 | 81 / 81 |

1000 cópias não são 1000 confirmações: com o gate, os reposts sociais (literais, "URGENTE:", "RT") somam **0** fontes
(antes 200). Mas o evento ainda conta **publishers, não origens**: 56 fontes para 6 origens (QA-011). A regra certa já existe
(`confidence_v2`, `_origins`), mas a flag `CONFIDENCE_V2` está declarada e **não está ligada a nada** no pipeline. Trocar
publisher por origem dentro do gate derrubaria o recall dos positivos com manchete idêntica em 4 veículos (sindicação de
agência é indistinguível de cobertura independente só pelo título); por isso não foi feito aqui.

### 8. Cobertura (5 sensores: oficial, 2 jornais, trânsito, social; derrubados do menos ao mais confiável)

| Cobertura | 100 | 80 | 60 | 40 | 20 | 0 |
|---|---|---|---|---|---|---|
| confiança (OFF e ON, idênticas) | 84 | 67 | 48 | 48 | 48 | — (sem evento) |
| nível | N2 | N2 | N2 | N2 | N2 | — |

Menor observabilidade nunca aumentou a confiança. Com 0% de cobertura não sai evento nem "normal" inventado.

## Correções desta rodada (todas atrás de flag desligada, exceto QA-006 e o validador do Sentinela)

| Onde | O quê | Por quê |
|---|---|---|
| `collectors/news/rss.py` | `FeedContentError` (DEGRADED); `ConnectionError` em corte de `Content-Length` | QA-006 |
| `processing/cluster_refine.py` | dateline mantém o lugar como entidade (só `CLUSTER_REFINE`) | QA-005 |
| `importance.GATE_SCHEDULED` | + "chuva fraca", "chuva leve", "garoa", "tempo nublado", "tempo instável", "trânsito lento", "trânsito intenso", "lentidão", "horário de pico" | NORMAL_RAIN/RUSH_HOUR chegavam a N2 com o gate ligado |
| `importance.GATE_OPERATIONAL` | + "sem transporte", "estação fechada", "trens param", "ficam presos" | CONCERT_TRANSPORT_FAILURE |
| `events.is_publishable` | com o gate, termo operacional publica mesmo em pauta de agenda | QA-012 |
| `events.stats_for` | com o gate, repost social é quase-cópia (Jaccard ≥ 0,8), não título idêntico | cascata: "URGENTE:"/"RT" somavam +10 fontes |
| `research/validator.py` | `claim_side`: a negação tem precedência ("não deixou feridos"); "apagão" nomeia o evento, não afirma estado | negação oficial era lida como confirmação; afeta o Sentinela (SHADOW) |
| `events.py` + flag `EVENT_CONTRADICTION` (OFF) | contradição no evento: DISPUTED + desconto de confiança; desfecho posterior não é disputa | QA-013 |

## Achados novos

| Id | Sev. | Dono | Achado | Estado |
|---|---|---|---|---|
| QA-010 | P2 | motor (classificador/cluster) | "Briga entre torcidas deixa feridos" em 4 paráfrases vira 3 eventos N1: categorias divergem (OTHER/SECURITY/HEALTH) e o refino veta categoria diferente | aberto, `xfail` strict |
| QA-011 | P2 | motor | independência do evento conta publisher, não origem (56 para 6); `CONFIDENCE_V2` declarada e não ligada | aberto, `xfail` strict |
| QA-012 | **P1** | motor | em produção, "pane nos trens após show" some inteiro: o papel de agenda do PR #89 descarta o cluster antes do score | corrigido só com `NOISE_GATE`; `xfail` strict no modo padrão |
| QA-013 | P2 | motor/plataforma | o pipeline nunca passa `contradiction` ao evento e `status_for` não tem caminho para DISPUTED; negação oficial confirmava | corrigido atrás de `EVENT_CONTRADICTION` (OFF) |
| QA-014 | P3 | motor (Sentinela) | volume de rotina (pico, chuva fraca, apostas) abre investigação; o gate não cobre o Sentinela | aberto (shadow, não muda nada visível) |

O QA-012 é o argumento mais forte para avançar o gate: hoje há um falso negativo em produção que só o gate fecha.

## Tabela completa (gerada)

`ev` eventos · `N2+` eventos de nível ≥ 2 · `top` maior nível · status · `conf` maior confiança · `fontes` maior
`source_count` · `inv` investigações do Sentinela abertas. "+FLAG" no nome: flag extra ligada nos DOIS modos.

| Cenário | OFF | ON | Esperado | OFF | ON | Risco de regressão |
|---|---|---|---|---|---|---|
| `SPORTS_NEWS_BURST@10` | ev 1 · N2+ 1 · top N2 · CONFIRMED · conf 42 · fontes 8 · inv 0 | ev 1 · N2+ 0 · top N1 · CONFIRMED · conf 42 · fontes 8 · inv 0 | nenhum evento N2+ | FAIL | PASS | baixo: o teto só vale se TODOS os relatos são agenda/rotina; um termo de impacto anula |
| `SPORTS_NEWS_BURST@50` | ev 1 · N2+ 1 · top N2 · CONFIRMED · conf 37 · fontes 28 · inv 0 | ev 1 · N2+ 0 · top N1 · CONFIRMED · conf 37 · fontes 28 · inv 0 | nenhum evento N2+ | FAIL | PASS | baixo: o teto só vale se TODOS os relatos são agenda/rotina; um termo de impacto anula |
| `SPORTS_NEWS_BURST@100` | ev 1 · N2+ 1 · top N2 · CONFIRMED · conf 36 · fontes 30 · inv 0 | ev 1 · N2+ 0 · top N1 · CONFIRMED · conf 36 · fontes 30 · inv 0 | nenhum evento N2+ | FAIL | PASS | baixo: o teto só vale se TODOS os relatos são agenda/rotina; um termo de impacto anula |
| `SPORTS_NEWS_BURST@500` | ev 1 · N2+ 1 · top N2 · CONFIRMED · conf 35 · fontes 30 · inv 0 | ev 1 · N2+ 0 · top N1 · CONFIRMED · conf 35 · fontes 30 · inv 0 | nenhum evento N2+ | FAIL | PASS | baixo: o teto só vale se TODOS os relatos são agenda/rotina; um termo de impacto anula |
| `SPORTS_NEWS_BURST@1000` | ev 1 · N2+ 1 · top N2 · CONFIRMED · conf 35 · fontes 30 · inv 0 | ev 1 · N2+ 0 · top N1 · CONFIRMED · conf 35 · fontes 30 · inv 0 | nenhum evento N2+ | FAIL | PASS | baixo: o teto só vale se TODOS os relatos são agenda/rotina; um termo de impacto anula |
| `BETTING_NEWS_BURST@10` | ev 1 · N2+ 0 · top N1 · DEVELOPING · conf 25 · fontes 2 · inv 1 | ev 1 · N2+ 0 · top N1 · DEVELOPING · conf 25 · fontes 2 · inv 1 | nenhum evento N2+ | PASS | PASS | baixo: o teto só vale se TODOS os relatos são agenda/rotina; um termo de impacto anula |
| `BETTING_NEWS_BURST@50` | ev 1 · N2+ 1 · top N2 · CONFIRMED · conf 37 · fontes 10 · inv 1 | ev 1 · N2+ 0 · top N1 · CONFIRMED · conf 37 · fontes 10 · inv 1 | nenhum evento N2+ | FAIL | PASS | baixo: o teto só vale se TODOS os relatos são agenda/rotina; um termo de impacto anula |
| `BETTING_NEWS_BURST@100` | ev 1 · N2+ 1 · top N2 · CONFIRMED · conf 36 · fontes 10 · inv 1 | ev 1 · N2+ 0 · top N1 · CONFIRMED · conf 36 · fontes 10 · inv 1 | nenhum evento N2+ | FAIL | PASS | baixo: o teto só vale se TODOS os relatos são agenda/rotina; um termo de impacto anula |
| `BETTING_NEWS_BURST@500` | ev 1 · N2+ 1 · top N2 · CONFIRMED · conf 35 · fontes 10 · inv 1 | ev 1 · N2+ 0 · top N1 · CONFIRMED · conf 35 · fontes 10 · inv 1 | nenhum evento N2+ | FAIL | PASS | baixo: o teto só vale se TODOS os relatos são agenda/rotina; um termo de impacto anula |
| `BETTING_NEWS_BURST@1000` | ev 1 · N2+ 1 · top N2 · CONFIRMED · conf 35 · fontes 10 · inv 1 | ev 1 · N2+ 0 · top N1 · CONFIRMED · conf 35 · fontes 10 · inv 1 | nenhum evento N2+ | FAIL | PASS | baixo: o teto só vale se TODOS os relatos são agenda/rotina; um termo de impacto anula |
| `TRANSFER_MARKET@10` | ev 3 · N2+ 1 · top N2 · CONFIRMED/DEVELOPING · conf 43 · fontes 5 · inv 0 | ev 3 · N2+ 0 · top N1 · CONFIRMED/DEVELOPING · conf 43 · fontes 5 · inv 0 | nenhum evento N2+ | FAIL | PASS | baixo: o teto só vale se TODOS os relatos são agenda/rotina; um termo de impacto anula |
| `TRANSFER_MARKET@50` | ev 3 · N2+ 3 · top N2 · CONFIRMED · conf 37 · fontes 20 · inv 0 | ev 3 · N2+ 0 · top N1 · CONFIRMED · conf 37 · fontes 20 · inv 0 | nenhum evento N2+ | FAIL | PASS | baixo: o teto só vale se TODOS os relatos são agenda/rotina; um termo de impacto anula |
| `TRANSFER_MARKET@100` | ev 3 · N2+ 3 · top N2 · CONFIRMED · conf 36 · fontes 20 · inv 0 | ev 3 · N2+ 0 · top N1 · CONFIRMED · conf 36 · fontes 20 · inv 0 | nenhum evento N2+ | FAIL | PASS | baixo: o teto só vale se TODOS os relatos são agenda/rotina; um termo de impacto anula |
| `TRANSFER_MARKET@500` | ev 3 · N2+ 3 · top N2 · CONFIRMED · conf 35 · fontes 20 · inv 0 | ev 3 · N2+ 0 · top N1 · CONFIRMED · conf 35 · fontes 20 · inv 0 | nenhum evento N2+ | FAIL | PASS | baixo: o teto só vale se TODOS os relatos são agenda/rotina; um termo de impacto anula |
| `TRANSFER_MARKET@1000` | ev 3 · N2+ 3 · top N2 · CONFIRMED · conf 35 · fontes 20 · inv 0 | ev 3 · N2+ 0 · top N1 · CONFIRMED · conf 35 · fontes 20 · inv 0 | nenhum evento N2+ | FAIL | PASS | baixo: o teto só vale se TODOS os relatos são agenda/rotina; um termo de impacto anula |
| `WHERE_TO_WATCH@10` | ev 0 · N2+ 0 · top N0 · - · conf 0 · fontes 0 · inv 0 | ev 0 · N2+ 0 · top N0 · - · conf 0 · fontes 0 · inv 0 | nenhum evento N2+ | PASS | PASS | baixo: o teto só vale se TODOS os relatos são agenda/rotina; um termo de impacto anula |
| `WHERE_TO_WATCH@50` | ev 0 · N2+ 0 · top N0 · - · conf 0 · fontes 0 · inv 0 | ev 0 · N2+ 0 · top N0 · - · conf 0 · fontes 0 · inv 0 | nenhum evento N2+ | PASS | PASS | baixo: o teto só vale se TODOS os relatos são agenda/rotina; um termo de impacto anula |
| `WHERE_TO_WATCH@100` | ev 0 · N2+ 0 · top N0 · - · conf 0 · fontes 0 · inv 0 | ev 0 · N2+ 0 · top N0 · - · conf 0 · fontes 0 · inv 0 | nenhum evento N2+ | PASS | PASS | baixo: o teto só vale se TODOS os relatos são agenda/rotina; um termo de impacto anula |
| `WHERE_TO_WATCH@500` | ev 0 · N2+ 0 · top N0 · - · conf 0 · fontes 0 · inv 0 | ev 0 · N2+ 0 · top N0 · - · conf 0 · fontes 0 · inv 0 | nenhum evento N2+ | PASS | PASS | baixo: o teto só vale se TODOS os relatos são agenda/rotina; um termo de impacto anula |
| `WHERE_TO_WATCH@1000` | ev 0 · N2+ 0 · top N0 · - · conf 0 · fontes 0 · inv 0 | ev 0 · N2+ 0 · top N0 · - · conf 0 · fontes 0 · inv 0 | nenhum evento N2+ | PASS | PASS | baixo: o teto só vale se TODOS os relatos são agenda/rotina; um termo de impacto anula |
| `CONCERT_NORMAL@10` | ev 1 · N2+ 0 · top N1 · DEVELOPING · conf 25 · fontes 2 · inv 0 | ev 1 · N2+ 0 · top N1 · DEVELOPING · conf 25 · fontes 2 · inv 0 | nenhum evento N2+ | PASS | PASS | baixo: o teto só vale se TODOS os relatos são agenda/rotina; um termo de impacto anula |
| `CONCERT_NORMAL@50` | ev 1 · N2+ 1 · top N2 · CONFIRMED · conf 37 · fontes 10 · inv 0 | ev 1 · N2+ 0 · top N1 · CONFIRMED · conf 37 · fontes 10 · inv 0 | nenhum evento N2+ | FAIL | PASS | baixo: o teto só vale se TODOS os relatos são agenda/rotina; um termo de impacto anula |
| `CONCERT_NORMAL@100` | ev 1 · N2+ 1 · top N2 · CONFIRMED · conf 36 · fontes 10 · inv 0 | ev 1 · N2+ 0 · top N1 · CONFIRMED · conf 36 · fontes 10 · inv 0 | nenhum evento N2+ | FAIL | PASS | baixo: o teto só vale se TODOS os relatos são agenda/rotina; um termo de impacto anula |
| `CONCERT_NORMAL@500` | ev 1 · N2+ 1 · top N2 · CONFIRMED · conf 35 · fontes 10 · inv 0 | ev 1 · N2+ 0 · top N1 · CONFIRMED · conf 35 · fontes 10 · inv 0 | nenhum evento N2+ | FAIL | PASS | baixo: o teto só vale se TODOS os relatos são agenda/rotina; um termo de impacto anula |
| `CONCERT_NORMAL@1000` | ev 1 · N2+ 1 · top N2 · CONFIRMED · conf 35 · fontes 10 · inv 0 | ev 1 · N2+ 0 · top N1 · CONFIRMED · conf 35 · fontes 10 · inv 0 | nenhum evento N2+ | FAIL | PASS | baixo: o teto só vale se TODOS os relatos são agenda/rotina; um termo de impacto anula |
| `TV_EVENT@10` | ev 3 · N2+ 0 · top N1 · CONFIRMED/DEVELOPING · conf 32 · fontes 3 · inv 0 | ev 3 · N2+ 0 · top N1 · CONFIRMED/DEVELOPING · conf 32 · fontes 3 · inv 0 | nenhum evento N2+ | PASS | PASS | baixo: o teto só vale se TODOS os relatos são agenda/rotina; um termo de impacto anula |
| `TV_EVENT@50` | ev 3 · N2+ 3 · top N2 · CONFIRMED · conf 37 · fontes 10 · inv 0 | ev 3 · N2+ 0 · top N1 · CONFIRMED · conf 37 · fontes 10 · inv 0 | nenhum evento N2+ | FAIL | PASS | baixo: o teto só vale se TODOS os relatos são agenda/rotina; um termo de impacto anula |
| `TV_EVENT@100` | ev 3 · N2+ 3 · top N2 · CONFIRMED · conf 36 · fontes 10 · inv 0 | ev 3 · N2+ 0 · top N1 · CONFIRMED · conf 36 · fontes 10 · inv 0 | nenhum evento N2+ | FAIL | PASS | baixo: o teto só vale se TODOS os relatos são agenda/rotina; um termo de impacto anula |
| `TV_EVENT@500` | ev 3 · N2+ 3 · top N2 · CONFIRMED · conf 35 · fontes 10 · inv 0 | ev 3 · N2+ 0 · top N1 · CONFIRMED · conf 35 · fontes 10 · inv 0 | nenhum evento N2+ | FAIL | PASS | baixo: o teto só vale se TODOS os relatos são agenda/rotina; um termo de impacto anula |
| `TV_EVENT@1000` | ev 3 · N2+ 3 · top N2 · CONFIRMED · conf 35 · fontes 10 · inv 0 | ev 3 · N2+ 0 · top N1 · CONFIRMED · conf 35 · fontes 10 · inv 0 | nenhum evento N2+ | FAIL | PASS | baixo: o teto só vale se TODOS os relatos são agenda/rotina; um termo de impacto anula |
| `HOLIDAY@10` | ev 4 · N2+ 0 · top N1 · CONFIRMED/DEVELOPING · conf 32 · fontes 3 · inv 0 | ev 4 · N2+ 0 · top N1 · CONFIRMED/DEVELOPING · conf 32 · fontes 3 · inv 0 | nenhum evento N2+ | PASS | PASS | baixo: o teto só vale se TODOS os relatos são agenda/rotina; um termo de impacto anula |
| `HOLIDAY@50` | ev 4 · N2+ 4 · top N2 · CONFIRMED · conf 37 · fontes 10 · inv 0 | ev 4 · N2+ 0 · top N1 · CONFIRMED · conf 37 · fontes 10 · inv 0 | nenhum evento N2+ | FAIL | PASS | baixo: o teto só vale se TODOS os relatos são agenda/rotina; um termo de impacto anula |
| `HOLIDAY@100` | ev 4 · N2+ 4 · top N2 · CONFIRMED · conf 36 · fontes 10 · inv 0 | ev 4 · N2+ 0 · top N1 · CONFIRMED · conf 36 · fontes 10 · inv 0 | nenhum evento N2+ | FAIL | PASS | baixo: o teto só vale se TODOS os relatos são agenda/rotina; um termo de impacto anula |
| `HOLIDAY@500` | ev 4 · N2+ 4 · top N2 · CONFIRMED · conf 35 · fontes 10 · inv 0 | ev 4 · N2+ 0 · top N1 · CONFIRMED · conf 35 · fontes 10 · inv 0 | nenhum evento N2+ | FAIL | PASS | baixo: o teto só vale se TODOS os relatos são agenda/rotina; um termo de impacto anula |
| `HOLIDAY@1000` | ev 4 · N2+ 4 · top N2 · CONFIRMED · conf 35 · fontes 10 · inv 0 | ev 4 · N2+ 0 · top N1 · CONFIRMED · conf 35 · fontes 10 · inv 0 | nenhum evento N2+ | FAIL | PASS | baixo: o teto só vale se TODOS os relatos são agenda/rotina; um termo de impacto anula |
| `NORMAL_RAIN@10` | ev 4 · N2+ 0 · top N1 · CONFIRMED/DEVELOPING · conf 32 · fontes 3 · inv 0 | ev 4 · N2+ 0 · top N1 · CONFIRMED/DEVELOPING · conf 32 · fontes 3 · inv 0 | nenhum evento N2+ | PASS | PASS | médio: 'chuva fraca'/'garoa' viram rotina; chuva perigosa precisa de 'chuva forte'/'temporal' no texto |
| `NORMAL_RAIN@50` | ev 4 · N2+ 4 · top N2 · CONFIRMED · conf 37 · fontes 10 · inv 0 | ev 4 · N2+ 0 · top N1 · CONFIRMED · conf 37 · fontes 10 · inv 0 | nenhum evento N2+ | FAIL | PASS | médio: 'chuva fraca'/'garoa' viram rotina; chuva perigosa precisa de 'chuva forte'/'temporal' no texto |
| `NORMAL_RAIN@100` | ev 4 · N2+ 4 · top N2 · CONFIRMED · conf 36 · fontes 10 · inv 0 | ev 4 · N2+ 0 · top N1 · CONFIRMED · conf 36 · fontes 10 · inv 0 | nenhum evento N2+ | FAIL | PASS | médio: 'chuva fraca'/'garoa' viram rotina; chuva perigosa precisa de 'chuva forte'/'temporal' no texto |
| `NORMAL_RAIN@500` | ev 4 · N2+ 4 · top N2 · CONFIRMED · conf 35 · fontes 10 · inv 1 | ev 4 · N2+ 0 · top N1 · CONFIRMED · conf 35 · fontes 10 · inv 1 | nenhum evento N2+ | FAIL | PASS | médio: 'chuva fraca'/'garoa' viram rotina; chuva perigosa precisa de 'chuva forte'/'temporal' no texto |
| `NORMAL_RAIN@1000` | ev 4 · N2+ 4 · top N2 · CONFIRMED · conf 35 · fontes 10 · inv 1 | ev 4 · N2+ 0 · top N1 · CONFIRMED · conf 35 · fontes 10 · inv 1 | nenhum evento N2+ | FAIL | PASS | médio: 'chuva fraca'/'garoa' viram rotina; chuva perigosa precisa de 'chuva forte'/'temporal' no texto |
| `RUSH_HOUR@10` | ev 4 · N2+ 0 · top N1 · CONFIRMED/DEVELOPING · conf 32 · fontes 3 · inv 0 | ev 4 · N2+ 0 · top N1 · CONFIRMED/DEVELOPING · conf 32 · fontes 3 · inv 0 | nenhum evento N2+ | PASS | PASS | médio: 'lentidão' vira rotina; lentidão por incidente precisa de 'acidente'/'congestionamento'/'bloqueio' |
| `RUSH_HOUR@50` | ev 4 · N2+ 4 · top N2 · CONFIRMED · conf 37 · fontes 10 · inv 2 | ev 4 · N2+ 0 · top N1 · CONFIRMED · conf 37 · fontes 10 · inv 2 | nenhum evento N2+ | FAIL | PASS | médio: 'lentidão' vira rotina; lentidão por incidente precisa de 'acidente'/'congestionamento'/'bloqueio' |
| `RUSH_HOUR@100` | ev 4 · N2+ 4 · top N2 · CONFIRMED · conf 36 · fontes 10 · inv 2 | ev 4 · N2+ 0 · top N1 · CONFIRMED · conf 36 · fontes 10 · inv 2 | nenhum evento N2+ | FAIL | PASS | médio: 'lentidão' vira rotina; lentidão por incidente precisa de 'acidente'/'congestionamento'/'bloqueio' |
| `RUSH_HOUR@500` | ev 4 · N2+ 4 · top N2 · CONFIRMED · conf 35 · fontes 10 · inv 2 | ev 4 · N2+ 0 · top N1 · CONFIRMED · conf 35 · fontes 10 · inv 2 | nenhum evento N2+ | FAIL | PASS | médio: 'lentidão' vira rotina; lentidão por incidente precisa de 'acidente'/'congestionamento'/'bloqueio' |
| `RUSH_HOUR@1000` | ev 4 · N2+ 4 · top N2 · CONFIRMED · conf 35 · fontes 10 · inv 2 | ev 4 · N2+ 0 · top N1 · CONFIRMED · conf 35 · fontes 10 · inv 2 | nenhum evento N2+ | FAIL | PASS | médio: 'lentidão' vira rotina; lentidão por incidente precisa de 'acidente'/'congestionamento'/'bloqueio' |
| `SOCIAL_REPOST_STORM@10` | ev 2 · N2+ 1 · top N2 · DETECTED · conf 40 · fontes 8 · inv 0 | ev 2 · N2+ 0 · top N1 · DETECTED · conf 32 · fontes 3 · inv 0 | nenhum evento N2+ | FAIL | PASS | baixo: viral social já é teto 3 e DETECTED; o gate só tira volume da independência |
| `SOCIAL_REPOST_STORM@50` | ev 3 · N2+ 2 · top N2 · DETECTED · conf 37 · fontes 28 · inv 0 | ev 3 · N2+ 0 · top N1 · DETECTED · conf 27 · fontes 3 · inv 0 | nenhum evento N2+ | FAIL | PASS | baixo: viral social já é teto 3 e DETECTED; o gate só tira volume da independência |
| `SOCIAL_REPOST_STORM@100` | ev 3 · N2+ 2 · top N2 · DETECTED · conf 39 · fontes 30 · inv 0 | ev 3 · N2+ 0 · top N1 · DETECTED · conf 26 · fontes 3 · inv 0 | nenhum evento N2+ | FAIL | PASS | baixo: viral social já é teto 3 e DETECTED; o gate só tira volume da independência |
| `SOCIAL_REPOST_STORM@500` | ev 2 · N2+ 2 · top N2 · DETECTED · conf 35 · fontes 30 · inv 0 | ev 2 · N2+ 0 · top N1 · DETECTED · conf 25 · fontes 3 · inv 0 | nenhum evento N2+ | FAIL | PASS | baixo: viral social já é teto 3 e DETECTED; o gate só tira volume da independência |
| `SOCIAL_REPOST_STORM@1000` | ev 2 · N2+ 2 · top N2 · DETECTED · conf 35 · fontes 30 · inv 0 | ev 2 · N2+ 0 · top N1 · DETECTED · conf 25 · fontes 3 · inv 0 | nenhum evento N2+ | FAIL | PASS | baixo: viral social já é teto 3 e DETECTED; o gate só tira volume da independência |
| `DERBY_METRO_FAILURE@4` | ev 1 · N2+ 1 · top N2 · CONFIRMED · conf 55 · fontes 4 · inv 2 | ev 1 · N2+ 1 · top N2 · CONFIRMED · conf 55 · fontes 4 · inv 2 | algum evento N2+ | PASS | PASS | baixo: o gate só sobe severidade/publica com termo operacional; nunca rebaixa impacto |
| `DERBY_METRO_FAILURE@12` | ev 1 · N2+ 1 · top N2 · CONFIRMED · conf 42 · fontes 12 · inv 2 | ev 1 · N2+ 1 · top N2 · CONFIRMED · conf 42 · fontes 12 · inv 2 | algum evento N2+ | PASS | PASS | baixo: o gate só sobe severidade/publica com termo operacional; nunca rebaixa impacto |
| `STADIUM_EVACUATION@4` | ev 1 · N2+ 1 · top N2 · CONFIRMED · conf 55 · fontes 4 · inv 1 | ev 1 · N2+ 1 · top N2 · CONFIRMED · conf 55 · fontes 4 · inv 1 | algum evento N2+ | PASS | PASS | baixo: o gate só sobe severidade/publica com termo operacional; nunca rebaixa impacto |
| `STADIUM_EVACUATION@12` | ev 1 · N2+ 1 · top N2 · CONFIRMED · conf 42 · fontes 12 · inv 1 | ev 1 · N2+ 1 · top N2 · CONFIRMED · conf 42 · fontes 12 · inv 1 | algum evento N2+ | PASS | PASS | baixo: o gate só sobe severidade/publica com termo operacional; nunca rebaixa impacto |
| `SPORT_EVENT_BLACKOUT@4` | ev 1 · N2+ 1 · top N2 · CONFIRMED · conf 45 · fontes 3 · inv 2 | ev 1 · N2+ 1 · top N2 · CONFIRMED · conf 45 · fontes 3 · inv 2 | algum evento N2+ | PASS | PASS | baixo: o gate só sobe severidade/publica com termo operacional; nunca rebaixa impacto |
| `SPORT_EVENT_BLACKOUT@12` | ev 1 · N2+ 1 · top N2 · CONFIRMED · conf 42 · fontes 11 · inv 2 | ev 1 · N2+ 1 · top N2 · CONFIRMED · conf 42 · fontes 11 · inv 2 | algum evento N2+ | PASS | PASS | baixo: o gate só sobe severidade/publica com termo operacional; nunca rebaixa impacto |
| `SPORT_EVENT_SECURITY_INCIDENT@4` | ev 3 · N2+ 0 · top N1 · DETECTED/DEVELOPING · conf 35 · fontes 2 · inv 0 | ev 3 · N2+ 0 · top N1 · DETECTED/DEVELOPING · conf 35 · fontes 2 · inv 0 | algum evento N2+ | FAIL | FAIL | baixo: o gate só sobe severidade/publica com termo operacional; nunca rebaixa impacto |
| `SPORT_EVENT_SECURITY_INCIDENT@12` | ev 3 · N2+ 3 · top N2 · CONFIRMED · conf 42 · fontes 6 · inv 0 | ev 3 · N2+ 3 · top N2 · CONFIRMED · conf 42 · fontes 6 · inv 0 | algum evento N2+ | PASS | PASS | baixo: o gate só sobe severidade/publica com termo operacional; nunca rebaixa impacto |
| `CONCERT_EVACUATION@4` | ev 2 · N2+ 0 · top N1 · CONFIRMED/DETECTED · conf 45 · fontes 3 · inv 0 | ev 2 · N2+ 1 · top N2 · CONFIRMED/DETECTED · conf 45 · fontes 3 · inv 0 | algum evento N2+ | FAIL | PASS | baixo: o gate só sobe severidade/publica com termo operacional; nunca rebaixa impacto |
| `CONCERT_EVACUATION@12` | ev 2 · N2+ 2 · top N2 · CONFIRMED · conf 42 · fontes 9 · inv 0 | ev 2 · N2+ 2 · top N2 · CONFIRMED · conf 42 · fontes 9 · inv 0 | algum evento N2+ | PASS | PASS | baixo: o gate só sobe severidade/publica com termo operacional; nunca rebaixa impacto |
| `CONCERT_TRANSPORT_FAILURE@4` | ev 0 · N2+ 0 · top N0 · - · conf 0 · fontes 0 · inv 0 | ev 1 · N2+ 1 · top N2 · CONFIRMED · conf 45 · fontes 3 · inv 0 | algum evento N2+ | FAIL | PASS | médio: 'ficam presos'/'trens param' podem publicar pauta de agenda ambígua |
| `CONCERT_TRANSPORT_FAILURE@12` | ev 0 · N2+ 0 · top N0 · - · conf 0 · fontes 0 · inv 0 | ev 2 · N2+ 1 · top N2 · CONFIRMED · conf 42 · fontes 9 · inv 0 | algum evento N2+ | FAIL | PASS | médio: 'ficam presos'/'trens param' podem publicar pauta de agenda ambígua |
| `CITY_BLACKOUT@4` | ev 1 · N2+ 1 · top N2 · CONFIRMED · conf 55 · fontes 4 · inv 2 | ev 1 · N2+ 1 · top N2 · CONFIRMED · conf 55 · fontes 4 · inv 2 | algum evento N2+ | PASS | PASS | baixo: o gate só sobe severidade/publica com termo operacional; nunca rebaixa impacto |
| `CITY_BLACKOUT@12` | ev 1 · N2+ 1 · top N2 · CONFIRMED · conf 42 · fontes 12 · inv 2 | ev 1 · N2+ 1 · top N2 · CONFIRMED · conf 42 · fontes 12 · inv 2 | algum evento N2+ | PASS | PASS | baixo: o gate só sobe severidade/publica com termo operacional; nunca rebaixa impacto |
| `TELECOM_FAILURE@4` | ev 1 · N2+ 1 · top N2 · CONFIRMED · conf 45 · fontes 3 · inv 0 | ev 1 · N2+ 1 · top N2 · CONFIRMED · conf 45 · fontes 3 · inv 0 | algum evento N2+ | PASS | PASS | baixo: o gate só sobe severidade/publica com termo operacional; nunca rebaixa impacto |
| `TELECOM_FAILURE@12` | ev 2 · N2+ 1 · top N2 · CONFIRMED/DEVELOPING · conf 43 · fontes 10 · inv 0 | ev 2 · N2+ 1 · top N2 · CONFIRMED/DEVELOPING · conf 43 · fontes 10 · inv 0 | algum evento N2+ | PASS | PASS | baixo: o gate só sobe severidade/publica com termo operacional; nunca rebaixa impacto |
| `ROAD_BLOCKAGE@4` | ev 1 · N2+ 0 · top N1 · CONFIRMED · conf 45 · fontes 3 · inv 0 | ev 1 · N2+ 1 · top N2 · CONFIRMED · conf 45 · fontes 3 · inv 0 | algum evento N2+ | FAIL | PASS | baixo: o gate só sobe severidade/publica com termo operacional; nunca rebaixa impacto |
| `ROAD_BLOCKAGE@12` | ev 2 · N2+ 1 · top N2 · CONFIRMED · conf 42 · fontes 9 · inv 0 | ev 2 · N2+ 1 · top N2 · CONFIRMED · conf 42 · fontes 9 · inv 0 | algum evento N2+ | PASS | PASS | baixo: o gate só sobe severidade/publica com termo operacional; nunca rebaixa impacto |
| `FLOOD@4` | ev 1 · N2+ 1 · top N2 · CONFIRMED · conf 55 · fontes 4 · inv 2 | ev 1 · N2+ 1 · top N2 · CONFIRMED · conf 55 · fontes 4 · inv 2 | algum evento N2+ | PASS | PASS | baixo: o gate só sobe severidade/publica com termo operacional; nunca rebaixa impacto |
| `FLOOD@12` | ev 1 · N2+ 1 · top N2 · CONFIRMED · conf 42 · fontes 12 · inv 2 | ev 1 · N2+ 1 · top N2 · CONFIRMED · conf 42 · fontes 12 · inv 2 | algum evento N2+ | PASS | PASS | baixo: o gate só sobe severidade/publica com termo operacional; nunca rebaixa impacto |
| `DERBY_METRO_FAILURE_IN_500_SPORTS` | ev 2 · N2+ 2 · top N2 · CONFIRMED · conf 45 · fontes 30 · inv 2 | ev 2 · N2+ 1 · top N2 · CONFIRMED · conf 45 · fontes 30 · inv 2 | o incidente segue N2+ no meio de 500 matérias de futebol | PASS | PASS | baixo: o gate só sobe severidade/publica com termo operacional; nunca rebaixa impacto |
| `CASCADE_1_5_50` | ev 1 · N2+ 1 · top N3 · CONFIRMED · conf 94 · fontes 56 · inv 4 | ev 1 · N2+ 1 · top N3 · CONFIRMED · conf 94 · fontes 56 · inv 4 | fontes do evento <= 6 (1 origem + 5 paráfrases) | FAIL | FAIL | médio: relato social curto e parecido com a manchete deixa de somar (quase-cópia) |
| `CASCADE_1_5_50_1000` | ev 1 · N2+ 1 · top N3 · CONFIRMED · conf 81 · fontes 256 · inv 4 | ev 1 · N2+ 1 · top N3 · CONFIRMED · conf 81 · fontes 56 · inv 4 | fontes do evento <= 6; 1000 reposts não somam | FAIL | FAIL | médio: relato social curto e parecido com a manchete deixa de somar (quase-cópia) |
| `FALSE_MERGE` | ev 2 · N2+ 2 · top N2 · DEVELOPING · conf 25 · fontes 2 · inv 3 | ev 2 · N2+ 2 · top N2 · DEVELOPING · conf 25 · fontes 2 · inv 3 | 2 eventos (SP e MG) | PASS | PASS | nenhum: o gate não toca o agrupamento |
| `FALSE_MERGE+CLUSTER_REFINE` | ev 2 · N2+ 2 · top N2 · DEVELOPING · conf 25 · fontes 2 · inv 3 | ev 2 · N2+ 2 · top N2 · DEVELOPING · conf 25 · fontes 2 · inv 3 | 2 eventos (SP e MG) | PASS | PASS | nenhum: o gate não toca o agrupamento |
| `FALSE_SPLIT` | ev 4 · N2+ 0 · top N1 · DETECTED · conf 22 · fontes 1 · inv 2 | ev 4 · N2+ 0 · top N1 · DETECTED · conf 22 · fontes 1 · inv 2 | 1 evento com 4 fontes | FAIL | FAIL | nenhum: o gate não toca o agrupamento |
| `FALSE_SPLIT+CLUSTER_REFINE` | ev 1 · N2+ 1 · top N2 · CONFIRMED · conf 55 · fontes 4 · inv 2 | ev 1 · N2+ 1 · top N2 · CONFIRMED · conf 55 · fontes 4 · inv 2 | 1 evento com 4 fontes | PASS | PASS | nenhum: o gate não toca o agrupamento |
| `EVENT_DRIFT` | ev 3 · N2+ 0 · top N1 · DETECTED/DEVELOPING · conf 35 · fontes 2 · inv 0 | ev 3 · N2+ 0 · top N1 · DETECTED/DEVELOPING · conf 35 · fontes 2 · inv 0 | a cadeia incêndio -> demissão -> protesto não vira 1 evento | PASS | PASS | nenhum: o gate não toca o agrupamento |
| `EVENT_RESURRECTION` | ev 0 · N2+ 0 · top N0 · - · conf 0 · fontes 0 · inv 0 | ev 0 · N2+ 0 · top N0 · - · conf 0 · fontes 0 · inv 0 | matéria de 3 dias atrás não cria evento | PASS | PASS | nenhum: o gate não toca o agrupamento |
| `OFFICIAL_CONFIRMATION` | ev 1 · N2+ 1 · top N2 · CONFIRMED · conf 87 · fontes 4 · inv 2 | ev 1 · N2+ 1 · top N2 · CONFIRMED · conf 87 · fontes 4 · inv 2 | CONFIRMED | PASS | PASS | nenhum para o gate; EVENT_CONTRADICTION depende de regex de negação (médio) |
| `OFFICIAL_DENIAL` | ev 1 · N2+ 1 · top N2 · CONFIRMED · conf 87 · fontes 4 · inv 2 | ev 1 · N2+ 1 · top N2 · CONFIRMED · conf 87 · fontes 4 · inv 2 | DISPUTED | FAIL | FAIL | nenhum para o gate; EVENT_CONTRADICTION depende de regex de negação (médio) |
| `OFFICIAL_DENIAL+EVENT_CONTRADICTION` | ev 1 · N2+ 1 · top N2 · DISPUTED · conf 72 · fontes 4 · inv 2 | ev 1 · N2+ 1 · top N2 · DISPUTED · conf 72 · fontes 4 · inv 2 | DISPUTED | PASS | PASS | nenhum para o gate; EVENT_CONTRADICTION depende de regex de negação (médio) |
| `CONFLICTING_SENSORS` | ev 1 · N2+ 1 · top N2 · CONFIRMED · conf 55 · fontes 4 · inv 0 | ev 1 · N2+ 1 · top N2 · CONFIRMED · conf 55 · fontes 4 · inv 0 | DISPUTED (sem energia x restabelecida ao mesmo tempo) | FAIL | FAIL | nenhum para o gate; EVENT_CONTRADICTION depende de regex de negação (médio) |
| `CONFLICTING_SENSORS+EVENT_CONTRADICTION` | ev 1 · N2+ 1 · top N2 · DISPUTED · conf 40 · fontes 4 · inv 0 | ev 1 · N2+ 1 · top N2 · DISPUTED · conf 40 · fontes 4 · inv 0 | DISPUTED (sem energia x restabelecida ao mesmo tempo) | PASS | PASS | nenhum para o gate; EVENT_CONTRADICTION depende de regex de negação (médio) |
| `RESOLUTION_IS_NOT_DISPUTE+EVENT_CONTRADICTION` | ev 1 · N2+ 1 · top N2 · CONFIRMED · conf 45 · fontes 3 · inv 0 | ev 1 · N2+ 1 · top N2 · CONFIRMED · conf 45 · fontes 3 · inv 0 | não DISPUTED (restabelecida DEPOIS) | PASS | PASS | nenhum para o gate; EVENT_CONTRADICTION depende de regex de negação (médio) |
| `STALE_SENSOR` | ev 2 · N2+ 1 · top N2 · CONFIRMED · conf 48 · fontes 3 · inv 0 | ev 2 · N2+ 1 · top N2 · CONFIRMED · conf 48 · fontes 3 · inv 0 | confirmação oficial de 14 h atrás não se soma ao relato de agora | PASS | PASS | nenhum para o gate; EVENT_CONTRADICTION depende de regex de negação (médio) |

