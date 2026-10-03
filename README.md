# PULSO 🇧🇷

**O PULSO é um instrumento que mede o Brasil em tempo real.** Ele junta centenas de fontes públicas (imprensa nacional e local, alertas oficiais, clima, energia, câmbio, saúde, buscas) e responde, o tempo todo, a quatro perguntas:

1. **O que está acontecendo?** (eventos, agrupados e localizados por estado e cidade)
2. **Quão fora do normal está?** (anomalia contra o comportamento esperado)
3. **Quão bem sustentado está?** (confiança: quantas fontes independentes, se há confirmação oficial)
4. **Para onde está indo?** (previsões de curto prazo, sempre com probabilidade, incerteza e histórico de acertos)

> A ideia é o espírito do *Pizza Index*: um sinal indireto que muda **antes** da manchete. O PULSO não é um portal de notícias. Uma notícia é só mais um sensor.

O PULSO mede **atividade e sinais públicos detectados**. Ele não mede a probabilidade de dano a ninguém, não afirma que algo é verdade e não rastreia pessoas.

## Como funciona

```text
 FONTES (≈280)                     MOTOR PYTHON                              PRODUTO
 imprensa nacional/local     coletar → normalizar → deduplicar        ┌──────────────────────┐
 alertas oficiais (INMET,    localizar (cidade/UF) → agrupar em       │  Pulso 0-100 do país │
 Defesa Civil, INPE...)      eventos com estado                       │  e de cada estado    │
 energia, câmbio, saúde,     → severidade + confiança + frescor       │  eventos e "por quê" │
 buscas, redes sociais       → anomalia e tendência (baseline)        │  previsões com       │
                             → Sentinela (investiga o anormal)        │  histórico de acerto │
                             → previsão (Brier, backtest)             └──────────────────────┘
```

- **Coleta:** a cada 5 minutos, em paralelo, com limite de uso por servidor e respeito aos termos de cada fonte (`docs/COLLECTION_PROTOCOL.md`).
- **Eventos:** notícias sobre o mesmo fato viram **um evento** com identidade estável; cópias da mesma matéria contam como **uma** fonte.
- **O que é de agora vale mais:** cada categoria tem uma meia-vida (trânsito esfria em horas; política em dias). Uma notícia de 12 h atrás pesa menos que uma de agora.
- **Rotina de campanha pesa pouco:** comício, carreata e agenda de candidato são eventos esperados e entram com severidade baixa, a menos que venha com violência ou vítimas.
- **Pulso (0-100):** soma explicável de severidade, confiança, velocidade, diversidade de fontes, anomalia, recência, persistência e alcance. Todo número responde "por que 87?" ([docs/SCORING.md](docs/SCORING.md)).
- **Severidade ≠ confiança:** um incêndio possivelmente grande com um só relato tem severidade alta e confiança baixa. Rede social **detecta, nunca confirma**.
- **Sentinela:** quando algo foge do normal (volume, velocidade, vários tipos de fonte ao mesmo tempo, sinal oficial), abre uma **investigação** com estado, procura evidências nos sinais já coletados e vai esfriando até encerrar.
- **Previsão honesta:** sem histórico suficiente o PULSO responde `INSUFFICIENT_DATA`; até 100 previsões resolvidas, tudo é `EXPERIMENTAL`; toda previsão registra método, versão, evidências e é pontuada depois (Brier). Probabilidade nunca vem de um modelo de linguagem ([docs/architecture/PREDICTION.md](docs/architecture/PREDICTION.md)).

## O que o PULSO nunca faz

- Reconhecimento facial, rastreamento de pessoas ou perfil individual.
- Tratar alegação política como fato, recomendar voto, ranquear candidatos ou prever vencedor de eleição.
- Burlar login, captcha, limites ou termos de uso de qualquer fonte. Rede social entra só pela API oficial, com chave do projeto.
- Publicar previsão sem probabilidade, incerteza e método.

## Peças do projeto

| Peça | Pasta | Tecnologia |
|---|---|---|
| Interface | [apps/web](apps/web) | React + TypeScript + Vite |
| API / gateway | [apps/worker](apps/worker) | Cloudflare Worker + Hono + zod |
| **Motor (a alma do PULSO)** | [engine](engine) | Python, sem dependências obrigatórias |
| Contratos | [packages/shared](packages/shared) | TypeScript (espelho em `engine/pulso_engine/models.py`) |
| Banco | [database](database) | migrations SQL (hoje em Turso/SQLite; ver ADR 0008) |

O motor roda no GitHub Actions a cada 5 minutos (disparado pelo Cron da Cloudflare), grava no banco pelo Worker e a interface lê a API. Tudo em planos gratuitos; o custo de escrita no banco é um orçamento controlado pelo próprio motor.

## Estado hoje (outubro de 2026)

- ≈280 fontes ativas em todos os estados, mais de 170 veículos locais; coleta completa em menos de 1 minuto.
- Pulso nacional e por estado, eventos com "por quê", previsões de Pulso e de volume com Brier e backtest.
- Sentinela e histórico agregado por hora em construção; baseline sazonal precisa de semanas de coleta para ficar útil.
- Reddit, X e Bluesky: adaptadores prontos e desligados à espera de chaves ([como ativar](docs/ATIVAR_REDES_SOCIAIS.md)).
- Câmeras: catálogo de links e de algumas prévias autorizadas ([docs/sources/CAMERAS.md](docs/sources/CAMERAS.md)).

O estado detalhado, os problemas conhecidos e o roadmap estão em **[docs/BACKEND_STATUS.md](docs/BACKEND_STATUS.md)**.

## Rodar localmente

```bash
npm install
npm run dev:worker          # API em http://127.0.0.1:8787 (D1 local)
npm run dev:web             # interface em http://localhost:5173
cd engine
py -m pytest                # testes do motor
py -m pulso_engine.pipeline # uma rodada completa, sem enviar nada
py -m pulso_engine.audit    # o que cada fonte entrega agora
```

Antes de abrir um PR: `npm run typecheck && npm test && npm run build` e `cd engine && py -m pytest`. Verifique o comportamento real (rode a fonte, chame o endpoint), não só "compilou".

## Documentação

[Arquitetura](docs/architecture/ARCHITECTURE.md) · [API](docs/api/API.md) · [Scoring](docs/SCORING.md) · [Previsão](docs/architecture/PREDICTION.md) · [Protocolo de coleta](docs/COLLECTION_PROTOCOL.md) · [Fontes](docs/sources/SOURCES.md) ([catálogo](docs/sources/CATALOGO_FONTES.md), [câmeras](docs/sources/CAMERAS.md)) · [Pesquisa de sensores](docs/research/PROMPT_PESQUISA_DE_SENSORES.md) · [Operação](docs/RUNBOOK.md) · [Pendências do dono](docs/PENDENCIAS_DO_DONO.md) · [Decisões (ADRs)](docs/decisions) · [Como contribuir](CONTRIBUTING.md) · [Regras para agentes](AGENTS.md)

## Trabalhando em equipe (e com agentes de IA)

Só existem as branches `main`, `hen`, `thig`, `art` e `isar`; **ninguém cria outra**. Mudanças entram por PR para a `main` e o merge é decisão humana. Mais de uma pessoa (ou agente) pode usar a mesma branch, desde que combinem: **um commit por vez**, `git add` sempre por nome de arquivo, e cada um só edita a sua frente. Segredos nunca vão para o repositório. Contrato público só muda com `contracts.ts`, `models.py` e `API.md` juntos, com a label `contract`. Detalhes em [AGENTS.md](AGENTS.md) e [CONTRIBUTING.md](CONTRIBUTING.md).
