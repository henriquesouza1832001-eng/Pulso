# Coordenação entre agentes (Claude, Codex e humanos)

O PULSO é desenvolvido por várias pessoas e agentes de IA **ao mesmo tempo, no mesmo diretório e na mesma branch** (`hen`). Não criamos uma branch por agente (decisão do dono). Em vez disso, combinamos **quem edita o quê** e **quem commita**, por um barramento de arquivos simples.

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
