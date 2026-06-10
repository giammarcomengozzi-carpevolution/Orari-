"""Repository SQLite per le note settimanali ricevute da Telegram."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

from .week_parser import ParsedNoteMetadata


@dataclass(frozen=True)
class Note:
    id: int
    created_at: str
    raw_text: str
    target_week_start: str
    target_week_end: str
    interpreted_date: str | None
    person: str | None
    location: str | None
    constraint_type: str | None
    status: str


class NotesRepository:
    """Persistenza delle istruzioni di pianificazione."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def add(self, raw_text: str, metadata: ParsedNoteMetadata) -> Note:
        created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        cursor = self.connection.execute(
            """
            INSERT INTO notes (
                created_at, raw_text, target_week_start, target_week_end,
                interpreted_date, person, location, constraint_type, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active')
            """,
            (
                created_at,
                raw_text.strip(),
                metadata.target_week_start.isoformat(),
                metadata.target_week_end.isoformat(),
                (
                    metadata.interpreted_date.isoformat()
                    if metadata.interpreted_date
                    else None
                ),
                metadata.person,
                metadata.location,
                metadata.constraint_type,
            ),
        )
        self.connection.commit()
        return self.get(int(cursor.lastrowid))

    def get(self, note_id: int) -> Note:
        row = self.connection.execute(
            "SELECT * FROM notes WHERE id = ?", (note_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"Nota {note_id} non trovata")
        return _note_from_row(row)

    def active_for_week(self, week_start: str, week_end: str) -> list[Note]:
        rows = self.connection.execute(
            """
            SELECT * FROM notes
            WHERE status = 'active'
              AND target_week_start <= ?
              AND target_week_end >= ?
            ORDER BY interpreted_date IS NULL, interpreted_date, created_at, id
            """,
            (week_end, week_start),
        ).fetchall()
        return [_note_from_row(row) for row in rows]

    def delete(self, note_id: int) -> bool:
        cursor = self.connection.execute(
            "UPDATE notes SET status = 'deleted' WHERE id = ? AND status = 'active'",
            (note_id,),
        )
        self.connection.commit()
        return cursor.rowcount > 0

    def archive_week(self, week_start: str, week_end: str) -> int:
        cursor = self.connection.execute(
            """
            UPDATE notes SET status = 'used'
            WHERE status = 'active' AND target_week_start <= ? AND target_week_end >= ?
            """,
            (week_end, week_start),
        )
        self.connection.commit()
        return int(cursor.rowcount)


def _note_from_row(row: sqlite3.Row) -> Note:
    return Note(
        id=int(row["id"]),
        created_at=str(row["created_at"]),
        raw_text=str(row["raw_text"]),
        target_week_start=str(row["target_week_start"]),
        target_week_end=str(row["target_week_end"]),
        interpreted_date=row["interpreted_date"],
        person=row["person"],
        location=row["location"],
        constraint_type=row["constraint_type"],
        status=str(row["status"]),
    )
