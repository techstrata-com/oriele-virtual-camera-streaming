from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CameraCreate(BaseModel):
    client_id: str = Field(..., min_length=1, examples=["client-123"])
    name: str
    video_id: str
    # Linux: optional — backend allocates /dev/videoX when omitted.
    # macOS/Windows: optional — defaults to obs/auto behavior when omitted.
    device_path: Optional[str] = Field(
        default=None,
        examples=["/dev/video10", "obs", "auto"],
    )
    fps: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    loop: bool = True

    @field_validator("client_id")
    @classmethod
    def trim_client_id(cls, v: str) -> str:
        s = (v or "").strip()
        if not s:
            raise ValueError("client_id must not be empty")
        if s == "legacy":
            raise ValueError('client_id "legacy" is reserved for migrated records')
        return s


class CameraOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    client_id: str
    video_id: str
    device_path: str
    device_label: Optional[str] = None
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
