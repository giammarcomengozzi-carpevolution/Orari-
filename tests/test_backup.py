from zipfile import ZipFile

from orari_agent.backup import collect_backup_info, create_backup
from orari_agent.storage.db import connect
from orari_agent.storage.notes_repository import NotesRepository
from orari_agent.storage.operational_memory_parser import parse_operational_memory
from orari_agent.storage.operational_memory_repository import (
    OperationalMemoryRepository,
)
from orari_agent.storage.week_parser import parse_note_metadata
from orari_agent.storage.wife_calendar_repository import WifeCalendarRepository


def test_backup_generation_includes_database_imports_and_metadata(tmp_path):
    data_dir = tmp_path / "data"
    db_path = data_dir / "orari_bot.sqlite3"
    connection = connect(db_path)
    NotesRepository(connection).add(
        "Martedì Angelo non c'è.", parse_note_metadata("Martedì Angelo non c'è.")
    )
    OperationalMemoryRepository(connection).add(
        parse_operational_memory("Lorenzo in ferie dal 10 al 15 agosto")
    )
    WifeCalendarRepository(connection).upsert_code("2026-06-01", "M", "test")
    imports_dir = data_dir / "imports"
    imports_dir.mkdir(parents=True)
    (imports_dir / "moglie.xlsx").write_bytes(b"xlsx")

    backup_path = create_backup(database_path=db_path, data_dir=data_dir)

    assert backup_path.name.startswith("backup_")
    assert backup_path.suffix == ".zip"
    with ZipFile(backup_path) as archive:
        names = set(archive.namelist())
    assert "data/orari_bot.sqlite3" in names
    assert "data/imports/moglie.xlsx" in names
    assert "metadata.json" in names

    info = collect_backup_info(db_path, data_dir / "backups")
    assert info.notes_count == 1
    assert info.memories_count == 1
    assert info.wife_calendar_entries_count == 1
    assert info.latest_backup == backup_path
