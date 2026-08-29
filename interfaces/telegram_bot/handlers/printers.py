"""/printers — lists printers and allows choosing the chat's active one.
/active — shows which printer is currently active in this chat.
"""
from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from core.context import AppContext
from core.services import printer_service
from interfaces.telegram_bot.keyboards import SELECT_PRINTER_PREFIX, printers_keyboard


async def printers_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ctx: AppContext = context.bot_data["app_context"]
    printers = printer_service.list_printers(ctx)
    await update.effective_message.reply_text(
        "Choose the active printer for this chat:",
        reply_markup=printers_keyboard(printers),
    )


async def active_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ctx: AppContext = context.bot_data["app_context"]
    printer = ctx.resolve_active_printer(update.effective_chat.id)

    if printer is None:
        await update.effective_message.reply_text(
            "There is no active printer in this chat. Use /printers to choose one."
        )
        return

    await update.effective_message.reply_text(f"🖨️ Active printer: {printer.display_name}")


async def select_printer_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ctx: AppContext = context.bot_data["app_context"]
    query = update.callback_query
    printer_name = query.data.removeprefix(SELECT_PRINTER_PREFIX)

    printer = ctx.get_printer(printer_name)
    if printer is None:
        await query.answer("That printer no longer exists in the config.", show_alert=True)
        return

    ctx.state_store.set_active_printer(query.message.chat_id, printer_name)
    await query.answer()
    await query.edit_message_text(f"🖨️ Active printer: {printer.display_name}")
