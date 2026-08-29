"""Casos de uso de consulta: listar impresoras y ver su estado."""
from __future__ import annotations

from core.context import AppContext
from core.models import Printer, PrintStatus


class PrinterNotFoundError(Exception):
    pass


def list_printers(ctx: AppContext) -> list[Printer]:
    return ctx.list_printers()


async def get_status(ctx: AppContext, printer_name: str) -> PrintStatus:
    printer = ctx.get_printer(printer_name)
    if printer is None:
        raise PrinterNotFoundError(printer_name)
    client = ctx.moonraker_client(printer_name)
    return await client.get_status()
