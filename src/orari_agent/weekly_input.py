"""Parser degli input settimanali in linguaggio naturale e file strutturati.

Il parser testuale non è un motore NLP completo: riconosce intenzioni ricorrenti
e le trasforma in vincoli strutturati. Il parser strutturato accetta un piccolo
sottoinsieme YAML/JSON pensato per compilare ogni settimana un file guidato.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

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
    "gianmarco": GIAMMARCO.full_name,
    "io": GIAMMARCO.full_name,
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
class TimeRangeUnavailability:
    """Indisponibilità personale su una fascia oraria precisa."""

    day: str
    person: str
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
    """Vincoli e note ricavati dal testo/file inserito dall'utente."""

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
    unavailable_ranges_by_person: dict[str, list[TimeRangeUnavailability]] = field(
        default_factory=dict
    )
    forced_shop_coverage: list[CoverageRequest] = field(default_factory=list)
    forced_lake_coverage: list[CoverageRequest] = field(default_factory=list)
    lake_opening_coverage: list[CoverageRequest] = field(default_factory=list)
    lake_closing_coverage: list[CoverageRequest] = field(default_factory=list)
    extra_lake_coverage_days: set[str] = field(default_factory=set)
    extra_lake_coverage: list[CoverageRequest] = field(default_factory=list)
    exceptional_closures: list[ClosureRequest] = field(default_factory=list)
    exceptional_openings: list[OpeningRequest] = field(default_factory=list)
    day_notes: dict[str, list[str]] = field(default_factory=dict)
    weekly_notes: list[str] = field(default_factory=list)
    lorenzo_overtime_authorized: bool = False
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

        return [
            request for request in self.giammarco_external_work if request.day == day
        ]

    def person_is_absent_for_range(
        self, person: str, day: str, start: str, end: str
    ) -> bool:
        """Indica se una persona è assente per una parte della fascia richiesta."""

        if day in self.unavailable_days_for(person):
            return True
        start_minutes = _to_minutes(start)
        end_minutes = _to_minutes(end)
        for absence in self.unavailable_ranges_by_person.get(person, []):
            if absence.day != day:
                continue
            if (
                start_minutes < _to_minutes(absence.end)
                and _to_minutes(absence.start) < end_minutes
            ):
                return True
        if day in self.morning_absence_days_for(person) and start_minutes < _to_minutes(
            "14:00"
        ):
            return True
        return day in self.afternoon_absence_days_for(
            person
        ) and end_minutes > _to_minutes("14:00")

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


@dataclass(frozen=True)
class StructuredWeeklyPlanning:
    """Risultato della lettura di un file settimanale YAML/JSON."""

    instruction: WeeklyInstruction
    week_start: str | None = None


def load_structured_weekly_planning(path: str | Path) -> StructuredWeeklyPlanning:
    """Legge un file settimanale YAML/JSON e restituisce vincoli strutturati."""

    source = Path(path)
    text = source.read_text(encoding="utf-8")
    data = _load_structured_data(text, source.suffix.lower())
    if not isinstance(data, dict):
        raise ValueError(
            "Il file di pianificazione deve contenere un oggetto YAML/JSON alla radice."
        )
    return parse_structured_weekly_planning(data)


def parse_structured_weekly_planning(data: dict[str, Any]) -> StructuredWeeklyPlanning:
    """Converte un dizionario YAML/JSON nei vincoli usati dal generatore."""

    instruction = WeeklyInstruction(raw_text="input settimanale strutturato")
    week_start = _optional_string(data.get("week_start"))

    _read_absences(instruction, data.get("absences"))
    _read_giammarco(instruction, data.get("giammarco"))
    _read_activity_section(instruction, ActivityId.LAKE, data.get("lake"))
    _read_activity_section(instruction, ActivityId.SHOP, data.get("shop"))
    _read_manual_coverage(
        instruction, data.get("manual_coverage"), default_activity=None
    )

    for note in _as_list(data.get("notes")):
        instruction.weekly_notes.append(str(note))

    supported = {
        "week_start",
        "absences",
        "giammarco",
        "lake",
        "shop",
        "manual_coverage",
        "notes",
    }
    for key in data:
        if key not in supported:
            instruction.unknown_notes.append(f"Sezione non supportata nel file: {key}")

    return StructuredWeeklyPlanning(instruction=instruction, week_start=week_start)


def parse_weekly_instruction(text: str | None) -> WeeklyInstruction:
    """Estrae le istruzioni supportate da un testo libero italiano/inglese."""

    instruction = WeeklyInstruction(raw_text=text or "")
    if not text:
        return instruction

    sentences = [
        part.strip() for part in text.replace("\n", ". ").split(".") if part.strip()
    ]
    for sentence in sentences:
        lowered = _normalize_free_text(sentence)
        days = _days_in_text(lowered)
        people = _people_in_text(lowered)
        period = _period_in_text(lowered)

        if LORENZO.full_name in people and _mentions_overtime(lowered):
            instruction.lorenzo_overtime_authorized = True
            note = "Straordinario Lorenzo autorizzato"
            if note not in instruction.weekly_notes:
                instruction.weekly_notes.append(note)
            if not days:
                continue

        if GIAMMARCO.full_name in people and _mentions_shop(lowered) and not days:
            requested_count = _requested_day_count(lowered)
            if requested_count is not None:
                instruction.giammarco_requested_shop_day_count = requested_count
                continue

        explicit_work_range = _time_range_in_text(lowered)
        if people and days and _mentions_evening_lake_coverage_context(lowered):
            for person in people:
                for day in days:
                    request = CoverageRequest(
                        day,
                        person,
                        ActivityId.LAKE,
                        "18:30",
                        "23:00",
                        "evento serale lago",
                    )
                    instruction.forced_lake_coverage.append(request)
                    if person == GIAMMARCO.full_name:
                        instruction.giammarco_lake_days.add(day)
            continue

        if days and _mentions_lake_evening_event(lowered):
            instruction.high_lake_booking_days.update(days)
            for day in days:
                _add_day_note(
                    instruction,
                    day,
                    "Evento serale lago: apertura fino alle 23:00",
                )
            continue

        if (
            people
            and explicit_work_range is not None
            and (_mentions_work_request(lowered) or _mentions_lake(lowered))
        ):
            activity = ActivityId.SHOP if _mentions_shop(lowered) else ActivityId.LAKE
            target = (
                instruction.forced_shop_coverage
                if activity == ActivityId.SHOP
                else instruction.forced_lake_coverage
            )
            for person in people:
                for day in days:
                    target.append(
                        CoverageRequest(
                            day,
                            person,
                            activity,
                            explicit_work_range[0],
                            explicit_work_range[1],
                            "turno indicato dall'utente",
                        )
                    )
                    if person == GIAMMARCO.full_name:
                        (
                            instruction.giammarco_shop_days
                            if activity == ActivityId.SHOP
                            else instruction.giammarco_lake_days
                        ).add(day)
            continue

        if not days:
            instruction.unknown_notes.append(sentence)
            continue

        if _mentions_only_morning_opening(lowered) and (
            _mentions_lake(lowered) or _mentions_shop(lowered)
        ):
            _add_exceptional_closure(instruction, days, lowered, AFTERNOON)
            continue

        if _mentions_closure(lowered) and (
            _mentions_lake(lowered) or _mentions_shop(lowered)
        ):
            _add_exceptional_closure(instruction, days, lowered, period)
            continue

        if _mentions_exceptional_opening(lowered) and (
            _mentions_lake(lowered) or _mentions_shop(lowered)
        ):
            _add_exceptional_opening(instruction, days, lowered, period)
            continue

        if people and _mentions_unavailability(lowered):
            for person in people:
                _add_absence(instruction, person, days, period, lowered)
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
                    request = CoverageRequest(
                        day, person, ActivityId.LAKE, "07:30", "14:00", "apertura lago"
                    )
                    instruction.lake_opening_coverage.append(request)
                    instruction.forced_lake_coverage.append(request)
                    if person == LORENZO.full_name:
                        instruction.lorenzo_must_open_lake_days.add(day)
                    if person == GIAMMARCO.full_name:
                        instruction.giammarco_lake_days.add(day)
            continue

        if people and _mentions_shop(lowered) and _mentions_opening(lowered):
            for person in people:
                for day in days:
                    request = CoverageRequest(
                        day,
                        person,
                        ActivityId.SHOP,
                        "09:00",
                        "12:30",
                        "apertura negozio",
                    )
                    instruction.forced_shop_coverage.append(request)
                    if person == GIAMMARCO.full_name:
                        instruction.giammarco_shop_days.add(day)
            continue

        if people and _mentions_lake(lowered) and _mentions_closing(lowered):
            for person in people:
                for day in days:
                    request = CoverageRequest(
                        day, person, ActivityId.LAKE, "14:00", "18:30", "chiusura lago"
                    )
                    instruction.lake_closing_coverage.append(request)
                    instruction.forced_lake_coverage.append(request)
                    if person == GIAMMARCO.full_name:
                        instruction.giammarco_lake_days.add(day)
            continue

        if people and _mentions_shop(lowered) and _mentions_closing(lowered):
            for person in people:
                for day in days:
                    request = CoverageRequest(
                        day,
                        person,
                        ActivityId.SHOP,
                        "15:30",
                        "19:30",
                        "chiusura negozio",
                    )
                    instruction.forced_shop_coverage.append(request)
                    if person == GIAMMARCO.full_name:
                        instruction.giammarco_shop_days.add(day)
            continue

        if people and _mentions_leaves_at(lowered):
            for person in people:
                _add_absence(instruction, person, days, AFTERNOON, lowered)
            continue

        if people and _mentions_shop(lowered):
            for person in people:
                for day in days:
                    for start, end in _shop_ranges_for_period(period):
                        instruction.forced_shop_coverage.append(
                            CoverageRequest(
                                day,
                                person,
                                ActivityId.SHOP,
                                start,
                                end,
                                "copertura negozio",
                            )
                        )
                    if person == GIAMMARCO.full_name:
                        instruction.giammarco_shop_days.add(day)
            continue

        if people and _mentions_lake(lowered):
            for person in people:
                for day in days:
                    for start, end in _lake_ranges_for_period(period):
                        instruction.forced_lake_coverage.append(
                            CoverageRequest(
                                day,
                                person,
                                ActivityId.LAKE,
                                start,
                                end,
                                "copertura lago",
                            )
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
                        CoverageRequest(
                            day,
                            GIAMMARCO.full_name,
                            ActivityId.LAKE,
                            start,
                            end,
                            "copertura extra lago",
                        )
                    )
            continue

        if _mentions_high_lake_bookings(lowered):
            instruction.high_lake_booking_days.update(days)
            continue

        if LORENZO.full_name in people and _mentions_work_request(lowered):
            instruction.lorenzo_must_open_lake_days.update(days)
            for day in days:
                _add_day_note(
                    instruction,
                    day,
                    "Lorenzo deve lavorare per istruzione settimanale",
                )
            continue

        instruction.unknown_notes.append(sentence)

    return instruction


def _load_structured_data(text: str, suffix: str) -> Any:
    if suffix == ".json":
        return json.loads(text)
    return _parse_simple_yaml(text)


def _normalize_free_text(text: str) -> str:
    return text.lower().replace("’", "'").replace("`", "'")


def _read_absences(instruction: WeeklyInstruction, absences: Any) -> None:
    if absences is None:
        return
    if not isinstance(absences, dict):
        raise ValueError(
            "La sezione 'absences' deve essere una mappa persona -> elenco assenze."
        )
    for person_name, entries in absences.items():
        person = _person_from_value(str(person_name))
        for entry in _as_list(entries):
            item = _require_mapping(entry, "assenza")
            day = _day_from_value(item.get("day"))
            period = _period_from_value(item.get("period", FULL_DAY))
            _add_absence(instruction, person, {day}, period)
            reason = _optional_string(item.get("reason"))
            if reason:
                _add_day_note(
                    instruction,
                    day,
                    f"{person} assente ({_period_label(period)}): {reason}",
                )


def _read_giammarco(instruction: WeeklyInstruction, giammarco: Any) -> None:
    if giammarco is None:
        return
    section = _require_mapping(giammarco, "giammarco")
    for day_value in _as_list(section.get("preferred_shop_days")):
        day = _day_from_value(day_value)
        instruction.giammarco_shop_days.add(day)
        for start, end in _shop_ranges_for_period(FULL_DAY):
            instruction.forced_shop_coverage.append(
                CoverageRequest(
                    day,
                    GIAMMARCO.full_name,
                    ActivityId.SHOP,
                    start,
                    end,
                    "preferenza negozio",
                )
            )
        _add_day_note(
            instruction, day, "Giammarco preferito in negozio da file settimanale"
        )

    for entry in _as_list(section.get("company_work")):
        item = _require_mapping(entry, "lavoro aziendale Giammarco")
        day = _day_from_value(item.get("day"))
        period = _period_from_value(item.get("period", FULL_DAY))
        reason = _optional_string(item.get("reason")) or "lavoro aziendale esterno"
        start, end = _external_work_range_for_period(period)
        instruction.giammarco_external_work.append(
            ExternalWorkRequest(day, start, end, reason)
        )

    supported = {"preferred_shop_days", "company_work"}
    for key in section:
        if key not in supported:
            instruction.unknown_notes.append(f"Campo giammarco non supportato: {key}")


def _read_activity_section(
    instruction: WeeklyInstruction, activity: ActivityId, raw_section: Any
) -> None:
    if raw_section is None:
        return
    section = _require_mapping(raw_section, activity.value)
    for entry in _as_list(section.get("events")):
        item = _require_mapping(entry, "evento")
        day = _day_from_value(item.get("day"))
        period = _period_from_value(item.get("period", FULL_DAY))
        description = (
            _optional_string(item.get("description"))
            or _optional_string(item.get("reason"))
            or "evento"
        )
        if activity == ActivityId.LAKE:
            instruction.high_lake_booking_days.add(day)
        _add_day_note(
            instruction,
            day,
            f"{_activity_label(activity)} {_period_label(period)}: {description}",
        )

    if activity == ActivityId.LAKE:
        for entry in _as_list(section.get("extra_coverage")):
            item = _require_mapping(entry, "copertura extra lago")
            day = _day_from_value(item.get("day"))
            period = _period_from_value(item.get("period", FULL_DAY))
            reason = _optional_string(item.get("reason")) or "copertura extra lago"
            instruction.extra_lake_coverage_days.add(day)
            instruction.high_lake_booking_days.add(day)
            for start, end in _lake_ranges_for_period(period):
                instruction.extra_lake_coverage.append(
                    CoverageRequest(
                        day, GIAMMARCO.full_name, ActivityId.LAKE, start, end, reason
                    )
                )
            _add_day_note(
                instruction,
                day,
                f"Copertura extra lago ({_period_label(period)}): {reason}",
            )

    for entry in _as_list(section.get("special_needs")):
        item = _require_mapping(entry, "necessità speciale")
        day = _day_from_value(item.get("day"))
        period = _period_from_value(item.get("period", FULL_DAY))
        reason = _optional_string(item.get("reason")) or "necessità speciale"
        _add_day_note(
            instruction,
            day,
            f"{_activity_label(activity)} {_period_label(period)}: {reason}",
        )

    for entry in _as_list(section.get("exceptional_openings")):
        item = _require_mapping(entry, "apertura straordinaria")
        day = _day_from_value(item.get("day"))
        period = _period_from_value(item.get("period", FULL_DAY))
        reason = _optional_string(item.get("reason"))
        instruction.exceptional_openings.append(OpeningRequest(day, activity, period))
        _add_day_note(
            instruction,
            day,
            f"Apertura straordinaria {_activity_label(activity).lower()} ({_period_label(period)})"
            + (f": {reason}" if reason else ""),
        )

    for entry in _as_list(section.get("exceptional_closures")):
        item = _require_mapping(entry, "chiusura eccezionale")
        day = _day_from_value(item.get("day"))
        period = _period_from_value(item.get("period", FULL_DAY))
        reason = _optional_string(item.get("reason"))
        instruction.exceptional_closures.append(ClosureRequest(day, activity, period))
        _add_day_note(
            instruction,
            day,
            f"Chiusura eccezionale {_activity_label(activity).lower()} ({_period_label(period)})"
            + (f": {reason}" if reason else ""),
        )

    _read_manual_coverage(
        instruction, section.get("manual_coverage"), default_activity=activity
    )

    supported = {
        "events",
        "extra_coverage",
        "special_needs",
        "exceptional_openings",
        "exceptional_closures",
        "manual_coverage",
    }
    for key in section:
        if key not in supported:
            instruction.unknown_notes.append(
                f"Campo {activity.value} non supportato: {key}"
            )


def _read_manual_coverage(
    instruction: WeeklyInstruction, entries: Any, *, default_activity: ActivityId | None
) -> None:
    for entry in _as_list(entries):
        item = _require_mapping(entry, "copertura manuale")
        activity = default_activity or _activity_from_value(item.get("activity"))
        person = _person_from_value(str(item.get("person", "")))
        day = _day_from_value(item.get("day"))
        period = _period_from_value(item.get("period", FULL_DAY))
        label = (
            _optional_string(item.get("reason"))
            or _optional_string(item.get("label"))
            or "copertura manuale"
        )
        ranges = (
            _lake_ranges_for_period(period)
            if activity == ActivityId.LAKE
            else _shop_ranges_for_period(period)
        )
        target = (
            instruction.forced_lake_coverage
            if activity == ActivityId.LAKE
            else instruction.forced_shop_coverage
        )
        for start, end in ranges:
            target.append(CoverageRequest(day, person, activity, start, end, label))
        if person == GIAMMARCO.full_name:
            (
                instruction.giammarco_lake_days
                if activity == ActivityId.LAKE
                else instruction.giammarco_shop_days
            ).add(day)


def _parse_simple_yaml(text: str) -> Any:
    lines: list[tuple[int, str]] = []
    for raw_line in text.splitlines():
        without_comment = raw_line.split("#", 1)[0].rstrip()
        if not without_comment.strip():
            continue
        lines.append(
            (
                len(without_comment) - len(without_comment.lstrip(" ")),
                without_comment.strip(),
            )
        )
    if not lines:
        return {}

    def parse_block(index: int, indent: int) -> tuple[Any, int]:
        if index >= len(lines) or lines[index][0] < indent:
            return {}, index
        if lines[index][1].startswith("- "):
            return parse_list(index, indent)
        return parse_map(index, indent)

    def parse_map(index: int, indent: int) -> tuple[dict[str, Any], int]:
        result: dict[str, Any] = {}
        while index < len(lines):
            current_indent, content = lines[index]
            if current_indent < indent or content.startswith("- "):
                break
            if current_indent > indent:
                raise ValueError(f"Indentazione YAML inattesa: {content}")
            if ":" not in content:
                raise ValueError(f"Riga YAML non valida: {content}")
            key, value = content.split(":", 1)
            key = key.strip()
            value = value.strip()
            index += 1
            if value:
                result[key] = _parse_scalar(value)
            else:
                if index < len(lines) and lines[index][0] > current_indent:
                    result[key], index = parse_block(index, lines[index][0])
                else:
                    result[key] = None
        return result, index

    def parse_list(index: int, indent: int) -> tuple[list[Any], int]:
        result: list[Any] = []
        while index < len(lines):
            current_indent, content = lines[index]
            if current_indent < indent:
                break
            if current_indent != indent or not content.startswith("- "):
                break
            item_text = content[2:].strip()
            index += 1
            if not item_text:
                item, index = (
                    parse_block(index, lines[index][0])
                    if index < len(lines) and lines[index][0] > current_indent
                    else ({}, index)
                )
            elif ":" in item_text and not item_text.startswith(('"', "'")):
                key, value = item_text.split(":", 1)
                item = {
                    key.strip(): _parse_scalar(value.strip()) if value.strip() else None
                }
                if index < len(lines) and lines[index][0] > current_indent:
                    extra, index = parse_map(index, lines[index][0])
                    item.update(extra)
            else:
                item = _parse_scalar(item_text)
            result.append(item)
        return result, index

    parsed, final_index = parse_block(0, lines[0][0])
    if final_index != len(lines):
        raise ValueError("Il file YAML contiene righe non interpretabili.")
    return parsed


def _parse_scalar(value: str) -> Any:
    if value in {"null", "None", "~"}:
        return None
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    return value


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"La voce '{label}' deve essere una mappa YAML/JSON.")
    return value


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _day_from_value(value: Any) -> str:
    text = _optional_string(value)
    if not text:
        raise ValueError("Ogni voce settimanale deve indicare il campo 'day'.")
    lowered = text.lower()
    if lowered in DAY_ALIASES:
        return DAY_ALIASES[lowered]
    raise ValueError(f"Giorno non riconosciuto: {text}")


def _person_from_value(value: str) -> str:
    lowered = value.lower().strip()
    for person in (ANGELO.full_name, GIAMMARCO.full_name, LORENZO.full_name):
        if lowered == person.lower():
            return person
    if lowered in PEOPLE_ALIASES:
        return PEOPLE_ALIASES[lowered]
    raise ValueError(f"Persona non riconosciuta: {value}")


def _activity_from_value(value: Any) -> ActivityId:
    text = (_optional_string(value) or "").lower()
    if text in {"lake", "lago", "tenuta"}:
        return ActivityId.LAKE
    if text in {"shop", "negozio", "store"}:
        return ActivityId.SHOP
    raise ValueError(f"Attività non riconosciuta: {value}")


def _period_from_value(value: Any) -> str:
    text = (_optional_string(value) or FULL_DAY).lower()
    aliases = {
        "full_day": FULL_DAY,
        "full day": FULL_DAY,
        "giornata": FULL_DAY,
        "tutto il giorno": FULL_DAY,
        "intera giornata": FULL_DAY,
        "morning": MORNING,
        "mattina": MORNING,
        "afternoon": AFTERNOON,
        "pomeriggio": AFTERNOON,
    }
    if text in aliases:
        return aliases[text]
    raise ValueError(f"Periodo non riconosciuto: {value}")


def _external_work_range_for_period(period: str) -> tuple[str, str]:
    if period == MORNING:
        return "07:30", "14:00"
    if period == AFTERNOON:
        return "14:00", "19:30"
    return "07:30", "19:30"


def _add_day_note(instruction: WeeklyInstruction, day: str, note: str) -> None:
    instruction.day_notes.setdefault(day, []).append(note)


def _period_label(period: str) -> str:
    return {FULL_DAY: "giornata intera", MORNING: "mattina", AFTERNOON: "pomeriggio"}[
        period
    ]


def _activity_label(activity: ActivityId) -> str:
    return "Lago" if activity == ActivityId.LAKE else "Negozio"


def _days_in_text(lowered_text: str) -> set[str]:
    explicit_days = [day for alias, day in DAY_ALIASES.items() if alias in lowered_text]
    days = set(explicit_days)
    if len(explicit_days) >= 2 and any(
        marker in lowered_text
        for marker in (" da ", " a ", " fino a", " through ", " to ")
    ):
        indexes = sorted(WEEK_DAYS.index(day) for day in days)
        if len(indexes) >= 2:
            start, end = indexes[0], indexes[-1]
            days.update(WEEK_DAYS[start : end + 1])
    return days


def _people_in_text(lowered_text: str) -> set[str]:
    people = {
        person
        for alias, person in PEOPLE_ALIASES.items()
        if (alias == "io" and f" {alias} " in f" {lowered_text} ")
        or (alias != "io" and alias in lowered_text)
    }
    return people


def _period_in_text(lowered_text: str) -> str:
    if any(word in lowered_text for word in ("solo mattina", "mattina", "morning")):
        return MORNING
    if any(
        word in lowered_text for word in ("solo pomeriggio", "pomeriggio", "afternoon")
    ):
        return AFTERNOON
    return FULL_DAY


def _add_absence(
    instruction: WeeklyInstruction,
    person: str,
    days: set[str],
    period: str,
    lowered_text: str = "",
) -> None:
    explicit_range = _time_range_in_text(lowered_text)
    if explicit_range is not None:
        start, end = explicit_range
        for day in days:
            instruction.unavailable_ranges_by_person.setdefault(person, []).append(
                TimeRangeUnavailability(day, person, start, end, "indisponibilità")
            )
        return
    leave_time = _leave_time_in_text(lowered_text)
    if leave_time is not None:
        for day in days:
            instruction.unavailable_ranges_by_person.setdefault(person, []).append(
                TimeRangeUnavailability(
                    day, person, leave_time, "23:59", "uscita anticipata"
                )
            )
        return
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
            instruction.exceptional_closures.append(
                ClosureRequest(day, activity, period)
            )


def _add_exceptional_opening(
    instruction: WeeklyInstruction, days: set[str], lowered: str, period: str
) -> None:
    activities = _activities_in_text(lowered)
    for activity in activities:
        for day in days:
            instruction.exceptional_openings.append(
                OpeningRequest(day, activity, period)
            )


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


def _mentions_overtime(lowered_text: str) -> bool:
    overtime_words = (
        "straordinario",
        "superare le 40",
        "superare 40",
        "piu di 40",
        "più di 40",
        "12 ore",
        "11 ore",
        "10 ore",
        "di fila",
    )
    return any(word in lowered_text for word in overtime_words)


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
    explicit_range = _time_range_in_text(lowered_text)
    if explicit_range is not None:
        return explicit_range[0], explicit_range[1], _external_work_label(lowered_text)
    appointment_time = _appointment_time_in_text(lowered_text)
    if appointment_time is not None:
        start = appointment_time
        end = _add_hours(start, 2)
        return start, end, _external_work_label(lowered_text)
    if any(word in lowered_text for word in ("mattina", "morning")):
        return "07:30", "14:00", _external_work_label(lowered_text)
    if any(word in lowered_text for word in ("pomeriggio", "afternoon")):
        return "14:00", "19:30", _external_work_label(lowered_text)
    return "07:30", "19:30", _external_work_label(lowered_text)


def _time_range_in_text(lowered_text: str) -> tuple[str, str] | None:
    match = re.search(
        r"\b(?:dalle|da)\s+(\d{1,2})(?::(\d{2}))?\s+(?:alle|a)\s+(\d{1,2})(?::(\d{2}))?\b",
        lowered_text,
    )
    if not match:
        match = re.search(
            r"\b(\d{1,2})(?::(\d{2}))?\s*[-/]\s*(\d{1,2})(?::(\d{2}))?\b",
            lowered_text,
        )
    if not match:
        return None
    return _format_time(match.group(1), match.group(2)), _format_time(
        match.group(3), match.group(4)
    )


def _appointment_time_in_text(lowered_text: str) -> str | None:
    match = re.search(r"\balle\s+(\d{1,2})(?::(\d{2}))?\b", lowered_text)
    if not match:
        return None
    return _format_time(match.group(1), match.group(2))


def _leave_time_in_text(lowered_text: str) -> str | None:
    if not _mentions_leaves_at(lowered_text):
        return None
    return _appointment_time_in_text(lowered_text)


def _format_time(hour: str, minute: str | None) -> str:
    return f"{int(hour):02d}:{int(minute or '00'):02d}"


def _add_hours(start: str, hours: int) -> str:
    minutes = _to_minutes(start) + hours * 60
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _external_work_label(lowered_text: str) -> str:
    if "banca" in lowered_text or "bank" in lowered_text:
        return "banca"
    if "commercialista" in lowered_text or "accountant" in lowered_text:
        return "commercialista"
    if any(
        word in lowered_text
        for word in ("fornitore", "fornitori", "supplier", "suppliers")
    ):
        return "fornitori"
    if "admin" in lowered_text or "amministrazione" in lowered_text:
        return "amministrazione"
    if any(
        word in lowered_text
        for word in ("commissione", "commissioni", "errand", "errands")
    ):
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
        "non ci sono",
        "non ci sei",
        "non ci sara",
        "non ci sarà",
        "unavailable",
        "absent",
        "holiday",
        "vacation",
        "day off",
    )
    return any(word in lowered_text for word in unavailable_words)


def _mentions_leaves_at(lowered_text: str) -> bool:
    return any(
        text in lowered_text
        for text in (
            "deve uscire",
            "esce",
            "uscire alle",
            "va via",
            "deve andare via",
        )
    )


def _mentions_high_lake_bookings(lowered_text: str) -> bool:
    booking_words = (
        "prenotazioni",
        "bookings",
        "pieno",
        "piena",
        "molte",
        "many",
        "evento",
        "event",
    )
    return any(word in lowered_text for word in booking_words) and _mentions_lake(
        lowered_text
    )


def _mentions_lake_evening_event(lowered_text: str) -> bool:
    evening_words = (
        "sera",
        "serale",
        "aperitivo",
        "aperitivi",
        "cena",
        "cene",
        "fino alle 23",
        "fino a 23",
        "23:00",
    )
    return _mentions_lake(lowered_text) and any(
        word in lowered_text for word in evening_words
    )


def _mentions_evening_lake_coverage_context(lowered_text: str) -> bool:
    if _mentions_lake_evening_event(lowered_text):
        return True
    if _mentions_shop(lowered_text) or _mentions_external_work(lowered_text):
        return False
    return any(
        word in lowered_text
        for word in ("sera", "serale", "fino alle 23", "fino a 23", "23:00")
    )


def _mentions_extra_lake_coverage(lowered_text: str) -> bool:
    extra_words = (
        "doppio presidio",
        "doppia copertura",
        "più copertura",
        "piu copertura",
        "extra",
    )
    return any(word in lowered_text for word in extra_words) and _mentions_lake(
        lowered_text
    )


def _mentions_work_request(lowered_text: str) -> bool:
    return any(
        text in lowered_text
        for text in ("deve lavorare", "deve essere al lavoro", "lavora")
    )


def _mentions_closure(lowered_text: str) -> bool:
    closure_words = (
        "resta chiuso",
        "resta chiusa",
        "chiuso",
        "chiusa",
        "non apre",
        "closed",
    )
    return any(word in lowered_text for word in closure_words)


def _mentions_only_morning_opening(lowered_text: str) -> bool:
    return any(
        text in lowered_text
        for text in (
            "apre solo la mattina",
            "aperto solo la mattina",
            "aperta solo la mattina",
        )
    )


def _mentions_exceptional_opening(lowered_text: str) -> bool:
    opening_words = (
        "apertura straordinaria",
        "apre straordinariamente",
        "aperto straordinariamente",
        "aperta straordinariamente",
    )
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
