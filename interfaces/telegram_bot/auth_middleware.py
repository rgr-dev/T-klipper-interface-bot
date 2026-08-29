"""Allowlist middleware: runs before any handler.

- Resolves pending usernames (see core/auth.py) if the sender matches.
- Sets the main chat (for push alerts) the first time a confirmed user
  messages the bot, if it wasn't fixed via TELEGRAM_MAIN_CHAT_ID.
- Blocks the update if the user is not confirmed in the allowlist.
"""
from __future__ import annotations

from telegram import Update
from telegram.ext import ApplicationHandlerStop, ContextTypes

from core.context import AppContext

NOT_ALLOWED_MSG = "You are not authorized to use this bot."


async def enforce_allowlist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user is None:
        return

    ctx: AppContext = context.bot_data["app_context"]
    ctx.allowlist.resolve_pending(user.username, user.id)

    if not ctx.allowlist.is_allowed(user.id):
        if update.effective_message:
            await update.effective_message.reply_text(NOT_ALLOWED_MSG)
        elif update.callback_query:
            await update.callback_query.answer(NOT_ALLOWED_MSG, show_alert=True)
        raise ApplicationHandlerStop

    if ctx.state_store.get_main_chat_id() is None and update.effective_chat is not None:
        ctx.state_store.set_main_chat_id(update.effective_chat.id)
