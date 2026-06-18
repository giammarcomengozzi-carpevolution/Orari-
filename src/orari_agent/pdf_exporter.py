"""Esportazione PDF dell'orario settimanale.

Il modulo resta separato dal motore di scheduling: riceve un ``WeeklySchedule``
già generato e produce un PDF A4 verticale pronto per la condivisione manuale.
"""

from __future__ import annotations

import textwrap
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable, Sequence

from .models import WeeklySchedule
from .generator import lake_opening_label, shop_opening_label
from .presentation import (
    EffectiveShift,
    OperationalDayView,
    OperationalShiftRow,
    critical_conflicts,
    display_person,
    effective_shifts,
    format_duration,
    informational_alerts,
    lorenzo_target_status,
    operational_day_views,
    weekly_hour_totals,
)
from .people import ANGELO, GIAMMARCO, LORENZO

PDF_TITLE = "Orario settimanale"
PDF_SUBTITLE = "CarpeEvolution Store & Tenuta del Germano"
DEFAULT_FILENAME_PREFIX = "Orario_CarpeEvolution_Tenuta"

# A4 portrait in PostScript points.
PAGE_WIDTH = 595.28
PAGE_HEIGHT = 841.89
MARGIN = 18.0
TABLE_WIDTH = PAGE_WIDTH - (MARGIN * 2)

COLUMN_SPECS = [
    ("Giorno", 58.0),
    ("Data", 66.0),
    ("Persona", 128.0),
    ("Sede", 74.0),
    ("Orario", 126.0),
    ("Pausa", 88.0),
    ("Compito", 132.0),
    ("Note", TABLE_WIDTH - 58.0 - 66.0 - 128.0 - 74.0 - 126.0 - 88.0 - 132.0),
]


@dataclass(frozen=True)
class _Cell:
    text: str
    font_size: float = 7.4


def export_weekly_schedule_pdf(
    schedule: WeeklySchedule,
    output_path: str | Path | None = None,
    *,
    week_start_date: str | date | None = None,
    weekly_notes: Iterable[str] | None = None,
    operational_memories: Iterable[str] | None = None,
) -> Path:
    """Genera il PDF settimanale e restituisce il percorso del file creato.

    Se ``output_path`` è una directory, viene creato al suo interno un file con
    nome standard ``Orario_CarpeEvolution_Tenuta_YYYY-MM-DD.pdf``. Se è un file
    ``.pdf``, quel percorso viene usato direttamente.
    """

    resolved_week_start = _resolve_week_start(schedule, week_start_date)
    destination = _resolve_output_path(output_path, resolved_week_start)
    destination.parent.mkdir(parents=True, exist_ok=True)

    content_streams = _build_pdf_pages(
        schedule,
        resolved_week_start,
        weekly_notes=weekly_notes,
        operational_memories=operational_memories,
    )
    _write_pdf(destination, content_streams)
    return destination


def default_pdf_filename(week_start_date: str | date | None = None) -> str:
    """Restituisce il nome file standard per un'esportazione PDF."""

    if isinstance(week_start_date, date):
        date_part = week_start_date.isoformat()
    elif week_start_date:
        date_part = week_start_date
    else:
        date_part = date.today().isoformat()
    return f"{DEFAULT_FILENAME_PREFIX}_{date_part}.pdf"


def _resolve_week_start(
    schedule: WeeklySchedule, week_start_date: str | date | None
) -> str | None:
    if isinstance(week_start_date, date):
        return week_start_date.isoformat()
    if week_start_date:
        return week_start_date
    return schedule.week_start_date


def _resolve_output_path(
    output_path: str | Path | None, week_start_date: str | None
) -> Path:
    filename = default_pdf_filename(week_start_date)
    if output_path is None:
        return Path.cwd() / filename

    path = Path(output_path)
    if path.suffix.lower() == ".pdf":
        return path
    return path / filename


def _build_pdf_pages(
    schedule: WeeklySchedule,
    week_start_date: str | None,
    *,
    weekly_notes: Iterable[str] | None,
    operational_memories: Iterable[str] | None,
) -> list[bytes]:
    notes = _compact_items(
        weekly_notes if weekly_notes is not None else schedule.global_notes
    )
    memories = _compact_items(operational_memories)
    conflicts = critical_conflicts(schedule)
    alerts = informational_alerts(schedule)
    totals = weekly_hour_totals(schedule)
    day_views = operational_day_views(schedule)

    pages: list[bytes] = []
    day_index = 0
    page_number = 1
    summary_drawn = False

    while day_index < len(day_views):
        commands: list[str] = []
        _draw_header(commands, week_start_date, compact=page_number > 1)
        if page_number > 1:
            _add_text(
                commands,
                MARGIN,
                PAGE_HEIGHT - 92,
                "Turni operativi - continuazione",
                9.0,
                bold=True,
                color=(0.05, 0.20, 0.12),
            )
        top_y = PAGE_HEIGHT - (70 if page_number == 1 else 76)
        summary_bottom_y = 154.0
        page_bottom_y = 34.0

        end_with_summary = _fit_day_end(day_views, day_index, top_y, summary_bottom_y)
        if end_with_summary == len(day_views):
            y = _draw_day_cards(
                commands, day_views[day_index:end_with_summary], top_y, summary_bottom_y
            )
            y = _draw_weekly_totals(commands, y - 8, totals)
            _draw_summary_sections(commands, y - 8, notes, conflicts, memories, alerts)
            summary_drawn = True
            day_index = end_with_summary
        else:
            end = _fit_day_end(day_views, day_index, top_y, page_bottom_y)
            if end == day_index:
                end = min(day_index + 1, len(day_views))
            _draw_day_cards(commands, day_views[day_index:end], top_y, page_bottom_y)
            day_index = end

        _draw_footer(commands, page_number)
        pages.append("\n".join(commands).encode("latin-1", errors="replace"))
        page_number += 1

    if not day_views or not summary_drawn:
        commands = []
        _draw_header(commands, week_start_date, compact=bool(pages))
        y = PAGE_HEIGHT - 70
        y = _draw_weekly_totals(commands, y, totals)
        _draw_summary_sections(commands, y - 8, notes, conflicts, memories, alerts)
        _draw_footer(commands, page_number)
        pages.append("\n".join(commands).encode("latin-1", errors="replace"))
        page_number += 1

    if _needs_detail_page(notes, conflicts + alerts, memories):
        detail: list[str] = []
        _draw_header(detail, week_start_date, compact=True)
        _draw_detail_page(detail, notes, conflicts + alerts, memories)
        _draw_footer(detail, page_number)
        pages.append("\n".join(detail).encode("latin-1", errors="replace"))
    return pages


def _draw_header(
    commands: list[str], week_start_date: str | None, *, compact: bool = False
) -> None:
    top = PAGE_HEIGHT - 22
    header_height = 48 if not compact else 42
    _draw_filled_rect(commands, 0, PAGE_HEIGHT - header_height, PAGE_WIDTH, header_height, 0.05, 0.20, 0.12)
    _add_text(
        commands,
        MARGIN,
        top,
        PDF_TITLE,
        13 if not compact else 11,
        bold=True,
        color=(1, 1, 1),
    )
    _add_text(
        commands,
        MARGIN,
        top - 14,
        PDF_SUBTITLE,
        7.8,
        bold=True,
        color=(0.88, 0.95, 0.90),
    )
    week = _week_label(week_start_date)
    if week:
        _add_text(
            commands,
            MARGIN,
            top - 28,
            week,
            7.6,
            bold=True,
            color=(1, 1, 1),
        )


def _draw_footer(commands: list[str], page_number: int) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    footer = f"Generato il {timestamp} - Pagina {page_number}"
    _add_text(commands, MARGIN, 16, footer, 6.2, color=(0.25, 0.25, 0.25))


def _collect_warning_texts(schedule: WeeklySchedule) -> list[str]:
    warnings = list(schedule.global_warnings)
    for day in schedule.days:
        warnings.extend(f"{day.day}: {warning}" for warning in day.warnings)
    return warnings


def _compact_items(items: Iterable[str] | None) -> list[str]:
    return [
        _normalize_text(str(item)).strip()
        for item in (items or [])
        if str(item).strip()
    ]


def _needs_detail_page(
    notes: Sequence[str], warnings: Sequence[str], memories: Sequence[str]
) -> bool:
    total = len(notes) + len(warnings) + len(memories)
    return total > 9 or len(warnings) > 3 or len(notes) > 4 or len(memories) > 3


def _week_label(week_start_date: str | None) -> str | None:
    if not week_start_date:
        return None
    try:
        start = datetime.strptime(week_start_date, "%Y-%m-%d").date()
    except ValueError:
        return f"Settimana: {week_start_date}"
    end = start + timedelta(days=6)
    return f"Settimana: {start.isoformat()} / {end.isoformat()}"


def _date_for_row(week_start_date: str | None, index: int) -> str:
    if not week_start_date:
        return "-"
    try:
        start = datetime.strptime(week_start_date, "%Y-%m-%d").date()
    except ValueError:
        return "-"
    return (start + timedelta(days=index)).isoformat()


def _draw_day_cards(
    commands: list[str],
    days: list[OperationalDayView],
    top_y: float,
    bottom_y: float,
) -> float:
    y = top_y
    for day in days:
        height = _day_card_height(day)
        if y - height < bottom_y:
            break
        _draw_day_card(commands, day, y, height)
        y -= height + 8.0
    return y


def _fit_day_end(
    days: Sequence[OperationalDayView], start_index: int, top_y: float, bottom_y: float
) -> int:
    y = top_y
    index = start_index
    while index < len(days):
        height = _day_card_height(days[index])
        if y - height < bottom_y:
            break
        y -= height + 8.0
        index += 1
    return index


def _day_card_height(day: OperationalDayView) -> float:
    if not any(section.rows for section in day.location_sections):
        return 20.0
    row_count = sum(len(section.rows) for section in day.location_sections)
    visible_sections = sum(1 for section in day.location_sections if section.rows)
    return 17.0 + visible_sections * 13.0 + row_count * 8.2 + 4.0


def _draw_day_card(
    commands: list[str], day: OperationalDayView, top_y: float, height: float
) -> None:
    bottom_y = top_y - height
    title = f"{day.day.upper()} {_short_date(day.date)}"
    _draw_filled_rect(commands, MARGIN, top_y - 15, TABLE_WIDTH, 15, 0.14, 0.25, 0.39)
    _add_text(commands, MARGIN + 5, top_y - 10, title, 7.8, bold=True, color=(1, 1, 1))
    _add_text(
        commands,
        MARGIN + 98,
        top_y - 10,
        f"{lake_opening_label(day.day, day.date)}  |  {shop_opening_label(day.day)}",
        6.0,
        color=(0.88, 0.95, 0.90),
    )

    if not any(section.rows for section in day.location_sections):
        _add_text(commands, MARGIN + 5, top_y - 25, "Lago chiuso | Negozio chiuso", 6.8)
        return

    _draw_rect(commands, MARGIN, bottom_y, TABLE_WIDTH, height, stroke_gray=0.70)
    y = top_y - 25
    for section in day.location_sections:
        if not section.rows:
            continue
        _add_text(
            commands,
            MARGIN + 5,
            y,
            section.location,
            6.9,
            bold=True,
            color=(0.05, 0.20, 0.12),
        )
        _draw_day_row_header(commands, y)
        y -= 8.0
        for row in section.rows:
            _draw_day_shift_row(commands, row, y)
            y -= 8.2
        y -= 3.0


def _draw_day_row_header(commands: list[str], y: float) -> None:
    headers = [
        ("Persona", 0),
        ("Orario", 132),
        ("Pausa", 286),
        ("Compito", 372),
        ("Ore", 520),
    ]
    for label, offset in headers:
        _add_text(
            commands,
            MARGIN + 5 + offset,
            y,
            label,
            5.7,
            bold=True,
            color=(0.25, 0.25, 0.25),
        )


def _draw_day_shift_row(
    commands: list[str], row: OperationalShiftRow, y: float
) -> None:
    values = [
        (display_person(row.person), 0, 124, 6.4),
        (row.work_time, 132, 145, 6.3),
        (row.break_time, 286, 78, 6.1),
        (row.task, 372, 140, 6.1),
        (format_duration(row.daily_hours), 520, 34, 6.0),
    ]
    for text, offset, width, size in values:
        line = _wrap_cell(text, width, size)[0]
        _add_text(commands, MARGIN + 5 + offset, y, line, size)


def _short_date(value: str) -> str:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return value
    return parsed.strftime("%d/%m")


def _draw_table(
    commands: list[str],
    shifts: list[EffectiveShift],
    top_y: float,
    bottom_y: float,
) -> float:
    x_positions = [MARGIN]
    for _, width in COLUMN_SPECS[:-1]:
        x_positions.append(x_positions[-1] + width)

    header_height = 20.0
    _draw_filled_rect(
        commands,
        MARGIN,
        top_y - header_height,
        TABLE_WIDTH,
        header_height,
        0.14,
        0.25,
        0.39,
    )
    for x, (label, width) in zip(x_positions, COLUMN_SPECS, strict=True):
        _add_text(commands, x + 4, top_y - 13, label, 8.0, bold=True, color=(1, 1, 1))
        _draw_rect(commands, x, top_y - header_height, width, header_height)

    y = top_y - header_height
    for index, shift in enumerate(shifts):
        row = _row_for_shift(shift)
        wrapped_cells = [
            _wrap_cell(cell.text, width, cell.font_size)
            for cell, (_, width) in zip(row, COLUMN_SPECS, strict=True)
        ]
        row_height = _row_height_for_wrapped_cells(wrapped_cells)
        if y - row_height < bottom_y:
            break

        if index % 2 == 1:
            _draw_filled_rect(
                commands,
                MARGIN,
                y - row_height,
                TABLE_WIDTH,
                row_height,
                0.96,
                0.98,
                1.0,
            )

        for x, (cell, lines, (_, width)) in zip(
            x_positions, zip(row, wrapped_cells, COLUMN_SPECS, strict=True), strict=True
        ):
            _draw_rect(commands, x, y - row_height, width, row_height, stroke_gray=0.72)
            text_y = y - 10.5
            for line in lines[:3]:
                _add_text(
                    commands,
                    x + 4,
                    text_y,
                    line,
                    cell.font_size,
                    bold=cell.font_size >= 8.5,
                )
                text_y -= 7.2
        y -= row_height

    return y


def _fit_shift_end(
    shifts: Sequence[EffectiveShift], start_index: int, top_y: float, bottom_y: float
) -> int:
    y = top_y - 20.0
    index = start_index
    while index < len(shifts):
        row = _row_for_shift(shifts[index])
        wrapped_cells = [
            _wrap_cell(cell.text, width, cell.font_size)
            for cell, (_, width) in zip(row, COLUMN_SPECS, strict=True)
        ]
        row_height = _row_height_for_wrapped_cells(wrapped_cells)
        if y - row_height < bottom_y:
            break
        y -= row_height
        index += 1
    return index


def _row_height_for_wrapped_cells(wrapped_cells: Sequence[list[str]]) -> float:
    line_count = max(len(lines) for lines in wrapped_cells)
    return max(18.0, min(30.0, 7.5 + line_count * 7.2))


def _row_for_shift(shift: EffectiveShift) -> list[_Cell]:
    return [
        _Cell(shift.day, 7.8),
        _Cell(shift.date, 7.2),
        _Cell(display_person(shift.person), 7.2),
        _Cell(shift.location, 7.4),
        _Cell(shift.work_time, 7.3),
        _Cell(shift.break_time, 7.0),
        _Cell(shift.task, 7.0),
        _Cell(shift.notes or "-", 6.5),
    ]


def _wrap_cell(text: str, width: float, font_size: float) -> list[str]:
    normalized = _normalize_text(text)
    chars_per_line = max(8, int(width / (font_size * 0.46)))
    lines: list[str] = []
    for chunk in normalized.split("; "):
        for part in chunk.splitlines():
            wrapped = textwrap.wrap(
                part, width=chars_per_line, break_long_words=False
            ) or [""]
            lines.extend(wrapped)
    if len(lines) > 5:
        return [*lines[:4], "..."]
    return lines


def _draw_weekly_totals(
    commands: list[str], top_y: float, totals: dict[str, float]
) -> float:
    height = 45.0
    y = max(34.0, top_y - height)
    _draw_filled_rect(commands, MARGIN, y, TABLE_WIDTH, height, 0.94, 0.97, 0.94)
    _draw_rect(commands, MARGIN, y, TABLE_WIDTH, height, stroke_gray=0.65)
    _add_text(
        commands,
        MARGIN + 6,
        top_y - 12,
        "RIEPILOGO MONTE ORE",
        7.3,
        bold=True,
        color=(0.05, 0.20, 0.12),
    )
    x = MARGIN + 6
    y_text = top_y - 26
    people = [GIAMMARCO.full_name, ANGELO.full_name, LORENZO.full_name]
    for person in people:
        total = totals.get(person, 0.0)
        status = "Nessun target impostato"
        if person == LORENZO.full_name:
            status = lorenzo_target_status(total)
        _add_text(
            commands,
            x,
            y_text,
            f"{display_person(person)}   {format_duration(total)}   {status}",
            6.4,
        )
        y_text -= 8.0
    return y


def _draw_summary_sections(
    commands: list[str],
    top_y: float,
    notes: Sequence[str],
    warnings: Sequence[str],
    memories: Sequence[str],
    alerts: Sequence[str] | None = None,
) -> float:
    box_gap = 8.0
    box_width = (TABLE_WIDTH - box_gap) / 2
    height = max(48.0, min(64.0, top_y - 31.0))
    y = max(34.0, top_y - height)
    alert_lines = list(alerts or [])
    conflict_lines = (
        ["Nessun conflitto critico rilevato"]
        if not warnings
        else ["ATTENZIONE - conflitti critici"] + list(warnings)
    )
    if alert_lines:
        conflict_lines.extend(["Alert informativi", *alert_lines])
    note_lines = list(notes or ["Nessuna nota operativa specifica."])
    if memories:
        note_lines.extend([f"Memoria: {memory}" for memory in memories])
    summaries = [
        (
            "NOTE / ALERT",
            note_lines,
            (0.94, 0.97, 0.94),
            (0.05, 0.20, 0.12),
        ),
        (
            "CONFLITTI CRITICI",
            conflict_lines,
            (1.0, 0.94, 0.84) if warnings else (0.94, 0.97, 0.94),
            (0.70, 0.18, 0.02) if warnings else (0.05, 0.20, 0.12),
        ),
    ]
    for index, (title, items, fill, title_color) in enumerate(summaries):
        x = MARGIN + index * (box_width + box_gap)
        _draw_filled_rect(commands, x, y, box_width, height, *fill)
        _draw_rect(commands, x, y, box_width, height, stroke_gray=0.65)
        _add_text(commands, x + 5, top_y - 11, title, 7.0, bold=True, color=title_color)
        text_y = top_y - 23
        preview_lines = _section_preview_lines(items, box_width)
        for line in preview_lines[:4]:
            _add_text(commands, x + 5, text_y, "- " + line, 6.0, color=(0.10, 0.10, 0.10))
            text_y -= 7.4
    return y


def _section_preview_lines(items: Sequence[str], box_width: float) -> list[str]:
    lines: list[str] = []
    width = max(22, int(box_width / 3.7))
    for item in items:
        lines.extend(
            textwrap.wrap(_normalize_text(item), width=width, break_long_words=False)
            or [""]
        )
    if len(lines) > 5:
        return [*lines[:4], "Dettagli a pagina 2..."]
    return lines


def _draw_detail_page(
    commands: list[str],
    notes: Sequence[str],
    warnings: Sequence[str],
    memories: Sequence[str],
) -> None:
    y = PAGE_HEIGHT - 102
    y = _draw_detail_section(
        commands, "Note operative", notes or ["Nessuna nota operativa specifica."], y
    )
    y = _draw_detail_section(
        commands,
        "Conflitti critici / alert informativi",
        warnings or ["Nessun conflitto critico rilevato"],
        y - 10,
        warning=bool(warnings),
    )
    y = _draw_detail_section(
        commands,
        "Memorie operative applicate",
        memories or ["Nessuna memoria operativa applicata."],
        y - 10,
    )


def _draw_detail_section(
    commands: list[str],
    title: str,
    items: Sequence[str],
    top_y: float,
    *,
    warning: bool = False,
) -> float:
    _add_text(
        commands,
        MARGIN,
        top_y,
        title,
        10,
        bold=True,
        color=(0.70, 0.18, 0.02) if warning else (0.05, 0.20, 0.12),
    )
    y = top_y - 15
    for item in items:
        wrapped = textwrap.wrap(
            _normalize_text(item), width=150, break_long_words=False
        ) or [""]
        for index, line in enumerate(wrapped[:3]):
            prefix = "• " if index == 0 else "  "
            _add_text(commands, MARGIN + 8, y, prefix + line, 7.5)
            y -= 9.0
        if y < 48:
            _add_text(
                commands,
                MARGIN + 8,
                y,
                "• Altri dettagli omessi per mantenere il PDF compatto.",
                7.5,
            )
            return y - 9
    return y


def _draw_warning_box(
    commands: list[str], title: str, warnings: Iterable[str], top_y: float
) -> None:
    lines = [title]
    for warning in warnings:
        lines.extend(
            textwrap.wrap(_normalize_text(warning), width=128, break_long_words=False)
        )
    height = min(68.0, 12.0 + len(lines) * 8.5)
    bottom_y = max(34.0, top_y - height)
    height = top_y - bottom_y
    _draw_filled_rect(commands, MARGIN, bottom_y, TABLE_WIDTH, height, 1.0, 0.96, 0.86)
    _draw_rect(commands, MARGIN, bottom_y, TABLE_WIDTH, height, stroke_gray=0.55)
    text_y = top_y - 11
    for index, line in enumerate(lines[:7]):
        _add_text(
            commands,
            MARGIN + 6,
            text_y,
            line,
            7.4,
            bold=index == 0,
            color=(0.45, 0.12, 0.0),
        )
        text_y -= 8.5


def _add_text(
    commands: list[str],
    x: float,
    y: float,
    text: str,
    size: float,
    *,
    bold: bool = False,
    color: tuple[float, float, float] = (0, 0, 0),
) -> None:
    font = "F2" if bold else "F1"
    r, g, b = color
    commands.append(
        f"BT /{font} {size:.2f} Tf {r:.3f} {g:.3f} {b:.3f} rg {x:.2f} {y:.2f} Td ({_pdf_escape(_normalize_text(text))}) Tj ET"
    )


def _draw_rect(
    commands: list[str],
    x: float,
    y: float,
    width: float,
    height: float,
    *,
    stroke_gray: float = 0.45,
) -> None:
    commands.append(
        f"{stroke_gray:.3f} G {x:.2f} {y:.2f} {width:.2f} {height:.2f} re S"
    )


def _draw_filled_rect(
    commands: list[str],
    x: float,
    y: float,
    width: float,
    height: float,
    r: float,
    g: float,
    b: float,
) -> None:
    commands.append(
        f"{r:.3f} {g:.3f} {b:.3f} rg {x:.2f} {y:.2f} {width:.2f} {height:.2f} re f"
    )


def _normalize_text(text: str) -> str:
    replacements = {
        "⚠️": "ATTENZIONE:",
        "⚠": "ATTENZIONE:",
        "✅": "OK",
        "—": "-",
        "–": "-",
        "’": "'",
        "“": '"',
        "”": '"',
        "à": "a",
        "è": "e",
        "é": "e",
        "ì": "i",
        "ò": "o",
        "ù": "u",
        "À": "A",
        "È": "E",
        "É": "E",
        "Ì": "I",
        "Ò": "O",
        "Ù": "U",
        "•": "-",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return text


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _write_pdf(path: Path, content_streams: Sequence[bytes]) -> None:
    page_count = len(content_streams)
    first_font_object = 3 + page_count + page_count
    helvetica_object = first_font_object
    bold_object = first_font_object + 1
    first_content_object = 3 + page_count

    kids = " ".join(f"{3 + index} 0 R" for index in range(page_count)).encode("ascii")
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids ["
        + kids
        + b"] /Count "
        + str(page_count).encode("ascii")
        + b" >>",
    ]

    for index in range(page_count):
        content_object = first_content_object + index
        objects.append(
            (
                b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 "
                + f"{PAGE_WIDTH:.2f} {PAGE_HEIGHT:.2f}".encode("ascii")
                + b"] /Resources << /Font << /F1 "
                + str(helvetica_object).encode("ascii")
                + b" 0 R /F2 "
                + str(bold_object).encode("ascii")
                + b" 0 R >> >> /Contents "
                + str(content_object).encode("ascii")
                + b" 0 R >>"
            )
        )

    for stream in content_streams:
        objects.append(
            b"<< /Length "
            + str(len(stream)).encode("ascii")
            + b" >>\nstream\n"
            + stream
            + b"\nendstream"
        )

    objects.extend(
        [
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
        ]
    )

    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{number} 0 obj\n".encode("ascii"))
        output.extend(obj)
        output.extend(b"\nendobj\n")

    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode(
            "ascii"
        )
    )
    path.write_bytes(bytes(output))
