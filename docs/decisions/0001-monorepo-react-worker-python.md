# 0001 — Monorepo com React, Worker Cloudflare e Engine Python

**Contexto.** A primeira versão era um app React Router com SSR dentro de um Worker. O produto evoluiu para um mapa em tempo real, com NLP, geolocalização e clustering em Python, e vários desenvolvedores em paralelo.

**Decisão.** Monorepo (`apps/web`, `apps/worker`, `engine`, `packages/shared`, `database`). Web é SPA React + Vite (SSR agrega pouco numa tela centrada em mapa). O Worker é o gateway (Hono + zod). O Python Engine fica desacoplado e só conversa por `POST /api/ingest`, com contrato tipado.

**Consequências.** Contratos duplicados (TS e Python) precisam andar juntos (regra no AGENTS.md). Cloudflare Queues, KV, R2 e Durable Objects ficam para quando houver necessidade medida. O D1 ganhou schema v2; não havia produção, então a migration `0001` foi reescrita.
