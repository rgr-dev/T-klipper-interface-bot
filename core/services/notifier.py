"""Dispatch of push alerts to subscribed interfaces (Telegram bot).

core/ doesn't import python-telegram-bot: interfaces subscribe with an
async callback `(text: str) -> None` that they implement themselves (e.g.
sending the message to the main chat). This way core/moonraker_ws.py can
trigger alerts without knowing anything about Telegram.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable

from core.context import AppContext

Subscriber = Callable[[str], Awaitable[None]]

_subscribers: list[Subscriber] = []


def subscribe(callback: Subscriber) -> None:
    _subscribers.append(callback)


async def dispatch(ctx: AppContext, printer_name: str, event_key: str, text: str) -> None:
    """Sends `text` to all subscribers, only once per (printer_name, event_key)."""
    if ctx.state_store.was_notified(printer_name, event_key):
        return
    ctx.state_store.mark_notified(printer_name, event_key)
    for callback in _subscribers:
        await callback(text)


async def notify_now(text: str) -> None:
    """Sends `text` to all subscribers immediately, bypassing state_store's
    per-(printer, event_key) dedupe. Used for events that flap over time
    (e.g. a WebSocket connection going down/up) rather than a one-shot
    state transition — the caller is expected to track on its own whether
    it needs to send (e.g. an in-memory "was this already reported?" flag)."""
    for callback in _subscribers:
        await callback(text)
