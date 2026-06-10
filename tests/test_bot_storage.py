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


def test_parse_week_request_questa_settimana():
    start, end = parse_week_request("questa settimana", today=date(2026, 6, 10))

    assert start.isoformat() == "2026-06-08"
    assert end.isoformat() == "2026-06-14"


def test_parse_week_request_settimana_prossima():
    start, end = parse_week_request("settimana prossima", today=date(2026, 6, 10))

    assert start.isoformat() == "2026-06-15"
    assert end.isoformat() == "2026-06-21"


def test_parse_week_request_fra_due_settimane_digits():
    start, end = parse_week_request("fra 2 settimane", today=date(2026, 6, 10))

    assert start.isoformat() == "2026-06-22"
    assert end.isoformat() == "2026-06-28"


def test_parse_week_request_fra_due_settimane_words():
    start, end = parse_week_request("fra due settimane", today=date(2026, 6, 10))

    assert start.isoformat() == "2026-06-22"
    assert end.isoformat() == "2026-06-28"


def test_parse_week_request_settimana_del_date():
    start, end = parse_week_request("settimana del 17 giugno", today=date(2026, 6, 10))

    assert start.isoformat() == "2026-06-15"
    assert end.isoformat() == "2026-06-21"


def test_notes_repository_delete_single_note(tmp_path):
    connection = connect(tmp_path / "orari_bot.sqlite3")
    repository = NotesRepository(connection)
    note = repository.add(
        "Martedì Angelo non c'è.",
        parse_note_metadata("Martedì Angelo non c'è.", today=date(2026, 6, 10)),
    )

    assert repository.delete(note.id) is True
    assert repository.delete(note.id) is False
    assert repository.active_for_week("2026-06-15", "2026-06-21") == []


def test_notes_repository_archive_week_deletes_all_active_notes(tmp_path):
    connection = connect(tmp_path / "orari_bot.sqlite3")
    repository = NotesRepository(connection)
    next_week_note = repository.add(
        "Settimana prossima Lorenzo apre martedì.",
        parse_note_metadata(
            "Settimana prossima Lorenzo apre martedì.", today=date(2026, 6, 10)
        ),
    )
    current_week_note = repository.add(
        "Questa settimana Angelo non c'è sabato.",
        parse_note_metadata(
            "Questa settimana Angelo non c'è sabato.", today=date(2026, 6, 10)
        ),
    )

    count = repository.archive_week("2026-06-15", "2026-06-21")

    assert count == 1
    assert repository.get(next_week_note.id).status == "used"
    assert repository.get(current_week_note.id).status == "active"


def test_parse_week_request_prossima_settimana_variant():
    start, end = parse_week_request("prossima settimana", today=date(2026, 6, 10))

    assert start.isoformat() == "2026-06-15"
    assert end.isoformat() == "2026-06-21"


def test_parse_week_request_tra_due_settimane_variant():
    start, end = parse_week_request("tra due settimane", today=date(2026, 6, 10))

    assert start.isoformat() == "2026-06-22"
    assert end.isoformat() == "2026-06-28"


def test_saved_note_message_includes_interpretation_summary(tmp_path):
    from orari_agent.bot.note_messages import saved_note_message

    connection = connect(tmp_path / "orari_bot.sqlite3")
    repository = NotesRepository(connection)
    text = "Giovedì Gianmarco in negozio tutto il giorno per fatture"
    note = repository.add(text, parse_note_metadata(text, today=date(2026, 6, 10)))

    message = saved_note_message(note)

    assert "Nota salvata con ID" in message
    assert "Settimana: 2026-06-15 - 2026-06-21" in message
    assert "Data interpretata: 2026-06-18" in message
    assert "Persona: Giammarco Mengozzi" in message
    assert "Luogo: CarpeEvolution Store" in message
    assert "Interpretazione:" in message
    assert "Giammarco Mengozzi forzato su negozio Giovedì" in message
