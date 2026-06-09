"""Regole fisse delle due attività.

Questo modulo contiene solo dati di business stabili: giorni di apertura,
orari e persone principali. La logica di generazione e validazione vive in
moduli separati, così in futuro sarà semplice aggiungere PDF, WhatsApp o OCR.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ActivityId(StrEnum):
    """Identificativi interni delle attività pianificate."""

    LAKE = "lake"
    SHOP = "shop"
    COMPANY_WORK = "company_work"


@dataclass(frozen=True)
class TimeRange:
    """Intervallo orario nel formato HH:MM."""

    start: str
    end: str

    def label(self) -> str:
        return f"{self.start}-{self.end}"


@dataclass(frozen=True)
class ActivityRules:
    """Regole di apertura e copertura di una singola attività."""

    activity_id: ActivityId
    name: str
    activity_type: str
    open_days: tuple[str, ...]
    closed_days: tuple[str, ...]
    morning: TimeRange
    afternoon: TimeRange
    default_person: str
    notes: str = ""


WEEK_DAYS: tuple[str, ...] = (
    "Lunedì",
    "Martedì",
    "Mercoledì",
    "Giovedì",
    "Venerdì",
    "Sabato",
    "Domenica",
)

TENUTA_DEL_GERMANO = ActivityRules(
    activity_id=ActivityId.LAKE,
    name="Tenuta del Germano",
    activity_type="lago di pesca sportiva",
    open_days=("Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"),
    closed_days=("Lunedì",),
    morning=TimeRange("07:30", "14:00"),
    afternoon=TimeRange("15:00", "18:30"),
    default_person="Lorenzo Sansavini",
)

CARPEEVOLUTION_STORE = ActivityRules(
    activity_id=ActivityId.SHOP,
    name="CarpeEvolution Store",
    activity_type="negozio di articoli da pesca",
    open_days=("Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato"),
    closed_days=("Domenica", "Lunedì"),
    morning=TimeRange("09:00", "12:30"),
    afternoon=TimeRange("15:30", "19:30"),
    default_person="Angelo Antonelli",
    notes="Il negozio si trova a circa 400 metri dal lago.",
)

ACTIVITIES = {
    ActivityId.LAKE: TENUTA_DEL_GERMANO,
    ActivityId.SHOP: CARPEEVOLUTION_STORE,
}
