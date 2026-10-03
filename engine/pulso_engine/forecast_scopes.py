"""Nowcast por escopo (BR + estados): estende `forecast.py` sem alterar o previsor.

Cada escopo usa o PRÓPRIO histórico de Pulso (variações de 60 min), com as mesmas regras de honestidade: sem pares
suficientes não se prevê; o selo EXPERIMENTAL e a pontuação por Brier valem igual (o método leva o escopo no id).
Para respeitar o orçamento de escrita do banco, só entram escopos com Pulso atual relevante, no máximo `MAX_SCOPES`
por rodada, e os mais intensos primeiro.
"""
from __future__ import annotations

from datetime import datetime

from .forecast import make_nowcasts, resolve_due

MAX_SCOPES = 6  # previsões novas por rodada (2 perguntas por escopo): teto de escrita
MIN_CURRENT = 15  # abaixo disso o Pulso do escopo é ruído: "será >= 25?" não informa nada


def _current(points: list[dict]) -> float:
    return float(max(points, key=lambda p: p["timestamp"])["score"]) if points else 0.0


def make_scope_nowcasts(points_by_scope: dict[str, list[dict]], now: datetime, max_scopes: int = MAX_SCOPES,
                        min_current: float = MIN_CURRENT, include_br: bool = True) -> list[dict]:
    """Previsões novas para os escopos com histórico suficiente. O Brasil nunca é cortado pelo teto (já existe a v1)."""
    ranked = sorted(((s, p) for s, p in points_by_scope.items() if s != "BR" and _current(p) >= min_current),
                    key=lambda sp: (-_current(sp[1]), sp[0]))[:max_scopes]
    out: list[dict] = []
    if include_br and "BR" in points_by_scope:
        out.extend(make_nowcasts(points_by_scope["BR"], now, "BR"))
    for scope, pts in ranked:
        out.extend(make_nowcasts(pts, now, scope))
    return out


def resolve_scope_due(open_forecasts: list[dict], points_by_scope: dict[str, list[dict]], now: datetime) -> list[dict]:
    """Resolve cada previsão aberta com o histórico do SEU escopo (um escopo sem pontos não resolve: vence e anula
    pelas regras de `resolve_due`, nunca usa o Pulso de outro escopo)."""
    out: list[dict] = []
    for scope in sorted({f["scope"] for f in open_forecasts}):
        mine = [f for f in open_forecasts if f["scope"] == scope]
        out.extend(resolve_due(mine, points_by_scope.get(scope, []), now))
    return out
