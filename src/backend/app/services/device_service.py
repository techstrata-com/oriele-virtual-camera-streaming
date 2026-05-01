from __future__ import annotations

from pathlib import Path
from typing import List

from sqlalchemy.orm import Session

from app.models.camera import Camera


def device_exists(device_path: str) -> bool:
    p = Path(device_path)
    return p.exists() and p.is_char_device()


def list_video_devices() -> List[str]:
    dev = Path("/dev")
    if not dev.exists():
        return []
    return sorted(str(p) for p in dev.glob("video*") if p.exists())


def device_used_by_running_camera(db: Session, device_path: str) -> bool:
    q = (
        db.query(Camera)
        .filter(Camera.device_path == device_path)
        .filter(Camera.status == "running")
    )
    return db.query(q.exists()).scalar() is True

