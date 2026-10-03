# Previsão no PULSO (o "Pizza Index do Brasil")

## Decisão
O PULSO **prevê**. Qualquer pergunta sobre o futuro cuja resposta seja verificável com informação pública pode virar uma previsão: política, eleições, economia, segurança, clima, trânsito, infraestrutura, relações internacionais, saúde, eventos. Esta decisão substitui a regra anterior que proibia previsões políticas (ver ADR 0002).

O que a torna confiável **não é limitar o assunto, e sim a forma**: toda previsão é uma **probabilidade calibrada, rastreável e auditável**, nunca uma afirmação.

## O que é uma previsão
```
Forecast {
  forecast_id, question            "O Pulso BR passará de 70 nas próximas 24 h?"
  kind                             NOWCAST | EVENT | QUANTITY | OPEN
  horizon / resolves_at            quando a pergunta tem resposta
  probability (0–1) + intervalo    "62% (faixa 48–74%)"
  method + version                 qual modelo gerou
  evidence[]                       ids de sinais/eventos/séries que sustentam
  created_at
  outcome                          pendente | sim | não | anulada  (+ resolved_at, fonte da resolução)
  score                            Brier / log score depois de resolvida
}
```

## Tipos de previsão
| Tipo | Exemplo | Método inicial |
|---|---|---|
| **NOWCAST** (minutos–horas) | "Esta anomalia em BH vira evento nível 3+ em 2 h?" | baseline + anomalia (z-score/EWMA), aceleração de menções, convergência de tipos de fonte |
| **EVENT** (horas–dias) | "Haverá manifestação com bloqueio em Brasília até sexta?" | séries históricas por escopo×categoria, sazonalidade, sinais antecipatórios, taxas-base |
| **QUANTITY** | "Pulso Brasil amanhã às 18 h?", "Selic na próxima reunião?" | séries temporais (EWMA/ARIMA/regressão), intervalo de previsão |
| **OPEN** (qualquer tema) | "Quem lidera no 2º turno?", "A medida passa no Senado?" | combina taxas-base históricas + dados públicos (pesquisas registradas, calendário, votos, cobertura) em ensemble; LLM só ajuda a estruturar a pergunta e levantar evidências, **nunca produz o número sozinho** |

A cobertura jornalística e a atividade social são **sinais**, não a verdade: servem de entrada ao modelo e ficam listadas como evidência.

## Regras que mantêm a previsão honesta
1. **Rótulo sempre visível**: "PREVISÃO (probabilidade), não fato". Nunca no mesmo estilo visual de um evento confirmado.
2. **Probabilidade + incerteza**, nunca "vai acontecer". Sem dados suficientes → "dados insuficientes" em vez de chute.
3. **Histórico de acertos público**: cada previsão é registrada antes do resultado e pontuada depois (Brier score, curva de calibração). A página de uma previsão mostra o desempenho do método naquele tipo de pergunta. Previsões sem calibração suficiente saem marcadas como **EXPERIMENTAL**.
4. **Rastreabilidade**: evidências e versão do método guardadas; o "POR QUE?" mostra o que moveu a probabilidade (mesma lógica do score explicável).
5. **Previsão não eleva alerta**: o nível PULSO 4–5 continua exigindo confirmação por fontes (SCORING.md). Previsão alta de emergência gera "atenção antecipada", não alerta de emergência.
6. **Sem dados pessoais**: previsões sobre eventos, séries e instituições; nada de prever comportamento de indivíduos privados, nem perfilamento.
7. **Eleições**: previsões que usem pesquisas devem se apoiar em pesquisas **registradas na Justiça Eleitoral** e citar a fonte, e a publicação deve respeitar a legislação eleitoral vigente. Revisar isso com assessoria jurídica antes de publicar previsões eleitorais ao público.
8. **Reversibilidade**: o sistema precisa conseguir retirar/corrigir uma previsão e registrar a correção publicamente.

## Roteiro técnico (um módulo/branch por item)
1. **Histórico** (pré-requisito de tudo): gravar séries por (escopo, categoria, janela) a cada rodada. Exige coleta contínua (ver `docs/COLLECTION_PROTOCOL.md`).
2. **Baseline** (`baseline.py`): normal por escopo×categoria×hora×dia da semana. Até haver dados, `anomaly = 0` (não se finge).
3. **Anomalia e tendência** (`anomaly.py`, `trends.py`): z-score/EWMA, 5 min vs 5 min anteriores, e 15 min, 1 h, 6 h, 24 h.
4. **Termos emergentes**: n-gramas que crescem juntos sem keyword cadastrada.
5. **Registro de previsões** (`forecasts` no D1, `/api/forecasts`): criar, resolver, pontuar.
6. **Modelos por tipo** (NOWCAST → QUANTITY → EVENT → OPEN), cada um só sai de EXPERIMENTAL após calibrar.
7. **Sensores extras** por vias oficiais: Reddit/X (API oficial; perfis pequenos pesam menos e nunca confirmam sozinhos), trânsito, Defesa Civil/INMET, câmeras públicas autorizadas. Convergência de **tipos** de fonte pesa mais que volume.

## Estado da implementação (2026-10-03)
**Pronto (v1, tudo EXPERIMENTAL):**
- Tabela `forecasts` (migration 0003) e contrato `Forecast`. A previsão é **imutável**: o Worker só aceita preencher a resolução de uma previsão ainda aberta, e recusa probabilidade 0 ou 1, resolvida sem resultado e probabilidade fora do próprio intervalo.
- API pública: `GET /api/forecasts`, `/api/forecasts/:id`, `/api/forecasts/track-record` (Brier por método, taxa observada, curva de calibração em faixas de 20% e *skill* contra a referência ingênua). Toda resposta traz o aviso "PREVISÃO (probabilidade), não fato". Um método é EXPERIMENTAL até resolver 100 previsões.
- Previsor `pulse_empirical_delta` v1 (NOWCAST): "o Pulso do Brasil será ≥ T daqui a 60 min?", com T = atual+10 e atual+20 (arredondado a 5). Probabilidade pela distribuição empírica das variações de 60 min do próprio histórico do Pulso, com suavização de Laplace e intervalo de Wilson. **Só prevê com ≥ 36 pares de histórico (~3,5 h contínuas); sem isso não prevê.**
- Resolução automática com o valor **real** observado; sem observação em até 30 min do vencimento a previsão é **anulada** (`void`), nunca estimada.

**Falta:** previsores de EVENT (um evento chega ao nível 3+?), QUANTITY por estado e OPEN; modelos que usem mais do que a persistência do Pulso; sazonalidade; a avaliação de quando um método deixa de ser experimental com base no *skill*, não só na contagem.
