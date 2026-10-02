"""Keyword engine: famílias de termos, recarregáveis sem redeploy.

Recarga: o arquivo é relido quando o mtime muda (ou via `reload()`); em produção a fonte
pode ser a tabela `keywords` do D1, mantendo esta mesma interface.
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

DEFAULT_PATH = Path(__file__).with_name("keywords.json")


def _fold(text: str) -> str:
    """Minúsculas e sem acentos: 'ARRASTÃO' casa com 'arrastao'."""
    nfkd = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


@dataclass(frozen=True)
class Match:
    family: str
    term: str


class KeywordEngine:
    def __init__(self, path: Path = DEFAULT_PATH) -> None:
        self._path = path
        self._mtime = 0.0
        self._patterns: list[tuple[str, str, re.Pattern[str]]] = []
        self.reload()

    def reload(self) -> None:
        families: dict[str, list[str]] = json.loads(self._path.read_text(encoding="utf-8"))
        self._patterns = [
            (fam, term, re.compile(rf"\b{re.escape(_fold(term))}\b"))
            for fam, terms in families.items()
            for term in terms
        ]
        self._mtime = self._path.stat().st_mtime

    def _maybe_reload(self) -> None:
        if self._path.stat().st_mtime != self._mtime:
            self.reload()

    def match(self, text: str) -> list[Match]:
        self._maybe_reload()
        folded = _fold(text)
        return [Match(fam, term) for fam, term, pat in self._patterns if pat.search(folded)]

    def classify(self, text: str) -> str | None:
        """Família dominante (mais termos casados); None se nada casar."""
        counts: dict[str, int] = {}
        for m in self.match(text):
            counts[m.family] = counts.get(m.family, 0) + 1
        return max(counts, key=counts.__getitem__) if counts else None
