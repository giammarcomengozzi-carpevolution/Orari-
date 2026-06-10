"""Handler dei comandi Telegram."""

from __future__ import annotations

from datetime import datetime
from html import escape

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from orari_agent.storage.notes_repository import NotesRepository
from orari_agent.storage.week_parser import (
    current_or_next_week_bounds,
    parse_note_metadata,
    parse_week_request,
)
from orari_agent.storage.wife_calendar_repository import WifeCalendarRepository

from .schedule_service import ScheduleService
from .security import is_allowed_user, reject_unauthorized


def _deps(
    context: ContextTypes.DEFAULT_TYPE,
) -> tuple[int, NotesRepository, ScheduleService, WifeCalendarRepository]:
    return (
        int(context.application.bot_data["allowed_user_id"]),
        context.application.bot_data["notes_repository"],
        context.application.bot_data["schedule_service"],
        context.application.bot_data["wife_calendar_repository"],
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    allowed_user_id, _, _, _ = _deps(context)
    if not is_allowed_user(update, allowed_user_id):
        await reject_unauthorized(update)
        return
    await update.effective_message.reply_text(
        "Ciao Gianmarco! Sono il tuo assistente privato per gli orari di CarpeEvolution Store "
        "e Tenuta del Germano.\n\n"
        "Scrivimi note durante la settimana, per esempio:\n"
        "• Giovedì Gianmarco deve stare in negozio tutto il giorno per fatture\n"
        "• Sabato Lorenzo deve uscire alle 15\n"
        "• Domenica al lago ci sono molte prenotazioni\n\n"
        "Quando vuoi il PDF scrivi /genera oppure 'Genera orario settimana prossima'."
    )


async def aiuto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    allowed_user_id, _, _, _ = _deps(context)
    if not is_allowed_user(update, allowed_user_id):
        await reject_unauthorized(update)
        return
    await update.effective_message.reply_text(
        "Comandi disponibili:\n"
        "/nota testo — salva una nota per la settimana\n"
        "/lista — mostra le note attive della prossima settimana\n"
        "/lista questa settimana — mostra una settimana specifica\n"
        "/lista fra 2 settimane — mostra la settimana tra due settimane\n"
        "/lista dal 17 al 23 giugno — mostra un intervallo specifico\n"
        "/cancella 12 — cancella la nota con ID 12\n"
        "/cancella_tutte confermo — archivia tutte le note attive della prossima settimana\n"
        "/cancella_tutte questa settimana confermo — archivia tutte le note attive della settimana scelta\n"
        "/moglie_set YYYY-MM-DD M — salva un codice del calendario moglie\n"
        "/moglie_lista — mostra i codici salvati\n"
        "/moglie_cancella YYYY-MM-DD — elimina un codice salvato\n"
        "/genera — genera il PDF della prossima settimana\n"
        "/genera dal 17 al 23 giugno — genera una settimana specifica\n"
        "/reset_settimana dal 17 al 23 giugno confermo — archivia le note attive della settimana\n\n"
        "Puoi anche scrivere una frase normale: verrà salvata come nota, se non è un comando."
    )


async def nota(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    allowed_user_id, notes_repository, _, _ = _deps(context)
    if not is_allowed_user(update, allowed_user_id):
        await reject_unauthorized(update)
        return
    text = " ".join(context.args).strip()
    if not text:
        await update.effective_message.reply_text(
            "Scrivi il testo dopo /nota, ad esempio: /nota Sabato Lorenzo esce alle 15"
        )
        return
    note = notes_repository.add(text, parse_note_metadata(text))
    await update.effective_message.reply_text(
        _saved_note_message(note), parse_mode=ParseMode.HTML
    )


async def lista(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    allowed_user_id, notes_repository, _, _ = _deps(context)
    if not is_allowed_user(update, allowed_user_id):
        await reject_unauthorized(update)
        return
    request_text = " ".join(context.args)
    start, end = (
        parse_week_request(request_text)
        if request_text
        else current_or_next_week_bounds()
    )
    notes = notes_repository.active_for_week(start.isoformat(), end.isoformat())
    if not notes:
        await update.effective_message.reply_text(
            f"Nessuna nota attiva per la settimana {start.isoformat()} - {end.isoformat()}."
        )
        return
    lines = [f"Note attive per la settimana {start.isoformat()} - {end.isoformat()}:"]
    for note in notes:
        interpreted = note.interpreted_date or "non specificata"
        lines.append(
            f"ID {note.id} | settimana {note.target_week_start} - {note.target_week_end} "
            f"| data {interpreted} | testo: {note.raw_text}"
        )
    await update.effective_message.reply_text("\n".join(lines))


async def cancella(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    allowed_user_id, notes_repository, _, _ = _deps(context)
    if not is_allowed_user(update, allowed_user_id):
        await reject_unauthorized(update)
        return
    if not context.args or not context.args[0].isdigit():
        await update.effective_message.reply_text(
            "Uso: /cancella ID, ad esempio /cancella 12"
        )
        return
    note_id = int(context.args[0])
    deleted = notes_repository.delete(note_id)
    await update.effective_message.reply_text(
        f"Nota ID {note_id} cancellata correttamente."
        if deleted
        else f"Nota ID {note_id} non trovata tra le note attive."
    )


async def cancella_tutte(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    allowed_user_id, notes_repository, _, _ = _deps(context)
    if not is_allowed_user(update, allowed_user_id):
        await reject_unauthorized(update)
        return
    text = " ".join(context.args).strip()
    if "confermo" not in text.lower().split():
        await update.effective_message.reply_text(
            "Per sicurezza, ripeti il comando aggiungendo confermo."
        )
        return
    request_text = " ".join(arg for arg in context.args if arg.lower() != "confermo")
    start, end = parse_week_request(request_text)
    count = notes_repository.archive_week(start.isoformat(), end.isoformat())
    await update.effective_message.reply_text(
        f"Ho archiviato {count} note attive per la settimana {start.isoformat()} - {end.isoformat()}."
    )


async def moglie_set(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    allowed_user_id, _, _, wife_repository = _deps(context)
    if not is_allowed_user(update, allowed_user_id):
        await reject_unauthorized(update)
        return
    if len(context.args) != 2:
        await update.effective_message.reply_text(
            "Uso: /moglie_set YYYY-MM-DD CODICE, ad esempio /moglie_set 2026-06-17 M"
        )
        return
    day, code = context.args[0], context.args[1].upper()
    if not _is_iso_date(day):
        await update.effective_message.reply_text(
            "Data non valida. Usa il formato YYYY-MM-DD, ad esempio 2026-06-17."
        )
        return
    wife_repository.upsert_code(day, code, source="telegram")
    effect = (
        "blocca l'apertura lago delle 07:30"
        if code == "M"
        else "non ha effetto bloccante"
    )
    await update.effective_message.reply_text(
        f"Codice calendario moglie salvato: {day} = {code} ({effect})."
    )


async def moglie_lista(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    allowed_user_id, _, _, wife_repository = _deps(context)
    if not is_allowed_user(update, allowed_user_id):
        await reject_unauthorized(update)
        return
    entries = wife_repository.list_entries()
    if not entries:
        await update.effective_message.reply_text(
            "Nessun codice calendario moglie salvato."
        )
        return
    lines = ["Codici calendario moglie salvati:"]
    lines.extend(f"{entry.date}: {entry.code}" for entry in entries)
    await update.effective_message.reply_text("\n".join(lines))


async def moglie_cancella(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    allowed_user_id, _, _, wife_repository = _deps(context)
    if not is_allowed_user(update, allowed_user_id):
        await reject_unauthorized(update)
        return
    if len(context.args) != 1 or not _is_iso_date(context.args[0]):
        await update.effective_message.reply_text(
            "Uso: /moglie_cancella YYYY-MM-DD, ad esempio /moglie_cancella 2026-06-17"
        )
        return
    day = context.args[0]
    deleted = wife_repository.delete(day)
    await update.effective_message.reply_text(
        f"Codice calendario moglie per {day} cancellato."
        if deleted
        else f"Nessun codice calendario moglie trovato per {day}."
    )


async def genera(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    allowed_user_id, _, schedule_service, _ = _deps(context)
    if not is_allowed_user(update, allowed_user_id):
        await reject_unauthorized(update)
        return
    await _generate_and_send(update, context, " ".join(context.args), schedule_service)


async def reset_settimana(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    allowed_user_id, notes_repository, _, _ = _deps(context)
    if not is_allowed_user(update, allowed_user_id):
        await reject_unauthorized(update)
        return
    text = " ".join(context.args)
    if "confermo" not in text.lower():
        await update.effective_message.reply_text(
            "Per evitare errori, ripeti con 'confermo'. Esempio: /reset_settimana dal 17 al 23 giugno confermo"
        )
        return
    start, end = parse_week_request(text)
    count = notes_repository.archive_week(start.isoformat(), end.isoformat())
    await update.effective_message.reply_text(
        f"Ho archiviato {count} note attive per {start.isoformat()} - {end.isoformat()}."
    )


async def free_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    allowed_user_id, notes_repository, schedule_service, _ = _deps(context)
    if not is_allowed_user(update, allowed_user_id):
        await reject_unauthorized(update)
        return
    text = (update.effective_message.text or "").strip()
    if not text:
        return
    lowered = text.lower()
    if lowered.startswith("genera orario") or lowered.startswith("genera l'orario"):
        await _generate_and_send(update, context, text, schedule_service)
        return
    note = notes_repository.add(text, parse_note_metadata(text))
    await update.effective_message.reply_text(
        _saved_note_message(note), parse_mode=ParseMode.HTML
    )


async def _generate_and_send(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    request_text: str,
    schedule_service: ScheduleService,
) -> None:
    start, end = parse_week_request(request_text)
    await update.effective_message.reply_text(
        f"Genero l'orario per {start.isoformat()} - {end.isoformat()} usando le note salvate..."
    )
    result = schedule_service.generate_for_week(start.isoformat(), end.isoformat())
    warning_text = _warnings_text(result.warnings)
    with result.pdf_path.open("rb") as pdf_file:
        await update.effective_message.reply_document(
            document=pdf_file,
            filename=result.pdf_path.name,
            caption=f"{result.summary}\n{warning_text}",
        )


def _warnings_text(warnings: list[str]) -> str:
    if not warnings:
        return "Nessun avviso rilevato."
    preview = "\n".join(f"• {warning}" for warning in warnings[:8])
    if len(warnings) > 8:
        preview += f"\n• ... altri {len(warnings) - 8} avvisi nel PDF/registro."
    return "Avvisi/conflitti:\n" + preview


def _saved_note_message(note) -> str:
    pieces = [
        f"Nota salvata con ID <b>{note.id}</b>.",
        f"Settimana: {escape(note.target_week_start)} - {escape(note.target_week_end)}.",
    ]
    if note.interpreted_date:
        pieces.append(f"Data interpretata: {escape(note.interpreted_date)}.")
    return "\n".join(pieces)


def _is_iso_date(value: str) -> bool:
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return False
    return True
