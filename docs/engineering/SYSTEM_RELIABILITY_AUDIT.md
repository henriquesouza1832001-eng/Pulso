# System Reliability Audit

Data: 2026-10-03. Escopo: revisão estática, testes locais e ataques reprodutíveis; sem credenciais, escrita remota ou ativação V2.

## Estado Git

- Referência inicial da campanha: `30442b3` em `hen`; `origin/main`: `66b07c0`.
- Mudanças anteriores desta campanha: validação de métricas (`4e69fce`), manifesto golden incompleto (`67e5adc`) e bloqueio de desfecho no replay (`30442b3`).
- Arquivos não rastreados de `claude-motor` foram preservados e não fazem parte desta auditoria.

## Reliability Lab e métricas

O laboratório isolado existe em `engine/pulso_engine/validation/`. Brier, log loss, ECE, classificação, cobertura e lead time têm testes de borda. A campanha reproduziu Brier `2.25` para probabilidade `1.5`; o reparo agora rejeita probabilidade não finita/fora de `[0,1]`, outcome fora de `{0,1}`, bins/cutoff inválidos e diferencia F1 zero de ausência de denominador.

## Replay e leakage

`ReplayItem.available_at` usa a última marca disponível entre publicação, observação, fetch e confirmação. O ataque encontrou que `payload` genérico podia carregar outcome futuro. `outcome`, `resolved_at` e `resolution` são agora proibidos, com regressão. O `forecast_registry` também passou a registrar `data_cutoff` UTC dentro do snapshot canônico e recusa timestamps ingênuos. Ainda não há schema por feature, snapshot de baseline separado, nem teste contra valores futuros escondidos em campos semanticamente equivalentes: **P1**.

## Storage, Worker e migrations

Ver [STORAGE_AUTHORITY.md](STORAGE_AUTHORITY.md). Migrations V2 estão em `database/pending`, e o budget remove shadow/driver fora de modo normal. Ingest/admin usam Bearer fail-closed, Zod e SQL parametrizado. Não há rate limit/WAF, credencial separada para admin, nem ensaio de falha Turso/D1: **P1**.

## Geo, fontes e frontend

Geo V2 está OFF por flag. O ataque de falsa precisão reproduziu aeroporto, rio, bairro e homônimo como cidades; PR #69 fechou os quatro casos com regressões. No corpus editorial de 14 manchetes, V1 acertou 1/4 cidades explícitas e V2 4/4; ambos tiveram 0/8 falsas precisões nos negativos inequívocos. A amostra é pequena, o caso Rio Branco permanece `DISPUTED` e isto não é métrica histórica nem autoriza a flag.

Há 282 fontes ativas: todas têm `access`, retenção e display; somente 9 têm termos não pendentes e somente 3 têm `reviewed_by/reviewed_at` concluídos. Isso impede classificar a confiabilidade de fonte como validada. O front exibe sinais/fontes e confiança do evento; não foi auditada uma interface pública de previsão com calibração, incerteza e proveniência completa.

## Prioridades

| Prioridade | Achado | Próxima ação segura |
|---|---|---|
| P0 corrigido | outcome em payload de replay | manter teste de regressão e criar schema de features por modelo |
| P1 | precisão falsa de Geo V2 | bloquear contextos adversariais e medir corpus antes de flag |
| P1 | storage/migrations e shadow incompletos | ensaio local Turso/D1, migration e rollback documentados |
| P1 | stale data não distinto de HTTP ONLINE | adicionar freshness por conteúdo, sem mudar status para NORMAL |
| P1 | 279 fontes sem revisão | revisão humana por fonte antes de ampliar exposição |
| P2 | sem rate-limit/WAF e token admin compartilhado | hardening de plataforma com teste de integração |

## Lacunas quantitativas

Não existem casos históricos completos, negativos completos ou shadow live suficiente. Por isso Brier Skill, ECE operacional, FPR, recall, falsos alertas/dia e lead time histórico são **N/A**, não zero nem estimativa.
