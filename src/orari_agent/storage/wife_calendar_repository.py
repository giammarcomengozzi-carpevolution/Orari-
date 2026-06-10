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
        self.bulk_upsert_code([day], code, source)

    def bulk_upsert_code(
        self, days: list[str], code: str, source: str | None = None
    ) -> tuple[int, int]:
        normalized = code.strip().upper()
        created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        inserted = 0
        updated = 0
        for day in days:
            exists = self.connection.execute(
                "SELECT 1 FROM wife_calendar WHERE date = ? LIMIT 1", (day,)
            ).fetchone()
            if exists:
                updated += 1
            else:
                inserted += 1
            self.connection.execute(
                (
                    "INSERT INTO wife_calendar(date, code, source, created_at) "
                    "VALUES (?, ?, ?, ?)"
                ),
                (day, normalized, source, created_at),
            )
        self.connection.commit()
        return inserted, updated

    def delete(self, day: str) -> bool:
        cursor = self.connection.execute(
            "DELETE FROM wife_calendar WHERE date = ?", (day,)
        )
        self.connection.commit()
        return cursor.rowcount > 0

    def list_entries(self, code: str | None = None) -> list[WifeCalendarEntry]:
        params: tuple[str, ...] = ()
        where = ""
        if code is not None:
            where = "WHERE wc.code = ?"
            params = (code.strip().upper(),)
        rows = self.connection.execute(
            f"""
            SELECT wc.date, wc.code, wc.source, wc.created_at
            FROM wife_calendar wc
            JOIN (
                SELECT date, MAX(id) AS max_id FROM wife_calendar GROUP BY date
            ) latest ON latest.max_id = wc.id
            {where}
            ORDER BY wc.date
            """,
            params,
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

    def reset(self) -> int:
        cursor = self.connection.execute("DELETE FROM wife_calendar")
        self.connection.commit()
        return cursor.rowcount

    def add_import_record(
        self,
        source: str,
        status: str,
        summary: str,
        warnings: list[str] | None = None,
        image_path: str | None = None,
    ) -> int:
        created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        cursor = self.connection.execute(
            (
                "INSERT INTO wife_calendar_imports"
                "(created_at, source, image_path, status, summary, warnings) "
                "VALUES (?, ?, ?, ?, ?, ?)"
            ),
            (
                created_at,
                source,
                image_path,
                status,
                summary,
                "\n".join(warnings or []),
            ),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def load_codes(self) -> dict[str, str]:
        return {entry.date: entry.code for entry in self.list_entries()}
