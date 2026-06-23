"""Tool deterministici richiamabili dal layer AI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from orari_agent.backup import collect_backup_info, create_backup as create_backup_zip
from orari_agent.bot.schedule_service import GeneratedScheduleResult, ScheduleService
from orari_agent.storage.notes_repository import Note, NotesRepository
from orari_agent.storage.operational_memory_parser import parse_operational_memory
from orari_agent.storage.operational_memory_repository import (
    OperationalMemory,
    OperationalMemoryRepository,
)
from orari_agent.storage.week_parser import parse_note_metadata, parse_week_request
from orari_agent.storage.wife_calendar_repository import WifeCalendarRepository
from orari_agent.ai.schedule_explainer import ScheduleExplainer

DESTRUCTIVE_TOOLS = {
    "delete_weekly_notes_for_week",
    "reset_wife_calendar",
    "reset_memory",
}


@dataclass(frozen=True)
class ToolExecutionResult:
    name: str
    message: str
    data: dict[str, Any]
    generated_schedule: GeneratedScheduleResult | None = None


class AiToolExecutor:
    """Adattatore tra tool call AI e servizi/repository esistenti."""

    def __init__(
        self,
        notes_repository: NotesRepository,
        operational_memory_repository: OperationalMemoryRepository,
        schedule_service: ScheduleService,
        wife_calendar_repository: WifeCalendarRepository,
        database_path: Path,
        data_dir: Path,
        backup_dir: Path,
    ) -> None:
        self.notes_repository = notes_repository
        self.operational_memory_repository = operational_memory_repository
        self.schedule_service = schedule_service
        self.wife_calendar_repository = wife_calendar_repository
        self.database_path = database_path
        self.data_dir = data_dir
        self.backup_dir = backup_dir

    def execute(self, name: str, arguments: dict[str, Any]) -> ToolExecutionResult:
        if name == "add_weekly_note":
            return self.add_weekly_note(
                str(arguments.get("text", "")).strip(),
                str(arguments.get("week_request", "")).strip(),
            )
        if name == "list_weekly_notes":
            return self.list_weekly_notes(
                str(arguments.get("week_request", "")).strip()
            )
        if name == "delete_weekly_note":
            return self.delete_weekly_note(int(arguments.get("note_id", 0)))
        if name == "delete_weekly_notes_for_week":
            return self.delete_weekly_notes_for_week(
                str(arguments.get("week_request", "")).strip()
            )
        if name == "add_operational_memory":
            return self.add_operational_memory(str(arguments.get("text", "")).strip())
        if name in {"list_operational_memory", "list_operational_memories"}:
            return self.list_operational_memory()
        if name == "generate_schedule":
            return self.generate_schedule(
                str(arguments.get("week_request", "")).strip()
            )
        if name == "explain_last_schedule":
            return self.explain_last_schedule(str(arguments.get("question", "")).strip())
        if name == "get_last_schedule":
            return self.explain_last_schedule("")
        if name == "validate_schedule":
            return self.validate_last_schedule()
        if name == "get_wife_calendar_info":
            return self.get_wife_calendar_info()
        if name == "list_wife_calendar_m_dates":
            return self.list_wife_calendar_m_dates()
        if name == "backup_info":
            return self.backup_info()
        if name == "create_backup":
            return self.create_backup()
        raise ValueError(f"Tool AI non supportato: {name}")

    def add_weekly_note(self, text: str, week_request: str = "") -> ToolExecutionResult:
        if not text:
            raise ValueError("Testo nota mancante.")
        metadata = parse_note_metadata(f"{week_request} {text}".strip())
        note = self.notes_repository.add(text, metadata)
        return ToolExecutionResult(
            "add_weekly_note",
            _note_summary(note),
            {
                "note_id": note.id,
                "week_start": note.target_week_start,
                "week_end": note.target_week_end,
            },
        )

    def list_weekly_notes(self, week_request: str = "") -> ToolExecutionResult:
        start, end = parse_week_request(week_request)
        notes = self.notes_repository.active_for_week(
            start.isoformat(), end.isoformat()
        )
        if notes:
            lines = [f"Note attive {start.isoformat()} - {end.isoformat()}:"]
            lines.extend(f"ID {note.id}: {note.raw_text}" for note in notes)
        else:
            lines = [
                f"Nessuna nota attiva per {start.isoformat()} - {end.isoformat()}."
            ]
        return ToolExecutionResult(
            "list_weekly_notes",
            "\n".join(lines),
            {
                "count": len(notes),
                "week_start": start.isoformat(),
                "week_end": end.isoformat(),
            },
        )

    def delete_weekly_note(self, note_id: int) -> ToolExecutionResult:
        deleted = self.notes_repository.delete(note_id)
        return ToolExecutionResult(
            "delete_weekly_note",
            (
                f"Nota ID {note_id} cancellata."
                if deleted
                else f"Nota ID {note_id} non trovata."
            ),
            {"note_id": note_id, "deleted": deleted},
        )

    def delete_weekly_notes_for_week(
        self, week_request: str = ""
    ) -> ToolExecutionResult:
        start, end = parse_week_request(week_request)
        count = self.notes_repository.archive_week(start.isoformat(), end.isoformat())
        return ToolExecutionResult(
            "delete_weekly_notes_for_week",
            f"Ho archiviato {count} note attive per {start.isoformat()} - {end.isoformat()}.",
            {
                "count": count,
                "week_start": start.isoformat(),
                "week_end": end.isoformat(),
            },
        )

    def add_operational_memory(self, text: str) -> ToolExecutionResult:
        if not text:
            raise ValueError("Testo memoria mancante.")
        memory = self.operational_memory_repository.add(
            parse_operational_memory(text), source="telegram_ai"
        )
        return ToolExecutionResult(
            "add_operational_memory",
            _memory_summary(memory),
            {"memory_id": memory.id},
        )

    def list_operational_memory(self) -> ToolExecutionResult:
        memories = self.operational_memory_repository.list_active()
        if memories:
            lines = ["Memorie operative attive:"]
            lines.extend(f"ID {memory.id}: {memory.raw_text}" for memory in memories)
        else:
            lines = ["Nessuna memoria operativa attiva."]
        return ToolExecutionResult(
            "list_operational_memory", "\n".join(lines), {"count": len(memories)}
        )

    def generate_schedule(self, week_request: str = "") -> ToolExecutionResult:
        start, end = parse_week_request(week_request)
        result = self.schedule_service.generate_for_week(
            start.isoformat(), end.isoformat()
        )
        warning_text = (
            "Nessun conflitto critico rilevato."
            if not result.warnings
            else "Conflitti critici:\n"
            + "\n".join(f"• {warning}" for warning in result.warnings[:8])
        )
        return ToolExecutionResult(
            "generate_schedule",
            f"{result.summary}\n{warning_text}",
            {
                "week_start": start.isoformat(),
                "week_end": end.isoformat(),
                "pdf_path": str(result.pdf_path),
                "warnings": result.warnings,
            },
            generated_schedule=result,
        )

    def validate_last_schedule(self) -> ToolExecutionResult:
        snapshot = self.schedule_service.schedules_repository.latest_snapshot()
        if snapshot is None:
            return ToolExecutionResult("validate_schedule", "Nessun orario generato da validare.", {"available": False})
        import json
        data = json.loads(snapshot["snapshot_json"])
        validation = data.get("validation", {})
        critical = validation.get("critical_conflicts", [])
        alerts = validation.get("informational_alerts", [])
        message = (
            f"Validazione ultimo orario: {len(critical)} conflitti critici, "
            f"{len(alerts)} alert informativi."
        )
        return ToolExecutionResult("validate_schedule", message, validation)

    def explain_last_schedule(self, question: str = "") -> ToolExecutionResult:
        message = ScheduleExplainer(self.schedule_service.schedules_repository).explain(question)
        return ToolExecutionResult("explain_last_schedule", message, {"question": question})

    def get_wife_calendar_info(self) -> ToolExecutionResult:
        entries = self.wife_calendar_repository.list_entries("M")
        latest = self.wife_calendar_repository.latest_import_record()
        message = (
            "Info calendario moglie:\n"
            f"Numero date M: {len(entries)}\n"
            f"Prima data M: {entries[0].date if entries else 'nessuna'}\n"
            f"Ultima data M: {entries[-1].date if entries else 'nessuna'}\n"
            f"Ultimo import: {latest.created_at if latest else 'nessuno'}\n"
            "Regola: solo M blocca Gianmarco all'apertura lago 07:30; date mancanti luglio/agosto = nessun vincolo."
        )
        return ToolExecutionResult(
            "get_wife_calendar_info", message, {"m_count": len(entries)}
        )

    def list_wife_calendar_m_dates(self) -> ToolExecutionResult:
        entries = self.wife_calendar_repository.list_entries("M")
        dates = [entry.date for entry in entries]
        message = "Date M calendario moglie: " + (
            ", ".join(dates) if dates else "nessuna"
        )
        return ToolExecutionResult(
            "list_wife_calendar_m_dates", message, {"dates": dates}
        )

    def backup_info(self) -> ToolExecutionResult:
        info = collect_backup_info(self.database_path, self.backup_dir)
        message = (
            "Backup info:\n"
            f"Database: {info.database_path}\n"
            f"Note: {info.notes_count}\n"
            f"Memorie operative: {info.memories_count}\n"
            f"Date calendario moglie: {info.wife_calendar_entries_count}\n"
            f"Ultimo backup: {info.latest_backup.name if info.latest_backup else 'nessuno'}"
        )
        return ToolExecutionResult(
            "backup_info",
            message,
            {"latest_backup": info.latest_backup.name if info.latest_backup else None},
        )

    def create_backup(self) -> ToolExecutionResult:
        zip_path = create_backup_zip(self.database_path, self.data_dir, self.backup_dir)
        return ToolExecutionResult(
            "create_backup",
            f"Backup creato: {zip_path.name}",
            {"zip_path": str(zip_path)},
        )


def _note_summary(note: Note) -> str:
    lines = [
        f"Nota salvata con ID {note.id}.",
        f"Testo: {note.raw_text}",
        f"Settimana: {note.target_week_start} - {note.target_week_end}",
    ]
    if note.interpreted_date:
        lines.append(f"Data interpretata: {note.interpreted_date}")
    if note.person:
        lines.append(f"Persona: {note.person}")
    if note.location:
        lines.append(f"Luogo: {note.location}")
    lines.append("La userò nella generazione dell'orario.")
    return "\n".join(lines)


def _memory_summary(memory: OperationalMemory) -> str:
    lines = [
        f"Memoria operativa salvata con ID {memory.id}.",
        f"Testo: {memory.raw_text}",
        f"Tipo: {memory.constraint_type}",
    ]
    if memory.person:
        lines.append(f"Persona: {memory.person}")
    if memory.start_date:
        lines.append(
            f"Periodo: {memory.start_date} - {memory.end_date or memory.start_date}"
        )
    lines.append("La applicherò automaticamente quando genera orari compatibili.")
    return "\n".join(lines)
