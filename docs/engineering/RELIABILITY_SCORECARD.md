# Reliability Scorecard

Data de corte: 2026-10-03. Os status abaixo não são uma nota única; `VALIDATED` exige amostra quantitativa e reprodução independente.

| Dimensão | Status | Evidência | Falha/incerteza |
|---|---|---|---|
| Code reliability | MODERATE | 483 testes Python locais; replay, métricas e ciclos simulados | cobertura não equivale a tráfego real/caos completo |
| Data reliability | UNVERIFIED | manifesto de 9 eventos e 8 negativos criado | nenhum caso histórico real está COMPLETE |
| Geo reliability | WEAK | corpus editorial de 14 manchetes: V1 city accuracy 25%, V2 100%; false precision 0% nos 8 negativos inequívocos | amostra pequena e editorial; GEO_V2 continua OFF |
| Source reliability | WEAK | 282 fontes ativas com metadados básicos | 279 revisões de termos pendentes |
| Storage reliability | UNVERIFIED | batch, idempotência e trilhas em código | backend ativo/migrations/failover não ensaiados |
| Forecast reliability | UNVERIFIED | métricas e gate isolados disponíveis | sem amostra histórica/shadow live suficiente |
| Security reliability | MODERATE | Bearer fail-closed, Zod, parâmetros SQL, CORS configurável | sem rate limit/WAF, token admin compartilhado, configuração remota não auditada |
| Operational reliability | WEAK | healthcheck e cron em código | HTTP 200 com dados estagnados não gera STALE por fonte |

## Métricas disponíveis

- Testes locais: 483 pass, 24 avisos de conformidade pendente.
- Métricas de previsão (Brier, Brier Skill, ECE, FPR, recall, lead time): **N/A**; faltam desfechos reais completos e shadow pareado.
- Casos históricos: 0 COMPLETE de 9 planejados.
- Janelas negativas: 0 COMPLETE de 8 planejadas.
- Corpus Geo editorial (não histórico): V1 `city_accuracy=0.25`, V2 `city_accuracy=1.00`; V1/V2 `false_precision_rate=0.00` nos 8 negativos inequívocos; V2 `state_accuracy=0.80` contra V1 `1.00`; V2 se abstém em 64,29% das 14 manchetes contra 57,14% do V1. Um caso de Rio Branco é `DISPUTED`, fora das taxas de acerto/falsa precisão.

## Gate de promoção

Qualquer V2 permanece `SHADOW` ou `EXPERIMENTAL` até possuir amostra mínima, melhora de Brier, não regressão de calibração/FPR/recall, replay histórico, negativos, shadow live e rollback exercitado.

## Top 10 ações

1. Fechar a correção Geo V2 e medir o corpus antes da flag.
2. Adquirir o primeiro caso histórico verificável com quatro timestamps.
3. Adquirir uma janela negativa verificável por categoria de burst.
4. Formalizar schema de features/cutoff no replay e registry.
5. Ensaiar D1/Turso e falhas parciais localmente.
6. Tornar stale de conteúdo distinto de health de transporte.
7. Preservar shadow/driver em modo de orçamento ou registrá-los como indisponíveis.
8. Separar segredo admin do segredo de ingest e adicionar rate limit/WAF.
9. Revisar conformidade e direitos de retenção/exibição das 279 fontes.
10. Publicar métricas apenas quando as amostras completas existirem.
