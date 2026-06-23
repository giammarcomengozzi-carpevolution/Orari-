"""Repository SQLite per gli orari PDF già generati."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any


class SchedulesRepository:
    """Registra cronologia, ultimo snapshot e riepilogo delle generazioni."""

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

    def latest(self) -> sqlite3.Row | None:
        return self.connection.execute(
            "SELECT * FROM generated_schedules ORDER BY id DESC LIMIT 1"
        ).fetchone()

    def save_snapshot(
        self,
        *,
        schedule_id: int | None,
        week_start: str,
        week_end: str,
        snapshot: dict[str, Any],
    ) -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO latest_schedule_snapshots (
                created_at, schedule_id, week_start, week_end, snapshot_json
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                schedule_id,
                week_start,
                week_end,
                json.dumps(snapshot, ensure_ascii=False, sort_keys=True),
            ),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def latest_snapshot(self) -> sqlite3.Row | None:
        return self.connection.execute(
            "SELECT * FROM latest_schedule_snapshots ORDER BY id DESC LIMIT 1"
        ).fetchone()
