"""Repository SQLite per trascrizioni vocali Telegram."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class VoiceTranscript:
    id: int
    created_at: str
    file_name: str
    transcript: str
    user_id: int


class VoiceTranscriptsRepository:
    """Memorizza le trascrizioni audio per debug e comando /trascrivi_ultimo."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def add(self, file_name: str, transcript: str, user_id: int) -> VoiceTranscript:
        created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        cursor = self.connection.execute(
            """
            INSERT INTO voice_transcripts (created_at, file_name, transcript, user_id)
            VALUES (?, ?, ?, ?)
            """,
            (created_at, file_name, transcript, user_id),
        )
        self.connection.commit()
        return VoiceTranscript(
            id=int(cursor.lastrowid),
            created_at=created_at,
            file_name=file_name,
            transcript=transcript,
            user_id=user_id,
        )

    def latest_for_user(self, user_id: int) -> VoiceTranscript | None:
        row = self.connection.execute(
            """
            SELECT id, created_at, file_name, transcript, user_id
            FROM voice_transcripts
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
        if row is None:
            return None
        return VoiceTranscript(
            id=int(row["id"]),
            created_at=str(row["created_at"]),
            file_name=str(row["file_name"]),
            transcript=str(row["transcript"]),
            user_id=int(row["user_id"]),
        )
