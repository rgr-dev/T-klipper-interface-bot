import pytest

from core.auth import AllowlistStore
from core.context import AppContext
from core.models import Printer, PrintStatus
from core.services import job_service, printer_service, timelapse_service
from core.services.printer_service import PrinterNotFoundError
from core.state_store import StateStore

PRINTER = Printer(name="k1c", display_name="Creality K1C", moonraker_url="http://printer.local:7125")


class FakeMoonrakerClient:
    def __init__(self):
        self.calls: list[str] = []

    async def get_status(self):
        self.calls.append("get_status")
        return PrintStatus(
            printer_name="k1c",
            state="printing",
            filename="cube.gcode",
            progress=0.5,
            time_elapsed_s=100.0,
            time_remaining_s=100.0,
            extruder_temp=210.0,
            extruder_target=210.0,
            bed_temp=60.0,
            bed_target=60.0,
        )

    async def pause_print(self):
        self.calls.append("pause")

    async def resume_print(self):
        self.calls.append("resume")

    async def cancel_print(self):
        self.calls.append("cancel")

    async def list_gcode_files(self):
        self.calls.append("list_gcode_files")
        return [
            {"path": "oldest.gcode", "modified": 100},
            {"path": "newest.gcode", "modified": 300},
            {"path": "middle.gcode", "modified": 200},
        ]

    async def list_files(self, root):
        self.calls.append(f"list_files:{root}")
        return [
            {"path": "old.mp4", "modified": 100, "size": 1_000_000},
            {"path": "new.mp4", "modified": 300, "size": 1_000_000},
        ]

    async def download_file(self, root, filename):
        self.calls.append(f"download_file:{root}:{filename}")
        return b"fake-bytes"

    async def delete_file(self, root, filename):
        self.calls.append(f"delete_file:{root}:{filename}")


def _make_context(tmp_path, fake_client: FakeMoonrakerClient) -> AppContext:
    users_path = tmp_path / "users.yaml"
    users_path.write_text("users: []\n")

    ctx = AppContext(
        printers=[PRINTER],
        allowlist=AllowlistStore(path=users_path),
        state_store=StateStore(path=tmp_path / "state.json"),
    )
    ctx._moonraker_clients["k1c"] = fake_client
    return ctx


@pytest.mark.asyncio
async def test_get_status_delegates_to_moonraker_client(tmp_path):
    fake_client = FakeMoonrakerClient()
    ctx = _make_context(tmp_path, fake_client)

    status = await printer_service.get_status(ctx, "k1c")

    assert status.state == "printing"
    assert fake_client.calls == ["get_status"]


@pytest.mark.asyncio
async def test_get_status_unknown_printer_raises(tmp_path):
    ctx = _make_context(tmp_path, FakeMoonrakerClient())

    with pytest.raises(PrinterNotFoundError):
        await printer_service.get_status(ctx, "does-not-exist")


@pytest.mark.asyncio
async def test_pause_resume_cancel_delegate_to_client(tmp_path):
    fake_client = FakeMoonrakerClient()
    ctx = _make_context(tmp_path, fake_client)

    await job_service.pause(ctx, "k1c")
    await job_service.resume(ctx, "k1c")
    await job_service.cancel(ctx, "k1c")

    assert fake_client.calls == ["pause", "resume", "cancel"]


@pytest.mark.asyncio
async def test_list_files_sorts_newest_first(tmp_path):
    ctx = _make_context(tmp_path, FakeMoonrakerClient())

    files = await job_service.list_files(ctx, "k1c")

    assert [f["path"] for f in files] == ["newest.gcode", "middle.gcode", "oldest.gcode"]


@pytest.mark.asyncio
async def test_list_timelapses_sorts_newest_first(tmp_path):
    ctx = _make_context(tmp_path, FakeMoonrakerClient())

    files = await timelapse_service.list_timelapses(ctx, "k1c")

    assert [f["path"] for f in files] == ["new.mp4", "old.mp4"]


@pytest.mark.asyncio
async def test_list_timelapses_deduplicates_repeated_paths(tmp_path):
    class DuplicatingFakeClient(FakeMoonrakerClient):
        async def list_files(self, root):
            self.calls.append(f"list_files:{root}")
            return [
                {"path": "new.mp4", "modified": 300, "size": 1_000_000},
                {"path": "old.mp4", "modified": 100, "size": 1_000_000},
                {"path": "new.mp4", "modified": 300, "size": 1_000_000},  # Moonraker listed it twice
            ]

    ctx = _make_context(tmp_path, DuplicatingFakeClient())

    files = await timelapse_service.list_timelapses(ctx, "k1c")

    assert [f["path"] for f in files] == ["new.mp4", "old.mp4"]


@pytest.mark.asyncio
async def test_list_timelapses_filters_out_zero_byte_files(tmp_path):
    class BrokenRenderFakeClient(FakeMoonrakerClient):
        async def list_files(self, root):
            self.calls.append(f"list_files:{root}")
            return [
                {"path": "good.mp4", "modified": 300, "size": 1_500_000},
                {"path": "broken.mp4", "modified": 400, "size": 0},  # failed/interrupted render
            ]

    ctx = _make_context(tmp_path, BrokenRenderFakeClient())

    files = await timelapse_service.list_timelapses(ctx, "k1c")

    assert [f["path"] for f in files] == ["good.mp4"]


@pytest.mark.asyncio
async def test_list_timelapses_filters_out_thumbnail_images(tmp_path):
    class ThumbnailFakeClient(FakeMoonrakerClient):
        async def list_files(self, root):
            self.calls.append(f"list_files:{root}")
            return [
                {"path": "print1.mp4", "modified": 300, "size": 1_500_000},
                {"path": "print1.jpg", "modified": 300, "size": 20_000},  # thumbnail
            ]

    ctx = _make_context(tmp_path, ThumbnailFakeClient())

    files = await timelapse_service.list_timelapses(ctx, "k1c")

    assert [f["path"] for f in files] == ["print1.mp4"]


@pytest.mark.asyncio
async def test_download_timelapse_delegates_to_client(tmp_path):
    fake_client = FakeMoonrakerClient()
    ctx = _make_context(tmp_path, fake_client)

    content = await timelapse_service.download_timelapse(ctx, "k1c", "new.mp4")

    assert content == b"fake-bytes"
    assert "download_file:timelapse:new.mp4" in fake_client.calls


@pytest.mark.asyncio
async def test_clear_timelapses_deletes_every_file_and_returns_count(tmp_path):
    fake_client = FakeMoonrakerClient()
    ctx = _make_context(tmp_path, fake_client)

    deleted_count = await timelapse_service.clear_timelapses(ctx, "k1c")

    assert deleted_count == 2
    assert "delete_file:timelapse:old.mp4" in fake_client.calls
    assert "delete_file:timelapse:new.mp4" in fake_client.calls


@pytest.mark.asyncio
async def test_timelapse_service_unknown_printer_raises(tmp_path):
    ctx = _make_context(tmp_path, FakeMoonrakerClient())

    with pytest.raises(PrinterNotFoundError):
        await timelapse_service.list_timelapses(ctx, "does-not-exist")


def test_resolve_active_printer_defaults_to_only_printer(tmp_path):
    ctx = _make_context(tmp_path, FakeMoonrakerClient())

    printer = ctx.resolve_active_printer(chat_id=1)

    assert printer.name == "k1c"
