"""Audit trail SQLite per interpretazioni AI e tool call."""
from __future__ import annotations

import json, sqlite3
from datetime import datetime, timezone
from typing import Any

class AiAuditRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def add_event(self, *, telegram_user_id: int, raw_user_text: str, normalized_text: str = "", detected_intent: str = "", confidence: str = "", requires_confirmation: bool = False, tool_called: str = "", tool_arguments: dict[str, Any] | None = None, tool_result: dict[str, Any] | None = None, bot_response: str = "", related_note_id: int | None = None, related_schedule_id: int | None = None, error: str = "") -> int:
        cursor = self.connection.execute(
            """
            INSERT INTO ai_events (timestamp, telegram_user_id, raw_user_text, normalized_text, detected_intent, confidence, requires_confirmation, tool_called, tool_arguments_json, tool_result_json, bot_response, related_note_id, related_schedule_id, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (datetime.now(timezone.utc).isoformat(timespec="seconds"), telegram_user_id, raw_user_text, normalized_text, detected_intent, confidence, int(requires_confirmation), tool_called, json.dumps(tool_arguments or {}, ensure_ascii=False), json.dumps(tool_result or {}, ensure_ascii=False), bot_response, related_note_id, related_schedule_id, error),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def latest_event(self, telegram_user_id: int | None = None) -> sqlite3.Row | None:
        if telegram_user_id is None:
            return self.connection.execute("SELECT * FROM ai_events ORDER BY id DESC LIMIT 1").fetchone()
        return self.connection.execute("SELECT * FROM ai_events WHERE telegram_user_id = ? ORDER BY id DESC LIMIT 1", (telegram_user_id,)).fetchone()
