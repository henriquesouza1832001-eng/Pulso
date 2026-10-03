# AGENTS.md — regras para agentes de IA (e humanos) no PULSO

**Contexto completo, divisão de tarefas e como entregar: `docs/OVERVIEW_PARA_AGENTES.md`. Passo a passo humano: `docs/ONBOARDING_BACKEND.md`.**

Leia antes de qualquer alteração: `docs/architecture/ARCHITECTURE.md`, `docs/api/API.md`, `docs/SCORING.md`.

## Coordenação com outros agentes (LEIA PRIMEIRO se houver mais de um trabalhando)
Vários agentes (Claude, Codex, humanos) podem editar este repositório **ao mesmo tempo, na mesma pasta e na mesma branch**. Para não sobrescrever ninguém, usem o barramento de arquivos `scripts/agentbus.py` (sem rede, sem instalação). Detalhes em `docs/agents/COORDENACAO.md`.
1. Escolha um nome e entre no quadro: `py scripts/agentbus.py register <nome> --role "o que você faz"`.
2. Antes de editar: `py scripts/agentbus.py who` (quem faz o quê, quem tem o turno de commit, arquivos reservados) e `py scripts/agentbus.py inbox <nome>` (mensagens para você).
3. Reserve o que vai editar: `py scripts/agentbus.py claim <nome> <arquivo-ou-pasta>`. Se der CONFLITO, fale com o dono da reserva (`send`) em vez de editar.
4. **Só quem tem o turno de commit faz `git add/commit/push`**: `py scripts/agentbus.py lock acquire <nome> --note "o que vai subir"`; ao terminar, `lock release <nome>`. `git add` **sempre por nome de arquivo**, nunca `-A` ou `.` (a pasta é compartilhada e o arquivo ainda não commitado de outro entraria junto). Faça `git pull` antes. Um PR da `hen` aberto por vez.
5. Fale com os outros por `py scripts/agentbus.py send <para|all> "primeira linha autoexplicativa..." --from <nome>`.
6. Papéis: `codex` = red team/confiabilidade, `claude-motor` = engine/Sentinela, `claude-hen` = plataforma (Worker, banco, pipeline). Nada é promovido sem o Reliability Gate (shadow → canary → prod); ver `docs/agents/COORDENACAO.md`.
7. Mudou arquivo compartilhado (pipeline, contratos, Worker, migrations, workflows, `BACKEND_STATUS.md`)? Avise com `send all`.

## Sempre
1. `git status` e `git branch --show-current` antes de começar; `git pull` na branch.
2. Trabalhar apenas na branch pessoal de quem pediu (`hen`, `thig`, `art` ou `isar`). Nunca na `main` e **nunca criar outras branches**. Só essas cinco existem.
3. Não sobrescrever nem apagar trabalho de outra pessoa. Se o código dela conflita com a tarefa, **adapte ou peça resolução**; não delete.
4. Não apagar código sem entender suas dependências.
5. Rodar os testes do módulo tocado e `npm run typecheck && npm run build`; Python: `cd engine && py -m pytest`.
6. Verificar o comportamento real (subir o Worker, chamar o endpoint), não só "compilou".
7. Registrar decisões arquiteturais relevantes em `docs/decisions/NNNN-titulo.md`.
8. Atualizar `docs/BACKEND_STATUS.md` (estado, problemas conhecidos, roadmap e registro de mudanças) no mesmo PR de qualquer mudança relevante no backend.

## Nunca
- Commitar secrets: `.env`, `.dev.vars`, tokens, cookies, chaves privadas.
- Mudar contrato silenciosamente. Contratos vivem em `packages/shared/src/contracts.ts` (espelho: `engine/pulso_engine/models.py`) e `docs/api/API.md`. Mudança de contrato = mesmo PR atualiza os 3 + label `contract`.
- Fazer merge automático na `main`. Merge é decisão humana, via PR.
- Contornar autenticação, limites ou termos de uso de qualquer fonte.
- Implementar reconhecimento facial, rastreamento de pessoas ou perfil individual.
- Tratar alegação política como fato.
- Publicar previsão sem probabilidade, incerteza, evidências e método registrados, ou apresentá-la como fato. O PULSO prevê qualquer tema (ver `docs/architecture/PREDICTION.md`), mas sempre como previsão calibrada.
- Coletar de uma fonte sem cumprir `docs/COLLECTION_PROTOCOL.md`.

## Antes de integrar uma fonte externa
Verificar e documentar em `docs/sources/SOURCES.md`: API oficial, termos de uso, rate limits, custo, autenticação, licença, retenção permitida e possibilidade de exibição pública.

## Dono de cada pasta (reduz conflito)
| Pasta | Responsabilidade |
|---|---|
| `apps/web` | React + UI + mapa |
| `apps/worker`, `database/` | Worker, API, D1, infraestrutura Cloudflare |
| `engine/` | Python: coleta, NLP, geolocalização, clustering, scoring |
| `engine/pulso_engine/collectors/<fonte>` | uma pasta por fonte, uma branch `collector/<fonte>` |
| `packages/shared` | contratos (alterar com cuidado) |
