# Protocolo de coleta de informação

Vale para **toda** fonte, humana ou agente. Quem integra uma fonte segue este protocolo; o Engine recusa carregar uma fonte que não traga os campos exigidos (`engine/pulso_engine/config.py`).

## 1. Princípios
1. **Só vias autorizadas.** Nunca contornar login, captcha, paywall, limite de taxa ou termos. Sem contas falsas, sem raspagem de plataformas que a proíbem, sem câmeras privadas.
2. **Mínimo necessário.** Guardamos título, resumo curto (≤ 500 caracteres), link, data, autoria e fonte. Não copiamos texto integral. Sempre com atribuição e link para o original.
3. **Nenhuma fonte é ponto único de falha.** Falha vira `source_health`, nunca queda do ciclo.
4. **Sinal ≠ fato.** A classe da fonte (`OFFICIAL`, `NEWS_HIGH`, … `SOCIAL`) define o peso; rede social detecta, não confirma sozinha.
5. **Tudo auditável.** Para cada dado: de onde veio, quando foi coletado, por qual versão do coletor.

## 2. Ordem de preferência do método
1. API oficial (com chave própria) → 2. dados abertos/feeds estruturados → 3. RSS/Atom → 4. sitemap → 5. página pública permitida pelo `robots.txt` e pelos termos → 6. raspagem **somente com autorização escrita** do dono.

## 3. Ciclo de vida de uma fonte
`PROPOSTA → REVISADA → PILOTO → ATIVA → DEGRADADA → APOSENTADA`
- **Proposta**: PR com a ficha em `docs/sources/SOURCES.md` e a entrada em `engine/config/sources.json` com `"enabled": false`.
- **Revisada**: outra pessoa confere o checklist da seção 4 e registra `reviewed_by`/`reviewed_at`.
- **Piloto**: roda em `--dry-run` (sem `--push`), avaliando volume, qualidade e erros por pelo menos 48 h.
- **Ativa**: `enabled: true`. **Degradada**: erros ou itens vazios recorrentes (ver seção 8). **Aposentada**: removida, mantendo o histórico conforme retenção.

## 4. Checklist de admissão (todos os itens antes de ativar)
- [ ] API/termos oficiais lidos; link guardado em `terms_url`.
- [ ] O uso (coletar, armazenar, **exibir publicamente**, e **usar em modelos de previsão**) é permitido? Registrar em `display` e na ficha.
- [ ] Autenticação e segredos necessários: nomes dos secrets, nunca valores.
- [ ] Limites de taxa e custo; cadência escolhida (`interval_s`) cabe com folga.
- [ ] `robots.txt` verificado quando for página/sitemap (`robots_checked`).
- [ ] Retenção definida (`retention_days`) e compatível com os termos.
- [ ] Fallback se a fonte cair e fonte alternativa para o mesmo assunto.
- [ ] Classe de confiabilidade (`source_class`) justificada.
- [ ] Sem dados pessoais de pessoas privadas; se houver, descrever tratamento.

## 5. Como coletar
| Item | Regra |
|---|---|
| Identificação | `User-Agent: pulso-engine/<versão> (+URL do projeto)`. Nunca fingir ser navegador. |
| Cadência | Notícias RSS ≥ 300 s; oficiais conforme a API; sociais conforme cota. Adicionar *jitter* de ±10% para não sincronizar rajadas. |
| Requisição condicional | Usar `ETag`/`If-Modified-Since` quando a fonte suportar. |
| Timeout e tamanho | 15 s e 5 MB por requisição. |
| Falha | Backoff exponencial (1, 2, 4… até 30 min), respeitando `Retry-After`. Após 3 falhas seguidas → `DEGRADED`; após 1 h sem sucesso → `OFFLINE`. `429` → `RATE_LIMITED` e pausa. `401/403` → `AUTH_ERROR` e alerta humano (não insistir). |
| Segurança do parser | Recusar XML com `<!ENTITY`; limitar tamanho; tratar texto como não confiável (nada de HTML do feed é renderizado). |
| Datas | UTC; data no futuro é limitada ao instante da coleta; sem data → data da coleta. |

## 6. Qualidade e deduplicação
- `hash` = URL canônica (sem `utm_*`, `fbclid`, fragmento); sem URL, título normalizado.
- Mesma matéria replicada não vira várias confirmações (`duplicate_ratio` reduz a confiança).
- Idempotência: reenviar o mesmo lote não duplica (upsert por chave).
- Descartar itens sem título ou com timestamp inválido; contar descartes na saúde da fonte.

## 7. Retenção e privacidade
Sinais: `retention_days` por fonte (padrão 90). Séries agregadas (Pulso, contagens, baseline) são mantidas por mais tempo, pois alimentam a previsão e não contêm conteúdo de terceiros. Pedido de remoção de uma fonte ou matéria é atendido removendo o sinal e recalculando os eventos afetados. Nenhuma coleta de dados pessoais de indivíduos privados; sem reconhecimento facial.

## 8. Saúde das fontes
`ONLINE → DEGRADED → OFFLINE`, com `RATE_LIMITED` e `AUTH_ERROR` à parte. Estado e motivo vão para `source_health` e para `/api/health`, e alimentam o painel administrativo. Mudança de estado repetida (flapping) gera alerta.

## 9. Histórico para a previsão
Toda rodada grava, além dos eventos, **séries agregadas** por (escopo, categoria, janela): contagem de sinais, de fontes distintas, velocidade e Pulso. Sem esse histórico não existe baseline nem previsão calibrada (ver `PREDICTION.md`). Por isso a coleta precisa rodar de forma contínua e sem lacunas; lacunas são registradas, não preenchidas.

## 10. Execução e agendamento
- Coleta periódica por agendador (GitHub Actions `schedule`, intervalo mínimo 5 min, ou container/VM para tempo real), com `concurrency` para impedir duas rodadas simultâneas.
- Um ciclo = coletar → processar → enviar lote ao Worker (`/api/ingest`). Falha de envio não perde dados: o lote é reenviável (idempotente).
- Ambientes separados (local / staging / produção); piloto sempre sem `--push` em produção.

## 11. Segredos
Chaves de API só em secrets (GitHub Actions / `wrangler secret`), nomeados por fonte (`X_BEARER_TOKEN`, `REDDIT_CLIENT_SECRET`…). Nunca no Git, nunca em logs, nunca no frontend. Chave vazada → rotacionar imediatamente.

## 12. Estado das integrações pedidas
| Fonte | Via permitida | Situação |
|---|---|---|
| Sites de notícias | RSS/Atom, sitemaps | ✅ ~100 feeds ativos (ver `docs/sources/CATALOGO_FONTES.md`); revisão de termos pendente |
| Órgãos oficiais (Defesa Civil, INMET, PRF, TSE, IBGE, BC…) | APIs e dados abertos | ⏳ próximo; verificar termos de cada um |
| Reddit | API oficial; exige registro do app e respeito aos termos (uso comercial pode exigir acordo) | ⏳ revisar termos antes |
| X (Twitter) | API oficial paga, por plano | ⏳ decisão de custo; perfis pequenos com peso baixo; nunca confirma sozinho |
| Waze | Programa *Waze for Cities* (parceiros públicos) | ⏳ depende de parceria formal |
| Google (Maps/Trends/Notícias) | Os termos do Maps Platform proíbem extrair e reutilizar seus dados; o mapa de calor do PULSO é gerado a partir dos **nossos** eventos (MapLibre). Google News RSS: termos a revisar. | ❌ sem extração do Maps |
| Instagram | Graph API cobre só contas próprias/de negócio autorizadas | ⏳ uso restrito |
| Câmeras de trânsito | Somente feeds que o órgão dono libera oficialmente | ⏳ Fase 3, por autorização |

## 13. Painel administrativo
Fonte da verdade: `source_health`, contagem de sinais por fonte/hora, erros, último sucesso e backlog. O painel lê `/api/health` e endpoints `/api/admin/*` protegidos (Cloudflare Access ou token), nunca públicos.

## 14. Pendências de conformidade (fontes já em operação)
As fontes RSS foram ligadas **antes** deste protocolo (e o catálogo de ~100 feeds foi ativado depois, por decisão do dono, ADR 0006). Ficam como `PENDENTE` em `engine/config/sources.json` até uma pessoa ler os termos de cada site, confirmar que coletar o RSS, exibir título/link com atribuição e usar a série em previsões é permitido, e preencher `terms_url`, `reviewed_by` e `reviewed_at`. Hoje isso gera um aviso agregado a cada rodada. Links de termos confirmados: EBC (Agência Brasil) e UOL; G1, Folha e CNN Brasil ainda sem link verificado.
