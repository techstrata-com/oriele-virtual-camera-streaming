from __future__ import annotations

import shutil
from pathlib import Path

from app.config import get_settings


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def safe_remove_file(path: Path) -> None:
    try:
        if path.exists() and path.is_file():
            path.unlink()
    except Exception:
        # Best-effort cleanup for MVP.
        pass


def safe_remove_dir(path: Path) -> None:
    try:
        if path.exists() and path.is_dir():
            shutil.rmtree(path)
    except Exception:
        # Best-effort cleanup for MVP.
        pass


def file_size_bytes(path: Path) -> int:
    return path.stat().st_size


def build_video_dir(video_id: str) -> Path:
    s = get_settings()
    return s.videos_dir / video_id


def build_thumbnail_path(video_id: str) -> Path:
    s = get_settings()
    return s.thumbnails_dir / f"{video_id}.jpg"

