"""Parser semplice per istruzioni settimanali in linguaggio naturale.

Non è un motore NLP completo: riconosce intenzioni ricorrenti e le trasforma in
vincoli strutturati. In futuro questo modulo potrà essere sostituito da un LLM
senza cambiare generator, validator o formatter.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .business_rules import ActivityId, WEEK_DAYS
from .people import ANGELO, GIAMMARCO, LORENZO


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
    "giammarco": GIAMMARCO.full_name,
    "mengozzi": GIAMMARCO.full_name,
    "lorenzo": LORENZO.full_name,
    "sansavini": LORENZO.full_name,
}

FULL_DAY = "full_day"
MORNING = "morning"
AFTERNOON = "afternoon"


@dataclass(frozen=True)
class ExternalWorkRequest:
    """Lavoro aziendale di Giammarco non valido come copertura fissa."""

    day: str
    start: str
    end: str
    label: str


@dataclass(frozen=True)
class CoverageRequest:
    """Copertura manuale richiesta dall'utente."""

    day: str
    person: str
    activity: ActivityId
    start: str
    end: str
    label: str


@dataclass(frozen=True)
class ClosureRequest:
    """Chiusura eccezionale di una attività per giorno/fascia."""

    day: str
    activity: ActivityId
    period: str


@dataclass(frozen=True)
class OpeningRequest:
    """Apertura eccezionale di una attività normalmente chiusa."""

    day: str
    activity: ActivityId
    period: str


@dataclass
class WeeklyInstruction:
    """Vincoli e note ricavati dal testo inserito dall'utente."""

    raw_text: str = ""
    lorenzo_must_open_lake_days: set[str] = field(default_factory=set)
    giammarco_shop_days: set[str] = field(default_factory=set)
    giammarco_lake_days: set[str] = field(default_factory=set)
    giammarco_requested_shop_day_count: int | None = None
    giammarco_external_work: list[ExternalWorkRequest] = field(default_factory=list)
    high_lake_booking_days: set[str] = field(default_factory=set)
    unavailable_by_person: dict[str, set[str]] = field(default_factory=dict)
    morning_absence_by_person: dict[str, set[str]] = field(default_factory=dict)
    afternoon_absence_by_person: dict[str, set[str]] = field(default_factory=dict)
    forced_shop_coverage: list[CoverageRequest] = field(default_factory=list)
    forced_lake_coverage: list[CoverageRequest] = field(default_factory=list)
    lake_opening_coverage: list[CoverageRequest] = field(default_factory=list)
    lake_closing_coverage: list[CoverageRequest] = field(default_factory=list)
    extra_lake_coverage_days: set[str] = field(default_factory=set)
    extra_lake_coverage: list[CoverageRequest] = field(default_factory=list)
    exceptional_closures: list[ClosureRequest] = field(default_factory=list)
    exceptional_openings: list[OpeningRequest] = field(default_factory=list)
    unknown_notes: list[str] = field(default_factory=list)

    def unavailable_days_for(self, person: str) -> set[str]:
        """Restituisce i giorni in cui una persona non è disponibile tutto il giorno."""

        return self.unavailable_by_person.get(person, set())

    def morning_absence_days_for(self, person: str) -> set[str]:
        """Restituisce i giorni in cui una persona non è disponibile la mattina."""

        return self.morning_absence_by_person.get(person, set())

    def afternoon_absence_days_for(self, person: str) -> set[str]:
        """Restituisce i giorni in cui una persona non è disponibile il pomeriggio."""

        return self.afternoon_absence_by_person.get(person, set())

    def external_work_for(self, day: str) -> list[ExternalWorkRequest]:
        """Restituisce gli impegni aziendali esterni di Giammarco per il giorno."""

        return [request for request in self.giammarco_external_work if request.day == day]

    def person_is_absent_for_range(self, person: str, day: str, start: str, end: str) -> bool:
        """Indica se una persona è assente per una parte della fascia richiesta."""

        if day in self.unavailable_days_for(person):
            return True
        start_minutes = _to_minutes(start)
        end_minutes = _to_minutes(end)
        if day in self.morning_absence_days_for(person) and start_minutes < _to_minutes("14:00"):
            return True
        return day in self.afternoon_absence_days_for(person) and end_minutes > _to_minutes("14:00")

    # Compatibilità con test e chiamanti esistenti che accedevano a campi dedicati.
    @property
    def lorenzo_absent_days(self) -> set[str]:
        return self.unavailable_days_for(LORENZO.full_name)

    @property
    def angelo_absent_days(self) -> set[str]:
        return self.unavailable_days_for(ANGELO.full_name)

    @property
    def giammarco_absent_days(self) -> set[str]:
        return self.unavailable_days_for(GIAMMARCO.full_name)


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
        period = _period_in_text(lowered)

        if GIAMMARCO.full_name in people and _mentions_shop(lowered) and not days:
            requested_count = _requested_day_count(lowered)
            if requested_count is not None:
                instruction.giammarco_requested_shop_day_count = requested_count
                continue

        if not days:
            instruction.unknown_notes.append(sentence)
            continue

        if _mentions_only_morning_opening(lowered) and (_mentions_lake(lowered) or _mentions_shop(lowered)):
            _add_exceptional_closure(instruction, days, lowered, AFTERNOON)
            continue

        if _mentions_closure(lowered) and (_mentions_lake(lowered) or _mentions_shop(lowered)):
            _add_exceptional_closure(instruction, days, lowered, period)
            continue

        if _mentions_exceptional_opening(lowered) and (_mentions_lake(lowered) or _mentions_shop(lowered)):
            _add_exceptional_opening(instruction, days, lowered, period)
            continue

        if people and _mentions_unavailability(lowered):
            for person in people:
                _add_absence(instruction, person, days, period)
            continue

        if GIAMMARCO.full_name in people and _mentions_external_work(lowered):
            for day in days:
                instruction.giammarco_external_work.append(
                    ExternalWorkRequest(day, *_external_work_range_and_label(lowered))
                )
            continue

        if people and _mentions_lake(lowered) and _mentions_opening(lowered):
            for person in people:
                for day in days:
                    request = CoverageRequest(day, person, ActivityId.LAKE, "07:30", "14:00", "apertura lago")
                    instruction.lake_opening_coverage.append(request)
                    instruction.forced_lake_coverage.append(request)
                    if person == LORENZO.full_name:
                        instruction.lorenzo_must_open_lake_days.add(day)
                    if person == GIAMMARCO.full_name:
                        instruction.giammarco_lake_days.add(day)
            continue

        if people and _mentions_lake(lowered) and _mentions_closing(lowered):
            for person in people:
                for day in days:
                    request = CoverageRequest(day, person, ActivityId.LAKE, "14:00", "18:30", "chiusura lago")
                    instruction.lake_closing_coverage.append(request)
                    instruction.forced_lake_coverage.append(request)
                    if person == GIAMMARCO.full_name:
                        instruction.giammarco_lake_days.add(day)
            continue

        if people and _mentions_shop(lowered):
            for person in people:
                for day in days:
                    for start, end in _shop_ranges_for_period(period):
                        instruction.forced_shop_coverage.append(
                            CoverageRequest(day, person, ActivityId.SHOP, start, end, "copertura negozio")
                        )
                    if person == GIAMMARCO.full_name:
                        instruction.giammarco_shop_days.add(day)
            continue

        if people and _mentions_lake(lowered):
            for person in people:
                for day in days:
                    for start, end in _lake_ranges_for_period(period):
                        instruction.forced_lake_coverage.append(
                            CoverageRequest(day, person, ActivityId.LAKE, start, end, "copertura lago")
                        )
                    if person == GIAMMARCO.full_name:
                        instruction.giammarco_lake_days.add(day)
            continue

        if _mentions_extra_lake_coverage(lowered):
            instruction.extra_lake_coverage_days.update(days)
            instruction.high_lake_booking_days.update(days)
            for day in days:
                for start, end in _lake_ranges_for_period(period):
                    instruction.extra_lake_coverage.append(
                        CoverageRequest(day, GIAMMARCO.full_name, ActivityId.LAKE, start, end, "copertura extra lago")
                    )
            continue

        if _mentions_high_lake_bookings(lowered):
            instruction.high_lake_booking_days.update(days)
            continue

        instruction.unknown_notes.append(sentence)

    return instruction


def _days_in_text(lowered_text: str) -> set[str]:
    explicit_days = [day for alias, day in DAY_ALIASES.items() if alias in lowered_text]
    days = set(explicit_days)
    if len(explicit_days) >= 2 and any(marker in lowered_text for marker in (" da ", " a ", " fino a", " through ", " to ")):
        indexes = sorted(WEEK_DAYS.index(day) for day in days)
        if len(indexes) >= 2:
            start, end = indexes[0], indexes[-1]
            days.update(WEEK_DAYS[start : end + 1])
    return days


def _people_in_text(lowered_text: str) -> set[str]:
    return {person for alias, person in PEOPLE_ALIASES.items() if alias in lowered_text}


def _period_in_text(lowered_text: str) -> str:
    if any(word in lowered_text for word in ("solo mattina", "mattina", "morning")):
        return MORNING
    if any(word in lowered_text for word in ("solo pomeriggio", "pomeriggio", "afternoon")):
        return AFTERNOON
    return FULL_DAY


def _add_absence(instruction: WeeklyInstruction, person: str, days: set[str], period: str) -> None:
    if period == MORNING:
        instruction.morning_absence_by_person.setdefault(person, set()).update(days)
        return
    if period == AFTERNOON:
        instruction.afternoon_absence_by_person.setdefault(person, set()).update(days)
        return
    instruction.unavailable_by_person.setdefault(person, set()).update(days)


def _add_exceptional_closure(
    instruction: WeeklyInstruction, days: set[str], lowered: str, period: str
) -> None:
    activities = _activities_in_text(lowered)
    for activity in activities:
        for day in days:
            instruction.exceptional_closures.append(ClosureRequest(day, activity, period))


def _add_exceptional_opening(
    instruction: WeeklyInstruction, days: set[str], lowered: str, period: str
) -> None:
    activities = _activities_in_text(lowered)
    for activity in activities:
        for day in days:
            instruction.exceptional_openings.append(OpeningRequest(day, activity, period))


def _activities_in_text(lowered: str) -> set[ActivityId]:
    activities: set[ActivityId] = set()
    if _mentions_lake(lowered):
        activities.add(ActivityId.LAKE)
    if _mentions_shop(lowered):
        activities.add(ActivityId.SHOP)
    return activities


def _mentions_opening_lake(lowered_text: str) -> bool:
    return _mentions_opening(lowered_text) and _mentions_lake(lowered_text)


def _mentions_opening(lowered_text: str) -> bool:
    opening_words = ("aprire", "apertura", "apre", "open", "opening")
    return any(word in lowered_text for word in opening_words)


def _mentions_closing(lowered_text: str) -> bool:
    closing_words = ("chiusura", "chiudere", "chiude", "closing", "close")
    return any(word in lowered_text for word in closing_words)


def _mentions_lake(lowered_text: str) -> bool:
    lake_words = ("lago", "lake", "tenuta")
    return any(word in lowered_text for word in lake_words)


def _mentions_shop(lowered_text: str) -> bool:
    shop_words = ("negozio", "shop", "store", "fatture", "invoices")
    return any(word in lowered_text for word in shop_words)


def _mentions_external_work(lowered_text: str) -> bool:
    external_words = (
        "banca",
        "bank",
        "commercialista",
        "accountant",
        "fornitore",
        "fornitori",
        "supplier",
        "suppliers",
        "amministrazione",
        "admin",
        "commissione",
        "commissioni",
        "errand",
        "errands",
        "esterno",
        "esterna",
        "fuori sede",
        "fuori per",
    )
    return any(word in lowered_text for word in external_words)


def _external_work_range_and_label(lowered_text: str) -> tuple[str, str, str]:
    if any(word in lowered_text for word in ("mattina", "morning")):
        return "07:30", "14:00", _external_work_label(lowered_text)
    if any(word in lowered_text for word in ("pomeriggio", "afternoon")):
        return "14:00", "19:30", _external_work_label(lowered_text)
    return "07:30", "19:30", _external_work_label(lowered_text)


def _external_work_label(lowered_text: str) -> str:
    if "banca" in lowered_text or "bank" in lowered_text:
        return "banca"
    if "commercialista" in lowered_text or "accountant" in lowered_text:
        return "commercialista"
    if any(word in lowered_text for word in ("fornitore", "fornitori", "supplier", "suppliers")):
        return "fornitori"
    if "admin" in lowered_text or "amministrazione" in lowered_text:
        return "amministrazione"
    if any(word in lowered_text for word in ("commissione", "commissioni", "errand", "errands")):
        return "commissioni"
    return "lavoro aziendale esterno"


def _mentions_unavailability(lowered_text: str) -> bool:
    unavailable_words = (
        "assente",
        "assenza",
        "ferie",
        "vacanza",
        "vacanze",
        "non disponibile",
        "non è disponibile",
        "non e disponibile",
        "indisponibile",
        "non c'è",
        "non c'e",
        "non ce",
        "non cè",
        "unavailable",
        "absent",
        "holiday",
        "vacation",
        "day off",
    )
    return any(word in lowered_text for word in unavailable_words)


def _mentions_high_lake_bookings(lowered_text: str) -> bool:
    booking_words = ("prenotazioni", "bookings", "pieno", "piena", "molte", "many", "evento", "event")
    return any(word in lowered_text for word in booking_words) and _mentions_lake(lowered_text)


def _mentions_extra_lake_coverage(lowered_text: str) -> bool:
    extra_words = ("doppio presidio", "doppia copertura", "più copertura", "piu copertura", "extra")
    return any(word in lowered_text for word in extra_words) and _mentions_lake(lowered_text)


def _mentions_closure(lowered_text: str) -> bool:
    closure_words = ("resta chiuso", "resta chiusa", "chiuso", "chiusa", "non apre", "closed")
    return any(word in lowered_text for word in closure_words)


def _mentions_only_morning_opening(lowered_text: str) -> bool:
    return any(text in lowered_text for text in ("apre solo la mattina", "aperto solo la mattina", "aperta solo la mattina"))


def _mentions_exceptional_opening(lowered_text: str) -> bool:
    opening_words = ("apertura straordinaria", "apre straordinariamente", "aperto straordinariamente", "aperta straordinariamente")
    return any(word in lowered_text for word in opening_words)


def _requested_day_count(lowered_text: str) -> int | None:
    count_words = {
        "un giorno": 1,
        "1 giorno": 1,
        "one day": 1,
        "due giorni": 2,
        "2 giorni": 2,
        "two days": 2,
        "tre giorni": 3,
        "3 giorni": 3,
        "three days": 3,
    }
    for text, count in count_words.items():
        if text in lowered_text:
            return count
    return None


def _shop_ranges_for_period(period: str) -> list[tuple[str, str]]:
    if period == FULL_DAY:
        return [("09:00", "12:30"), ("15:30", "19:30")]
    return [_shop_range_for_period(period)]


def _shop_range_for_period(period: str) -> tuple[str, str]:
    if period == MORNING:
        return "09:00", "12:30"
    if period == AFTERNOON:
        return "15:30", "19:30"
    return "09:00", "19:30"


def _lake_ranges_for_period(period: str) -> list[tuple[str, str]]:
    if period == FULL_DAY:
        return [("07:30", "14:00"), ("14:00", "18:30")]
    return [_lake_range_for_period(period)]


def _lake_range_for_period(period: str) -> tuple[str, str]:
    if period == MORNING:
        return "07:30", "14:00"
    if period == AFTERNOON:
        return "14:00", "18:30"
    return "07:30", "18:30"


def _to_minutes(value: str) -> int:
    hours, minutes = value.split(":")
    return int(hours) * 60 + int(minutes)
