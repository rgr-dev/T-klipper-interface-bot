"""Builds the python-telegram-bot Application and registers the handlers.

This module is the only place that touches the Telegram library; the
handlers in handlers/ only call core/services/*.
"""
from __future__ import annotations

import os

from telegram import Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    TypeHandler,
)

from core.context import AppContext
from core.services import notifier
from interfaces.telegram_bot.auth_middleware import enforce_allowlist
from interfaces.telegram_bot.handlers import (
    camera,
    control,
    files,
    printers,
    start,
    status,
    timelapses,
)
from interfaces.telegram_bot.keyboards import (
    CANCEL_PREFIX,
    SELECT_PRINTER_PREFIX,
    START_PRINT_PREFIX,
    TIMELAPSE_DOWNLOAD_PREFIX,
)

AUTH_MIDDLEWARE_GROUP = -1


def build_application(ctx: AppContext, token: str) -> Application:
    application = Application.builder().token(token).build()
    application.bot_data["app_context"] = ctx

    application.add_handler(TypeHandler(Update, enforce_allowlist), group=AUTH_MIDDLEWARE_GROUP)

    application.add_handler(CommandHandler("start", start.start_command))
    application.add_handler(CommandHandler("help", start.help_command))

    application.add_handler(CommandHandler("printers", printers.printers_command))
    application.add_handler(CommandHandler("active", printers.active_command))
    application.add_handler(
        CallbackQueryHandler(
            printers.select_printer_callback, pattern=f"^{SELECT_PRINTER_PREFIX}"
        )
    )

    application.add_handler(CommandHandler("status", status.status_command))

    application.add_handler(CommandHandler("pause", control.pause_command))
    application.add_handler(CommandHandler("resume", control.resume_command))
    application.add_handler(CommandHandler("cancel", control.cancel_command))
    application.add_handler(
        CallbackQueryHandler(
            control.confirm_cancel_print_callback, pattern=control.CONFIRM_CANCEL_PRINT_PATTERN
        )
    )
    application.add_handler(
        CallbackQueryHandler(control.cancel_action_callback, pattern=f"^{CANCEL_PREFIX}")
    )

    application.add_handler(CommandHandler("snapshot", camera.snapshot_command))

    application.add_handler(CommandHandler("files", files.files_command))
    application.add_handler(
        CallbackQueryHandler(files.start_print_callback, pattern=f"^{START_PRINT_PREFIX}")
    )

    application.add_handler(CommandHandler("timelapses", timelapses.timelapses_command))
    application.add_handler(
        CallbackQueryHandler(
            timelapses.download_timelapse_callback, pattern=f"^{TIMELAPSE_DOWNLOAD_PREFIX}"
        )
    )
    application.add_handler(
        CommandHandler("clear_timelapses", timelapses.clear_timelapses_command)
    )
    application.add_handler(
        CallbackQueryHandler(
            timelapses.confirm_clear_timelapses_callback,
            pattern=timelapses.CONFIRM_CLEAR_TIMELAPSES_PATTERN,
        )
    )

    async def send_to_main_chat(text: str) -> None:
        chat_id = ctx.state_store.get_main_chat_id()
        env_chat_id = os.environ.get("TELEGRAM_MAIN_CHAT_ID")
        target = int(env_chat_id) if env_chat_id else chat_id
        if target is None:
            return
        await application.bot.send_message(chat_id=target, text=text)

    notifier.subscribe(send_to_main_chat)

    return application
