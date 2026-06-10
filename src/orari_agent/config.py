"""Configurazione per il bot Telegram e la memoria persistente."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dipendenza opzionale in ambienti CLI legacy
    load_dotenv = None  # type: ignore[assignment]


@dataclass(frozen=True)
class BotConfig:
    """Valori necessari per avviare il chatbot Telegram."""

    telegram_bot_token: str
    allowed_telegram_user_id: int
    database_path: Path
    output_dir: Path


def load_config(env_file: str | Path = ".env") -> BotConfig:
    """Carica la configurazione da `.env` e variabili d'ambiente."""

    if load_dotenv is not None:
        load_dotenv(env_file)

    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN non configurato.")

    raw_user_id = os.getenv("ALLOWED_TELEGRAM_USER_ID", "").strip()
    if not raw_user_id:
        raise RuntimeError("ALLOWED_TELEGRAM_USER_ID non configurato.")
    try:
        allowed_user_id = int(raw_user_id)
    except ValueError as exc:
        raise RuntimeError("ALLOWED_TELEGRAM_USER_ID deve essere un numero intero.") from exc

    database_path = Path(os.getenv("DATABASE_PATH", "data/orari_bot.sqlite3"))
    output_dir = Path(os.getenv("OUTPUT_DIR", "output"))
    return BotConfig(
        telegram_bot_token=token,
        allowed_telegram_user_id=allowed_user_id,
        database_path=database_path,
        output_dir=output_dir,
    )
