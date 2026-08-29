"""Inline keyboards reusable by the bot's handlers."""
from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from core.models import Printer

SELECT_PRINTER_PREFIX = "select_printer:"
CONFIRM_PREFIX = "confirm:"
CANCEL_PREFIX = "cancel_action:"
START_PRINT_PREFIX = "start_print:"
TIMELAPSE_DOWNLOAD_PREFIX = "download_timelapse:"


def printers_keyboard(printers: list[Printer]) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(p.display_name, callback_data=f"{SELECT_PRINTER_PREFIX}{p.name}")]
        for p in printers
    ]
    return InlineKeyboardMarkup(buttons)


def confirm_keyboard(action: str, payload: str) -> InlineKeyboardMarkup:
    """Generic yes/no keyboard for destructive actions (cancel print, etc.)."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ Yes", callback_data=f"{CONFIRM_PREFIX}{action}:{payload}"
                ),
                InlineKeyboardButton("❌ No", callback_data=CANCEL_PREFIX),
            ]
        ]
    )


_MAX_BUTTON_LABEL_LEN = 64  # Telegram's limit for a button's text


def _label(name: str) -> str:
    if len(name) <= _MAX_BUTTON_LABEL_LEN:
        return name
    return name[: _MAX_BUTTON_LABEL_LEN - 1] + "…"


def _indexed_keyboard(filenames: list[str], prefix: str) -> InlineKeyboardMarkup:
    """callback_data uses the index (not the name) because Telegram limits
    callback_data to 64 bytes, and filenames (especially timelapses, with
    timestamps or subfolders) often exceed it. The actual name is resolved
    on the handler side against the list stored in chat_data.
    """
    buttons = [
        [InlineKeyboardButton(_label(name), callback_data=f"{prefix}{i}")]
        for i, name in enumerate(filenames)
    ]
    return InlineKeyboardMarkup(buttons)


def files_keyboard(filenames: list[str]) -> InlineKeyboardMarkup:
    return _indexed_keyboard(filenames, START_PRINT_PREFIX)


def timelapses_keyboard(filenames: list[str]) -> InlineKeyboardMarkup:
    return _indexed_keyboard(filenames, TIMELAPSE_DOWNLOAD_PREFIX)
