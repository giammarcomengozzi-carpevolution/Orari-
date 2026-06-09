"""Interfaccia a riga di comando dell'agente."""

from __future__ import annotations

import argparse

from .formatter import format_schedule_italian
from .generator import generate_weekly_schedule
from .pdf_exporter import export_weekly_schedule_pdf


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Genera l'orario settimanale per CarpeEvolution Store e Tenuta del Germano."
    )
    parser.add_argument(
        "weekly_instruction",
        nargs="*",
        help="Istruzioni settimanali in linguaggio naturale.",
    )
    parser.add_argument(
        "--week-start",
        help="Data di inizio settimana in formato YYYY-MM-DD, usata per calendario e riferimento PDF.",
    )
    parser.add_argument(
        "--pdf",
        action="store_true",
        help="Genera anche un PDF A4 orizzontale pronto per la condivisione manuale su WhatsApp.",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Percorso file PDF o cartella di destinazione. Valido solo con --pdf.",
    )
    args = parser.parse_args(argv)

    if args.output and not args.pdf:
        parser.error("--output può essere usato solo insieme a --pdf")

    text = " ".join(args.weekly_instruction).strip()
    schedule = generate_weekly_schedule(text, week_start_date=args.week_start)
    print(format_schedule_italian(schedule))

    if args.pdf:
        pdf_path = export_weekly_schedule_pdf(schedule, args.output, week_start_date=args.week_start)
        print(f"\nPDF generato: {pdf_path}")

    return 0
