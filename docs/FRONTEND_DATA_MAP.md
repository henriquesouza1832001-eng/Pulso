# Mapa de dados do front (Web ⇄ API)

> **Para:** a pessoa do front. **De:** backend. **Atualizado:** 2026-10-03, com base na leitura de `apps/web` (branch `thig` já na `main`) e dos dados reais de produção.
> Regra: o front só fala com a API pública; contratos em `packages/shared/src/contracts.ts` e `docs/api/API.md`. Mudou algo no formato? Avise o backend antes.

## 1. O que já é real hoje
| Bloco da tela | Fonte | Observação |
|---|---|---|
| Indicador nacional (número, nível, gauge) | `GET /api/pulse/br` | ✅ real. `delta_2h` agora é `null` quando não há ponto real de ~2 h atrás (antes podia mostrar variação enganosa). |
| Cidades, Mapa, Lista por UF, Feed OSINT, Briefings, Painel de UF | `GET /api/events?limit=50` | ✅ real, ordenado por Pulso. |
| Dossiê do evento (por que N, sinais e fontes) | `GET /api/events/:id` | ✅ real; `signals[]` traz fonte, horário e link original. |
| Monitor de fontes | `GET /api/health` | ✅ real. Novo: `collection.age_seconds` / `stale` (a coleta está atrasada?). |
| FAQ, Hero | estático | — |

## 2. O que ainda é demonstração (`VITE_DEMO=1`) e o que o backend entrega
| Bloco | Hoje | Backend | Ação sugerida no front |
|---|---|---|---|
| **Curva "Pulso · últimas 24h"** | `Sparkline` com semente aleatória (**não é dado real**) | ✅ `GET /api/pulse/history?scope=BR&hours=24` → `points[{timestamp,score,alert_level}]` | Plotar os pontos reais. Com pouco histórico, mostrar "coletando histórico" em vez de curva inventada. |
| **Contadores do indicador** ("eventos ativos", "sinais · 2h", "UFs ativas") | calculados no front a partir da lista de 50 eventos (`signal_count` somado ≠ "2h"; o total trava em 50) | ✅ `GET /api/stats` → `active_events, states_active, alerts, signals_2h, signals_24h, sources_online, sources_total, last_pulse_at` | Usar `/api/stats` nesses números. |
| **Pulso por UF** (lista e mapa) | derivado dos eventos no front | ✅ `GET /api/pulse/states` → `states[{uf,score,alert_level,timestamp}]` | Preferir o valor do servidor; o dos eventos serve só para marcadores. |
| **Mercados / odds** | `DEMO_FORECASTS` `{q, yes, drivers}` | ✅ `GET /api/forecasts` (**depende do merge do PR de previsões**) → ver seção 3 | Trocar o adaptador. |
| **Histórico de inteligência** | `DEMO_HISTORY` | ✅ `GET /api/history?min_level=3` → `entries[{kind,date,level,peak_pulse,title,...}]` | Trocar `DEMO_HISTORY`. Enquanto nada tiver chegado a nível 3 (hoje é o caso), a lista vem vazia: mostrar "sem registros". |
| **Câmeras** | `DEMO_CAMERAS` | ❌ só na Fase 3 (câmeras oficiais autorizadas; depende de parcerias) | Manter vazio. Nunca mostrar câmera fictícia em produção. |
| **Feed cronológico de relatos brutos** | mostra eventos, não sinais | ⏳ `GET /api/timeline` (a fazer, tarefa E4) | Hoje o "feed" é por evento; combinar a necessidade. |

## 3. Previsões no front (Mercados)
Resposta de `GET /api/forecasts`:
```
{ "notice": "PREVISÃO (probabilidade), não fato...", "forecasts": [{
  "forecast_id", "question", "probability" (0–1, nunca 0 nem 1),
  "interval_low", "interval_high", "horizon_minutes", "created_at", "resolves_at",
  "status": "open|resolved|void", "outcome", "observed_value", "brier",
  "experimental": true, "evidence": { "current_score", "pairs", "hits", "history_hours" } }] }
```
Adaptador sugerido: `yes = Math.round(probability * 100)`; `drivers` a partir de `evidence` (ex.: "baseado em N variações históricas do Pulso").
**Regras de exibição (inegociáveis, vêm do `PREDICTION.md`):**
1. Rótulo **PREVISÃO** sempre visível; nunca no estilo de um evento confirmado.
2. Mostrar a **faixa de incerteza** (`interval_low`–`interval_high`), não só o número.
3. Se `experimental` for `true`, mostrar o selo **EXPERIMENTAL** (hoje será sempre, até 100 previsões resolvidas).
4. Link/seção de **histórico de acertos**: `GET /api/forecasts/track-record`.
5. Evitar linguagem de aposta ("odds ao vivo", "SIM/NÃO" como cassino). O texto atual já diz "não é aposta"; sugiro renomear "Mercados" para "Previsões".
6. Enquanto não houver previsões (o previsor precisa de ~3,5 h de histórico contínuo), manter o estado vazio. O texto "PULSO-ML ainda não treinado" não é exato: o modelo atual é estatístico simples; sugiro "ainda reunindo histórico".

## 4. Dados reais agora (para calibrar o visual)
Em 2026-10-03, ~01h UTC, produção:
- Dia calmo: Pulso Brasil ≈ 29 (nível 1); **todos os eventos em nível 1–2**, nenhum alerta ≥ 3. O front deve ficar bom e informativo mesmo assim (não depender de eventos críticos para parecer "vivo").
- Categorias dominadas por **POLITICS** (notícias de política); poucos EMERGENCY/TRAFFIC. É consequência das fontes (portais de notícia); virá mais variedade com fontes oficiais.
- Cerca de **1/3 dos eventos não tem localização** (notícia nacional): não aparecem no mapa. Sugestão: contador "N sem localização" ou lista própria.
- Muitos eventos compartilham a mesma coordenada (capital do estado): usar agrupamento/jitter nos marcadores. Precisão é `CITY` ou `STATE`; **não há ruas nem bairros** ainda.
- **Bug corrigido pelo backend:** a palavra "para" (preposição) era lida como o estado do Pará, concentrando ~1/3 dos eventos no PA. Corrigido; os eventos se reajustam sozinhos nas próximas coletas.
- Atualização: a coleta roda a cada 5 min; a API tem cache de 5–15 s. Polling de 15 s está adequado.

## 5. Pequenos pontos no código atual
- `level ?? 3` (TopBar, PulseIndicator): enquanto a API não responde mostra "nível 3". Preferir estado "carregando" neutro.
- O app roda sem `VITE_DEMO` em produção (`npm run deploy`): confirmar que o badge "DEMO DATA" nunca aparece lá.
- `ALLOWED_ORIGINS` do Worker só libera `localhost:5173` e `pulso-web.henriquesouza.workers.dev`. Domínio novo ou outra porta de dev exige o backend atualizar a lista.
- O tipo `HealthSnapshot` em `lib/api.ts` não tem o campo `collection`; pode ser acrescentado para exibir "coleta atrasada".

## 6. Como combinamos mudanças
Front pede um campo/endpoint novo → abre issue ou avisa o backend com o formato desejado (JSON de exemplo) → backend implementa, documenta em `API.md` e responde "pronto". Backend muda um contrato → atualiza `contracts.ts`, `models.py`, `API.md` e avisa o front no mesmo PR.
