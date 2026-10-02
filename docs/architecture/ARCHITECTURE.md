# Arquitetura do PULSO

## Visão
O PULSO transforma sinais públicos dispersos ("asteroides") em eventos geolocalizados com **severidade**, **confiança** e **Pulso Score** explicáveis. Detecção não é confirmação: o sistema mostra a evidência, não decide a verdade.

```
FONTES → Collectors (Python) → Normalize → Keywords → Entidades → Geolocalização
      → Dedup → Clustering → Anomalia/Baseline → Confiança → Pulso
      → POST /api/ingest → Worker → D1 / KV → API → React (mapa, dashboard)
```

## Três peças desacopladas
| Peça | Pasta | Papel | Roda em |
|---|---|---|---|
| Web | `apps/web` | React + TypeScript + Vite; só fala com a API pública | Cloudflare (assets) |
| Worker | `apps/worker` | Gateway: API, CORS, validação, cache, ingestão autenticada | Cloudflare Workers |
| Engine | `engine/` | Inteligência: coleta, NLP, geo, clustering, scoring | onde for adequado (container/VM/cron); Python não roda como Worker tradicional |

O Engine só conhece o **contrato** (`IngestBatch`): ele calcula e envia; o Worker valida e grava. Trocar o ambiente do Engine não exige reescrever nada.

## Estado atual (Fase 1, fundação)
Implementado e testado: contratos compartilhados, schema D1 v2, API de leitura (`/api/pulse/*`, `/api/events`, `/api/map`, `/api/health`), ingestão autenticada e idempotente, front com Pulso BR e eventos explicáveis, Engine com `SourceAdapter`, keyword engine recarregável, confiança, Pulso Score, nível PULSO 1–5 e cliente do Worker.

Próximos módulos (branches independentes): `collector/news-rss`, geolocalização, deduplicação, clustering, mapa MapLibre, SSE.

## Princípios
- Cloudflare first, sem overengineering: KV, Queues, R2 e Durable Objects entram quando houver necessidade medida (ADR por decisão).
- Mensagens de fila (futuro) sempre com ID: processamento idempotente, nunca "exatamente uma vez".
- Nenhuma integração é ponto único de falha; falha de fonte = `source_health`, não queda.
- Fallback sem IA: keywords + estatística + regras sustentam o produto; LLM só melhora.
- Privacidade: eventos e ambientes públicos, nunca indivíduos.

## Ambientes
LOCAL (`wrangler dev` + D1 local) → STAGING → PRODUCTION. Nunca testar integração destrutiva em produção.
