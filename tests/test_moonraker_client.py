import httpx
import pytest

from core.models import Printer
from core.moonraker_client import MoonrakerClient, MoonrakerError, MoonrakerUnavailableError

PRINTER = Printer(name="k1c", display_name="Creality K1C", moonraker_url="http://printer.local:7125")


def _client_with_handler(handler) -> MoonrakerClient:
    transport = httpx.MockTransport(handler)
    return MoonrakerClient(PRINTER, transport=transport)


@pytest.mark.asyncio
async def test_get_status_parses_moonraker_response():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/printer/objects/query"
        return httpx.Response(
            200,
            json={
                "result": {
                    "status": {
                        "print_stats": {
                            "state": "printing",
                            "filename": "cube.gcode",
                            "print_duration": 100.0,
                        },
                        "virtual_sdcard": {"progress": 0.5},
                        "extruder": {"temperature": 210.1, "target": 210.0},
                        "heater_bed": {"temperature": 60.2, "target": 60.0},
                    }
                }
            },
        )

    client = _client_with_handler(handler)
    status = await client.get_status()

    assert status.state == "printing"
    assert status.filename == "cube.gcode"
    assert status.progress == 0.5
    assert status.extruder_temp == 210.1
    assert status.bed_temp == 60.2
    assert status.time_remaining_s == pytest.approx(100.0)  # 100/0.5 - 100


@pytest.mark.asyncio
async def test_pause_print_posts_to_correct_endpoint():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(200, json={"result": "ok"})

    client = _client_with_handler(handler)
    await client.pause_print()

    assert calls == ["/printer/print/pause"]


@pytest.mark.asyncio
async def test_http_error_raises_moonraker_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    client = _client_with_handler(handler)

    with pytest.raises(MoonrakerError):
        await client.get_status()


@pytest.mark.asyncio
async def test_http_status_error_is_not_unavailable():
    """A 500 means Moonraker IS reachable, it just rejected the request —
    that's a plain MoonrakerError, not "printer offline"."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    client = _client_with_handler(handler)

    with pytest.raises(MoonrakerError) as exc_info:
        await client.get_status()
    assert not isinstance(exc_info.value, MoonrakerUnavailableError)


@pytest.mark.asyncio
async def test_connection_error_raises_moonraker_unavailable_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused", request=request)

    client = _client_with_handler(handler)

    with pytest.raises(MoonrakerUnavailableError) as exc_info:
        await client.get_status()
    assert "unreachable" in str(exc_info.value)


@pytest.mark.asyncio
async def test_snapshot_requires_camera_url_configured():
    client = _client_with_handler(lambda request: httpx.Response(200))

    with pytest.raises(MoonrakerError):
        await client.get_camera_snapshot()


@pytest.mark.asyncio
async def test_list_files_uses_requested_root():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/server/files/list"
        assert request.url.params["root"] == "timelapse"
        return httpx.Response(200, json={"result": [{"path": "a.mp4", "modified": 1}]})

    client = _client_with_handler(handler)
    files = await client.list_files("timelapse")

    assert files == [{"path": "a.mp4", "modified": 1}]


@pytest.mark.asyncio
async def test_download_file_returns_raw_bytes():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/server/files/timelapse/a.mp4"
        return httpx.Response(200, content=b"fake-video-bytes")

    client = _client_with_handler(handler)
    content = await client.download_file("timelapse", "a.mp4")

    assert content == b"fake-video-bytes"


@pytest.mark.asyncio
async def test_download_file_raises_on_http_error():
    client = _client_with_handler(lambda request: httpx.Response(404))

    with pytest.raises(MoonrakerError):
        await client.download_file("timelapse", "missing.mp4")


@pytest.mark.asyncio
async def test_delete_file_sends_delete_request():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        return httpx.Response(200, json={"result": "ok"})

    client = _client_with_handler(handler)
    await client.delete_file("timelapse", "a.mp4")

    assert calls == [("DELETE", "/server/files/timelapse/a.mp4")]
