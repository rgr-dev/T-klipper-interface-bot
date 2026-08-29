from pathlib import Path

import yaml

from core.auth import AllowlistStore
from core.models import UserRole


def _write_users_yaml(path: Path, users: list[dict]) -> None:
    path.write_text(yaml.safe_dump({"users": users}, sort_keys=False))


def test_pending_user_is_not_allowed(tmp_path: Path):
    users_path = tmp_path / "users.yaml"
    _write_users_yaml(users_path, [{"username": "alice", "status": "pending", "role": "admin"}])

    store = AllowlistStore(path=users_path)

    assert store.is_allowed(12345) is False


def test_resolve_pending_confirms_user_and_persists(tmp_path: Path):
    users_path = tmp_path / "users.yaml"
    _write_users_yaml(users_path, [{"username": "alice", "status": "pending", "role": "admin"}])

    store = AllowlistStore(path=users_path)
    changed = store.resolve_pending("alice", user_id=12345)

    assert changed is True
    assert store.is_allowed(12345) is True

    # The file was rewritten on disk.
    reloaded = AllowlistStore(path=users_path)
    assert reloaded.is_allowed(12345) is True


def test_resolve_pending_ignores_unknown_username(tmp_path: Path):
    users_path = tmp_path / "users.yaml"
    _write_users_yaml(users_path, [{"username": "alice", "status": "pending", "role": "admin"}])

    store = AllowlistStore(path=users_path)
    changed = store.resolve_pending("bob", user_id=999)

    assert changed is False
    assert store.is_allowed(999) is False


def test_add_pending_is_idempotent(tmp_path: Path):
    users_path = tmp_path / "users.yaml"
    _write_users_yaml(users_path, [])

    store = AllowlistStore(path=users_path)
    store.add_pending("@carol", role=UserRole.ADMIN)
    store.add_pending("carol")  # already exists (with or without @), should not duplicate

    raw = yaml.safe_load(users_path.read_text())
    assert len(raw["users"]) == 1
    assert raw["users"][0]["username"] == "carol"
    assert raw["users"][0]["status"] == "pending"
