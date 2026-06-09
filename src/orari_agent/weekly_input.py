"""Parser semplice per istruzioni settimanali in linguaggio naturale.

Non è un motore NLP completo: riconosce intenzioni ricorrenti e le trasforma in
vincoli strutturati. In futuro questo modulo potrà essere sostituito da un LLM
senza cambiare generator, validator o formatter.
"""

from __future__ import annotations

from dataclasses import dataclass, field


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


@dataclass
class WeeklyInstruction:
    """Vincoli e note ricavati dal testo inserito dall'utente."""

    raw_text: str = ""
    lorenzo_must_open_lake_days: set[str] = field(default_factory=set)
    gianmarco_shop_days: set[str] = field(default_factory=set)
    high_lake_booking_days: set[str] = field(default_factory=set)
    unknown_notes: list[str] = field(default_factory=list)


def parse_weekly_instruction(text: str | None) -> WeeklyInstruction:
    """Estrae le istruzioni supportate da un testo libero italiano/inglese."""

    instruction = WeeklyInstruction(raw_text=text or "")
    if not text:
        return instruction

    sentences = [part.strip() for part in text.replace("\n", ". ").split(".") if part.strip()]
    for sentence in sentences:
        lowered = sentence.lower()
        days = _days_in_text(lowered)
        if not days:
            instruction.unknown_notes.append(sentence)
            continue

        if "lorenzo" in lowered and _mentions_opening_lake(lowered):
            instruction.lorenzo_must_open_lake_days.update(days)
            continue

        if "gianmarco" in lowered and _mentions_shop(lowered):
            instruction.gianmarco_shop_days.update(days)
            continue

        if _mentions_high_lake_bookings(lowered):
            instruction.high_lake_booking_days.update(days)
            continue

        instruction.unknown_notes.append(sentence)

    return instruction


def _days_in_text(lowered_text: str) -> set[str]:
    return {day for alias, day in DAY_ALIASES.items() if alias in lowered_text}


def _mentions_opening_lake(lowered_text: str) -> bool:
    opening_words = ("aprire", "apertura", "open", "opening")
    lake_words = ("lago", "lake", "tenuta")
    return any(word in lowered_text for word in opening_words) and any(
        word in lowered_text for word in lake_words
    )


def _mentions_shop(lowered_text: str) -> bool:
    shop_words = ("negozio", "shop", "store", "fatture", "invoices")
    return any(word in lowered_text for word in shop_words)


def _mentions_high_lake_bookings(lowered_text: str) -> bool:
    booking_words = ("prenotazioni", "bookings", "pieno", "molte", "many")
    lake_words = ("lago", "lake", "tenuta")
    return any(word in lowered_text for word in booking_words) and any(
        word in lowered_text for word in lake_words
    )
