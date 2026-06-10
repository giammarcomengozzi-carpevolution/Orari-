"""Factory dell'applicazione Telegram in long polling."""

from __future__ import annotations

from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
)

from orari_agent.config import BotConfig
from orari_agent.storage.db import connect
from orari_agent.storage.notes_repository import NotesRepository
from orari_agent.storage.operational_memory_repository import (
    OperationalMemoryRepository,
)
from orari_agent.storage.schedules_repository import SchedulesRepository
from orari_agent.storage.wife_calendar_repository import WifeCalendarRepository

from . import commands
from .schedule_service import ScheduleService


def build_application(config: BotConfig) -> Application:
    """Crea ApplicationBuilder e registra comandi/handler."""

    connection = connect(config.database_path)
    notes_repository = NotesRepository(connection)
    schedules_repository = SchedulesRepository(connection)
    wife_calendar_repository = WifeCalendarRepository(connection)
    operational_memory_repository = OperationalMemoryRepository(connection)
    schedule_service = ScheduleService(
        notes_repository,
        schedules_repository,
        wife_calendar_repository,
        operational_memory_repository,
        config.output_dir,
    )

    application = ApplicationBuilder().token(config.telegram_bot_token).build()
    application.bot_data["allowed_user_id"] = config.allowed_telegram_user_id
    application.bot_data["notes_repository"] = notes_repository
    application.bot_data["schedule_service"] = schedule_service
    application.bot_data["wife_calendar_repository"] = wife_calendar_repository
    application.bot_data["operational_memory_repository"] = (
        operational_memory_repository
    )
    application.bot_data["wife_calendar_import_dir"] = "data/imports"
    application.bot_data["database_path"] = config.database_path
    application.bot_data["data_dir"] = config.database_path.parent
    application.bot_data["backup_dir"] = config.database_path.parent / "backups"

    application.add_handler(CommandHandler("start", commands.start))
    application.add_handler(CommandHandler("aiuto", commands.aiuto))
    application.add_handler(CommandHandler("nota", commands.nota))
    application.add_handler(CommandHandler("lista", commands.lista))
    application.add_handler(CommandHandler("cancella", commands.cancella))
    application.add_handler(CommandHandler("cancella_tutte", commands.cancella_tutte))
    application.add_handler(CommandHandler("memoria", commands.memoria))
    application.add_handler(
        CommandHandler("memoria_aggiungi", commands.memoria_aggiungi)
    )
    application.add_handler(CommandHandler("memoria_lista", commands.memoria_lista))
    application.add_handler(
        CommandHandler("memoria_cancella", commands.memoria_cancella)
    )
    application.add_handler(CommandHandler("memoria_reset", commands.memoria_reset))
    application.add_handler(
        CommandHandler("carica_calendario_moglie", commands.carica_calendario_moglie)
    )
    application.add_handler(
        CommandHandler("calendario_moglie_info", commands.calendario_moglie_info)
    )
    application.add_handler(
        CommandHandler("calendario_moglie_reset", commands.calendario_moglie_reset)
    )
    application.add_handler(CommandHandler("backup", commands.backup))
    application.add_handler(CommandHandler("backup_info", commands.backup_info))
    application.add_handler(CommandHandler("moglie_set", commands.moglie_set))
    application.add_handler(CommandHandler("moglie_lista", commands.moglie_lista))
    application.add_handler(
        CommandHandler("moglie_importa_m", commands.moglie_importa_m)
    )
    application.add_handler(
        CommandHandler("importa_calendario_moglie", commands.importa_calendario_moglie)
    )
    application.add_handler(
        CommandHandler(
            "conferma_calendario_moglie", commands.conferma_calendario_moglie
        )
    )
    application.add_handler(CommandHandler("moglie_reset", commands.moglie_reset))
    application.add_handler(CommandHandler("moglie_cancella", commands.moglie_cancella))
    application.add_handler(
        CommandHandler("debug_calendario_moglie", commands.debug_calendario_moglie)
    )
    application.add_handler(CommandHandler("genera", commands.genera))
    application.add_handler(CommandHandler("reset_settimana", commands.reset_settimana))
    application.add_handler(MessageHandler(filters.PHOTO, commands.wife_calendar_image))
    application.add_handler(
        MessageHandler(filters.Document.ALL, commands.wife_calendar_document)
    )
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, commands.free_text)
    )
    return application


def run_bot(config: BotConfig) -> None:
    """Avvia il bot con getUpdates/long polling."""

    application = build_application(config)
    application.run_polling(drop_pending_updates=False)
