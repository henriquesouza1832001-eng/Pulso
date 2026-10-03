# 0003 — Reddit e X como sensores sociais temáticos (política), nunca como confirmação

**Contexto.** Queremos captar cedo assuntos de política (candidaturas, instituições, eleições) e tensões (protestos, confrontos) que ainda não chegaram aos feeds de notícia. Reddit e X têm APIs oficiais, mas com custo por leitura (X), cota e termos restritivos (exibição, retenção, uso analítico), e o conteúdo é de pessoas, não de redações.

**Decisão.**
1. Só APIs oficiais (`official_api`, classe `SOCIAL`); `config.py` recusa ativar sem `authorization_ref` e revisão humana.
2. Cada fonte social é **temática**: consulta fixa em `query` (e `subreddit` no Reddit) + `categories`; post que o keyword engine não classifica nessas categorias é descartado.
3. Mínimo de dados: título de até 300 caracteres sem links e com `@menções` trocadas por `@usuário`, link para o post, data. Sem autor, texto integral ou perfil.
4. Evento só com fontes sociais fica `DETECTED` (nunca `CONFIRMED`), e a confiança tem teto 40 (SCORING.md).
5. Cadência por `interval_s` sem estado: o agendador roda a cada 5 min e a fonte só roda na sua janela de relógio (`pipeline.is_due`). No X, a busca pede só o intervalo desde a janela anterior (`start_time`), para não pagar duas vezes pelo mesmo post.
6. `429` → `RATE_LIMITED`, `401/403` → `AUTH_ERROR`; nada de nova tentativa no mesmo ciclo.
7. Piloto via `pulso_engine.pipeline --source <id>` (aceita fonte desativada, recusa `--push`).

**Consequências.** Ligar uma fonte social é decisão de conformidade e custo, não de código: preencher a ficha em `docs/sources/SOURCES.md`, revisar, rodar ≥ 48 h em piloto e só então `enabled: true`. Atrasos do agendador podem pular uma janela (aceitável; lacunas são registradas, não preenchidas). As consultas iniciais são termos institucionais em português, sem nomes de políticos nem comunidades de viés declarado, para não enviesar a amostra; ajustes passam por revisão.
