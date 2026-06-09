"""Generazione dell'orario settimanale."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, timedelta

from .business_rules import ActivityId, CARPEEVOLUTION_STORE, TENUTA_DEL_GERMANO, WEEK_DAYS
from .models import Assignment, DaySchedule, WeeklySchedule
from .people import ANGELO, GIAMMARCO, LORENZO
from .validator import validate_schedule
from .weekly_input import WeeklyInstruction, parse_weekly_instruction
from .wife_calendar import WifeCalendarRepository, can_giammarco_open_lake_at_0730


LAKE_FULL_DAY = ("07:30", "18:30")
SHOP_MORNING = ("09:00", "12:30")
SHOP_AFTERNOON = ("15:30", "19:30")


def generate_weekly_schedule(
    weekly_text: str | None = None,
    *,
    week_start_date: str | date | None = None,
    wife_calendar_repository: WifeCalendarRepository | None = None,
    wife_calendar_codes: dict[str, str] | None = None,
) -> WeeklySchedule:
    """Crea un orario completo applicando regole fisse e istruzioni settimanali.

    Se `week_start_date` è valorizzato, il motore può collegare i giorni della
    settimana ai codici salvati nel calendario della moglie di Giammarco. Per ora
    solo il codice `M` blocca l'apertura lago delle 07:30.
    """

    instruction = parse_weekly_instruction(weekly_text)
    lorenzo_days = _resolve_lorenzo_working_days(instruction)
    _expand_giammarco_requested_shop_days(instruction, lorenzo_days)
    wife_codes = wife_calendar_codes if wife_calendar_codes is not None else _load_wife_calendar_codes(wife_calendar_repository)
    week_dates = _week_dates_by_day(week_start_date)
    days = [_build_day(day, lorenzo_days, instruction, wife_codes, week_dates) for day in WEEK_DAYS]
    schedule = WeeklySchedule(days=days, week_start_date=_normalize_week_start_date(week_start_date))
    schedule.global_warnings.extend(
        f"Nota non interpretata automaticamente: {note}" for note in instruction.unknown_notes
    )
    validate_schedule(schedule)
    return schedule


def _normalize_week_start_date(week_start_date: str | date | None) -> str | None:
    if isinstance(week_start_date, date):
        return week_start_date.isoformat()
    return week_start_date


def _load_wife_calendar_codes(repository: WifeCalendarRepository | None) -> dict[str, str]:
    if repository is None:
        repository = WifeCalendarRepository()
    return repository.load()


def _week_dates_by_day(week_start_date: str | date | None) -> dict[str, str]:
    if week_start_date is None:
        return {}
    if isinstance(week_start_date, str):
        start = datetime.strptime(week_start_date, "%Y-%m-%d").date()
    else:
        start = week_start_date
    return {day: (start + timedelta(days=index)).isoformat() for index, day in enumerate(WEEK_DAYS)}



def _expand_giammarco_requested_shop_days(
    instruction: WeeklyInstruction, lorenzo_days: set[str]
) -> None:
    """Trasforma richieste tipo "due giorni in negozio" in giorni concreti."""

    requested_count = instruction.giammarco_requested_shop_day_count
    if requested_count is None or len(instruction.giammarco_shop_days) >= requested_count:
        return

    unavailable = instruction.unavailable_days_for(GIAMMARCO.full_name)
    external_days = {request.day for request in instruction.giammarco_external_work}
    preferred_days = [
        day
        for day in CARPEEVOLUTION_STORE.open_days
        if day in lorenzo_days and day not in unavailable and day not in external_days
    ]
    fallback_days = [
        day
        for day in CARPEEVOLUTION_STORE.open_days
        if day not in unavailable and day not in external_days
    ]

    for day in [*preferred_days, *fallback_days]:
        instruction.giammarco_shop_days.add(day)
        if len(instruction.giammarco_shop_days) >= requested_count:
            return

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


def _build_day(
    day: str,
    lorenzo_days: set[str],
    instruction: WeeklyInstruction,
    wife_codes: dict[str, str],
    week_dates: dict[str, str],
) -> DaySchedule:
    day_schedule = DaySchedule(day=day)
    unavailable = {
        person
        for person in (ANGELO.full_name, GIAMMARCO.full_name, LORENZO.full_name)
        if day in instruction.unavailable_days_for(person)
    }

    _add_closure_and_absence_notes(day_schedule, unavailable)
    _add_giammarco_external_work(day_schedule, instruction)
    _assign_lorenzo_default_lake(day_schedule, lorenzo_days, unavailable)
    _assign_forced_giammarco(day_schedule, instruction, unavailable, wife_codes, week_dates)
    _assign_default_angelo_shop(day_schedule, instruction, unavailable)
    _fill_required_coverage(day_schedule, unavailable, wife_codes, week_dates)
    _apply_notes(day_schedule, instruction, wife_codes, week_dates)

    return day_schedule


def _add_closure_and_absence_notes(day_schedule: DaySchedule, unavailable: set[str]) -> None:
    if day_schedule.day in TENUTA_DEL_GERMANO.closed_days:
        day_schedule.notes.append("Lago chiuso")
    if day_schedule.day in CARPEEVOLUTION_STORE.closed_days:
        day_schedule.notes.append("Negozio chiuso")
    for person in sorted(unavailable):
        day_schedule.notes.append(f"{person} non disponibile per istruzione settimanale")


def _add_giammarco_external_work(day_schedule: DaySchedule, instruction: WeeklyInstruction) -> None:
    for request in instruction.external_work_for(day_schedule.day):
        _append_assignment(
            day_schedule,
            _assignment(GIAMMARCO.full_name, ActivityId.COMPANY_WORK, request.start, request.end),
        )
        day_schedule.notes.append(
            f"Giammarco impegnato in {request.label} ({request.start}-{request.end}): non conta come copertura fissa"
        )


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


def _assign_forced_giammarco(
    day_schedule: DaySchedule,
    instruction: WeeklyInstruction,
    unavailable: set[str],
    wife_codes: dict[str, str],
    week_dates: dict[str, str],
) -> None:
    day = day_schedule.day
    if GIAMMARCO.full_name in unavailable:
        return

    if day in instruction.giammarco_shop_days and day in CARPEEVOLUTION_STORE.open_days:
        _append_shop_full_day(day_schedule, GIAMMARCO.full_name)
        day_schedule.notes.append("Giammarco in negozio per istruzione settimanale")

    if day in instruction.giammarco_lake_days and day in TENUTA_DEL_GERMANO.open_days:
        _append_lake_full_day(day_schedule, GIAMMARCO.full_name, wife_codes, week_dates)
        day_schedule.notes.append("Giammarco al lago per istruzione settimanale")


def _assign_default_angelo_shop(
    day_schedule: DaySchedule,
    instruction: WeeklyInstruction,
    unavailable: set[str],
) -> None:
    day = day_schedule.day
    if day not in CARPEEVOLUTION_STORE.open_days or ANGELO.full_name in unavailable:
        return

    # Se Giammarco è stato richiesto in negozio, lasciamo Angelo libero per il
    # riequilibrio del lago: il negozio è già coperto e Angelo può intervenire
    # solo dove serve davvero, senza creare sovrapposizioni.
    if day in instruction.giammarco_shop_days:
        return

    _append_shop_full_day(day_schedule, ANGELO.full_name)


def _fill_required_coverage(
    day_schedule: DaySchedule,
    unavailable: set[str],
    wife_codes: dict[str, str],
    week_dates: dict[str, str],
) -> None:
    day = day_schedule.day

    # Angelo può normalmente gestire il negozio da solo. Se però non c'è in un
    # giorno di apertura, Giammarco deve prima coprire il presidio negozio.
    if day in CARPEEVOLUTION_STORE.open_days and ANGELO.full_name in unavailable:
        _fill_shop_coverage(day_schedule, unavailable, wife_codes, week_dates)
        _fill_lake_coverage(day_schedule, unavailable, wife_codes, week_dates)
        return

    # Priorità operativa: quando Giammarco serve come copertura, lo usiamo prima
    # sul lago; il negozio resta ad Angelo salvo richiesta esplicita o buco.
    _fill_lake_coverage(day_schedule, unavailable, wife_codes, week_dates)
    _fill_shop_coverage(day_schedule, unavailable, wife_codes, week_dates)


def _fill_lake_coverage(
    day_schedule: DaySchedule,
    unavailable: set[str],
    wife_codes: dict[str, str],
    week_dates: dict[str, str],
) -> None:
    if day_schedule.day not in TENUTA_DEL_GERMANO.open_days:
        return
    _fill_activity_ranges(
        day_schedule,
        ActivityId.LAKE,
        [LAKE_FULL_DAY],
        (GIAMMARCO.full_name, ANGELO.full_name),
        unavailable,
        wife_codes,
        week_dates,
    )


def _fill_shop_coverage(
    day_schedule: DaySchedule,
    unavailable: set[str],
    wife_codes: dict[str, str],
    week_dates: dict[str, str],
) -> None:
    if day_schedule.day not in CARPEEVOLUTION_STORE.open_days:
        return
    _fill_activity_ranges(
        day_schedule,
        ActivityId.SHOP,
        [SHOP_MORNING, SHOP_AFTERNOON],
        (ANGELO.full_name, GIAMMARCO.full_name),
        unavailable,
        wife_codes,
        week_dates,
    )


def _fill_activity_ranges(
    day_schedule: DaySchedule,
    activity: ActivityId,
    required_ranges: Iterable[tuple[str, str]],
    candidate_people: tuple[str, ...],
    unavailable: set[str],
    wife_codes: dict[str, str],
    week_dates: dict[str, str],
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
                wife_codes,
                week_dates,
            )


def _assign_first_available(
    day_schedule: DaySchedule,
    activity: ActivityId,
    start: str,
    end: str,
    candidate_people: tuple[str, ...],
    unavailable: set[str],
    wife_codes: dict[str, str],
    week_dates: dict[str, str],
) -> None:
    giammarco_conflict = _conflicting_interval(day_schedule, GIAMMARCO.full_name, start, end)
    if (
        activity == ActivityId.LAKE
        and GIAMMARCO.full_name in candidate_people
        and giammarco_conflict is not None
        and giammarco_conflict[0] <= _to_minutes(start)
        and giammarco_conflict[1] < _to_minutes(end)
    ):
        split = _to_label(giammarco_conflict[1])
        fallback_people = tuple(person for person in candidate_people if person != GIAMMARCO.full_name)
        _assign_first_available(
            day_schedule, activity, start, split, fallback_people, unavailable, wife_codes, week_dates
        )
        _assign_first_available(
            day_schedule, activity, split, end, candidate_people, unavailable, wife_codes, week_dates
        )
        return

    for person in candidate_people:
        if person in unavailable:
            continue
        if not _can_assign_person(day_schedule, person, activity, start, end, wife_codes, week_dates):
            continue
        _append_assignment(day_schedule, _assignment(person, activity, start, end))
        return


def _can_assign_person(
    day_schedule: DaySchedule,
    person: str,
    activity: ActivityId,
    start: str,
    end: str,
    wife_codes: dict[str, str],
    week_dates: dict[str, str],
) -> bool:
    if _person_has_conflict(day_schedule, person, start, end):
        return False
    if person == GIAMMARCO.full_name and activity == ActivityId.LAKE and start == "07:30":
        return _can_giammarco_open_lake(day_schedule, wife_codes, week_dates)
    return True


def _can_giammarco_open_lake(
    day_schedule: DaySchedule,
    wife_codes: dict[str, str],
    week_dates: dict[str, str],
) -> bool:
    date_key = week_dates.get(day_schedule.day)
    code = wife_codes.get(date_key) if date_key else None
    allowed = can_giammarco_open_lake_at_0730(code)
    if allowed is False:
        warning = (
            f"Calendario moglie {date_key}: codice M, quindi Giammarco non può aprire il lago alle 07:30."
        )
        if warning not in day_schedule.warnings:
            day_schedule.warnings.append(warning)
        return False
    return True


def _append_lake_full_day(
    day_schedule: DaySchedule,
    person: str,
    wife_codes: dict[str, str],
    week_dates: dict[str, str],
) -> None:
    if _can_assign_person(day_schedule, person, ActivityId.LAKE, "07:30", "14:00", wife_codes, week_dates):
        _append_assignment(day_schedule, _assignment(person, ActivityId.LAKE, "07:30", "14:00"))
    if _can_assign_person(day_schedule, person, ActivityId.LAKE, "14:00", "18:30", wife_codes, week_dates):
        _append_assignment(day_schedule, _assignment(person, ActivityId.LAKE, "14:00", "18:30"))


def _append_shop_full_day(day_schedule: DaySchedule, person: str) -> None:
    _append_if_no_person_conflict(day_schedule, person, ActivityId.SHOP, *SHOP_MORNING)
    _append_if_no_person_conflict(day_schedule, person, ActivityId.SHOP, *SHOP_AFTERNOON)


def _append_if_no_person_conflict(
    day_schedule: DaySchedule, person: str, activity: ActivityId, start: str, end: str
) -> None:
    if not _person_has_conflict(day_schedule, person, start, end):
        _append_assignment(day_schedule, _assignment(person, activity, start, end))


def _append_assignment(day_schedule: DaySchedule, assignment: Assignment) -> None:
    target = {
        (ActivityId.LAKE, "morning"): day_schedule.lake_morning,
        (ActivityId.LAKE, "afternoon"): day_schedule.lake_afternoon,
        (ActivityId.SHOP, "morning"): day_schedule.shop_morning,
        (ActivityId.SHOP, "afternoon"): day_schedule.shop_afternoon,
        (ActivityId.COMPANY_WORK, "morning"): day_schedule.company_work,
        (ActivityId.COMPANY_WORK, "afternoon"): day_schedule.company_work,
    }[(assignment.activity, assignment.period)]
    target.append(assignment)


def _assignment(person: str, activity: ActivityId, start: str, end: str) -> Assignment:
    return Assignment(person, activity, _period_for(start), start, end, _hours_between(start, end))


def _apply_notes(
    day_schedule: DaySchedule,
    instruction: WeeklyInstruction,
    wife_codes: dict[str, str],
    week_dates: dict[str, str],
) -> None:
    if day_schedule.day in instruction.lorenzo_must_open_lake_days:
        day_schedule.notes.append("Lorenzo apre il lago per istruzione settimanale")

    if day_schedule.day in instruction.high_lake_booking_days:
        day_schedule.notes.append("Molte prenotazioni al lago: consigliata attenzione extra")
        if _can_assign_person(
            day_schedule,
            GIAMMARCO.full_name,
            ActivityId.LAKE,
            "07:30",
            "14:00",
            wife_codes,
            week_dates,
        ):
            day_schedule.lake_morning.append(
                Assignment(GIAMMARCO.full_name, ActivityId.LAKE, "morning", "07:30", "14:00", 6.5)
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


def _assignments_for_activity(day_schedule: DaySchedule, activity: ActivityId) -> list[Assignment]:
    return [assignment for assignment in day_schedule.assignments() if assignment.activity == activity]


def _person_has_conflict(day_schedule: DaySchedule, person: str, start: str, end: str) -> bool:
    return _conflicting_interval(day_schedule, person, start, end) is not None


def _conflicting_interval(
    day_schedule: DaySchedule, person: str, start: str, end: str
) -> tuple[int, int] | None:
    start_minutes = _to_minutes(start)
    end_minutes = _to_minutes(end)
    for assignment in sorted(day_schedule.assignments(), key=lambda item: _to_minutes(item.start)):
        if assignment.person != person:
            continue
        assignment_start = _to_minutes(assignment.start)
        assignment_end = _to_minutes(assignment.end)
        if start_minutes < assignment_end and assignment_start < end_minutes:
            return assignment_start, assignment_end
    return None


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
