"""Moonraker JSON-RPC WebSocket listener: real-time push alerts.

Instead of HTTP polling, a persistent connection is opened per printer to
`/websocket` and `printer.objects.subscribe` is sent. From there, Moonraker
pushes a `notify_status_update` every time one of the subscribed objects
changes — from those messages, state transitions are detected (print
completed, error, paused) and an alert is triggered via
core/services/notifier.py.

Reference: https://moonraker.readthedocs.io/en/latest/web_api/#websocket-notifications
"""
from __future__ import annotations

import asyncio
import json
import logging

import websockets

from core.context import AppContext
from core.models import Printer
from core.services import notifier

log = logging.getLogger(__name__)

_SUBSCRIBE_OBJECTS = {
    "print_stats": None,
    "virtual_sdcard": None,
    "heater_bed": None,
    "extruder": None,
}

# print_stats.state transitions that generate a push alert.
_ALERT_STATES = {"complete", "error", "paused"}

_RECONNECT_DELAY_S = 5
_MAX_RECONNECT_DELAY_S = 60


def _ws_url(moonraker_url: str) -> str:
    return moonraker_url.replace("https://", "wss://").replace("http://", "ws://") + "/websocket"


def _event_message(printer: Printer, state: str, filename: str | None) -> str:
    label = filename or "the print"
    if state == "complete":
        return f"✅ {printer.display_name}: {label} completed."
    if state == "error":
        return f"🛑 {printer.display_name}: error printing {label}."
    if state == "paused":
        return f"⏸️ {printer.display_name}: {label} paused."
    return f"ℹ️ {printer.display_name}: {label} changed to state '{state}'."


async def _handle_notification(
    ctx: AppContext, printer: Printer, params: list, last_state: dict
) -> None:
    status = params[0] if params else {}
    print_stats = status.get("print_stats") or {}
    state = print_stats.get("state")
    if not state or state == last_state.get("value"):
        return

    previous = last_state.get("value")
    last_state["value"] = state

    if state in _ALERT_STATES and previous is not None:
        filename = print_stats.get("filename")
        event_key = f"{filename}:{state}"
        await notifier.dispatch(
            ctx, printer.name, event_key, _event_message(printer, state, filename)
        )


async def _listen_once(
    ctx: AppContext, printer: Printer, last_state: dict, on_connected=None
) -> None:
    url = _ws_url(printer.moonraker_url)
    additional_headers = {"X-Api-Key": printer.api_key} if printer.api_key else None

    async with websockets.connect(url, additional_headers=additional_headers) as ws:
        await ws.send(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "method": "printer.objects.subscribe",
                    "params": {"objects": _SUBSCRIBE_OBJECTS},
                    "id": 1,
                }
            )
        )

        if on_connected is not None:
            await on_connected()

        async for raw_message in ws:
            try:
                message = json.loads(raw_message)
            except json.JSONDecodeError:
                continue

            if message.get("method") == "notify_status_update":
                await _handle_notification(ctx, printer, message.get("params", []), last_state)


async def listen_printer(ctx: AppContext, printer: Printer) -> None:
    """Runs forever: reconnects with backoff if the connection drops.

    Also pushes a one-off chat alert when the connection is lost (printer
    likely off / unreachable) and another when it comes back, so downtime
    doesn't go unnoticed just because no print was running at the time.
    """
    last_state: dict = {"value": None}
    delay = _RECONNECT_DELAY_S
    was_down = False

    async def _mark_connected() -> None:
        nonlocal was_down
        if was_down:
            was_down = False
            await notifier.notify_now(
                f"🔌✅ {printer.display_name}: connection to Moonraker restored."
            )

    while True:
        try:
            await _listen_once(ctx, printer, last_state, on_connected=_mark_connected)
            delay = _RECONNECT_DELAY_S
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if not was_down:
                was_down = True
                await notifier.notify_now(
                    f"🔌⚠️ {printer.display_name}: lost connection to Moonraker "
                    "(printer off or unreachable on the network). Will keep "
                    "retrying in the background."
                )
            log.warning(
                "WebSocket for %s down (%s); retrying in %ss", printer.name, exc, delay
            )
            await asyncio.sleep(delay)
            delay = min(delay * 2, _MAX_RECONNECT_DELAY_S)


def build_listener_tasks(ctx: AppContext) -> list[asyncio.Task]:
    return [asyncio.create_task(listen_printer(ctx, printer)) for printer in ctx.list_printers()]
