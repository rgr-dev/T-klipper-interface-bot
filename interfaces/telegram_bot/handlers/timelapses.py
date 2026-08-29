"""/timelapses — lists and downloads timelapses (same pattern as /files).
/clear_timelapses — deletes all timelapses of the active printer,
with prior confirmation since it's a destructive, irreversible action.
"""
from __future__ import annotations

import io

from telegram import Update
from telegram.ext import ContextTypes

from core.context import AppContext
from core.moonraker_client import MoonrakerError
from core.services import timelapse_service
from interfaces.telegram_bot.handlers.common import parse_count, require_active_printer
from interfaces.telegram_bot.keyboards import (
    CONFIRM_PREFIX,
    TIMELAPSE_DOWNLOAD_PREFIX,
    confirm_keyboard,
    timelapses_keyboard,
)

DEFAULT_TIMELAPSES_SHOWN = 5
MAX_TIMELAPSES_SHOWN = 20  # hard cap, even if a larger number is requested via parameter
CLEAR_ACTION = "clear_timelapses"


async def timelapses_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ctx: AppContext = context.bot_data["app_context"]
    printer = await require_active_printer(update, ctx)
    if printer is None:
        return

    count = parse_count(context.args, DEFAULT_TIMELAPSES_SHOWN, MAX_TIMELAPSES_SHOWN)

    try:
        files = await timelapse_service.list_timelapses(ctx, printer.name)  # most recent first
    except MoonrakerError as exc:
        await update.effective_message.reply_text(f"⚠️ {exc}")
        return

    if not files:
        await update.effective_message.reply_text("No timelapses available.")
        return

    # Same as /files: shown ascending (the newest one ends up at the bottom).
    latest_first = files[:count]
    filenames = [f["path"] for f in reversed(latest_first)]
    context.chat_data["active_printer_for_timelapses"] = printer.name
    context.chat_data["timelapses_for_selection"] = filenames

    text = f"Last {len(filenames)} timelapses on {printer.display_name}"
    if len(files) > count:
        text += f" (of {len(files)} total — use /timelapses <n> to see more)"
    await update.effective_message.reply_text(
        f"{text}:", reply_markup=timelapses_keyboard(filenames)
    )


async def download_timelapse_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ctx: AppContext = context.bot_data["app_context"]
    query = update.callback_query
    index = int(query.data.removeprefix(TIMELAPSE_DOWNLOAD_PREFIX))

    filenames = context.chat_data.get("timelapses_for_selection") or []
    printer_name = context.chat_data.get("active_printer_for_timelapses")
    if not printer_name:
        active = ctx.resolve_active_printer(query.message.chat_id)
        printer_name = active.name if active else None

    if (
        not printer_name
        or ctx.get_printer(printer_name) is None
        or index >= len(filenames)
    ):
        await query.answer(
            "Could not determine the file. Use /timelapses again.", show_alert=True
        )
        return

    filename = filenames[index]

    await query.answer("Downloading…")
    try:
        video_bytes = await timelapse_service.download_timelapse(ctx, printer_name, filename)
    except MoonrakerError as exc:
        await query.message.reply_text(f"⚠️ {exc}")
        return

    await query.message.reply_video(
        video=io.BytesIO(video_bytes), filename=filename, caption=filename
    )


async def clear_timelapses_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ctx: AppContext = context.bot_data["app_context"]
    printer = await require_active_printer(update, ctx)
    if printer is None:
        return

    await update.effective_message.reply_text(
        f"Are you sure you want to delete ALL timelapses of {printer.display_name}? "
        "This action cannot be undone.",
        reply_markup=confirm_keyboard(CLEAR_ACTION, printer.name),
    )


async def confirm_clear_timelapses_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    ctx: AppContext = context.bot_data["app_context"]
    query = update.callback_query
    _, _, printer_name = query.data.split(":", 2)

    printer = ctx.get_printer(printer_name)
    if printer is None:
        await query.answer("That printer no longer exists in the config.", show_alert=True)
        return

    try:
        deleted_count = await timelapse_service.clear_timelapses(ctx, printer_name)
    except MoonrakerError as exc:
        await query.answer()
        await query.edit_message_text(f"⚠️ {exc}")
        return

    await query.answer()
    await query.edit_message_text(
        f"🗑️ Deleted {deleted_count} timelapses from {printer.display_name}."
    )


CONFIRM_CLEAR_TIMELAPSES_PATTERN = f"^{CONFIRM_PREFIX}{CLEAR_ACTION}:"
