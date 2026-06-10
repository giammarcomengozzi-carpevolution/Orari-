"""Handler dei comandi Telegram."""

from __future__ import annotations

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

from .schedule_service import ScheduleService
from .security import is_allowed_user, reject_unauthorized


def _deps(
    context: ContextTypes.DEFAULT_TYPE,
) -> tuple[int, NotesRepository, ScheduleService]:
    return (
        int(context.application.bot_data["allowed_user_id"]),
        context.application.bot_data["notes_repository"],
        context.application.bot_data["schedule_service"],
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    allowed_user_id, _, _ = _deps(context)
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
    allowed_user_id, _, _ = _deps(context)
    if not is_allowed_user(update, allowed_user_id):
        await reject_unauthorized(update)
        return
    await update.effective_message.reply_text(
        "Comandi disponibili:\n"
        "/nota testo — salva una nota per la settimana\n"
        "/lista — mostra le note attive della prossima settimana\n"
        "/lista dal 17 al 23 giugno — mostra una settimana specifica\n"
        "/cancella 12 — cancella la nota con ID 12\n"
        "/genera — genera il PDF della prossima settimana\n"
        "/genera dal 17 al 23 giugno — genera una settimana specifica\n"
        "/reset_settimana dal 17 al 23 giugno confermo — archivia le note attive della settimana\n\n"
        "Puoi anche scrivere una frase normale: verrà salvata come nota, se non è un comando."
    )


async def nota(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    allowed_user_id, notes_repository, _ = _deps(context)
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
    allowed_user_id, notes_repository, _ = _deps(context)
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
    lines = [f"Note attive per {start.isoformat()} - {end.isoformat()}:"]
    for note in notes:
        date_label = f" ({note.interpreted_date})" if note.interpreted_date else ""
        lines.append(f"#{note.id}{date_label}: {note.raw_text}")
    await update.effective_message.reply_text("\n".join(lines))


async def cancella(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    allowed_user_id, notes_repository, _ = _deps(context)
    if not is_allowed_user(update, allowed_user_id):
        await reject_unauthorized(update)
        return
    if not context.args or not context.args[0].isdigit():
        await update.effective_message.reply_text(
            "Uso: /cancella ID, ad esempio /cancella 12"
        )
        return
    deleted = notes_repository.delete(int(context.args[0]))
    await update.effective_message.reply_text(
        "Nota cancellata." if deleted else "Nota non trovata tra quelle attive."
    )


async def genera(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    allowed_user_id, _, schedule_service = _deps(context)
    if not is_allowed_user(update, allowed_user_id):
        await reject_unauthorized(update)
        return
    await _generate_and_send(update, context, " ".join(context.args), schedule_service)


async def reset_settimana(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    allowed_user_id, notes_repository, _ = _deps(context)
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
    allowed_user_id, notes_repository, schedule_service = _deps(context)
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
