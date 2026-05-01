from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CameraCreate(BaseModel):
    name: str
    video_id: str
    # Linux: /dev/video10, /dev/video11, ...
    # macOS/Windows (OBS): "obs" or "auto" (device is selected by pyvirtualcam backend)
    device_path: str = Field(..., examples=["/dev/video10", "obs", "auto"])
    fps: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    loop: bool = True


class CameraOut(BaseModel):
    id: str
    name: str
    video_id: str
    device_path: str
    status: str
    pid: Optional[int] = None
    rtsp_pid: Optional[int] = None
    rtsp_url: Optional[str] = None
    http_live_url: Optional[str] = None
    fps: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    loop: bool
    created_at: datetime
    updated_at: datetime
    last_started_at: Optional[datetime] = None
    last_stopped_at: Optional[datetime] = None

    class Config:
        from_attributes = True

