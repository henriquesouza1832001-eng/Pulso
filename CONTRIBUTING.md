# Contribuindo com o Pulso

## Branches

- `main`: produção. Só recebe código por Pull Request vindo da `hen`.
- `hen`: única branch de trabalho desta implementação. Não criamos `feat/*` nem `fix/*`.
- `art`, `isar`, `thig`: branches pessoais de outras pessoas do time.

Antes de qualquer alteração: `git status`, `git branch --show-current` e `git pull`.

## Regras de merge

1. Nada de push direto em `main`: toda mudança entra por PR `hen` → `main`.
2. O CI (typecheck e build) precisa estar verde.
3. O PR segue o template e descreve como testar.
4. Merge por **squash**, com mensagem no formato `tipo: descrição` (`feat`, `fix`, `chore`, `docs`, `refactor`, `test`).
5. Após o merge, a `hen` é atualizada com a `main` (`git pull origin main`), nunca deletada.
6. Proibido force-push em `main` e `hen`.
7. Sem aprovação obrigatória por enquanto (há um só colaborador). Quando entrar mais gente, ligar a proteção de branch exigindo 1 aprovação.

## Rodando localmente

```
npm install
npm run db:migrate   # cria o D1 local
npm run dev
npm run typecheck && npm run build
```

## Segurança

- Nunca versionar `.env`, `.dev.vars`, tokens ou chaves. Use Cloudflare Secrets.
- Nenhum secret no frontend.

## Princípio editorial

O Pulso agrega e organiza; não decide quem tem razão. Alegações nunca viram fatos automaticamente, e todo resumo gerado por IA precisa estar ligado às fontes originais.
