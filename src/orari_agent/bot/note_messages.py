"""Messaggi Telegram per il salvataggio delle note."""

from __future__ import annotations

from html import escape

from orari_agent.business_rules import ActivityId
from orari_agent.weekly_input import parse_weekly_instruction


def saved_note_message(note) -> str:
    """Costruisce la risposta Telegram con metadati e sintesi interpretata."""

    pieces = [
        f"Nota salvata con ID <b>{note.id}</b>.",
        f"Settimana: {escape(note.target_week_start)} - {escape(note.target_week_end)}.",
    ]
    if note.interpreted_date:
        pieces.append(f"Data interpretata: {escape(note.interpreted_date)}.")
    if note.person:
        pieces.append(f"Persona: {escape(note.person)}.")
    if note.location:
        pieces.append(f"Luogo: {escape(note.location)}.")
    if note.constraint_type:
        pieces.append(f"Tipo vincolo: {escape(note.constraint_type)}.")
    summary = interpretation_summary(note.raw_text)
    if summary:
        pieces.append(f"Interpretazione: {escape(summary)}")
    else:
        pieces.append(
            "Nota salvata, ma non sono riuscito a trasformarla in un vincolo automatico. "
            "Verrà mostrata come nota nel PDF."
        )
    return "\n".join(pieces)


def interpretation_summary(text: str) -> str | None:
    """Restituisce una sintesi breve del vincolo automatico riconosciuto."""

    instruction = parse_weekly_instruction(text)
    if instruction.unknown_notes and not any(
        (
            instruction.unavailable_by_person,
            instruction.morning_absence_by_person,
            instruction.afternoon_absence_by_person,
            instruction.unavailable_ranges_by_person,
            instruction.giammarco_external_work,
            instruction.forced_shop_coverage,
            instruction.forced_lake_coverage,
            instruction.high_lake_booking_days,
            instruction.extra_lake_coverage,
            instruction.exceptional_closures,
            instruction.exceptional_openings,
        )
    ):
        return None

    summaries: list[str] = []
    for person, days in instruction.unavailable_by_person.items():
        summaries.append(f"{person} assente tutto il giorno: {', '.join(sorted(days))}.")
    for person, days in instruction.morning_absence_by_person.items():
        summaries.append(f"{person} assente la mattina: {', '.join(sorted(days))}.")
    for person, days in instruction.afternoon_absence_by_person.items():
        summaries.append(f"{person} assente il pomeriggio: {', '.join(sorted(days))}.")
    for absences in instruction.unavailable_ranges_by_person.values():
        for absence in absences:
            summaries.append(
                f"{absence.person} non disponibile {absence.day} {absence.start}-{absence.end}."
            )
    for work in instruction.giammarco_external_work:
        summaries.append(
            f"Giammarco in lavoro esterno ({work.label}) {work.day} {work.start}-{work.end}."
        )
    for coverage in [
        *instruction.forced_shop_coverage,
        *instruction.forced_lake_coverage,
    ]:
        luogo = _activity_place_label(coverage.activity)
        summaries.append(
            f"{coverage.person} forzato su {luogo} {coverage.day} {coverage.start}-{coverage.end}."
        )
    for day in sorted(instruction.high_lake_booking_days):
        summaries.append(f"Carico alto al lago {day}: consigliata copertura extra.")
    for closure in instruction.exceptional_closures:
        luogo = _activity_place_label(closure.activity)
        summaries.append(f"Chiusura eccezionale {luogo} {closure.day}.")
    for opening in instruction.exceptional_openings:
        luogo = _activity_place_label(opening.activity)
        summaries.append(f"Apertura eccezionale {luogo} {opening.day}.")
    return " ".join(summaries[:3]) if summaries else None


def _activity_place_label(activity: ActivityId) -> str:
    if activity == ActivityId.SHOP:
        return "negozio"
    if activity == ActivityId.LAKE:
        return "lago"
    return activity.value
