"""Repository SQLite per il calendario moglie di Giammarco."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class WifeCalendarEntry:
    date: str
    code: str
    source: str | None
    created_at: str


class WifeCalendarRepository:
    """Tabella dei codici giornalieri: per ora conta operativamente solo `M`."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def upsert_code(self, day: str, code: str, source: str | None = None) -> None:
        normalized = code.strip().upper()
        self.connection.execute(
            (
                "INSERT INTO wife_calendar(date, code, source, created_at) "
                "VALUES (?, ?, ?, ?)"
            ),
            (
                day,
                normalized,
                source,
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
            ),
        )
        self.connection.commit()

    def delete(self, day: str) -> bool:
        cursor = self.connection.execute(
            "DELETE FROM wife_calendar WHERE date = ?", (day,)
        )
        self.connection.commit()
        return cursor.rowcount > 0

    def list_entries(self) -> list[WifeCalendarEntry]:
        rows = self.connection.execute(
            """
            SELECT wc.date, wc.code, wc.source, wc.created_at
            FROM wife_calendar wc
            JOIN (
                SELECT date, MAX(id) AS max_id FROM wife_calendar GROUP BY date
            ) latest ON latest.max_id = wc.id
            ORDER BY wc.date
            """
        ).fetchall()
        return [
            WifeCalendarEntry(
                date=str(row["date"]),
                code=str(row["code"]),
                source=row["source"],
                created_at=str(row["created_at"]),
            )
            for row in rows
        ]

    def load_codes(self) -> dict[str, str]:
        return {entry.date: entry.code for entry in self.list_entries()}
