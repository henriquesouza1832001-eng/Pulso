"""Utilitários comuns dos coletores JSON."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from ..models import Signal


def loads(data: bytes) -> Any:
    """Algumas APIs públicas brasileiras respondem em Latin-1/cp1252 sem avisar."""
    try:
        return json.loads(data.decode("utf-8"))
    except UnicodeDecodeError:
        return json.loads(data.decode("cp1252", errors="replace"))


def aware(dt: datetime, now: datetime) -> datetime:
    """UTC, nunca no futuro."""
    return min(dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc), now)


def valid(signal: Signal) -> bool:
    return bool(signal.title.strip()) and signal.timestamp.tzinfo is not None
