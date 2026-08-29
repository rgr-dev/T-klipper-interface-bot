"""Read-only endpoints: configured printers and their status."""
from __future__ import annotations

from quart import Blueprint, current_app

from core.moonraker_client import MoonrakerError, MoonrakerUnavailableError
from core.services import printer_service
from core.services.printer_service import PrinterNotFoundError
from interfaces.rest_api.auth import require_api_token

bp = Blueprint("printers", __name__)


@bp.get("/api/printers")
@require_api_token
async def list_printers():
    ctx = current_app.config["APP_CONTEXT"]
    printers = printer_service.list_printers(ctx)
    return {
        "printers": [
            {"name": p.name, "display_name": p.display_name} for p in printers
        ]
    }


@bp.get("/api/printers/<name>/status")
@require_api_token
async def get_status(name: str):
    ctx = current_app.config["APP_CONTEXT"]
    try:
        status = await printer_service.get_status(ctx, name)
    except PrinterNotFoundError:
        return {"error": f"Printer '{name}' not found"}, 404
    except MoonrakerUnavailableError as exc:
        return {"error": str(exc), "printer_offline": True}, 503
    except MoonrakerError as exc:
        return {"error": str(exc)}, 502

    return {
        "printer_name": status.printer_name,
        "state": status.state,
        "filename": status.filename,
        "progress": status.progress,
        "time_elapsed_s": status.time_elapsed_s,
        "time_remaining_s": status.time_remaining_s,
        "extruder_temp": status.extruder_temp,
        "extruder_target": status.extruder_target,
        "bed_temp": status.bed_temp,
        "bed_target": status.bed_target,
    }
