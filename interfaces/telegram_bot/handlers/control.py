"""/pause /resume /cancel — control of the active print.

/cancel is destructive (aborts the print in progress) so it asks for
confirmation with an inline keyboard before executing.
"""
from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from core.context import AppContext
from core.moonraker_client import MoonrakerError
from core.services import job_service
from interfaces.telegram_bot.handlers.common import require_active_printer
from interfaces.telegram_bot.keyboards import CANCEL_PREFIX, CONFIRM_PREFIX, confirm_keyboard

CANCEL_ACTION = "cancel_print"


async def pause_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ctx: AppContext = context.bot_data["app_context"]
    printer = await require_active_printer(update, ctx)
    if printer is None:
        return
    try:
        await job_service.pause(ctx, printer.name)
    except MoonrakerError as exc:
        await update.effective_message.reply_text(f"⚠️ {exc}")
        return
    await update.effective_message.reply_text(f"⏸️ {printer.display_name} paused.")


async def resume_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ctx: AppContext = context.bot_data["app_context"]
    printer = await require_active_printer(update, ctx)
    if printer is None:
        return
    try:
        await job_service.resume(ctx, printer.name)
    except MoonrakerError as exc:
        await update.effective_message.reply_text(f"⚠️ {exc}")
        return
    await update.effective_message.reply_text(f"▶️ {printer.display_name} resumed.")


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ctx: AppContext = context.bot_data["app_context"]
    printer = await require_active_printer(update, ctx)
    if printer is None:
        return
    await update.effective_message.reply_text(
        f"Are you sure you want to cancel the print on {printer.display_name}?",
        reply_markup=confirm_keyboard(CANCEL_ACTION, printer.name),
    )


async def confirm_cancel_print_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ctx: AppContext = context.bot_data["app_context"]
    query = update.callback_query
    _, _, printer_name = query.data.split(":", 2)

    printer = ctx.get_printer(printer_name)
    if printer is None:
        await query.answer("That printer no longer exists in the config.", show_alert=True)
        return

    try:
        await job_service.cancel(ctx, printer_name)
    except MoonrakerError as exc:
        await query.answer()
        await query.edit_message_text(f"⚠️ {exc}")
        return

    await query.answer()
    await query.edit_message_text(f"🛑 Print cancelled on {printer.display_name}.")


async def cancel_action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Operation cancelled, nothing was done.")


CONFIRM_CANCEL_PRINT_PATTERN = f"^{CONFIRM_PREFIX}{CANCEL_ACTION}:"
CANCEL_ACTION_CALLBACK_PATTERN = f"^{CANCEL_PREFIX}"
