"""Entry point locale per avviare il bot Telegram in long polling."""

from __future__ import annotations

import sys
from pathlib import Path

# Permette `python main.py` anche prima dell'installazione editable del pacchetto.
src_path = Path(__file__).resolve().parent / "src"
if src_path.exists():
    sys.path.insert(0, str(src_path))

from orari_agent.bot.app import run_bot
from orari_agent.config import load_config


if __name__ == "__main__":
    run_bot(load_config())
