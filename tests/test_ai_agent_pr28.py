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

import asyncio
from pathlib import Path

from orari_agent.ai_agent import AiAgent
from orari_agent.bot import commands
from orari_agent.storage.ai_repository import AiConversationRepository


class TelegramMessage:
    def __init__(self, text: str = ""):
        self.text = text
        self.replies: list[str] = []
        self.documents: list[dict] = []
        self.voice = None
        self.audio = None
        self.document = None
        self.photo = None
        self.caption = ""

    async def reply_text(self, text: str, **kwargs):
        self.replies.append(text)

    async def reply_document(self, **kwargs):
        self.documents.append(kwargs)


class TelegramUser:
    id = 123


class TelegramUpdate:
    def __init__(self, text: str = ""):
        self.effective_message = TelegramMessage(text)
        self.effective_user = TelegramUser()


def telegram_context(bot_data: dict, args: list[str] | None = None):
    return SimpleNamespace(application=SimpleNamespace(bot_data=bot_data), args=args or [], user_data={})


class SnapshotScheduleService:
    def __init__(self, tmp_path: Path, schedules_repository: SchedulesRepository):
        self.tmp_path = tmp_path
        self.schedules_repository = schedules_repository
        self.calls: list[tuple[str, str]] = []

    def generate_for_week(self, week_start: str, week_end: str):
        self.calls.append((week_start, week_end))
        pdf = self.tmp_path / "orario.pdf"
        pdf.write_bytes(b"pdf")
        schedule_id = self.schedules_repository.add(
            week_start=week_start,
            week_end=week_end,
            pdf_path=str(pdf),
            summary=f"Orario generato per {week_start} / {week_end}.",
            warnings="",
        )
        self.schedules_repository.save_snapshot(
            schedule_id=schedule_id,
            week_start=week_start,
            week_end=week_end,
            snapshot={
                "week_start": week_start,
                "week_end": week_end,
                "notes_used": ["Venerdì Angelo dopo il negozio al lago fino alle 23"],
                "memories_used": [],
                "weekly_hours": {"Lorenzo Sansavini": 41.5},
                "daily_hours": {"Domenica": {"Lorenzo Sansavini": 11.0}},
                "assignments": [
                    {"day": "Venerdì", "date": "2026-06-26", "person": "Angelo Antonelli", "location": "Negozio", "start": "09:00", "end": "12:30", "task": "NEGOZIO", "working_hours": 7.5},
                    {"day": "Venerdì", "date": "2026-06-26", "person": "Angelo Antonelli", "location": "Negozio", "start": "15:30", "end": "19:30", "task": "NEGOZIO", "working_hours": 7.5},
                    {"day": "Venerdì", "date": "2026-06-26", "person": "Angelo Antonelli", "location": "Lago", "start": "19:30", "end": "23:00", "task": "EVENTO SERALE LAGO", "working_hours": 3.5},
                    {"day": "Domenica", "date": "2026-06-28", "person": "Lorenzo Sansavini", "location": "Lago", "start": "11:00", "end": "23:00", "task": "CHIUSURA LAGO 23:00", "working_hours": 11.0},
                ],
                "validation": {"critical_conflicts": [], "informational_alerts": [{"message": "Lorenzo sopra target 40h"}]},
            },
        )
        return SimpleNamespace(
            pdf_path=pdf,
            summary=f"Orario generato per {week_start} / {week_end}.",
            warnings=[],
            notes=[],
            memories=[],
        )


def _telegram_bot_data(tmp_path):
    connection = connect(tmp_path / "orari.sqlite3")
    notes = NotesRepository(connection)
    memories = OperationalMemoryRepository(connection)
    schedules = SchedulesRepository(connection)
    schedule_service = SnapshotScheduleService(tmp_path, schedules)
    tools = AiToolExecutor(notes, memories, schedule_service, WifeCalendarRepository(connection), tmp_path / "orari.sqlite3", tmp_path, tmp_path / "backups")
    audit = AiAuditRepository(connection)
    agent = AiAgent(None, tools, AiConversationRepository(connection), audit)
    return {
        "allowed_user_id": 123,
        "notes_repository": notes,
        "operational_memory_repository": memories,
        "wife_calendar_repository": WifeCalendarRepository(connection),
        "schedule_service": schedule_service,
        "ai_agent": agent,
        "ai_audit_repository": audit,
        "database_path": tmp_path / "orari.sqlite3",
        "data_dir": tmp_path,
        "backup_dir": tmp_path / "backups",
        "voice_debug": False,
    }, notes, schedules, schedule_service


def test_telegram_free_text_angelo_after_shop_saves_correct_note(tmp_path):
    bot_data, notes, *_ = _telegram_bot_data(tmp_path)
    update = TelegramUpdate("Venerdì Angelo dopo il negozio viene al lago fino alle 23")

    asyncio.run(commands.free_text(update, telegram_context(bot_data)))

    saved = notes.active_for_week("2026-06-22", "2026-06-28")
    assert len(saved) == 1
    assert "Angelo" in saved[0].raw_text
    assert "19:30-23:00" in saved[0].raw_text
    assert "negozio" in saved[0].raw_text.lower()


def test_telegram_generation_stores_latest_schedule_snapshot(tmp_path):
    bot_data, _, schedules, schedule_service = _telegram_bot_data(tmp_path)
    update = TelegramUpdate("Genera settimana prossima")

    asyncio.run(commands.free_text(update, telegram_context(bot_data)))

    assert schedule_service.calls == [("2026-06-22", "2026-06-28")]
    assert schedules.latest_snapshot() is not None
    assert update.effective_message.documents


def test_explain_who_closes_friday_and_why_lorenzo_sunday(tmp_path):
    bot_data, _, schedules, schedule_service = _telegram_bot_data(tmp_path)
    schedule_service.generate_for_week("2026-06-22", "2026-06-28")
    explainer = ScheduleExplainer(schedules)

    friday = explainer.explain("Chi chiude venerdì?")
    sunday = explainer.explain("Perché Lorenzo chiude domenica?")

    assert "Angelo Antonelli" in friday
    assert "23:00" in friday
    assert "stagionale" in sunday
    assert "Lorenzo" in sunday


def test_ambiguous_lui_asks_clarification_and_saves_nothing(tmp_path):
    bot_data, notes, *_ = _telegram_bot_data(tmp_path)
    update = TelegramUpdate("Venerdì lui va al lago")

    asyncio.run(commands.free_text(update, telegram_context(bot_data)))

    assert "Chi intendi" in update.effective_message.replies[0]
    assert notes.active_for_week("2026-06-22", "2026-06-28") == []


def test_debug_ai_shows_latest_interpreted_intent(tmp_path):
    bot_data, *_ = _telegram_bot_data(tmp_path)
    update = TelegramUpdate("Venerdì lui va al lago")
    asyncio.run(commands.free_text(update, telegram_context(bot_data)))
    debug_update = TelegramUpdate()

    asyncio.run(commands.debug_ai(debug_update, telegram_context(bot_data)))

    assert "Intento: clarification_required" in debug_update.effective_message.replies[0]


class FakeTelegramFile:
    async def download_to_drive(self, custom_path):
        Path(custom_path).write_bytes(b"audio")


class FakeVoiceAttachment:
    file_unique_id = "abc"
    file_size = 10

    async def get_file(self):
        return FakeTelegramFile()


class FakeTranscriber:
    def transcribe(self, audio_path):
        return "Venerdì Angelo dopo il negozio viene al lago fino alle 23"


def test_voice_transcript_routes_through_same_agent_path(tmp_path):
    bot_data, notes, *_ = _telegram_bot_data(tmp_path)
    bot_data["audio_transcriber"] = FakeTranscriber()
    bot_data["audio_dir"] = tmp_path / "audio"
    update = TelegramUpdate()
    update.effective_message.voice = FakeVoiceAttachment()

    asyncio.run(commands.voice_message(update, telegram_context(bot_data)))

    saved = notes.active_for_week("2026-06-22", "2026-06-28")
    assert len(saved) == 1
    assert "19:30-23:00" in saved[0].raw_text
    assert any("Trascrizione" in reply for reply in update.effective_message.replies)
