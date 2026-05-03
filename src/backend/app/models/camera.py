from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Camera(Base):
    __tablename__ = "cameras"
    __table_args__ = (UniqueConstraint("client_id", "video_id", name="uq_camera_client_video"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String, nullable=False)

    client_id: Mapped[str] = mapped_column(String, nullable=False, default="legacy", index=True)
    video_id: Mapped[str] = mapped_column(String, ForeignKey("videos.id"), nullable=False)
    video = relationship("Video", lazy="joined")

    # Legacy virtual-camera path; unused for direct streaming (empty string for new rows).
    device_path: Mapped[str] = mapped_column(String, nullable=False, default="")
    device_label: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    status: Mapped[str] = mapped_column(String, nullable=False, default="stopped")
    pid: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    rtsp_pid: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    rtsp_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    http_live_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    fps: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    loop: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    last_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_stopped_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

