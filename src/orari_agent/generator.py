"""Generazione dell'orario settimanale."""

from __future__ import annotations

from collections.abc import Iterable

from .business_rules import ActivityId, CARPEEVOLUTION_STORE, TENUTA_DEL_GERMANO, WEEK_DAYS
from .models import Assignment, DaySchedule, WeeklySchedule
from .people import ANGELO, GIANMARCO, LORENZO
from .validator import validate_schedule
from .weekly_input import WeeklyInstruction, parse_weekly_instruction


LAKE_FULL_DAY = ("07:30", "18:30")
SHOP_MORNING = ("09:00", "12:30")
SHOP_AFTERNOON = ("15:30", "19:30")


def generate_weekly_schedule(weekly_text: str | None = None) -> WeeklySchedule:
    """Crea un orario completo applicando regole fisse e istruzioni settimanali."""

    instruction = parse_weekly_instruction(weekly_text)
    lorenzo_days = _resolve_lorenzo_working_days(instruction)
    days = [_build_day(day, lorenzo_days, instruction) for day in WEEK_DAYS]
    schedule = WeeklySchedule(days=days)
    schedule.global_warnings.extend(
        f"Nota non interpretata automaticamente: {note}" for note in instruction.unknown_notes
    )
    validate_schedule(schedule)
    return schedule


def _resolve_lorenzo_working_days(instruction: WeeklyInstruction) -> set[str]:
    """Determina i 5 giorni di Lorenzo, preservando 40 ore settimanali quando possibile."""

    unavailable = instruction.unavailable_days_for(LORENZO.full_name)
    forced_days = {
        day
        for day in instruction.lorenzo_must_open_lake_days
        if day in TENUTA_DEL_GERMANO.open_days and day not in unavailable
    }
    working_days = {
        day
        for day in LORENZO.ideal_working_days
        if day in TENUTA_DEL_GERMANO.open_days and day not in unavailable
    }
    working_days.update(forced_days)

    target_days = LORENZO.strict_working_days or len(working_days)
    if len(working_days) < target_days:
        for day in TENUTA_DEL_GERMANO.open_days:
            if day not in unavailable:
                working_days.add(day)
            if len(working_days) >= target_days:
                break

    removable_days = [
        day
        for day in LORENZO.ideal_working_days
        if day not in forced_days and day not in unavailable
    ]
    while len(working_days) > target_days and removable_days:
        working_days.remove(removable_days.pop(0))

    return working_days


def _build_day(day: str, lorenzo_days: set[str], instruction: WeeklyInstruction) -> DaySchedule:
    day_schedule = DaySchedule(day=day)
    unavailable = {
        person
        for person in (ANGELO.full_name, GIANMARCO.full_name, LORENZO.full_name)
        if day in instruction.unavailable_days_for(person)
    }

    _add_closure_and_absence_notes(day_schedule, unavailable)
    _assign_lorenzo_default_lake(day_schedule, lorenzo_days, unavailable)
    _assign_forced_gianmarco(day_schedule, instruction, unavailable)
    _assign_default_angelo_shop(day_schedule, instruction, unavailable)
    _fill_required_coverage(day_schedule, unavailable)
    _apply_notes(day_schedule, instruction)

    return day_schedule


def _add_closure_and_absence_notes(day_schedule: DaySchedule, unavailable: set[str]) -> None:
    if day_schedule.day in TENUTA_DEL_GERMANO.closed_days:
        day_schedule.notes.append("Lago chiuso")
    if day_schedule.day in CARPEEVOLUTION_STORE.closed_days:
        day_schedule.notes.append("Negozio chiuso")
    for person in sorted(unavailable):
        day_schedule.notes.append(f"{person} non disponibile per istruzione settimanale")


def _assign_lorenzo_default_lake(
    day_schedule: DaySchedule,
    lorenzo_days: set[str],
    unavailable: set[str],
) -> None:
    day = day_schedule.day
    if day not in TENUTA_DEL_GERMANO.open_days:
        return
    if day not in lorenzo_days or LORENZO.full_name in unavailable:
        return

    day_schedule.lake_morning.append(_lorenzo_lake_morning())
    day_schedule.lake_afternoon.append(_lorenzo_lake_afternoon())


def _assign_forced_gianmarco(
    day_schedule: DaySchedule,
    instruction: WeeklyInstruction,
    unavailable: set[str],
) -> None:
    day = day_schedule.day
    if GIANMARCO.full_name in unavailable:
        return

    if day in instruction.gianmarco_shop_days and day in CARPEEVOLUTION_STORE.open_days:
        _append_shop_full_day(day_schedule, GIANMARCO.full_name)
        day_schedule.notes.append("Gianmarco in negozio per istruzione settimanale")

    if day in instruction.gianmarco_lake_days and day in TENUTA_DEL_GERMANO.open_days:
        _append_lake_full_day(day_schedule, GIANMARCO.full_name)
        day_schedule.notes.append("Gianmarco al lago per istruzione settimanale")


def _assign_default_angelo_shop(
    day_schedule: DaySchedule,
    instruction: WeeklyInstruction,
    unavailable: set[str],
) -> None:
    day = day_schedule.day
    if day not in CARPEEVOLUTION_STORE.open_days or ANGELO.full_name in unavailable:
        return

    # Se Gianmarco è stato richiesto in negozio, lasciamo Angelo libero per il
    # riequilibrio del lago: il negozio è già coperto e Angelo può intervenire
    # solo dove serve davvero, senza creare sovrapposizioni.
    if day in instruction.gianmarco_shop_days:
        return

    _append_shop_full_day(day_schedule, ANGELO.full_name)


def _fill_required_coverage(day_schedule: DaySchedule, unavailable: set[str]) -> None:
    day = day_schedule.day

    # Se Angelo non c'è in un giorno di apertura del negozio, Gianmarco deve
    # prima coprire il presidio negozio. Eventuali impossibilità residue vengono
    # poi evidenziate dal validatore sul lago.
    if day in CARPEEVOLUTION_STORE.open_days and ANGELO.full_name in unavailable:
        _fill_shop_coverage(day_schedule, unavailable)
        _fill_lake_coverage(day_schedule, unavailable)
        return

    _fill_lake_coverage(day_schedule, unavailable)
    _fill_shop_coverage(day_schedule, unavailable)


def _fill_lake_coverage(day_schedule: DaySchedule, unavailable: set[str]) -> None:
    if day_schedule.day not in TENUTA_DEL_GERMANO.open_days:
        return
    _fill_activity_ranges(
        day_schedule,
        ActivityId.LAKE,
        [LAKE_FULL_DAY],
        (GIANMARCO.full_name, ANGELO.full_name),
        unavailable,
    )


def _fill_shop_coverage(day_schedule: DaySchedule, unavailable: set[str]) -> None:
    if day_schedule.day not in CARPEEVOLUTION_STORE.open_days:
        return
    _fill_activity_ranges(
        day_schedule,
        ActivityId.SHOP,
        [SHOP_MORNING, SHOP_AFTERNOON],
        (ANGELO.full_name, GIANMARCO.full_name),
        unavailable,
    )


def _fill_activity_ranges(
    day_schedule: DaySchedule,
    activity: ActivityId,
    required_ranges: Iterable[tuple[str, str]],
    candidate_people: tuple[str, ...],
    unavailable: set[str],
) -> None:
    for required_start, required_end in required_ranges:
        for start_minutes, end_minutes in _missing_ranges(
            _assignments_for_activity(day_schedule, activity),
            _to_minutes(required_start),
            _to_minutes(required_end),
        ):
            _assign_first_available(
                day_schedule,
                activity,
                _to_label(start_minutes),
                _to_label(end_minutes),
                candidate_people,
                unavailable,
            )


def _assign_first_available(
    day_schedule: DaySchedule,
    activity: ActivityId,
    start: str,
    end: str,
    candidate_people: tuple[str, ...],
    unavailable: set[str],
) -> None:
    for person in candidate_people:
        if person in unavailable:
            continue
        if not _person_has_conflict(day_schedule, person, start, end):
            _append_assignment(day_schedule, _assignment(person, activity, start, end))
            return


def _append_lake_full_day(day_schedule: DaySchedule, person: str) -> None:
    _append_assignment(day_schedule, _assignment(person, ActivityId.LAKE, "07:30", "14:00"))
    _append_assignment(day_schedule, _assignment(person, ActivityId.LAKE, "14:00", "18:30"))


def _append_shop_full_day(day_schedule: DaySchedule, person: str) -> None:
    _append_assignment(day_schedule, _assignment(person, ActivityId.SHOP, *SHOP_MORNING))
    _append_assignment(day_schedule, _assignment(person, ActivityId.SHOP, *SHOP_AFTERNOON))


def _append_assignment(day_schedule: DaySchedule, assignment: Assignment) -> None:
    target = {
        (ActivityId.LAKE, "morning"): day_schedule.lake_morning,
        (ActivityId.LAKE, "afternoon"): day_schedule.lake_afternoon,
        (ActivityId.SHOP, "morning"): day_schedule.shop_morning,
        (ActivityId.SHOP, "afternoon"): day_schedule.shop_afternoon,
    }[(assignment.activity, assignment.period)]
    target.append(assignment)


def _assignment(person: str, activity: ActivityId, start: str, end: str) -> Assignment:
    return Assignment(person, activity, _period_for(start), start, end, _hours_between(start, end))


def _apply_notes(day_schedule: DaySchedule, instruction: WeeklyInstruction) -> None:
    if day_schedule.day in instruction.lorenzo_must_open_lake_days:
        day_schedule.notes.append("Lorenzo apre il lago per istruzione settimanale")

    if day_schedule.day in instruction.high_lake_booking_days:
        day_schedule.notes.append("Molte prenotazioni al lago: consigliata attenzione extra")
        if not _person_has_conflict(day_schedule, GIANMARCO.full_name, "07:30", "14:00"):
            day_schedule.lake_morning.append(
                Assignment(GIANMARCO.full_name, ActivityId.LAKE, "morning", "07:30", "14:00", 6.5)
            )


def _lorenzo_lake_morning() -> Assignment:
    return Assignment(
        LORENZO.full_name,
        ActivityId.LAKE,
        "morning",
        "07:30",
        "14:00",
        6.5,
        break_label=None,
    )


def _lorenzo_lake_afternoon() -> Assignment:
    return Assignment(
        LORENZO.full_name,
        ActivityId.LAKE,
        "afternoon",
        "15:00",
        "16:30",
        1.5,
        break_label="14:00-15:00",
    )


def _assignments_for_activity(day: DaySchedule, activity: ActivityId) -> list[Assignment]:
    return [assignment for assignment in day.assignments() if assignment.activity == activity]


def _person_has_conflict(day: DaySchedule, person: str, start: str, end: str) -> bool:
    start_minutes = _to_minutes(start)
    end_minutes = _to_minutes(end)
    return any(
        assignment.person == person
        and start_minutes < _to_minutes(assignment.end)
        and end_minutes > _to_minutes(assignment.start)
        for assignment in day.assignments()
    )


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


def _period_for(start: str) -> str:
    return "morning" if _to_minutes(start) < _to_minutes("14:00") else "afternoon"


def _hours_between(start: str, end: str) -> float:
    return (_to_minutes(end) - _to_minutes(start)) / 60


def _to_minutes(value: str) -> int:
    hours, minutes = value.split(":")
    return int(hours) * 60 + int(minutes)


def _to_label(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"
