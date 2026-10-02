# Antecipação de acontecimentos (o "Pizza Index do Brasil")

## Ideia
O Pizza Index funciona porque mede um **comportamento indireto que muda antes da notícia**. O PULSO faz o mesmo: em vez de esperar a matéria consolidada, detecta quando o conjunto de sinais públicos **foge do normal** para aquele lugar, tema e horário, e mostra isso como alerta antecipado, separado de confirmação.

## Princípio: antecipar ≠ afirmar
O PULSO **não prevê fatos nem resultados** (quem vai ganhar, se haverá crise). Ele emite **sinais antecipatórios**: "a cobertura/atividade sobre X em Y está N desvios acima do normal e acelerando". Cada alerta mostra evidências, confiança e estágio:

`ANOMALIA DETECTADA (conf. baixa)` → `MÚLTIPLOS SINAIS` → `IMPRENSA` → `FONTE OFICIAL`

Isso respeita as regras 55, 61 e 62: política nunca vira "chance de golpe", e sinal fraco nunca vira fato.

## O que já existe
Coleta RSS, deduplicação, clusterização, geolocalização, confiança e Pulso Score (`engine/`). **Falta o histórico**, e sem ele não há "normal" para comparar.

## Roteiro (cada item é um módulo / branch próprio)
1. **Histórico**: guardar séries por (escopo, categoria, janela) a cada rodada do Engine. A coleta precisa rodar de forma contínua (cron/container). *Pré-requisito de tudo abaixo.*
2. **Baseline** (`baseline.py`): média e variação por escopo × categoria × hora do dia × dia da semana, com EWMA. Só calcula quando há dados suficientes; antes disso, `anomaly = 0` (hoje é assim; não fingimos).
3. **Anomalia** (`anomaly.py`): z-score / percentil sobre menções, velocidade e aceleração, comparando 5 min × 5 min anteriores, e 15 min, 1 h, 6 h, 24 h.
4. **Descoberta de termos emergentes**: n-gramas que crescem juntos numa janela curta (ex.: "Praça Sete" + "fechada" + "polícia"), sem keyword cadastrada.
5. **Sensores adicionais** (só vias oficiais): Reddit e X por API oficial (com peso reduzido para perfis pequenos), trânsito, defesa civil/INMET, câmeras públicas autorizadas. Convergência de **tipos** de fonte pesa mais que volume.
6. **Calibração**: registrar cada alerta e o que aconteceu depois (acertou, errou, quanto antecipou). Sem isso não se afirma que o índice "antecipa" nada.

## Perfis pequenos no X/Reddit
Peso por tipo (`SOCIAL` < `SOCIAL_VERIFIED`), teto de confiança 40 quando só há social (já implementado), penalidade por rajada, texto repetido, conta nova e URLs repetidas (regra 49). Perfil pequeno **detecta**, mas nunca **confirma** sozinho.
