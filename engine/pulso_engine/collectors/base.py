"""Interface de fonte. Nunca acople o sistema a uma fonte específica: cada fonte é um adaptador."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..models import Signal


class SourceAdapter(ABC):
    source_id: str
    source_class: str

    @abstractmethod
    def fetch(self) -> list[Any]:
        """Busca itens brutos. Deve respeitar API oficial, termos de uso e rate limits."""

    @abstractmethod
    def normalize(self, raw: Any) -> Signal | None:
        """Converte um item bruto em Signal; None se o item for inválido."""

    def validate(self, signal: Signal) -> bool:
        return bool(signal.title.strip()) and signal.timestamp.tzinfo is not None

    def geolocate(self, signal: Signal) -> Signal:
        """Geolocalização específica da fonte (opcional). Padrão: não altera."""
        return signal

    @abstractmethod
    def score_reliability(self, signal: Signal) -> int:
        """Confiabilidade 0-100 da FONTE (só um componente da confiança do evento)."""

    def run(self) -> list[Signal]:
        out: list[Signal] = []
        for raw in self.fetch():
            sig = self.normalize(raw)
            if sig is None or not self.validate(sig):
                continue
            out.append(self.geolocate(sig))
        return out
