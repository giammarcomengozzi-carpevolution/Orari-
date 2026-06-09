"""Modelli dati condivisi dall'agente."""

from __future__ import annotations

from dataclasses import dataclass, field

from .business_rules import ActivityId


@dataclass
class Assignment:
    """Assegnazione di una persona a una fascia di una attività."""

    person: str
    activity: ActivityId
    period: str
    start: str
    end: str
    working_hours: float
    break_label: str | None = None

    def label(self) -> str:
        break_text = f", pausa {self.break_label}" if self.break_label else ""
        return f"{self.person} ({self.start}-{self.end}{break_text})"


@dataclass
class DaySchedule:
    """Pianificazione di un singolo giorno."""

    day: str
    lake_morning: list[Assignment] = field(default_factory=list)
    lake_afternoon: list[Assignment] = field(default_factory=list)
    shop_morning: list[Assignment] = field(default_factory=list)
    shop_afternoon: list[Assignment] = field(default_factory=list)
    company_work: list[Assignment] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def assignments(self) -> list[Assignment]:
        return [
            *self.lake_morning,
            *self.lake_afternoon,
            *self.shop_morning,
            *self.shop_afternoon,
            *self.company_work,
        ]


@dataclass
class WeeklySchedule:
    """Risultato della generazione settimanale."""

    days: list[DaySchedule]
    global_warnings: list[str] = field(default_factory=list)
