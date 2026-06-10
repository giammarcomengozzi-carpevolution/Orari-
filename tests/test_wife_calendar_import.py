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
    assert (
        "Date ignorate perché non valide: non-data, 2026-02-31." in message.replies[0]
    )


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


def test_image_import_handler_saves_image_before_ocr_fallback(
    wife_repository, tmp_path
):
    message = DummyMessage(photo=[DummyPhoto()])
    context = make_context(wife_repository, tmp_path)
    context.user_data["awaiting_wife_calendar_image"] = True

    asyncio.run(commands.wife_calendar_image(make_update(message), context))

    saved_images = list((tmp_path / "imports").glob("moglie_*.jpg"))
    assert len(saved_images) == 1
    assert saved_images[0].read_bytes() == b"fake image"
    assert "Ho ricevuto la foto" in message.replies[0]
    assert "Non ho salvato automaticamente" in message.replies[0]
    assert context.user_data["awaiting_wife_calendar_image"] is False


def test_image_handler_high_confidence_does_not_save_immediately(
    monkeypatch, wife_repository, tmp_path
):
    from orari_agent.wife_calendar_ocr import WifeCalendarOcrResult

    def fake_extract(image_path, year=None):
        return WifeCalendarOcrResult(
            imported_dates=["2026-01-03", "2026-09-10"],
            confidence=0.9,
            warnings=[],
            debug_summary="test high confidence",
            ocr_status="test ocr",
        )

    monkeypatch.setattr(commands, "extract_m_dates_from_image", fake_extract)
    message = DummyMessage(photo=[DummyPhoto()])
    context = make_context(wife_repository, tmp_path)
    context.user_data["awaiting_wife_calendar_image"] = True

    asyncio.run(commands.wife_calendar_image(make_update(message), context))

    assert wife_repository.list_entries("M") == []
    assert "Calendario moglie letto automaticamente." in message.replies[0]
    assert "Date M candidate trovate: 2." in message.replies[0]
    assert "Confidenza OCR: 90%." in message.replies[0]
    assert "non ho ancora salvato" in message.replies[0]
    assert "/conferma_calendario_moglie" in message.replies[0]
    record = wife_repository.latest_import_record()
    assert record is not None
    assert record.status == "ocr_pending_confirmation"
    assert "Date M candidate: 2026-01-03, 2026-09-10" in record.summary
    assert context.user_data["awaiting_wife_calendar_image"] is False


def test_conferma_calendario_moglie_saves_last_candidate_dates(
    wife_repository, tmp_path
):
    wife_repository.add_import_record(
        source="telegram_image",
        status="ocr_pending_confirmation",
        summary=(
            "Calendario moglie letto automaticamente, in attesa di conferma.\n"
            "Date M candidate: 2026-01-03, 2026-09-10\n"
            "Confidenza OCR: 90%."
        ),
        warnings=[],
        image_path=str(tmp_path / "imports" / "moglie.jpg"),
    )
    message = DummyMessage()
    context = make_context(wife_repository, tmp_path)

    asyncio.run(commands.conferma_calendario_moglie(make_update(message), context))

    entries = wife_repository.list_entries("M")
    assert [entry.date for entry in entries] == ["2026-01-03", "2026-09-10"]
    assert entries[0].source == "telegram_image_ocr_confirmed"
    assert "Calendario moglie confermato." in message.replies[0]
    assert "Date M salvate: 2." in message.replies[0]
    record = wife_repository.latest_import_record()
    assert record is not None
    assert record.status == "ocr_confirmed"


def test_conferma_calendario_moglie_without_candidates_does_nothing(
    wife_repository, tmp_path
):
    wife_repository.add_import_record(
        source="telegram_image",
        status="ocr_low_confidence",
        summary="Date M candidate: nessuna",
        warnings=["Nessuna cella con M rilevata automaticamente."],
        image_path=str(tmp_path / "imports" / "moglie.jpg"),
    )
    message = DummyMessage()
    context = make_context(wife_repository, tmp_path)

    asyncio.run(commands.conferma_calendario_moglie(make_update(message), context))

    assert wife_repository.list_entries("M") == []
    assert "Nessuna data M candidata da confermare" in message.replies[0]


def test_image_handler_low_confidence_does_not_save(
    monkeypatch, wife_repository, tmp_path
):
    from orari_agent.wife_calendar_ocr import WifeCalendarOcrResult

    def fake_extract(image_path, year=None):
        return WifeCalendarOcrResult(
            imported_dates=["2026-01-03"],
            confidence=0.4,
            warnings=["Griglia non sicura."],
            debug_summary="low confidence",
            ocr_status="test ocr",
        )

    monkeypatch.setattr(commands, "extract_m_dates_from_image", fake_extract)
    message = DummyMessage(photo=[DummyPhoto()])
    context = make_context(wife_repository, tmp_path)
    context.user_data["awaiting_wife_calendar_image"] = True

    asyncio.run(commands.wife_calendar_image(make_update(message), context))

    assert wife_repository.list_entries("M") == []
    assert "Non ho salvato automaticamente le date." in message.replies[0]
    record = wife_repository.latest_import_record()
    assert record is not None
    assert record.status == "ocr_low_confidence"
    assert "Griglia non sicura." in record.warnings


def test_image_handler_ocr_unavailable_fallback_does_not_crash(
    wife_repository, tmp_path
):
    message = DummyMessage(photo=[DummyPhoto()])
    context = make_context(wife_repository, tmp_path)
    context.user_data["awaiting_wife_calendar_image"] = True

    asyncio.run(commands.wife_calendar_image(make_update(message), context))

    assert wife_repository.list_entries("M") == []
    assert "Ho ricevuto la foto" in message.replies[0]
    assert "/moglie_importa_m" in message.replies[0]
    record = wife_repository.latest_import_record()
    assert record is not None
    assert record.status in {"ocr_failed", "ocr_low_confidence"}
    assert "Pillow" in record.summary or "formato non supportato" in record.warnings


def test_debug_calendario_moglie_shows_last_import(wife_repository, tmp_path):
    wife_repository.add_import_record(
        source="telegram_image",
        status="ocr_pending_confirmation",
        summary="Date M candidate: 2026-01-03, 2026-09-10\nlinee verticali=33",
        warnings=["foto storta"],
        image_path=str(tmp_path / "imports" / "moglie.jpg"),
    )
    message = DummyMessage()
    context = make_context(wife_repository, tmp_path)

    asyncio.run(commands.debug_calendario_moglie(make_update(message), context))

    assert "Debug ultimo import calendario moglie:" in message.replies[0]
    assert "OCR status: ocr_pending_confirmation" in message.replies[0]
    assert "2026-01-03, 2026-09-10" in message.replies[0]
    assert "foto storta" in message.replies[0]


class DummyDocument:
    def __init__(self, source_path, file_name="calendario.xlsx"):
        self.source_path = Path(source_path)
        self.file_name = file_name

    async def get_file(self):
        return DummyExcelTelegramFile(self.source_path)


class DummyExcelTelegramFile:
    def __init__(self, source_path):
        self.source_path = Path(source_path)

    async def download_to_drive(self, custom_path):
        Path(custom_path).write_bytes(self.source_path.read_bytes())


def make_excel(path):
    openpyxl = pytest.importorskip("openpyxl")
    Workbook = openpyxl.Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Giugno"
    sheet.append(["Data", "Codice"])
    sheet.append(["2026-06-01", "M"])
    sheet.append(["2026-06-02", "P"])
    sheet.append(["2026-06-03", "I"])
    sheet.append(["2026-06-04", "F"])
    sheet.append(["2026-06-05", None])
    sheet.append(["2026-06-06", "m"])
    workbook.save(path)


def test_excel_import_extracts_only_m_dates(wife_repository, tmp_path):
    excel_path = tmp_path / "calendario.xlsx"
    make_excel(excel_path)
    message = DummyMessage()
    message.document = DummyDocument(excel_path)
    context = make_context(wife_repository, tmp_path)
    context.user_data["awaiting_wife_calendar_excel"] = True

    asyncio.run(commands.wife_calendar_document(make_update(message), context))

    assert [entry.date for entry in wife_repository.list_entries("M")] == [
        "2026-06-01",
        "2026-06-06",
    ]
    assert wife_repository.list_entries("P") == []
    assert "Date M trovate: 2." in message.replies[0]
    assert "P, I, F" in message.replies[0]
    assert context.user_data["awaiting_wife_calendar_excel"] is False


def test_calendario_moglie_info_command(wife_repository, tmp_path):
    wife_repository.bulk_upsert_code(["2026-06-01", "2026-06-06"], "M", "test")
    wife_repository.add_import_record(
        source="telegram_excel",
        status="excel_imported",
        summary="Import Excel calendario moglie completato.",
    )
    message = DummyMessage()
    context = make_context(wife_repository, tmp_path)

    asyncio.run(commands.calendario_moglie_info(make_update(message), context))

    assert "Prima data caricata: 2026-06-01" in message.replies[0]
    assert "Ultima data caricata: 2026-06-06" in message.replies[0]
    assert "Numero date M: 2" in message.replies[0]
    assert "Ultimo import:" in message.replies[0]


def test_calendario_moglie_reset_command(wife_repository, tmp_path):
    wife_repository.upsert_code("2026-06-01", "M", "test")
    message = DummyMessage()
    context = make_context(wife_repository, tmp_path, args=["confermo"])

    asyncio.run(commands.calendario_moglie_reset(make_update(message), context))

    assert wife_repository.list_entries() == []
    assert "Calendario moglie svuotato: 1 righe eliminate." in message.replies[0]
