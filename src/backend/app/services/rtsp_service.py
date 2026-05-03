from __future__ import annotations

from app.config import get_settings


def build_rtsp_push_url(camera_id: str) -> str:
    settings = get_settings()
    return f"rtsp://{settings.rtsp_host}:{settings.rtsp_port}/{camera_id}"


def build_rtsp_public_url(camera_id: str) -> str:
    settings = get_settings()
    base = (settings.rtsp_public_base_url or "").strip().rstrip("/")
    if base:
        return f"{base}/{camera_id}"
    return build_rtsp_push_url(camera_id)


def build_http_live_url(camera_id: str) -> str:
    settings = get_settings()
    base = (settings.http_live_public_base_url or "").strip().rstrip("/")
    if base:
        return f"{base}/live/{camera_id}"
    return f"http://localhost:8000/live/{camera_id}"
