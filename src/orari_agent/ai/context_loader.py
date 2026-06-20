"""Caricamento contesto operativo leggero per il runtime AI."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

from orari_agent.ai_tools import AiToolExecutor
from orari_agent.storage.week_parser import current_or_next_week_bounds


@dataclass(frozen=True)
class AgentContext:
    week_start: str
    week_end: str
    active_notes_count: int
    active_memories_count: int
    has_latest_schedule: bool
    latest_schedule_week: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AgentContextLoader:
    """Carica il minimo contesto persistente necessario prima dell'interpretazione."""

    def __init__(self, tools: AiToolExecutor) -> None:
        self.tools = tools

    def load(self) -> AgentContext:
        week_start, week_end = current_or_next_week_bounds()
        notes = self.tools.notes_repository.active_for_week(
            week_start.isoformat(), week_end.isoformat()
        )
        memories = self.tools.operational_memory_repository.list_active()
        latest = getattr(self.tools.schedule_service, "schedules_repository", None)
        latest_row = latest.latest() if latest is not None else None
        latest_week = (
            f"{latest_row['week_start']} / {latest_row['week_end']}"
            if latest_row is not None
            else None
        )
        return AgentContext(
            week_start=week_start.isoformat(),
            week_end=week_end.isoformat(),
            active_notes_count=len(notes),
            active_memories_count=len(memories),
            has_latest_schedule=latest_row is not None,
            latest_schedule_week=latest_week,
        )
