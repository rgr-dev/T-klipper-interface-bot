"""Entrypoint: python main.py --mode bot|rest|both (default: both).

Runs the Telegram bot, the REST API, and each printer's WebSocket
listeners (push alerts) in a single asyncio process.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os

from dotenv import load_dotenv

from core.auth import AllowlistStore
from core.config import load_printers
from core.context import AppContext
from core.moonraker_ws import build_listener_tasks
from core.state_store import StateStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="klipper_bot")
    parser.add_argument("--mode", choices=["bot", "rest", "both"], default="both")
    return parser.parse_args()


def build_context() -> AppContext:
    printers = load_printers()
    allowlist = AllowlistStore()
    state_store = StateStore()
    return AppContext(printers=printers, allowlist=allowlist, state_store=state_store)


async def run(mode: str) -> None:
    ctx = build_context()
    tasks: list[asyncio.Task] = build_listener_tasks(ctx)

    try:
        if mode in ("bot", "both"):
            from interfaces.telegram_bot.app import build_application

            token = os.environ["TELEGRAM_BOT_TOKEN"]
            application = build_application(ctx, token)

            await application.initialize()
            await application.start()
            await application.updater.start_polling()
            log.info("Telegram bot listening (polling).")

        if mode in ("rest", "both"):
            from interfaces.rest_api.app import build_app

            app = build_app(ctx)
            port = int(os.environ.get("REST_API_PORT", "8080"))
            tasks.append(asyncio.create_task(app.run_task(host="0.0.0.0", port=port)))
            log.info("REST API listening on :%s", port)

        # The bot (if running) is already listening in the background via
        # start_polling(); here we just wait indefinitely while the
        # WebSocket listeners (and the REST server, if applicable) run
        # until Ctrl+C / signal.
        await asyncio.gather(*tasks, asyncio.Event().wait())
    finally:
        if mode in ("bot", "both"):
            await application.updater.stop()
            await application.stop()
            await application.shutdown()
        for task in tasks:
            task.cancel()
        await ctx.aclose()


def main() -> None:
    load_dotenv()
    args = parse_args()
    try:
        asyncio.run(run(args.mode))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
