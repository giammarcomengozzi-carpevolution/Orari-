"""Formattazione dell'orario in italiano per utenti non tecnici."""

from __future__ import annotations

from .models import Assignment, DaySchedule, WeeklySchedule

HEADERS = [
    "Giorno",
    "Lago mattina",
    "Lago pomeriggio",
    "Negozio mattina",
    "Negozio pomeriggio",
    "Note / avvisi",
]


def format_schedule_italian(schedule: WeeklySchedule) -> str:
    """Restituisce una tabella Markdown con riepilogo dei controlli."""

    rows = [_row_for_day(day) for day in schedule.days]
    table = _markdown_table(HEADERS, rows)

    result = [
        "# Orario settimanale proposto",
        "",
        table,
        "",
        "## Controlli automatici",
    ]

    all_warnings = [*schedule.global_warnings]
    for day in schedule.days:
        all_warnings.extend(f"{day.day}: {warning}" for warning in day.warnings)

    if all_warnings:
        result.extend(f"- ⚠️ {warning}" for warning in all_warnings)
    else:
        result.append("- ✅ Nessun conflitto o violazione rilevata.")

    result.extend(
        [
            "",
            "## Legenda rapida",
            "- La pausa 14:00-15:00 di Lorenzo non viene conteggiata come lavoro.",
            "- Angelo copre di default il negozio negli orari di apertura.",
            "- Giammarco è general manager / CEO: lavora sempre per l’azienda, ma viene contato come copertura fissa solo quando è assegnato a lago o negozio.",
        ]
    )
    return "\n".join(result)


def _row_for_day(day: DaySchedule) -> list[str]:
    notes_and_warnings = [*day.notes, *[f"⚠️ {warning}" for warning in day.warnings]]
    return [
        day.day,
        _format_assignments(day.lake_morning),
        _format_assignments(day.lake_afternoon),
        _format_assignments(day.shop_morning),
        _format_assignments(day.shop_afternoon),
        "<br>".join(notes_and_warnings) if notes_and_warnings else "—",
    ]


def _format_assignments(assignments: list[Assignment]) -> str:
    if not assignments:
        return "—"
    return "<br>".join(assignment.label() for assignment in assignments)


def _markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    output = ["| " + " | ".join(headers) + " |"]
    output.append("| " + " | ".join("---" for _ in headers) + " |")
    for row in rows:
        output.append("| " + " | ".join(_escape_cell(cell) for cell in row) + " |")
    return "\n".join(output)


def _escape_cell(value: str) -> str:
    return value.replace("|", "\\|")
