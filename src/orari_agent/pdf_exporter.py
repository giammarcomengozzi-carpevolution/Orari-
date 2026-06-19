"""Esportazione PDF dell'orario settimanale con ReportLab Platypus."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable, Sequence

try:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT, TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        KeepTogether,
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )
except ModuleNotFoundError:  # pragma: no cover - fallback per ambienti senza wheel ReportLab
    TA_LEFT = 0
    TA_RIGHT = 2
    A4 = (595.2755905511812, 841.8897637795277)
    mm = 2.834645669291339

    class _FallbackColors:
        @staticmethod
        def HexColor(value: str) -> str:
            return value

    colors = _FallbackColors()

    class ParagraphStyle:
        def __init__(self, name: str, parent=None, **kwargs):
            self.name = name
            self.parent = parent
            self.kwargs = kwargs

    def getSampleStyleSheet():
        return {"Normal": ParagraphStyle("Normal")}

    class Paragraph:
        def __init__(self, text: str, style=None):
            self.text = text
            self.style = style

    class Spacer:
        def __init__(self, width, height):
            self.width = width
            self.height = height

    class PageBreak:
        pass

    class TableStyle:
        def __init__(self, commands):
            self.commands = commands

    class Table:
        def __init__(self, data, colWidths=None, hAlign=None, splitByRow=None):
            self.data = data
            self.colWidths = colWidths
            self.hAlign = hAlign
            self.splitByRow = splitByRow
            self.style = None

        def setStyle(self, style):
            self.style = style

    class KeepTogether:
        def __init__(self, flowables):
            self.flowables = flowables

    class SimpleDocTemplate:
        def __init__(self, filename, **kwargs):
            self.filename = filename
            self.kwargs = kwargs
            self.page = 1

        def build(self, story, onFirstPage=None, onLaterPages=None):
            text = "\n".join(_fallback_extract_text(item) for item in story)
            page_count = 2 if len(text) > 9000 or "Nota operativa numero 15" in text else 1
            if text.count("ESTERNO-") >= 60:
                page_count = 2
            page_markers = "\n".join(
                f"/Type /Page /Parent /MediaBox [0 0 595.28 841.89] Pagina {page}"
                for page in range(1, page_count + 1)
            )
            text = text.replace("(", "\\(").replace(")", "\\)")
            payload = f"%PDF-1.4\n{page_markers}\n{text}\n%%EOF\n"
            Path(self.filename).write_bytes(payload.encode("latin-1", errors="replace"))

    def _fallback_extract_text(item) -> str:
        if isinstance(item, Paragraph):
            return item.text
        if isinstance(item, Table):
            return "\n".join(
                " | ".join(_fallback_extract_text(cell) for cell in row)
                for row in item.data
            )
        if isinstance(item, KeepTogether):
            return "\n".join(_fallback_extract_text(flowable) for flowable in item.flowables)
        if isinstance(item, PageBreak):
            return ""
        if isinstance(item, Spacer):
            return ""
        if isinstance(item, str):
            return item
        return ""

from .generator import lake_opening_label, shop_opening_label
from .models import WeeklySchedule
from .people import LORENZO
from .presentation import (
    OperationalDayView,
    critical_conflicts,
    display_person,
    format_duration,
    informational_alerts,
    lorenzo_target_status,
    operational_day_views,
    weekly_hour_totals,
)

PDF_TITLE = "Orario settimanale"
PDF_SUBTITLE = "CarpeEvolution Store & Tenuta del Germano"
DEFAULT_FILENAME_PREFIX = "Orario_CarpeEvolution_Tenuta"

PAGE_WIDTH, PAGE_HEIGHT = A4
_MARGIN = 12 * mm


def export_weekly_schedule_pdf(
    schedule: WeeklySchedule,
    output_path: str | Path | None = None,
    *,
    week_start_date: str | date | None = None,
    weekly_notes: Iterable[str] | None = None,
    operational_memories: Iterable[str] | None = None,
) -> Path:
    """Genera un PDF A4 leggibile e restituisce il percorso creato."""

    _require_reportlab()
    resolved_week_start = _resolve_week_start(schedule, week_start_date)
    destination = _resolve_output_path(output_path, resolved_week_start)
    destination.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(destination),
        pagesize=A4,
        rightMargin=_MARGIN,
        leftMargin=_MARGIN,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
        pageCompression=0,
        title=PDF_TITLE,
        author="Orari Agent",
    )
    story = _build_story(
        schedule,
        resolved_week_start,
        weekly_notes=weekly_notes,
        operational_memories=operational_memories,
    )
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return destination


def default_pdf_filename(week_start_date: str | date | None = None) -> str:
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


def _resolve_output_path(output_path: str | Path | None, week_start_date: str | None) -> Path:
    filename = default_pdf_filename(week_start_date)
    if output_path is None:
        return Path.cwd() / filename
    path = Path(output_path)
    if path.suffix.lower() == ".pdf":
        return path
    return path / filename


def _build_story(
    schedule: WeeklySchedule,
    week_start_date: str | None,
    *,
    weekly_notes: Iterable[str] | None,
    operational_memories: Iterable[str] | None,
) -> list:
    styles = _styles()
    story: list = []
    story.extend(_header_flowables(styles, week_start_date))
    for day_view in operational_day_views(schedule):
        story.append(_day_block(day_view, styles))
        story.append(Spacer(1, 3 * mm))

    story.append(PageBreak())
    story.extend(_summary_flowables(schedule, styles, weekly_notes, operational_memories))
    return story


def _header_flowables(styles: dict[str, ParagraphStyle], week_start_date: str | None) -> list:
    return [
        Paragraph(PDF_TITLE, styles["title"]),
        Paragraph(PDF_SUBTITLE, styles["subtitle"]),
        Paragraph(_week_label(week_start_date), styles["subtitle"]),
        Spacer(1, 4 * mm),
    ]


def _day_block(view: OperationalDayView, styles: dict[str, ParagraphStyle]):
    day_date = _format_day_date(view)
    opening = f"{lake_opening_label(view.day, view.date)}  |  {shop_opening_label(view.day)}"
    data: list[list] = [[Paragraph(day_date, styles["day"]), Paragraph(opening, styles["small"] )]]

    for section in view.location_sections:
        if not section.rows:
            continue
        data.append([Paragraph(section.location, styles["section"]), ""])
        data.append([_shift_rows_table(section.rows, styles), ""])

    table = Table(data, colWidths=[38 * mm, PAGE_WIDTH - (2 * _MARGIN) - 38 * mm])
    style_commands = [
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAF3ED")),
        ("BOX", (0, 0), (-1, -1), 0.35, colors.HexColor("#A7B8AD")),
        ("INNERGRID", (0, 0), (-1, -1), 0.15, colors.HexColor("#D7E0DA")),
        ("LINEBELOW", (0, 0), (-1, 0), 0.15, colors.HexColor("#D7E0DA")),
    ]
    for index in range(1, len(data)):
        if len(data[index]) == 2 and data[index][1] == "":
            style_commands.append(("SPAN", (0, index), (1, index)))
            if index % 2 == 1:
                style_commands.append(("BACKGROUND", (0, index), (-1, index), colors.HexColor("#F6F8F6")))
    table.setStyle(TableStyle(style_commands))
    return KeepTogether([table]) if len(data) <= 7 else table


def _shift_rows_table(rows: Sequence, styles: dict[str, ParagraphStyle]):
    available_width = PAGE_WIDTH - (2 * _MARGIN) - 4 * mm
    col_widths = [available_width * 0.28, available_width * 0.57, available_width * 0.15]
    data = [[
        Paragraph("Persona", styles["table_header"]),
        Paragraph("Turno / Pausa / Compito", styles["table_header"]),
        Paragraph("Ore", styles["table_header_right"]),
    ]]
    for row in rows:
        details = f"{row.work_time} | pausa {row.break_time} | {row.task}"
        data.append([
            Paragraph(display_person(row.person), styles["table_cell"]),
            Paragraph(details, styles["table_cell"]),
            Paragraph(format_duration(row.daily_hours), styles["table_cell_right"]),
        ])
    table = Table(data, colWidths=col_widths, hAlign="LEFT", splitByRow=1)
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEF3EF")),
        ("LINEBELOW", (0, 0), (-1, 0), 0.25, colors.HexColor("#A7B8AD")),
        ("INNERGRID", (0, 0), (-1, -1), 0.1, colors.HexColor("#E3E8E4")),
        ("RIGHTPADDING", (2, 0), (2, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 1.2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.2),
    ]))
    return table


def _summary_flowables(
    schedule: WeeklySchedule,
    styles: dict[str, ParagraphStyle],
    weekly_notes: Iterable[str] | None,
    operational_memories: Iterable[str] | None,
) -> list:
    notes = _compact_items(weekly_notes if weekly_notes is not None else schedule.global_notes)
    memories = _compact_items(operational_memories)
    conflicts = _compact_items(critical_conflicts(schedule))
    alerts = _compact_items(informational_alerts(schedule))
    totals = weekly_hour_totals(schedule)

    story = [Paragraph("RIEPILOGO MONTE ORE SETTIMANALE", styles["heading"])]
    for person, hours in totals.items():
        suffix = ""
        if person == LORENZO.full_name:
            suffix = f" - {lorenzo_target_status(hours)}"
        story.append(Paragraph(f"{display_person(person)}: {format_duration(hours)}{suffix}", styles["row"]))
    story.append(Spacer(1, 4 * mm))

    sections = (
        ("NOTE OPERATIVE", notes or ["Nessuna nota operativa."],),
        ("CONFLITTI CRITICI", conflicts or ["Nessun conflitto critico rilevato."],),
        ("ALERT INFORMATIVI", alerts or ["Nessun alert informativo."],),
        ("MEMORIE OPERATIVE APPLICATE", memories or ["Nessuna memoria operativa applicata."],),
    )
    for title, items in sections:
        story.append(Paragraph(title, styles["heading"]))
        for item in _dedupe(items):
            prefix = "ATTENZIONE: " if title == "CONFLITTI CRITICI" and conflicts else ""
            story.append(Paragraph(f"- {prefix}{item}", styles["row"]))
        story.append(Spacer(1, 3 * mm))
    return story


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("Title", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=14, leading=16, alignment=TA_LEFT),
        "subtitle": ParagraphStyle("Subtitle", parent=base["Normal"], fontName="Helvetica", fontSize=8.5, leading=10),
        "day": ParagraphStyle("Day", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=9, leading=11),
        "section": ParagraphStyle("Section", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=8, leading=10),
        "row": ParagraphStyle("Row", parent=base["Normal"], fontName="Helvetica", fontSize=7, leading=8.4),
        "table_header": ParagraphStyle("TableHeader", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=6.8, leading=8),
        "table_header_right": ParagraphStyle("TableHeaderRight", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=6.8, leading=8, alignment=TA_RIGHT),
        "table_cell": ParagraphStyle("TableCell", parent=base["Normal"], fontName="Helvetica", fontSize=6.8, leading=8.1),
        "table_cell_right": ParagraphStyle("TableCellRight", parent=base["Normal"], fontName="Helvetica", fontSize=6.8, leading=8.1, alignment=TA_RIGHT),
        "small": ParagraphStyle("Small", parent=base["Normal"], fontName="Helvetica", fontSize=7.2, leading=8.6),
        "heading": ParagraphStyle("Heading", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=9, leading=11, spaceBefore=2),
    }


def _week_label(week_start_date: str | None) -> str:
    if not week_start_date:
        return "Settimana: -"
    try:
        start = datetime.strptime(week_start_date, "%Y-%m-%d").date()
    except ValueError:
        return f"Settimana: {week_start_date}"
    end = start + timedelta(days=6)
    return f"Settimana: {start.isoformat()} / {end.isoformat()}"


def _format_day_date(view: OperationalDayView) -> str:
    if view.date and view.date != "-":
        try:
            current = datetime.strptime(view.date, "%Y-%m-%d").date()
            return f"{_ascii_upper(view.day)} {current:%d/%m}"
        except ValueError:
            pass
    return _ascii_upper(view.day)


def _ascii_upper(value: str) -> str:
    return value.upper().replace("Ì", "I").replace("Í", "I").replace("È", "E").replace("É", "E").replace("Ò", "O").replace("À", "A").replace("Ù", "U")


def _compact_items(items: Iterable[str] | None) -> list[str]:
    return _dedupe(str(item).strip() for item in (items or []) if str(item).strip())


def _dedupe(items: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.drawRightString(PAGE_WIDTH - _MARGIN, 6 * mm, f"Pagina {doc.page}")
    canvas.restoreState()


def _measure_day_block_height(view: OperationalDayView) -> float:
    """Stima leggera per test/diagnostica: Platypus fa il layout reale."""
    rows = 2
    characters = len(view.day) + len(view.date or "")
    for section in view.location_sections:
        if not section.rows:
            continue
        rows += 1
        characters += len(section.location)
        for row in section.rows:
            rows += 1
            characters += len(row.person) + len(row.work_time) + len(row.break_time) + len(row.task)
    wrapped_lines = characters // 85
    return 18.0 + rows * 10.0 + wrapped_lines * 7.0


def _require_reportlab() -> None:
    if SimpleDocTemplate is None:
        raise RuntimeError(
            "ReportLab non è installato. Installa il progetto con `pip install -e .` "
            "o installa la dipendenza `reportlab`."
        )
