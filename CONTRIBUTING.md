# Contribuindo com o Pulso

Leia também o [AGENTS.md](AGENTS.md) (vale para humanos e agentes de IA).

## Branches
- `main`: produção, protegida. Só recebe código por Pull Request.
- Existem **somente** estas branches: `main`, `hen`, `thig`, `art` e `isar`. Cada pessoa trabalha na sua (a `hen` é do backend).
- **Não criar outras branches** (`feature/*`, `infra/*`, `collector/*` etc.). O trabalho de cada módulo acontece na branch pessoal de quem o faz.

Antes de começar: `git status`, `git branch --show-current`, `git pull`.

## Fluxo
sua branch → commit → push → Pull Request para `main` → CI verde → review → merge → `main` → atualize sua branch com `git pull origin main`.

## Regras de merge
1. Nada de push direto em `main`; proibido force-push em `main`.
2. CI verde: typecheck, build, testes do Worker/shared e testes Python.
3. PR segue o template; mudança de contrato leva label `contract` e atualiza `contracts.ts`, `models.py` e `docs/api/API.md`.
4. Nenhum secret no diff.
5. Merge por **squash**, mensagem `tipo: descrição` (`feat`, `fix`, `refactor`, `infra`, `collector`, `docs`, `test`). Nada de `update`, `teste`, `novo`.
6. Quando houver mais de uma pessoa ativa, ligar a proteção de branch na `main` exigindo 1 aprovação.

## Rodando localmente
```
npm install
npm run db:migrate && npm run db:seed     # D1 local com dados fictícios
npm run dev:worker                         # API em :8787 (copie apps/worker/.dev.vars.example para .dev.vars)
npm run dev:web                            # React em :5173 (proxy para a API)
cd engine && py -m pip install -e ".[dev]" && py -m pytest
# verificação operacional (ver docs/RUNBOOK.md): py -m pulso_engine.audit (roda cada fonte) e py -m pulso_engine.healthcheck (saúde da produção)
```

## Segurança
Nunca versionar `.env`, `.dev.vars`, tokens ou chaves. Produção usa `wrangler secret put`. Nenhum secret no frontend.

## Princípio editorial
O Pulso observa, correlaciona, localiza, confirma, explica e visualiza. Sinal fraco não é fato; alegação política não vira fato; IA não é fonte.
