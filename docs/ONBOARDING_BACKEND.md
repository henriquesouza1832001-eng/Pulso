# Passo a passo: entrando no backend do PULSO

Este guia é para quem vai ajudar no backend. Você pode seguir sozinha ou usando um agente (Codex, Claude etc.); nesse caso, mande o agente ler também [OVERVIEW_PARA_AGENTES.md](OVERVIEW_PARA_AGENTES.md).

## 0. O que é o PULSO, em 1 minuto
Uma plataforma que coleta **sinais públicos** (hoje, notícias por RSS; depois fontes oficiais e redes sociais), agrupa em **eventos**, mede **severidade**, **confiança** e **Pulso Score**, e quer **antecipar** acontecimentos como previsões probabilísticas honestas (no espírito do "Pizza Index"). Um sinal fraco nunca vira fato; toda previsão é uma probabilidade com evidências.

Três peças: **Engine** em Python (`engine/`), **Worker** da Cloudflare (`apps/worker`, a API) e **Web** em React (`apps/web`, feita por outra pessoa).

## 1. Quem faz o quê
| Quem | Responsabilidade |
|---|---|
| **Henrique (dono do backend)** com o Claude | Núcleo e infraestrutura: coleta contínua, agrupamento com estado, **previsões**, tempo real (SSE), segredos e deploy. Também revisa os PRs de vocês. |
| **Você (backend, módulos independentes)** | Qualidade da classificação/geo, coletores de fontes oficiais, busca e timeline, proteção do painel admin. Detalhes na seção 5. |
| **Pessoa do front** | Interface React. Qualquer mudança em contrato de API precisa avisá-la. |

Os arquivos de cada um são separados de propósito para não haver conflito.

## 2. Preparar o ambiente (≈ 1 hora)
**Peça ao Henrique, por canal seguro (nunca por chat público/PR):**
- convite como colaboradora no GitHub (repositório `henriquesouza1832001-eng/Pulso`);
- qual das branches `thig`, `art` ou `isar` é a sua;
- (só se for mexer em deploy) acesso à conta Cloudflare. Para as tarefas 1 a 4 você **não** precisa de segredos de produção.

**Instalar:** Git, Node.js 22, Python 3.12+ (no Windows, use o comando `py`), e o GitHub CLI (`gh`) é opcional.

**Preparar o código (PowerShell):**
```
git clone https://github.com/henriquesouza1832001-eng/Pulso.git
cd Pulso
git checkout <sua-branch>          # thig, art ou isar
git pull origin main               # traz o que há de mais novo
npm install
cd engine
py -m pip install -e ".[dev]"
py -m pytest                       # deve passar tudo (~230 testes, ~30 s)
cd ..
npm run typecheck                  # deve passar sem erros
```
**Rodar o sistema localmente:**
```
npm run db:migrate
npm run db:seed                    # dados FICTÍCIOS, só para desenvolvimento
copy apps\worker\.dev.vars.example apps\worker\.dev.vars
npm run dev:worker                 # API em http://localhost:8787
```
Em outro terminal: `cd engine` e `py -m pulso_engine.pipeline` (rodada simulada, não envia nada). Para ver eventos reais no seu banco local: `$env:PULSO_API_URL="http://localhost:8787"; $env:PULSO_INGEST_TOKEN="<o valor do seu .dev.vars>"; py -m pulso_engine.pipeline --push`.

**Armadilhas conhecidas (Windows):** use `py`, não `python`; se o `npm run dev:worker` ficar mudo, há um servidor antigo preso na porta (feche pelo Gerenciador de Tarefas ou use outra porta com `--port`); nunca rode o seed em produção.

## 3. Leia nesta ordem (≈ 1 hora)
1. `AGENTS.md`: as regras (valem para pessoas e agentes).
2. `docs/BACKEND_STATUS.md`: estado atual, problemas conhecidos e roadmap. **Documento vivo.**
3. `docs/architecture/ARCHITECTURE.md` e `PREDICTION.md`.
4. `docs/COLLECTION_PROTOCOL.md`: como uma fonte entra no sistema.
5. `docs/SCORING.md` e `docs/api/API.md`.

## 4. Regras que valem sempre
- **Só existem as branches `main`, `hen`, `thig`, `art`, `isar`. Não crie outras.** Você trabalha na sua e abre um Pull Request para a `main`.
- **Nunca** commite `.env`, `.dev.vars`, tokens ou chaves. Nunca cole segredos em chat, issue ou PR.
- Não faça push direto na `main`. Não faça merge sozinha: o Henrique revisa e faz o merge.
- PR pequeno, uma coisa por vez, com testes. O CI (typecheck e testes) precisa estar verde.
- Mensagem de commit: `tipo: descrição` (`feat`, `fix`, `docs`, `test`, `refactor`), nunca `update` ou `teste`.
- Mudou contrato de API (`packages/shared/src/contracts.ts`, `engine/pulso_engine/models.py`, `docs/api/API.md`)? **Avise antes** o Henrique e a pessoa do front.
- Fonte externa nova: só depois de ler API/termos/limites e seguir o checklist do protocolo de coleta. Sem contornar login, limites ou termos.
- No fim de cada PR, atualize `docs/BACKEND_STATUS.md` (estado e registro de mudanças).

## 5. Suas tarefas, em ordem
Cada tarefa é um PR. Termina quando os critérios de aceite estão cumpridos.

### E1 · Aquecimento (valida acesso, CI e fluxo)
Faça uma mudança mínima (por exemplo, corrigir um erro de digitação em um doc), abra o PR e veja o CI passar.
**Aceite:** PR aberto, CI verde, Henrique consegue revisar.

### E2 · Qualidade da classificação e da geolocalização
Hoje a classificação por palavras-chave erra: um boletim de vídeos foi classificado como política; a mesma história virou dois eventos; só capitais e estados são reconhecidos.
- Amplie o gazetteer em `engine/pulso_engine/processing/geo.py` (mais municípios) sem criar ambiguidades (ex.: "Natal" festa x cidade).
- Ajuste as famílias em `engine/pulso_engine/processing/keywords.json` e reduza falsos positivos.
- Para cada ajuste, escreva um teste com um exemplo real em `engine/tests/`.
**Aceite:** testes novos cobrindo os casos ruins; `py -m pytest` verde; nenhum teste antigo quebrado.

### E3 · Coletores de fontes oficiais (um por PR)
Fontes: INMET (alertas), Defesa Civil, PRF, IBGE, Banco Central.
1. **Antes de codar:** leia a API e os termos da fonte; preencha o checklist de `docs/COLLECTION_PROTOCOL.md` §4 e a ficha em `docs/sources/SOURCES.md`.
2. Crie `engine/pulso_engine/collectors/official/<fonte>.py` com a mesma interface do `RssAdapter` (veja `collectors/news/rss.py`): construtor `(source, keywords, fetcher, now)` e `run() -> list[Signal]`.
3. Registre com **uma linha** em `engine/pulso_engine/collectors/registry.py`.
4. Adicione a fonte em `engine/config/sources.json` com todos os campos do protocolo (`terms_url`, `access`, `interval_s` etc.). O `config.py` recusa fonte incompleta.
5. Teste **sem rede**, com uma resposta gravada da fonte.
**Aceite:** testes verdes; fonte aparece em `py -m pulso_engine.pipeline` com status ONLINE; ficha preenchida; fonte da classe `OFFICIAL`.

### E4 · Busca e linha do tempo na API
Crie `apps/worker/src/routes/search.ts` (`GET /api/search?q=`) e `timeline.ts` (`GET /api/timeline`), registre em `apps/worker/src/index.ts`, seguindo o padrão de `routes/events.ts` (validação com zod, `Cache-Control`, erros `{ "error": ... }`). Documente em `docs/api/API.md`. Avise a pessoa do front.
**Aceite:** `npm run typecheck` verde; teste local com `curl`; entrada inválida devolve 400.

### E5 · Proteger o painel admin (combine antes com o Henrique)
Hoje `/api/admin/*` usa o mesmo token do Engine. O desenho (Cloudflare Access ou token próprio) deve ser decidido em conjunto, num ADR curto em `docs/decisions/`.

## 6. Abrindo um PR
```
git add .
git commit -m "feat: descrição curta"
git push origin <sua-branch>
gh pr create --base main --head <sua-branch>
```
(ou pelo site do GitHub). No PR: o que mudou, como testar, e o resultado dos testes. Espere o CI ficar verde e peça revisão ao Henrique.

## 7. O que o Henrique faz em paralelo
Liga a coleta automática de 5 em 5 minutos (token do GitHub no Worker), revoga um token antigo exposto, revisa os termos das fontes RSS, constrói o agrupamento com estado, o **sistema de previsões**, o tempo real (SSE) e revisa seus PRs. Se algo seu depender disso, ele avisa.

## 8. Travou?
Leia o `BACKEND_STATUS.md` (seção 7 lista os problemas conhecidos). Se continuar, descreva ao Henrique: o que tentou, o comando, e a mensagem de erro completa (sem segredos).
