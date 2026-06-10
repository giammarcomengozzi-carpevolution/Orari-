"""Controlli per rendere il bot privato."""

from __future__ import annotations

from telegram import Update


def is_allowed_user(update: Update, allowed_user_id: int) -> bool:
    """True solo per l'utente Telegram autorizzato."""

    return bool(update.effective_user and update.effective_user.id == allowed_user_id)


async def reject_unauthorized(update: Update) -> None:
    """Risposta cortese per utenti non autorizzati."""

    if update.effective_message:
        await update.effective_message.reply_text(
            "Mi dispiace, questo bot è privato e non posso salvare o generare orari per questo utente."
        )
