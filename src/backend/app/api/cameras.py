from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.camera_schema import CameraCreate, CameraOut
from app.services import camera_service

router = APIRouter(prefix="/api/cameras", tags=["cameras"])


@router.post("", response_model=CameraOut)
def create_camera(payload: CameraCreate, db: Session = Depends(get_db)):
    return camera_service.create_camera(db, payload)


@router.get("", response_model=list[CameraOut])
def list_cameras(db: Session = Depends(get_db)):
    return camera_service.list_cameras(db)


@router.get("/{camera_id}", response_model=CameraOut)
def get_camera(camera_id: str, db: Session = Depends(get_db)):
    return camera_service.get_camera(db, camera_id)


@router.post("/{camera_id}/start", response_model=CameraOut)
def start_camera(camera_id: str, db: Session = Depends(get_db)):
    return camera_service.start_camera(db, camera_id)


@router.post("/{camera_id}/stop", response_model=CameraOut)
def stop_camera(camera_id: str, db: Session = Depends(get_db)):
    return camera_service.stop_camera(db, camera_id)


@router.post("/{camera_id}/restart", response_model=CameraOut)
def restart_camera(camera_id: str, db: Session = Depends(get_db)):
    return camera_service.restart_camera(db, camera_id)


@router.post("/{camera_id}/pause", response_model=CameraOut)
def pause_camera(camera_id: str, db: Session = Depends(get_db)):
    return camera_service.pause_camera(db, camera_id)


@router.post("/{camera_id}/resume", response_model=CameraOut)
def resume_camera(camera_id: str, db: Session = Depends(get_db)):
    return camera_service.resume_camera(db, camera_id)


@router.delete("/{camera_id}")
def delete_camera(camera_id: str, db: Session = Depends(get_db)):
    camera_service.delete_camera(db, camera_id)
    return {"deleted": True}


@router.get("/{camera_id}/stream-urls")
def get_camera_stream_urls(camera_id: str, db: Session = Depends(get_db)):
    cam = camera_service.get_camera(db, camera_id)

    available = cam.status in {"running", "paused"} and bool(cam.rtsp_url) and bool(cam.http_live_url)

    if not available:
        return {
            "camera_id": cam.id,
            "status": cam.status,
            "rtsp_url": None,
            "http_live_url": None,
            "available": False,
            "message": "Camera is not running or live streams are not available.",
        }

    return {
        "camera_id": cam.id,
        "status": cam.status,
        "rtsp_url": cam.rtsp_url,
        "http_live_url": cam.http_live_url,
        "available": True,
    }

