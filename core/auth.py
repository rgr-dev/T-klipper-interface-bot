"""User allowlist, backed by users.yaml (see core/config.py).

Telegram doesn't allow resolving an @username to a user_id unless that user
has messaged the bot before. That's why a new user is added as "pending"
(username only) and only becomes "confirmed" (with a user_id) once that
username actually messages the bot — see resolve_pending().
"""
from __future__ import annotations

import threading

from core import config
from core.models import User, UserRole, UserStatus


class AllowlistStore:
    """Keeps the allowlist in memory, synchronized with users.yaml.

    A single lock protects concurrent reads/writes from different Telegram
    updates (or REST requests) arriving at the same time.
    """

    def __init__(self, path=None):
        self._path = path or config.USERS_YAML_PATH
        self._lock = threading.Lock()
        self._users: list[User] = config.load_users(self._path)

    def reload(self) -> None:
        with self._lock:
            self._users = config.load_users(self._path)

    def is_allowed(self, user_id: int) -> bool:
        with self._lock:
            return any(
                u.user_id == user_id and u.status == UserStatus.CONFIRMED
                for u in self._users
            )

    def get_confirmed_user_ids(self) -> list[int]:
        with self._lock:
            return [
                u.user_id
                for u in self._users
                if u.status == UserStatus.CONFIRMED and u.user_id is not None
            ]

    def add_pending(self, username: str, role: UserRole = UserRole.ADMIN) -> None:
        """Registers a username awaiting it to message the bot."""
        username = username.lstrip("@")
        with self._lock:
            if any(u.username == username for u in self._users):
                return
            self._users.append(
                User(username=username, status=UserStatus.PENDING, role=role)
            )
            config.save_users(self._users, self._path)

    def resolve_pending(self, username: str | None, user_id: int) -> bool:
        """If `username` matches a pending one, confirms it with its user_id.

        Called on every Telegram update, before dispatching to the handler.
        Returns True if a new user was confirmed (so they can be notified).
        """
        if not username:
            return False

        with self._lock:
            changed = False
            for u in self._users:
                if u.status == UserStatus.PENDING and u.username.lower() == username.lower():
                    u.user_id = user_id
                    u.status = UserStatus.CONFIRMED
                    changed = True
            if changed:
                config.save_users(self._users, self._path)
            return changed
