"""Controlli di validità dell'orario generato."""

from __future__ import annotations

from collections import defaultdict

from .business_rules import CARPEEVOLUTION_STORE, TENUTA_DEL_GERMANO, ActivityId
from .models import Assignment, DaySchedule, WeeklySchedule
from .people import LORENZO


def validate_schedule(schedule: WeeklySchedule) -> WeeklySchedule:
    """Aggiunge warning per ore, coperture mancanti e sovrapposizioni."""

    _validate_lorenzo_hours(schedule)
    for day in schedule.days:
        _validate_coverage(day)
        _validate_person_conflicts(day)
    return schedule


def _validate_lorenzo_hours(schedule: WeeklySchedule) -> None:
    hours_by_day: dict[str, float] = defaultdict(float)
    for day in schedule.days:
        for assignment in day.assignments():
            if assignment.person == LORENZO.full_name:
                hours_by_day[day.day] += assignment.working_hours

    working_days = {day for day, hours in hours_by_day.items() if hours > 0}
    total_hours = sum(hours_by_day.values())

    if total_hours != LORENZO.strict_weekly_hours:
        schedule.global_warnings.append(
            f"Lorenzo ha {total_hours:g} ore lavorative: devono essere esattamente 40."
        )

    if len(working_days) != LORENZO.strict_working_days:
        schedule.global_warnings.append(
            f"Lorenzo lavora {len(working_days)} giorni: devono essere esattamente 5."
        )

    for day, hours in sorted(hours_by_day.items()):
        if hours and hours != LORENZO.strict_daily_hours:
            schedule.global_warnings.append(
                f"Lorenzo lavora {hours:g} ore di {day}: devono essere 8 ore."
            )


def _validate_coverage(day: DaySchedule) -> None:
    lake_ranges = day.lake_required_ranges
    if lake_ranges is None and day.day in TENUTA_DEL_GERMANO.open_days:
        lake_ranges = [("07:30", "18:30")]
    for start, end in lake_ranges or []:
        _validate_activity_coverage(
            day,
            ActivityId.LAKE,
            _assignments_for_activity(day, ActivityId.LAKE),
            start,
            end,
            "lago",
        )

    shop_ranges = day.shop_required_ranges
    if shop_ranges is None and day.day in CARPEEVOLUTION_STORE.open_days:
        shop_ranges = [("09:00", "12:30"), ("15:30", "19:30")]
    for start, end in shop_ranges or []:
        label = "negozio mattina" if start < "14:00" else "negozio pomeriggio"
        _validate_activity_coverage(
            day,
            ActivityId.SHOP,
            _assignments_for_activity(day, ActivityId.SHOP),
            start,
            end,
            label,
        )


def _validate_activity_coverage(
    day: DaySchedule,
    activity: ActivityId,
    assignments: list[Assignment],
    required_start: str,
    required_end: str,
    label: str,
) -> None:
    del activity  # Mantiene la firma pronta per controlli più avanzati.
    missing_ranges = _missing_ranges(assignments, _to_minutes(required_start), _to_minutes(required_end))
    for start, end in missing_ranges:
        day.warnings.append(
            f"Copertura mancante {label} dalle {_to_label(start)} alle {_to_label(end)}."
        )


def _validate_person_conflicts(day: DaySchedule) -> None:
    assignments_by_person: dict[str, list[Assignment]] = defaultdict(list)
    for assignment in day.assignments():
        assignments_by_person[assignment.person].append(assignment)

    for person, assignments in assignments_by_person.items():
        ordered = sorted(assignments, key=lambda item: _to_minutes(item.start))
        for previous, current in zip(ordered, ordered[1:]):
            if _to_minutes(current.start) < _to_minutes(previous.end):
                day.warnings.append(
                    f"Conflitto: {person} è assegnato in fasce sovrapposte "
                    f"({previous.start}-{previous.end} e {current.start}-{current.end})."
                )


def _assignments_for_activity(day: DaySchedule, activity: ActivityId) -> list[Assignment]:
    return [assignment for assignment in day.assignments() if assignment.activity == activity]


def _missing_ranges(assignments: list[Assignment], required_start: int, required_end: int) -> list[tuple[int, int]]:
    intervals = sorted(
        (_to_minutes(assignment.start), _to_minutes(assignment.end)) for assignment in assignments
    )
    cursor = required_start
    missing: list[tuple[int, int]] = []

    for start, end in intervals:
        if end <= cursor:
            continue
        if start > cursor:
            missing.append((cursor, start))
        cursor = max(cursor, end)
        if cursor >= required_end:
            break

    if cursor < required_end:
        missing.append((cursor, required_end))
    return missing


def _to_minutes(value: str) -> int:
    hours, minutes = value.split(":")
    return int(hours) * 60 + int(minutes)


def _to_label(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"
