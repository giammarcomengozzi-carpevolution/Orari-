"""Repository SQLite per il futuro calendario moglie di Giammarco."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone


class WifeCalendarRepository:
    """Tabella pronta per codici giornalieri: per ora conta solo il codice M."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def upsert_code(self, day: str, code: str, source: str | None = None) -> None:
        self.connection.execute(
            (
                "INSERT INTO wife_calendar(date, code, source, created_at) "
                "VALUES (?, ?, ?, ?)"
            ),
            (
                day,
                code.strip().upper(),
                source,
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
            ),
        )
        self.connection.commit()

    def load_codes(self) -> dict[str, str]:
        rows = self.connection.execute(
            """
            SELECT wc.date, wc.code
            FROM wife_calendar wc
            JOIN (
                SELECT date, MAX(id) AS max_id FROM wife_calendar GROUP BY date
            ) latest ON latest.max_id = wc.id
            """
        ).fetchall()
        return {str(row["date"]): str(row["code"]) for row in rows}
