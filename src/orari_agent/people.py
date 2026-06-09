"""Anagrafica e vincoli delle persone."""

from __future__ import annotations

from dataclasses import dataclass

from .business_rules import TimeRange


@dataclass(frozen=True)
class Person:
    """Persona disponibile per coprire negozio o lago."""

    full_name: str
    default_role: str
    strict_weekly_hours: float | None = None
    strict_working_days: int | None = None
    strict_daily_hours: float | None = None
    default_rest_day: str | None = None
    preferred_second_rest_day: str | None = None
    ideal_working_days: tuple[str, ...] = ()
    default_shift: TimeRange | None = None
    default_break: TimeRange | None = None


ANGELO = Person(
    full_name="Angelo Antonelli",
    default_role="copertura principale negozio",
)

GIAMMARCO = Person(
    full_name="Giammarco Mengozzi",
    default_role="general manager / CEO: lavoro aziendale continuo, copertura fissa solo quando serve",
)


LORENZO = Person(
    full_name="Lorenzo Sansavini",
    default_role="copertura principale lago",
    strict_weekly_hours=40.0,
    strict_working_days=5,
    strict_daily_hours=8.0,
    default_rest_day="Lunedì",
    preferred_second_rest_day="Martedì",
    ideal_working_days=("Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"),
    default_shift=TimeRange("07:30", "16:30"),
    default_break=TimeRange("14:00", "15:00"),
)

PEOPLE = {
    person.full_name: person
    for person in (ANGELO, GIAMMARCO, LORENZO)
}
