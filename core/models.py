"""Domain dataclasses, agnostic of YAML/TinyDB/Telegram."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class UserStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"


class UserRole(str, Enum):
    ADMIN = "admin"


@dataclass
class Printer:
    name: str
    display_name: str
    moonraker_url: str
    api_key: str | None = None
    camera_snapshot_url: str | None = None


@dataclass
class User:
    username: str
    status: UserStatus
    role: UserRole
    user_id: int | None = None


@dataclass
class PrintStatus:
    printer_name: str
    state: str  # "printing" | "paused" | "complete" | "error" | "standby" | ...
    filename: str | None
    progress: float  # 0.0 - 1.0
    time_elapsed_s: float | None
    time_remaining_s: float | None
    extruder_temp: float | None
    extruder_target: float | None
    bed_temp: float | None
    bed_target: float | None
