"""Schemi strutturati per l'agente AI operativo."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Literal

Confidence = Literal["high", "medium", "low"]
IntentName = Literal[
    "save_constraint", "update_constraint", "delete_constraint", "list_constraints",
    "save_memory", "update_memory", "delete_memory", "list_memory",
    "generate_schedule", "regenerate_schedule", "explain_schedule",
    "ask_schedule_question", "backup", "help", "unknown", "clarification_required",
]

@dataclass(frozen=True)
class InterpretedAction:
    intent: IntentName
    confidence: Confidence
    requires_confirmation: bool
    person: str | None = None
    date: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    location: str | None = None
    constraint_type: str | None = None
    scope: str = "weekly"
    week_request: str = ""
    human_summary: str = ""
    tool_name: str | None = None
    tool_arguments: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass(frozen=True)
class ValidationIssue:
    date: str | None
    type: str
    message: str

@dataclass(frozen=True)
class StructuredValidationResult:
    valid: bool
    critical_conflicts: list[ValidationIssue] = field(default_factory=list)
    informational_alerts: list[ValidationIssue] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "critical_conflicts": [asdict(item) for item in self.critical_conflicts],
            "informational_alerts": [asdict(item) for item in self.informational_alerts],
        }
