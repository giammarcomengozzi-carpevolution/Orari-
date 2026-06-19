from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from orari_agent.ai.intent_router import AiIntentRouter
from orari_agent.ai.audit import AiAuditRepository
from orari_agent.ai.schedule_explainer import ScheduleExplainer
from orari_agent.ai_tools import AiToolExecutor
from orari_agent.storage.db import connect
from orari_agent.storage.notes_repository import NotesRepository
from orari_agent.storage.operational_memory_repository import OperationalMemoryRepository
from orari_agent.storage.schedules_repository import SchedulesRepository
from orari_agent.storage.wife_calendar_repository import WifeCalendarRepository


def test_router_first_person_maps_to_gianmarco():
    action = AiIntentRouter(today=date(2026, 6, 19)).interpret("Giovedì sono dal commercialista dalle 10 alle 12")
    assert action.person == "Giammarco Mengozzi"
    assert action.constraint_type == "external_work"
    assert action.start_time == "10:00"
    assert action.end_time == "12:00"


def test_router_angelo_friday_after_shop_until_23():
    action = AiIntentRouter(today=date(2026, 6, 19)).interpret("Venerdì Angelo dopo il negozio viene al lago fino alle 23")
    assert action.intent == "save_constraint"
    assert action.confidence == "high"
    assert action.person == "Angelo Antonelli"
    assert action.location == "Tenuta del Germano"
    assert action.start_time == "19:30"
    assert action.end_time == "23:00"
    assert "negozio" in action.tool_arguments["text"].lower()


def test_router_ambiguous_lui_asks_clarification():
    action = AiIntentRouter(today=date(2026, 6, 19)).interpret("Venerdì lui va al lago")
    assert action.intent == "clarification_required"
    assert action.requires_confirmation is True
    assert "Chi intendi" in action.human_summary


def test_router_settimana_prossima_generation():
    action = AiIntentRouter(today=date(2026, 6, 19)).interpret("Genera settimana prossima")
    assert action.intent == "generate_schedule"
    assert action.tool_arguments == {"week_request": "settimana prossima"}


def test_ai_audit_repository_persists_latest_event(tmp_path):
    connection = connect(tmp_path / "orari.sqlite3")
    audit = AiAuditRepository(connection)
    audit.add_event(telegram_user_id=123, raw_user_text="test", detected_intent="save_constraint", confidence="high", tool_called="add_weekly_note", tool_arguments={"text": "x"}, bot_response="ok")
    row = audit.latest_event(123)
    assert row is not None
    assert row["detected_intent"] == "save_constraint"
    assert row["tool_called"] == "add_weekly_note"


def test_tool_executor_explains_latest_schedule_notes(tmp_path):
    connection = connect(tmp_path / "orari.sqlite3")
    schedules = SchedulesRepository(connection)
    schedule_id = schedules.add(week_start="2026-06-22", week_end="2026-06-28", pdf_path="out.pdf", summary="Orario generato", warnings="")
    schedules.save_snapshot(schedule_id=schedule_id, week_start="2026-06-22", week_end="2026-06-28", snapshot={"notes_used": ["Angelo venerdì lago"], "memories_used": [], "validation": {"critical_conflicts": [], "informational_alerts": []}})
    assert "Angelo venerdì lago" in ScheduleExplainer(schedules).explain("Che note hai usato?")


def test_tool_executor_save_constraint_calls_repository(tmp_path):
    connection = connect(tmp_path / "orari.sqlite3")
    notes = NotesRepository(connection)
    schedules = SchedulesRepository(connection)
    fake_service = SimpleNamespace(schedules_repository=schedules)
    tools = AiToolExecutor(notes, OperationalMemoryRepository(connection), fake_service, WifeCalendarRepository(connection), tmp_path / "orari.sqlite3", tmp_path, tmp_path / "backups")
    result = tools.execute("add_weekly_note", {"text": "Venerdì Angelo dopo il negozio al lago fino alle 23", "week_request": "settimana prossima"})
    assert result.data["note_id"] > 0
    assert notes.active_for_week("2026-06-22", "2026-06-28")
