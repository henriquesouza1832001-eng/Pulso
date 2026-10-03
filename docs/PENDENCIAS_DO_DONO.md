# Pendências que só o dono do projeto pode resolver

O que depende de uma conta, um cadastro, um pagamento ou uma decisão sua. Tudo o que dava para fazer sem isso já está feito e documentado (ver `docs/BACKEND_STATUS.md`). Ordenado por impacto.

## 1. Chaves e cadastros (destravam fontes que já têm código ou desenho pronto)
| O quê | Para quê | Como | Custo |
|---|---|---|---|
| **Chave da API de webcams do Windy** | Câmeras ao vivo na plataforma para todos verem (a única via **sem pedir permissão a órgão público**, com atribuição e link) | Cadastro em https://api.windy.com/webcams (plano gratuito). Guardar como secret `WINDY_API_KEY` no Worker (`wrangler secret put`). Depois de ter a chave, um agente deve **chamar o endpoint uma vez e salvar a resposta real** antes de escrever o mapeador (o esquema só é visível com chave). Ver `docs/sources/CAMERAS.md`. | Gratuito (imagens com atraso de 10 min no plano gratuito) |
| **Aprovação do app no Reddit** | Coletor do Reddit (já escrito, desligado) | Pedido de acesso à API (Responsible Builder Policy exige aprovação prévia). Secrets: `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT`. | Gratuito para uso não comercial; aprovação pode demorar |
| **Plano da API do X** | Coletor do X pela API oficial (já escrito, desligado) | Não existe leitura gratuita e legítima. Secret `X_BEARER_TOKEN`, **com teto de gasto**. | Pago por leitura |
| **Conta no Bluesky + *app password*** | Rede social com muito mais volume em português que o Mastodon (medido: o Mastodon quase não tem desastre em português) | Criar conta, gerar *app password*; secrets `BSKY_HANDLE` e `BSKY_APP_PASSWORD`. O adaptador só deve ser escrito com a credencial em mãos, para validar o formato da resposta. | Gratuito |

## 2. Revisão humana de conformidade (~95 fontes ativas com `PENDENTE`)
O catálogo foi ativado por decisão sua (ADR 0006), mas `terms_url`, `reviewed_by` e `reviewed_at` ainda estão `PENDENTE`. Antes de a plataforma ser pública em larga escala, alguém precisa, **para cada fonte** (lista em `docs/sources/CATALOGO_FONTES.md`):
1. Abrir os termos do veículo/órgão e confirmar: pode coletar o RSS; pode exibir **título e link com atribuição**; pode usar a série em previsões.
2. Preencher `terms_url`, `reviewed_by` (seu nome) e `reviewed_at` em `engine/config/sources.json`.
3. Se algum termo proibir, desligar a fonte (`"enabled": false`). O aviso de conformidade some quando todas estiverem preenchidas.
Atenção especial: INPE, Defesa Civil (IDAP), InfoDengue, Banco Central e USGS exigem **citar a fonte**; a plataforma já mostra título e link, confirme que mostra o nome.

## 3. Acompanhar nos primeiros dias
- **Cloudflare D1** (painel > D1 > pulso > Metrics): linhas **escritas** (limite gratuito 100 mil/dia) e **lidas** (5 milhões/dia). A estimativa é ~12 mil escritas e 3 a 4 milhões de leituras por dia, mas só o painel confirma. Se as leituras passarem de ~4 milhões, espaçar o ciclo para 10 min ou migrar para o plano pago (ver `docs/decisions/0006`, "Orçamento do D1").
- **E-mails de falha do GitHub Actions**: o workflow `Saúde da produção` falha e avisa quando a coleta para, o banco cai ou a maioria das fontes sai do ar. Diagnóstico: `docs/RUNBOOK.md`.
- **Previsões**: aparecem sozinhas quando houver histórico (Pulso: ~3,5 h; volume por categoria: > 25 h). O histórico de acertos fica em `/api/forecasts/track-record`. Nada disso é acurácia comprovada até haver semanas de dados.

## 4. Datas e riscos conhecidos
- **Domingo, 4/10/2026: primeiro turno das eleições.** A coleta deve ter pico de política e internacional. O PULSO não coleta a apuração do TSE (formato do arquivo de resultados de 2026 não verificado); a cobertura vem da imprensa e do Senado/Câmara. Integrar a apuração oficial do TSE é a próxima fonte natural (verificar o endereço dos arquivos de resultado assim que o TSE publicar).
- **`GH_DISPATCH_TOKEN` vence em 31/12/2026**: renovar antes (o Cron deixa de disparar a coleta).
- **Um token da Cloudflare foi colado em chat** (registrado no `BACKEND_STATUS.md`): deve ser **revogado** se ainda não foi.
- **Fontes bloqueadas de nuvem**: o MetSul responde da sua rede e dá 403 no GitHub Actions; está desligado. Não se contorna bloqueio.
- **Sem cobertura regional própria** de SP capital, RJ, PE e CE (os feeds do G1 desses estados estão parados desde ~2018; o do governo de SP exige passar por desafio anti-robô). MG tem BHAZ e UAI.

## 5. O que o sistema NÃO faz (e por quê)
- **Não raspa redes sociais com login por navegador nem tenta passar captcha.** É um limite do agente que trabalhou neste projeto, independente das regras do repositório; as fontes abertas e oficiais cobrem o essencial (ver `docs/sources/SOURCES.md`).
- **Não afirma acurácia** que ainda não mediu: os backtests em `tests/` são sintéticos e provam a mecânica; só dados reais provam acerto.
