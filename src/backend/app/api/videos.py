from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.video_schema import VideoOut
from app.services import video_service

router = APIRouter(prefix="/api/videos", tags=["videos"])


@router.post("/upload", response_model=VideoOut)
def upload_video(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename.")
    return video_service.save_upload(db, file)


@router.get("", response_model=list[VideoOut])
def list_videos(db: Session = Depends(get_db)):
    return video_service.list_videos(db)


@router.get("/{video_id}", response_model=VideoOut)
def get_video(video_id: str, db: Session = Depends(get_db)):
    return video_service.get_video(db, video_id)


@router.delete("/{video_id}")
def delete_video(video_id: str, db: Session = Depends(get_db)):
    video_service.delete_video(db, video_id)
    return {"deleted": True}


@router.get("/{video_id}/thumbnail")
def get_thumbnail(video_id: str, db: Session = Depends(get_db)):
    v = video_service.get_video(db, video_id)
    if not v.thumbnail_path:
        raise HTTPException(status_code=404, detail="Thumbnail not available.")
    p = Path(v.thumbnail_path)
    if not p.exists():
        raise HTTPException(status_code=404, detail="Thumbnail file missing on disk.")
    return FileResponse(str(p), media_type="image/jpeg")

