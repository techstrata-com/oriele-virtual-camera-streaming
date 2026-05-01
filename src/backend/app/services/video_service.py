from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.camera import Camera
from app.models.video import Video
from app.utils.file_utils import (
    build_thumbnail_path,
    build_video_dir,
    ensure_dir,
    file_size_bytes,
    safe_remove_dir,
    safe_remove_file,
)
from app.utils.video_utils import extract_opencv_metadata, generate_thumbnail


def list_videos(db: Session) -> List[Video]:
    return db.query(Video).order_by(Video.created_at.desc()).all()


def get_video(db: Session, video_id: str) -> Video:
    v = db.query(Video).filter(Video.id == video_id).first()
    if not v:
        raise HTTPException(status_code=404, detail=f"Video '{video_id}' not found.")
    return v


def save_upload(db: Session, file: UploadFile, name: Optional[str] = None) -> Video:
    settings = get_settings()
    ensure_dir(settings.videos_dir)
    ensure_dir(settings.thumbnails_dir)

    video = Video(
        name=name or (Path(file.filename).stem if file.filename else "Untitled"),
        original_filename=file.filename or "upload.bin",
        file_path="",
        size_bytes=0,
    )
    db.add(video)
    db.commit()
    db.refresh(video)

    video_dir = build_video_dir(video.id)
    ensure_dir(video_dir)

    dest_path = video_dir / video.original_filename
    with dest_path.open("wb") as out:
        while True:
            chunk = file.file.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)

    video.file_path = str(dest_path.resolve())
    video.size_bytes = file_size_bytes(dest_path)

    meta = extract_opencv_metadata(dest_path)
    video.fps = meta.fps
    video.width = meta.width
    video.height = meta.height
    video.duration = meta.duration

    thumb_path = build_thumbnail_path(video.id)
    if generate_thumbnail(dest_path, thumb_path):
        video.thumbnail_path = str(thumb_path.resolve())

    db.add(video)
    db.commit()
    db.refresh(video)
    return video


def delete_video(db: Session, video_id: str) -> None:
    video = get_video(db, video_id)

    # Prevent deletion if any camera references it.
    in_use = db.query(Camera).filter(Camera.video_id == video.id).count()
    if in_use:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete this video because at least one camera is using it.",
        )

    # Delete files first (best-effort), then DB row.
    try:
        if video.thumbnail_path:
            safe_remove_file(Path(video.thumbnail_path))
        video_dir = build_video_dir(video.id)
        safe_remove_dir(video_dir)

        # If stored elsewhere, try removing path directly.
        if video.file_path:
            p = Path(video.file_path)
            if p.exists() and p.is_file():
                safe_remove_file(p)
    finally:
        db.delete(video)
        db.commit()

