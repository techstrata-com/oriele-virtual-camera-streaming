from __future__ import annotations

import time
from pathlib import Path
from typing import Iterator, Optional

import cv2
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.video import Video
from app.services import camera_service


router = APIRouter(tags=["live"])


def _mjpeg_frames(
    *,
    video_path: Path,
    loop: bool,
    fps: Optional[float],
    width: Optional[int],
    height: Optional[int],
) -> Iterator[bytes]:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise HTTPException(status_code=400, detail="OpenCV cannot open video.")

    try:
        src_fps = cap.get(cv2.CAP_PROP_FPS)
        out_fps = fps or (float(src_fps) if src_fps and src_fps > 0 else 10.0)
        if out_fps <= 0:
            out_fps = 10.0
        delay_s = 1.0 / out_fps

        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                if loop:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                break

            if width and height and (frame.shape[1] != width or frame.shape[0] != height):
                frame = cv2.resize(frame, (int(width), int(height)), interpolation=cv2.INTER_AREA)

            ok_jpg, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            if not ok_jpg:
                continue

            jpg = buf.tobytes()
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + jpg + b"\r\n"
            )
            time.sleep(delay_s)
    finally:
        cap.release()


@router.get("/live/{camera_id}")
def live_mjpeg(camera_id: str, db: Session = Depends(get_db)):
    cam = camera_service.get_camera(db, camera_id)
    if cam.status != "running" or not cam.pid:
        raise HTTPException(status_code=409, detail="Camera is not running.")

    video = db.query(Video).filter(Video.id == cam.video_id).first()
    if not video:
        raise HTTPException(status_code=400, detail="Camera video not found.")

    video_path = Path(video.file_path)
    if not video_path.exists():
        raise HTTPException(status_code=400, detail="Video file does not exist on disk.")

    return StreamingResponse(
        _mjpeg_frames(
            video_path=video_path,
            loop=bool(cam.loop),
            fps=cam.fps,
            width=cam.width,
            height=cam.height,
        ),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )

