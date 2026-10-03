# ENGINE_V2_PLAN — evolução incremental dos motores (2026-10-03)

> Parte B/C/D/E/F/G da primeira entrega do prompt "Evolução segura dos motores preditivos". Base: [ENGINE_AUDIT.md](ENGINE_AUDIT.md). Princípio: **nenhum V2 substitui o V1 porque parece melhor; substitui quando os dados provam** (portão da §5). O V1 continua em produção o tempo todo. **Este plano aguarda revisão do dono antes de qualquer mudança estrutural grande** (itens da §9).

## 1. Estratégia
```text
V1 em produção ──────────────────────────────► continua igual
V2 em paralelo (arquivo novo, por composição) ► atrás de feature flag (OFF)
        ↓ SHADOW: calcula e GRAVA, não muda evento/Pulso/alerta
        ↓ BACKTEST V1 × V2 (eventos reais quando houver histórico)
        ↓ PORTÃO DE PROMOÇÃO (§5)
        ↓ CANARY (parte dos escopos) → ACTIVE
```

## 2. Mapa de arquivos

### CRIAR (novos, por composição)
| Arquivo | Fase | Observação |
|---|---|---|
| `engine/pulso_engine/flags.py` | A | **já criado** (14 flags, padrão seguro, `PULSO_FLAG_<NOME>`) |
| `engine/pulso_engine/validation/shadow_compare.py` | A | grava `V1 × V2 × desfecho` por evento/previsão |
| `engine/pulso_engine/validation/metrics.py` | A | Brier, log loss, erro de calibração, precision/recall/F1, FPR, lead time, cobertura |
| `engine/pulso_engine/validation/backtest_v2.py` | A/C | evolui o `backtest.py` (sintético) para eventos reais e V1 × V2; o antigo fica |
| `engine/pulso_engine/validation/forecast_registry.py` | A | snapshot de features, `model_version`, `feature_version`, `baseline_version` por previsão |
| `engine/pulso_engine/processing/geo_v2.py` + `engine/data/br_municipalities.*` | A | gazetteer dos 5.570 municípios (IBGE), com origem e versão registradas; `geo.py` fica |
| `engine/pulso_engine/quality.py` | A | completeness, freshness, geo_quality, duplication_probability por sinal |
| `engine/pulso_engine/intelligence/anomaly_v2.py` | B | `anomaly_score` e `anomaly_confidence` separados, `robust_z` (mediana/MAD), percentil; reaproveita `anomaly.window_anomaly` |
| `engine/pulso_engine/intelligence/seasonal_robust.py` | B | mediana/MAD/percentis sobre `signal_observations`; **estende** `baseline.seasonal_baseline`, não duplica |
| `engine/pulso_engine/intelligence/event_fingerprint.py` | B | identidade estável da história além do título |
| `engine/pulso_engine/scoring/confidence_v2.py` | B | `publisher ≠ origin`, diversidade de sensores, contradição (usa `research/validator.py`) |
| `engine/pulso_engine/scoring/severity_v2.py` | B | vetor de impacto (dano físico, mobilidade, infraestrutura, alcance, extensão, duração, serviços, severidade oficial) |
| `engine/pulso_engine/scoring/national_pulse.py` | B | dispersão, nº de estados, diversidade, persistência |
| `engine/pulso_engine/intelligence/driver_validator.py` | C | Brier com × sem driver; registro de drivers com estados `CANDIDATE/TESTING/ACTIVE/DEGRADED/DISABLED` |
| `engine/pulso_engine/intelligence/event_escalation.py` | C | P(evento atingir nível superior no horizonte); **começa em shadow** |
| `engine/pulso_engine/intelligence/sensor_reliability.py` | C | desempenho histórico por fonte × tipo de evento × geografia (desempenho operacional, não "verdade") |
| `engine/pulso_engine/intelligence/context_engine.py` | C | feriados (BrasilAPI já validado), jogos, eleições: ajusta baseline/anomalia, **nunca** confirma |
| `engine/pulso_engine/intelligence/information_gain.py` | D | qual sensor consultar para reduzir mais a incerteza |
| `engine/pulso_engine/intelligence/signatures.py` | D | `EVENT_SIGNATURE` (leading/concurrent/confirming/contextual) aprendida de lead times medidos |
| `engine/pulso_engine/collectors/breaker.py` | D | circuit breaker por coletor (OPEN/HALF_OPEN) |
| `engine/tests/test_*` por módulo + cenários integrados | todas | ver §6 |

### MODIFICAR (só quando não houver composição; sempre aditivo e atrás de flag)
| Arquivo | Mudança | Por quê / risco |
|---|---|---|
| `engine/pulso_engine/pipeline.py` | chamadas novas em `run_once`, cada uma com `flag(...)` e `try/except` (já feito para histórico e Sentinela) | único ponto de integração; risco médio, coberto por `test_pipeline`, `test_cycle_simulation` |
| `apps/worker/src/routes/ingest.ts`, `admin.ts`, `lib/budget.ts` | campos opcionais novos (`shadow`, `forecast_registry`...) com escrita condicional e governador | produção de dados; cada campo novo passa pelo `write_budget` |
| `packages/shared/src/contracts.ts`, `models.py`, `docs/api/API.md` | só campos opcionais, label `contract` | contrato (regra do `AGENTS.md`) |
| `engine/pulso_engine/baseline.py`, `anomaly.py` | **congelados**: já receberam funções aditivas; novas versões vão em arquivos novos | prompt §3 |

### NÃO TOCAR
`processing/clustering.py`, `processing/geo.py`, `processing/importance.py`, `scoring/pulse.py`, `scoring/confidence.py`, `events.py`, `forecast.py`, `forecast_surge.py`, `drivers.py`, `apps/web/**`, as migrations `0001`-`0005`, as rotas públicas existentes. Mudar o comportamento deles só por V2 paralelo + portão. Frontend não é prioridade (prompt §69).

## 3. Migrations (todas `IF NOT EXISTS`, aditivas; aplicadas no Turso pelo workflow `Turso schema`)
| Nº | Tabela | Para quê | Estado |
|---|---|---|---|
| 0006 | `signal_observations` | histórico por hora | **feita** (em `database/pending/`) |
| 0007 | `investigations` | Sentinela | **feita** (em `database/pending/`) |
| 0008 | `forecast_registry` (features_snapshot JSON, model/feature/baseline_version, flags ativas) | reprodutibilidade (§55) | a fazer |
| 0009 | `shadow_results` (V1, V2, desfecho, escopo, método) | comparação (§52) | a fazer |
| 0010 | `driver_registry` (driver, alvo, escopo, lag, amostras, Brier com/sem, estado) | validador de drivers | a fazer |
| 0011 | `sensor_performance` (fonte × tipo de evento × geografia: precision, lead mediano, disponibilidade) | confiabilidade de sensor | a fazer |
| 0012 | `event_fingerprints`, `model_metrics` | identidade e métricas por versão | a fazer |
Regras: sem índice secundário por padrão (cada índice dobra a escrita), escrita só do que mudou, retenção definida na própria migration, e entrada no governador de orçamento. Nada altera tabela existente; reverter = desligar a flag (as tabelas novas ficam, sem efeito).

## 4. Feature flags
Definidas em `engine/pulso_engine/flags.py`; ligar/desligar por variável `PULSO_FLAG_<NOME>`. Padrão: **tudo V2 desligado**, exceto o que já roda como **shadow** (só grava dados): `HISTORY_OBSERVATIONS`, `SENTINEL`. Lista: `SEASONAL_BASELINE_V2, ANOMALY_V2, CLUSTER_REFINE, SEMANTIC_CLUSTERING, GEO_V2, CONFIDENCE_V2, SEVERITY_V2, PULSE_V2, NATIONAL_PULSE_V2, DRIVER_VALIDATOR, EVENT_ESCALATION, CONTEXT_ENGINE`. O estado efetivo das flags vai no snapshot da previsão e no log do ciclo.

## 5. Portão de promoção (valores iniciais; revisar com dados reais)
Nenhum V2 sai de shadow sem **todas** as condições:
1. `samples >= 200` desfechos resolvidos (ou o mínimo do tipo de evento, documentado);
2. melhoria de **Brier >= 5%** sobre o V1 **e** sobre a referência ingênua (frequência histórica);
3. **FPR** não piora além de +10% relativo; **recall** não cai mais de 5%;
4. erro de calibração não piora; sem regressão grande em nenhum escopo;
5. testes verdes, rollback testado, documentação atualizada.
Depois: `SHADOW → EXPERIMENTAL → CANARY (escopos escolhidos) → ACTIVE`. Rótulos obrigatórios na saída: `INSUFFICIENT_DATA` (sem histórico), `EXPERIMENTAL` (não calibrado), `DISPUTED` (fontes contraditórias). Modelos simples primeiro (heurística → regressão logística calibrada → árvores só se justificar); **sempre** com o modelo ingênuo como referência.

## 6. Plano de testes
Cada módulo: testes unitários. Cenários integrados do prompt (§78-§85), com o estado atual:
| Cenário | Prova | Estado |
|---|---|---|
| `normal_day` | dia normal não abre investigação nem dispara anomalia | feito (`test_sentinel`) |
| `flood` | rajada abre 1 investigação por escopo | feito (`test_sentinel`) |
| `duplicated_news_wave` (§79) | 1 matéria + 30 republicações = 1 origem, não 30 confirmações | parcial (`test_validator::copies_are_one_origin`); falta o cenário de ponta a ponta com a confiança V2 |
| `false_social_spike` (§80) | 500 posts sem outro sensor: confiança limitada | parcial (teto de 40 e `social_only_never_confirmed`); falta cenário com 500 |
| `normalidade SP segunda 18h` (§82) e `anomalia real SP domingo 3h` (§83) | baseline sazonal distingue | falta (precisa da integração do baseline sazonal) |
| `driver falso` (§84) | correlação alta com amostra pequena é rejeitada | falta (`driver_validator`) |
| `geo ambíguo` (§85) | município do interior não vai para o centro da capital | parcial (`test_geo_markers`); falta com o gazetteer completo |
| `blackout`, `traffic_collapse`, `storm`, `internet_outage`, `conflicting_reports`, `stale_source` | simulações de cenário | a fazer |
| Idempotência (§62) | reprocessar não duplica | feito (`test_stateful`, `test_write_budget`, `test_observations_pipeline`) |
| Rollback (§86) | flag OFF devolve o V1 sem rastro | feito para histórico e Sentinela (`test_flags`) |

## 7. Mapa de risco
| Risco | Onde | Mitigação |
|---|---|---|
| Quebrar produção ao tocar `run_once` | `pipeline.py` | só aditivo, `try/except`, flag, testes de ciclo |
| Estourar a cota de escrita | tabelas novas | escrita condicional, retenção, governador (`economy` e `critical`) |
| Estourar a cota de leitura | histórico semanal a cada ciclo | radar a cada 15 min, teto de linhas (`fetch_observations`) |
| Estourar o tempo do ciclo (8 min) | embeddings/NLP | adiado por decisão do dono; medir antes |
| Baseline sazonal sem dados | primeiras semanas | `insufficient` não afirma anomalia; fallback EWMA |
| Probabilidade vazia de significado | modelos novos | portão, referência ingênua, rótulos `EXPERIMENTAL`/`INSUFFICIENT_DATA` |
| Conflito entre duas sessões na `hen` | repositório | turno de commit único, `git add` por nome, uma frente por arquivo |

## 8. Ordem (fase → passo do roteiro em `docs/CURRENT_ENGINE_STATE.md`)
**A. Fundação:** flags ✔ → histórico ✔ (1) → baseline sazonal ✔ código (2), ligar atrás de flag → **geo_v2 + gazetteer** → qualidade de dado → shadow_compare + forecast_registry + metrics.
**B. Correlação:** tendência ✔ e anomalia v2 ✔ código (3-4) → fingerprint → refino/semântico (8) → procedência/origem ✔ código (7) → confiança v2 → severidade v2 → Pulso nacional v2.
**C. Predição:** driver_validator → event_escalation (shadow) → calibração → sensor_reliability → contexto.
**D. Sentinela:** Sentinela ✔ (5) → information gain → deep search adaptativo ✔ código (6) → assinaturas aprendidas → circuit breaker.
Depois de cada fase: backtest V1 × V2, comparação, portão.

## 9. Decisões para a revisão do dono (antes de mudanças estruturais grandes)
1. **Nomes de pasta:** manter `research/` e `intelligence/trends.py` como estão (recomendado) ou mover para `intelligence/*` com reexportação?
2. **Gazetteer dos municípios:** autorizar baixar a base pública do IBGE (nomes, UF, centroide, população) para `engine/data/`?
3. **Limiares do portão** (§5): 200 amostras e 5% de Brier estão bons para começar?
4. **Backtest com eventos reais** depende de histórico acumulado (semanas): aceitar que as primeiras comparações V1 × V2 sejam só em shadow?
5. **Nowcast "BH Pulso 3+"** exige escopo por cidade (hoje só BR e UF): priorizar depois do gazetteer?
