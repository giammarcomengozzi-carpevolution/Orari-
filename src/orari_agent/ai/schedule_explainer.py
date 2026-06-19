"""Spiegazioni sull'ultimo orario generato."""
from __future__ import annotations

import json
from orari_agent.storage.schedules_repository import SchedulesRepository

class ScheduleExplainer:
    def __init__(self, schedules_repository: SchedulesRepository) -> None:
        self.schedules_repository = schedules_repository

    def explain(self, question: str = "") -> str:
        latest = self.schedules_repository.latest()
        if latest is None:
            return "Non ho ancora un orario generato da spiegare."
        snapshot = self.schedules_repository.latest_snapshot()
        q = question.lower()
        if snapshot:
            data = json.loads(snapshot["snapshot_json"])
            if "note" in q:
                notes = data.get("notes_used", [])
                return "Note usate per l'ultimo orario:\n" + ("\n".join(f"• {n}" for n in notes) if notes else "• nessuna")
            if "memori" in q:
                memories = data.get("memories_used", [])
                return "Memorie usate per l'ultimo orario:\n" + ("\n".join(f"• {m}" for m in memories) if memories else "• nessuna")
            if "proble" in q or "non ti torna" in q:
                val = data.get("validation", {})
                crit = val.get("critical_conflicts", [])
                alerts = val.get("informational_alerts", [])
                return "Conflitti critici: " + ("nessuno" if not crit else "\n" + "\n".join(f"• {c.get('message')}" for c in crit)) + "\nAlert: " + ("nessuno" if not alerts else "\n" + "\n".join(f"• {a.get('message')}" for a in alerts))
        warnings = latest["warnings"] or "nessun conflitto critico"
        return f"Ultimo orario {latest['week_start']} / {latest['week_end']}.\n{latest['summary']}\nAvvisi: {warnings}"
