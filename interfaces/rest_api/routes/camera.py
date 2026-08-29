"""Camera snapshot endpoint."""
from __future__ import annotations

from quart import Blueprint, Response, current_app

from core.moonraker_client import MoonrakerError, MoonrakerUnavailableError
from core.services import camera_service
from core.services.printer_service import PrinterNotFoundError
from interfaces.rest_api.auth import require_api_token

bp = Blueprint("camera", __name__)


@bp.get("/api/printers/<name>/snapshot")
@require_api_token
async def snapshot(name: str):
    ctx = current_app.config["APP_CONTEXT"]
    try:
        image_bytes = await camera_service.get_snapshot(ctx, name)
    except PrinterNotFoundError:
        return {"error": f"Printer '{name}' not found"}, 404
    except MoonrakerUnavailableError as exc:
        return {"error": str(exc), "printer_offline": True}, 503
    except MoonrakerError as exc:
        return {"error": str(exc)}, 502

    return Response(image_bytes, mimetype="image/jpeg")
