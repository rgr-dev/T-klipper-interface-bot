"""Shared application context: instantiated once in main.py and passed to
the interface adapters (Telegram bot, REST API), which in turn pass it to
the services. Avoids scattered globals and makes it easier to test the
services with a test context.
"""
from __future__ import annotations

from core.auth import AllowlistStore
from core.models import Printer
from core.moonraker_client import MoonrakerClient
from core.state_store import StateStore


class AppContext:
    def __init__(
        self,
        printers: list[Printer],
        allowlist: AllowlistStore,
        state_store: StateStore,
    ):
        self.printers_by_name: dict[str, Printer] = {p.name: p for p in printers}
        self.allowlist = allowlist
        self.state_store = state_store
        self._moonraker_clients: dict[str, MoonrakerClient] = {}

    def list_printers(self) -> list[Printer]:
        return list(self.printers_by_name.values())

    def get_printer(self, name: str) -> Printer | None:
        return self.printers_by_name.get(name)

    def moonraker_client(self, printer_name: str) -> MoonrakerClient:
        client = self._moonraker_clients.get(printer_name)
        if client is None:
            printer = self.printers_by_name.get(printer_name)
            if printer is None:
                raise KeyError(f"Unknown printer: {printer_name}")
            client = MoonrakerClient(printer)
            self._moonraker_clients[printer_name] = client
        return client

    def resolve_active_printer(self, chat_id: int) -> Printer | None:
        """The chat's active printer, or the only configured one if there's just one."""
        name = self.state_store.get_active_printer(chat_id)
        if name and name in self.printers_by_name:
            return self.printers_by_name[name]
        if len(self.printers_by_name) == 1:
            return next(iter(self.printers_by_name.values()))
        return None

    async def aclose(self) -> None:
        for client in self._moonraker_clients.values():
            await client.aclose()
        self.state_store.close()
