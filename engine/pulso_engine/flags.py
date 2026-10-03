"""Feature flags do motor: toda inteligência V2 pode ser desligada sem deploy de código (docs/engineering/ENGINE_V2_PLAN.md).

Regra: um V2 só vira padrão LIGADO depois de passar o portão de promoção (shadow, backtest, comparação com o V1). Até lá
o padrão é DESLIGADO, exceto o que já roda em produção como SHADOW (só grava dados, nunca muda evento, Pulso, alerta ou previsão).

Como ligar/desligar: variável de ambiente `PULSO_FLAG_<NOME>` (`1/true/on` liga; `0/false/off` desliga), por exemplo como
variável do repositório no `collect.yml`. Sem variável vale o padrão abaixo. Nome desconhecido é erro (evita typo silencioso).
"""
from __future__ import annotations

import os

# nome -> (padrão, estado, o que faz)
FLAGS: dict[str, tuple[bool, str, str]] = {
    "HISTORY_OBSERVATIONS": (True, "SHADOW", "agrega contagens por hora e envia ao banco; só grava, não muda nada visível"),
    "FORECAST_REGISTRY": (True, "SHADOW", "grava a trilha de auditoria (snapshot + hash) de cada previsão nova em forecast_registry; só grava, não muda nada visível"),
    "SENTINEL": (True, "SHADOW", "abre/avança investigações; só grava em `investigations`, não muda evento, Pulso, alerta nem previsão"),
    "SEASONAL_BASELINE_V2": (False, "OFF", "usa seasonal_baseline (hora x dia da semana) em cluster_anomaly quando válido; senão EWMA"),
    "ANOMALY_V2": (False, "OFF", "anomalia por janela com percentil e separação score/confiança"),
    "CLUSTER_REFINE": (False, "OFF", "refino de clusters por entidades, geo e afinidade (processing/cluster_refine.py)"),
    "SEMANTIC_CLUSTERING": (False, "OFF", "zona cinza do clustering resolvida por embedding local (adiado: sem NLP pesado por ora)"),
    "GEO_V2": (False, "OFF", "gazetteer dos municípios e evidências de geolocalização"),
    "CONFIDENCE_V2": (False, "OFF", "confiança com publisher != origin, diversidade de sensores e contradição"),
    "SEVERITY_V2": (False, "OFF", "severidade por vetor de impacto"),
    "PULSE_V2": (False, "OFF", "pesos do Pulso com aceleração e diversidade de tipos de sensor (scoring/pulse.py: WEIGHTS_V2); o V1 fica intacto"),
    "NATIONAL_PULSE_V2": (False, "OFF", "Pulso nacional com dispersão geográfica e diversidade"),
    "DRIVER_VALIDATOR": (False, "OFF", "driver só afeta previsão se melhorar o Brier (registro de drivers)"),
    "EVENT_ESCALATION": (False, "OFF", "P(evento subir de nível) em shadow, depois experimental"),
    "FORECAST_V2_SHADOW": (False, "OFF", "previsor V2 do Pulso (condicionado à hora do dia) em shadow: guarda a probabilidade em evidence.shadow_v2 e grava V1 x V2 x desfecho em shadow_results quando resolve; nunca muda a previsão exibida"),
    "CONTEXT_ENGINE": (False, "OFF", "feriados, jogos e eventos ajustam baseline/anomalia (nunca viram confirmação)"),
}

_TRUE = {"1", "true", "on", "yes", "sim"}
_FALSE = {"0", "false", "off", "no", "nao", "não"}


def enabled(name: str, env: dict[str, str] | None = None) -> bool:
    if name not in FLAGS:
        raise KeyError(f"feature flag desconhecida: {name}")
    raw = (os.environ if env is None else env).get(f"PULSO_FLAG_{name}", "").strip().lower()
    if raw in _TRUE:
        return True
    if raw in _FALSE:
        return False
    return FLAGS[name][0]


def snapshot(env: dict[str, str] | None = None) -> dict[str, bool]:
    """Estado efetivo de todas as flags (para registrar no log do ciclo e nas previsões)."""
    return {name: enabled(name, env) for name in FLAGS}
