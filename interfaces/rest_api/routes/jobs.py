"""Print control and file management endpoints."""
from __future__ import annotations

from quart import Blueprint, current_app, request

from core.moonraker_client import MoonrakerError, MoonrakerUnavailableError
from core.services import job_service
from core.services.printer_service import PrinterNotFoundError
from interfaces.rest_api.auth import require_api_token

bp = Blueprint("jobs", __name__)


async def _run(coro):
    try:
        return await coro, None
    except PrinterNotFoundError as exc:
        return None, ({"error": f"Printer '{exc}' not found"}, 404)
    except MoonrakerUnavailableError as exc:
        return None, ({"error": str(exc), "printer_offline": True}, 503)
    except MoonrakerError as exc:
        return None, ({"error": str(exc)}, 502)


@bp.post("/api/printers/<name>/pause")
@require_api_token
async def pause(name: str):
    ctx = current_app.config["APP_CONTEXT"]
    _, error = await _run(job_service.pause(ctx, name))
    return error or ({"ok": True}, 200)


@bp.post("/api/printers/<name>/resume")
@require_api_token
async def resume(name: str):
    ctx = current_app.config["APP_CONTEXT"]
    _, error = await _run(job_service.resume(ctx, name))
    return error or ({"ok": True}, 200)


@bp.post("/api/printers/<name>/cancel")
@require_api_token
async def cancel(name: str):
    ctx = current_app.config["APP_CONTEXT"]
    _, error = await _run(job_service.cancel(ctx, name))
    return error or ({"ok": True}, 200)


@bp.get("/api/printers/<name>/files")
@require_api_token
async def list_files(name: str):
    ctx = current_app.config["APP_CONTEXT"]
    files, error = await _run(job_service.list_files(ctx, name))
    if error:
        return error
    return {"files": files}


@bp.post("/api/printers/<name>/print")
@require_api_token
async def start_print(name: str):
    body = await request.get_json(silent=True) or {}
    filename = body.get("filename")
    if not filename:
        return {"error": "Missing 'filename' in the body"}, 400

    ctx = current_app.config["APP_CONTEXT"]
    _, error = await _run(job_service.start_print(ctx, name, filename))
    return error or ({"ok": True}, 200)
