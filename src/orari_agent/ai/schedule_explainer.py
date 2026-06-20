"""Spiegazioni operative sull'ultimo orario generato."""
from __future__ import annotations

import json
from typing import Any

from orari_agent.people import LORENZO
from orari_agent.storage.schedules_repository import SchedulesRepository


class ScheduleExplainer:
    def __init__(self, schedules_repository: SchedulesRepository) -> None:
        self.schedules_repository = schedules_repository

    def explain(self, question: str = "") -> str:
        latest = self.schedules_repository.latest()
        if latest is None:
            return "Non ho ancora un orario generato da spiegare."
        data = self._snapshot_data()
        q = question.lower()
        if data:
            if "note" in q:
                return _list_items("Note usate per l'ultimo orario", data.get("notes_used", []))
            if "memori" in q:
                return _list_items("Memorie usate per l'ultimo orario", data.get("memories_used", []))
            if "proble" in q or "non ti torna" in q or "conflitt" in q:
                return _problems(data)
            if "quante ore" in q and "lorenzo" in q:
                return _person_hours(data, LORENZO.full_name)
            if "chi chiude" in q:
                return _who_closes(data, q)
            if "perch" in q or "perché" in q or "perche" in q:
                return _why(data, q)
            if "angelo" in q and "lago" in q and "venerd" in q:
                return _angelo_friday(data)
        warnings = latest["warnings"] or "nessun conflitto critico"
        return f"Ultimo orario {latest['week_start']} / {latest['week_end']}.\n{latest['summary']}\nAvvisi: {warnings}"

    def _snapshot_data(self) -> dict[str, Any] | None:
        snapshot = self.schedules_repository.latest_snapshot()
        if snapshot is None:
            return None
        return json.loads(snapshot["snapshot_json"])


def _list_items(title: str, items: list[str]) -> str:
    return f"{title}:\n" + ("\n".join(f"• {item}" for item in items) if items else "• nessuna")


def _problems(data: dict[str, Any]) -> str:
    val = data.get("validation", {})
    crit = val.get("critical_conflicts", [])
    alerts = val.get("informational_alerts", [])
    return (
        "Conflitti critici: "
        + ("nessuno" if not crit else "\n" + "\n".join(f"• {c.get('message')}" for c in crit))
        + "\nAlert: "
        + ("nessuno" if not alerts else "\n" + "\n".join(f"• {a.get('message')}" for a in alerts))
    )


def _person_hours(data: dict[str, Any], person: str) -> str:
    hours = float((data.get("weekly_hours") or {}).get(person, 0.0))
    delta = hours - 40.0 if person == LORENZO.full_name else 0.0
    if person == LORENZO.full_name:
        if abs(delta) < 0.01:
            return "Lorenzo fa 40h: è in target."
        direction = "sopra" if delta > 0 else "sotto"
        return f"Lorenzo fa {hours:.1f}h: {direction} il target 40h di {abs(delta):.1f}h. È un alert informativo, non un conflitto critico."
    return f"{person} fa {hours:.1f}h nell'ultimo orario."


def _who_closes(data: dict[str, Any], question: str) -> str:
    day = _day_from_question(question) or "venerdì"
    assignments = _assignments_for_day(data, day)
    if not assignments:
        return f"Non trovo turni per {day} nell'ultimo orario."
    closing = max(assignments, key=lambda item: _to_minutes(str(item.get("end", "00:00"))))
    return (
        f"{day.capitalize()} chiude {closing.get('person')} a {closing.get('location')} "
        f"alle {closing.get('end')} ({closing.get('task')})."
    )


def _why(data: dict[str, Any], question: str) -> str:
    if "lorenzo" in question and "domen" in question:
        sunday = [a for a in _assignments_for_day(data, "domenica") if "Lorenzo" in str(a.get("person"))]
        if sunday:
            latest = max(sunday, key=lambda item: _to_minutes(str(item.get("end", "00:00"))))
            return (
                f"Perché domenica il lago può richiedere copertura lunga fino alle 23:00 nel periodo stagionale. "
                f"Lorenzo è assegnato a {latest.get('location')} {latest.get('start')}-{latest.get('end')} ({latest.get('task')})."
            )
        return "Non trovo Lorenzo assegnato domenica nell'ultimo orario."
    if "angelo" in question and "venerd" in question and "lago" in question:
        return _angelo_friday(data)
    return _problems(data)


def _angelo_friday(data: dict[str, Any]) -> str:
    friday = [a for a in _assignments_for_day(data, "venerdì") if "Angelo" in str(a.get("person"))]
    lake = [a for a in friday if str(a.get("location", "")).lower() == "lago"]
    shop = [a for a in friday if str(a.get("location", "")).lower() == "negozio"]
    if lake:
        lake_text = ", ".join(f"{a.get('start')}-{a.get('end')}" for a in lake)
        shop_text = ", ".join(f"{a.get('start')}-{a.get('end')}" for a in shop) or "negozio non trovato nello snapshot"
        return f"Angelo è al lago venerdì sera perché dopo il negozio può supportare la Tenuta. Negozio: {shop_text}. Lago: {lake_text}."
    return "Non trovo Angelo assegnato al lago venerdì sera nell'ultimo orario."


def _assignments_for_day(data: dict[str, Any], day: str) -> list[dict[str, Any]]:
    return [a for a in data.get("assignments", []) if str(a.get("day", "")).lower().startswith(day[:6])]


def _day_from_question(question: str) -> str | None:
    for day in ("lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"):
        if day[:6] in question:
            return day
    return None


def _to_minutes(value: str) -> int:
    try:
        hours, minutes = value.split(":", 1)
        return int(hours) * 60 + int(minutes)
    except Exception:  # noqa: BLE001
        return 0
