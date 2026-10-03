# Provenance + Cluster V2 + Sentinela — validação

Data da medição: 2026-10-03. Esta rodada foi auditada sobre o branch `hen`; o WIP do motor do Claude foi preservado e não foi incluído neste commit.

## BASELINE

- HEAD: `7357087` (`hen`), com `7b416a0` já integrado em `main` anteriormente.
- Engine limpo, antes do WIP: **767 passed, 5 xfailed, 24 warnings**, 57,24s.
- Engine com o WIP de Provenance/Cluster/Sentinela: **883 passed, 5 xfailed, 24 warnings**, 95,69s.
- Testes adversariais novos e módulos de apoio: **115 passed**, 49,36s.
- QA ainda aberto: QA-002 (4 casos de incidente operacional sem termo classificador) e QA-006 (resposta vazia tratada como falha de transporte). QA-010 (briga de torcida em paráfrases) deixou de ser `xfail` após o refino.
- `npm ci`: **BLOCKED_EXTERNAL/ENVIRONMENT** (`EBUSY` ao remover `node_modules/miniflare/dist/local-explorer-ui`). Consequentemente `npm test` não encontrou `vitest`; não houve alteração destrutiva em `node_modules`.

## PROVENANCE

**PASS — harness determinístico.** `research/provenance.py` separa publisher, documento/origem, republicação e social repost; remove tracking de URL, reconhece cópia por título/shingles, créditos de agência, atribuições e links compartilhados. O corpus cobre uma origem em cascata por 5 publishers, 50 sites e centenas de reposts sociais, além de variações de headline, UTM, paráfrase e RT.

As invariantes verificadas são: 1000 cópias não elevam `independent_origin_count`; uma origem exclusivamente social não confirma; publishers independentes permanecem distintos; `UNKNOWN` não fabrica origem.

**PARTIAL — integração de consumidores.** Sentinela e features V2 já consomem contagens de origem. O evento legado ainda mantém compatibilidade própria para o `NOISE_GATE`; a promoção de `CLUSTER_REFINE` continua desligada.

## CLUSTERING

**PASS — corpus mecânico, não evidência de produção.** `cluster_eval.py` mede `false_merge_rate`, `false_split_rate`, pureza, perdas de ID, fragmentação e ressurreição. `cluster_refine.py` usa categoria, janela, geografia, entidades e texto com vetos rígidos; a flag `CLUSTER_REFINE` permanece OFF.

Os testes cobrem falso merge (local/tempo/incidente), falso split, drift incremental, evento encerrado com matéria retrospectiva e estabilidade de ordem. A separação entre o mesmo incidente em paráfrases e incidentes em cidades/janelas diferentes é testada.

**PARTIAL — causa de QA-008.** O corpus sintético reduz false split, mas a clusterização V1 continua lexical e pode fragmentar reescritas muito diferentes. Isso é medido, não escondido, e não há promoção automática. O controle QA-010 (quatro paráfrases de incidente esportivo) agora passa sem `xfail`.

## SENTINELA

**PASS — política determinística de investigação.** O Sentinela usa origem independente, famílias de sensor, baseline/expectedness, cobertura e contradições. `information_gain.py` ordena `RESOLVE_CONTRADICTION`, fonte oficial, sensor físico, origem independente e geolocalização; não usa LLM nem aumenta threshold global.

Hard negatives cobrem dia normal, chuva normal, rush hour, futebol, show, feriado, bursts editoriais/sociais, duplicação, sensor stale, outage, ambiguidade geográfica e negação oficial. Positive controls cobrem blackout, falha de metrô, evacuação, enchente, bloqueio, telecom e incidentes de segurança. O replay não consulta observações futuras.

**INSUFFICIENT_DATA — produção.** Os resultados são de harness/corpus sintético; não há semanas de investigações reais suficientes para estimar falsos por dia, ganho de informação ou recall operacional.

## PERFORMANCE

Benchmark determinístico em Windows 11, Python 3.14.4, 4 CPUs:

| N | Provenance | Clustering V1 | Sentinela | Resultado |
|---:|---:|---:|---:|---|
| 100 | 0,0236s | 0,0099s | 0,1263s | PASS |
| 1.000 | 0,6108s | 0,3719s | 0,7686s | PASS |
| 5.000 | 2,0545s | 32,3186s | 7,0113s | PARTIAL |
| 10.000 | 4,7521s | pulado por orçamento | pulado por orçamento | INSUFFICIENT_DATA |

O custo de clustering V1 em escala é uma limitação conhecida; antes de ampliar corpus deve-se usar janela/bucket/fingerprint para evitar comparação excessiva. Não foi aplicado tuning cosmético nesta rodada.

## REGRESSIONS

Nenhuma regressão Python foi observada no WIP: a suíte completa passou. Forecast não foi alterado; seus contratos e testes existentes permanecem verdes.

## OPEN DEFECTS

- **PARTIAL:** `CLUSTER_REFINE` permanece shadow/off até validação com dados reais.
- **PARTIAL:** QA-008 ainda exige corpus real e resolução de fragmentação lexical.
- **UNVERIFIED:** métricas reais de investigações/dia, diversidade e ganho de informação.
- **BLOCKED_EXTERNAL:** suíte npm bloqueada por lock de `node_modules`; CI deve ser a fonte de confirmação do Worker.
- **INSUFFICIENT_DATA:** não há amostra operacional para transformar os resultados do harness em skill ou maturidade de produção.

Conclusão: as propriedades A–F estão demonstradas no harness determinístico, com limites explicitamente medidos. Isso não constitui evidência de desempenho preditivo ou operacional em produção.
