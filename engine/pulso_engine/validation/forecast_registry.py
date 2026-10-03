"""Registro de previsões para REPRODUTIBILIDADE: o que o modelo viu quando previu.

Cada previsão ganha um snapshot imutável: features, versões (modelo, features, baseline) e flags ativas, com um hash
do conteúdo. Dá para provar depois que a previsão não foi alterada e explicar por que ela saiu daquele jeito. Só entra
o que é necessário para reproduzir (não conteúdo de terceiros). A previsão em si continua em `forecasts`; isto é a
trilha de auditoria ao lado dela (migration 0008 `forecast_registry`, a ser aplicada por quem mantém o banco).
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime

from .. import flags


def _canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def build_entry(forecast: dict, features: dict, now: datetime, model_version: str, feature_version: str,
                baseline_version: str, active_flags: dict[str, bool] | None = None) -> dict:
    """Entrada de registro para `forecast` (dict com `forecast_id`). `features`: números/strings simples que alimentaram
    o modelo (ex.: Pulso atual, pares, baseline). Flags: por padrão o estado efetivo atual (`flags.snapshot()`)."""
    body = {"features": features, "model_version": model_version, "feature_version": feature_version,
            "baseline_version": baseline_version, "flags": active_flags if active_flags is not None else flags.snapshot(),
            "probability": forecast["probability"], "method": forecast["method"], "method_version": forecast["method_version"],
            "scope": forecast["scope"], "threshold": forecast["threshold"]}
    return {"forecast_id": forecast["forecast_id"], "created_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "snapshot": _canonical(body), "snapshot_hash": hashlib.sha256(_canonical(body).encode()).hexdigest()}


def verify(entry: dict) -> bool:
    """O snapshot guardado ainda corresponde ao hash? (detecta alteração posterior)."""
    return hashlib.sha256(entry["snapshot"].encode()).hexdigest() == entry["snapshot_hash"]


def new_entries(entries: list[dict], already_registered: set[str]) -> list[dict]:
    """Escrita condicional: o registro é imutável, então só se envia o que ainda não existe."""
    return [e for e in entries if e["forecast_id"] not in already_registered]


def reproduces(entry: dict, forecast: dict) -> bool:
    """A previsão atual bate com o que o registro diz que foi prevista? (probabilidade, método, escopo e limiar)."""
    snap = json.loads(entry["snapshot"])
    return verify(entry) and all(snap[k] == forecast[k] for k in ("probability", "method", "method_version", "scope", "threshold"))
