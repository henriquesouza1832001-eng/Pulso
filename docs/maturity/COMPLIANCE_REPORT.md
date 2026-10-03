# Conformidade das fontes (relatório gerado)

> Gerado por `py -m pulso_engine.compliance --write` a partir de `engine/config/sources.json`. **Não editar à mão.** Nenhuma fonte é APPROVED automaticamente: a decisão é humana (`review_status` + `reviewed_by` + `reviewed_at` + `terms_url`).

- Fontes cadastradas: **291** · ativas: **282** · domínios ativos distintos: **238** (domínios com revisão pendente: 238).

| Estado | Fontes | % das ativas |
|---|---|---|
| APPROVED | 0 | 0.0% |
| RESTRICTED | 0 | 0.0% |
| PENDING | 282 | 100.0% |
| DISABLED | 9 |  |
| UNKNOWN | 0 | 0.0% |

## Por família (classe/adaptador)

| Família | APPROVED | RESTRICTED | PENDING | DISABLED | UNKNOWN |
|---|---|---|---|---|---|
| NEWS_HIGH/rss | 0 | 0 | 60 | 1 | 0 |
| NEWS_REGIONAL/gdelt | 0 | 0 | 0 | 1 | 0 |
| NEWS_REGIONAL/rss | 0 | 0 | 202 | 0 | 0 |
| OFFICIAL/bcb_ptax | 0 | 0 | 1 | 0 | 0 |
| OFFICIAL/idap_cap | 0 | 0 | 1 | 0 | 0 |
| OFFICIAL/infodengue | 0 | 0 | 1 | 0 | 0 |
| OFFICIAL/inmet | 0 | 0 | 1 | 0 | 0 |
| OFFICIAL/inpe_fires | 0 | 0 | 1 | 0 | 0 |
| OFFICIAL/ons_ear | 0 | 0 | 1 | 0 | 0 |
| OFFICIAL/rss | 0 | 0 | 12 | 0 | 0 |
| OFFICIAL/usgs | 0 | 0 | 1 | 0 | 0 |
| SOCIAL/bluesky | 0 | 0 | 0 | 2 | 0 |
| SOCIAL/google_trends | 0 | 0 | 1 | 0 | 0 |
| SOCIAL/mastodon | 0 | 0 | 0 | 1 | 0 |
| SOCIAL/reddit | 0 | 0 | 0 | 2 | 0 |
| SOCIAL/x | 0 | 0 | 0 | 2 | 0 |

Atribuição exigida desconhecida em **282** fontes ativas (campo `attribution_required` ainda não preenchido).

## Como reduzir PENDING

1. Abrir `docs/sources/REVIEW_WORKSHEET.csv` (uma linha por domínio: uma leitura de termos cobre todas as fontes do domínio).
2. Ler os termos reais do site e preencher `terms_url`, `reviewed_by`, `reviewed_at` e `review_status` (`APPROVED` ou `RESTRICTED`) em `engine/config/sources.json`.
3. `RESTRICTED` quando os termos limitam o uso (ex.: sem redistribuição de texto): registrar a restrição em `compliance_notes` e ajustar `display`/`retention_days`.
4. Termos que proíbem a coleta: `enabled: false` (DISABLED). Nunca contornar login, CAPTCHA, paywall, robots ou limites.
