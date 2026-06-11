"""Esportazione PDF dell'orario settimanale.

Il modulo resta separato dal motore di scheduling: riceve un ``WeeklySchedule``
già generato e produce un PDF A4 orizzontale pronto per la condivisione manuale.
"""

from __future__ import annotations

import textwrap
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable, Sequence

from .models import WeeklySchedule
from .presentation import (
    EffectiveShift,
    critical_conflicts,
    display_person,
    effective_shifts,
    format_duration,
    informational_alerts,
    lorenzo_target_status,
    weekly_hour_totals,
)
from .people import ANGELO, GIAMMARCO, LORENZO

PDF_TITLE = "Orario settimanale"
PDF_SUBTITLE = "CarpeEvolution Store & Tenuta del Germano"
DEFAULT_FILENAME_PREFIX = "Orario_CarpeEvolution_Tenuta"

# A4 landscape in PostScript points.
PAGE_WIDTH = 841.89
PAGE_HEIGHT = 595.28
MARGIN = 28.0
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
    shifts = effective_shifts(schedule)

    page_one: list[str] = []
    _draw_header(page_one, week_start_date)
    y = _draw_table(page_one, shifts, PAGE_HEIGHT - 104)

    y = _draw_weekly_totals(page_one, y - 8, totals)
    y = _draw_summary_sections(page_one, y - 8, notes, conflicts, memories, alerts)
    _draw_footer(page_one, 1)

    pages = ["\n".join(page_one).encode("latin-1", errors="replace")]
    if _needs_detail_page(notes, conflicts + alerts, memories):
        detail: list[str] = []
        _draw_header(detail, week_start_date, compact=True)
        _draw_detail_page(detail, notes, conflicts + alerts, memories)
        _draw_footer(detail, 2)
        pages.append("\n".join(detail).encode("latin-1", errors="replace"))
    return pages


def _draw_header(
    commands: list[str], week_start_date: str | None, *, compact: bool = False
) -> None:
    top = PAGE_HEIGHT - 31
    _draw_filled_rect(commands, 0, PAGE_HEIGHT - 74, PAGE_WIDTH, 74, 0.05, 0.20, 0.12)
    _add_text(
        commands,
        MARGIN,
        top,
        PDF_TITLE,
        18 if not compact else 15,
        bold=True,
        color=(1, 1, 1),
    )
    _add_text(
        commands,
        MARGIN,
        top - 20,
        PDF_SUBTITLE,
        10,
        bold=True,
        color=(0.88, 0.95, 0.90),
    )
    week = _week_label(week_start_date)
    if week:
        _add_text(
            commands,
            PAGE_WIDTH - MARGIN - 210,
            top - 10,
            week,
            9.5,
            bold=True,
            color=(1, 1, 1),
        )


def _draw_footer(commands: list[str], page_number: int) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    footer = (
        f"Generato il {timestamp} - pronto per WhatsApp/Telegram - Pagina {page_number}"
    )
    _add_text(commands, MARGIN, 20, footer, 7, color=(0.25, 0.25, 0.25))


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


def _draw_table(
    commands: list[str],
    shifts: list[EffectiveShift],
    top_y: float,
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
    visible_shifts = shifts[:18]
    for index, shift in enumerate(visible_shifts):
        row = _row_for_shift(shift)
        wrapped_cells = [
            _wrap_cell(cell.text, width, cell.font_size)
            for cell, (_, width) in zip(row, COLUMN_SPECS, strict=True)
        ]
        line_count = max(len(lines) for lines in wrapped_cells)
        row_height = max(18.0, min(30.0, 7.5 + line_count * 7.2))

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

    if len(shifts) > len(visible_shifts):
        _add_text(
            commands,
            MARGIN,
            y - 10,
            f"Altri {len(shifts) - len(visible_shifts)} turni disponibili nei dettagli operativi.",
            7.0,
            bold=True,
            color=(0.45, 0.12, 0.0),
        )
        y -= 16
    return y


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
    height = 52.0
    y = max(34.0, top_y - height)
    _draw_filled_rect(commands, MARGIN, y, TABLE_WIDTH, height, 0.94, 0.97, 0.94)
    _draw_rect(commands, MARGIN, y, TABLE_WIDTH, height, stroke_gray=0.65)
    _add_text(
        commands,
        MARGIN + 6,
        top_y - 12,
        "Riepilogo monte ore settimanale",
        8.0,
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
            f"{display_person(person)} | {format_duration(total)} | {status}",
            7.0,
        )
        y_text -= 9.0
    return y


def _draw_summary_sections(
    commands: list[str],
    top_y: float,
    notes: Sequence[str],
    warnings: Sequence[str],
    memories: Sequence[str],
    alerts: Sequence[str] | None = None,
) -> float:
    box_gap = 7.0
    box_width = (TABLE_WIDTH - (box_gap * 2)) / 3
    height = max(54.0, min(78.0, top_y - 36.0))
    y = max(34.0, top_y - height)
    alert_lines = list(alerts or [])
    conflict_lines = (
        ["Nessun conflitto critico rilevato"]
        if not warnings
        else ["ATTENZIONE - conflitti critici"] + list(warnings)
    )
    if alert_lines:
        conflict_lines.extend(["Alert informativi", *alert_lines])
    summaries = [
        (
            "Note operative",
            notes or ["Nessuna nota operativa specifica."],
            (0.94, 0.97, 0.94),
            (0.05, 0.20, 0.12),
        ),
        (
            "Conflitti critici / alert",
            conflict_lines,
            (1.0, 0.94, 0.84) if warnings else (0.94, 0.97, 0.94),
            (0.70, 0.18, 0.02) if warnings else (0.05, 0.20, 0.12),
        ),
        (
            "Memorie operative applicate",
            memories or ["Nessuna memoria operativa applicata."],
            (0.94, 0.97, 0.94),
            (0.05, 0.20, 0.12),
        ),
    ]
    for index, (title, items, fill, title_color) in enumerate(summaries):
        x = MARGIN + index * (box_width + box_gap)
        _draw_filled_rect(commands, x, y, box_width, height, *fill)
        _draw_rect(commands, x, y, box_width, height, stroke_gray=0.65)
        _add_text(commands, x + 6, top_y - 12, title, 7.6, bold=True, color=title_color)
        text_y = top_y - 23
        preview_lines = _section_preview_lines(items, box_width)
        for line in preview_lines[:5]:
            _add_text(commands, x + 6, text_y, line, 6.6, color=(0.10, 0.10, 0.10))
            text_y -= 8.0
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
