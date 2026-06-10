"""Repository SQLite per gli orari PDF già generati."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone


class SchedulesRepository:
    """Registra cronologia e riepilogo delle generazioni."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def add(
        self,
        *,
        week_start: str,
        week_end: str,
        pdf_path: str,
        summary: str,
        warnings: str,
    ) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO generated_schedules (
                created_at, week_start, week_end, pdf_path, summary, warnings
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                week_start,
                week_end,
                pdf_path,
                summary,
                warnings,
            ),
        )
        self.connection.commit()
        return int(cursor.lastrowid)
