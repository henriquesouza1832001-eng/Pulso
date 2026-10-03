# Fontes

Cada integração documenta aqui: fonte, API, limites, credenciais, dados coletados, frequência, fallback e termos relevantes. **Antes de implementar**, verifique API oficial, termos, rate limits, custo, autenticação, licença, retenção e exibição pública. Nunca contorne autenticação ou limites.

| Fonte | Classe | Adaptador | Status |
|---|---|---|---|
| (modelo) Agência Brasil | NEWS_HIGH | RSS | ⏳ `collector/news-rss` |
| (modelo) PRF | OFFICIAL | API | ⏳ verificar termos |
| Agência Senado | OFFICIAL | RSS | ✅ ativa desde 2026-10-03 (piloto encurtado, ver ficha) |
| Agência Câmara de Notícias | OFFICIAL | RSS | ✅ ativa desde 2026-10-03 (piloto encurtado, ver ficha) |
| INMET — avisos meteorológicos | OFFICIAL | API de avisos (`inmet`) | ✅ ativa desde 2026-10-03 (piloto encurtado, ver ficha) |
| Reddit | SOCIAL | API oficial OAuth (piloto desativado) | ⏳ exige aprovação prévia do Reddit (desde nov/2025) |
| X | SOCIAL | API v2 busca recente (piloto desativado) | ⏳ orçamento/termos pendentes |
| GDELT — cobertura de notícias | NEWS_REGIONAL | API aberta (`gdelt`) | 🧪 desligada: **não validada ao vivo** (429 persistente mesmo a 7 s de intervalo e consulta vazia em 2026-10-03) |
| Mastodon — hashtags de impacto | SOCIAL | API aberta (`mastodon`) | 🧪 proposta (`enabled: false`), aguarda revisão |
| USGS — terremotos significativos | OFFICIAL | GeoJSON aberto (`usgs`) | 🧪 proposta (`enabled: false`), aguarda revisão |
| **Catálogo RSS** (imprensa nacional, regional, internacional e órgãos oficiais) | NEWS_HIGH / NEWS_REGIONAL / OFFICIAL | RSS/Atom/RDF (`rss`) | ✅ ativos, `revisão pendente`: ver [CATALOGO_FONTES.md](CATALOGO_FONTES.md) |
| Trânsito, câmeras públicas | — | — | ver [CAMERAS.md](CAMERAS.md) |

## Modelo de ficha
```
Fonte / URL:
Tipo de acesso (RSS, API, feed):
Autenticação e secrets necessários:
Limites e custo:
Dados coletados e retenção permitida:
Frequência:
Fallback se cair:
Termos relevantes (link):
Exibição pública permitida:
```

## Agência Senado — ATIVA
```
Fonte / URL: https://www12.senado.leg.br/noticias/feed/todasnoticias/RSS
Tipo de acesso: RSS público (robots.txt: "User-agent: * Disallow:" — sem bloqueio)
Autenticação e secrets: nenhum
Limites e custo: gratuito; sem limite publicado; cadência 300 s
Dados coletados: título, resumo ≤ 500 caracteres, link, data, autor (jornalista, exigido no crédito); retenção 90 dias
Frequência: 300 s
Fallback: Agência Câmara + G1/Folha/UOL (cobertura política); futuro: API de Dados Abertos do Senado
Termos: https://www12.senado.leg.br/noticias/politica-de-uso — "A reprodução de matérias e fotografias é livre,
  desde que não haja descaracterização de conteúdo e mediante a citação da Agência Senado e do autor."
Exibição pública: sim, título + link com crédito "Agência Senado" (headline_link). Não cobre explicitamente
  uso automatizado/agregação; exibimos só título e link, sem alterar o texto.
Classe OFFICIAL: canal da própria instituição sobre os próprios atos (votações, agenda, sessões). Em temas
  externos ao Legislativo, tratar como cobertura, não como confirmação (revisar se gerar falso CONFIRMED).
```
Piloto em 2026-10-03: 15 itens/rodada, ONLINE, quase todos POLITICS (eleições, plenário, PECs).

## Agência Câmara de Notícias — ATIVA
```
Fonte / URL: https://www.camara.leg.br/noticias/rss/ultimas-noticias
Tipo de acesso: RSS público (robots.txt bloqueia só bots de IA/treino e áreas administrativas; o RSS não)
Autenticação e secrets: nenhum
Limites e custo: gratuito; sem limite publicado; cadência 300 s
Dados coletados: título, resumo ≤ 500 caracteres, link, data; retenção 90 dias
Frequência: 300 s
Fallback: Agência Senado + imprensa; futuro: API de Dados Abertos da Câmara (dadosabertos.camara.leg.br)
Termos: guia para jornalistas (terms_url): reprodução livre de notícias com a assinatura "Agência Câmara Notícias".
  O feed declara "Copyright(C) Câmara dos Deputados". Confirmar na revisão que exibir título + link é coberto.
Exibição pública: título + link com crédito "Agência Câmara Notícias" (headline_link)
Classe OFFICIAL: mesma justificativa da Agência Senado.
```
**Ativação (2026-10-03):** Senado, Câmara e INMET ligados por decisão de Arthur266760 (`reviewed_by`), com piloto de poucas horas em vez das 48 h do protocolo §3 (Senado/Câmara ONLINE no Actions; INMET testado localmente). Acompanhar `source_health` nos primeiros dias; se houver erro recorrente ou falso positivo, voltar `enabled: false` (o painel remove a fonte sozinho). Piloto: `py -m pulso_engine.pipeline --source agencia-senado --source agencia-camara`.

## INMET — avisos meteorológicos — ATIVA
```
Fonte / URL: https://apiprevmet3.inmet.gov.br/avisos/ativos (JSON; mesma base do RSS /avisos/rss e de avisos.inmet.gov.br)
Tipo de acesso: dados abertos, sem autenticação
Autenticação e secrets: nenhum
Limites e custo: gratuito; sem limite publicado; cadência 900 s (avisos mudam em horas)
Dados coletados: tipo do aviso, severidade, UFs, início/fim, 1º texto de "riscos" (≤ 500); retenção 90 dias.
  Não guardamos polígono nem lista de municípios (geo no nível de UF).
Frequência: 900 s
Fallback: notícias (Agência Brasil, G1...) e, futuro, Defesa Civil/CEMADEN
Termos: comentário de licença no RSS oficial: "O conteudo deste site, podera ser reproduzido desde que citada
  a fonte, excetuando os casos especificados em contrario e os conteudos replicados de outras fontes."; <copyright>public domain</copyright>
Exibição pública: sim, com crédito "INMET" e link para o aviso
Classe OFFICIAL: órgão federal responsável pelos avisos meteorológicos.
```
Regras: só `hoje` (vigentes), nunca `futuro`; descarta vencidos/encerrados e, por padrão, "Perigo Potencial" (`min_severity`). Um sinal por UF; "Grande Perigo" → `EMERGENCY`, "Perigo" → `WEATHER` (ADR 0004). Piloto em 2026-10-03: ONLINE, aviso de acumulado de chuva (Perigo) → 3 eventos (MG, ES, RJ).

## Reddit e X de clima (`reddit-clima`, `x-clima`) — PILOTO DESATIVADO
Mesmo modelo dos sensores de política (mesmas comunidades e `subreddit_states` no Reddit), com consulta de enchente, alagamento, deslizamento, temporal, vendaval, granizo, queimada, onda de calor, estiagem, desabrigados, Defesa Civil e estado de calamidade; `categories`: WEATHER, EMERGENCY, INFRASTRUCTURE. Mesmas pendências de autorização. **Custo do X:** `x-clima` dobra o teto de leituras (até 1.920/dia somando os dois); decidir se liga só um.

## Piloto Reddit — NÃO ATIVO
**Situação (verificada em 2026-10-03):** pela [Responsible Builder Policy](https://support.reddithelp.com/hc/en-us/articles/42728983564564-Responsible-Builder-Policy), *todo* acesso à Data API exige pedido e aprovação explícita (inclusive não comercial); uso comercial exige aprovação escrita. O RSS público (`/r/<sub>/.rss`) **não** é alternativa: o `robots.txt` do Reddit é `Disallow: /` e a [Public Content Policy](https://support.reddithelp.com/hc/en-us/articles/26410290525844-Public-Content-Policy) restringe o uso. Caminho: abrir o pedido de acesso descrevendo o caso de uso (título + link de posts de r/brasil sobre política, contagem agregada, sem dados de usuários, sem treino de IA) e aguardar.
- API oficial: OAuth client credentials `POST https://www.reddit.com/api/v1/access_token`; leitura `GET https://oauth.reddit.com/r/{subreddit}/search?q=…&restrict_sr=on&sort=new&t=day` (ou `/new` sem `query`) ([referência](https://www.reddit.com/dev/api/)). Sem scraping. Escopo piloto: `r/brasil` com busca por termos institucionais/eleitorais em português (`query` em `sources.json`); só ficam posts classificados em `categories` (POLITICS, PROTEST, SECURITY, INTERNATIONAL). Comunidades aceitam `a+b`; incluir outras só após revisão humana (evitar comunidades de viés declarado).
- Credenciais: `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET` e `REDDIT_USER_AGENT` (formato exigido pelo Reddit: `<plataforma>:<app>:<versão> (by /u/<conta>)`), somente no Engine, em secrets do Actions; app/acesso sujeitos à aprovação do Reddit. Sem credenciais neste repositório.
- Limites/custo: dependem do acesso aprovado e do acordo; confirmar por escrito a cota atribuída antes de ligar. No máximo 25 resultados por consulta, 1 consulta a cada 15 min no piloto; revalidar cadência contra cota. 429 não será contornado.
- Dados: piloto só título (até 300 caracteres), URL e data; sem nome de usuário, texto integral ou perfil. `retention_days: 1` é proposta técnica, **não** autorização para retenção. Sem coleta em produção, exibição ou uso em previsão enquanto não houver permissão específica.
- Licença/termos: [Data API Terms](https://redditinc.com/policies/data-api-terms) e [Developer Terms](https://redditinc.com/policies/developer-terms); uso comercial ou além do permitido exige acordo separado; checar direitos de exibição, armazenamento, derivados/aggregados, exclusões e eliminação ao encerrar acesso. Revisão: PENDENTE.
- Fallback: RSS já ativo; falha de social nunca bloqueia a coleta. Não se conclui que postagem relata fato verdadeiro.

## Piloto X — NÃO ATIVO
- API oficial: [busca recente v2](https://docs.x.com/x-api/posts/search/introduction) `GET /2/tweets/search/recent`, OAuth2 app-only com `X_BEARER_TOKEN` no Engine/Actions. Consulta piloto: termos de eleição, candidatura, STF/TSE/Congresso/Senado/Câmara, impeachment, CPI, manifestação/protesto, com `lang:pt -is:retweet -is:reply` (ver `query` em `sources.json`; sem nomes de políticos). Pede só `start_time` = último `interval_s`, para não reler (e pagar de novo) posts já vistos. Posts fora de `categories` são descartados após a leitura (o custo já ocorreu: calibrar a consulta reduz gasto).
- Custo/cota: [preços atuais](https://docs.x.com/x-api/getting-started/pricing) são por recurso retornado; exemplo documentado US$0,005/post lido (confirmar no console antes de contratar); [limites](https://docs.x.com/x-api/fundamentals/rate-limits) variam por endpoint/plano. Piloto limitado a 10 itens a cada 15 min = até 960 leituras/dia se todos os ciclos retornarem 10 itens, sujeitas a cobrança; **configurar teto de gasto no console antes de ativar**. Não paginar automaticamente.
- Dados: título de até 300 caracteres (sem links; `@menções` viram `@usuário`), URL e data, sem autor/texto integral/perfil; retenção 1 dia apenas proposta. [Acordo de desenvolvedor](https://docs.x.com/developer-terms/agreement): conferir exibição, remoção/edição de posts, uso analítico, direitos sobre dados derivados e histórico antes de ativar. Exibição pública e previsões pendentes de aprovação/revisão humana.
- Fallback: RSS de notícias; 401/403/429: parar e alertar, nunca contornar limites. Revisão: PENDENTE.

**Como rodar o piloto (local ou Actions, sem enviar):** exporte as credenciais e rode `py -m pulso_engine.pipeline --source reddit-politics --source x-politics`. A CLI aceita fonte desativada nesse modo e recusa `--push`. Respostas 429 viram `RATE_LIMITED` e 401/403 `AUTH_ERROR` em `source_health`, sem nova tentativa no ciclo. Decisão: `docs/decisions/0003-sensores-sociais-reddit-x.md`.

**Piloto automático no Actions:** o `collect.yml` tem o passo "Piloto dos sensores sociais (sem envio)". Ele não faz nada até existirem os secrets; criado `REDDIT_CLIENT_ID`+`REDDIT_CLIENT_SECRET` e/ou `X_BEARER_TOKEN`, a fonte correspondente passa a rodar na sua janela de `interval_s` (`--respect-interval`), sem `--push`, e o log mostra só saúde e contagem por categoria (fonte `metrics_only`; o repositório é público). Para encerrar o piloto, apague o secret. Avaliar as 48 h pelos logs do workflow "Coleta".

**Checklist para ambos:** documentar autorização/ref do contrato, revisão por pessoa e data; confirmar licença, exibição pública, agregação para previsão, retenção/exclusão e processamento de remoções; adicionar credenciais só em secrets; piloto de ≥48 h sem `--push`; testar a recuperação de falhas e orçamento antes de alterar `enabled` para `true`. O pipeline atual é centrado no Brasil; cobertura mundial confiável demanda decisão arquitetural de escopo geográfico/contratos antes de publicação global.

## Ficha: GDELT (`gdelt-br`)
```
Fonte / URL: GDELT DOC 2.0, https://api.gdeltproject.org/api/v2/doc/doc
Tipo de acesso: dados abertos (sem chave).
Autenticação e secrets: nenhum.
Limites e custo: gratuito; 1 requisição a cada 5 s (o coletor faz UMA por rodada). Responde 429/aviso de texto se exceder; o coletor sinaliza RATE_LIMITED.
Dados coletados e retenção: título, link, data do artigo (sem texto integral). Retenção 90 dias.
Frequência: 900 s (o índice do GDELT atualiza a cada ~15 min).
Fallback se cair: as demais fontes de notícia (RSS) seguem.
Termos relevantes: https://www.gdeltproject.org/about.html (citar a fonte).
Exibição pública permitida: headline_link.
```

## Ficha: Mastodon (`mastodon-impacto`)
```
Fonte / URL: GET https://<instância>/api/v1/timelines/tag/<hashtag> (linha do tempo pública)
Tipo de acesso: API pública oficial do Mastodon, sem login.
Autenticação e secrets: nenhum.
Limites e custo: gratuito; limites por instância (padrão 300 req/5 min). 8 hashtags por rodada.
Dados coletados e retenção: texto (<= 500 car.), link e data. NENHUM autor ou perfil é guardado. Retenção 30 dias.
Frequência: 900 s.
Fallback se cair: uma instância/hashtag fora do ar é ignorada; as outras seguem.
Termos relevantes: termos de cada instância (confirmar mastodon.social antes de ativar).
Exibição pública permitida: a confirmar (por ora headline_link).
Filtro: processing/importance.py (só desastre/vítimas/emergência) + descarte de notícia de outro país.
Papel: detecta, nunca confirma sozinho (classe SOCIAL).
```

## Ficha: USGS (`usgs-terremotos`)
```
Fonte / URL: https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_week.geojson
Tipo de acesso: dados abertos (GeoJSON), sem chave.
Limites e custo: gratuito; o feed atualiza a cada minuto, usamos 900 s.
Dados coletados e retenção: título, link, data; coordenadas só se dentro do Brasil. Retenção 90 dias.
Termos relevantes: domínio público do governo dos EUA, citar a fonte.
Exibição pública permitida: sim (headline_link).
Papel: entra como INTERNATIONAL; abalos relevantes no exterior contam como contexto, não como evento nacional.
```

## Catálogo RSS em escala (2026-10-03)
```
Fontes: ver CATALOGO_FONTES.md (gerado de engine/config/sources.json).
Tipo de acesso: feeds RSS/Atom/RDF públicos publicados pelo próprio veículo ou órgão (access = public_feed).
Autenticação e secrets: nenhum.
Limites e custo: gratuito. Coleta em paralelo (8 simultâneas), User-Agent identificado, timeout de 15 s, resposta de no máximo 5 MB.
Dados coletados e retenção: título, resumo curto (<= 500 car.), link, data. Retenção 90 dias. Sem texto integral.
Frequência: 300 a 900 s por fonte (is_due respeita interval_s).
Fallback se cair: cada fonte é isolada; falha vira source_health e não derruba o ciclo.
Termos relevantes: terms_url = PENDENTE na maioria; um humano precisa conferir os termos de cada veículo (COLLECTION_PROTOCOL §4).
Exibição pública permitida: headline_link (título + link com atribuição).
Decisão: o dono do projeto autorizou ativar o catálogo mesmo com a revisão pendente (ADR 0006). O aviso de conformidade continua sendo emitido (agregado).
Critérios de entrada: testado ao vivo com o coletor real; publicação recente; sem filiação política declarada;
  feeds em inglês ficam de fora enquanto o vocabulário for em português; feeds que exigem contornar bloqueio (ex.: governo de SP com desafio anti-robô) NÃO entram.
Leitor tolerante: gzip (com limite na saída), RSS 1.0/RDF (gov.br), '&' solto e entidades HTML; declarações <!ENTITY seguem recusadas.
Cobertura regional: G1 de 17 estados; ES, SC, PA, MA, AM, RN, BA, DF, SP (Metrópoles), RJ (prefeitura) e GO (governo) por portais locais.
  Lacunas: não há RSS regional utilizável para SP capital, RJ, MG, PE e CE (os feeds do G1 desses estados estão parados desde ~2018).
```
