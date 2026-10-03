"""Normalização: texto limpo, URL canônica e hash de deduplicação."""
from __future__ import annotations

import hashlib
import html
import re
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")
_TRACKING = ("utm_", "fbclid", "gclid", "ref", "cmpid", "origin")


def clean_text(raw: str | None, limit: int = 600) -> str:
    text = html.unescape(_TAG.sub(" ", raw or ""))
    text = _WS.sub(" ", text).strip()
    return text[:limit]


def fold(text: str) -> str:
    """Minúsculas e sem acentos."""
    nfkd = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def canonical_url(url: str | None) -> str | None:
    if not url:
        return None
    parts = urlsplit(url.strip())
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return None
    query = [(k, v) for k, v in parse_qsl(parts.query) if not k.lower().startswith(_TRACKING)]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme, parts.netloc.lower(), path, urlencode(query), ""))


def normalized_title(title: str) -> str:
    return _WS.sub(" ", re.sub(r"[^a-z0-9 ]", " ", fold(title))).strip()


def content_hash(canonical: str | None, title: str) -> str:
    """Mesma URL canônica (ou, sem URL, mesmo título) = mesma matéria."""
    basis = canonical or normalized_title(title)
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:32]


# Programação de telejornal (não é notícia): "Assista ao JRO2 desta sexta", "Jornal X 2ª Edição de sexta-feira", "VÍDEO: AB2 de sexta".
_WEEKDAY = r"(segunda|ter[cç]a|quarta|quinta|sexta|s[áa]bado|domingo)"
_BROADCAST_LISTING = re.compile(
    rf"(edi[cç][aã]o de {_WEEKDAY}|assista ao [a-z]{{1,4}}\d? desta|^v[ií]deos?:\s*[a-z]{{1,4}}\d? de {_WEEKDAY})",
    re.IGNORECASE,
)


def is_broadcast_listing(title: str) -> bool:
    """True para chamadas de edição de telejornal. Padrões específicos: 'Vídeo: Veja os horários de votação' é notícia."""
    return bool(_BROADCAST_LISTING.search(title or ""))

