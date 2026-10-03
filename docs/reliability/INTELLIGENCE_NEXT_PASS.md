# Intelligence Engine — Next Pass — 2026-10-03

## Estado real

O commit `7b416a0` já está na `main` por meio do merge `a62d3e3`. A implementação editorial existente foi reutilizada; não houve réplica cega nem alteração de Forecast/Geo V2/frontend.

## Correções verificadas

### Editorial × operacional — PASS

O corpus cobre futebol, onde assistir, apostas/odds, transferência, entretenimento, show e feriado nos volumes 1/10/50/100/500/1000. `EDITORIAL_ONLY` e `SCHEDULED_CONTEXT` não publicam sozinhos. Controles de metrô interrompido, evacuação de estádio, apagão e falha de transporte continuam elegíveis.

### Provenance e deduplicação — PASS parcial

O evento agora usa uma chave conservadora de origem baseada em URL/título normalizado: republicações idênticas não aumentam `independent_sources` e não aumentam `velocity_per_hour`; reposts sociais idênticos não confirmam. Paráfrases completas continuam limitadas pelas regras determinísticas existentes e não são falsamente declaradas como cópias.

### Clustering adversarial — PASS parcial

Paráfrases que compartilham lugar + núcleo físico (por exemplo, deslizamento em Petrópolis) são agrupadas, enquanto cidades com o mesmo tipo de incidente permanecem separadas quando a geo é confiante. False merge entre incidentes distintos, drift temporal e ressurreição após encerramento ainda exigem estado histórico persistido.

### Contradição — PASS local

`EventStats.contradiction >= 0.5` produz `DISPUTED`, preservando o fato de que uma negativa oficial não é uma quarta confirmação positiva. O Sentinela continua registrando os dois lados.

## Suíte e evidência

O recorte adversarial passou com **87 passed, 10 xfailed**. Os xfails restantes são limitações conhecidas (telecom/alguns incidentes subestimados, conteúdo quebrado/frescor e outros casos ainda não resolvidos). A regressão completa do Engine deve ser executada após a integração deste passe.

## Status por área

| Área | Estado | Observação |
|---|---|---|
| Classification / roles | PASS | separação editorial/contexto/operacional preservada |
| Operational relevance | PARTIAL | vocabulário de incidentes ainda tem lacunas |
| Provenance | PASS parcial | origem determinística; reescrita completa é limite conhecido |
| Dedup | PASS parcial | URL/título e volume duplicado cobertos |
| Clustering | PASS parcial | paráfrase + geo cobertos; drift/resurrection pendentes |
| Contradiction | PASS | `DISPUTED` e provenance dos dois lados |
| Coverage / missingness | PARTIAL | cobertura/abstenção cobertas em V2; distribuição operacional histórica ausente |
| Sentinela / information gain | UNVERIFIED | corpus amplo e métricas diárias dependem do WIP do motor |
| Predictive skill | INSUFFICIENT_DATA | fora do escopo de tuning; V2 permanece shadow |

## Limitações explícitas

Não foram ajustados thresholds globais, não foi criado Forecast V3, não houve promoção de Geo V2 nem alteração de golden datasets. A suíte adversarial ainda deve ganhar casos explícitos de `EVENT_DRIFT`, `EVENT_RESURRECTION`, API outage, stale sensor e informação incremental da Sentinela antes de qualquer declaração de maturidade.
