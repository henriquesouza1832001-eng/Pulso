# Autoridade de armazenamento

## Estado observado em 2026-10-03

O Worker escolhe o backend por requisição. Com `DB_BACKEND=turso`, `TURSO_URL` e `TURSO_TOKEN`, `apps/worker/src/index.ts` substitui `c.env.DB` por `TursoDatabase`; caso contrário usa o binding D1. O `BACKEND_STATUS.md` declara Turso como banco ativo. A conclusão é operacional, não uma verificação remota desta campanha: não houve acesso a credenciais nem alteração de produção.

| Dado | Autoridade atual | Retenção / comportamento | Lacuna de confiabilidade |
|---|---|---|---|
| Eventos, sinais, fontes, Pulso e previsões | backend ativo do Worker (Turso quando configurado; D1 como fallback de código) | sinais/séries/observações: 90 dias; previsões pela tabela | não existe teste integrado Turso-vs-D1 nesta campanha |
| `forecast_registry`, `shadow_results`, `driver_registry` | migrations `database/pending/0008–0010` | registry/shadow: 180 dias | migrations não estão na pasta de deploy D1; aplicação real em Turso não foi comprovada localmente |
| Artefatos de validação | repositório Git | imutáveis por commit | não são dados de produção nem substituem trilha no banco |

## Escrita e falha parcial

O ingest monta statements e chama `db.batch(stmts)`. O adaptador Turso declara batch transacional; o comportamento D1 precisa ser comprovado contra o binding real. O endpoint só devolve sucesso após `batch`; a atualização de `write_budget` é explicitamente best-effort e pode falhar sem tornar a ingestão inválida. Portanto, não há evidência de sucesso parcial silencioso para as tabelas principais, mas tampouco há teste de falha induzida por tabela para D1 e Turso.

## Decisão de promoção

Não promover V2 ou usar `shadow_results` como evidência até que sejam demonstrados: migration aplicada no backend ativo, leitura autenticada do registro, rollback documentado e testes de indisponibilidade Turso/D1. A autoridade de storage permanece **UNVERIFIED**.
