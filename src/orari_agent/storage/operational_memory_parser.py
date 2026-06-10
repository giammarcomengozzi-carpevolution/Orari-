"""Parser deterministico per la memoria operativa persistente."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date

from orari_agent.storage.week_parser import MONTHS
from orari_agent.weekly_input import AFTERNOON, FULL_DAY, MORNING, PEOPLE_ALIASES

WEEKDAY_TO_RULE = {
    "lunedi": "MONDAY",
    "lunedì": "MONDAY",
    "martedi": "TUESDAY",
    "martedì": "TUESDAY",
    "mercoledi": "WEDNESDAY",
    "mercoledì": "WEDNESDAY",
    "giovedi": "THURSDAY",
    "giovedì": "THURSDAY",
    "venerdi": "FRIDAY",
    "venerdì": "FRIDAY",
    "sabato": "SATURDAY",
    "domenica": "SUNDAY",
}

PERIOD_TO_RULE = {MORNING: "MORNING", AFTERNOON: "AFTERNOON", FULL_DAY: "FULL_DAY"}


@dataclass(frozen=True)
class ParsedOperationalMemory:
    raw_text: str
    start_date: date | None = None
    end_date: date | None = None
    recurrence_rule: str | None = None
    person: str | None = None
    location: str | None = None
    constraint_type: str = "promemoria"
    start_time: str | None = None
    end_time: str | None = None
    notes: str | None = None
    interpreted: bool = False


def parse_operational_memory(
    text: str, *, today: date | None = None
) -> ParsedOperationalMemory:
    """Interpreta i pattern italiani supportati per assenze e vincoli futuri."""

    raw_text = _strip_memory_prefix(text.strip())
    base = today or date.today()
    lowered = _normalize(raw_text)
    person = _person_in_text(lowered)
    period = _period_in_text(lowered)

    recurring = _parse_recurring(lowered, raw_text, person, period)
    if recurring is not None:
        return recurring

    external = _parse_external_work(lowered, raw_text, base)
    if external is not None:
        return external

    holiday = _parse_holiday_range(lowered, raw_text, base, person)
    if holiday is not None:
        return holiday

    single_absence = _parse_single_absence(lowered, raw_text, base, person, period)
    if single_absence is not None:
        return single_absence

    return ParsedOperationalMemory(
        raw_text=raw_text,
        person=person,
        constraint_type="promemoria_non_interpretato",
        notes="Testo preservato ma non trasformato in vincolo automatico.",
        interpreted=False,
    )


def _strip_memory_prefix(text: str) -> str:
    return re.sub(
        r"^\s*(?:ricordati\s+che|memorizza\s+che|salva\s+memoria)\s+",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()


def _parse_recurring(
    lowered: str, raw_text: str, person: str | None, period: str
) -> ParsedOperationalMemory | None:
    if "ogni" not in lowered or person is None:
        return None
    weekday_pattern = "|".join(re.escape(day) for day in WEEKDAY_TO_RULE)
    match = re.search(rf"\bogni\s+({weekday_pattern})\b", lowered)
    if not match:
        return None
    recurrence_rule = f"WEEKLY:{WEEKDAY_TO_RULE[match.group(1)]}:{PERIOD_TO_RULE[period]}"
    ctype = "impegno_esterno" if _mentions_external(lowered) else "assenza"
    location = _external_location(lowered)
    start_time, end_time = _times_for_period(period)
    return ParsedOperationalMemory(
        raw_text=raw_text,
        recurrence_rule=recurrence_rule,
        person=person,
        location=location,
        constraint_type=ctype,
        start_time=start_time,
        end_time=end_time,
        notes=_effect_note(raw_text, ctype),
        interpreted=True,
    )


def _parse_external_work(
    lowered: str, raw_text: str, base: date
) -> ParsedOperationalMemory | None:
    if not _mentions_external(lowered):
        return None
    person = _person_in_text(lowered)
    if person is None:
        return None
    day = _single_date_in_text(lowered, base)
    if day is None:
        return None
    time_range = _time_range_in_text(lowered)
    if time_range is None:
        return None
    return ParsedOperationalMemory(
        raw_text=raw_text,
        start_date=day,
        end_date=day,
        person=person,
        location=_external_location(lowered),
        constraint_type="impegno_esterno",
        start_time=time_range[0],
        end_time=time_range[1],
        notes=_effect_note(raw_text, "impegno_esterno"),
        interpreted=True,
    )


def _parse_holiday_range(
    lowered: str, raw_text: str, base: date, person: str | None
) -> ParsedOperationalMemory | None:
    if person is None or "ferie" not in lowered:
        return None
    match = re.search(
        r"\bdal\s+(\d{1,2})(?:\s+([a-zà]+))?\s+al\s+(\d{1,2})\s+([a-zà]+)(?:\s+(\d{4}))?\b",
        lowered,
    )
    if not match:
        return None
    try:
        start_month = MONTHS.get(_unaccent(match.group(2) or match.group(4)))
        end_month = MONTHS.get(_unaccent(match.group(4)))
        year = int(match.group(5) or base.year)
        if start_month is None or end_month is None:
            return None
        start = date(year, start_month, int(match.group(1)))
        end = date(year, end_month, int(match.group(3)))
        if end < start:
            end = date(year + 1, end_month, int(match.group(3)))
        if match.group(5) is None and end < base:
            start = date(start.year + 1, start.month, start.day)
            end = date(end.year + 1, end.month, end.day)
    except ValueError:
        return None
    return ParsedOperationalMemory(
        raw_text=raw_text,
        start_date=start,
        end_date=end,
        person=person,
        constraint_type="ferie/assenza",
        notes=_effect_note(raw_text, "ferie/assenza"),
        interpreted=True,
    )


def _parse_single_absence(
    lowered: str, raw_text: str, base: date, person: str | None, period: str
) -> ParsedOperationalMemory | None:
    if person is None or not _mentions_absence(lowered):
        return None
    day = _single_date_in_text(lowered, base)
    if day is None:
        return None
    start_time, end_time = _times_for_period(period)
    return ParsedOperationalMemory(
        raw_text=raw_text,
        start_date=day,
        end_date=day,
        person=person,
        constraint_type="assenza",
        start_time=start_time,
        end_time=end_time,
        notes=_effect_note(raw_text, "assenza"),
        interpreted=True,
    )


def _single_date_in_text(lowered: str, base: date) -> date | None:
    match = re.search(r"\b(\d{1,2})\s+([a-zà]+)(?:\s+(\d{4}))?\b", lowered)
    if not match:
        return None
    month = MONTHS.get(_unaccent(match.group(2)))
    if month is None:
        return None
    year = int(match.group(3) or base.year)
    try:
        parsed = date(year, month, int(match.group(1)))
    except ValueError:
        return None
    if match.group(3) is None and parsed < base:
        parsed = date(year + 1, month, parsed.day)
    return parsed


def _time_range_in_text(lowered: str) -> tuple[str, str] | None:
    match = re.search(
        r"\bdalle\s+(\d{1,2})(?::(\d{2}))?\s+alle\s+(\d{1,2})(?::(\d{2}))?\b",
        lowered,
    )
    if not match:
        return None
    return (
        _format_time(match.group(1), match.group(2)),
        _format_time(match.group(3), match.group(4)),
    )


def _format_time(hour: str, minute: str | None) -> str:
    return f"{int(hour):02d}:{int(minute or '00'):02d}"


def _person_in_text(lowered: str) -> str | None:
    for alias, person in PEOPLE_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", lowered):
            return person
    return None


def _period_in_text(lowered: str) -> str:
    if "mattina" in lowered:
        return MORNING
    if "pomeriggio" in lowered:
        return AFTERNOON
    return FULL_DAY


def _times_for_period(period: str) -> tuple[str | None, str | None]:
    if period == MORNING:
        return "07:30", "14:00"
    if period == AFTERNOON:
        return "14:00", "19:30"
    return None, None


def _mentions_absence(lowered: str) -> bool:
    return any(
        token in lowered
        for token in ("assente", "non c'e", "non c'è", "non cè", "non lavora", "ferie")
    )


def _mentions_external(lowered: str) -> bool:
    return any(
        token in lowered
        for token in (
            "commercialista",
            "banca",
            "attivita aziendale esterna",
            "attività aziendale esterna",
        )
    )


def _external_location(lowered: str) -> str | None:
    if "commercialista" in lowered:
        return "commercialista"
    if "banca" in lowered:
        return "banca"
    if "esterna" in lowered:
        return "attività aziendale esterna"
    return None


def _effect_note(raw_text: str, constraint_type: str) -> str:
    return f"Memoria: {raw_text} ({constraint_type})"


def _normalize(text: str) -> str:
    return unicodedata.normalize("NFKC", text).lower().replace("’", "'").replace("`", "'")


def _unaccent(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text.lower())
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
