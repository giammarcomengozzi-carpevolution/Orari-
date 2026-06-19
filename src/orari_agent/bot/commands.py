"""Handler dei comandi Telegram."""

from __future__ import annotations

import mimetypes
import re
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from orari_agent.ai_agent import AiAgent
from orari_agent.backup import collect_backup_info, create_backup
from orari_agent.storage.voice_transcripts_repository import VoiceTranscriptsRepository
from orari_agent.voice import (
    AudioTooLargeError,
    AudioTranscriber,
    AudioTranscriptionError,
    OpenAiUnavailableError,
    SUPPORTED_AUDIO_EXTENSIONS,
    supported_audio_extension,
    supported_audio_mime_type,
    validate_audio_size,
)

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from orari_agent.storage.notes_repository import NotesRepository
from orari_agent.storage.operational_memory_parser import parse_operational_memory
from orari_agent.storage.operational_memory_repository import (
    OperationalMemory,
    OperationalMemoryRepository,
)
from orari_agent.storage.week_parser import (
    current_or_next_week_bounds,
    parse_note_metadata,
    parse_week_request,
)
from orari_agent.storage.wife_calendar_repository import WifeCalendarRepository
from orari_agent.wife_calendar_excel import extract_m_dates_from_excel
from orari_agent.wife_calendar_ocr import (
    WifeCalendarOcrResult,
    extract_m_dates_from_image,
)

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


def _memory_repo(context: ContextTypes.DEFAULT_TYPE) -> OperationalMemoryRepository:
    return context.application.bot_data["operational_memory_repository"]


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
        "/memoria — aiuto memoria operativa persistente\n"
        "/memoria_aggiungi testo — salva ferie, assenze o vincoli futuri\n"
        "/memoria_lista [mese] — mostra memorie attive\n"
        "/memoria_cancella ID — archivia una memoria\n"
        "/memoria_reset confermo — archivia tutte le memorie\n"
        "/moglie_set YYYY-MM-DD M — salva un codice del calendario moglie\n"
        "/moglie_importa_m date1,date2,... — importa più date M\n"
        "/importa_calendario_moglie — legge automaticamente una foto calendario e propone solo M\n"
        "/conferma_calendario_moglie — conferma l’ultimo OCR e salva le date M\n"
        "/debug_calendario_moglie — mostra l’ultimo riepilogo import/OCR\n"
        "/moglie_lista — mostra i codici salvati\n"
        "/moglie_lista M — mostra solo le date M\n"
        "/moglie_cancella YYYY-MM-DD — elimina un codice salvato\n"
        "/moglie_reset confermo — svuota il calendario moglie\n"
        "/genera — genera il PDF della prossima settimana\n"
        "/genera dal 17 al 23 giugno — genera una settimana specifica\n"
        "/reset_settimana dal 17 al 23 giugno confermo — archivia le note attive della settimana\n"
        "/trascrivi_ultimo — mostra l’ultima trascrizione vocale salvata\n\n"
        "Puoi anche scrivere una frase normale o mandare un vocale: verrà interpretato dall’AI."
    )


async def memoria(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    allowed_user_id, _, _, _ = _deps(context)
    if not is_allowed_user(update, allowed_user_id):
        await reject_unauthorized(update)
        return
    await update.effective_message.reply_text(
        "Memoria operativa persistente:\n"
        "• /memoria_aggiungi Lorenzo in ferie dal 10 al 15 agosto\n"
        "• /memoria_aggiungi Angelo assente il 27 giugno\n"
        "• /memoria_aggiungi Angelo non c’è il 3 settembre mattina\n"
        "• /memoria_aggiungi Gianmarco dal commercialista ogni giovedì mattina\n"
        "• /memoria_lista [luglio]\n"
        "• /memoria_cancella ID\n"
        "• /memoria_reset confermo\n\n"
        "Puoi anche scrivere: ‘ricordati che ...’, ‘memorizza che ...’ "
        "o ‘salva memoria ...’."
    )


async def memoria_aggiungi(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    allowed_user_id, _, _, _ = _deps(context)
    if not is_allowed_user(update, allowed_user_id):
        await reject_unauthorized(update)
        return
    text = " ".join(context.args).strip()
    if not text:
        await update.effective_message.reply_text(
            "Scrivi il testo dopo /memoria_aggiungi, ad esempio: "
            "/memoria_aggiungi Angelo assente il 27 giugno"
        )
        return
    memory = _save_memory_text(_memory_repo(context), text)
    await update.effective_message.reply_text(_memory_saved_message(memory))


async def memoria_lista(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    allowed_user_id, _, _, _ = _deps(context)
    if not is_allowed_user(update, allowed_user_id):
        await reject_unauthorized(update)
        return
    month_filter = context.args[0].lower() if context.args else None
    memories = _memory_repo(context).list_active()
    if month_filter:
        memories = [
            memory
            for memory in memories
            if _memory_matches_filter(memory, month_filter)
        ]
    if not memories:
        await update.effective_message.reply_text(
            "Nessuna memoria operativa attiva trovata."
        )
        return
    lines = ["Memorie operative attive:"]
    for memory in memories:
        when = (
            memory.recurrence_rule
            or _format_memory_period(memory)
            or "data non interpretata"
        )
        lines.append(
            f"ID {memory.id} | {when} | {memory.person or 'persona non indicata'} "
            f"| {memory.constraint_type} | {memory.raw_text}"
        )
    await update.effective_message.reply_text("\n".join(lines))


async def memoria_cancella(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    allowed_user_id, _, _, _ = _deps(context)
    if not is_allowed_user(update, allowed_user_id):
        await reject_unauthorized(update)
        return
    if not context.args or not context.args[0].isdigit():
        await update.effective_message.reply_text("Uso: /memoria_cancella ID")
        return
    deleted = _memory_repo(context).delete(int(context.args[0]))
    await update.effective_message.reply_text(
        f"Memoria {context.args[0]} cancellata."
        if deleted
        else f"Memoria {context.args[0]} non trovata o già cancellata."
    )


async def memoria_reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    allowed_user_id, _, _, _ = _deps(context)
    if not is_allowed_user(update, allowed_user_id):
        await reject_unauthorized(update)
        return
    if context.args != ["confermo"]:
        await update.effective_message.reply_text(
            "Per sicurezza, ripeti con: /memoria_reset confermo"
        )
        return
    count = _memory_repo(context).reset()
    await update.effective_message.reply_text(
        f"Memoria operativa svuotata: {count} regole archiviate."
    )


def _save_memory_text(
    repository: OperationalMemoryRepository, text: str
) -> OperationalMemory:
    return repository.add(parse_operational_memory(text), source="telegram")


def _memory_saved_message(memory: OperationalMemory) -> str:
    lines = [
        f"Memoria salvata con ID {memory.id}.",
        f"Testo: {memory.raw_text}",
        f"Tipo: {memory.constraint_type}",
        f"Persona: {memory.person or 'non indicata'}",
    ]
    period = _format_memory_period(memory)
    if period:
        lines.append(f"Periodo: {period}")
    if memory.recurrence_rule:
        lines.append(f"Ricorrenza: {memory.recurrence_rule}")
    if memory.start_time and memory.end_time:
        lines.append(f"Orario: {memory.start_time}-{memory.end_time}")
    if memory.constraint_type == "promemoria_non_interpretato":
        lines.append(
            "Effetto: ho salvato il testo, ma non sono riuscito a trasformarlo "
            "in un vincolo automatico. Verrà mostrato come promemoria "
            "durante la generazione."
        )
    else:
        lines.append(
            "Effetto: il vincolo sarà applicato automaticamente agli orari "
            "sovrapposti."
        )
    return "\n".join(lines)


def _format_memory_period(memory: OperationalMemory) -> str | None:
    if memory.start_date and memory.end_date and memory.start_date != memory.end_date:
        return f"{memory.start_date} - {memory.end_date}"
    return memory.start_date


def _memory_matches_filter(memory: OperationalMemory, month_filter: str) -> bool:
    if month_filter in (memory.raw_text or "").lower():
        return True
    month_numbers = {
        "gennaio": "-01-",
        "febbraio": "-02-",
        "marzo": "-03-",
        "aprile": "-04-",
        "maggio": "-05-",
        "giugno": "-06-",
        "luglio": "-07-",
        "agosto": "-08-",
        "settembre": "-09-",
        "ottobre": "-10-",
        "novembre": "-11-",
        "dicembre": "-12-",
    }
    token = month_numbers.get(month_filter)
    if token is None:
        return True
    return token in (memory.start_date or "") or token in (memory.end_date or "")


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


async def carica_calendario_moglie(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    allowed_user_id, _, _, wife_repository = _deps(context)
    if not is_allowed_user(update, allowed_user_id):
        await reject_unauthorized(update)
        return
    if update.effective_message.document:
        await _save_wife_calendar_excel(update, context, wife_repository)
        return
    context.user_data["awaiting_wife_calendar_excel"] = True
    await update.effective_message.reply_text(
        "Mandami ora il file Excel .xlsx del calendario moglie. "
        "Importerò solo le celle con codice M: P, I, F, colori e celle vuote saranno ignorati."
    )


async def wife_calendar_document(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    allowed_user_id, _, _, wife_repository = _deps(context)
    if not is_allowed_user(update, allowed_user_id):
        await reject_unauthorized(update)
        return
    document = update.effective_message.document
    if document is None:
        return
    caption = (update.effective_message.caption or "").strip()
    waiting = bool(context.user_data.get("awaiting_wife_calendar_excel"))
    if not waiting and not caption.startswith("/carica_calendario_moglie"):
        return
    await _save_wife_calendar_excel(update, context, wife_repository)


async def calendario_moglie_info(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    allowed_user_id, _, _, wife_repository = _deps(context)
    if not is_allowed_user(update, allowed_user_id):
        await reject_unauthorized(update)
        return
    entries = wife_repository.list_entries("M")
    latest = wife_repository.latest_import_record()
    lines = ["Info calendario moglie:"]
    if entries:
        lines.extend(
            [
                f"Prima data caricata: {entries[0].date}",
                f"Ultima data caricata: {entries[-1].date}",
                f"Numero date M: {len(entries)}",
            ]
        )
    else:
        lines.extend(
            [
                "Prima data caricata: nessuna",
                "Ultima data caricata: nessuna",
                "Numero date M: 0",
            ]
        )
    lines.append(
        "Ultimo import: "
        + (
            f"{latest.created_at} ({latest.source}, {latest.status})"
            if latest
            else "nessuno"
        )
    )
    lines.append(
        "Regola attiva: solo le date M salvate bloccano Gianmarco all'apertura lago 07:30; date future mancanti = nessun vincolo."
    )
    await update.effective_message.reply_text("\n".join(lines))


async def calendario_moglie_reset(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    allowed_user_id, _, _, wife_repository = _deps(context)
    if not is_allowed_user(update, allowed_user_id):
        await reject_unauthorized(update)
        return
    if context.args != ["confermo"]:
        await update.effective_message.reply_text(
            "Per sicurezza, ripeti con: /calendario_moglie_reset confermo"
        )
        return
    count = wife_repository.reset()
    wife_repository.add_import_record(
        source="telegram_reset",
        status="reset",
        summary=f"Calendario moglie svuotato: {count} righe eliminate.",
        warnings=[],
    )
    await update.effective_message.reply_text(
        f"Calendario moglie svuotato: {count} righe eliminate."
    )


async def backup(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    allowed_user_id, _, _, _ = _deps(context)
    if not is_allowed_user(update, allowed_user_id):
        await reject_unauthorized(update)
        return
    database_path = Path(
        context.application.bot_data.get("database_path", "data/orari_bot.sqlite3")
    )
    data_dir = Path(context.application.bot_data.get("data_dir", "data"))
    backup_dir = Path(
        context.application.bot_data.get("backup_dir", data_dir / "backups")
    )
    zip_path = create_backup(
        database_path=database_path, data_dir=data_dir, backup_dir=backup_dir
    )
    with zip_path.open("rb") as backup_file:
        await update.effective_message.reply_document(
            document=backup_file,
            filename=zip_path.name,
            caption=f"Backup creato: {zip_path.name}",
        )


async def backup_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    allowed_user_id, _, _, _ = _deps(context)
    if not is_allowed_user(update, allowed_user_id):
        await reject_unauthorized(update)
        return
    database_path = Path(
        context.application.bot_data.get("database_path", "data/orari_bot.sqlite3")
    )
    data_dir = Path(context.application.bot_data.get("data_dir", "data"))
    backup_dir = Path(
        context.application.bot_data.get("backup_dir", data_dir / "backups")
    )
    info = collect_backup_info(database_path, backup_dir)
    await update.effective_message.reply_text(
        "Backup info:\n"
        f"Database: {info.database_path}\n"
        f"Note: {info.notes_count}\n"
        f"Memorie operative: {info.memories_count}\n"
        f"Date calendario moglie: {info.wife_calendar_entries_count}\n"
        f"Ultimo backup: {info.latest_backup.name if info.latest_backup else 'nessuno'}"
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


async def wife_calendar_image(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    allowed_user_id, _, _, wife_repository = _deps(context)
    if not is_allowed_user(update, allowed_user_id):
        await reject_unauthorized(update)
        return
    caption = (update.effective_message.caption or "").strip()
    waiting = bool(context.user_data.get("awaiting_wife_calendar_image"))
    if not waiting and not caption.startswith("/importa_calendario_moglie"):
        return
    await _save_wife_calendar_image(update, context, wife_repository)


async def conferma_calendario_moglie(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    allowed_user_id, _, _, wife_repository = _deps(context)
    if not is_allowed_user(update, allowed_user_id):
        await reject_unauthorized(update)
        return
    record = wife_repository.latest_import_record()
    if record is None:
        await update.effective_message.reply_text(
            "Nessun OCR calendario moglie da confermare."
        )
        return
    candidate_dates = _candidate_dates_from_import_summary(record.summary)
    if record.status != "ocr_pending_confirmation" or not candidate_dates:
        await update.effective_message.reply_text(
            "Nessuna data M candidata da confermare. "
            "Usa /importa_calendario_moglie o /moglie_importa_m."
        )
        return
    inserted, updated = wife_repository.bulk_upsert_code(
        candidate_dates, "M", source="telegram_image_ocr_confirmed"
    )
    confirmation_summary = (
        f"{record.summary}\n"
        f"Confermato e salvato: {len(candidate_dates)} date M. "
        f"Inserite: {inserted}. Aggiornate: {updated}."
    )
    wife_repository.update_import_record(
        record.id,
        status="ocr_confirmed",
        summary=confirmation_summary,
        warnings=record.warnings.splitlines(),
    )
    await update.effective_message.reply_text(
        "Calendario moglie confermato.\n"
        f"Date M salvate: {len(candidate_dates)}.\n"
        f"Date salvate: {', '.join(candidate_dates)}.\n"
        "Controlla con /moglie_lista M."
    )


async def debug_calendario_moglie(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    allowed_user_id, _, _, wife_repository = _deps(context)
    if not is_allowed_user(update, allowed_user_id):
        await reject_unauthorized(update)
        return
    record = wife_repository.latest_import_record()
    if record is None:
        await update.effective_message.reply_text(
            "Nessun import calendario moglie registrato."
        )
        return
    lines = [
        "Debug ultimo import calendario moglie:",
        f"ID: {record.id}",
        f"Creato: {record.created_at}",
        f"Image path: {record.image_path or 'non disponibile'}",
        f"OCR status: {record.status}",
        f"Summary: {record.summary}",
        "Warnings:",
    ]
    lines.extend(
        f"• {warning}" for warning in record.warnings.splitlines() if warning.strip()
    )
    if lines[-1] == "Warnings:":
        lines.append("• nessun warning")
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
    allowed_user_id, _, _, _ = _deps(context)
    if not is_allowed_user(update, allowed_user_id):
        await reject_unauthorized(update)
        return
    text = (update.effective_message.text or "").strip()
    if not text:
        return
    await _handle_ai_agent_text(update, context, text)


async def trascrivi_ultimo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    allowed_user_id, _, _, _ = _deps(context)
    if not is_allowed_user(update, allowed_user_id):
        await reject_unauthorized(update)
        return
    repository: VoiceTranscriptsRepository | None = context.application.bot_data.get(
        "voice_transcripts_repository"
    )
    if repository is None:
        await update.effective_message.reply_text(
            "Archivio trascrizioni non configurato."
        )
        return
    user_id = _effective_user_id(update, allowed_user_id)
    transcript = repository.latest_for_user(user_id)
    if transcript is None:
        await update.effective_message.reply_text(
            "Nessuna trascrizione vocale salvata."
        )
        return
    await update.effective_message.reply_text(
        "🎤 Ultima trascrizione:\n"
        f"{_preview_transcript(transcript.transcript)}\n\n"
        f"File: {transcript.file_name}\n"
        f"Data: {transcript.created_at}"
    )


async def voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    allowed_user_id, _, _, _ = _deps(context)
    if not is_allowed_user(update, allowed_user_id):
        await reject_unauthorized(update)
        return

    transcriber: AudioTranscriber | None = context.application.bot_data.get(
        "audio_transcriber"
    )
    if transcriber is None:
        await update.effective_message.reply_text(
            "Trascrizione non disponibile: controlla OPENAI_API_KEY."
        )
        return

    try:
        attachment, file_name = _audio_attachment(update)
        validate_audio_size(getattr(attachment, "file_size", None))
    except AudioTooLargeError:
        await update.effective_message.reply_text("Messaggio vocale troppo grande.")
        return
    except ValueError:
        await update.effective_message.reply_text(
            "Formato audio non supportato. Usa ogg, mp3, m4a o wav."
        )
        return

    audio_dir = Path(context.application.bot_data.get("audio_dir", "data/audio"))
    audio_dir.mkdir(parents=True, exist_ok=True)
    audio_path = audio_dir / _safe_audio_filename(file_name)

    try:
        telegram_file = await attachment.get_file()
        await telegram_file.download_to_drive(custom_path=audio_path)
        validate_audio_size(audio_path.stat().st_size)
        transcript = transcriber.transcribe(audio_path)
    except AudioTooLargeError:
        _cleanup_audio_file(audio_path, context)
        await update.effective_message.reply_text("Messaggio vocale troppo grande.")
        return
    except OpenAiUnavailableError:
        _cleanup_audio_file(audio_path, context)
        await update.effective_message.reply_text(
            "Trascrizione non disponibile: controlla OPENAI_API_KEY."
        )
        return
    except AudioTranscriptionError:
        _cleanup_audio_file(audio_path, context)
        await update.effective_message.reply_text(
            "Non sono riuscito a trascrivere il messaggio vocale."
        )
        return
    except Exception:  # noqa: BLE001 - errore I/O Telegram/OpenAI normalizzato per chat
        _cleanup_audio_file(audio_path, context)
        await update.effective_message.reply_text(
            "Non sono riuscito a trascrivere il messaggio vocale."
        )
        return

    if not transcript.strip():
        _cleanup_audio_file(audio_path, context)
        await update.effective_message.reply_text(
            "Non sono riuscito a trascrivere il messaggio vocale."
        )
        return

    repository: VoiceTranscriptsRepository | None = context.application.bot_data.get(
        "voice_transcripts_repository"
    )
    user_id = _effective_user_id(update, allowed_user_id)
    if repository is not None:
        repository.add(audio_path.name, transcript, user_id)
    if context.application.bot_data.get("voice_debug", False):
        audio_path.with_suffix(audio_path.suffix + ".txt").write_text(
            transcript, encoding="utf-8"
        )
    else:
        _cleanup_audio_file(audio_path, context)

    await _handle_ai_agent_text(
        update,
        context,
        transcript,
        reply_prefix=f"🎤 Trascrizione:\n{_preview_transcript(transcript)}\n\n🤖 Interpretazione:\n",
    )


async def _handle_ai_agent_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
    reply_prefix: str = "",
) -> None:
    allowed_user_id, _, _, _ = _deps(context)
    ai_agent: AiAgent | None = context.application.bot_data.get("ai_agent")
    if ai_agent is None:
        await update.effective_message.reply_text(
            f"{reply_prefix}Modalità AI non configurata: manca OPENAI_API_KEY."
        )
        return
    user_id = _effective_user_id(update, allowed_user_id)
    result = ai_agent.handle_message(user_id, text)
    generated_results = [
        tool_result.generated_schedule
        for tool_result in result.tool_results
        if tool_result.generated_schedule is not None
    ]
    await update.effective_message.reply_text(f"{reply_prefix}{result.user_message}")
    for generated in generated_results:
        warning_text = _warnings_text(generated.warnings)
        with generated.pdf_path.open("rb") as pdf_file:
            await update.effective_message.reply_document(
                document=pdf_file,
                filename=generated.pdf_path.name,
                caption=_short_document_caption(generated.summary),
            )
        await _send_long_text_in_chunks(
            update.effective_message, f"{generated.summary}\n{warning_text}"
        )


def _effective_user_id(update: Update, allowed_user_id: int) -> int:
    return int(update.effective_user.id) if update.effective_user else allowed_user_id


def _preview_transcript(transcript: str, limit: int = 1000) -> str:
    clean = transcript.strip()
    if len(clean) <= limit:
        return clean
    return clean[:limit].rstrip() + "…\n[Trascrizione completa salvata internamente.]"


def _audio_attachment(update: Update):
    message = update.effective_message
    if message.voice is not None:
        file_unique = getattr(message.voice, "file_unique_id", "voice") or "voice"
        return message.voice, f"voice_{file_unique}.ogg"
    if message.audio is not None:
        file_name = getattr(message.audio, "file_name", "") or "audio"
        mime_type = getattr(message.audio, "mime_type", None)
        return message.audio, _audio_filename_with_supported_extension(
            file_name, mime_type
        )
    if message.document is not None:
        document = message.document
        file_name = getattr(document, "file_name", "") or "audio"
        mime_type = getattr(document, "mime_type", None)
        if not (
            supported_audio_mime_type(mime_type) or supported_audio_extension(file_name)
        ):
            raise ValueError("Documento non audio")
        return document, _audio_filename_with_supported_extension(file_name, mime_type)
    raise ValueError("Nessun audio trovato")


def _audio_filename_with_supported_extension(
    file_name: str, mime_type: str | None
) -> str:
    if supported_audio_extension(file_name):
        return file_name
    mime_extensions = {
        "audio/ogg": ".ogg",
        "audio/oga": ".ogg",
        "audio/mpeg": ".mp3",
        "audio/mp3": ".mp3",
        "audio/mp4": ".m4a",
        "audio/m4a": ".m4a",
        "audio/x-m4a": ".m4a",
        "audio/wav": ".wav",
        "audio/wave": ".wav",
        "audio/x-wav": ".wav",
    }
    clean_mime = (mime_type or "").lower().split(";", 1)[0].strip()
    guessed_extension = mime_extensions.get(clean_mime)
    guessed_extension = (
        guessed_extension or mimetypes.guess_extension(clean_mime) or ".ogg"
    )
    if guessed_extension == ".oga":
        guessed_extension = ".ogg"
    if guessed_extension not in SUPPORTED_AUDIO_EXTENSIONS:
        raise ValueError("Formato audio non supportato")
    return f"{Path(file_name).stem or 'audio'}{guessed_extension}"


def _safe_audio_filename(file_name: str) -> str:
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", Path(file_name).name).strip("._")
    if not safe_name:
        safe_name = "audio.ogg"
    suffix = Path(safe_name).suffix.lower()
    if suffix not in SUPPORTED_AUDIO_EXTENSIONS:
        safe_name += ".ogg"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{timestamp}_{uuid4().hex[:8]}_{safe_name}"


def _cleanup_audio_file(audio_path: Path, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.application.bot_data.get("voice_debug", False):
        return
    audio_path.unlink(missing_ok=True)


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
            caption=_short_document_caption(result.summary),
        )
    await _send_long_text_in_chunks(
        update.effective_message, f"{result.summary}\n{warning_text}"
    )


def _short_document_caption(summary: str) -> str:
    match = re.search(
        r"Orario generato per (\d{4}-\d{2}-\d{2}) / (\d{4}-\d{2}-\d{2})",
        summary,
    )
    if match:
        return f"Orario generato per {match.group(1)} / {match.group(2)}. PDF allegato."
    return "Orario generato. PDF allegato."


async def _send_long_text_in_chunks(message, text: str, max_chars: int = 3500) -> None:
    clean_text = text.strip()
    if not clean_text:
        return
    for chunk in _split_text_chunks(clean_text, max_chars=max_chars):
        await message.reply_text(chunk)


def _split_text_chunks(text: str, max_chars: int = 3500) -> list[str]:
    if max_chars <= 0:
        raise ValueError("max_chars deve essere positivo")
    chunks: list[str] = []
    current = ""
    for line in text.splitlines():
        pending_lines = [line] if line else [""]
        while pending_lines:
            pending_line = pending_lines.pop(0)
            separator = "\n" if current else ""
            if len(current) + len(separator) + len(pending_line) <= max_chars:
                current = f"{current}{separator}{pending_line}"
                break
            if current:
                chunks.append(current)
                current = ""
                pending_lines.insert(0, pending_line)
                continue
            chunks.append(pending_line[:max_chars])
            remainder = pending_line[max_chars:]
            if remainder:
                pending_lines.insert(0, remainder)
    if current:
        chunks.append(current)
    return chunks


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
    tokens = [token.strip() for token in re.split(r"[,;\s]+", payload) if token.strip()]
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

    result = extract_m_dates_from_image(image_path, year=datetime.now().year)
    context.user_data["awaiting_wife_calendar_image"] = False

    if result.is_high_confidence and result.imported_dates:
        summary = _ocr_pending_summary(result)
        wife_repository.add_import_record(
            source="telegram_image",
            image_path=str(image_path),
            status="ocr_pending_confirmation",
            summary=summary,
            warnings=result.warnings,
        )
        await update.effective_message.reply_text(
            "Calendario moglie letto automaticamente.\n"
            f"Date M candidate trovate: {len(result.imported_dates)}.\n"
            f"Date trovate: {', '.join(result.imported_dates)}.\n"
            f"Confidenza OCR: {result.confidence:.0%}.\n"
            "Attenzione: non ho ancora salvato queste date.\n"
            "Se sono corrette, conferma con /conferma_calendario_moglie."
        )
        return

    status = "ocr_low_confidence" if result.confidence > 0 else "ocr_failed"
    warnings = result.warnings or [
        "Lettura OCR non abbastanza sicura per import automatico."
    ]
    summary = (
        f"{result.debug_summary}\n"
        "Date M candidate: "
        f"{', '.join(result.imported_dates) if result.imported_dates else 'nessuna'}\n"
        f"Dipendenze OCR: {result.ocr_status}"
    )
    wife_repository.add_import_record(
        source="telegram_image",
        image_path=str(image_path),
        status=status,
        summary=summary,
        warnings=warnings,
    )
    await update.effective_message.reply_text(
        "Ho ricevuto la foto ma non sono abbastanza sicuro della lettura.\n"
        "Non ho salvato automaticamente le date.\n"
        "Puoi mandarmi una foto più dritta e nitida oppure usare /moglie_importa_m."
        f"\nDettaglio OCR: {warnings[0]}"
    )


async def _save_wife_calendar_excel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    wife_repository: WifeCalendarRepository,
) -> None:
    import_dir = Path(
        context.application.bot_data.get("wife_calendar_import_dir", "data/imports")
    )
    import_dir.mkdir(parents=True, exist_ok=True)
    document = update.effective_message.document
    filename = getattr(document, "file_name", "") or "calendario_moglie.xlsx"
    if not filename.lower().endswith(".xlsx"):
        await update.effective_message.reply_text(
            "File non valido: manda un file Excel .xlsx."
        )
        return
    telegram_file = await document.get_file()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    excel_path = import_dir / f"moglie_{timestamp}_{uuid4().hex[:8]}.xlsx"
    await telegram_file.download_to_drive(custom_path=excel_path)
    context.user_data["awaiting_wife_calendar_excel"] = False

    try:
        result = extract_m_dates_from_excel(excel_path)
    except Exception as exc:  # noqa: BLE001 - errore file utente da mostrare in chat
        wife_repository.add_import_record(
            source="telegram_excel",
            image_path=str(excel_path),
            status="excel_failed",
            summary=f"Import Excel fallito: {exc}",
            warnings=[str(exc)],
        )
        await update.effective_message.reply_text(
            "Non sono riuscito a leggere il file Excel. Controlla che sia un .xlsx valido."
        )
        return

    inserted, updated = (
        wife_repository.bulk_upsert_code(result.dates, "M", source="telegram_excel")
        if result.dates
        else (0, 0)
    )
    summary = (
        "Import Excel calendario moglie completato.\n"
        f"Date M trovate: {len(result.dates)}.\n"
        f"Celle M lette: {result.m_cells}. Celle non vuote analizzate: {result.scanned_cells}.\n"
        f"Inserite: {inserted}. Aggiornate: {updated}."
    )
    if result.dates:
        summary += f"\nPrima data: {result.dates[0]}. Ultima data: {result.dates[-1]}."
    wife_repository.add_import_record(
        source="telegram_excel",
        image_path=str(excel_path),
        status="excel_imported",
        summary=summary,
        warnings=result.warnings,
    )
    await update.effective_message.reply_text(
        summary
        + "\nSolo M è stato importato; P, I, F, colori e celle vuote sono stati ignorati."
    )


def _ocr_pending_summary(result: WifeCalendarOcrResult) -> str:
    dates = result.imported_dates
    return (
        "Calendario moglie letto automaticamente, in attesa di conferma.\n"
        f"Date M candidate: {', '.join(dates)}\n"
        f"Date M candidate trovate: {len(dates)}.\n"
        f"Confidenza OCR: {result.confidence:.0%}.\n"
        f"Debug: {result.debug_summary}\n"
        f"Dipendenze OCR: {result.ocr_status}"
    )


def _candidate_dates_from_import_summary(summary: str) -> list[str]:
    for line in summary.splitlines():
        if line.startswith("Date M candidate:"):
            payload = line.split(":", 1)[1]
            return [
                token.strip()
                for token in payload.split(",")
                if _is_iso_date(token.strip())
            ]
    return []


def _is_iso_date(value: str) -> bool:
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return False
    return True
