import asyncio
from datetime import date

from orari_agent.bot import commands
from orari_agent.bot.schedule_service import ScheduleService
from orari_agent.people import ANGELO, GIAMMARCO, LORENZO
from orari_agent.scheduling.memory_adapter import memories_to_weekly_instruction
from orari_agent.storage.db import connect
from orari_agent.storage.notes_repository import NotesRepository
from orari_agent.storage.operational_memory_parser import parse_operational_memory
from orari_agent.storage.operational_memory_repository import (
    OperationalMemoryRepository,
)
from orari_agent.storage.schedules_repository import SchedulesRepository
from orari_agent.storage.wife_calendar_repository import WifeCalendarRepository

TODAY = date(2026, 6, 10)


def _repo(tmp_path):
    connection = connect(tmp_path / "orari.sqlite3")
    return OperationalMemoryRepository(connection)


def test_add_single_day_absence_memory(tmp_path):
    repo = _repo(tmp_path)
    memory = repo.add(
        parse_operational_memory("Angelo assente il 27 giugno", today=TODAY)
    )

    assert memory.id == 1
    assert memory.person == ANGELO.full_name
    assert memory.start_date == "2026-06-27"
    assert memory.end_date == "2026-06-27"
    assert memory.constraint_type == "assenza"


def test_add_date_range_holiday_memory(tmp_path):
    repo = _repo(tmp_path)
    memory = repo.add(
        parse_operational_memory("Lorenzo in ferie dal 10 al 15 agosto", today=TODAY)
    )

    assert memory.person == LORENZO.full_name
    assert memory.start_date == "2026-08-10"
    assert memory.end_date == "2026-08-15"
    assert memory.constraint_type == "ferie/assenza"


def test_add_partial_morning_absence_memory(tmp_path):
    repo = _repo(tmp_path)
    memory = repo.add(
        parse_operational_memory("Angelo non c’è il 3 settembre mattina", today=TODAY)
    )

    assert memory.person == ANGELO.full_name
    assert memory.start_date == "2026-09-03"
    assert memory.start_time == "07:30"
    assert memory.end_time == "14:00"


def test_add_gianmarco_external_work_memory_with_time_range(tmp_path):
    repo = _repo(tmp_path)
    memory = repo.add(
        parse_operational_memory(
            "Gianmarco attività aziendale esterna il 12 luglio dalle 10 alle 12",
            today=TODAY,
        )
    )

    assert memory.person == GIAMMARCO.full_name
    assert memory.constraint_type == "impegno_esterno"
    assert memory.start_date == "2026-07-12"
    assert memory.start_time == "10:00"
    assert memory.end_time == "12:00"


def test_add_weekly_recurring_thursday_morning_memory(tmp_path):
    repo = _repo(tmp_path)
    memory = repo.add(
        parse_operational_memory(
            "Gianmarco dal commercialista ogni giovedì mattina", today=TODAY
        )
    )

    assert memory.person == GIAMMARCO.full_name
    assert memory.recurrence_rule == "WEEKLY:THURSDAY:MORNING"
    assert memory.start_time == "07:30"
    assert memory.end_time == "14:00"


def test_listing_memories(tmp_path):
    repo = _repo(tmp_path)
    repo.add(parse_operational_memory("Angelo assente il 27 giugno", today=TODAY))
    repo.add(
        parse_operational_memory("Lorenzo in ferie dal 10 al 15 agosto", today=TODAY)
    )

    memories = repo.list_active()

    assert [memory.raw_text for memory in memories] == [
        "Angelo assente il 27 giugno",
        "Lorenzo in ferie dal 10 al 15 agosto",
    ]


def test_deleting_one_memory(tmp_path):
    repo = _repo(tmp_path)
    memory = repo.add(
        parse_operational_memory("Angelo assente il 27 giugno", today=TODAY)
    )

    assert repo.delete(memory.id) is True
    assert repo.delete(memory.id) is False
    assert repo.list_active() == []


def test_reset_requires_confirmation_semantics_are_repository_reset(tmp_path):
    repo = _repo(tmp_path)
    repo.add(parse_operational_memory("Angelo assente il 27 giugno", today=TODAY))

    assert repo.list_active()
    assert repo.reset() == 1
    assert repo.list_active() == []


def test_schedule_generation_applies_memory_to_selected_week(tmp_path):
    connection = connect(tmp_path / "orari.sqlite3")
    memory_repo = OperationalMemoryRepository(connection)
    memory_repo.add(
        parse_operational_memory("Lorenzo in ferie dal 10 al 15 agosto", today=TODAY)
    )
    service = ScheduleService(
        NotesRepository(connection),
        SchedulesRepository(connection),
        WifeCalendarRepository(connection),
        memory_repo,
        tmp_path,
    )

    result = service.generate_for_week("2026-08-10", "2026-08-16")

    assert "Memorie operative: 1" in result.summary
    assert result.memories[0].person == LORENZO.full_name
    assert result.pdf_path.exists()


def test_telegram_generation_summary_includes_counts_and_filename(tmp_path):
    from orari_agent.storage.week_parser import parse_note_metadata

    connection = connect(tmp_path / "orari.sqlite3")
    notes_repo = NotesRepository(connection)
    notes_repo.add(
        "Sabato Angelo è in ferie",
        parse_note_metadata("Sabato Angelo è in ferie", today=TODAY),
    )
    memory_repo = OperationalMemoryRepository(connection)
    memory_repo.add(
        parse_operational_memory("Lorenzo in ferie dal 15 al 21 giugno", today=TODAY)
    )
    service = ScheduleService(
        notes_repo,
        SchedulesRepository(connection),
        WifeCalendarRepository(connection),
        memory_repo,
        tmp_path,
    )

    result = service.generate_for_week("2026-06-15", "2026-06-21")

    assert "Orario generato per 2026-06-15 / 2026-06-21." in result.summary
    assert "Note usate: 1." in result.summary
    assert "Memorie operative: 1." in result.summary
    assert f"Conflitti critici: {len(result.warnings)}." in result.summary
    assert (
        "PDF allegato: Orario_CarpeEvolution_Tenuta_2026-06-15_2026-06-21.pdf."
        in result.summary
    )


def test_unknown_memory_is_preserved_but_does_not_break_generation(tmp_path):
    repo = _repo(tmp_path)
    memory = repo.add(
        parse_operational_memory("Ricordati che c'è una cosa importante", today=TODAY)
    )

    instruction = memories_to_weekly_instruction([memory], "2026-06-15", "2026-06-21")

    assert instruction.unknown_notes == [
        f"Memoria {memory.id}: c'è una cosa importante"
    ]
    assert "c'è una cosa importante" in instruction.weekly_notes[0]


class _FakeUser:
    id = 123


class _FakeMessage:
    def __init__(self):
        self.replies = []

    async def reply_text(self, text, **kwargs):
        self.replies.append(text)


class _FakeUpdate:
    def __init__(self):
        self.effective_user = _FakeUser()
        self.effective_message = _FakeMessage()


class _FakeApplication:
    def __init__(self, repo):
        self.bot_data = {
            "allowed_user_id": 123,
            "notes_repository": None,
            "schedule_service": None,
            "wife_calendar_repository": None,
            "operational_memory_repository": repo,
        }


class _FakeContext:
    def __init__(self, repo, args):
        self.application = _FakeApplication(repo)
        self.args = args


def test_memory_reset_command_requires_confirmation(tmp_path):
    repo = _repo(tmp_path)
    repo.add(parse_operational_memory("Angelo assente il 27 giugno", today=TODAY))
    update = _FakeUpdate()
    context = _FakeContext(repo, [])

    asyncio.run(commands.memoria_reset(update, context))

    assert repo.list_active()
    assert update.effective_message.replies == [
        "Per sicurezza, ripeti con: /memoria_reset confermo"
    ]


def test_memory_reset_command_with_confirmation_deletes_memories(tmp_path):
    repo = _repo(tmp_path)
    repo.add(parse_operational_memory("Angelo assente il 27 giugno", today=TODAY))
    update = _FakeUpdate()
    context = _FakeContext(repo, ["confermo"])

    asyncio.run(commands.memoria_reset(update, context))

    assert repo.list_active() == []
    assert update.effective_message.replies == [
        "Memoria operativa svuotata: 1 regole archiviate."
    ]
