"""Repository SQLite per stato conversazionale dell'AI Telegram."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class PendingAction:
    user_id: int
    pending_action: str
    payload: dict[str, Any]
    created_at: str


class AiConversationRepository:
    """Memorizza azioni AI in attesa di conferma esplicita."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def save_pending_action(
        self, user_id: int, pending_action: str, payload: dict[str, Any]
    ) -> PendingAction:
        created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        self.connection.execute(
            "DELETE FROM ai_pending_actions WHERE user_id = ?",
            (user_id,),
        )
        self.connection.execute(
            """
            INSERT INTO ai_pending_actions (user_id, pending_action, payload_json, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, pending_action, payload_json, created_at),
        )
        self.connection.commit()
        return PendingAction(user_id, pending_action, payload, created_at)

    def get_pending_action(self, user_id: int) -> PendingAction | None:
        row = self.connection.execute(
            """
            SELECT user_id, pending_action, payload_json, created_at
            FROM ai_pending_actions
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
        if row is None:
            return None
        try:
            payload = json.loads(str(row["payload_json"]))
        except json.JSONDecodeError:
            payload = {}
        return PendingAction(
            user_id=int(row["user_id"]),
            pending_action=str(row["pending_action"]),
            payload=payload,
            created_at=str(row["created_at"]),
        )

    def clear_pending_action(self, user_id: int) -> bool:
        cursor = self.connection.execute(
            "DELETE FROM ai_pending_actions WHERE user_id = ?",
            (user_id,),
        )
        self.connection.commit()
        return cursor.rowcount > 0
