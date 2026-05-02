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
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.camera import Camera
from app.models.video import Video
from app.schemas.camera_schema import CameraCreate
from app.services import device_service
from app.services import camera_control_service
from app.services import rtsp_service
from app.services import virtual_camera_service
from app.services.process_service import is_alive, stop_process


VALID_STATUSES = {
    "created",
    "stopped",
    "starting",
    "running",
    "paused",
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

    client_id = payload.client_id.strip()

    existing = (
        db.query(Camera)
        .filter(Camera.client_id == client_id, Camera.video_id == payload.video_id)
        .first()
    )
    if existing:
        return existing

    device_path: str
    device_label: str | None

    if device_service.is_linux():
        try:
            device_path, device_label = virtual_camera_service.get_or_create_virtual_camera_device(
                db=db,
                client_id=client_id,
                video_id=payload.video_id,
                video_name=video.name,
                requested_device_path=payload.device_path,
            )
        except virtual_camera_service.VirtualCameraError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

        if device_service.device_used_by_any_camera(db, device_path):
            raise HTTPException(
                status_code=400,
                detail=f"Device '{device_path}' is already assigned to another camera.",
            )

        if not device_service.device_exists(device_path):
            raise HTTPException(
                status_code=400,
                detail=f"Device '{device_path}' not found. On Linux, load v4l2loopback first.",
            )
    else:
        raw = payload.device_path
        if raw is None or not str(raw).strip():
            raw = "obs"
        device_path = device_service.normalize_device_path(str(raw))
        device_label = None

        if not device_service.device_exists(device_path):
            raise HTTPException(
                status_code=400,
                detail="Invalid or unsupported device_path for this platform.",
            )

    cam = Camera(
        name=payload.name,
        client_id=client_id,
        video_id=payload.video_id,
        device_path=device_path,
        device_label=device_label,
        status="stopped",
        pid=None,
        rtsp_pid=None,
        rtsp_url=None,
        http_live_url=None,
        fps=payload.fps,
        width=payload.width,
        height=payload.height,
        loop=payload.loop,
    )
    db.add(cam)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        dup = (
            db.query(Camera)
            .filter(Camera.client_id == client_id, Camera.video_id == payload.video_id)
            .first()
        )
        if dup:
            return dup
        raise
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

    if cam.status == "paused":
        raise HTTPException(status_code=400, detail="Camera is paused. Use resume instead.")

    if device_service.device_used_by_running_camera(db, normalized_device):
        raise HTTPException(
            status_code=400,
            detail=f"Device '{cam.device_path}' is already used by a running camera.",
        )

    settings = get_settings()
    # Ensure controls exist and a fresh start isn't accidentally paused.
    camera_control_service.camera_control_dir(cam.id).mkdir(parents=True, exist_ok=True)
    camera_control_service.clear_paused(cam.id)
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
        "--control-dir",
        str(camera_control_service.camera_control_dir(cam.id)),
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

    # Start RTSP sidecar FFmpeg process (must not break the primary worker).
    cam.rtsp_pid = None
    cam.rtsp_url = None
    cam.http_live_url = None
    if settings.rtsp_enabled:
        try:
            with log_path.open("a", encoding="utf-8") as log_file:
                rtsp_proc, _push_url = rtsp_service.start_rtsp_process(
                    camera_id=cam.id,
                    video_path=video_path,
                    device_path=normalized_device,
                    loop=bool(cam.loop),
                    fps=cam.fps,
                    width=cam.width,
                    height=cam.height,
                    log_file=log_file,
                )

                time.sleep(0.25)
                if rtsp_proc.poll() is not None:
                    logger.error(
                        "RTSP ffmpeg exited immediately camera_id=%s returncode=%s; keeping worker running. log=%s",
                        cam.id,
                        rtsp_proc.returncode,
                        log_path,
                    )
                else:
                    cam.rtsp_pid = rtsp_proc.pid
                    cam.rtsp_url = rtsp_service.build_rtsp_public_url(cam.id)
                    cam.http_live_url = rtsp_service.build_http_live_url(cam.id)
        except Exception:
            logger.exception("Failed to start RTSP for camera_id=%s; keeping worker running", cam.id)
            cam.rtsp_pid = None
            cam.rtsp_url = None
            cam.http_live_url = None

        db.add(cam)
        db.commit()
        db.refresh(cam)

    return cam


def stop_camera(db: Session, camera_id: str) -> Camera:
    cam = get_camera(db, camera_id)

    # Always cleanup pause/resume controls on stop.
    camera_control_service.cleanup_controls(cam.id)

    # Stop RTSP first (sidecar), then the main worker.
    if cam.rtsp_pid:
        rtsp_pid = cam.rtsp_pid
        logger.info(
            "Stop RTSP requested camera_id=%s rtsp_pid=%s os=%s",
            cam.id,
            rtsp_pid,
            platform.system(),
        )
        try:
            stop_process(rtsp_pid)
        except Exception:
            logger.exception("Failed to stop RTSP process camera_id=%s pid=%s", cam.id, rtsp_pid)
        finally:
            cam.rtsp_pid = None

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
    cam.rtsp_url = None
    cam.http_live_url = None
    db.add(cam)
    db.commit()
    db.refresh(cam)
    return cam


def restart_camera(db: Session, camera_id: str) -> Camera:
    stop_camera(db, camera_id)
    return start_camera(db, camera_id)


def delete_camera(db: Session, camera_id: str) -> None:
    cam = get_camera(db, camera_id)
    if cam.status in {"running", "paused"} or cam.pid or cam.rtsp_pid:
        stop_camera(db, camera_id)
        cam = get_camera(db, camera_id)

    camera_control_service.cleanup_controls(camera_id)
    db.delete(cam)
    db.commit()


def pause_camera(db: Session, camera_id: str) -> Camera:
    cam = get_camera(db, camera_id)

    if cam.status == "paused":
        return cam

    if cam.status != "running":
        raise HTTPException(status_code=400, detail="Camera must be running to pause.")

    if not cam.pid or not is_alive(cam.pid):
        raise HTTPException(status_code=400, detail="Camera worker process is not running.")

    # RTSP pause behavior:
    # - Linux: FFmpeg reads from the v4l2 device; freezing the worker output freezes RTSP naturally.
    # - Non-Linux: FFmpeg reads directly from the video file (see rtsp_service), so pausing the worker
    #   does NOT pause RTSP playback. We intentionally do not try to pause FFmpeg cross-platform.
    if cam.rtsp_pid and platform.system().lower() != "linux":
        logger.warning(
            "Camera paused but RTSP sidecar is file-based on this OS; RTSP may keep advancing. camera_id=%s os=%s",
            cam.id,
            platform.system(),
        )

    try:
        camera_control_service.set_paused(cam.id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to pause camera: {e}") from e

    if not camera_control_service.is_paused(cam.id):
        raise HTTPException(status_code=500, detail="Failed to pause camera: pause flag was not created.")
    cam.status = "paused"
    db.add(cam)
    db.commit()
    db.refresh(cam)
    return cam


def resume_camera(db: Session, camera_id: str) -> Camera:
    cam = get_camera(db, camera_id)

    if cam.status == "running":
        return cam

    if cam.status != "paused":
        raise HTTPException(status_code=400, detail="Camera must be paused to resume.")

    if not cam.pid or not is_alive(cam.pid):
        raise HTTPException(status_code=400, detail="Camera worker process is not running.")

    try:
        camera_control_service.clear_paused(cam.id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to resume camera: {e}") from e

    if camera_control_service.is_paused(cam.id):
        raise HTTPException(status_code=500, detail="Failed to resume camera: pause flag still exists.")
    cam.status = "running"
    db.add(cam)
    db.commit()
    db.refresh(cam)
    return cam

