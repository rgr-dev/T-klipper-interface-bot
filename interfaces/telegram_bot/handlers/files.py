"""/files — lists available gcode files and starts a print."""
from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from core.context import AppContext
from core.moonraker_client import MoonrakerError
from core.services import job_service
from interfaces.telegram_bot.handlers.common import parse_count, require_active_printer
from interfaces.telegram_bot.keyboards import START_PRINT_PREFIX, files_keyboard

DEFAULT_FILES_SHOWN = 5
MAX_FILES_SHOWN = 20  # hard cap, even if a larger number is requested via parameter


async def files_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ctx: AppContext = context.bot_data["app_context"]
    printer = await require_active_printer(update, ctx)
    if printer is None:
        return

    count = parse_count(context.args, DEFAULT_FILES_SHOWN, MAX_FILES_SHOWN)

    try:
        files = await job_service.list_files(ctx, printer.name)  # most recent first
    except MoonrakerError as exc:
        await update.effective_message.reply_text(f"⚠️ {exc}")
        return

    if not files:
        await update.effective_message.reply_text("No gcode files available.")
        return

    # Shown in ascending order (the newest one ends up at the bottom, closer
    # to the buttons) but selecting the `count` most recent ones first.
    latest_first = files[:count]
    filenames = [f["path"] for f in reversed(latest_first)]
    context.chat_data["active_printer_for_files"] = printer.name
    context.chat_data["files_for_selection"] = filenames

    text = f"Last {len(filenames)} files on {printer.display_name}"
    if len(files) > count:
        text += f" (of {len(files)} total — use /files <n> to see more)"
    await update.effective_message.reply_text(
        f"{text}:", reply_markup=files_keyboard(filenames)
    )


async def start_print_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ctx: AppContext = context.bot_data["app_context"]
    query = update.callback_query
    index = int(query.data.removeprefix(START_PRINT_PREFIX))

    filenames = context.chat_data.get("files_for_selection") or []
    printer_name = context.chat_data.get("active_printer_for_files")
    if not printer_name:
        active = ctx.resolve_active_printer(query.message.chat_id)
        printer_name = active.name if active else None

    if (
        not printer_name
        or ctx.get_printer(printer_name) is None
        or index >= len(filenames)
    ):
        await query.answer("Could not determine the file. Use /files again.", show_alert=True)
        return

    filename = filenames[index]

    try:
        await job_service.start_print(ctx, printer_name, filename)
    except MoonrakerError as exc:
        await query.answer()
        await query.edit_message_text(f"⚠️ {exc}")
        return

    await query.answer()
    await query.edit_message_text(f"▶️ Starting print of `{filename}`", parse_mode="Markdown")
