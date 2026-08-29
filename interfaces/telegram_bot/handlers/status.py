"""/status — status, progress and temperatures of the active printer."""
from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from core.context import AppContext
from core.moonraker_client import MoonrakerError
from core.services import printer_service
from interfaces.telegram_bot.handlers.common import format_duration, require_active_printer


def _format_status(display_name: str, status) -> str:
    lines = [f"🖨️ *{display_name}*", f"State: `{status.state}`"]
    if status.filename:
        lines.append(f"File: `{status.filename}`")
    lines.append(f"Progress: {status.progress * 100:.1f}%")
    if status.time_remaining_s is not None:
        lines.append(f"Time remaining: {format_duration(status.time_remaining_s)}")
    if status.extruder_temp is not None:
        lines.append(
            f"Hotend: {status.extruder_temp:.1f}°C / {status.extruder_target or 0:.1f}°C"
        )
    if status.bed_temp is not None:
        lines.append(f"Bed: {status.bed_temp:.1f}°C / {status.bed_target or 0:.1f}°C")
    return "\n".join(lines)


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ctx: AppContext = context.bot_data["app_context"]
    printer = await require_active_printer(update, ctx)
    if printer is None:
        return

    try:
        status = await printer_service.get_status(ctx, printer.name)
    except MoonrakerError as exc:
        await update.effective_message.reply_text(f"⚠️ {exc}")
        return

    await update.effective_message.reply_markdown(_format_status(printer.display_name, status))
