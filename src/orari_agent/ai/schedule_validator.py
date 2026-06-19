"""Validatore strutturato che separa conflitti critici e alert informativi."""
from __future__ import annotations

from orari_agent.ai.schemas import StructuredValidationResult, ValidationIssue
from orari_agent.models import WeeklySchedule
from orari_agent.people import LORENZO
from orari_agent.presentation import weekly_hour_totals, effective_shifts

class ScheduleValidator:
    def validate(self, schedule: WeeklySchedule, warnings: list[str] | None = None) -> StructuredValidationResult:
        critical = [ValidationIssue(None, _type_from_warning(w), w) for w in (warnings or [])]
        alerts: list[ValidationIssue] = []
        totals = weekly_hour_totals(schedule)
        lorenzo_hours = totals.get(LORENZO.full_name, 0.0)
        if lorenzo_hours and abs(lorenzo_hours - 40.0) > 0.01:
            direction = "sopra" if lorenzo_hours > 40 else "sotto"
            alerts.append(ValidationIssue(None, "lorenzo_40h_target", f"Lorenzo {direction} target 40h: {lorenzo_hours:.1f}h."))
        for shift in effective_shifts(schedule):
            if getattr(shift, "duration_hours", 0) > 8.0:
                alerts.append(ValidationIssue(getattr(shift, "date", None), "long_shift", f"Turno lungo: {shift.person} {shift.start}-{shift.end}."))
        return StructuredValidationResult(valid=not critical, critical_conflicts=critical, informational_alerts=alerts)

def _type_from_warning(warning: str) -> str:
    text = warning.lower()
    if "negozio" in text: return "missing_shop_coverage"
    if "evento serale" in text or "23:00" in text: return "missing_evening_coverage"
    if "lago" in text: return "missing_lake_coverage"
    if "sovrapp" in text or "conflitto" in text: return "impossible_overlap"
    return "critical_conflict"
