from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import List

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.camera import Camera
from app.models.video import Video
from app.schemas.camera_schema import CameraCreate
from app.services import device_service
from app.services.process_service import is_alive, stop_process


VALID_STATUSES = {
    "created",
    "stopped",
    "starting",
    "running",
    "stopping",
    "failed",
}


def list_cameras(db: Session) -> List[Camera]:
    return db.query(Camera).order_by(Camera.created_at.desc()).all()


def get_camera(db: Session, camera_id: str) -> Camera:
    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found.")
    return cam


def create_camera(db: Session, payload: CameraCreate) -> Camera:
    video = db.query(Video).filter(Video.id == payload.video_id).first()
    if not video:
        raise HTTPException(status_code=400, detail="Video does not exist.")

    if not device_service.device_exists(payload.device_path):
        raise HTTPException(
            status_code=400,
            detail=f"Device '{payload.device_path}' not found. Load v4l2loopback first.",
        )

    if device_service.device_used_by_running_camera(db, payload.device_path):
        raise HTTPException(
            status_code=400,
            detail=f"Device '{payload.device_path}' is already used by a running camera.",
        )

    cam = Camera(
        name=payload.name,
        video_id=payload.video_id,
        device_path=payload.device_path,
        status="stopped",
        pid=None,
        fps=payload.fps,
        width=payload.width,
        height=payload.height,
        loop=payload.loop,
    )
    db.add(cam)
    db.commit()
    db.refresh(cam)
    return cam


def start_camera(db: Session, camera_id: str) -> Camera:
    cam = get_camera(db, camera_id)
    video = db.query(Video).filter(Video.id == cam.video_id).first()
    if not video:
        raise HTTPException(status_code=400, detail="Camera video not found.")

    video_path = Path(video.file_path)
    if not video_path.exists():
        raise HTTPException(status_code=400, detail="Video file does not exist on disk.")

    if not device_service.device_exists(cam.device_path):
        raise HTTPException(
            status_code=400,
            detail=f"Device '{cam.device_path}' not found. Load v4l2loopback first.",
        )

    if cam.status == "running" and cam.pid:
        if is_alive(cam.pid):
            raise HTTPException(status_code=400, detail="Camera is already running.")
        cam.pid = None
        cam.status = "failed"
        db.add(cam)
        db.commit()
        db.refresh(cam)
        raise HTTPException(status_code=400, detail="Camera was marked running but process is dead.")

    if device_service.device_used_by_running_camera(db, cam.device_path):
        raise HTTPException(
            status_code=400,
            detail=f"Device '{cam.device_path}' is already used by a running camera.",
        )

    # Spawn worker from `src/backend`: `python -m app.workers.camera_worker ...`
    cmd = [
        sys.executable,
        "-m",
        "app.workers.camera_worker",
        "--camera-id",
        cam.id,
        "--video-path",
        str(video_path),
        "--device-path",
        cam.device_path,
        "--loop" if cam.loop else "--no-loop",
    ]
    if cam.fps:
        cmd += ["--fps", str(cam.fps)]
    if cam.width:
        cmd += ["--width", str(cam.width)]
    if cam.height:
        cmd += ["--height", str(cam.height)]

    proc = subprocess.Popen(
        cmd,
        cwd=str(Path(__file__).resolve().parents[2]),  # `src/backend`
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    cam.pid = proc.pid
    cam.status = "running"
    cam.last_started_at = datetime.utcnow()
    db.add(cam)
    db.commit()
    db.refresh(cam)
    return cam


def stop_camera(db: Session, camera_id: str) -> Camera:
    cam = get_camera(db, camera_id)

    if cam.pid:
        try:
            stop_process(cam.pid)
        finally:
            cam.pid = None

    cam.status = "stopped"
    cam.last_stopped_at = datetime.utcnow()
    db.add(cam)
    db.commit()
    db.refresh(cam)
    return cam


def restart_camera(db: Session, camera_id: str) -> Camera:
    stop_camera(db, camera_id)
    return start_camera(db, camera_id)


def delete_camera(db: Session, camera_id: str) -> None:
    cam = get_camera(db, camera_id)
    if cam.pid and cam.status == "running":
        stop_camera(db, camera_id)
        cam = get_camera(db, camera_id)
    db.delete(cam)
    db.commit()

