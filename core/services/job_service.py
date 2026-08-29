"""Print control use cases: pause/resume/cancel, list gcode files, and
start a new print.
"""
from __future__ import annotations

from core.context import AppContext
from core.services.printer_service import PrinterNotFoundError


def _client(ctx: AppContext, printer_name: str):
    if ctx.get_printer(printer_name) is None:
        raise PrinterNotFoundError(printer_name)
    return ctx.moonraker_client(printer_name)


async def pause(ctx: AppContext, printer_name: str) -> None:
    await _client(ctx, printer_name).pause_print()


async def resume(ctx: AppContext, printer_name: str) -> None:
    await _client(ctx, printer_name).resume_print()


async def cancel(ctx: AppContext, printer_name: str) -> None:
    await _client(ctx, printer_name).cancel_print()


async def list_files(ctx: AppContext, printer_name: str) -> list[dict]:
    """Available gcode files, most recent first (by upload date)."""
    files = await _client(ctx, printer_name).list_gcode_files()
    return sorted(files, key=lambda f: f.get("modified", 0), reverse=True)


async def start_print(ctx: AppContext, printer_name: str, filename: str) -> None:
    await _client(ctx, printer_name).start_print(filename)
