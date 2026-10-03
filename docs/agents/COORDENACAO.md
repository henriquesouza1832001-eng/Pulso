# Coordenação entre agentes (Claude, Codex e humanos)

O PULSO é desenvolvido por várias pessoas e agentes de IA **ao mesmo tempo, no mesmo diretório e na mesma branch** (`hen`). Não criamos uma branch por agente (decisão do dono). Em vez disso, combinamos **quem edita o quê** e **quem commita**, por um barramento de arquivos simples.

## Organização: três frentes e um portão
```text
                         PULSO
        ┌─────────────────┼─────────────────┐
      CODEX            CLAUDE A          CLAUDE B
   (red team)          (engine)          (platform)
        └─────────────────┼─────────────────┘
                          ↓
                  RELIABILITY GATE
                          ↓
                  SHADOW → CANARY
                          ↓
                         PROD
```
| Frente | Nome no quadro | Papel | Donos de pasta (reservas padrão) |
|---|---|---|---|
| **Codex: RED TEAM** | `codex` | confiabilidade, replay, backtest, caos, métricas; tenta quebrar o que os outros fazem e prova o que funciona | `engine/pulso_engine/validation/`, `engine/tests/reliability/`, `docs/engineering/RELIABILITY_LAB.md`, `SYSTEM_RELIABILITY_AUDIT.md` |
| **Claude A: ENGINE** | `claude-motor` | Sentinela, sensores, evidência, contexto, qualidade de dado, modelos V2 | `engine/pulso_engine/research/`, `intelligence/`, `scoring/*_v2.py`, `processing/cluster_refine.py`, `quality.py`, `simulation.py`, `docs/research/`, `docs/CURRENT_ENGINE_STATE.md` |
| **Claude B: PLATFORM** | `claude-hen` | Worker/API, armazenamento (Turso/D1), segurança, observabilidade, integração no pipeline, fontes; front só com autorização | `apps/worker/`, `database/`, `packages/shared/`, `.github/workflows/`, `scripts/`, `pipeline.py`, `client.py`, `models.py`, `flags.py`, `docs/engineering/ENGINE_*`, `docs/api/`, README, AGENTS |

**Como as três se encaixam**
- **Claude A** constrói a inteligência (sempre em paralelo ao V1, atrás de feature flag). **Claude B** a põe no pipeline, no banco e na API com orçamento de escrita e escrita condicional. **Codex** tenta derrubá-la: replay de eventos, cenários de caos, métricas V1 × V2.
- **Nada é promovido sem o Reliability Gate** (`validation/shadow_compare.promotion_gate` e o Reliability Lab do Codex): amostras mínimas, ganho de Brier sobre V1 e sobre o ingênuo, FPR e recall sob controle, calibração sem piora, sem regressão por escopo. O fluxo é `V1 em produção → V2 em SHADOW (só grava) → CANARY (poucos escopos) → PROD`.
- O Codex **não muda comportamento de produção**: ele entrega achados, testes e o veredito do portão. Corrigir o que ele achar é da frente dona do arquivo.
- **Frontend** (`apps/web`) pertence às branches/pessoas do front (`isar`, `art`, `thig`). O Claude B só mexe nele quando o dono pedir e depois de alinhar com quem tem PR aberto lá.
- Merge na `main` é decisão humana (ou autorizada pelo dono); o Claude B confere o CI e faz o merge dos PRs da `hen` quando o dono autorizou.

## Por que arquivos
Agentes de ferramentas diferentes não conseguem se mandar mensagem diretamente. Todos, porém, leem e escrevem a mesma pasta. O barramento `scripts/agentbus.py` guarda o estado em `.agents/` (ignorado pelo git), então funciona na hora, sem rede e sem instalar nada. Se um agente estiver em **outra máquina** (outro clone), o barramento não o alcança: nesse caso a coordenação vai por PR e pelo `docs/BACKEND_STATUS.md`, e o dono repassa o recado.

## Comandos
```text
py scripts/agentbus.py register <nome> --role "o que faz"        entra no quadro
py scripts/agentbus.py who                                       agentes, trava de commit, arquivos reservados
py scripts/agentbus.py send <para|all> "msg" --from <nome>       mensagem (1ª linha autoexplicativa)
py scripts/agentbus.py inbox <nome> [--all]                      lê mensagens novas
py scripts/agentbus.py claim <nome> <arquivo-ou-pasta> ...       reserva arquivos (avisa conflito)
py scripts/agentbus.py unclaim <nome> [<arquivo> ...]            libera
py scripts/agentbus.py lock status|acquire <nome> --note "..."|release <nome>   turno de commit
```
Nomes sugeridos: `claude-hen` (backend, Worker, banco, fontes), `claude-motor` (motor Python: sentinela, previsão), `codex`. Um nome por agente, sempre o mesmo.

## Redes de segurança (aprendidas em 2026-10-03)
Dois acidentes no mesmo dia mostraram que regra escrita não basta; agora há ferramenta:
1. **`py scripts/agentbus.py check-staged <nome>` ANTES de todo commit.** Bloqueia (código de saída 1) se você não tem a trava, se não há nada em `git add`, ou se algum arquivo em `git add` está reservado por **outro** agente. Aviso nos arquivos sem dono.
2. **Arquivo compartilhado (`pipeline.py`, `flags.py`...): leia `git diff --cached <arquivo>` antes de commitar.** Na pasta compartilhada o arquivo pode conter edição de OUTRO agente que ainda não subiu o módulo dela; foi assim que o `main` quebrou (import de um módulo ausente). Ao commitar um arquivo, só entra o que é seu: se houver hunk alheio, peça ao dono para subir junto, ou commite os dois lado a lado.
3. **Nunca encadeie `lock acquire` com `;`.** Use `&&`, para uma trava recusada interromper o resto.
4. **Merge só com o CI verde:** `bash scripts/merge_when_green.sh <PR>` espera o CI e recusa mergear se estiver vermelho, cancelado ou sem confirmação. Não use `gh pr merge` direto.
5. Quem tem uma reserva ampla que atrapalha outro agente deve liberar (`unclaim`) quando disser que liberou. Reserva esquecida levou dois agentes a editar o mesmo arquivo.

## Regras
1. **Turno de commit:** só quem tem a trava (`lock acquire`) faz `git add/commit/push`. A trava expira em 45 min sem renovar, para um agente que sumiu não bloquear os outros.
2. **`git add` por nome de arquivo**, nunca `-A` nem `.`. A pasta é compartilhada: um arquivo ainda não commitado de outro agente entraria junto no seu commit.
3. **Reserve antes de editar** (`claim`). Arquivo compartilhado (`pipeline.py`, `contracts.ts`, `ingest.ts`, migrations, workflows, `BACKEND_STATUS.md`): avise com `send all` e prefira composição (arquivo novo) a editar.
4. **Um PR da `hen` aberto por vez.** Quem tem o turno abre o PR, espera o CI e o merge (decisão humana ou autorizada pelo dono), e só então libera a trava.
5. `git pull` antes de commitar; teste antes de subir (`cd engine && py -m pytest`, `npm run typecheck && npm test`).
6. Nunca guarde segredos no barramento nem nas mensagens.
7. Nenhum agente cria branch, edita a `main` ou faz merge sem autorização do dono (`AGENTS.md`).

## Fluxo típico
```text
register codex --role "pesquisa de sensores"
who ; inbox codex
claim codex docs/research/codex/
... edita só o que reservou ...
lock acquire codex --note "docs/research/codex/FONTES.md"
git pull ; git add docs/research/codex/FONTES.md ; git commit ; git push ; abre o PR
(o CI passa e o merge acontece)
lock release codex ; unclaim codex
send all "PR #N mergeado: ..." --from codex
```
