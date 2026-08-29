"""/snapshot — current photo from the active printer's camera."""
from __future__ import annotations

import io

from telegram import Update
from telegram.ext import ContextTypes

from core.context import AppContext
from core.moonraker_client import MoonrakerError
from core.services import camera_service
from interfaces.telegram_bot.handlers.common import require_active_printer


async def snapshot_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    ctx: AppContext = context.bot_data["app_context"]
    printer = await require_active_printer(update, ctx)
    if printer is None:
        return

    try:
        image_bytes = await camera_service.get_snapshot(ctx, printer.name)
    except MoonrakerError as exc:
        await update.effective_message.reply_text(f"⚠️ {exc}")
        return

    await update.effective_message.reply_photo(
        photo=io.BytesIO(image_bytes), caption=printer.display_name
    )
