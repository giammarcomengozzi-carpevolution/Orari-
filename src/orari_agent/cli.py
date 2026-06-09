"""Interfaccia a riga di comando dell'agente."""

from __future__ import annotations

import argparse

from .formatter import format_schedule_italian
from .generator import generate_weekly_schedule


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Genera l'orario settimanale per CarpeEvolution Store e Tenuta del Germano."
    )
    parser.add_argument(
        "weekly_instruction",
        nargs="*",
        help="Istruzioni settimanali in linguaggio naturale.",
    )
    args = parser.parse_args(argv)

    text = " ".join(args.weekly_instruction).strip()
    schedule = generate_weekly_schedule(text)
    print(format_schedule_italian(schedule))
    return 0
