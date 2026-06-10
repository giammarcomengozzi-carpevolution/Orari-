from datetime import date

from orari_agent.storage.db import connect
from orari_agent.storage.notes_repository import NotesRepository
from orari_agent.storage.week_parser import parse_note_metadata, parse_week_request


def test_parse_week_request_explicit_italian_range():
    start, end = parse_week_request(
        "Genera orario dal 17 al 23 giugno", today=date(2026, 6, 10)
    )

    assert start.isoformat() == "2026-06-17"
    assert end.isoformat() == "2026-06-23"


def test_notes_repository_persists_detected_metadata(tmp_path):
    connection = connect(tmp_path / "orari_bot.sqlite3")
    repository = NotesRepository(connection)
    text = "Martedì prossimo Angelo non c'è la mattina."

    note = repository.add(text, parse_note_metadata(text, today=date(2026, 6, 10)))
    notes = repository.active_for_week("2026-06-15", "2026-06-21")

    assert note.id == notes[0].id
    assert notes[0].person == "Angelo Antonelli"
    assert notes[0].constraint_type == "assenza"
    assert notes[0].interpreted_date == "2026-06-16"
