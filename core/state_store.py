"""Non-critical dynamic state, persisted in TinyDB (data/state.json).

Doesn't store anything that also lives in printers.yaml/users.yaml — only:
- which printer is "active" in each Telegram chat.
- which notification events were already sent, to avoid repeating alerts.
- which is the main chat that receives alerts (if not fixed via env).

Performance note: TinyDB's plain JSONStorage re-reads and re-serializes the
*entire* file on every single operation (including reads) and calls
`os.fsync()` on every write. Since `get_main_chat_id()` runs on every
incoming Telegram update (see auth_middleware.py), that means a full
synchronous disk read on every single bot interaction — noticeable CPU/IO
on an SD card. We wrap the storage with `CachingMiddleware` (reads the file
once, serves subsequent reads from memory, batches writes) and drop the
`fsync` — this file is explicitly non-critical state (see module docstring
and CLAUDE.md), so losing the last few milliseconds of it in a hard crash
is an acceptable trade for not blocking the event loop on disk flushes.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from tinydb import Query, TinyDB
from tinydb.middlewares import CachingMiddleware
from tinydb.storages import JSONStorage

STATE_DB_PATH = Path(os.environ.get("STATE_DB_PATH", "data/state.json"))


class _NoFsyncJSONStorage(JSONStorage):
    """Same as JSONStorage, minus the `os.fsync()` call on every write."""

    def write(self, data: dict) -> None:
        self._handle.seek(0)
        serialized = json.dumps(data, **self.kwargs)
        self._handle.write(serialized)
        self._handle.flush()
        self._handle.truncate()


_Storage = CachingMiddleware(_NoFsyncJSONStorage)


class StateStore:
    def __init__(self, path: Path = STATE_DB_PATH):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = TinyDB(path, storage=_Storage)
        self._active_printers = self._db.table("active_printers")
        self._sent_notifications = self._db.table("sent_notifications")

    def close(self) -> None:
        self._db.close()

    # -- active printer per chat -----------------------------------
    def set_active_printer(self, chat_id: int, printer_name: str) -> None:
        Chat = Query()
        self._active_printers.upsert(
            {"chat_id": chat_id, "printer_name": printer_name},
            Chat.chat_id == chat_id,
        )

    def get_active_printer(self, chat_id: int) -> str | None:
        Chat = Query()
        row = self._active_printers.get(Chat.chat_id == chat_id)
        return row["printer_name"] if row else None

    # -- main chat (receives alerts from all printers) ------
    def get_main_chat_id(self) -> int | None:
        row = self._db.table("main_chat").get(doc_id=1)
        return row["chat_id"] if row else None

    def set_main_chat_id(self, chat_id: int) -> None:
        table = self._db.table("main_chat")
        if table.get(doc_id=1) is None:
            table.insert({"chat_id": chat_id})
        else:
            table.update({"chat_id": chat_id}, doc_ids=[1])

    # -- notification dedupe -------------------------------------
    def was_notified(self, printer_name: str, event_key: str) -> bool:
        Event = Query()
        return self._sent_notifications.contains(
            (Event.printer_name == printer_name) & (Event.event_key == event_key)
        )

    def mark_notified(self, printer_name: str, event_key: str) -> None:
        """Remembers `event_key` as already-notified for `printer_name`.

        Only the printer's most recent event is kept — a state machine only
        ever needs to compare against the last transition it already
        reported, so older entries are dropped instead of accumulating
        forever (an unbounded table would make every read/write on this
        file — including the one on every Telegram update — progressively
        slower over the bot's lifetime).
        """
        Event = Query()
        self._sent_notifications.remove(Event.printer_name == printer_name)
        self._sent_notifications.insert({"printer_name": printer_name, "event_key": event_key})
