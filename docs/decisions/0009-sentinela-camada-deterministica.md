# 0009 — PULSO Sentinela como camada determinística sobre o pipeline

**Status:** aceita · **Data:** 2026-10-04 · **Contexto:** documento "Motor Python + PULSO Sentinela" e `docs/CURRENT_ENGINE_STATE.md`.

## Decisão
1. **O Sentinela é uma camada de análise determinística (estatística + regras + estado), sem LLM no caminho crítico.** Nasce sobre o `pipeline.run_once` existente; não substitui coleta, agrupamento, pontuação nem previsão.
2. **Não reorganizar as pastas.** Os módulos planos existentes (`baseline.py`, `anomaly.py`, `forecast.py`, `series.py`, `drivers.py`) são **estendidos**; só o que é novo ganha pacote (`research/`, `intelligence/`). Mover quebraria imports, ~370 testes e o `AGENTS.md`.
3. **Memória = observações agregadas por hora** (`signal_observations`: escopo × categoria × classe de fonte × hora; só contagens, sem conteúdo de terceiros), com escrita só de horas fechadas e condicional, para caber no orçamento de escrita (ADR 0008; banco ativo: Turso). Baseline sazonal (hora × dia da semana, hora de Brasília) consome essa tabela; sem histórico suficiente o resultado é `BASELINE INSUFICIENTE` e a anomalia vale 0.
4. **`radar.py` é o ponto de entrada** chamado pelo `collect.yml` (disparado pelo Cron da Cloudflare); não há segundo workflow. `pipeline.run_once` continua o núcleo.
5. **Deep search só sobre fontes já cadastradas e já coletadas**, com teto por ciclo e por investigação, cache na rodada e matriz de sensores por categoria (correlação, não causalidade). Nenhum motor de busca externo, nenhuma raspagem, nenhum contorno de termos.
6. **Validação registra contradições em vez de escolher a versão mais repetida**; cópias da mesma matéria são uma origem; rede social nunca confirma sozinha.
7. **Pulso V2 em paralelo e atrás de flag.** `WEIGHTS` (V1) fica intacto; `WEIGHTS_V2` (aceleração 5 e diversidade de tipos de sensor 5, tirando 5 de velocidade e 5 de diversidade de fontes) só vale com `PULSE_V2` ligada, depois do portão de promoção. Contradição (parâmetro aditivo, padrão 0) reduz a confiança e aparece no "POR QUE?" com 0 pontos só quando > 0.
8. **Clusterização v2** é um pós-passo (`processing/cluster_refine.py`, flag `CLUSTER_REFINE`, desligado) que só funde grupos com vetos rígidos (categoria, janela, lugar, entidade comum). DBSCAN, embeddings e spaCy ficam **adiados até uma medição mostrar ganho** (o job roda a cada 5 min, teto de 8 min, sem dependências hoje).
9. **Probabilidade só vem de estatística calibrada** (`forecast.py`, `forecast_scopes.py`, `calibration.py`); previsões seguem EXPERIMENTAL até 100 resolvidas por método e versão. Lead time e backtest de eventos (`backtest_events.py`) medem se o PULSO teria detectado e com quanta antecedência, sem espiar o futuro.

## Consequências
- Várias peças existem e passam em testes mas **só afetam produção quando o `analyze` é ligado ao `run_once`** (feito por quem mantém `pipeline.py`, com migration e campos opcionais no ingest).
- O baseline sazonal só vale depois de semanas de dados; até lá o EWMA atual é o comportamento correto.
- Assinaturas de evento usam JSON (`config/event_signatures.json`), não YAML, para não adicionar dependência.
- Limiares (gatilho do Sentinela, merge do `cluster_refine`, pesos novos do Pulso) são ponto de partida e precisam de recalibração com dados reais, registrada em novo ADR.

## Alternativas descartadas
LLM como núcleo (viola "funcionar sem LLM"); reorganizar pastas (custo sem ganho); guardar cada sinal por sensor (estoura o orçamento de escrita); workflow `radar.yml` separado (competiria por `concurrency` e duplicaria a coleta).
