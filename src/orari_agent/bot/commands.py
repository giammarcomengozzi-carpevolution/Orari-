"""Handler dei comandi Telegram."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from uuid import uuid4

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

from .note_messages import saved_note_message
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
        "/moglie_importa_m date1,date2,... — importa più date M\n"
        "/importa_calendario_moglie — salva una foto calendario per import semi-manuale\n"
        "/moglie_lista — mostra i codici salvati\n"
        "/moglie_lista M — mostra solo le date M\n"
        "/moglie_cancella YYYY-MM-DD — elimina un codice salvato\n"
        "/moglie_reset confermo — svuota il calendario moglie\n"
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
        saved_note_message(note), parse_mode=ParseMode.HTML
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
    code_filter = context.args[0].upper() if context.args else None
    entries = wife_repository.list_entries(code_filter)
    if not entries:
        message = (
            f"Nessun codice calendario moglie salvato con codice {code_filter}."
            if code_filter
            else "Nessun codice calendario moglie salvato."
        )
        await update.effective_message.reply_text(message)
        return
    title = (
        f"Codici calendario moglie salvati ({code_filter}):"
        if code_filter
        else "Codici calendario moglie salvati:"
    )
    lines = [title]
    lines.extend(f"{entry.date}: {entry.code}" for entry in entries)
    await update.effective_message.reply_text("\n".join(lines))


async def moglie_importa_m(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    allowed_user_id, _, _, wife_repository = _deps(context)
    if not is_allowed_user(update, allowed_user_id):
        await reject_unauthorized(update)
        return
    text = update.effective_message.text or ""
    dates, invalid = _parse_import_dates(text, "/moglie_importa_m")
    if not dates:
        await update.effective_message.reply_text(
            "Nessuna data M valida trovata. Usa: /moglie_importa_m 2026-09-03,2026-09-10"
        )
        return
    inserted, updated = wife_repository.bulk_upsert_code(
        dates, "M", source="telegram_bulk_import"
    )
    await update.effective_message.reply_text(
        _bulk_import_summary(dates, invalid, inserted, updated)
    )


async def moglie_reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    allowed_user_id, _, _, wife_repository = _deps(context)
    if not is_allowed_user(update, allowed_user_id):
        await reject_unauthorized(update)
        return
    if context.args != ["confermo"]:
        await update.effective_message.reply_text(
            "Per sicurezza, ripeti con: /moglie_reset confermo"
        )
        return
    wife_repository.reset()
    await update.effective_message.reply_text("Calendario moglie svuotato.")


async def importa_calendario_moglie(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    allowed_user_id, _, _, wife_repository = _deps(context)
    if not is_allowed_user(update, allowed_user_id):
        await reject_unauthorized(update)
        return
    if update.effective_message.photo:
        await _save_wife_calendar_image(update, context, wife_repository)
        return
    context.user_data["awaiting_wife_calendar_image"] = True
    await update.effective_message.reply_text(
        "Mandami ora la foto della tabella orari di tua moglie."
    )


async def wife_calendar_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    allowed_user_id, _, _, wife_repository = _deps(context)
    if not is_allowed_user(update, allowed_user_id):
        await reject_unauthorized(update)
        return
    caption = (update.effective_message.caption or "").strip()
    waiting = bool(context.user_data.get("awaiting_wife_calendar_image"))
    if not waiting and not caption.startswith("/importa_calendario_moglie"):
        return
    await _save_wife_calendar_image(update, context, wife_repository)


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
        saved_note_message(note), parse_mode=ParseMode.HTML
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


def _parse_import_dates(text: str, command: str) -> tuple[list[str], list[str]]:
    payload = text.strip()
    first_token = payload.split(maxsplit=1)[0] if payload else ""
    if first_token == command or first_token.startswith(command + "@"):
        payload = payload[len(first_token) :]
    tokens = [
        token.strip() for token in re.split(r"[,;\s]+", payload) if token.strip()
    ]
    valid: list[str] = []
    invalid: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        if _is_iso_date(token):
            if token not in seen:
                valid.append(token)
                seen.add(token)
        else:
            invalid.append(token)
    return sorted(valid), invalid


def _bulk_import_summary(
    dates: list[str], invalid: list[str], inserted: int, updated: int
) -> str:
    preview = ", ".join(dates[:10])
    if len(dates) > 10:
        preview += f", ... (+{len(dates) - 10})"
    lines = [
        "Import calendario moglie completato.",
        f"Date M salvate: {len(dates)}.",
        f"Inserite: {inserted}. Aggiornate: {updated}.",
        f"Prima data importata: {dates[0]}.",
        f"Ultima data importata: {dates[-1]}.",
        f"Prime date: {preview}.",
    ]
    if invalid:
        invalid_preview = ", ".join(invalid[:10])
        lines.append(f"Date ignorate perché non valide: {invalid_preview}.")
    return "\n".join(lines)


async def _save_wife_calendar_image(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    wife_repository: WifeCalendarRepository,
) -> None:
    import_dir = Path(
        context.application.bot_data.get("wife_calendar_import_dir", "data/imports")
    )
    import_dir.mkdir(parents=True, exist_ok=True)
    photo = update.effective_message.photo[-1]
    telegram_file = await photo.get_file()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    image_path = import_dir / f"moglie_{timestamp}_{uuid4().hex[:8]}.jpg"
    await telegram_file.download_to_drive(custom_path=image_path)
    warning = (
        "OCR automatico non abilitato: serve elenco date M con /moglie_importa_m."
    )
    wife_repository.add_import_record(
        source="telegram_image",
        image_path=str(image_path),
        status="saved_needs_manual_dates",
        summary="Foto calendario moglie ricevuta e salvata.",
        warnings=[warning],
    )
    context.user_data["awaiting_wife_calendar_image"] = False
    await update.effective_message.reply_text(
        "Foto calendario ricevuta e salvata.\n"
        "In questa versione non leggo ancora automaticamente la tabella con sicurezza.\n"
        "Mandami l’elenco delle date M con /moglie_importa_m."
    )


def _is_iso_date(value: str) -> bool:
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return False
    return True
