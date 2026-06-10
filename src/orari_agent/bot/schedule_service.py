"""Servizio applicativo per generare PDF usando note persistenti."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from orari_agent.generator import generate_weekly_schedule
from orari_agent.models import WeeklySchedule
from orari_agent.pdf_exporter import export_weekly_schedule_pdf
from orari_agent.storage.notes_repository import Note, NotesRepository
from orari_agent.storage.schedules_repository import SchedulesRepository
from orari_agent.storage.wife_calendar_repository import WifeCalendarRepository


@dataclass(frozen=True)
class GeneratedScheduleResult:
    pdf_path: Path
    summary: str
    warnings: list[str]
    notes: list[Note]


class ScheduleService:
    """Coordina memoria SQLite, motore orari e PDF."""

    def __init__(
        self,
        notes_repository: NotesRepository,
        schedules_repository: SchedulesRepository,
        wife_calendar_repository: WifeCalendarRepository,
        output_dir: Path,
    ) -> None:
        self.notes_repository = notes_repository
        self.schedules_repository = schedules_repository
        self.wife_calendar_repository = wife_calendar_repository
        self.output_dir = output_dir

    def generate_for_week(
        self, week_start: str, week_end: str
    ) -> GeneratedScheduleResult:
        notes = self.notes_repository.active_for_week(week_start, week_end)
        combined_text = _notes_to_planning_text(notes)
        schedule = generate_weekly_schedule(
            combined_text,
            week_start_date=week_start,
            wife_calendar_codes=self.wife_calendar_repository.load_codes(),
        )
        warnings = _collect_warnings(schedule)
        summary = _build_summary(schedule, notes, week_start, week_end, warnings)
        pdf_path = (
            self.output_dir
            / f"Orario_CarpeEvolution_Tenuta_{week_start}_{week_end}.pdf"
        )
        export_weekly_schedule_pdf(schedule, pdf_path, week_start_date=week_start)
        self.schedules_repository.add(
            week_start=week_start,
            week_end=week_end,
            pdf_path=str(pdf_path),
            summary=summary,
            warnings="\n".join(warnings),
        )
        return GeneratedScheduleResult(
            pdf_path=pdf_path, summary=summary, warnings=warnings, notes=notes
        )


def _notes_to_planning_text(notes: list[Note]) -> str:
    if not notes:
        return ""
    return "\n".join(f"{note.raw_text}." for note in notes)


def _collect_warnings(schedule: WeeklySchedule) -> list[str]:
    warnings = list(schedule.global_warnings)
    for day in schedule.days:
        warnings.extend(f"{day.day}: {warning}" for warning in day.warnings)
    return warnings


def _build_summary(
    schedule: WeeklySchedule,
    notes: list[Note],
    week_start: str,
    week_end: str,
    warnings: list[str],
) -> str:
    note_count = len(notes)
    warning_count = len(warnings)
    return (
        f"Orario generato per la settimana {week_start} - {week_end}. "
        f"Note usate: {note_count}. "
        f"Avvisi/conflitti: {warning_count}."
    )
