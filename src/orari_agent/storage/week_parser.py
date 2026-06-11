"""Utility minime per capire la settimana citata in un messaggio italiano."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from orari_agent.business_rules import WEEK_DAYS
from orari_agent.weekly_input import DAY_ALIASES, PEOPLE_ALIASES

MONTHS = {
    "gennaio": 1,
    "febbraio": 2,
    "marzo": 3,
    "aprile": 4,
    "maggio": 5,
    "giugno": 6,
    "luglio": 7,
    "agosto": 8,
    "settembre": 9,
    "ottobre": 10,
    "novembre": 11,
    "dicembre": 12,
}

_NUMBER_WORDS = {
    "zero": 0,
    "una": 1,
    "uno": 1,
    "un": 1,
    "due": 2,
    "tre": 3,
    "quattro": 4,
    "cinque": 5,
    "sei": 6,
    "sette": 7,
    "otto": 8,
    "nove": 9,
    "dieci": 10,
}

LOCATION_ALIASES = {
    "negozio": "CarpeEvolution Store",
    "store": "CarpeEvolution Store",
    "carpeevolution": "CarpeEvolution Store",
    "lago": "Tenuta del Germano",
    "tenuta": "Tenuta del Germano",
    "germano": "Tenuta del Germano",
}

CONSTRAINT_KEYWORDS = {
    "non c": "assenza",
    "assente": "assenza",
    "ferie": "assenza",
    "permesso": "assenza",
    "uscire": "assenza_oraria",
    "esce": "assenza_oraria",
    "deve": "vincolo",
    "negozio": "copertura_negozio",
    "lago": "copertura_lago",
    "prenotazioni": "carico_lago",
    "pieno": "carico_lago",
    "doppia copertura": "carico_lago",
    "fatture": "amministrazione",
    "commercialista": "impegno_esterno",
    "banca": "impegno_esterno",
    "esterna": "impegno_esterno",
}


@dataclass(frozen=True)
class ParsedNoteMetadata:
    target_week_start: date
    target_week_end: date
    interpreted_date: date | None = None
    person: str | None = None
    location: str | None = None
    constraint_type: str | None = None


def week_bounds_for(day: date) -> tuple[date, date]:
    """Restituisce lunedì e domenica della settimana di `day`."""

    start = day - timedelta(days=day.weekday())
    return start, start + timedelta(days=6)


def next_week_bounds(today: date | None = None) -> tuple[date, date]:
    """Settimana prossima rispetto a oggi."""

    base = today or date.today()
    current_start, _ = week_bounds_for(base)
    start = current_start + timedelta(days=7)
    return start, start + timedelta(days=6)


def current_or_next_week_bounds(today: date | None = None) -> tuple[date, date]:
    """Settimana corrente; da domenica in poi prepara già la prossima."""

    base = today or date.today()
    if base.weekday() >= 6:
        return next_week_bounds(base)
    return week_bounds_for(base)


def parse_week_request(
    text: str | None, today: date | None = None
) -> tuple[date, date]:
    """Interpreta richieste tipo `settimana prossima` o `dal 17 al 23 giugno`.

    La scelta è deterministica: senza una settimana esplicita torna la prossima
    settimana lunedì-domenica; `questa settimana` torna sempre la settimana
    corrente lunedì-domenica.
    """

    base = today or date.today()
    lowered = _normalize(text or "")

    explicit = _parse_explicit_range(lowered, base)
    if explicit is not None:
        return explicit

    relative = _parse_relative_week(lowered, base)
    if relative is not None:
        return relative

    single_date = _parse_single_date(lowered, base)
    if single_date is not None:
        return week_bounds_for(single_date)

    return next_week_bounds(base)


def parse_note_metadata(text: str, today: date | None = None) -> ParsedNoteMetadata:
    """Estrae metadati basilari; il testo resta comunque la fonte principale."""

    start, end = parse_week_request(text, today)
    interpreted = _interpreted_day(text, start)
    return ParsedNoteMetadata(
        target_week_start=start,
        target_week_end=end,
        interpreted_date=interpreted,
        person=_detect_person(text),
        location=_detect_location(text),
        constraint_type=_detect_constraint_type(text),
    )


def _parse_relative_week(text: str, base: date) -> tuple[date, date] | None:
    current_start, _ = week_bounds_for(base)
    if re.search(r"\bquesta\s+settimana\b", text):
        return current_start, current_start + timedelta(days=6)
    if re.search(r"\b(?:settimana\s+prossima|prossima\s+settimana)\b", text):
        start = current_start + timedelta(days=7)
        return start, start + timedelta(days=6)

    match = re.search(r"\b(?:fra|tra)\s+(\d+|[a-z]+)\s+settimane\b", text)
    if match:
        amount = _parse_integer(match.group(1))
        if amount is None:
            return None
        start = current_start + timedelta(days=7 * amount)
        return start, start + timedelta(days=6)
    return None


def _parse_integer(value: str) -> int | None:
    if value.isdigit():
        return int(value)
    return _NUMBER_WORDS.get(value)


def _parse_explicit_range(text: str, base: date) -> tuple[date, date] | None:
    match = re.search(
        r"(?:dal|da)\s+(\d{1,2})(?:\s+([a-z]+))?\s+(?:al|a)\s+(\d{1,2})\s+([a-z]+)(?:\s+(\d{4}))?",
        text,
    )
    if not match:
        return None
    start_day = int(match.group(1))
    start_month = MONTHS.get(match.group(2) or match.group(4))
    end_day = int(match.group(3))
    end_month = MONTHS.get(match.group(4))
    year = int(match.group(5) or base.year)
    if start_month is None or end_month is None:
        return None
    start = date(year, start_month, start_day)
    end = date(year, end_month, end_day)
    if end < start:
        end = date(year + 1, end_month, end_day)
    return start, end


def _parse_single_date(text: str, base: date) -> date | None:
    match = re.search(
        r"\b(?:settimana\s+del\s+)?(\d{1,2})\s+([a-z]+)(?:\s+(\d{4}))?\b", text
    )
    if not match:
        match_iso = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", text)
        if match_iso:
            return datetime.strptime(match_iso.group(0), "%Y-%m-%d").date()
        return None
    month = MONTHS.get(match.group(2))
    if month is None:
        return None
    return date(int(match.group(3) or base.year), month, int(match.group(1)))


def _interpreted_day(text: str, week_start: date) -> date | None:
    lowered = _normalize(text)
    for alias, canonical in DAY_ALIASES.items():
        if alias in lowered:
            index = WEEK_DAYS.index(canonical)
            return week_start + timedelta(days=index)
    return _parse_single_date(lowered, week_start)


def _detect_person(text: str) -> str | None:
    lowered = _normalize(text)
    for alias, person in PEOPLE_ALIASES.items():
        if alias == "io":
            continue
        if alias in lowered:
            return person
    if _has_first_person_reference(lowered):
        return PEOPLE_ALIASES["giammarco"]
    return None


def _has_first_person_reference(text: str) -> bool:
    return any(
        re.search(pattern, text)
        for pattern in (
            r"\bio\b",
            r"\bsono\b",
            r"\bsaro\b",
            r"\bsarò\b",
            r"\bdevo\b",
            r"\bvado\b",
            r"\bnon\s+ci\s+sono\b",
        )
    )


def _detect_location(text: str) -> str | None:
    lowered = _normalize(text)
    for alias, location in LOCATION_ALIASES.items():
        if alias in lowered:
            return location
    return None


def _detect_constraint_type(text: str) -> str | None:
    lowered = _normalize(text)
    for keyword, label in CONSTRAINT_KEYWORDS.items():
        if keyword in lowered:
            return label
    return None


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    return text.replace("’", "'")
