"""Generazione dell'orario settimanale."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime, timedelta

from .business_rules import (
    ActivityId,
    CARPEEVOLUTION_STORE,
    TENUTA_DEL_GERMANO,
    WEEK_DAYS,
)
from .models import Assignment, DaySchedule, WeeklySchedule
from .people import ANGELO, GIAMMARCO, LORENZO
from .validator import validate_schedule
from .weekly_input import CoverageRequest, WeeklyInstruction, parse_weekly_instruction
from .wife_calendar import WifeCalendarRepository, can_giammarco_open_lake_at_0730

LAKE_FULL_DAY = ("07:30", "18:30")
SHOP_MORNING = ("09:00", "12:30")
SHOP_AFTERNOON = ("15:30", "19:30")


def generate_weekly_schedule(
    weekly_text: str | WeeklyInstruction | None = None,
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

    instruction = (
        weekly_text
        if isinstance(weekly_text, WeeklyInstruction)
        else parse_weekly_instruction(weekly_text)
    )
    lorenzo_days = _resolve_lorenzo_working_days(instruction)
    _expand_giammarco_requested_shop_days(instruction, lorenzo_days)
    wife_codes = (
        wife_calendar_codes
        if wife_calendar_codes is not None
        else _load_wife_calendar_codes(wife_calendar_repository)
    )
    week_dates = _week_dates_by_day(week_start_date)
    days = [
        _build_day(day, lorenzo_days, instruction, wife_codes, week_dates)
        for day in WEEK_DAYS
    ]
    schedule = WeeklySchedule(
        days=days,
        global_notes=list(instruction.weekly_notes),
        week_start_date=_normalize_week_start_date(week_start_date),
    )
    schedule.global_warnings.extend(
        f"Nota non interpretata automaticamente: {note}"
        for note in instruction.unknown_notes
    )
    validate_schedule(schedule)
    return schedule


def _normalize_week_start_date(week_start_date: str | date | None) -> str | None:
    if isinstance(week_start_date, date):
        return week_start_date.isoformat()
    return week_start_date


def _load_wife_calendar_codes(
    repository: WifeCalendarRepository | None,
) -> dict[str, str]:
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
    return {
        day: (start + timedelta(days=index)).isoformat()
        for index, day in enumerate(WEEK_DAYS)
    }


def _coverage_request(
    day: str, person: str, activity: ActivityId, start: str, end: str, label: str
) -> CoverageRequest:
    return CoverageRequest(day, person, activity, start, end, label)


def _required_ranges_for(
    day: str, activity: ActivityId, instruction: WeeklyInstruction
) -> list[tuple[str, str]]:
    base: list[tuple[str, str]] = []
    if activity == ActivityId.LAKE:
        if day in TENUTA_DEL_GERMANO.open_days or _has_exceptional_opening(
            instruction, day, activity
        ):
            base = [LAKE_FULL_DAY]
    elif day in CARPEEVOLUTION_STORE.open_days or _has_exceptional_opening(
        instruction, day, activity
    ):
        base = [SHOP_MORNING, SHOP_AFTERNOON]

    for opening in instruction.exceptional_openings:
        if (
            opening.day == day
            and opening.activity == activity
            and opening.period != "full_day"
        ):
            base = [_period_range(activity, opening.period)]

    for closure in instruction.exceptional_closures:
        if closure.day != day or closure.activity != activity:
            continue
        if closure.period == "full_day":
            base = []
        else:
            base = _subtract_closed_range(base, _period_range(activity, closure.period))
    return base


def _subtract_closed_range(
    ranges: list[tuple[str, str]], closed: tuple[str, str]
) -> list[tuple[str, str]]:
    closed_start, closed_end = (_to_minutes(value) for value in closed)
    remaining: list[tuple[str, str]] = []
    for start, end in ranges:
        start_minutes = _to_minutes(start)
        end_minutes = _to_minutes(end)
        if closed_end <= start_minutes or closed_start >= end_minutes:
            remaining.append((start, end))
            continue
        if start_minutes < closed_start:
            remaining.append((start, closed[0]))
        if closed_end < end_minutes:
            remaining.append((closed[1], end))
    return remaining


def _has_exceptional_opening(
    instruction: WeeklyInstruction, day: str, activity: ActivityId
) -> bool:
    return any(
        opening.day == day and opening.activity == activity
        for opening in instruction.exceptional_openings
    )


def _period_range(activity: ActivityId, period: str) -> tuple[str, str]:
    if activity == ActivityId.LAKE:
        return ("07:30", "14:00") if period == "morning" else ("14:00", "18:30")
    return SHOP_MORNING if period == "morning" else SHOP_AFTERNOON


def _is_range_required(
    day_schedule: DaySchedule, activity: ActivityId, start: str, end: str
) -> bool:
    required_ranges = (
        day_schedule.lake_required_ranges
        if activity == ActivityId.LAKE
        else day_schedule.shop_required_ranges
    )
    return any(
        _to_minutes(req_start) <= _to_minutes(start)
        and _to_minutes(end) <= _to_minutes(req_end)
        for req_start, req_end in (required_ranges or [])
    )


def _expand_giammarco_requested_shop_days(
    instruction: WeeklyInstruction, lorenzo_days: set[str]
) -> None:
    """Trasforma richieste tipo "due giorni in negozio" in giorni concreti."""

    requested_count = instruction.giammarco_requested_shop_day_count
    if (
        requested_count is None
        or len(instruction.giammarco_shop_days) >= requested_count
    ):
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
        if day not in instruction.giammarco_shop_days:
            instruction.forced_shop_coverage.extend(
                [
                    _coverage_request(
                        day,
                        GIAMMARCO.full_name,
                        ActivityId.SHOP,
                        *SHOP_MORNING,
                        "copertura negozio",
                    ),
                    _coverage_request(
                        day,
                        GIAMMARCO.full_name,
                        ActivityId.SHOP,
                        *SHOP_AFTERNOON,
                        "copertura negozio",
                    ),
                ]
            )
        instruction.giammarco_shop_days.add(day)
        if len(instruction.giammarco_shop_days) >= requested_count:
            return


def _resolve_lorenzo_working_days(instruction: WeeklyInstruction) -> set[str]:
    """Determina i 5 giorni di Lorenzo, preservando 40 ore settimanali quando possibile."""

    unavailable = instruction.unavailable_days_for(LORENZO.full_name)
    forced_days = {
        day
        for day in instruction.lorenzo_must_open_lake_days
        if _required_ranges_for(day, ActivityId.LAKE, instruction)
        and day not in unavailable
    }
    working_days = {
        day
        for day in LORENZO.ideal_working_days
        if _required_ranges_for(day, ActivityId.LAKE, instruction)
        and day not in unavailable
    }
    working_days.update(forced_days)

    target_days = LORENZO.strict_working_days or len(working_days)
    if len(working_days) < target_days:
        for day in WEEK_DAYS:
            if (
                _required_ranges_for(day, ActivityId.LAKE, instruction)
                and day not in unavailable
            ):
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
    day_schedule.lake_required_ranges = _required_ranges_for(
        day, ActivityId.LAKE, instruction
    )
    day_schedule.shop_required_ranges = _required_ranges_for(
        day, ActivityId.SHOP, instruction
    )
    unavailable = {
        person
        for person in (ANGELO.full_name, GIAMMARCO.full_name, LORENZO.full_name)
        if day in instruction.unavailable_days_for(person)
    }

    _add_closure_and_absence_notes(day_schedule, unavailable)
    _add_giammarco_external_work(day_schedule, instruction)
    _assign_lorenzo_default_lake(day_schedule, lorenzo_days, instruction)
    _assign_forced_coverage(day_schedule, instruction, wife_codes, week_dates)
    _assign_default_angelo_shop(day_schedule, instruction)
    _fill_required_coverage(day_schedule, instruction, wife_codes, week_dates)
    _apply_notes(day_schedule, instruction, wife_codes, week_dates)

    return day_schedule


def _add_closure_and_absence_notes(
    day_schedule: DaySchedule, unavailable: set[str]
) -> None:
    if not day_schedule.lake_required_ranges:
        day_schedule.notes.append("Lago chiuso")
    if not day_schedule.shop_required_ranges:
        day_schedule.notes.append("Negozio chiuso")
    for person in sorted(unavailable):
        day_schedule.notes.append(
            f"{person} non disponibile tutto il giorno per istruzione settimanale"
        )


def _add_giammarco_external_work(
    day_schedule: DaySchedule, instruction: WeeklyInstruction
) -> None:
    for request in instruction.external_work_for(day_schedule.day):
        _append_assignment(
            day_schedule,
            _assignment(
                GIAMMARCO.full_name, ActivityId.COMPANY_WORK, request.start, request.end
            ),
        )
        day_schedule.notes.append(
            f"Giammarco impegnato in {request.label} ({request.start}-{request.end}): non conta come copertura fissa"
        )


def _assign_lorenzo_default_lake(
    day_schedule: DaySchedule,
    lorenzo_days: set[str],
    instruction: WeeklyInstruction,
) -> None:
    day = day_schedule.day
    if not day_schedule.lake_required_ranges:
        return
    if day not in lorenzo_days or day in instruction.unavailable_days_for(
        LORENZO.full_name
    ):
        return

    if not instruction.person_is_absent_for_range(
        LORENZO.full_name, day, "07:30", "14:00"
    ):
        day_schedule.lake_morning.append(_lorenzo_lake_morning())
    if not instruction.person_is_absent_for_range(
        LORENZO.full_name, day, "15:00", "16:30"
    ):
        day_schedule.lake_afternoon.append(_lorenzo_lake_afternoon())


def _assign_forced_coverage(
    day_schedule: DaySchedule,
    instruction: WeeklyInstruction,
    wife_codes: dict[str, str],
    week_dates: dict[str, str],
) -> None:
    for request in [
        *instruction.forced_shop_coverage,
        *instruction.forced_lake_coverage,
    ]:
        if request.day != day_schedule.day:
            continue
        if not _is_range_required(
            day_schedule, request.activity, request.start, request.end
        ):
            day_schedule.warnings.append(
                f"Copertura richiesta per {request.person} su {request.label} non applicata: attività chiusa o fascia non aperta."
            )
            continue
        if _person_covers_range(
            day_schedule, request.person, request.activity, request.start, request.end
        ):
            day_schedule.notes.append(
                f"{request.person} già su {request.label} per istruzione settimanale"
            )
            continue
        if not _can_assign_person(
            day_schedule,
            request.person,
            request.activity,
            request.start,
            request.end,
            instruction,
            wife_codes,
            week_dates,
        ):
            day_schedule.warnings.append(
                f"Copertura richiesta impossibile: {request.person} non può coprire {request.label} "
                f"{request.start}-{request.end}."
            )
            continue
        _append_assignment(
            day_schedule,
            _assignment(request.person, request.activity, request.start, request.end),
        )
        day_schedule.notes.append(
            f"{request.person} assegnato a {request.label} per istruzione settimanale"
        )


def _assign_default_angelo_shop(
    day_schedule: DaySchedule,
    instruction: WeeklyInstruction,
) -> None:
    day = day_schedule.day
    if (
        not day_schedule.shop_required_ranges
        or day in instruction.unavailable_days_for(ANGELO.full_name)
    ):
        return

    if any(
        request.day == day and request.person == GIAMMARCO.full_name
        for request in instruction.forced_shop_coverage
    ):
        return

    for start, end in day_schedule.shop_required_ranges:
        if not instruction.person_is_absent_for_range(
            ANGELO.full_name, day, start, end
        ):
            _append_if_no_person_conflict(
                day_schedule, ANGELO.full_name, ActivityId.SHOP, start, end
            )


def _fill_required_coverage(
    day_schedule: DaySchedule,
    instruction: WeeklyInstruction,
    wife_codes: dict[str, str],
    week_dates: dict[str, str],
) -> None:
    day = day_schedule.day

    # Angelo può normalmente gestire il negozio da solo. Se però non c'è in un
    # giorno di apertura, Giammarco deve prima coprire il presidio negozio.
    if day_schedule.shop_required_ranges and day in instruction.unavailable_days_for(
        ANGELO.full_name
    ):
        _fill_shop_coverage(day_schedule, instruction, wife_codes, week_dates)
        _fill_lake_coverage(day_schedule, instruction, wife_codes, week_dates)
        return

    # Priorità operativa: quando Giammarco serve come copertura, lo usiamo prima
    # sul lago; il negozio resta ad Angelo salvo richiesta esplicita o buco.
    _fill_lake_coverage(day_schedule, instruction, wife_codes, week_dates)
    _fill_shop_coverage(day_schedule, instruction, wife_codes, week_dates)


def _fill_lake_coverage(
    day_schedule: DaySchedule,
    instruction: WeeklyInstruction,
    wife_codes: dict[str, str],
    week_dates: dict[str, str],
) -> None:
    if not day_schedule.lake_required_ranges:
        return
    _fill_activity_ranges(
        day_schedule,
        ActivityId.LAKE,
        day_schedule.lake_required_ranges,
        (GIAMMARCO.full_name, ANGELO.full_name),
        instruction,
        wife_codes,
        week_dates,
    )


def _fill_shop_coverage(
    day_schedule: DaySchedule,
    instruction: WeeklyInstruction,
    wife_codes: dict[str, str],
    week_dates: dict[str, str],
) -> None:
    if not day_schedule.shop_required_ranges:
        return
    _fill_activity_ranges(
        day_schedule,
        ActivityId.SHOP,
        day_schedule.shop_required_ranges,
        (ANGELO.full_name, GIAMMARCO.full_name),
        instruction,
        wife_codes,
        week_dates,
    )


def _fill_activity_ranges(
    day_schedule: DaySchedule,
    activity: ActivityId,
    required_ranges: Iterable[tuple[str, str]],
    candidate_people: tuple[str, ...],
    instruction: WeeklyInstruction,
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
                instruction,
                wife_codes,
                week_dates,
            )


def _assign_first_available(
    day_schedule: DaySchedule,
    activity: ActivityId,
    start: str,
    end: str,
    candidate_people: tuple[str, ...],
    instruction: WeeklyInstruction,
    wife_codes: dict[str, str],
    week_dates: dict[str, str],
) -> None:
    giammarco_conflict = _conflicting_interval(
        day_schedule, GIAMMARCO.full_name, start, end
    )
    if (
        activity == ActivityId.LAKE
        and GIAMMARCO.full_name in candidate_people
        and giammarco_conflict is not None
        and giammarco_conflict[0] <= _to_minutes(start)
        and giammarco_conflict[1] < _to_minutes(end)
    ):
        split = _to_label(giammarco_conflict[1])
        fallback_people = tuple(
            person for person in candidate_people if person != GIAMMARCO.full_name
        )
        _assign_first_available(
            day_schedule,
            activity,
            start,
            split,
            fallback_people,
            instruction,
            wife_codes,
            week_dates,
        )
        _assign_first_available(
            day_schedule,
            activity,
            split,
            end,
            candidate_people,
            instruction,
            wife_codes,
            week_dates,
        )
        return

    for person in candidate_people:
        if instruction.person_is_absent_for_range(person, day_schedule.day, start, end):
            continue
        if not _can_assign_person(
            day_schedule,
            person,
            activity,
            start,
            end,
            instruction,
            wife_codes,
            week_dates,
        ):
            continue
        _append_assignment(day_schedule, _assignment(person, activity, start, end))
        return


def _can_assign_person(
    day_schedule: DaySchedule,
    person: str,
    activity: ActivityId,
    start: str,
    end: str,
    instruction: WeeklyInstruction,
    wife_codes: dict[str, str],
    week_dates: dict[str, str],
) -> bool:
    if instruction.person_is_absent_for_range(person, day_schedule.day, start, end):
        return False
    if _person_has_conflict(day_schedule, person, start, end):
        return False
    if (
        person == GIAMMARCO.full_name
        and activity == ActivityId.LAKE
        and start == "07:30"
    ):
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
        warning = f"Calendario moglie {date_key}: codice M, quindi Giammarco non può aprire il lago alle 07:30."
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
    if _can_assign_person(
        day_schedule,
        person,
        ActivityId.LAKE,
        "07:30",
        "14:00",
        WeeklyInstruction(),
        wife_codes,
        week_dates,
    ):
        _append_assignment(
            day_schedule, _assignment(person, ActivityId.LAKE, "07:30", "14:00")
        )
    if _can_assign_person(
        day_schedule,
        person,
        ActivityId.LAKE,
        "14:00",
        "18:30",
        WeeklyInstruction(),
        wife_codes,
        week_dates,
    ):
        _append_assignment(
            day_schedule, _assignment(person, ActivityId.LAKE, "14:00", "18:30")
        )


def _append_shop_full_day(day_schedule: DaySchedule, person: str) -> None:
    _append_if_no_person_conflict(day_schedule, person, ActivityId.SHOP, *SHOP_MORNING)
    _append_if_no_person_conflict(
        day_schedule, person, ActivityId.SHOP, *SHOP_AFTERNOON
    )


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
    return Assignment(
        person, activity, _period_for(start), start, end, _hours_between(start, end)
    )


def _apply_notes(
    day_schedule: DaySchedule,
    instruction: WeeklyInstruction,
    wife_codes: dict[str, str],
    week_dates: dict[str, str],
) -> None:
    for note in instruction.day_notes.get(day_schedule.day, []):
        day_schedule.notes.append(note)

    if day_schedule.day in instruction.lorenzo_must_open_lake_days:
        day_schedule.notes.append("Lorenzo apre il lago per istruzione settimanale")

    if day_schedule.day in instruction.high_lake_booking_days:
        day_schedule.notes.append(
            "Molte prenotazioni al lago: consigliata attenzione extra"
        )

    explicit_extra = [
        request
        for request in instruction.extra_lake_coverage
        if request.day == day_schedule.day
    ]
    if not explicit_extra and day_schedule.day in instruction.high_lake_booking_days:
        explicit_extra = [
            CoverageRequest(
                day_schedule.day,
                GIAMMARCO.full_name,
                ActivityId.LAKE,
                "07:30",
                "14:00",
                "copertura extra lago",
            )
        ]

    for request in explicit_extra:
        if _person_covers_range(
            day_schedule, request.person, request.activity, request.start, request.end
        ):
            continue
        if _can_assign_person(
            day_schedule,
            request.person,
            request.activity,
            request.start,
            request.end,
            instruction,
            wife_codes,
            week_dates,
        ):
            _append_assignment(
                day_schedule,
                _assignment(
                    request.person, request.activity, request.start, request.end
                ),
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


def _assignments_for_activity(
    day_schedule: DaySchedule, activity: ActivityId
) -> list[Assignment]:
    return [
        assignment
        for assignment in day_schedule.assignments()
        if assignment.activity == activity
    ]


def _person_covers_range(
    day_schedule: DaySchedule, person: str, activity: ActivityId, start: str, end: str
) -> bool:
    return any(
        assignment.person == person
        and assignment.activity == activity
        and _to_minutes(assignment.start) <= _to_minutes(start)
        and _to_minutes(end) <= _to_minutes(assignment.end)
        for assignment in day_schedule.assignments()
    )


def _person_has_conflict(
    day_schedule: DaySchedule, person: str, start: str, end: str
) -> bool:
    return _conflicting_interval(day_schedule, person, start, end) is not None


def _conflicting_interval(
    day_schedule: DaySchedule, person: str, start: str, end: str
) -> tuple[int, int] | None:
    start_minutes = _to_minutes(start)
    end_minutes = _to_minutes(end)
    for assignment in sorted(
        day_schedule.assignments(), key=lambda item: _to_minutes(item.start)
    ):
        if assignment.person != person:
            continue
        assignment_start = _to_minutes(assignment.start)
        assignment_end = _to_minutes(assignment.end)
        if start_minutes < assignment_end and assignment_start < end_minutes:
            return assignment_start, assignment_end
    return None


def _missing_ranges(
    assignments: list[Assignment], required_start: int, required_end: int
) -> list[tuple[int, int]]:
    intervals = sorted(
        (_to_minutes(assignment.start), _to_minutes(assignment.end))
        for assignment in assignments
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
