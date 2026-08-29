"""Loading and persistence of static config (printers.yaml, users.yaml).

Both files are the source of truth: printers.yaml is edited by hand;
users.yaml can also be rewritten at runtime (see core/auth.py) when a
pending user gets confirmed, which is why the writes are atomic.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import yaml

from core.models import Printer, User, UserRole, UserStatus

PRINTERS_YAML_PATH = Path(os.environ.get("PRINTERS_YAML_PATH", "printers.yaml"))
USERS_YAML_PATH = Path(os.environ.get("USERS_YAML_PATH", "users.yaml"))


class ConfigError(Exception):
    pass


def load_printers(path: Path = PRINTERS_YAML_PATH) -> list[Printer]:
    if not path.exists():
        raise ConfigError(f"Could not find {path}. Copy the example and edit it.")

    raw = yaml.safe_load(path.read_text()) or {}
    entries = raw.get("printers") or []
    printers: list[Printer] = []
    seen_names: set[str] = set()

    for entry in entries:
        name = entry.get("name")
        if not name:
            raise ConfigError(f"Printer entry without 'name': {entry}")
        if name in seen_names:
            raise ConfigError(f"Duplicate printer name: {name}")
        seen_names.add(name)

        moonraker_url = entry.get("moonraker_url")
        if not moonraker_url:
            raise ConfigError(f"Printer '{name}' without 'moonraker_url'")

        printers.append(
            Printer(
                name=name,
                display_name=entry.get("display_name", name),
                moonraker_url=moonraker_url.rstrip("/"),
                api_key=entry.get("api_key"),
                camera_snapshot_url=entry.get("camera_snapshot_url"),
            )
        )

    if not printers:
        raise ConfigError(f"{path} does not define any active printer.")

    return printers


def load_users(path: Path = USERS_YAML_PATH) -> list[User]:
    if not path.exists():
        raise ConfigError(f"Could not find {path}. Copy the example and edit it.")

    raw = yaml.safe_load(path.read_text()) or {}
    entries = raw.get("users") or []
    users: list[User] = []

    for entry in entries:
        username = entry.get("username")
        if not username:
            raise ConfigError(f"User entry without 'username': {entry}")

        users.append(
            User(
                username=username,
                user_id=entry.get("user_id"),
                status=UserStatus(entry.get("status", UserStatus.PENDING.value)),
                role=UserRole(entry.get("role", UserRole.ADMIN.value)),
            )
        )

    return users


def save_users(users: list[User], path: Path = USERS_YAML_PATH) -> None:
    """Rewrites users.yaml atomically (write to tmp + rename)."""
    payload = {
        "users": [
            {
                "username": u.username,
                "user_id": u.user_id,
                "status": u.status.value,
                "role": u.role.value,
            }
            for u in users
        ]
    }

    fd, tmp_path = tempfile.mkstemp(
        dir=path.parent or ".", prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w") as f:
            yaml.safe_dump(payload, f, sort_keys=False, allow_unicode=True)
        os.replace(tmp_path, path)
    except Exception:
        os.unlink(tmp_path)
        raise
