"""Calendario persistente della moglie di Giammarco.

La lettura immagini/OCR arriverà in un task futuro. Per ora usiamo solo codici
calendario già salvati o interpretati. L'unica regola operativa attiva è il
codice `M`: in quella data Giammarco non può aprire il lago alle 07:30.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

WifeCalendarCode = Literal["M", "P", "I", "F", "MPI"]

_SUPPORTED_CODES = {"M", "P", "I", "F", "MPI"}


@dataclass
class WifeCalendarRepository:
    """Archivio persistente minimale dei codici giornalieri già interpretati."""

    path: Path = field(default_factory=lambda: Path("data/wife_calendar.json"))

    def load(self) -> dict[str, WifeCalendarCode]:
        """Carica i codici salvati, se esistono."""

        if not self.path.exists():
            return {}
        with self.path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        return {str(day): code for day, code in data.items() if code in _SUPPORTED_CODES}

    def save(self, codes_by_date: dict[str, WifeCalendarCode]) -> None:
        """Salva codici già normalizzati da un futuro modulo OCR/import."""

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as file:
            json.dump(codes_by_date, file, ensure_ascii=False, indent=2, sort_keys=True)


def can_giammarco_open_lake_at_0730(code: str | None) -> bool:
    """Restituisce `False` solo se il codice calendario è `M`.

    Tutti gli altri codici, compresi `P`, `I`, `F`, colori già interpretati o
    dati mancanti, non sono vincoli di pianificazione in questa fase.
    """

    return code != "M"
