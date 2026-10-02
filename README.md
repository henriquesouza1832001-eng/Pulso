# Pulso

Radar de notícias em tempo real do Brasil: agrega fontes, agrupa matérias em eventos e mede a intensidade informacional (Pulso Score, 0–100). O score mede cobertura, não veracidade.

**Stack:** React 19 + React Router 7 (SSR) em Cloudflare Workers, D1 (dados) e KV (cache). Veja [CONTRIBUTING.md](CONTRIBUTING.md) para o fluxo de trabalho.

## Estado atual

- Esqueleto full-stack, schema D1 (`migrations/`), Pulso Score (`app/lib/score.ts`).
- Home com Pulso nacional e `GET /api/pulse`.
- Próximos passos: coletor RSS, normalização, deduplicação, eventos, trending, timeline, mapa.
