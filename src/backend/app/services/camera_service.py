from __future__ import annotations

import os
import platform
import subprocess
import sys
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import List

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
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

logger = logging.getLogger(__name__)


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

    normalized_device = device_service.normalize_device_path(payload.device_path)

    if not device_service.device_exists(normalized_device):
        raise HTTPException(
            status_code=400,
            detail=f"Device '{payload.device_path}' not found. On Linux, load v4l2loopback first.",
        )

    if device_service.device_used_by_running_camera(db, normalized_device):
        raise HTTPException(
            status_code=400,
            detail=f"Device '{payload.device_path}' is already used by a running camera.",
        )

    cam = Camera(
        name=payload.name,
        video_id=payload.video_id,
        device_path=normalized_device,
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

    normalized_device = device_service.normalize_device_path(cam.device_path)

    if not device_service.device_exists(normalized_device):
        raise HTTPException(
            status_code=400,
            detail=f"Device '{cam.device_path}' not found. On Linux, load v4l2loopback first.",
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

    if device_service.device_used_by_running_camera(db, normalized_device):
        raise HTTPException(
            status_code=400,
            detail=f"Device '{cam.device_path}' is already used by a running camera.",
        )

    settings = get_settings()
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = settings.logs_dir / f"camera_{cam.id}.log"

    # Spawn worker from `src/backend`: `python -m app.workers.camera_worker ...`
    cmd = [
        sys.executable,
        "-m",
        "app.workers.camera_worker",
        "--camera-id",
        cam.id,
        "--video-path",
        str(video_path),
        "--loop" if cam.loop else "--no-loop",
    ]
    # Linux: explicit /dev/videoX. macOS/Windows: let pyvirtualcam pick platform backend (e.g. OBS).
    if platform.system().lower() == "linux":
        cmd += ["--device-path", normalized_device]
    if cam.fps:
        cmd += ["--fps", str(cam.fps)]
    if cam.width:
        cmd += ["--width", str(cam.width)]
    if cam.height:
        cmd += ["--height", str(cam.height)]

    with log_path.open("a", encoding="utf-8") as log_file:
        log_file.write(f"\n=== start {datetime.utcnow().isoformat()}Z ===\n")
        log_file.write("CMD: " + " ".join(cmd) + "\n")
        log_file.flush()

        popen_kwargs = {
            "cwd": str(Path(__file__).resolve().parents[2]),  # `src/backend`
            "stdout": log_file,
            "stderr": subprocess.STDOUT,
            "stdin": subprocess.DEVNULL,
            "text": True,
            "close_fds": True,
        }
        if platform.system().lower().startswith("win"):
            popen_kwargs["creationflags"] = (
                subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
            )

        proc = subprocess.Popen(cmd, **popen_kwargs)
        logger.info(
            "Started camera worker camera_id=%s worker_pid=%s backend_pid=%s os=%s",
            cam.id,
            proc.pid,
            os.getpid(),
            platform.system(),
        )

        # Give the worker a moment to fail fast if pyvirtualcam can't initialize.
        time.sleep(0.25)
        if proc.poll() is not None:
            cam.pid = None
            cam.status = "failed"
            db.add(cam)
            db.commit()
            db.refresh(cam)
            raise HTTPException(
                status_code=400,
                detail=f"Worker failed to start. Check log: {log_path}",
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
        pid = cam.pid
        logger.info(
            "Stop camera requested camera_id=%s pid=%s os=%s",
            cam.id,
            pid,
            platform.system(),
        )
        try:
            stop_process(pid)
        except Exception:
            # Never crash the API on stop; log and proceed to mark camera stopped.
            logger.exception("Failed to stop worker process camera_id=%s pid=%s", cam.id, pid)
        finally:
            cam.pid = None
    else:
        logger.info("Stop camera requested camera_id=%s pid=None (already stopped?)", cam.id)

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

