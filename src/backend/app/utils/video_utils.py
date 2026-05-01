from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2


@dataclass
class VideoMeta:
    fps: Optional[float]
    width: Optional[int]
    height: Optional[int]
    frame_count: Optional[int]
    duration: Optional[float]


def extract_opencv_metadata(video_path: Path) -> VideoMeta:
    cap = cv2.VideoCapture(str(video_path))
    try:
        if not cap.isOpened():
            return VideoMeta(None, None, None, None, None)

        fps = cap.get(cv2.CAP_PROP_FPS)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0) or None
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0) or None
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0) or None

        fps_val = float(fps) if fps and fps > 0 else None
        duration = None
        if fps_val and frame_count:
            duration = frame_count / fps_val

        return VideoMeta(fps_val, width, height, frame_count, duration)
    finally:
        cap.release()


def generate_thumbnail(video_path: Path, thumbnail_path: Path) -> bool:
    cap = cv2.VideoCapture(str(video_path))
    try:
        if not cap.isOpened():
            return False

        for _ in range(60):  # try a few frames in case frame 0 is empty
            ok, frame = cap.read()
            if not ok or frame is None:
                continue
            thumbnail_path.parent.mkdir(parents=True, exist_ok=True)
            return bool(cv2.imwrite(str(thumbnail_path), frame))

        return False
    finally:
        cap.release()

