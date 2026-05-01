from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel


class Settings(BaseModel):
    project_root: Path
    data_dir: Path
    videos_dir: Path
    thumbnails_dir: Path
    logs_dir: Path
    database_url: str
    frontend_origin: str


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    # `src/backend/app/config.py` -> project root is `virtual-camera-platform/`
    # Path parts: .../virtual-camera-platform/src/backend/app/config.py
    # parents[0]=app, [1]=backend, [2]=src, [3]=virtual-camera-platform
    project_root = Path(__file__).resolve().parents[3]
    data_dir = project_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return Settings(
        project_root=project_root,
        data_dir=data_dir,
        videos_dir=data_dir / "videos",
        thumbnails_dir=data_dir / "thumbnails",
        logs_dir=data_dir / "logs",
        database_url=f"sqlite:///{(data_dir / 'app.db').as_posix()}",
        frontend_origin="http://localhost:5173",
    )

