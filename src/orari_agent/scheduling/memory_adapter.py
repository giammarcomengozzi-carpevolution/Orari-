"""Converte la memoria operativa persistente in WeeklyInstruction."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from orari_agent.business_rules import WEEK_DAYS
from orari_agent.people import GIAMMARCO
from orari_agent.storage.operational_memory_repository import OperationalMemory
from orari_agent.weekly_input import (
    AFTERNOON,
    FULL_DAY,
    MORNING,
    ExternalWorkRequest,
    TimeRangeUnavailability,
    WeeklyInstruction,
)

RULE_WEEKDAY_TO_DAY = {
    "MONDAY": "Lunedì",
    "TUESDAY": "Martedì",
    "WEDNESDAY": "Mercoledì",
    "THURSDAY": "Giovedì",
    "FRIDAY": "Venerdì",
    "SATURDAY": "Sabato",
    "SUNDAY": "Domenica",
}
RULE_PERIOD_TO_PERIOD = {
    "MORNING": MORNING,
    "AFTERNOON": AFTERNOON,
    "FULL_DAY": FULL_DAY,
}


def memories_to_weekly_instruction(
    memories: list[OperationalMemory], week_start: str, week_end: str
) -> WeeklyInstruction:
    """Crea vincoli settimanali dalle memorie attive rilevanti."""

    instruction = WeeklyInstruction(raw_text="memoria operativa persistente")
    start = _parse_date(week_start)
    end = _parse_date(week_end)
    date_by_day = {
        WEEK_DAYS[index]: start + timedelta(days=index) for index in range(7)
    }
    for memory in memories:
        applied = False
        if memory.recurrence_rule:
            applied = _apply_recurring(memory, instruction)
        elif memory.start_date:
            applied = _apply_dated(memory, instruction, start, end, date_by_day)
        else:
            instruction.unknown_notes.append(f"Memoria {memory.id}: {memory.raw_text}")
            applied = True
        if applied:
            instruction.weekly_notes.append(_memory_note(memory))
    return instruction


def merge_weekly_instructions(*instructions: WeeklyInstruction) -> WeeklyInstruction:
    """Unisce più WeeklyInstruction senza perdere note o vincoli."""

    merged = WeeklyInstruction(
        raw_text="\n".join(i.raw_text for i in instructions if i.raw_text)
    )
    for instruction in instructions:
        merged.lorenzo_must_open_lake_days.update(
            instruction.lorenzo_must_open_lake_days
        )
        merged.giammarco_shop_days.update(instruction.giammarco_shop_days)
        merged.giammarco_lake_days.update(instruction.giammarco_lake_days)
        if instruction.giammarco_requested_shop_day_count is not None:
            merged.giammarco_requested_shop_day_count = (
                instruction.giammarco_requested_shop_day_count
            )
        merged.giammarco_external_work.extend(instruction.giammarco_external_work)
        merged.high_lake_booking_days.update(instruction.high_lake_booking_days)
        _merge_dict_sets(
            merged.unavailable_by_person, instruction.unavailable_by_person
        )
        _merge_dict_sets(
            merged.morning_absence_by_person, instruction.morning_absence_by_person
        )
        _merge_dict_sets(
            merged.afternoon_absence_by_person,
            instruction.afternoon_absence_by_person,
        )
        for person, ranges in instruction.unavailable_ranges_by_person.items():
            merged.unavailable_ranges_by_person.setdefault(person, []).extend(ranges)
        merged.forced_shop_coverage.extend(instruction.forced_shop_coverage)
        merged.forced_lake_coverage.extend(instruction.forced_lake_coverage)
        merged.lake_opening_coverage.extend(instruction.lake_opening_coverage)
        merged.lake_closing_coverage.extend(instruction.lake_closing_coverage)
        merged.extra_lake_coverage_days.update(instruction.extra_lake_coverage_days)
        merged.extra_lake_coverage.extend(instruction.extra_lake_coverage)
        merged.exceptional_closures.extend(instruction.exceptional_closures)
        merged.exceptional_openings.extend(instruction.exceptional_openings)
        for day, notes in instruction.day_notes.items():
            merged.day_notes.setdefault(day, []).extend(notes)
        merged.weekly_notes.extend(instruction.weekly_notes)
        merged.unknown_notes.extend(instruction.unknown_notes)
    return merged


def _apply_recurring(memory: OperationalMemory, instruction: WeeklyInstruction) -> bool:
    parts = memory.recurrence_rule.split(":") if memory.recurrence_rule else []
    if len(parts) != 3 or parts[0] != "WEEKLY":
        instruction.unknown_notes.append(
            f"Memoria {memory.id} con ricorrenza non supportata: {memory.raw_text}"
        )
        return True
    day = RULE_WEEKDAY_TO_DAY.get(parts[1])
    period = RULE_PERIOD_TO_PERIOD.get(parts[2], FULL_DAY)
    if day is None or memory.person is None:
        instruction.unknown_notes.append(
            f"Memoria {memory.id} incompleta: {memory.raw_text}"
        )
        return True
    _apply_constraint_to_day(memory, instruction, day, period)
    return True


def _apply_dated(
    memory: OperationalMemory,
    instruction: WeeklyInstruction,
    start: date,
    end: date,
    date_by_day: dict[str, date],
) -> bool:
    memory_start = _parse_date(memory.start_date or "")
    memory_end = _parse_date(memory.end_date or memory.start_date or "")
    applied = False
    for day, current in date_by_day.items():
        if memory_start <= current <= memory_end:
            _apply_constraint_to_day(
                memory, instruction, day, _period_from_memory(memory)
            )
            applied = True
    return applied


def _apply_constraint_to_day(
    memory: OperationalMemory,
    instruction: WeeklyInstruction,
    day: str,
    period: str,
) -> None:
    if memory.person is None:
        instruction.unknown_notes.append(f"Memoria {memory.id}: {memory.raw_text}")
        return
    if (
        memory.constraint_type == "impegno_esterno"
        and memory.person == GIAMMARCO.full_name
    ):
        start, end = memory.start_time or "07:30", memory.end_time or "19:30"
        instruction.giammarco_external_work.append(
            ExternalWorkRequest(
                day, start, end, memory.location or "lavoro aziendale esterno"
            )
        )
        instruction.day_notes.setdefault(day, []).append(_memory_note(memory))
        return
    if period == MORNING:
        instruction.morning_absence_by_person.setdefault(memory.person, set()).add(day)
    elif period == AFTERNOON:
        instruction.afternoon_absence_by_person.setdefault(memory.person, set()).add(day)
    elif memory.start_time and memory.end_time:
        instruction.unavailable_ranges_by_person.setdefault(memory.person, []).append(
            TimeRangeUnavailability(
                day,
                memory.person,
                memory.start_time,
                memory.end_time,
                "memoria operativa",
            )
        )
    else:
        instruction.unavailable_by_person.setdefault(memory.person, set()).add(day)
    instruction.day_notes.setdefault(day, []).append(_memory_note(memory))


def _period_from_memory(memory: OperationalMemory) -> str:
    if memory.start_time == "07:30" and memory.end_time == "14:00":
        return MORNING
    if memory.start_time == "14:00" and memory.end_time == "19:30":
        return AFTERNOON
    return FULL_DAY


def _memory_note(memory: OperationalMemory) -> str:
    bits = [f"Memoria: {memory.raw_text} (ID {memory.id})"]
    if memory.start_time and memory.end_time:
        bits.append(f"{memory.start_time}-{memory.end_time}")
    return "; ".join(bits)


def _merge_dict_sets(target: dict[str, set[str]], source: dict[str, set[str]]) -> None:
    for key, values in source.items():
        target.setdefault(key, set()).update(values)


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()
