# Ativar Reddit, Bluesky e X (quando as chaves chegarem)

Tudo já está pronto no código e **desligado**. Falta só a chave de cada rede. Cada fonte social nasce com `enabled: false` e o
validador (`config.py`) **recusa** ligá-la sem revisão e autorização registradas: é de propósito.

## Use só chaves emitidas para você
Chave "pública" achada em repositório, fórum ou post **não é sua**. Usá-la viola os termos da rede, pode ser crime e
queima a nossa conta junto. Só entram chaves criadas na conta do projeto.

## 1. Criar as chaves
| Rede | Onde | O que guardar |
|---|---|---|
| **Bluesky** (grátis, imediato) | Criar uma conta só do bot. Em Configurações > Privacidade e segurança > **Senhas de app**, criar uma senha. | `BLUESKY_HANDLE` (ex.: `pulso-bot.bsky.social`) e `BLUESKY_APP_PASSWORD` (`xxxx-xxxx-xxxx-xxxx`). Nunca a senha da conta. |
| **Reddit** (exige aprovação prévia) | reddit.com/prefs/apps, app do tipo "script", depois o pedido de acesso à API. | `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET` e `REDDIT_USER_AGENT` (formato `web:pulso-engine:0.1 (by /u/SUA_CONTA)`). |
| **X** (plano pago) | developer.x.com, plano com busca recente (confira o preço atual). | `X_BEARER_TOKEN`. |

Guardar cada um como **segredo do GitHub** (Settings > Secrets and variables > Actions). Nunca em arquivo, chat ou issue.

## 2. Conferir que a chave funciona
Actions > **Verificar chaves sociais** > Run workflow. Cada rede responde `OK (contagens)`, `sem chave` ou `FALHOU` com a causa
provável (chave recusada, limite). O log é público, então só mostra contagens, nunca conteúdo.

## 3. Piloto de 48 h (COLLECTION_PROTOCOL.md §3)
Com os segredos presentes, a coleta normal já roda o **piloto sem enviar nada** (passo "Piloto dos sensores sociais" do
`collect.yml`): mostra só contagens por fonte. Olhar ao longo de 48 h: volume, quantos viram sinal depois do filtro de importância,
e se algo é ruído. Ajustar `queries`/`query`/`categories` em `engine/config/sources.json` se precisar.

## 4. Ligar
Por fonte, em PR (de `hen` para `main`): preencher `reviewed_by`, `reviewed_at`, `authorization_ref` e `enabled: true`.
Depois do merge, conferir em `/api/health` que a fonte aparece ONLINE e que os sinais sociais entram como classe SOCIAL.

## Como o motor trata rede social
- Classe `SOCIAL`, confiabilidade baixa: **detecta, nunca confirma**. Só ganha peso junto de imprensa ou fonte oficial.
- Links e @menções saem do texto; autor, texto integral e métricas não são guardados. O link do Bluesky usa o DID (opaco), não o @.
- Filtro de importância e `categories` por sensor: só desastre, política e infraestrutura entram.
- Erros viram estado de saúde: 429 `RATE_LIMITED`, 401/403 `AUTH_ERROR` (alerta humano, sem insistir).

## O que NÃO existe
O X não tem caminho legítimo sem a API paga: tudo fora dela é raspagem, que não fazemos. Enquanto isso, o X chega indiretamente
pelas notícias que citam posts oficiais (portais que já coletamos).
