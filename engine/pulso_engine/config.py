"""Carrega e VALIDA config/sources.json: uma fonte sem os campos do protocolo não entra.

Ver docs/COLLECTION_PROTOCOL.md (seções 3 e 4).
"""
from __future__ import annotations

import json
import warnings
from pathlib import Path
from typing import get_args

from .models import Category

SOURCE_CLASSES = {"OFFICIAL", "NEWS_HIGH", "NEWS_REGIONAL", "TRAFFIC_PROVIDER", "SOCIAL_VERIFIED", "SOCIAL", "UNKNOWN"}
ACCESS = {"official_api", "open_data", "public_feed", "sitemap", "public_page", "authorized_scrape"}
CATEGORIES = set(get_args(Category))
UFS = {"AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR",
       "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"}
DISPLAY = {"headline_link", "metrics_only", "full"}
REQUIRED = ("id", "name", "adapter", "source_class", "url", "access", "terms_url", "interval_s",
            "retention_days", "display", "reviewed_by", "reviewed_at")
MIN_INTERVAL_S = {"rss": 300, "sitemap": 300, "api": 60, "social": 60, "x": 300, "inmet": 300, "gdelt": 900, "mastodon": 600, "usgs": 600, "inpe_fires": 300, "bcb_ptax": 900}


PENDING = "PENDENTE"
DEFAULT_SOURCES_PATH = Path(__file__).resolve().parent.parent / "config" / "sources.json"


class SourceConfigError(ValueError):
    pass


def pending_items(src: dict) -> list[str]:
    """Campos de conformidade ainda não confirmados por uma pessoa."""
    return [k for k in ("terms_url", "reviewed_by", "reviewed_at") if src.get(k) == PENDING]


def validate_source(src: dict) -> None:
    sid = src.get("id", "<sem id>")
    missing = [k for k in REQUIRED if src.get(k) in (None, "")]
    if missing:
        raise SourceConfigError(f"{sid}: faltam campos do protocolo: {', '.join(missing)}")
    if src["source_class"] not in SOURCE_CLASSES:
        raise SourceConfigError(f"{sid}: source_class inválida")
    if src["access"] not in ACCESS:
        raise SourceConfigError(f"{sid}: access deve ser um de {sorted(ACCESS)}")
    if src["display"] not in DISPLAY:
        raise SourceConfigError(f"{sid}: display inválido")
    if not str(src["url"]).startswith(("http://", "https://")):
        raise SourceConfigError(f"{sid}: url deve ser http(s)")
    if src["terms_url"] != PENDING and not str(src["terms_url"]).startswith("http"):
        raise SourceConfigError(f"{sid}: terms_url deve ser http(s) ou PENDENTE")
    floor = MIN_INTERVAL_S.get(src["adapter"], 60)
    if int(src["interval_s"]) < floor:
        raise SourceConfigError(f"{sid}: interval_s {src['interval_s']} abaixo do mínimo {floor} para {src['adapter']}")
    if src["access"] in ("public_page", "sitemap") and not src.get("robots_checked"):
        raise SourceConfigError(f"{sid}: robots_checked obrigatório para {src['access']}")
    if src["access"] == "authorized_scrape" and not src.get("authorization_ref"):
        raise SourceConfigError(f"{sid}: authorized_scrape exige authorization_ref (autorização escrita)")
    if not (1 <= int(src["retention_days"]) <= 3650):
        raise SourceConfigError(f"{sid}: retention_days fora de 1–3650")
    if src["adapter"] in ("reddit", "x"):
        if src["access"] != "official_api" or src["source_class"] != "SOCIAL":
            raise SourceConfigError(f"{sid}: sensor social exige official_api e SOCIAL")
        needed = "subreddit" if src["adapter"] == "reddit" else "query"
        if not src.get(needed):
            raise SourceConfigError(f"{sid}: adapter {src['adapter']} exige '{needed}'")
        if (regional := src.get("subreddit_states")) is not None:
            subs = {s.lower() for s in str(src.get("subreddit", "")).split("+")}
            if not isinstance(regional, dict) or not all(
                    k.lower() in subs and v in UFS for k, v in regional.items()):
                raise SourceConfigError(f"{sid}: subreddit_states deve mapear comunidades de 'subreddit' para UFs")
        if (cats := src.get("categories")) is not None and (not cats or not set(cats) <= CATEGORIES):
            raise SourceConfigError(f"{sid}: categories inválidas")
        if src.get("enabled") and (pending_items(src) or not src.get("authorization_ref")):
            raise SourceConfigError(f"{sid}: autorização e revisão obrigatórias antes de ativar")


def load_sources(path: Path, only_enabled: bool = True) -> list[dict]:
    sources = json.loads(path.read_text(encoding="utf-8"))
    ids = [s.get("id") for s in sources]
    if len(ids) != len(set(ids)):
        raise SourceConfigError("ids de fonte duplicados")
    pending: list[str] = []
    for s in sources:
        validate_source(s)
        if s.get("enabled", True) and pending_items(s):
            pending.append(s["id"])
    if pending:
        # Fontes ativas sem revisão humana seguem em operação, mas com UM aviso agregado (e não um por fonte).
        shown = ", ".join(pending[:8]) + (f" e mais {len(pending) - 8}" if len(pending) > 8 else "")
        warnings.warn(f"conformidade pendente em {len(pending)} fonte(s) ativa(s): {shown}. Ver COLLECTION_PROTOCOL.md §4.",
                      stacklevel=2)
    return [s for s in sources if s.get("enabled", True)] if only_enabled else sources
