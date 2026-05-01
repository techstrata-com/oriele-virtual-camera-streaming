from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class VideoOut(BaseModel):
    id: str
    name: str
    original_filename: str
    file_path: str
    thumbnail_path: Optional[str] = None
    duration: Optional[float] = None
    fps: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    size_bytes: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

