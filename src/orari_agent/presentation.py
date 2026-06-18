"""Vista operativa degli orari generati per PDF e riepiloghi Telegram."""

from __future__ import annotations

from dataclasses import dataclass

from .business_rules import ActivityId, WEEK_DAYS
from .models import Assignment, DaySchedule, WeeklySchedule
from .people import ANGELO, GIAMMARCO, LORENZO

PEOPLE_IN_SUMMARY = (GIAMMARCO.full_name, ANGELO.full_name, LORENZO.full_name)
LORENZO_TARGET_HOURS = 40.0
LONG_DAY_HOURS = 8.0


@dataclass(frozen=True)
class EffectiveShift:
    """Riga operativa reale da mostrare a persone e responsabili."""

    day: str
    date: str
    person: str
    location: str
    work_time: str
    break_time: str
    task: str
    notes: str = "-"
    working_hours: float = 0.0


@dataclass(frozen=True)
class OperationalShiftRow:
    """Riga aggregata per persona/sede/giorno nella vista PDF a card."""

    person: str
    location: str
    segments: tuple[tuple[str, str], ...]
    break_time: str
    task: str
    daily_hours: float
    notes: str = "-"

    @property
    def work_time(self) -> str:
        return " / ".join(f"{start}-{end}" for start, end in self.segments)

    @property
    def timeline(self) -> str:
        bars = " / ".join(
            f"{start} {_bar_for_segment(start, end)} {end}"
            for start, end in self.segments
        )
        return f"{self.work_time} | {bars}"


@dataclass(frozen=True)
class LocationSection:
    """Sezione di una card giornaliera, per Lago o Negozio."""

    location: str
    rows: tuple[OperationalShiftRow, ...]


@dataclass(frozen=True)
class OperationalDayView:
    """Vista giornaliera operativa per il PDF calendario."""

    day: str
    date: str
    location_sections: tuple[LocationSection, ...]


def effective_shifts(schedule: WeeklySchedule) -> list[EffectiveShift]:
    """Converte blocchi interni in turni leggibili persona -> sede -> orario."""

    shifts: list[EffectiveShift] = []
    dates = _dates_by_day(schedule.week_start_date)
    for day in schedule.days:
        date_label = dates.get(day.day, "-")
        shifts.extend(_shop_shifts(day, date_label))
        shifts.extend(_lake_shifts(day, date_label))
        shifts.extend(_external_work_shifts(day, date_label))
    return sorted(
        shifts,
        key=lambda shift: (
            WEEK_DAYS.index(shift.day),
            _to_minutes(_first_start(shift.work_time)),
            shift.person,
            shift.location,
        ),
    )


def operational_day_views(schedule: WeeklySchedule) -> list[OperationalDayView]:
    """Raggruppa i turni per giorno, sede e persona per una lettura calendario."""

    dates = _dates_by_day(schedule.week_start_date)
    shifts_by_day: dict[str, list[EffectiveShift]] = {day: [] for day in WEEK_DAYS}
    for shift in effective_shifts(schedule):
        shifts_by_day.setdefault(shift.day, []).append(shift)

    views: list[OperationalDayView] = []
    for day in WEEK_DAYS:
        if day not in {scheduled.day for scheduled in schedule.days}:
            continue
        sections: list[LocationSection] = []
        for location in ("Lago", "Negozio"):
            rows = _rows_for_location(shifts_by_day.get(day, []), location)
            sections.append(LocationSection(location.upper(), tuple(rows)))
        external_rows = _rows_for_location(shifts_by_day.get(day, []), "Lavoro esterno")
        if external_rows:
            sections.append(LocationSection("LAVORO ESTERNO", tuple(external_rows)))
        views.append(OperationalDayView(day, dates.get(day, "-"), tuple(sections)))
    return views


def weekly_hour_totals(schedule: WeeklySchedule) -> dict[str, float]:
    """Somma il lavoro reale settimanale, pause escluse, per le tre persone."""

    totals = {person: 0.0 for person in PEOPLE_IN_SUMMARY}
    for shift in effective_shifts(schedule):
        if shift.task == "FERIE / ASSENTE":
            continue
        totals.setdefault(shift.person, 0.0)
        totals[shift.person] += shift.working_hours
    return totals


def lorenzo_target_status(total_hours: float) -> str:
    """Restituisce lo stato informativo rispetto al target non bloccante di 40h."""

    delta = total_hours - LORENZO_TARGET_HOURS
    if abs(delta) < 0.01:
        return "OK 40h"
    if delta < 0:
        return f"ATTENZIONE: Lorenzo sotto target: {_format_duration(abs(delta))} rispetto a 40h"
    return f"ATTENZIONE: Lorenzo sopra target: +{_format_duration(delta)} rispetto al target 40h"


def informational_alerts(schedule: WeeklySchedule) -> list[str]:
    """Avvisi informativi non bloccanti su monte ore e turni lunghi."""

    totals = weekly_hour_totals(schedule)
    alerts = [lorenzo_target_status(totals.get(LORENZO.full_name, 0.0))]
    if alerts[0] == "OK 40h":
        alerts = []
    for shift in effective_shifts(schedule):
        if shift.person == LORENZO.full_name and shift.working_hours > LONG_DAY_HOURS:
            alerts.append(
                f"ATTENZIONE: Lorenzo turno lungo {shift.day} {shift.work_time} ({_format_duration(shift.working_hours)})."
            )
    return alerts


def critical_conflicts(schedule: WeeklySchedule) -> list[str]:
    """Raccoglie solo conflitti operativi critici, escludendo alert ore."""

    conflicts: list[str] = []
    for warning in schedule.global_warnings:
        if _is_informational_hour_warning(warning):
            continue
        conflicts.append(warning)
    for day in schedule.days:
        for warning in day.warnings:
            if _is_informational_hour_warning(warning):
                continue
            conflicts.append(f"{day.day}: {warning}")
    return conflicts


def format_duration(hours: float) -> str:
    return _format_duration(hours)


def display_person(person: str) -> str:
    return person.replace("Giammarco Mengozzi", "Gianmarco Mengozzi").replace(
        "Giammarco", "Gianmarco"
    )


def _shop_shifts(day: DaySchedule, date_label: str) -> list[EffectiveShift]:
    shifts: list[EffectiveShift] = []
    by_person = _assignments_by_person(
        [*day.shop_morning, *day.shop_afternoon], ActivityId.SHOP
    )
    for person, assignments in by_person.items():
        intervals = _merged_intervals(assignments)
        has_morning = _covers(intervals, "09:00", "12:30")
        has_afternoon = _covers(intervals, "15:30", "19:30")
        if has_morning and has_afternoon:
            shifts.append(
                EffectiveShift(
                    day.day,
                    date_label,
                    person,
                    "Negozio",
                    "09:00-12:30 / 15:30-19:30",
                    "12:30-15:30",
                    "NEGOZIO",
                    working_hours=7.5,
                )
            )
            remaining = [
                interval
                for interval in intervals
                if interval not in {("09:00", "12:30"), ("15:30", "19:30")}
            ]
        else:
            remaining = intervals
        for start, end in remaining:
            task = (
                "APERTURA NEGOZIO"
                if _to_minutes(start) < _to_minutes("14:00")
                else "CHIUSURA NEGOZIO"
            )
            shifts.append(
                EffectiveShift(
                    day.day,
                    date_label,
                    person,
                    "Negozio",
                    f"{start}-{end}",
                    "-",
                    task,
                    working_hours=_hours_between(start, end),
                )
            )
    return shifts


def _lake_shifts(day: DaySchedule, date_label: str) -> list[EffectiveShift]:
    shifts: list[EffectiveShift] = []
    by_person = _assignments_by_person(
        [*day.lake_morning, *day.lake_afternoon], ActivityId.LAKE
    )
    for person, assignments in by_person.items():
        intervals = _merged_intervals(assignments)
        if _covers(intervals, "07:30", "18:30"):
            shifts.append(
                EffectiveShift(
                    day.day,
                    date_label,
                    person,
                    "Lago",
                    "07:30-18:30",
                    "14:00-15:00",
                    "APERTURA LAGO / CHIUSURA LAGO / TURNO LUNGO",
                    working_hours=10.0,
                )
            )
            continue
        consumed: set[tuple[str, str]] = set()
        if _covers(intervals, "07:30", "14:00") and _covers(
            intervals, "15:00", "16:30"
        ):
            task, note = _lake_opening_task(8.0)
            shifts.append(
                EffectiveShift(
                    day.day,
                    date_label,
                    person,
                    "Lago",
                    "07:30-16:30",
                    "14:00-15:00",
                    task,
                    note,
                    8.0,
                )
            )
            consumed.update({("07:30", "14:00"), ("15:00", "16:30")})
        if _covers(intervals, "14:00", "18:30") and not _covers(
            intervals, "07:30", "14:00"
        ):
            shifts.append(
                EffectiveShift(
                    day.day,
                    date_label,
                    person,
                    "Lago",
                    "09:30-18:30",
                    "13:30-14:30",
                    _long_task("CHIUSURA LAGO", 8.0),
                    working_hours=8.0,
                )
            )
            consumed.add(("14:00", "18:30"))
        for start, end in intervals:
            if (start, end) in consumed:
                continue
            hours = _lake_hours(start, end)
            task = _task_for_lake_interval(start, end, hours)
            break_time = _lake_break_for_interval(start, end)
            shifts.append(
                EffectiveShift(
                    day.day,
                    date_label,
                    person,
                    "Lago",
                    f"{start}-{end}",
                    break_time,
                    task,
                    working_hours=hours,
                )
            )
    return shifts


def _external_work_shifts(day: DaySchedule, date_label: str) -> list[EffectiveShift]:
    shifts = []
    for assignment in day.company_work:
        shifts.append(
            EffectiveShift(
                day.day,
                date_label,
                assignment.person,
                "Lavoro esterno",
                f"{assignment.start}-{assignment.end}",
                "-",
                "LAVORO ESTERNO",
                assignment.period,
                assignment.working_hours,
            )
        )
    return shifts


def _assignments_by_person(
    assignments: list[Assignment], activity: ActivityId
) -> dict[str, list[Assignment]]:
    by_person: dict[str, list[Assignment]] = {}
    for assignment in assignments:
        if assignment.activity == activity:
            by_person.setdefault(assignment.person, []).append(assignment)
    return by_person


def _merged_intervals(assignments: list[Assignment]) -> list[tuple[str, str]]:
    ordered = sorted(assignments, key=lambda item: _to_minutes(item.start))
    intervals: list[tuple[int, int]] = []
    for assignment in ordered:
        start = _to_minutes(assignment.start)
        end = _to_minutes(assignment.end)
        if intervals and start <= intervals[-1][1]:
            intervals[-1] = (intervals[-1][0], max(intervals[-1][1], end))
        else:
            intervals.append((start, end))
    return [(_to_label(start), _to_label(end)) for start, end in intervals]


def _covers(intervals: list[tuple[str, str]], start: str, end: str) -> bool:
    start_minutes = _to_minutes(start)
    end_minutes = _to_minutes(end)
    return any(
        _to_minutes(item_start) <= start_minutes
        and end_minutes <= _to_minutes(item_end)
        for item_start, item_end in intervals
    )


def _task_for_lake_interval(start: str, end: str, hours: float) -> str:
    if end == "23:00":
        return _long_task("EVENTO SERALE LAGO / CHIUSURA LAGO 23:00", hours)
    if start == "07:30" and end == "16:30":
        return _long_task("APERTURA LAGO", hours)
    if start == "09:30" and end == "18:30":
        return _long_task("CHIUSURA LAGO", hours)
    if start == "07:30":
        return _long_task("APERTURA LAGO", hours)
    if end == "18:30":
        return _long_task("CHIUSURA LAGO", hours)
    return _long_task("LAGO", hours)


def _lake_opening_task(hours: float) -> tuple[str, str]:
    task = _long_task("APERTURA LAGO", hours)
    return task, "-"


def _long_task(base: str, hours: float) -> str:
    if hours > LONG_DAY_HOURS:
        return f"{base} / TURNO LUNGO"
    return base


def _lake_break_for_interval(start: str, end: str) -> str:
    start_minutes = _to_minutes(start)
    end_minutes = _to_minutes(end)
    if start_minutes < _to_minutes("14:00") and _to_minutes("15:00") < end_minutes:
        return "14:00-15:00"
    if start_minutes < _to_minutes("13:30") and _to_minutes("14:30") < end_minutes:
        return "13:30-14:30"
    return "-"


def _lake_hours(start: str, end: str) -> float:
    hours = _hours_between(start, end)
    break_time = _lake_break_for_interval(start, end)
    if break_time != "-":
        hours -= 1.0
    return hours


def _dates_by_day(week_start_date: str | None) -> dict[str, str]:
    if not week_start_date:
        return {}
    from datetime import datetime, timedelta

    try:
        start = datetime.strptime(week_start_date, "%Y-%m-%d").date()
    except ValueError:
        return {}
    return {
        day: (start + timedelta(days=index)).isoformat()
        for index, day in enumerate(WEEK_DAYS)
    }


def _is_informational_hour_warning(warning: str) -> bool:
    lowered = warning.lower()
    return "lorenzo" in lowered and any(
        word in lowered for word in ("ore", "target", "turno lungo")
    )


def _first_start(work_time: str) -> str:
    return work_time.split("-", 1)[0].strip()


def _rows_for_location(
    shifts: list[EffectiveShift], location: str
) -> list[OperationalShiftRow]:
    grouped: dict[tuple[str, str, str], list[EffectiveShift]] = {}
    for shift in shifts:
        if shift.location != location:
            continue
        note_key = shift.notes if location == "Lavoro esterno" else ""
        grouped.setdefault((shift.person, shift.location, note_key), []).append(shift)

    rows: list[OperationalShiftRow] = []
    for (person, shift_location, _), person_shifts in grouped.items():
        segments = _segments_from_shifts(person_shifts)
        rows.append(
            OperationalShiftRow(
                person=person,
                location=shift_location,
                segments=tuple(segments),
                break_time=_combined_breaks(person_shifts),
                task=_combined_tasks(person_shifts),
                daily_hours=sum(shift.working_hours for shift in person_shifts),
                notes=_combined_notes(person_shifts),
            )
        )
    return sorted(rows, key=lambda row: (_to_minutes(row.segments[0][0]), row.person))


def _segments_from_shifts(shifts: list[EffectiveShift]) -> list[tuple[str, str]]:
    segments: list[tuple[str, str]] = []
    for shift in shifts:
        for part in shift.work_time.split("/"):
            if "-" not in part:
                continue
            start, end = [item.strip() for item in part.split("-", 1)]
            segments.append((start, end))
    return _merge_label_intervals(segments)


def _merge_label_intervals(segments: list[tuple[str, str]]) -> list[tuple[str, str]]:
    assignments = [
        Assignment(
            "", ActivityId.COMPANY_WORK, "", start, end, _hours_between(start, end)
        )
        for start, end in segments
    ]
    return _merged_intervals(assignments)


def _combined_breaks(shifts: list[EffectiveShift]) -> str:
    breaks = []
    for shift in shifts:
        if shift.break_time == "-" or shift.break_time == shift.work_time:
            continue
        breaks.extend(
            part.strip() for part in shift.break_time.split("/") if part.strip() != "-"
        )
    return " / ".join(dict.fromkeys(breaks)) or "-"


def _combined_tasks(shifts: list[EffectiveShift]) -> str:
    parts: list[str] = []
    for shift in shifts:
        for raw in shift.task.replace(" / ", " + ").split("+"):
            task = raw.strip()
            if task and task not in parts:
                parts.append(task)
    task = " + ".join(parts) or "-"
    notes = _combined_notes(shifts)
    if task == "LAVORO ESTERNO" and notes != "-":
        return f"{task}: {notes}"
    return task


def _combined_notes(shifts: list[EffectiveShift]) -> str:
    notes = [shift.notes for shift in shifts if shift.notes and shift.notes != "-"]
    return " / ".join(dict.fromkeys(notes)) or "-"


def _bar_for_segment(start: str, end: str) -> str:
    hours = max(0.5, _hours_between(start, end))
    return "━" * max(1, min(10, round(hours)))


def _hours_between(start: str, end: str) -> float:
    return (_to_minutes(end) - _to_minutes(start)) / 60


def _to_minutes(value: str) -> int:
    hours, minutes = value.split(":")
    return int(hours) * 60 + int(minutes)


def _to_label(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _format_duration(hours: float) -> str:
    total_minutes = int(round(hours * 60))
    return f"{total_minutes // 60}h {total_minutes % 60:02d}m"
