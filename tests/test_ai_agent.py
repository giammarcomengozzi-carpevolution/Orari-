from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace


from orari_agent.ai_agent import AiAgent, MISSING_AI_KEY_MESSAGE
from orari_agent.ai_tools import AiToolExecutor, ToolExecutionResult
from orari_agent.bot import commands
from orari_agent.storage.ai_repository import AiConversationRepository
from orari_agent.storage.db import connect
from orari_agent.storage.notes_repository import NotesRepository
from orari_agent.storage.operational_memory_repository import (
    OperationalMemoryRepository,
)
from orari_agent.storage.wife_calendar_repository import WifeCalendarRepository


class FakeResponder:
    def __init__(self, payload: str | dict):
        self.payload = payload

    def respond(self, user_message: str) -> str:
        if isinstance(self.payload, str):
            return self.payload
        return json.dumps(self.payload)


class FakeScheduleService:
    def __init__(self):
        self.calls = []

    def generate_for_week(self, week_start: str, week_end: str):
        self.calls.append((week_start, week_end))
        pdf = Path("/tmp/orari-test.pdf")
        pdf.write_bytes(b"pdf")
        return SimpleNamespace(
            pdf_path=pdf,
            summary=f"Orario generato per {week_start} / {week_end}.",
            warnings=["warning di test"],
            notes=[],
            memories=[],
        )


class FakeMessage:
    def __init__(self, text: str):
        self.text = text
        self.replies = []
        self.documents = []

    async def reply_text(self, text: str, **kwargs):
        self.replies.append(text)

    async def reply_document(self, **kwargs):
        self.documents.append(kwargs)


class FakeUser:
    id = 123


class FakeUpdate:
    def __init__(self, text: str = ""):
        self.effective_message = FakeMessage(text)
        self.effective_user = FakeUser()


def _context(bot_data: dict, args: list[str] | None = None):
    return SimpleNamespace(
        application=SimpleNamespace(bot_data=bot_data), args=args or [], user_data={}
    )


def _agent(tmp_path, responder_payload):
    connection = connect(tmp_path / "orari.sqlite3")
    notes = NotesRepository(connection)
    memories = OperationalMemoryRepository(connection)
    wife = WifeCalendarRepository(connection)
    schedule_service = FakeScheduleService()
    tools = AiToolExecutor(
        notes,
        memories,
        schedule_service,  # type: ignore[arg-type]
        wife,
        tmp_path / "orari.sqlite3",
        tmp_path,
        tmp_path / "backups",
    )
    repo = AiConversationRepository(connection)
    return (
        AiAgent(FakeResponder(responder_payload), tools, repo),
        notes,
        memories,
        schedule_service,
        repo,
    )


def test_bot_starts_without_openai_api_key(tmp_path):
    from orari_agent.bot.app import build_application
    from orari_agent.config import BotConfig

    app = build_application(
        BotConfig(
            telegram_bot_token="123:ABC",
            allowed_telegram_user_id=123,
            database_path=tmp_path / "orari.sqlite3",
            output_dir=tmp_path / "out",
            openai_api_key=None,
        )
    )

    assert app.bot_data["ai_agent"].configured is False


def test_commands_still_work_without_ai(tmp_path):
    connection = connect(tmp_path / "orari.sqlite3")
    bot_data = {
        "allowed_user_id": 123,
        "notes_repository": NotesRepository(connection),
        "schedule_service": object(),
        "wife_calendar_repository": WifeCalendarRepository(connection),
        "operational_memory_repository": OperationalMemoryRepository(connection),
    }
    update = FakeUpdate()

    asyncio.run(commands.aiuto(update, _context(bot_data)))

    assert "/nota testo" in update.effective_message.replies[0]


def test_free_text_missing_ai_key_message(tmp_path):
    connection = connect(tmp_path / "orari.sqlite3")
    bot_data = {
        "allowed_user_id": 123,
        "notes_repository": NotesRepository(connection),
        "schedule_service": object(),
        "wife_calendar_repository": WifeCalendarRepository(connection),
        "operational_memory_repository": OperationalMemoryRepository(connection),
        "ai_agent": AiAgent(
            None, SimpleNamespace(), AiConversationRepository(connection)
        ),
    }
    update = FakeUpdate("Giovedì sono dal commercialista")

    asyncio.run(commands.free_text(update, _context(bot_data)))

    assert update.effective_message.replies == [MISSING_AI_KEY_MESSAGE]


def test_ai_parsed_note_triggers_add_weekly_note(tmp_path):
    agent, notes, *_ = _agent(
        tmp_path,
        {
            "user_message": "Ho capito e salvo la nota.",
            "action": "save_note",
            "tool_calls": [
                {
                    "name": "add_weekly_note",
                    "arguments": {
                        "text": "Giovedì Gianmarco commercialista 10-12",
                        "week_request": "settimana prossima",
                    },
                }
            ],
            "needs_confirmation": False,
            "confidence": "high",
        },
    )

    result = agent.handle_message(
        123, "Giovedì sono dal commercialista dalle 10 alle 12"
    )

    saved = notes.active_for_week("2026-06-15", "2026-06-21")
    assert len(saved) == 1
    assert "Giovedì Gianmarco" in saved[0].raw_text
    assert "Nota salvata" in result.user_message
    assert "La userò" in result.user_message


def test_ai_memory_phrase_triggers_add_operational_memory(tmp_path):
    agent, _, memories, *_ = _agent(
        tmp_path,
        {
            "user_message": "Salvo questa memoria operativa.",
            "action": "save_memory",
            "tool_calls": [
                {
                    "name": "add_operational_memory",
                    "arguments": {"text": "Lorenzo è in ferie dal 10 al 15 agosto"},
                }
            ],
            "needs_confirmation": False,
            "confidence": "high",
        },
    )

    result = agent.handle_message(
        123, "Ricordati che Lorenzo è in ferie dal 10 al 15 agosto"
    )

    active = memories.list_active()
    assert len(active) == 1
    assert "Lorenzo" in active[0].raw_text
    assert "Memoria operativa salvata" in result.user_message


def test_ai_generation_request_triggers_generate_schedule(tmp_path):
    agent, _, _, schedule_service, _ = _agent(
        tmp_path,
        {
            "user_message": "Genero l'orario richiesto.",
            "action": "generate",
            "tool_calls": [
                {
                    "name": "generate_schedule",
                    "arguments": {"week_request": "settimana prossima"},
                }
            ],
            "needs_confirmation": False,
            "confidence": "high",
        },
    )

    result = agent.handle_message(123, "Generami l'orario della prossima settimana")

    assert schedule_service.calls == [("2026-06-15", "2026-06-21")]
    assert result.tool_results[0].generated_schedule is not None
    assert "Conflitti critici" in result.user_message


def test_destructive_action_requires_confirmation(tmp_path):
    agent, notes, _, _, repo = _agent(
        tmp_path,
        {
            "user_message": "Cancellerò le note della settimana prossima.",
            "action": "delete_notes",
            "tool_calls": [
                {
                    "name": "delete_weekly_notes_for_week",
                    "arguments": {"week_request": "settimana prossima"},
                }
            ],
            "needs_confirmation": False,
            "confidence": "high",
        },
    )
    notes.add(
        "Nota da tenere finché non confermo",
        __import__(
            "orari_agent.storage.week_parser", fromlist=["parse_note_metadata"]
        ).parse_note_metadata("settimana prossima Nota"),
    )

    result = agent.handle_message(
        123, "Cancella tutte le note della settimana prossima"
    )

    assert "Confermi" in result.user_message
    assert repo.get_pending_action(123) is not None
    assert len(notes.active_for_week("2026-06-15", "2026-06-21")) == 1


def test_confirmation_executes_pending_action(tmp_path):
    agent, notes, _, _, _ = _agent(
        tmp_path,
        {
            "user_message": "Cancellerò le note.",
            "action": "delete_notes",
            "tool_calls": [
                {
                    "name": "delete_weekly_notes_for_week",
                    "arguments": {"week_request": "settimana prossima"},
                }
            ],
            "needs_confirmation": True,
            "confidence": "high",
        },
    )
    from orari_agent.storage.week_parser import parse_note_metadata

    notes.add(
        "Nota da cancellare",
        parse_note_metadata("settimana prossima Nota da cancellare"),
    )
    first = agent.handle_message(123, "Cancella tutte le note della settimana prossima")
    second = agent.handle_message(123, "confermo")

    assert "Confermi" in first.user_message
    assert "Azione confermata" in second.user_message
    assert notes.active_for_week("2026-06-15", "2026-06-21") == []


def test_invalid_ai_json_does_not_execute_actions(tmp_path):
    agent, notes, *_ = _agent(tmp_path, "non è json")

    result = agent.handle_message(123, "Angelo venerdì mattina non c'è")

    assert result.invalid_json is True
    assert notes.active_for_week("2026-06-15", "2026-06-21") == []
    assert "nessuna azione" in result.user_message.lower()


def test_ai_response_summarizes_saved_constraints(tmp_path):
    agent, *_ = _agent(
        tmp_path,
        {
            "user_message": "Perfetto, ho interpretato: Angelo assente venerdì mattina.",
            "action": "save_note",
            "tool_calls": [
                {
                    "name": "add_weekly_note",
                    "arguments": {
                        "text": "Angelo venerdì mattina non c'è",
                        "week_request": "settimana prossima",
                    },
                }
            ],
            "needs_confirmation": False,
            "confidence": "high",
        },
    )

    result = agent.handle_message(123, "Angelo venerdì mattina non c'è")

    assert "Angelo assente venerdì mattina" in result.user_message
    assert "Settimana:" in result.user_message


def test_first_person_weekly_note_maps_to_gianmarco(tmp_path):
    agent, notes, *_ = _agent(
        tmp_path,
        {
            "user_message": "Salvo: Gianmarco Mengozzi dal commercialista giovedì 10-12.",
            "action": "save_note",
            "tool_calls": [
                {
                    "name": "add_weekly_note",
                    "arguments": {
                        "text": "sono dal commercialista giovedì dalle 10 alle 12",
                        "week_request": "settimana prossima",
                    },
                }
            ],
            "needs_confirmation": False,
            "confidence": "high",
        },
    )

    agent.handle_message(123, "sono dal commercialista giovedì dalle 10 alle 12")

    saved = notes.active_for_week("2026-06-15", "2026-06-21")
    assert len(saved) == 1
    assert saved[0].person == "Giammarco Mengozzi"
    assert saved[0].constraint_type == "impegno_esterno"


def test_ai_multi_person_message_saves_separate_constraints(tmp_path):
    agent, notes, *_ = _agent(
        tmp_path,
        {
            "user_message": (
                "Salvo due vincoli separati: Gianmarco Mengozzi dal commercialista "
                "giovedì 10-12; Lorenzo Sansavini esce sabato alle 15."
            ),
            "action": "save_note",
            "tool_calls": [
                {
                    "name": "add_weekly_note",
                    "arguments": {
                        "text": "Giovedì Gianmarco Mengozzi dal commercialista dalle 10 alle 12",
                        "week_request": "settimana prossima",
                    },
                },
                {
                    "name": "add_weekly_note",
                    "arguments": {
                        "text": "Sabato Lorenzo Sansavini esce alle 15",
                        "week_request": "settimana prossima",
                    },
                },
            ],
            "needs_confirmation": False,
            "confidence": "high",
        },
    )

    result = agent.handle_message(
        123,
        "giovedì sono dal commercialista e sabato Lorenzo esce alle 15",
    )

    saved = notes.active_for_week("2026-06-15", "2026-06-21")
    assert len(saved) == 2
    assert [note.person for note in saved] == [
        "Giammarco Mengozzi",
        "Lorenzo Sansavini",
    ]
    assert "Gianmarco Mengozzi dal commercialista" in result.user_message
    assert "Lorenzo Sansavini esce" in result.user_message


def test_ai_reply_summary_does_not_assign_first_person_commitment_to_lorenzo(tmp_path):
    agent, notes, *_ = _agent(
        tmp_path,
        {
            "user_message": "Ho registrato che giovedì prossimo Lorenzo sarà dal commercialista.",
            "action": "save_note",
            "tool_calls": [
                {
                    "name": "add_weekly_note",
                    "arguments": {
                        "text": "Giovedì Gianmarco Mengozzi dal commercialista dalle 10 alle 12",
                        "week_request": "settimana prossima",
                    },
                }
            ],
            "needs_confirmation": False,
            "confidence": "high",
        },
    )

    result = agent.handle_message(
        123,
        "sono dal commercialista giovedì dalle 10 alle 12",
    )

    saved = notes.active_for_week("2026-06-15", "2026-06-21")
    assert len(saved) == 1
    assert saved[0].person == "Giammarco Mengozzi"
    assert "Lorenzo sarà dal commercialista" not in result.user_message
    assert "Gianmarco Mengozzi dal commercialista" in result.user_message
