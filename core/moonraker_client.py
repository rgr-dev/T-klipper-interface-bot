"""Async HTTP wrapper over Moonraker's REST API.

Reference: https://moonraker.readthedocs.io/en/latest/web_api/

Each instance talks to ONE printer (one moonraker_url). The services layer
(core/services/) is the one that decides which Printer to instantiate the
client with on each call.
"""
from __future__ import annotations

import httpx

from core.models import Printer, PrintStatus

_STATUS_OBJECTS = ["print_stats", "virtual_sdcard", "extruder", "heater_bed"]


class MoonrakerError(Exception):
    pass


class MoonrakerUnavailableError(MoonrakerError):
    """Moonraker couldn't be reached at all (connection refused/timed out/DNS
    failure) — usually means the printer is powered off or unreachable on
    the network, as opposed to Moonraker responding with an error."""


class MoonrakerClient:
    def __init__(
        self,
        printer: Printer,
        timeout: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.printer = printer
        self._headers = {"X-Api-Key": printer.api_key} if printer.api_key else {}
        self._client = httpx.AsyncClient(
            base_url=printer.moonraker_url,
            headers=self._headers,
            timeout=timeout,
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "MoonrakerClient":
        return self

    async def __aexit__(self, *exc_info) -> None:
        await self.aclose()

    def _wrap_error(self, exc: httpx.HTTPError, message: str) -> MoonrakerError:
        """Translates an httpx error into a MoonrakerError, distinguishing
        "can't reach Moonraker at all" (RequestError: connection
        refused/timed out/DNS failure — printer likely offline) from
        "Moonraker responded but rejected the request" (HTTPStatusError)."""
        if isinstance(exc, httpx.RequestError):
            return MoonrakerUnavailableError(
                f"{self.printer.display_name} is unreachable "
                f"(printer off or not reachable on the network): {exc}"
            )
        return MoonrakerError(f"{message}: {exc}")

    async def _get(self, path: str, params: dict | None = None) -> dict:
        try:
            resp = await self._client.get(path, params=params)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise self._wrap_error(exc, f"Error querying {self.printer.name} ({path})") from exc
        return resp.json()

    async def _post(self, path: str, params: dict | None = None) -> dict:
        try:
            resp = await self._client.post(path, params=params)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise self._wrap_error(
                exc, f"Error sending command to {self.printer.name} ({path})"
            ) from exc
        return resp.json()

    async def get_status(self) -> PrintStatus:
        params = {name: "" for name in _STATUS_OBJECTS}
        data = await self._get("/printer/objects/query", params=params)
        objects = data.get("result", {}).get("status", {})
        print_stats = objects.get("print_stats", {})
        virtual_sdcard = objects.get("virtual_sdcard", {})
        extruder = objects.get("extruder", {})
        heater_bed = objects.get("heater_bed", {})

        progress = virtual_sdcard.get("progress", 0.0) or 0.0
        print_duration = print_stats.get("print_duration") or 0.0
        time_remaining = None
        if progress > 0:
            time_remaining = (print_duration / progress) - print_duration

        return PrintStatus(
            printer_name=self.printer.name,
            state=print_stats.get("state", "unknown"),
            filename=print_stats.get("filename") or None,
            progress=progress,
            time_elapsed_s=print_duration or None,
            time_remaining_s=time_remaining,
            extruder_temp=extruder.get("temperature"),
            extruder_target=extruder.get("target"),
            bed_temp=heater_bed.get("temperature"),
            bed_target=heater_bed.get("target"),
        )

    async def pause_print(self) -> None:
        await self._post("/printer/print/pause")

    async def resume_print(self) -> None:
        await self._post("/printer/print/resume")

    async def cancel_print(self) -> None:
        await self._post("/printer/print/cancel")

    async def start_print(self, filename: str) -> None:
        await self._post("/printer/print/start", params={"filename": filename})

    async def list_gcode_files(self) -> list[dict]:
        return await self.list_files("gcodes")

    async def list_files(self, root: str) -> list[dict]:
        data = await self._get("/server/files/list", params={"root": root})
        return data.get("result", [])

    async def download_file(self, root: str, filename: str) -> bytes:
        try:
            resp = await self._client.get(f"/server/files/{root}/{filename}")
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise self._wrap_error(
                exc, f"Error downloading '{filename}' from {self.printer.name}"
            ) from exc
        return resp.content

    async def delete_file(self, root: str, filename: str) -> None:
        try:
            resp = await self._client.delete(f"/server/files/{root}/{filename}")
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise self._wrap_error(
                exc, f"Error deleting '{filename}' from {self.printer.name}"
            ) from exc

    async def get_camera_snapshot(self) -> bytes:
        if not self.printer.camera_snapshot_url:
            raise MoonrakerError(
                f"Printer '{self.printer.name}' does not have camera_snapshot_url configured"
            )
        try:
            resp = await self._client.get(
                self.printer.camera_snapshot_url, headers={}, timeout=10.0
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise self._wrap_error(exc, f"Error getting snapshot from {self.printer.name}") from exc
        return resp.content
