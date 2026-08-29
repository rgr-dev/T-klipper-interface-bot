"""Use case: get a current snapshot of a printer's camera."""
from __future__ import annotations

from core.context import AppContext
from core.services.printer_service import PrinterNotFoundError


async def get_snapshot(ctx: AppContext, printer_name: str) -> bytes:
    if ctx.get_printer(printer_name) is None:
        raise PrinterNotFoundError(printer_name)
    client = ctx.moonraker_client(printer_name)
    return await client.get_camera_snapshot()
