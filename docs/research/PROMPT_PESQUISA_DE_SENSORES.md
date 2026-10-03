# Prompt de pesquisa de sensores do PULSO (versão para agentes de IA e desenvolvedores)

> Uso: colar o **corpo** (a partir de "Você está trabalhando no projeto PULSO") em cada agente, trocando a linha "SUA FRENTE" pela
> frente atribuída (A, B, C ou D, seção 4). Este arquivo é a versão ajustada do prompt original do dono, com o contexto real do
> repositório em 2026-10-03, as regras de trabalho em paralelo e a divisão em frentes. Nada do espírito original foi removido.

---

## CORPO DO PROMPT

Você está trabalhando no projeto **PULSO**. Repositório: `https://github.com/henriquesouza1832001-eng/Pulso`.

**SUA FRENTE:** `<A | B | C | D>` (seção 4). Trabalhe só nela; as outras estão com outros agentes.

### 0. Antes de qualquer coisa
Leia, nesta ordem: `AGENTS.md`, `docs/OVERVIEW_PARA_AGENTES.md`, `README.md`, `docs/BACKEND_STATUS.md` (estado e registro de mudanças),
`docs/architecture/ARCHITECTURE.md`, `docs/architecture/PREDICTION.md`, `docs/SCORING.md`, `docs/COLLECTION_PROTOCOL.md`,
`docs/sources/SOURCES.md` + `CATALOGO_FONTES.md` + `CAMERAS.md`, `docs/decisions/` (ADRs 0005 a 0008), `packages/shared/src/contracts.ts`,
`engine/config/sources.json`, `engine/pulso_engine/` (collectors, processing, pipeline, forecast*), `apps/worker/`, `database/migrations/`
e os testes. NÃO recrie o projeto, NÃO substitua arquitetura funcional, NÃO apague trabalho de outras pessoas. O projeto é colaborativo.

### 1. Regras do repositório que valem para você (do `AGENTS.md`)
- **Branch:** trabalhe só na branch que o dono atribuiu a você. **Nunca crie branches, nunca use a `main`.** Só existem `main`, `hen`, `thig`, `art` e `isar`. Abra PR para a `main`; **o merge é decisão humana**.
- **Nunca** commite segredos (`.env`, tokens, cookies, chaves). Nunca contorne autenticação, limites, captcha ou termos de uso; nunca use proxy rotativo, conta falsa, cookie alheio ou chave que não tenha sido emitida para o projeto.
- Mudança de contrato = mesmo PR atualiza `packages/shared/src/contracts.ts`, `engine/pulso_engine/models.py` e `docs/api/API.md`, com label `contract`.
- Antes de integrar uma fonte: ficha em `docs/sources/SOURCES.md` (API oficial, termos, limites, custo, autenticação, licença, retenção, exibição pública). Toda fonte nova entra **com `reviewed_by: "PENDENTE"`** até o dono revisar.
- Atualize `docs/BACKEND_STATUS.md` (registro de mudanças) em todo PR relevante. Decisões arquiteturais viram `docs/decisions/NNNN-titulo.md`.
- Rode `cd engine && py -m pytest`, `npm test`, `npm run typecheck && npm run build`. **Verifique o comportamento real** (chame a fonte de verdade, não só "compilou").
- Previsão sempre com probabilidade, incerteza, evidências e método; **nunca** apresentada como fato; **nunca** probabilidade vinda só de LLM.

### 2. Estado do PULSO (2026-10-03). NÃO refaça o que já existe
- **Coleta:** 282 fontes ativas (RSS nacional/regional/local de todos os estados, INMET, INPE queimadas, Defesa Civil/IDAP, USGS, BCB/PTAX, InfoDengue, ONS energia armazenada, Google Trends BR, GDELT). Ciclo a cada 5 min (Cloudflare Cron → GitHub Actions `collect.yml`, limite 8 min; hoje ~40 s).
- **Processamento:** importância do texto, geolocalização (cidade/UF/gentílico), agrupamento em eventos com ids estáveis, frescor por categoria, rotina de campanha com peso baixo, tipos de evento e precursores (`engine/config/event_types.json`, só como evidência).
- **Previsão:** previsor de Pulso e de volume por categoria, Brier, backtest sintético (prova a mecânica, não a acurácia), indicadores antecedentes por correlação defasada. Rótulo EXPERIMENTAL até 100 previsões resolvidas.
- **Banco:** hoje o **Turso** (SQLite hospedado, plano grátis) é o banco ativo (`DB_BACKEND=turso`); o D1 estourou o limite diário de escrita em 2026-10-03 (ADR 0008). Há governador de orçamento de escrita no ingest.
- **Redes sociais:** adaptadores Reddit, X e Bluesky **prontos e desligados** à espera de chaves (roteiro `docs/ATIVAR_REDES_SOCIAIS.md`).
- **Câmeras:** catálogo `engine/config/cameras.json` (RealData, Motiva com prévia autorizada; Skyline e painéis oficiais só link).
- **Front:** `apps/web` é de outra pessoa; não altere sem pedir.

**Já pesquisado e DESCARTADO. Não repita, apenas cite:**
- Google News RSS e Bing News RSS: o próprio feed proíbe uso comercial; só serviram como ferramenta de pesquisa de veículos, nunca como fonte contínua.
- Waze (403), ANA hidroweb convencional (401), MetSul (403 em IPs do GitHub), CET-SP e outros painéis oficiais (sem termos de reuso: só link), Skyline (bloqueia hotlink de imagem, não se contorna).
- X sem API paga: não existe caminho legítimo. Bluesky `searchPosts` público sem login devolve 403 (exige conta); `getAuthorFeed`, `getFeed` e `searchActors` públicos funcionam sem login.
- Raspagem de redes sociais, captcha, "chave pública" de terceiros: proibido.

### 3. Restrições operacionais (toda integração precisa caber nelas)
- **Orçamento de escrita:** Turso grátis = 10 milhões de linhas escritas/mês; cada fonte nova gera escrita. Prefira sinais agregados e só grave o que mudou.
- **Tempo de coleta:** o ciclo tem teto de 8 min. Fonte lenta ou com muitos pontos precisa de `interval_s` alto e paralelismo limitado por host.
- **Classe e confiança:** rede social = `SOCIAL` (detecta, nunca confirma); oficial = `OFFICIAL`; imprensa = `NEWS_*`. Sensor físico (clima, rio, energia, voo) entra como sinal com baseline, não como notícia.
- **Licença:** registre se a fonte permite exibição pública, armazenamento e uso em modelo. Sem confirmação documentada, a fonte fica `BLOCKED`.

### 4. Frentes em paralelo (cada agente pega UMA; arquivos separados para não gerar conflito)
| Frente | Escopo (Partes do prompt) | Arquivos que ela escreve |
|---|---|---|
| **A: Governo, clima, hidrologia, energia, saúde, geologia, mar, satélites** | 1, 2, 3 (dados oficiais), 7, 8, 9, 12, 13, 14, 23, 29 | `docs/research/A/` |
| **B: Mobilidade, aviação, telecom, câmeras, eventos** | 4, 5, 6, 10, 11, 24, 25, 21 (embaixadas) | `docs/research/B/` |
| **C: Notícias, hiperlocal, social, buscas, internacional** | 15, 16, 17, 18, 19, 20, 22, 27, 28, 26 (mercados) | `docs/research/C/` |
| **D: Modelagem: assinaturas, indicadores antecedentes, validação, backtest, dataset, grafo** | 4 (cadeias), 5, 6, 7, 8, 9, 12, 15, 16, 17, 18, 19 (prioridade) | `docs/research/D/` e os consolidados |

- A, B e C produzem **fichas (JSON da Parte 2) e pontuação (Parte 3)** das fontes da sua frente em `docs/research/<frente>/FONTES.md` e `ASTEROIDES.md`.
- **D** consolida: `SENSOR_DISCOVERY.md`, `SOURCE_MATRIX.md`, `LEADING_INDICATORS.md`, `EVENT_SIGNATURES.md`, `BACKTEST_PLAN.md` em `docs/research/`, lendo o que A, B e C já mergearam. Enquanto A–C não terminam, D desenha o **modelo** (signatures, validation engine, query expansion, entidades emergentes, sensor graph) sobre o código existente.
- Nenhuma frente edita `docs/sources/SOURCES.md` diretamente com fonte não verificada. Só **uma** frente por vez edita arquivos compartilhados (`SOURCES.md`, `sources.json`): quem for integrar uma P0 avisa antes.

### 5. Prova obrigatória (aprendizado do projeto)
Para cada fonte registrada como utilizável, grave na ficha: URL exata consultada, **data e hora da consulta**, código HTTP, um trecho **curto** da resposta (sem segredos), autenticação, limite e a **citação literal** dos termos (com URL) sobre reutilização, armazenamento e exibição. Divergência entre fontes vai para "Contradições". Resultado de busca na web **não** vale como prova: abra a fonte original. Na dúvida, `status: "BLOCKED"` ou `"RESEARCH"`, nunca "permitido".

---

# OBJETIVO DESTA TAREFA

Sua missão é descobrir, pesquisar, classificar e, quando apropriado, integrar **novas fontes públicas de informação capazes de aumentar a capacidade de detecção antecipada do PULSO**.

Pense no PULSO como um **Pizza Index extremamente expandido para o Brasil**. Não estamos construindo um portal de notícias; estamos construindo um **sistema de detecção de sinais e anomalias**. Queremos detectar "algo fora do normal está começando a acontecer aqui" e depois procurar evidências adicionais para: confirmar, refutar, contextualizar, localizar, medir intensidade, estimar evolução, atualizar confiança e alimentar modelos de nowcast/previsão.

## PRINCÍPIO CENTRAL
Não procure apenas NOTÍCIAS. Procure **SENSORES**. Uma notícia é apenas um sensor. Queremos o máximo de fontes públicas independentes.

```text
trânsito + chuva + radar + queda de energia + transporte público + Defesa Civil + Bombeiros
+ redes sociais + câmeras públicas + notícias locais + fontes oficiais + atividade anormal = EVENTO
```
Quanto maior a diversidade de sensores independentes convergindo no tempo e no espaço, maior a capacidade de detectar acontecimentos relevantes.

---

# PARTE 1: PESQUISA PROFUNDA DE FONTES
Pesquise APIs, RSS, feeds, dados abertos, GeoJSON, GTFS, GTFS-Realtime, CAP, XML, JSON, CSV, WebSocket, SSE e outros feeds **oficialmente disponibilizados**. Prioridade: fontes brasileiras.

## 1. Governo federal
Presidência; gov.br; Agência Brasil; Câmara; Senado; STF; TSE; TREs; Banco Central; IBGE; IPEA; Receita Federal; Polícia Federal; PRF; Ministérios da Justiça, Defesa, Saúde, Transportes e Minas e Energia; ANEEL; ANATEL; ANAC; ANTT; ANTAQ; ANA; CEMADEN; INMET; INPE; Defesa Civil; DATASUS; OpenDataSUS; dados.gov.br. Descubra quais têm API, RSS, dados abertos, feeds, alertas e atualização frequente. *(Já existentes: ver seção 2; foque no que falta.)*

## 2. Estados
Os 26 estados + DF. Prioridade inicial: MG, SP, RJ, DF, RS, SC, PR, BA, PE, CE, GO, PA, AM. Pesquise: Defesa Civil, Polícia Militar, Bombeiros, DER, Detran, governo estadual, secretarias, dados abertos, trânsito, meteorologia, emergências, energia, transporte.

## 3. Municípios
Comece pelas maiores: São Paulo, Rio de Janeiro, Belo Horizonte, Brasília, Salvador, Fortaleza, Recife, Porto Alegre, Curitiba, Goiânia, Belém, Manaus. Pesquise: prefeituras; CET, BHTrans e equivalentes; centros de operações; Defesa Civil; transporte; dados abertos; interdições; obras; acidentes; eventos; chuvas; alagamentos; câmeras públicas.

## 4. Trânsito
Órgãos públicos; DER; DNIT; PRF; CET; concessionárias; rodovias; pedágios; centros de operações; Waze for Cities (parceria); feeds públicos; APIs municipais; dados de velocidade; acidentes; interdições; obras. Inclua rodovias federais e estaduais, pontes, túneis e vias urbanas.

## 5. Transporte público
GTFS, GTFS-Realtime, metrô, CPTM, ônibus, BRT, VLT, trens, aeroportos, portos. Detectar atrasos, linhas paradas, estações fechadas, alterações, cancelamentos e anomalias de frequência.

## 6. Aviação
ANAC, DECEA, INFRAERO, aeroportos, NOTAM, METAR, TAF, atrasos, cancelamentos, fechamentos, restrições. *(Já validado: `aviationweather.gov/api/data/metar` responde METAR de aeroportos brasileiros, ex.: SBGR; falta TAF, NOTAM, atrasos e a análise de termos.)* Investigue o que pode legalmente ser usado; não use fonte que proíba reutilização.

## 7. Clima
INMET, INPE, CEMADEN, Defesa Civil, CPTEC, radares estaduais, institutos estaduais, dados pluviométricos, nível de rios, alertas, tempestades, raios, vento, temperatura, deslizamentos. **Clima deve ser um sensor extremamente importante.** *(Já validado: Open-Meteo responde chuva a cada 15 min, vazão de rios e qualidade do ar; termos: uso não comercial, < 10 mil chamadas/dia, CC-BY 4.0, sem anúncio nem assinatura; confirme se o PULSO se enquadra.)*

## 8. Hidrologia
Nível de rios, reservatórios, barragens, chuvas, enchentes; ANA, CEMADEN, Defesa Civil, companhias estaduais. Identifique atualizações rápidas.

## 9. Energia
ONS, ANEEL, concessionárias, geração, carga, interrupções, apagões, reservatórios, frequência, energia por região. Pergunta: **é possível detectar anomalias energéticas antes de aparecerem na imprensa?** *(Já existe `ons-ear`; investigue carga, geração e interrupções.)*

## 10. Telecom / Internet
ANATEL, IX.br, NIC.br, CERT.br, Cloudflare Radar, status pages, operadoras, BGP, DNS, outages, internet exchanges. Objetivo: detectar anomalias grandes de conectividade.

## 11. Câmeras
Pesquise **apenas** câmeras oficialmente públicas, disponibilizadas por órgãos públicos ou feeds expressamente autorizados (trânsito, rodovias, centros urbanos, meteorologia, portos, aeroportos quando permitido). **Nunca:** câmeras privadas, credenciais expostas, feeds achados por vulnerabilidade, Shodan para acessar dispositivos, bypass de autenticação, `no-referrer` para driblar proteção de hotlink. Estenda o catálogo existente (`engine/config/cameras.json`, `docs/sources/CAMERAS.md`) com: `camera_id, owner, city, state, latitude, longitude, public_url, stream_type, terms, automation_allowed, retention_allowed`. *(Decisão do dono: câmeras só valem se der para ver de verdade; câmeras são baixa prioridade frente à coleta.)*

## 12. Incêndios
INPE, Bombeiros, satélites, queimadas, focos de calor, Defesa Civil. Verifique a atualização temporal.

## 13. Terremotos / eventos geológicos
Observatório Sismológico (USP/UnB), USGS quando afetar o Brasil, fontes internacionais públicas.

## 14. Mar / costa
Marinha, DHN, portos, ondas, marés, ressacas, alertas marítimos, ANTAQ, autoridades portuárias.

## 15. Redes sociais
Pesquise possibilidades **oficiais** para Reddit, X, Bluesky, Mastodon, YouTube e Telegram (somente canais explicitamente públicos e método permitido). **Não contornar APIs pagas.** Não usar cookies roubados, contas falsas, captcha bypass, proxy rotativo para evasão, raspagem proibida. Social é SENSOR, **nunca confirmação automática**. *(Reddit, X e Bluesky: chaves do dono chegam na semana de 2026-10-05; adaptadores prontos. Use apenas chaves emitidas para o projeto.)*

## 16. Bluesky
Investigue API pública, firehose, **Jetstream**, busca, feeds, termos e rate limits. *(Já verificado em 2026-10-03: `public.api.bsky.app` `searchPosts` exige login (403); `getAuthorFeed`, `getFeed` e `searchActors` funcionam sem login; Jetstream responde HTTP 200. Falta: lista de contas oficiais brasileiras, termos da API, limites e viabilidade do Jetstream.)* Avalie como sensor social gratuito/baixo custo.

## 17. Reddit
Comunidades brasileiras relevantes (Brasil, estados, cidades, trânsito, universidades, futebol, política, economia). Reddit não é fonte confiável: use para detecção de termos, crescimento, anomalias, localização aproximada e descoberta de eventos.

## 18. Notícias
Catálogo amplo, não só grandes veículos. Separe: `NEWS_NATIONAL`, `NEWS_REGIONAL`, `NEWS_LOCAL`, `NEWS_SPECIALIZED`, `NEWS_AGENCY`. Pesquise RSS/feeds permitidos; cubra todas as regiões. *(Hoje só existem as classes `NEWS_HIGH` e `NEWS_REGIONAL`; criar as novas é mudança de contrato.)*

## 19. Notícias hiperlocais (extremamente importante)
Veículos locais de cidades, bairros, rodovias, regiões metropolitanas e interior: muitos eventos aparecem primeiro neles. Crie catálogo progressivo por UF. *(Já feito em 2026-10-03: 171 veículos locais cadastrados a partir de uma descoberta por cidade, cada RSS validado; 4 com 403 descartados. Continue por cidade, evite duplicar domínios já cadastrados e não use Google News como fonte contínua.)*

## 20. Fontes internacionais
Para eventos relacionados ao Brasil: Reuters, AP, BBC, DW, France24, governos estrangeiros, embaixadas, consulados, State Department, Foreign Office, organizações internacionais.

## 21. Embaixadas e consulados
Monitore páginas públicas e alertas oficiais: fechamentos, alertas, restrições, security notices, mudanças de funcionamento. Pode funcionar como "asteroide" incomum.

## 22. Universidades e observatórios
USP, Unicamp, UFMG, UFRJ, UnB, UFPE, UFRGS, institutos, laboratórios, observatórios: dados públicos sobre clima, sismologia, mobilidade, saúde, economia, sociedade.

## 23. Saúde pública
Ministério da Saúde, OpenDataSUS, Fiocruz, secretarias estaduais, boletins, vigilância epidemiológica. **Somente dados agregados; nada de dado médico pessoal.**

## 24. Eventos
Calendários públicos, estádios, shows, eventos municipais, corridas, festas, Carnaval, grandes concentrações. Evento programado entra como **contexto/base rate**, não necessariamente como anomalia. *(BrasilAPI já valida os feriados nacionais.)*

## 25. Futebol
Calendários, estádios, CBF, competições, horários. Use **apenas como contexto operacional**.

## 26. Mercados e economia
Câmbio, juros, Selic, IPCA, Ibovespa, curva de juros, Banco Central, Tesouro, B3 (quando o licenciamento permitir). Detecte anomalias; **nunca recomendação financeira**.

## 27. Buscas e interesse
Alternativas legalmente utilizáveis para detectar aumento de interesse público: Google Trends, Wikipedia pageviews, Wikimedia, GDELT, outros índices públicos. *(Google Trends BR já integrado; Google News RSS proíbe uso comercial: só pesquisa.)* **Wikipedia Pageviews** pode ser um ótimo sensor ("enchente", "apagão", "terremoto" subindo rápido): investigue.

## 28. GDELT
Investigue a fundo: API, event database, GKG, Geo, atualização, cobertura brasileira, licença, utilidade como sensor internacional complementar. *(Há um coletor `gdelt-br` ainda não validado em produção por limite 429.)*

## 29. NASA / satélites
NASA FIRMS, NOAA, Copernicus, Sentinel, GOES: incêndios, fumaça, tempestades, anomalias térmicas.

## 30. Fontes incomuns (aqui quero criatividade)
Pergunte: **"Que dado público muda antes de um grande acontecimento virar notícia?"** Exemplos: trânsito anormal, atrasos aeroportuários, metrô interrompido, consumo elétrico, queda de internet, alertas oficiais, atividade sísmica, chuva, nível de rios, rodovias, câmeras, aumento de buscas, Wikipedia, NOTAM, portos, interdições, emergências, status pages, dados meteorológicos, fechamentos extraordinários, cancelamentos. Descubra outros. Esse é o espírito do Pizza Index.

---

# PARTE 2: CLASSIFICAÇÃO
Para cada fonte, uma ficha:

```json
{
  "name": "", "organization": "", "category": "", "coverage": "", "geographic_scope": "",
  "url": "", "api_url": "", "method": "API|RSS|ATOM|JSON|XML|CSV|GTFS|SSE|WEBSOCKET|PAGE",
  "authentication": "", "cost": "", "rate_limit": "", "update_frequency": "",
  "historical_data": true, "realtime": true, "geolocation": true,
  "terms_url": "", "terms_quote": "", "robots_url": "",
  "display_allowed": "", "storage_allowed": "", "prediction_use_allowed": "", "retention": "",
  "reliability_class": "", "expected_signal_value": "", "integration_complexity": "",
  "verified_at": "", "verified_request": {"url": "", "http_status": 0, "sample": ""},
  "status": "RESEARCH|P0|P1|P2|BLOCKED"
}
```

# PARTE 3: SCORE DA FONTE
Avaliação **técnica**, não política, de utilidade operacional, de 0 a 5: TIMELINESS, GEOGRAPHIC_PRECISION, STRUCTURE, RELIABILITY, INDEPENDENCE, COVERAGE, HISTORICAL_VALUE, COST_EFFICIENCY, INTEGRATION_EASE. Depois `SENSOR_VALUE`. O score serve para priorizar engenharia e **nunca** para avaliar partidos, candidatos ou opiniões.

# PARTE 4: DETECÇÃO ANTES DA NOTÍCIA
Para cada categoria de acontecimento, determine quais sensores mudam PRIMEIRO. Exemplos:

```text
ENCHENTE: chuva extrema → radar → pluviômetros → nível de rios → trânsito → transporte → social → Defesa Civil → notícias
APAGÃO: anomalia elétrica → internet/outages → transporte → social → concessionária → notícias
MANIFESTAÇÃO / GRANDE CONCENTRAÇÃO: evento programado + transporte + trânsito + atividade social agregada + interdições oficiais + imprensa
```
**Não rastrear indivíduos.**

# PARTE 5: EVENT SIGNATURES
Cada tipo de evento tem uma assinatura provável de sensores:

```yaml
FLOOD:
  leading: [rainfall, radar, river_level]
  concurrent: [traffic, transit, civil_defense]
  confirming: [official, news]
  contextual: [social]
```
Crie signatures para: FLOOD, FIRE, BLACKOUT, TRAFFIC_COLLAPSE, LANDSLIDE, STORM, EARTHQUAKE, PROTEST, LARGE_EVENT, PUBLIC_TRANSPORT_FAILURE, INTERNET_OUTAGE, AIRPORT_DISRUPTION, ROAD_BLOCK, HEALTH_ALERT, INFRASTRUCTURE_FAILURE. *(Parta de `engine/config/event_types.json`, que já tem 12 tipos e relações `raises` como hipóteses a validar.)*

# PARTE 6: LEADING INDICATORS
Banco de **indicadores antecedentes**: sensores que historicamente antecedem determinado evento. Não afirme causalidade sem evidência. Exemplo: chuva extrema T-90 min; nível de rio T-50; trânsito anormal T-25; Defesa Civil T-15; notícias T+0. Com histórico suficiente, meça `lead_time`, `precision`, `recall`, `false_positive_rate`. *(Já existe `engine/pulso_engine/drivers.py`, correlação defasada entre categorias; estenda, não duplique.)*

# PARTE 7: VALIDAÇÃO POR NOTÍCIAS
Quando o PULSO detectar uma anomalia: não espere passivamente. Crie o **VALIDATION ENGINE**: `ANOMALIA → LOCATION → CATEGORY → KEYWORDS → QUERY EXPANSION → NEWS SEARCH → OFFICIAL SEARCH → SOCIAL SEARCH → CORRELATION`. Exemplo (BH, FLOOD, termos "alagamento", "Venda Nova", "Vilarinho"): `"alagamento" "Venda Nova"`, `"chuva" "Venda Nova"`, `"interdição" "Vilarinho"`, `site:mg.gov.br "Vilarinho"`. **Use somente mecanismos e APIs que permitam esse uso** (buscar nos **nossos próprios sinais armazenados** é sempre permitido e é o primeiro passo; busca externa só em API que autorize).

# PARTE 8: QUERY EXPANSION
O Python expande consultas automaticamente (ACIDENTE → colisão, batida, capotamento, engavetamento, interdição, bloqueio, trânsito parado), considerando contexto para evitar falso positivo ("apagão" energia vs. figurado; "explosão" literal vs. expressão). Use NLP/contexto.

# PARTE 9: ENTIDADES EMERGENTES
Detecte termos que crescem rápido sem estar cadastrados (em 10 min: "Vilarinho", "alagado", "ônibus", "água", "Venda Nova") → cluster emergente → pesquisa de notícias, fontes oficiais e sensores relacionados.

# PARTE 10: GEOSEARCH
Considere país, UF, cidade, bairro, logradouro, ponto de interesse. **Não invente coordenadas.** Registre `geo_precision` e `geo_confidence` (os níveis atuais estão em `processing/geo.py`).

# PARTE 11: CONFIRMAÇÃO MULTIMODAL
50 posts do X **não** são 50 confirmações. Prefira 1 radar + 1 Defesa Civil + 1 trânsito + 2 veículos independentes + atividade social a 300 reposts da mesma publicação. **A diversidade de TIPO de sensor pesa fortemente.**

# PARTE 12: PREVISIBILIDADE
O objetivo é aumentar: **LEAD TIME** (quanto antes percebe), **PRECISION**, **RECALL**, **CALIBRATION** (70% acontece ~70%?) e reduzir **FALSE POSITIVE RATE**.

# PARTE 13: PREVISÃO
O PULSO produz **nowcasts** de eventos e condições verificáveis. Exemplo: "BH atingir PULSO 3+ nas próximas 2 h? 68%, intervalo 52–79%, EXPERIMENTAL". Toda previsão tem `forecast_id, question, horizon, probability, uncertainty, method, model_version, evidence, created_at, resolves_at, outcome, score` (já é o contrato `Forecast`). **Nunca use LLM sozinho para gerar probabilidade.** LLM pode interpretar, classificar, expandir query e resumir evidências; a probabilidade vem de modelo estatístico auditável.

# PARTE 14: POLÍTICA E ELEIÇÕES
Monitore política como **categoria de eventos e cobertura**, com neutralidade. Separe fato, declaração, alegação, fonte oficial e análise. Sem recomendação eleitoral; sem "melhor/pior/mais perigoso" para candidato ou partido. Para pesquisas eleitorais, só dados verificáveis, registrando instituto, contratante, período de campo, população, amostra, margem de erro, registro, data e URL original. **Não produza previsão própria de vencedor.** *(Ajuste: o dono quer cenários pós-eleição por cidade. Isso é permitido e desejado quando for sobre **consequências verificáveis**: trânsito, segurança, mobilização, mercado, serviços. Nunca sobre quem ganha. Eleição 2026: 1º turno em 2026-10-04; o TSE publica resultados em `resultados.tse.jus.br`.)*

# PARTE 15: TESTE RETROSPECTIVO (muito importante)
Escolha acontecimentos históricos públicos (enchentes, apagões, grandes tempestades, manifestações, interdições, incêndios, colapsos de transporte). Reconstrua T-6h, T-3h, T-1h, T-30m, T-10m, T0, T+30m. Pergunte: quais sensores já mudavam? Quando saiu a primeira notícia? Quando a fonte oficial? Quanto antes o PULSO poderia ter detectado? Relatório por evento:

```text
EVENTO X | Primeiro sensor: T-47m | Primeira correlação: T-31m | Primeira fonte oficial: T-18m
Primeira grande notícia: T0 | Lead potencial PULSO: 31 minutos
```
*(Ressalva do projeto: o backtest atual é sintético e só prova a mecânica. Backtest com eventos reais exige histórico dos sensores; verifique se a fonte oferece dado histórico antes de prometer o resultado.)*

# PARTE 16: NÃO CONFUNDIR CORRELAÇÃO COM PREVISÃO
Um sensor aparecer antes de um evento uma vez não prova que o prevê. Registre verdadeiros e falsos positivos e negativos e calcule desempenho.

# PARTE 17: DATASET DE TREINAMENTO
Construa o dataset histórico do próprio PULSO: `timestamp, location, sensor, signal, category, value, baseline, anomaly, event_id, event_outcome, lead_time`. É um dos ativos técnicos mais importantes. *(Respeite o orçamento de escrita da seção 3: proponha agregação e retenção antes de gravar.)*

# PARTE 18: PULSO SENSOR GRAPH
Proponha um grafo de relações temporais entre sensores (CHUVA → TRÂNSITO e RIOS → ALAGAMENTO → DEFESA CIVIL → NOTÍCIA). **Não trate o grafo como causalidade.**

# PARTE 19: PRIORIDADE DE IMPLEMENTAÇÃO
**P0 implementar agora:** gratuito, legalmente claro, estruturado, alta atualização, alto valor, **cabe no orçamento de escrita e de tempo (seção 3)**. **P1 próximo:** boa fonte, integração moderada. **P2 futuro:** útil, mas complexo ou caro. **BLOCKED:** depende de contrato, API paga, parceria, autorização ou termos incompatíveis.

# PARTE 20: NÃO INTEGRAR TUDO IMEDIATAMENTE
Primeiro o inventário; depois a seleção; só então implemente P0 **claramente permitidas**, cada uma com adaptador, testes (com resposta real gravada como fixture), ficha em `SOURCES.md`, `reviewed_by: "PENDENTE"` e entrada no `BACKEND_STATUS.md`. Não adicione raspagem duvidosa só porque funciona.

# PARTE 21: RESULTADO ESPERADO
Responda: (1) quais fontes brasileiras podemos usar; (2) quais são gratuitas; (3) têm API; (4) têm RSS; (5) são tempo real; (6) têm localização; (7) têm histórico; (8) são bons leading indicators; (9) aparecem antes das notícias; (10) podem validar uma anomalia; (11) podem reduzir falsos positivos; (12) têm maior valor; (13) exigem parceria; (14) são pagas; (15) não podemos usar; (16) **quais 10 integrações implementar primeiro**.

# PARTE 22: ENTREGÁVEIS
Por frente (seção 4): `docs/research/<A|B|C>/FONTES.md` e `ASTEROIDES.md`. Consolidados pela frente D em `docs/research/`: `SENSOR_DISCOVERY.md` (catálogo), `LEADING_INDICATORS.md`, `SOURCE_MATRIX.md`, `EVENT_SIGNATURES.md`, `BACKTEST_PLAN.md`. Atualize `docs/sources/SOURCES.md` **somente com fontes verificadas**. Não marque fonte como permitida sem confirmar a documentação/termos.

# PARTE 23: MATRIZ FINAL

| Fonte | Tipo | Tempo real | Geo | Histórico | Custo | Leading Indicator | Confirmação | Prioridade |
|---|---|---:|---:|---:|---:|---:|---:|---|

Não invente dados; cada afirmação precisa de fonte (URL + data).

# PARTE 24: NOVOS "ASTEROIDES"
Mantenha a seção **ASTEROIDES DESCOBERTOS**. Para cada ideia: nome; o que mede; quem fornece; frequência; cobertura; por que pode antecipar; como correlacionar; existe histórico; risco de falso positivo; como validar; se é legal e tecnicamente utilizável. Procure sinais estranhos, indiretos e pouco óbvios.

# PARTE 25: PERGUNTA GUIA
Para cada fonte: **"Isso ajuda o PULSO a saber que algo está acontecendo ANTES de simplesmente ler a notícia?"** Se sim: sensor primário. Se só confirma: sensor de validação. Se apenas replica outra fonte: baixa prioridade.

# PARTE 26: META FINAL
De "NOTÍCIA → PULSO DESCOBRE" para: `SINAL 1 + SINAL 2 + SINAL 3 → ANOMALIA → PULSO DETECTA → DEEP SEARCH → NOTÍCIAS + OFICIAIS + SOCIAL + OUTROS SENSORES → VALIDAÇÃO → EVENTO → NOWCAST → ACOMPANHAMENTO → RESOLUÇÃO → BACKTEST → MODELO MELHORA`. O diferencial: **DETECTAR → INVESTIGAR → CORRELACIONAR → VALIDAR → ACOMPANHAR → APRENDER**, não copiar notícias.

---

# EXECUÇÃO
Comece **somente** pela leitura do projeto e pela pesquisa da sua frente. Não faça alterações arquiteturais grandes sem justificar (ADR). Use prioritariamente documentação oficial, órgãos públicos e provedores. Para cada integração: abra a documentação, confirme disponibilidade, autenticação, custo, frequência, termos, se podemos **exibir**, **armazenar** e **usar dados derivados em modelos**. Não confie só em resultados de busca; abra a fonte original. Registre divergências; não chute.

## PRIMEIRA RESPOSTA ESPERADA (antes de implementar qualquer coisa)
1. **Estado atual do PULSO** (o que já existe no repo). 2. **Gaps.** 3. **Fontes já existentes.** 4. **Novos sensores descobertos** (da sua frente). 5. **Top 10 integrações P0** (tecnicamente mais úteis, sem ranking político ou editorial). 6. **Asteroides inesperados.** 7. **Arquitetura proposta** (encaixar sem destruir o que existe). 8. **Plano de backtest.** 9. **Custos e limitações** (APIs pagas, quotas, contratos, bloqueios). 10. **Próxima etapa** (só depois da análise, proponha quais P0 implementar).

A pesquisa deve ser ampla. O objetivo é descobrir o máximo de **sensores públicos, legais, úteis e independentes** capazes de transformar o PULSO no radar de anomalias do Brasil.
