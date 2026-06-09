"""Generazione dell'orario settimanale."""

from __future__ import annotations

from .business_rules import ActivityId, CARPEEVOLUTION_STORE, TENUTA_DEL_GERMANO, WEEK_DAYS
from .models import Assignment, DaySchedule, WeeklySchedule
from .people import ANGELO, GIANMARCO, LORENZO
from .validator import validate_schedule
from .weekly_input import WeeklyInstruction, parse_weekly_instruction


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
    """Determina i 5 giorni di Lorenzo, preservando 40 ore settimanali."""

    working_days = set(LORENZO.ideal_working_days)
    for day in instruction.lorenzo_must_open_lake_days:
        if day in TENUTA_DEL_GERMANO.open_days:
            working_days.add(day)

    # Se un'istruzione aggiunge il martedì, togliamo il primo giorno ideale non
    # imposto dall'utente. Così Lorenzo resta su 5 giorni da 8 ore.
    removable_days = [
        day
        for day in LORENZO.ideal_working_days
        if day not in instruction.lorenzo_must_open_lake_days
    ]
    while len(working_days) > (LORENZO.strict_working_days or 5) and removable_days:
        working_days.remove(removable_days.pop(0))

    return working_days


def _build_day(day: str, lorenzo_days: set[str], instruction: WeeklyInstruction) -> DaySchedule:
    day_schedule = DaySchedule(day=day)

    _assign_lake(day_schedule, lorenzo_days, instruction)
    _assign_shop(day_schedule, instruction)
    _apply_notes(day_schedule, instruction)

    return day_schedule


def _assign_lake(day_schedule: DaySchedule, lorenzo_days: set[str], instruction: WeeklyInstruction) -> None:
    day = day_schedule.day
    if day in TENUTA_DEL_GERMANO.closed_days:
        day_schedule.notes.append("Lago chiuso")
        return

    if day in lorenzo_days:
        day_schedule.lake_morning.append(_lorenzo_lake_morning())
        day_schedule.lake_afternoon.append(_lorenzo_lake_afternoon())
        _assign_gianmarco_lake_closing_if_available(day_schedule, instruction)
        return

    # Giorni aperti senza Lorenzo: Gianmarco copre il lago come jolly.
    day_schedule.lake_morning.append(
        Assignment(GIANMARCO.full_name, ActivityId.LAKE, "morning", "07:30", "14:00", 6.5)
    )
    day_schedule.lake_afternoon.append(
        Assignment(GIANMARCO.full_name, ActivityId.LAKE, "afternoon", "14:00", "18:30", 4.5)
    )


def _assign_gianmarco_lake_closing_if_available(
    day_schedule: DaySchedule,
    instruction: WeeklyInstruction,
) -> None:
    """Copre la chiusura lago quando Lorenzo termina alle 16:30."""

    day_schedule.lake_afternoon.append(
        Assignment(GIANMARCO.full_name, ActivityId.LAKE, "afternoon", "14:00", "15:00", 1.0)
    )

    if day_schedule.day in instruction.gianmarco_shop_days:
        day_schedule.notes.append(
            "Gianmarco richiesto in negozio: verificare copertura lago dopo le 16:30"
        )
        return

    day_schedule.lake_afternoon.append(
        Assignment(GIANMARCO.full_name, ActivityId.LAKE, "afternoon", "16:30", "18:30", 2.0)
    )


def _assign_shop(day_schedule: DaySchedule, instruction: WeeklyInstruction) -> None:
    day = day_schedule.day
    if day in CARPEEVOLUTION_STORE.closed_days:
        day_schedule.notes.append("Negozio chiuso")
        return

    day_schedule.shop_morning.append(
        Assignment(ANGELO.full_name, ActivityId.SHOP, "morning", "09:00", "12:30", 3.5)
    )
    day_schedule.shop_afternoon.append(
        Assignment(ANGELO.full_name, ActivityId.SHOP, "afternoon", "15:30", "19:30", 4.0)
    )

    if day in instruction.gianmarco_shop_days:
        day_schedule.shop_morning.append(
            Assignment(GIANMARCO.full_name, ActivityId.SHOP, "morning", "09:00", "12:30", 3.5)
        )
        day_schedule.shop_afternoon.append(
            Assignment(GIANMARCO.full_name, ActivityId.SHOP, "afternoon", "15:30", "19:30", 4.0)
        )
        day_schedule.notes.append("Gianmarco in negozio per istruzione settimanale")


def _apply_notes(day_schedule: DaySchedule, instruction: WeeklyInstruction) -> None:
    if day_schedule.day in instruction.lorenzo_must_open_lake_days:
        day_schedule.notes.append("Lorenzo apre il lago per istruzione settimanale")

    if day_schedule.day in instruction.high_lake_booking_days:
        day_schedule.notes.append("Molte prenotazioni al lago: consigliata attenzione extra")
        if day_schedule.day not in instruction.gianmarco_shop_days:
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
