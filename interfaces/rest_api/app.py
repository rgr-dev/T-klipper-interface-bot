"""App factory for the REST API (Quart), exposes the same services as the bot."""
from __future__ import annotations

from quart import Quart

from core.context import AppContext
from interfaces.rest_api.routes import camera, jobs, printers


def build_app(ctx: AppContext) -> Quart:
    app = Quart(__name__)
    app.config["APP_CONTEXT"] = ctx

    app.register_blueprint(printers.bp)
    app.register_blueprint(jobs.bp)
    app.register_blueprint(camera.bp)

    return app
