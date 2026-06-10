import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from orari_agent.bot import commands
from orari_agent.storage.db import connect
from orari_agent.storage.wife_calendar_repository import WifeCalendarRepository


class DummyMessage:
    def __init__(self, text="", caption="", photo=None):
        self.text = text
        self.caption = caption
        self.photo = photo or []
        self.replies = []

    async def reply_text(self, text):
        self.replies.append(text)


class DummyTelegramFile:
    async def download_to_drive(self, custom_path):
        Path(custom_path).write_bytes(b"fake image")


class DummyPhoto:
    async def get_file(self):
        return DummyTelegramFile()


def make_context(repository, tmp_path, args=None):
    return SimpleNamespace(
        args=args or [],
        user_data={},
        application=SimpleNamespace(
            bot_data={
                "allowed_user_id": 123,
                "notes_repository": None,
                "schedule_service": None,
                "wife_calendar_repository": repository,
                "wife_calendar_import_dir": str(tmp_path / "imports"),
            }
        ),
    )


def make_update(message):
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=123),
        effective_message=message,
    )


@pytest.fixture()
def wife_repository(tmp_path):
    connection = connect(tmp_path / "orari_bot.sqlite3")
    return WifeCalendarRepository(connection)


def test_bulk_import_m_dates(wife_repository, tmp_path):
    message = DummyMessage("/moglie_importa_m 2026-09-03,2026-09-10")
    context = make_context(wife_repository, tmp_path)

    asyncio.run(commands.moglie_importa_m(make_update(message), context))

    entries = wife_repository.list_entries("M")
    assert [entry.date for entry in entries] == ["2026-09-03", "2026-09-10"]
    assert entries[0].source == "telegram_bulk_import"
    assert "Date M salvate: 2" in message.replies[0]
    assert "Inserite: 2. Aggiornate: 0." in message.replies[0]


def test_invalid_date_handling(wife_repository, tmp_path):
    message = DummyMessage("/moglie_importa_m 2026-09-03,non-data,2026-02-31")
    context = make_context(wife_repository, tmp_path)

    asyncio.run(commands.moglie_importa_m(make_update(message), context))

    assert [entry.date for entry in wife_repository.list_entries("M")] == ["2026-09-03"]
    assert "Date ignorate perché non valide: non-data, 2026-02-31." in message.replies[0]


def test_duplicate_dates_handling(wife_repository, tmp_path):
    wife_repository.upsert_code("2026-09-03", "P", source="test")
    message = DummyMessage("/moglie_importa_m 2026-09-03,2026-09-03,2026-09-10")
    context = make_context(wife_repository, tmp_path)

    asyncio.run(commands.moglie_importa_m(make_update(message), context))

    entries = wife_repository.list_entries("M")
    assert [entry.date for entry in entries] == ["2026-09-03", "2026-09-10"]
    assert "Date M salvate: 2" in message.replies[0]
    assert "Inserite: 1. Aggiornate: 1." in message.replies[0]


def test_moglie_lista_m_filtering(wife_repository, tmp_path):
    wife_repository.upsert_code("2026-09-03", "M", source="test")
    wife_repository.upsert_code("2026-09-04", "P", source="test")
    message = DummyMessage()
    context = make_context(wife_repository, tmp_path, args=["M"])

    asyncio.run(commands.moglie_lista(make_update(message), context))

    assert "2026-09-03: M" in message.replies[0]
    assert "2026-09-04" not in message.replies[0]


def test_moglie_reset_requires_confirmation(wife_repository, tmp_path):
    wife_repository.upsert_code("2026-09-03", "M", source="test")
    message = DummyMessage()
    context = make_context(wife_repository, tmp_path)

    asyncio.run(commands.moglie_reset(make_update(message), context))

    assert "Per sicurezza" in message.replies[0]
    assert wife_repository.list_entries()


def test_moglie_reset_confermo_deletes_entries(wife_repository, tmp_path):
    wife_repository.upsert_code("2026-09-03", "M", source="test")
    message = DummyMessage()
    context = make_context(wife_repository, tmp_path, args=["confermo"])

    asyncio.run(commands.moglie_reset(make_update(message), context))

    assert message.replies == ["Calendario moglie svuotato."]
    assert wife_repository.list_entries() == []


def test_image_import_handler_saves_image_without_ocr(wife_repository, tmp_path):
    message = DummyMessage(photo=[DummyPhoto()])
    context = make_context(wife_repository, tmp_path)
    context.user_data["awaiting_wife_calendar_image"] = True

    asyncio.run(commands.wife_calendar_image(make_update(message), context))

    saved_images = list((tmp_path / "imports").glob("moglie_*.jpg"))
    assert len(saved_images) == 1
    assert saved_images[0].read_bytes() == b"fake image"
    assert "Foto calendario ricevuta e salvata." in message.replies[0]
    assert "Mandami l’elenco delle date M con /moglie_importa_m." in message.replies[0]
    assert context.user_data["awaiting_wife_calendar_image"] is False
