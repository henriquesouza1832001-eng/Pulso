# Observability + Coverage + Confidence — validação

Data: 2026-10-03. Auditoria sobre o branch `hen`, com a `main` remota em `d85edd4` no início da rodada. O WIP do motor do Claude foi preservado; este relatório não assume que arquivos ainda não commitados estejam prontos para integração.

## BASELINE

- PR #94: aberto, CI mais recente verde (Engine Python, Worker/shared e GitGuardian).
- Baseline Python limpo anterior: **767 passed, 5 xfailed, 24 warnings**, 57,24s.
- Regressão do branch com campanhas integradas: **883 passed, 5 xfailed, 24 warnings**, 95,69s.
- Validação focada de observabilidade/cobertura/confiança/forecast/Sentinela: **94 passed**, 39,43s.
- QA conhecidos: QA-002 e QA-006; não foram reclassificados nesta rodada.
- `npm ci` local continua `BLOCKED_EXTERNAL/ENVIRONMENT` por `EBUSY` em `node_modules/miniflare`; CI remoto permanece a referência para Worker.

## SOURCE HEALTH

**PASS.** A arquitetura distingue transporte, conteúdo e frescor: `ONLINE/DEGRADED/OFFLINE` no transporte e `FRESH/STALE/EMPTY/QUIET/UNKNOWN` no dado. HTTP 200 com conteúdo repetido é stale; payload inválido é degraded/empty; timeout, DNS, 429 e 5xx não viram dado normal.

## FRESHNESS

**PASS local / PARTIAL operacional.** O contrato preserva `last_successful_fetch`, último conteúdo novo, idade do item e estado de frescor quando disponíveis. A cadência específica por fonte já é respeitada por `stale_after_min`; não há TTL universal. Falta observar percentis reais por família em produção durante uma janela longa.

## COVERAGE

**PASS no contrato de fonte.** `coverage_ratio` conta apenas fontes esperadas, exclui `QUIET`, considera `STALE/EMPTY/UNKNOWN` como cobertura perdida e retorna `None` quando cobertura não se aplica. `view_state` diferencia `COMPLETE`, `PARTIAL`, `DEGRADED`, `CRITICAL` e `NOT_APPLICABLE`. A camada por família está disponível.

**PARTIAL na agregação de mundo real.** A cobertura atual ainda é principalmente por fonte/família observada; cobertura geográfica e expectativa de disponibilidade por cidade/evento precisam de dados de catálogo e histórico operacional suficientes para não inventar granularidade.

## MISSINGNESS

**PASS.** Sensor ausente, stale, empty e unknown permanecem distintos de silêncio normal. Forecast V2 registra `expected`, `available`, `stale`, `missing` e `ratio`; cobertura crítica produz abstention/`INSUFFICIENT_DATA`.

## CONFIDENCE

**PASS nos invariantes locais.** A degradação usa fator monotônico de cobertura; perder sensores nunca aumenta confiança. Duplicatas não substituem diversidade de família/origem. Confidence continua separada de severity: impacto alto pode ter confiança baixa, e evento pequeno pode ter confiança alta.

**PARTIAL na integração ampla.** Nem todo consumidor legado de evento expõe uma estrutura observability comum; alguns caminhos ainda recebem apenas `EventStats`/frescor legado. Não houve tuning de pesos nem mudança de Forecast V3.

## SENTINELA

**PASS no harness.** O Sentinela aceita cobertura e registra visão degradada; os testes distinguem investigação por conflito, por lacuna de sensor e por anomalia inesperada. `information_gain` prioriza família física/oficial ausente em vez de multiplicar publishers de NEWS.

**INSUFFICIENT_DATA em produção.** Não há amostra real suficiente para afirmar taxas de investigação falsa/dia, ganho marginal ou recuperação sem flapping por família.

## FORECAST CONTRACT

**PASS / SHADOW.** Snapshot V2 recebe `source_coverage`, coverage por sensor, missingness e abstention. A comparação 95% versus 20% de cobertura é monotônica e cobertura crítica retorna `INSUFFICIENT_DATA`; o modelo não foi redesenhado nem calibrado nesta rodada.

## ADVERSARIAL MATRIX

| Cenário | Resultado |
|---|---|
| normal + cobertura alta/baixa | PASS — baixa cobertura reduz confiança e explicita degradação |
| incidente + cobertura alta/baixa | PASS local — não confunde ausência com normalidade |
| oficial denial / sensores contraditórios | PASS — contradição permanece separada de ausência |
| NEWS storm / duplicate storm | PASS — publisher não substitui origem/família |
| sensor outage / multi-outage | PASS — outage não vira incidente real |
| stale sources / recovery | PASS local — stale/unknown não são fresh; recuperação testada |
| cobertura geográfica nacional real | INSUFFICIENT_DATA |

## PERFORMANCE

A camada de cobertura é linear no número de assessments/famílias e os testes focados não indicam custo dominante. Benchmark de provenance/sentinel anterior registrou a limitação de clustering V1 em 5.000 sinais; coverage não deve recalcular o universo por evento. Cache por escopo/família/time bucket permanece recomendação operacional.

## OPEN DEFECTS

- **PARTIAL:** observability state comum ainda não é exposto de forma uniforme em todos os consumidores legados.
- **INSUFFICIENT_DATA:** cobertura geográfica e por evento em produção, percentis de frescor, ganho marginal real e falsos por dia.
- **BLOCKED_EXTERNAL:** `npm ci` local por lock de `node_modules`; CI remoto verde no PR.
- **UNVERIFIED:** contratos Worker/DB para novos campos de observabilidade não foram alterados nesta rodada.

Conclusão: o PULSO já diferencia “nenhuma evidência com sensores saudáveis” de “visão insuficiente” no harness e nos contratos V2. Isso ainda não é uma garantia de cobertura real nacional nem evidência de skill preditiva.
