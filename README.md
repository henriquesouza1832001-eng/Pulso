# PULSO 🇧🇷

Plataforma brasileira de inteligência situacional em tempo real, a partir de **sinais públicos**: o que está acontecendo no Brasil, onde, quão anormal é e quais evidências sustentam isso.

O PULSO mede **atividade e sinais detectados**, não a probabilidade de dano a ninguém, e separa **severidade** de **confiança**.

| Peça | Pasta | Tecnologia |
|---|---|---|
| Interface | [apps/web](apps/web) | React + TypeScript + Vite |
| API / gateway | [apps/worker](apps/worker) | Cloudflare Worker + Hono + D1 |
| Inteligência | [engine](engine) | Python |
| Contratos | [packages/shared](packages/shared) | TypeScript |
| Banco | [database](database) | migrations e seeds D1 |

**Entrando no backend? Comece por [docs/BACKEND_STATUS.md](docs/BACKEND_STATUS.md)** (estado, ambientes, problemas conhecidos e roadmap).

Documentação: [arquitetura](docs/architecture/ARCHITECTURE.md) · [API](docs/api/API.md) · [scoring](docs/SCORING.md) · [fontes](docs/sources/SOURCES.md) ([catálogo](docs/sources/CATALOGO_FONTES.md), [câmeras](docs/sources/CAMERAS.md)) · [operação](docs/RUNBOOK.md) · [pendências do dono](docs/PENDENCIAS_DO_DONO.md) · [estado do backend](docs/BACKEND_STATUS.md) · [decisões](docs/decisions) · [como contribuir](CONTRIBUTING.md) · [regras para agentes](AGENTS.md)
