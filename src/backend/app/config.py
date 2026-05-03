from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel

_BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(_BACKEND_DIR / ".env", override=False)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    v = raw.strip().lower()
    if v in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if v in {"0", "false", "f", "no", "n", "off"}:
        return False
    return default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw.strip())
    except Exception:
        return default


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw.strip())
    except Exception:
        return default


class Settings(BaseModel):
    project_root: Path
    data_dir: Path
    controls_dir: Path
    videos_dir: Path
    thumbnails_dir: Path
    logs_dir: Path
    database_url: str
    frontend_origin: str
    rtsp_enabled: bool
    rtsp_host: str
    rtsp_port: int
    rtsp_public_base_url: str
    http_live_public_base_url: str
    ffmpeg_binary: str
    stream_default_fps: float


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    # `src/backend/app/config.py` -> project root is `virtual-camera-platform/`
    # Path parts: .../virtual-camera-platform/src/backend/app/config.py
    # parents[0]=app, [1]=backend, [2]=src, [3]=virtual-camera-platform
    project_root = Path(__file__).resolve().parents[3]
    data_dir = project_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    controls_dir = data_dir / "controls"
    controls_dir.mkdir(parents=True, exist_ok=True)
    logs_dir = data_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return Settings(
        project_root=project_root,
        data_dir=data_dir,
        controls_dir=controls_dir,
        videos_dir=data_dir / "videos",
        thumbnails_dir=data_dir / "thumbnails",
        logs_dir=logs_dir,
        database_url=f"sqlite:///{(data_dir / 'app.db').as_posix()}",
        frontend_origin=os.getenv("FRONTEND_ORIGIN", "http://localhost:5173"),
        rtsp_enabled=_env_bool("RTSP_ENABLED", True),
        rtsp_host=os.getenv("RTSP_HOST", "localhost").strip() or "localhost",
        rtsp_port=_env_int("RTSP_PORT", 8554),
        rtsp_public_base_url=os.getenv("RTSP_PUBLIC_BASE_URL", "").strip(),
        http_live_public_base_url=os.getenv("HTTP_LIVE_PUBLIC_BASE_URL", "").strip(),
        ffmpeg_binary=os.getenv("FFMPEG_BINARY", "ffmpeg").strip() or "ffmpeg",
        stream_default_fps=max(1.0, _env_float("STREAM_DEFAULT_FPS", 30.0)),
    )

