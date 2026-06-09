"""Parser semplice per istruzioni settimanali in linguaggio naturale.

Non è un motore NLP completo: riconosce intenzioni ricorrenti e le trasforma in
vincoli strutturati. In futuro questo modulo potrà essere sostituito da un LLM
senza cambiare generator, validator o formatter.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .people import ANGELO, GIANMARCO, LORENZO


DAY_ALIASES = {
    "lunedi": "Lunedì",
    "lunedì": "Lunedì",
    "monday": "Lunedì",
    "martedi": "Martedì",
    "martedì": "Martedì",
    "tuesday": "Martedì",
    "mercoledi": "Mercoledì",
    "mercoledì": "Mercoledì",
    "wednesday": "Mercoledì",
    "giovedi": "Giovedì",
    "giovedì": "Giovedì",
    "thursday": "Giovedì",
    "venerdi": "Venerdì",
    "venerdì": "Venerdì",
    "friday": "Venerdì",
    "sabato": "Sabato",
    "saturday": "Sabato",
    "domenica": "Domenica",
    "sunday": "Domenica",
}

PEOPLE_ALIASES = {
    "angelo": ANGELO.full_name,
    "antonelli": ANGELO.full_name,
    "gianmarco": GIANMARCO.full_name,
    "mengozzi": GIANMARCO.full_name,
    "lorenzo": LORENZO.full_name,
    "sansavini": LORENZO.full_name,
}


@dataclass
class WeeklyInstruction:
    """Vincoli e note ricavati dal testo inserito dall'utente."""

    raw_text: str = ""
    lorenzo_must_open_lake_days: set[str] = field(default_factory=set)
    gianmarco_shop_days: set[str] = field(default_factory=set)
    gianmarco_lake_days: set[str] = field(default_factory=set)
    high_lake_booking_days: set[str] = field(default_factory=set)
    unavailable_by_person: dict[str, set[str]] = field(default_factory=dict)
    unknown_notes: list[str] = field(default_factory=list)

    def unavailable_days_for(self, person: str) -> set[str]:
        """Restituisce i giorni in cui una persona non è disponibile."""

        return self.unavailable_by_person.get(person, set())


    # Compatibilità con test e chiamanti esistenti che accedevano a campi dedicati.
    @property
    def lorenzo_absent_days(self) -> set[str]:
        return self.unavailable_days_for(LORENZO.full_name)

    @property
    def angelo_absent_days(self) -> set[str]:
        return self.unavailable_days_for(ANGELO.full_name)

    @property
    def gianmarco_absent_days(self) -> set[str]:
        return self.unavailable_days_for(GIANMARCO.full_name)


def parse_weekly_instruction(text: str | None) -> WeeklyInstruction:
    """Estrae le istruzioni supportate da un testo libero italiano/inglese."""

    instruction = WeeklyInstruction(raw_text=text or "")
    if not text:
        return instruction

    sentences = [part.strip() for part in text.replace("\n", ". ").split(".") if part.strip()]
    for sentence in sentences:
        lowered = sentence.lower()
        days = _days_in_text(lowered)
        people = _people_in_text(lowered)
        if not days:
            instruction.unknown_notes.append(sentence)
            continue

        if people and _mentions_unavailability(lowered):
            for person in people:
                instruction.unavailable_by_person.setdefault(person, set()).update(days)
            continue

        if LORENZO.full_name in people and _mentions_opening_lake(lowered):
            instruction.lorenzo_must_open_lake_days.update(days)
            continue

        if GIANMARCO.full_name in people and _mentions_shop(lowered):
            instruction.gianmarco_shop_days.update(days)
            continue

        if GIANMARCO.full_name in people and _mentions_lake(lowered):
            instruction.gianmarco_lake_days.update(days)
            continue

        if _mentions_high_lake_bookings(lowered):
            instruction.high_lake_booking_days.update(days)
            continue

        instruction.unknown_notes.append(sentence)

    return instruction


def _days_in_text(lowered_text: str) -> set[str]:
    return {day for alias, day in DAY_ALIASES.items() if alias in lowered_text}


def _people_in_text(lowered_text: str) -> set[str]:
    return {person for alias, person in PEOPLE_ALIASES.items() if alias in lowered_text}


def _mentions_opening_lake(lowered_text: str) -> bool:
    opening_words = ("aprire", "apertura", "apre", "open", "opening")
    return any(word in lowered_text for word in opening_words) and _mentions_lake(lowered_text)


def _mentions_lake(lowered_text: str) -> bool:
    lake_words = ("lago", "lake", "tenuta")
    return any(word in lowered_text for word in lake_words)


def _mentions_shop(lowered_text: str) -> bool:
    shop_words = ("negozio", "shop", "store", "fatture", "invoices")
    return any(word in lowered_text for word in shop_words)


def _mentions_unavailability(lowered_text: str) -> bool:
    unavailable_words = (
        "assente",
        "assenza",
        "ferie",
        "vacanza",
        "vacanze",
        "non disponibile",
        "indisponibile",
        "unavailable",
        "absent",
        "holiday",
        "vacation",
        "day off",
    )
    return any(word in lowered_text for word in unavailable_words)


def _mentions_high_lake_bookings(lowered_text: str) -> bool:
    booking_words = ("prenotazioni", "bookings", "pieno", "molte", "many")
    return any(word in lowered_text for word in booking_words) and _mentions_lake(lowered_text)
