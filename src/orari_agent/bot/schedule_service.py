"""Servizio applicativo per generare PDF usando note persistenti."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from orari_agent.generator import generate_weekly_schedule
from orari_agent.models import WeeklySchedule
from orari_agent.pdf_exporter import export_weekly_schedule_pdf
from orari_agent.presentation import (
    critical_conflicts,
    effective_shifts,
    format_duration,
    lorenzo_target_status,
    weekly_hour_totals,
)
from orari_agent.people import ANGELO, GIAMMARCO, LORENZO
from orari_agent.scheduling.memory_adapter import (
    memories_to_weekly_instruction,
    merge_weekly_instructions,
)
from orari_agent.storage.notes_repository import Note, NotesRepository
from orari_agent.storage.operational_memory_repository import (
    OperationalMemory,
    OperationalMemoryRepository,
)
from orari_agent.storage.schedules_repository import SchedulesRepository
from orari_agent.weekly_input import parse_weekly_instruction
from orari_agent.storage.wife_calendar_repository import WifeCalendarRepository


@dataclass(frozen=True)
class GeneratedScheduleResult:
    pdf_path: Path
    summary: str
    warnings: list[str]
    notes: list[Note]
    memories: list[OperationalMemory]


class ScheduleService:
    """Coordina memoria SQLite, motore orari e PDF."""

    def __init__(
        self,
        notes_repository: NotesRepository,
        schedules_repository: SchedulesRepository,
        wife_calendar_repository: WifeCalendarRepository,
        operational_memory_repository: OperationalMemoryRepository | None,
        output_dir: Path,
    ) -> None:
        self.notes_repository = notes_repository
        self.schedules_repository = schedules_repository
        self.wife_calendar_repository = wife_calendar_repository
        self.operational_memory_repository = operational_memory_repository
        self.output_dir = output_dir

    def generate_for_week(
        self, week_start: str, week_end: str
    ) -> GeneratedScheduleResult:
        notes = self.notes_repository.active_for_week(week_start, week_end)
        memories = (
            self.operational_memory_repository.active_overlapping(week_start, week_end)
            if self.operational_memory_repository is not None
            else []
        )
        notes_instruction = parse_weekly_instruction(_notes_to_planning_text(notes))
        memory_instruction = memories_to_weekly_instruction(
            memories, week_start, week_end
        )
        instruction = merge_weekly_instructions(notes_instruction, memory_instruction)
        schedule = generate_weekly_schedule(
            instruction,
            week_start_date=week_start,
            wife_calendar_codes=self.wife_calendar_repository.load_codes(),
        )
        warnings = _collect_warnings(schedule)
        summary = _build_summary(
            schedule, week_start, week_end, warnings, len(notes), len(memories)
        )
        pdf_path = (
            self.output_dir
            / f"Orario_CarpeEvolution_Tenuta_{week_start}_{week_end}.pdf"
        )
        export_weekly_schedule_pdf(
            schedule,
            pdf_path,
            week_start_date=week_start,
            weekly_notes=[note.raw_text for note in notes],
            operational_memories=[memory.raw_text for memory in memories],
        )
        self.schedules_repository.add(
            week_start=week_start,
            week_end=week_end,
            pdf_path=str(pdf_path),
            summary=summary,
            warnings="\n".join(warnings),
        )
        return GeneratedScheduleResult(
            pdf_path=pdf_path,
            summary=summary,
            warnings=warnings,
            notes=notes,
            memories=memories,
        )


def _notes_to_planning_text(notes: list[Note]) -> str:
    if not notes:
        return ""
    return "\n".join(f"{note.raw_text}." for note in notes)


def _collect_warnings(schedule: WeeklySchedule) -> list[str]:
    return critical_conflicts(schedule)


def _build_summary(
    schedule: WeeklySchedule,
    week_start: str,
    week_end: str,
    warnings: list[str],
    note_count: int = 0,
    memory_count: int = 0,
) -> str:
    filename = f"Orario_CarpeEvolution_Tenuta_{week_start}_{week_end}.pdf"
    totals = weekly_hour_totals(schedule)
    shift_count = len(effective_shifts(schedule))
    lorenzo_status = lorenzo_target_status(totals.get(LORENZO.full_name, 0.0))
    return (
        f"Orario generato per {week_start} / {week_end}.\n"
        f"Turni: {shift_count}.\n"
        f"Note usate: {note_count}.\n"
        f"Memorie operative: {memory_count}.\n"
        "Monte ore:\n"
        f"- Gianmarco: {format_duration(totals.get(GIAMMARCO.full_name, 0.0))}\n"
        f"- Angelo: {format_duration(totals.get(ANGELO.full_name, 0.0))}\n"
        f"- Lorenzo: {format_duration(totals.get(LORENZO.full_name, 0.0))} {lorenzo_status}\n"
        f"Conflitti critici: {len(warnings)}.\n"
        f"PDF allegato: {filename}."
    )
