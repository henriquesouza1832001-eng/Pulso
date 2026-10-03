# FORECAST V2: briefing de engenharia (do dono, 2026-10-03)

> Resumo fiel do prompt "PULSO — FORECAST V2 ENGINEERING". **Responsável: Claude A (`claude-motor`)**, dona do `forecast_v2.py` e dos módulos de inteligência. **Codex mede e tenta quebrar. Claude B (`claude-hen`) entrega a plataforma** (armazenamento, versões, rotas, pipeline). O relatório vivo é `docs/engineering/FORECAST_V2_ENGINEERING.md` (Claude A cria e mantém).

## Regras de ouro
- **Codex mede, Claude implementa, Codex tenta quebrar de novo.** Nenhuma feature entra porque "parece fazer sentido": entra porque há hipótese testável.
- **Não alterar** `validation/`, golden datasets, replay científico, métricas e expected outputs do Codex, nem o Reliability Scorecard, para o modelo parecer melhor. Nunca ler expected outcomes dentro do modelo nem criar regra por ID de cenário.
- **Não criar Forecast V3**: evoluir o V2. V1 preservado; V2 permanece **SHADOW/EXPERIMENTAL**; nunca substitui o V1 sozinho; nada afeta alerta público; canary só depois do Reliability Gate (não nesta tarefa).
- Nada de previsão política (vencedor, ranking, "perigo" de candidato). Forecast é sobre eventos/situações operacionais.
- Sem deep learning. **Modelo simples primeiro**: se o V2 ainda é heurístico, preserve-o e crie uma camada experimental separada; primeiro candidato estatístico = regressão logística simples e regularizada, se dados e dependências permitirem. Sempre manter o modelo ingênuo (frequência histórica) como referência.

## Arquitetura alvo
```text
EVENT STATE → FEATURE SNAPSHOT → FEATURE QUALITY → MISSINGNESS → FORECAST MODEL → RAW PROBABILITY
  → CALIBRATOR → CALIBRATED PROBABILITY → UNCERTAINTY → ABSTENTION → FORECAST REGISTRY
```
- **Snapshot reproduzível** por previsão, só com features existentes naquele instante: `feature_version`, `data_cutoff`, `model_version`, `calibrator_version`, `context_version`, `baseline_version`. Mesmo snapshot + mesma versão = mesmo forecast (determinismo).
- **Versões:** qualquer mudança que altere a probabilidade = nova `model_version`; mudança semântica de feature = nova `feature_version`; pesos/configuração também reproduzíveis.
- **Registro append-only**: nova evidência gera NOVA previsão, nunca altera a antiga (isso dá a **trajetória** 18% → 27% → 43% → 71% → evento). Histerese só se o Codex demonstrar instabilidade, sem esconder mudança real.

## Grupos de features (nem todos precisam existir)
baseline, anomaly, velocity, acceleration, persistence, severity, confidence, origin_diversity, sensor_diversity, official_signal, social_signal, news_signal, weather, hydrology, traffic, energy, internet, aviation, public_attention, context, geo, sensor_health.
- **Ausência nunca vira zero em silêncio:** distinguir `VALUE_ZERO`, `MISSING`, `STALE`, `UNAVAILABLE`, `NOT_APPLICABLE`.
- **Cobertura de sensores:** `expected_sensor_classes`, `available`, `missing`, `stale`, e `coverage ratio` quando fizer sentido.
- **Qualidade do dado:** não misturar `event confidence` com `sensor health`.
- **Origem independente, não nº de publishers:** 100 republicações não são 100 evidências.
- **Derivadas só com o passado:** velocity, acceleration, persistence, change_from_baseline; janelas 5m/15m/30m/60m/3h/6h sem criar centenas de features (o Codex faz ablation).
- **Anomalia:** magnitude, duração, velocidade e concordância entre sensores. **Concordância entre famílias independentes** (clima + hidrologia + trânsito) vale mais que 50 notícias; **discordância** (social alto, físico e oficial normais) aumenta a **incerteza**, não necessariamente a probabilidade.
- **Drivers:** só `ACTIVE`/validado; nunca candidato como evidência forte; respeitar o lag (chuva T-60 prevê alagamento T; relato de alagamento em T não prevê alagamento em T).
- **Contexto** (rush, jogo, feriado, show) ajusta a **expectativa**, nunca confirma; criar o conceito interno **expectedness** (trânsito alto 18h de segunda é esperado; colapso às 3h é inesperado).
- Também: `event_age`/`evidence_age`, **taxa de chegada de origens independentes**, **velocidade de confirmação** (classes de sensor independentes), **espalhamento geográfico** (ponto único / várias cidades / vários estados, sem inventar precisão; velocidade geográfica só se cientificamente válida e sem inferir propagação causal), e ciência da **categoria** (FLOOD, BLACKOUT, FIRE, INTERNET_OUTAGE, TRAFFIC_COLLAPSE não têm os mesmos pesos, mas sem modelos por categoria sem dados).
- Diagnóstico de **features redundantes** (não remover sozinho; documentar para o Codex) e **não contar o mesmo sinal várias vezes** (anomalia, velocidade e confiança compartilham informação).

## Calibração, incerteza e abstenção
- **Separar** `raw_probability` de `calibrated_probability`; nunca sobrescrever em silêncio.
- **Calibrador = artefato versionado**: método, janela de ajuste, nº de amostras, versão; nunca calibrar com dado de teste/futuro. Amostra insuficiente: **não** aplicar calibrador complexo (`UNCALIBRATED_EXPERIMENTAL` ou método simples já validado). **Sem isotônica em amostra pequena**; só com ganho fora do tempo demonstrado pelo Codex.
- **Probabilidade nunca 0 nem 1** em modelo experimental; extrema exige evidência extrema.
- **Saída:** `probability`, `uncertainty`, `coverage`, `status`. Incerteza sobe com sensor ausente, sensor parado, evidência conflitante, pouca amostra e ambiguidade geográfica.
- **Abstenção (`INSUFFICIENT_DATA`)** quando: cobertura muito baixa, dado parado, evento sem geo suficiente, snapshot incompleto ou modelo fora de domínio. Não fabricar probabilidade.
- **Fora de distribuição (OOD):** sinal simples (valores muito fora do treino), por categoria e por região com pouquíssimo histórico: aumentar incerteza ou abster. Informar `historical_support_count` quando houver modelo treinado.
- **Taxa-base:** saber a taxa-base do alvo (evento raro ≠ probabilidade alta só porque há sinais); prior sazonal (hora, dia da semana, mês, categoria, geo) com **fallback hierárquico** registrado: cidade/categoria/hora → estado/categoria/hora → nacional/categoria/hora → nacional/categoria → taxa global. Raciocínio prior + evidência nova = posterior, sem modelo bayesiano pesado.
- **Explicabilidade:** cada previsão mostra os principais grupos de evidência que contribuíram (não causalidade; nunca "porque a IA disse").

## Laço com o Codex e com o Sentinela
- **Falso positivo/negativo:** descobrir a **causa geral** (sensor ausente? tardio? feature fraca? geo ruim? cluster ruim? limiar?) e corrigir com feature/contexto geral → shadow → Codex retesta. Nunca regra para um caso (ruim: `if "Flamengo" subtrair 20`; bom: contexto `scheduled_mass_event`).
- **Aquisição de sensores:** o Codex mostra o que melhora Brier/lead time; hidrologia melhora? priorizar hidrologia; 50 RSS a mais não mexem no Brier? não adicionar.
- **Sentinela + Forecast:** o Forecast emite `missing_evidence_priorities` (ex.: HYDROLOGY: HIGH, OFFICIAL: HIGH, TRAFFIC: MEDIUM, MORE_NEWS: LOW) e o information gain, se existir, integra de forma compatível. Não inventar dado.
- **Handoff por experimento** (mensagem no AgentBus):
```text
HANDOFF  FROM: CLAUDE  TO: CODEX
HYPOTHESIS: | CHANGE: | FEATURES: | MODEL_VERSION: | FEATURE_VERSION:
EXPECTED BENEFIT: | EXPECTED FAILURE MODE: | FILES: | TEST COMMAND:
```

## Ordem de prioridade (não inverter)
P0 correção temporal → P1 snapshot de features → P2 missing/stale → P3 cobertura de sensores → P4 diversidade de origem → P5 concordância/discordância entre sensores → P6 taxa-base e prior sazonal → P7 camada de calibração → P8 incerteza → P9 abstenção → P10 novas features preditivas.

## Divisão de trabalho
| Quem | O que |
|---|---|
| **Claude A (`claude-motor`)** | todo o núcleo P0 a P10 em arquivos do engine (`forecast_v2*.py`, `intelligence/`), o relatório `FORECAST_V2_ENGINEERING.md` e os handoffs ao Codex |
| **Codex** | mede (ablation, calibração fora do tempo, FP/FN, lead time), tenta quebrar, decide o portão; não edita o modelo |
| **Claude B (`claude-hen`)** | plataforma: persistência dos campos novos do registro, artefato de calibrador versionado, trajetória de previsões, rotas de leitura, ligação no pipeline atrás de flag, orçamento de escrita |

> Meta final: não "mais inteligente", e sim **mais calibrado, mais antecipatório, menos suscetível a falsos sinais e mais consciente do que não sabe**. O melhor Forecast V2 antecipa quando há sinal real, fica cauteloso quando a evidência é fraca e admite quando ainda não sabe.
