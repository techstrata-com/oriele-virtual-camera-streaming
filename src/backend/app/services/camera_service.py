from __future__ import annotations

import logging
import os
import platform
import subprocess
import sys
import time
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
from app.services import camera_control_service
from app.services import rtsp_service
from app.services.process_service import is_alive, stop_process, stop_stream_worker

logger = logging.getLogger(__name__)


def _effective_fps(cam: Camera) -> float:
    settings = get_settings()
    if cam.fps is not None:
        try:
            f = float(cam.fps)
            if f > 0:
                return f
        except Exception:
            pass
    return float(settings.stream_default_fps)


def _mark_start_failed(db: Session, camera_id: str) -> Camera:
    """
    Best-effort reset after a failed start attempt.
    Only flips to failed if the camera is still in `starting` to avoid clobbering
    a concurrent stop() that already moved it to stopped.
    """
    db.query(Camera).filter(Camera.id == camera_id, Camera.status == "starting").update(
        {
            Camera.status: "failed",
            Camera.rtsp_pid: None,
            Camera.pid: None,
            Camera.rtsp_url: None,
            Camera.http_live_url: None,
        }
    )
    db.commit()
    return get_camera(db, camera_id)


def sync_camera_process_state(db: Session, cam: Camera) -> Camera:
    if cam.status not in {"running", "paused"}:
        return cam
    pid = cam.rtsp_pid
    if pid and is_alive(pid):
        return cam

    logger.warning(
        "Stream worker missing or dead; marking camera failed camera_id=%s status_was=%s rtsp_pid=%s",
        cam.id,
        cam.status,
        pid,
    )
    cam.status = "failed"
    cam.rtsp_pid = None
    cam.pid = None
    cam.rtsp_url = None
    cam.http_live_url = None
    try:
        camera_control_service.cleanup_controls(cam.id)
    except Exception:
        logger.exception("cleanup_controls failed during sync camera_id=%s", cam.id)
    db.add(cam)
    db.commit()
    db.refresh(cam)
    return cam


def list_cameras(db: Session) -> List[Camera]:
    rows = db.query(Camera).order_by(Camera.created_at.desc()).all()
    return [sync_camera_process_state(db, c) for c in rows]


def get_camera(db: Session, camera_id: str) -> Camera:
    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(status_code=404, detail=f"Camera '{camera_id}' not found.")
    return sync_camera_process_state(db, cam)


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

    cam = Camera(
        name=payload.name,
        client_id=client_id,
        video_id=payload.video_id,
        device_path="",
        device_label=None,
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
    settings = get_settings()
    cam = get_camera(db, camera_id)
    if not settings.rtsp_enabled:
        raise HTTPException(
            status_code=400,
            detail="RTSP is disabled (RTSP_ENABLED=false). Enable RTSP or set RTSP_ENABLED=1.",
        )

    # Ensure we don't start with stale process state.
    cam = sync_camera_process_state(db, cam)

    video = db.query(Video).filter(Video.id == cam.video_id).first()
    if not video:
        raise HTTPException(status_code=400, detail="Camera video not found.")

    video_path = Path(video.file_path)
    if not video_path.exists():
        raise HTTPException(status_code=400, detail="Video file does not exist on disk.")

    if cam.status == "paused":
        raise HTTPException(status_code=400, detail="Camera is paused. Use resume instead.")

    if cam.status == "starting":
        raise HTTPException(status_code=409, detail="Camera is already starting.")

    if cam.status == "running" and cam.rtsp_pid and is_alive(cam.rtsp_pid):
        return cam

    # If another request is racing with this one, we must acquire a \"starting\" lock
    # before spawning the worker, otherwise two workers could be created.
    #
    # For SQLite, keep it simple: update the row to starting BEFORE spawning.
    updated = (
        db.query(Camera)
        .filter(
            Camera.id == cam.id,
            Camera.status.in_({"stopped", "failed"}),
        )
        .update(
            {
                Camera.status: "starting",
                Camera.rtsp_pid: None,
                Camera.pid: None,
                Camera.rtsp_url: None,
                Camera.http_live_url: None,
            }
        )
    )
    if updated != 1:
        # Someone else beat us to it: reload and respond based on current state.
        db.rollback()
        fresh = get_camera(db, cam.id)
        if fresh.status == "running" and fresh.rtsp_pid and is_alive(fresh.rtsp_pid):
            return fresh
        if fresh.status == "paused":
            raise HTTPException(status_code=400, detail="Camera is paused. Use resume instead.")
        if fresh.status == "starting":
            raise HTTPException(status_code=409, detail="Camera is already starting.")
        # Fallback: not in a startable state.
        raise HTTPException(status_code=409, detail=f"Camera cannot be started from status '{fresh.status}'.")

    db.commit()
    cam = get_camera(db, cam.id)
    if cam.status != "starting":
        # Shouldn't happen, but fail safe: never spawn without the lock.
        raise HTTPException(status_code=409, detail="Camera start was preempted by another request.")

    # Anything after we acquire `starting` must not leave the camera stuck in `starting`.
    try:
        ctrl = camera_control_service.camera_control_dir(cam.id)
        ctrl.mkdir(parents=True, exist_ok=True)
        camera_control_service.clear_paused(cam.id)
        settings.logs_dir.mkdir(parents=True, exist_ok=True)
        log_path = settings.logs_dir / f"camera_{cam.id}.log"

        eff_fps = _effective_fps(cam)
        cmd = [
            sys.executable,
            "-m",
            "app.workers.stream_worker",
            "--camera-id",
            cam.id,
            "--video-path",
            str(video_path),
            "--loop" if cam.loop else "--no-loop",
            "--control-dir",
            str(ctrl),
            "--rtsp-push-url",
            rtsp_service.build_rtsp_push_url(cam.id),
            "--ffmpeg-binary",
            settings.ffmpeg_binary,
            "--fps",
            str(eff_fps),
        ]
        if cam.width:
            cmd += ["--width", str(cam.width)]
        if cam.height:
            cmd += ["--height", str(cam.height)]

        with log_path.open("a", encoding="utf-8") as log_file:
            log_file.write(f"\n=== stream start {datetime.utcnow().isoformat()}Z ===\n")
            log_file.write("CMD: " + " ".join(cmd) + "\n")
            log_file.flush()

            popen_kwargs: dict = {
                "cwd": str(Path(__file__).resolve().parents[2]),
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
            else:
                popen_kwargs["start_new_session"] = True

            proc = subprocess.Popen(cmd, **popen_kwargs)

            logger.info(
                "Started stream_worker camera_id=%s worker_pid=%s backend_pid=%s os=%s",
                cam.id,
                proc.pid,
                os.getpid(),
                platform.system(),
            )

            time.sleep(0.35)
            if proc.poll() is not None:
                cam = _mark_start_failed(db, cam.id)
                rc = proc.returncode
                raise HTTPException(
                    status_code=400,
                    detail=f"Stream worker exited immediately (code {rc}). Check log: {log_path}",
                )
    except HTTPException:
        # Worker-exited path already marked failed above; for setup errors this ensures we don't stick in starting.
        if get_camera(db, cam.id).status == "starting":
            _mark_start_failed(db, cam.id)
        raise
    except Exception as e:
        _mark_start_failed(db, cam.id)
        raise HTTPException(status_code=500, detail=f"Failed to start camera: {e}") from e

    # Transition starting -> running only if still starting (stop could race).
    updated = (
        db.query(Camera)
        .filter(Camera.id == cam.id, Camera.status == "starting")
        .update(
            {
                Camera.status: "running",
                Camera.rtsp_pid: proc.pid,
                Camera.pid: None,
                Camera.rtsp_url: rtsp_service.build_rtsp_public_url(cam.id),
                Camera.http_live_url: rtsp_service.build_http_live_url(cam.id),
                Camera.last_started_at: datetime.utcnow(),
            }
        )
    )
    db.commit()
    cam = get_camera(db, cam.id)
    if updated != 1:
        # Camera was stopped/changed while starting; ensure worker is not left behind.
        try:
            stop_stream_worker(proc.pid)
        except Exception:
            logger.exception("Failed to stop orphaned worker after start race camera_id=%s pid=%s", cam.id, proc.pid)
        raise HTTPException(status_code=409, detail="Camera start was interrupted. Try again.")

    return cam


def stop_camera(db: Session, camera_id: str) -> Camera:
    cam = get_camera(db, camera_id)
    camera_control_service.cleanup_controls(cam.id)

    # If we're in the middle of starting and no pid is recorded yet, just reset safely.
    if cam.status == "starting" and not cam.rtsp_pid:
        cam.status = "stopped"
        cam.pid = None
        cam.rtsp_pid = None
        cam.rtsp_url = None
        cam.http_live_url = None
        cam.last_stopped_at = datetime.utcnow()
        db.add(cam)
        db.commit()
        db.refresh(cam)
        return cam

    if cam.rtsp_pid:
        rtp = cam.rtsp_pid
        logger.info(
            "Stop stream worker camera_id=%s rtsp_pid=%s os=%s",
            cam.id,
            rtp,
            platform.system(),
        )
        try:
            stop_stream_worker(rtp)
        except Exception:
            logger.exception("Failed to stop stream worker camera_id=%s pid=%s", cam.id, rtp)
        finally:
            cam.rtsp_pid = None

    if cam.pid:
        p = cam.pid
        logger.info("Stop legacy worker camera_id=%s pid=%s", cam.id, p)
        try:
            stop_process(p)
        except Exception:
            logger.exception("Failed to stop legacy worker camera_id=%s pid=%s", cam.id, p)
        finally:
            cam.pid = None

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
    if cam.status in {"running", "paused"} or cam.rtsp_pid or cam.pid:
        stop_camera(db, camera_id)
    camera_control_service.cleanup_controls(camera_id)
    cam = db.query(Camera).filter(Camera.id == camera_id).first()
    if not cam:
        return
    db.delete(cam)
    db.commit()


def pause_camera(db: Session, camera_id: str) -> Camera:
    cam = get_camera(db, camera_id)

    if cam.status == "paused":
        return cam

    if cam.status != "running":
        raise HTTPException(status_code=400, detail="Camera must be running to pause.")

    if not cam.rtsp_pid or not is_alive(cam.rtsp_pid):
        raise HTTPException(
            status_code=400,
            detail="Camera stream worker is not running. Restart the camera.",
        )

    try:
        camera_control_service.set_paused(cam.id)
    except camera_control_service.CameraControlError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

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

    if not cam.rtsp_pid or not is_alive(cam.rtsp_pid):
        raise HTTPException(
            status_code=400,
            detail="Camera stream worker is not running. Restart the camera.",
        )

    try:
        camera_control_service.clear_paused(cam.id)
    except camera_control_service.CameraControlError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    if camera_control_service.is_paused(cam.id):
        raise HTTPException(status_code=500, detail="Failed to resume camera: pause flag still exists.")
    cam.status = "running"
    db.add(cam)
    db.commit()
    db.refresh(cam)
    return cam
