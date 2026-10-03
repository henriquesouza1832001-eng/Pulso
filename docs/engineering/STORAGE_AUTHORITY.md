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

## Ensaio de falha do ingest (claude-hen, RT-005)

`apps/worker/tests/storage-chaos.test.ts` roda o `/api/ingest` REAL sobre SQLite real, por trás de um servidor Hrana de mentira com injeção de falha (`tests/helpers/hrana.ts`). Isso prova a lógica do Worker e do adaptador Turso; **não** prova o servidor remoto nem o binding D1 (o D1 usa o mesmo SQL, mas não há ensaio automatizado dele).

| Falha injetada | Comportamento comprovado |
|---|---|
| Rede cai antes do servidor agir | Worker responde `500 internal_error` com `request_id`; **nada** foi gravado; o reenvio do mesmo lote grava exatamente uma vez |
| Servidor responde HTTP 500 | idem |
| Servidor grava e a resposta se perde | o dado **está** no banco (nada se perde); o reenvio não cria linha nova; só o batimento de saúde (`source_health`) muda |
| Instrução falha no meio do lote | o adaptador desfaz tudo (BEGIN/COMMIT/ROLLBACK); zero linhas parciais |

Dois achados do ensaio:
1. **Idempotência (corrigido):** `events`, `series`, `forecasts` e `pulse_history` regravavam o mesmo conteúdo no reenvio (cada uma contava como escrita). Agora o upsert é condicional (`WHERE` só quando algo mudou), como já eram as tabelas novas. Reduz o gasto do orçamento de escrita e remove a regravação em retry. `source_health` é a **única exceção intencional**: é estado de batimento (`last_check`/`last_success` avançam a cada ciclo).
2. **Limitação conhecida (aberta):** o contador `write_budget` é gravado DEPOIS do lote, em separado. Se a resposta se perde depois do commit, o dado está salvo mas o orçamento do dia fica **abaixo** do real (subestima, nunca superestima). Efeito: o governador pode ser otimista por um lote. Teste documenta o comportamento.

Matriz por tipo de dado (backend ativo = Turso; D1 = reserva de código):

| Dado | Autoritativo | Escrita | Leitura | Se a escrita falha |
|---|---|---|---|---|
| eventos, sinais, fontes, Pulso, séries, previsões | banco ativo | `/api/ingest`, 1 transação por lote, upsert condicional | rotas `/api/*` | `500` + `request_id`; nada parcial; o Engine reenvia o mesmo lote |
| `forecast_registry`, `shadow_results`, `driver_registry`, `calibrators`, `investigations`, `signal_observations` | banco ativo (migrations em `database/pending/`) | idem, no mesmo lote; descartados pelo governador em `economy`/`critical` | `/api/admin/*` | idem; em `economy` a observabilidade científica é suprimida de propósito |
| artefatos de validação | Git | commit | arquivos | n/a |
