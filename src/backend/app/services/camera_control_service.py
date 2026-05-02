from __future__ import annotations

import shutil
from pathlib import Path

from app.config import get_settings


class CameraControlError(RuntimeError):
    pass


def camera_control_dir(camera_id: str) -> Path:
    base = get_settings().controls_dir
    return base / str(camera_id)


def pause_flag_path(camera_id: str) -> Path:
    return camera_control_dir(camera_id) / "pause.flag"


def set_paused(camera_id: str) -> None:
    d = camera_control_dir(camera_id)
    try:
        d.mkdir(parents=True, exist_ok=True)
        flag = pause_flag_path(camera_id)
        flag.touch(exist_ok=True)
        if not flag.exists():
            raise CameraControlError("pause.flag was not created (unknown filesystem error).")
    except CameraControlError:
        raise
    except Exception as e:
        raise CameraControlError(f"Failed to create pause.flag: {e}") from e


def clear_paused(camera_id: str) -> None:
    flag = pause_flag_path(camera_id)
    try:
        flag.unlink(missing_ok=True)
        if flag.exists():
            raise CameraControlError("pause.flag still exists after attempting to remove it.")
    except CameraControlError:
        raise
    except Exception as e:
        raise CameraControlError(f"Failed to remove pause.flag: {e}") from e


def is_paused(camera_id: str) -> bool:
    try:
        return pause_flag_path(camera_id).exists()
    except Exception:
        return False


def cleanup_controls(camera_id: str) -> None:
    d = camera_control_dir(camera_id)
    try:
        if not d.exists():
            return
        # Remove only this camera's directory.
        shutil.rmtree(d, ignore_errors=True)
    except Exception:
        return

