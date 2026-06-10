"""Repository SQLite per la memoria operativa persistente."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

from .operational_memory_parser import ParsedOperationalMemory


@dataclass(frozen=True)
class OperationalMemory:
    id: int
    created_at: str
    raw_text: str
    start_date: str | None
    end_date: str | None
    recurrence_rule: str | None
    person: str | None
    location: str | None
    constraint_type: str
    start_time: str | None
    end_time: str | None
    status: str
    source: str
    notes: str | None


class OperationalMemoryRepository:
    """Persistenza delle regole operative riutilizzabili nel tempo."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def add(
        self, parsed: ParsedOperationalMemory, *, source: str = "telegram"
    ) -> OperationalMemory:
        created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        cursor = self.connection.execute(
            """
            INSERT INTO operational_memory (
                created_at, raw_text, start_date, end_date, recurrence_rule, person,
                location, constraint_type, start_time, end_time, status, source, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
            """,
            (
                created_at,
                parsed.raw_text,
                parsed.start_date.isoformat() if parsed.start_date else None,
                parsed.end_date.isoformat() if parsed.end_date else None,
                parsed.recurrence_rule,
                parsed.person,
                parsed.location,
                parsed.constraint_type,
                parsed.start_time,
                parsed.end_time,
                source,
                parsed.notes,
            ),
        )
        self.connection.commit()
        return self.get(int(cursor.lastrowid))

    def get(self, memory_id: int) -> OperationalMemory:
        row = self.connection.execute(
            "SELECT * FROM operational_memory WHERE id = ?", (memory_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"Memoria {memory_id} non trovata")
        return _memory_from_row(row)

    def list_active(self) -> list[OperationalMemory]:
        rows = self.connection.execute(
            """
            SELECT * FROM operational_memory
            WHERE status = 'active'
            ORDER BY created_at, id
            """
        ).fetchall()
        return [_memory_from_row(row) for row in rows]

    def active_overlapping(
        self, week_start: str, week_end: str
    ) -> list[OperationalMemory]:
        rows = self.connection.execute(
            """
            SELECT * FROM operational_memory
            WHERE status = 'active'
              AND (
                recurrence_rule IS NOT NULL
                OR start_date IS NULL
                OR (start_date <= ? AND COALESCE(end_date, start_date) >= ?)
              )
            ORDER BY start_date IS NULL, start_date, created_at, id
            """,
            (week_end, week_start),
        ).fetchall()
        return [_memory_from_row(row) for row in rows]

    def delete(self, memory_id: int) -> bool:
        cursor = self.connection.execute(
            """
            UPDATE operational_memory
            SET status = 'deleted'
            WHERE id = ? AND status = 'active'
            """,
            (memory_id,),
        )
        self.connection.commit()
        return cursor.rowcount > 0

    def reset(self) -> int:
        cursor = self.connection.execute(
            "UPDATE operational_memory SET status = 'deleted' WHERE status = 'active'"
        )
        self.connection.commit()
        return int(cursor.rowcount)


def _memory_from_row(row: sqlite3.Row) -> OperationalMemory:
    return OperationalMemory(
        id=int(row["id"]),
        created_at=str(row["created_at"]),
        raw_text=str(row["raw_text"]),
        start_date=row["start_date"],
        end_date=row["end_date"],
        recurrence_rule=row["recurrence_rule"],
        person=row["person"],
        location=row["location"],
        constraint_type=str(row["constraint_type"]),
        start_time=row["start_time"],
        end_time=row["end_time"],
        status=str(row["status"]),
        source=str(row["source"]),
        notes=row["notes"],
    )
