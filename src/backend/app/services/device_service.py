from __future__ import annotations

import platform
from pathlib import Path
from typing import List

from sqlalchemy.orm import Session

from app.models.camera import Camera


def is_linux() -> bool:
    return platform.system().lower() == "linux"


def normalize_device_path(device_path: str) -> str:
    """
    Linux: keep real /dev/videoX paths.
    macOS/Windows: treat OBS/default device as a single logical target.
    """
    dp = (device_path or "").strip()
    if is_linux():
        return dp
    if dp == "" or dp.lower() in {"auto", "default", "obs", "obs-virtual-camera"}:
        return "obs"
    return dp


def device_exists(device_path: str) -> bool:
    dp = normalize_device_path(device_path)
    if not is_linux():
        # On macOS/Windows, pyvirtualcam uses platform backends (e.g., OBS Virtual Camera).
        # There is no /dev/videoX to validate.
        return True
    p = Path(dp)
    return p.exists() and p.is_char_device()


def list_video_devices() -> List[str]:
    dev = Path("/dev")
    if not dev.exists():
        return []
    return sorted(str(p) for p in dev.glob("video*") if p.exists())


def device_used_by_running_camera(db: Session, device_path: str) -> bool:
    dp = normalize_device_path(device_path)
    q = (
        db.query(Camera)
        .filter(Camera.device_path == dp)
        .filter(Camera.status == "running")
    )
    return db.query(q.exists()).scalar() is True

