"""Entry point installabile per il chatbot Telegram."""

from __future__ import annotations

from .bot.app import run_bot
from .config import load_config


def main() -> None:
    """Avvia il bot Telegram in long polling."""

    run_bot(load_config())
