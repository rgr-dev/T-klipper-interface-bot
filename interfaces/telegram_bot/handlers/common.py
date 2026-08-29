"""Utilities shared between the bot's handlers."""
from __future__ import annotations

from telegram import Update

from core.context import AppContext
from core.models import Printer

NO_ACTIVE_PRINTER_MSG = (
    "There is no active printer in this chat and several are configured. "
    "Use /printers to choose one."
)


async def require_active_printer(update: Update, ctx: AppContext) -> Printer | None:
    """Returns the chat's active printer, or None (and replies with the error)."""
    printer = ctx.resolve_active_printer(update.effective_chat.id)
    if printer is None:
        await update.effective_message.reply_text(NO_ACTIVE_PRINTER_MSG)
    return printer


def parse_count(args: list[str], default: int, max_count: int) -> int:
    """Parses a command's first argument as a count, with a cap.

    Used by /files and /timelapses for the optional "how many to show" parameter.
    """
    if not args:
        return default
    try:
        count = int(args[0])
    except ValueError:
        return default
    return max(1, min(count, max_count))


def format_duration(seconds: float | None) -> str:
    if seconds is None or seconds < 0:
        return "?"
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m}m"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"
