"""Esportazione PDF dell'orario settimanale.

Il modulo resta separato dal motore di scheduling: riceve un ``WeeklySchedule``
già generato e produce un PDF A4 orizzontale pronto per la condivisione manuale.
"""

from __future__ import annotations

import textwrap
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable

from .models import Assignment, DaySchedule, WeeklySchedule

PDF_TITLE = "Orario settimanale CarpeEvolution & Tenuta del Germano"
DEFAULT_FILENAME_PREFIX = "Orario_CarpeEvolution_Tenuta"

# A4 landscape in PostScript points.
PAGE_WIDTH = 841.89
PAGE_HEIGHT = 595.28
MARGIN = 28.0
TABLE_WIDTH = PAGE_WIDTH - (MARGIN * 2)

COLUMN_SPECS = [
    ("Giorno", 66.0),
    ("Lago mattina", 124.0),
    ("Lago pomeriggio", 124.0),
    ("Negozio mattina", 124.0),
    ("Negozio pomeriggio", 124.0),
    ("Note", TABLE_WIDTH - 66.0 - (124.0 * 4)),
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
) -> Path:
    """Genera il PDF settimanale e restituisce il percorso del file creato.

    Se ``output_path`` è una directory, viene creato al suo interno un file con
    nome standard ``Orario_CarpeEvolution_Tenuta_YYYY-MM-DD.pdf``. Se è un file
    ``.pdf``, quel percorso viene usato direttamente.
    """

    resolved_week_start = _resolve_week_start(schedule, week_start_date)
    destination = _resolve_output_path(output_path, resolved_week_start)
    destination.parent.mkdir(parents=True, exist_ok=True)

    content_stream = _build_page_content(schedule, resolved_week_start)
    _write_pdf(destination, content_stream)
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


def _build_page_content(schedule: WeeklySchedule, week_start_date: str | None) -> bytes:
    commands: list[str] = []
    _add_text(commands, MARGIN, PAGE_HEIGHT - 36, PDF_TITLE, 16, bold=True)

    subtitle = _week_label(week_start_date)
    if subtitle:
        _add_text(commands, MARGIN, PAGE_HEIGHT - 56, subtitle, 10)

    warnings_count = len(schedule.global_warnings) + sum(
        len(day.warnings) for day in schedule.days
    )
    status = (
        "Avvisi presenti: controllare le note evidenziate in tabella."
        if warnings_count
        else "Nessun conflitto o violazione rilevata dai controlli automatici."
    )
    _add_text(commands, MARGIN, PAGE_HEIGHT - 74, status, 9, bold=bool(warnings_count))

    y = PAGE_HEIGHT - 96
    y = _draw_table(commands, schedule.days, y)

    if schedule.global_warnings:
        _draw_warning_box(commands, "Avvisi generali", schedule.global_warnings, y - 12)
    elif schedule.global_notes:
        _draw_warning_box(commands, "Note settimanali", schedule.global_notes, y - 12)

    footer = "PDF pronto per condivisione manuale su WhatsApp - invio automatico non incluso."
    _add_text(commands, MARGIN, 20, footer, 7)
    return "\n".join(commands).encode("latin-1", errors="replace")


def _week_label(week_start_date: str | None) -> str | None:
    if not week_start_date:
        return None
    try:
        start = datetime.strptime(week_start_date, "%Y-%m-%d").date()
    except ValueError:
        return f"Settimana: {week_start_date}"
    end = start + timedelta(days=6)
    return f"Settimana dal {start.strftime('%d/%m/%Y')} al {end.strftime('%d/%m/%Y')}"


def _draw_table(commands: list[str], days: list[DaySchedule], top_y: float) -> float:
    x_positions = [MARGIN]
    for _, width in COLUMN_SPECS[:-1]:
        x_positions.append(x_positions[-1] + width)

    header_height = 22.0
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
        _add_text(commands, x + 4, top_y - 14, label, 8.2, bold=True, color=(1, 1, 1))
        _draw_rect(commands, x, top_y - header_height, width, header_height)

    y = top_y - header_height
    for index, day in enumerate(days):
        row = _row_for_day(day)
        wrapped_cells = [
            _wrap_cell(cell.text, width, cell.font_size)
            for cell, (_, width) in zip(row, COLUMN_SPECS, strict=True)
        ]
        line_count = max(len(lines) for lines in wrapped_cells)
        row_height = max(48.0, min(62.0, 10.5 + line_count * 9.2))

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
        if day.warnings:
            _draw_filled_rect(
                commands,
                MARGIN,
                y - row_height,
                TABLE_WIDTH,
                row_height,
                1.0,
                0.96,
                0.86,
            )

        for x, (cell, lines, (_, width)) in zip(
            x_positions, zip(row, wrapped_cells, COLUMN_SPECS, strict=True), strict=True
        ):
            _draw_rect(commands, x, y - row_height, width, row_height, stroke_gray=0.72)
            text_y = y - 12.5
            color = (
                (0.55, 0.15, 0.0)
                if day.warnings and cell.text.startswith("ATTENZIONE")
                else (0, 0, 0)
            )
            for line in lines[:6]:
                _add_text(
                    commands,
                    x + 4,
                    text_y,
                    line,
                    cell.font_size,
                    bold=cell.font_size >= 8.5,
                    color=color,
                )
                text_y -= 9.2

        y -= row_height
    return y


def _row_for_day(day: DaySchedule) -> list[_Cell]:
    notes = [*day.notes]
    notes.extend(f"ATTENZIONE: {warning}" for warning in day.warnings)
    return [
        _Cell(day.day, 8.8),
        _Cell(_format_assignments(day.lake_morning)),
        _Cell(_format_assignments(day.lake_afternoon)),
        _Cell(_format_assignments(day.shop_morning)),
        _Cell(_format_assignments(day.shop_afternoon)),
        _Cell("; ".join(notes) if notes else "-", 6.9),
    ]


def _format_assignments(assignments: list[Assignment]) -> str:
    if not assignments:
        return "-"
    return "; ".join(assignment.label() for assignment in assignments)


def _wrap_cell(text: str, width: float, font_size: float) -> list[str]:
    normalized = _normalize_text(text)
    chars_per_line = max(8, int(width / (font_size * 0.46)))
    lines: list[str] = []
    for chunk in normalized.split("; "):
        wrapped = textwrap.wrap(
            chunk, width=chars_per_line, break_long_words=False
        ) or [""]
        lines.extend(wrapped)
    if len(lines) > 6:
        return [*lines[:5], "..."]
    return lines


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
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return text


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _write_pdf(path: Path, content_stream: bytes) -> None:
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 "
            + f"{PAGE_WIDTH:.2f} {PAGE_HEIGHT:.2f}".encode("ascii")
            + b"] /Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> /Contents 6 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>",
        b"<< /Length "
        + str(len(content_stream)).encode("ascii")
        + b" >>\nstream\n"
        + content_stream
        + b"\nendstream",
    ]

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
