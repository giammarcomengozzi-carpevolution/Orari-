"""Predisposizione per il calendario persistente della moglie di Gianmarco.

La lettura immagini/OCR arriverà in un task futuro. Per ora offriamo un piccolo
repository JSON e un punto di integrazione stabile per le regole sui codici M,
P, I e MPI.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

WifeCalendarCode = Literal["M", "P", "I", "MPI"]


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
        return {str(day): code for day, code in data.items() if code in {"M", "P", "I", "MPI"}}

    def save(self, codes_by_date: dict[str, WifeCalendarCode]) -> None:
        """Salva codici già normalizzati da un futuro modulo OCR/import."""

        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as file:
            json.dump(codes_by_date, file, ensure_ascii=False, indent=2, sort_keys=True)


def can_gianmarco_open_lake_at_0730(code: WifeCalendarCode | None) -> bool | None:
    """Valuta la futura regola di apertura lago delle 07:30 per Gianmarco.

    Restituisce `None` per casi non ancora implementati o dati mancanti.
    """

    if code == "M":
        return False
    if code in {"P", "I"}:
        return True
    return None
