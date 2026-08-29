"""/start and /help — welcome message and list of available commands.

/start is the command Telegram triggers when opening the chat with the bot
for the first time (or via a t.me/<bot>?start=... link); it has no logic
of its own beyond convention, so it reuses the same text as /help.
"""
from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

HELP_TEXT = (
    "🖨️ <b>klipper_bot</b>\n"
    "Available commands:\n\n"
    "/printers - Choose the active printer\n"
    "/active - See which printer is active\n"
    "/status - Status, progress and temperatures\n"
    "/pause - Pause the active print\n"
    "/resume - Resume the active print\n"
    "/cancel - Cancel the active print (asks for confirmation)\n"
    "/snapshot - Current photo from the camera\n"
    "/files - List gcode files and start a print\n"
    "/timelapses - List and download timelapses\n"
    "/clear_timelapses - Delete all timelapses (asks for confirmation)\n"
    "/help - Show this message\n\n"
    "Alerts for print completed, error, or paused arrive automatically, no "
    "need to request them."
)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_html(f"Hello! 👋\n\n{HELP_TEXT}")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_html(HELP_TEXT)
