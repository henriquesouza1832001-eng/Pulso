# Contribuindo com o Pulso

## Branches

- `main`: produção. Protegida; ninguém faz push direto.
- `hen`: branch de integração da implementação atual.
- `feat/*`, `fix/*`, `chore/*`: trabalho de cada pessoa, abertas a partir de `hen`.

Antes de qualquer alteração: `git status`, `git branch --show-current` e `git pull`.

## Regras de merge

1. Todo código entra por Pull Request. Sem push direto em `main`.
2. PR de `feat/*`, `fix/*` e `chore/*` vai para `hen`; de `hen` para `main` só com a etapa testada.
3. Mínimo de 1 aprovação de outra pessoa (o autor não aprova o próprio PR).
4. O CI (typecheck, lint e build) precisa estar verde.
5. Conversas do PR resolvidas antes do merge.
6. Branch atualizada com a base antes do merge.
7. Merge por **squash**, com mensagem no formato `tipo: descrição` (`feat`, `fix`, `chore`, `docs`, `refactor`, `test`).
8. Proibido force-push em `main` e `hen`.

## Segurança

- Nunca versionar `.env`, `.dev.vars`, tokens ou chaves. Use Cloudflare Secrets e `.dev.vars.example` como modelo.
- Nenhum secret no frontend.

## Princípio editorial

O Pulso agrega e organiza; não decide quem tem razão. Alegações nunca viram fatos automaticamente, e todo resumo gerado por IA precisa estar ligado às fontes originais.
