from __future__ import annotations

import logging
import os
import platform
import subprocess
from pathlib import Path
from typing import Optional, TextIO

from app.config import get_settings


logger = logging.getLogger(__name__)


def build_rtsp_push_url(camera_id: str) -> str:
    settings = get_settings()
    return f"rtsp://{settings.rtsp_host}:{settings.rtsp_port}/{camera_id}"


def build_rtsp_public_url(camera_id: str) -> str:
    settings = get_settings()
    base = (settings.rtsp_public_base_url or "").strip().rstrip("/")
    if base:
        return f"{base}/{camera_id}"
    return build_rtsp_push_url(camera_id)


def build_http_live_url(camera_id: str) -> str:
    settings = get_settings()
    base = (settings.http_live_public_base_url or "").strip().rstrip("/")
    if base:
        return f"{base}/live/{camera_id}"
    return f"http://localhost:8000/live/{camera_id}"


def _is_linux() -> bool:
    return platform.system().lower() == "linux"


def _is_windows() -> bool:
    return platform.system().lower().startswith("win")


def start_rtsp_process(
    *,
    camera_id: str,
    video_path: Path,
    device_path: str,
    loop: bool,
    fps: Optional[float],
    width: Optional[int],
    height: Optional[int],
    log_file: TextIO,
) -> tuple[subprocess.Popen, str]:
    settings = get_settings()
    if not settings.rtsp_enabled:
        raise RuntimeError("RTSP is disabled")

    push_url = build_rtsp_push_url(camera_id)
    public_url = build_rtsp_public_url(camera_id)

    cmd: list[str] = [settings.ffmpeg_binary, "-y"]

    if _is_linux():
        cmd += ["-re", "-f", "v4l2", "-i", device_path]
    else:
        if loop:
            cmd += ["-stream_loop", "-1"]
        cmd += ["-re", "-i", str(video_path)]

    vf_parts: list[str] = []
    if width and height:
        vf_parts.append(f"scale={width}:{height}")
    if vf_parts:
        cmd += ["-vf", ",".join(vf_parts)]

    if fps is not None:
        try:
            if float(fps) > 0:
                cmd += ["-r", str(fps)]
        except Exception:
            pass

    cmd += [
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-tune",
        "zerolatency",
        "-f",
        "rtsp",
        push_url,
    ]

    log_file.write(f"\n=== rtsp start {camera_id} backend_pid={os.getpid()} os={platform.system()} ===\n")
    log_file.write("FFMPEG_CMD: " + " ".join(cmd) + "\n")
    log_file.write(f"RTSP_PUSH_URL: {push_url}\n")
    log_file.write(f"RTSP_PUBLIC_URL: {public_url}\n")
    log_file.flush()

    popen_kwargs = {
        "stdout": log_file,
        "stderr": subprocess.STDOUT,
        "stdin": subprocess.DEVNULL,
        "text": True,
        "close_fds": True,
    }
    if _is_windows():
        popen_kwargs["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        )

    try:
        proc = subprocess.Popen(cmd, **popen_kwargs)
    except FileNotFoundError as e:
        raise RuntimeError("FFmpeg was not found. Install FFmpeg or set FFMPEG_BINARY.") from e

    logger.info(
        "Started RTSP ffmpeg camera_id=%s ffmpeg_pid=%s push_url=%s public_url=%s backend_pid=%s os=%s",
        camera_id,
        proc.pid,
        push_url,
        public_url,
        os.getpid(),
        platform.system(),
    )
    log_file.write(f"FFMPEG_PID: {proc.pid}\n")
    log_file.flush()
    return proc, push_url

