from __future__ import annotations

import logging
import os
import re
import shutil
import stat
import subprocess
import threading
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.camera import Camera
from app.services import device_service

logger = logging.getLogger(__name__)

_LABEL_MAX = 220
_DEVICE_PATH_RE = re.compile(r"^/dev/video(\d+)$")

# Serializes minor-number selection and v4l2loopback-ctl add across threads.
_ALLOCATION_LOCK = threading.Lock()


class VirtualCameraError(Exception):
    """Allocation or creation of a v4l2loopback device failed."""


def build_device_label(client_id: str, video_name: str) -> str:
    """
    Human-readable v4l2 card label: "{client_id} - {video_name}".
    Sanitized and length-limited for sysfs / v4l2.
    """
    cid = (client_id or "").strip()
    base = Path((video_name or "").strip()).name
    base = re.sub(r"[\x00-\x1f\x7f]", "", base)
    base = re.sub(r"\s+", " ", base).strip() or "video"
    if len(base) > 120:
        stem = Path(base).stem[:100]
        suf = Path(base).suffix[:16]
        base = stem + suf

    label = f"{cid} - {base}"
    if len(label) > _LABEL_MAX:
        label = label[: _LABEL_MAX - 1] + "…"
    return label


def _video_nr_from_path(device_path: str) -> Optional[int]:
    m = _DEVICE_PATH_RE.match(device_service.normalize_device_path(device_path))
    if not m:
        return None
    return int(m.group(1))


def read_sysfs_device_label(device_path: str) -> Optional[str]:
    """Return trimmed contents of /sys/class/video4linux/videoN/name, or None if missing."""
    n = _video_nr_from_path(device_path)
    if n is None:
        return None
    p = Path(f"/sys/class/video4linux/video{n}/name")
    if not p.is_file():
        return None
    try:
        return p.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None


def find_existing_device_by_label(label: str) -> Optional[str]:
    """Find first /dev/videoX whose sysfs name equals this label."""
    want = (label or "").strip()
    if not want:
        return None

    v4l_root = Path("/sys/class/video4linux")
    if not v4l_root.is_dir():
        return None

    for entry in sorted(v4l_root.iterdir()):
        if not entry.is_dir() or not entry.name.startswith("video"):
            continue
        name_file = entry / "name"
        if not name_file.is_file():
            continue
        try:
            current = name_file.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            continue
        if current == want:
            m = re.fullmatch(r"video(\d+)", entry.name)
            if m:
                return f"/dev/video{m.group(1)}"
    return None


def _v4l2loopback_module_present() -> bool:
    return Path("/sys/module/v4l2loopback").exists()


def _resolve_ctl_binary() -> Optional[str]:
    settings = get_settings()
    ctl = settings.v4l2loopback_ctl_binary.strip() or "v4l2loopback-ctl"
    if Path(ctl).is_absolute():
        return ctl if Path(ctl).exists() else None
    w = shutil.which(ctl)
    return w


def _raise_ctl_not_found() -> None:
    raise VirtualCameraError(
        "v4l2loopback-ctl was not found. Install v4l2loopback-utils or configure V4L2LOOPBACK_CTL_BINARY."
    )


def _classify_ctl_failure(stderr: str, stdout: str) -> VirtualCameraError:
    combined = f"{stderr}\n{stdout}".lower()
    if "sudo" in combined and (
        "password" in combined
        or "a password is required" in combined
        or "a terminal is required" in combined
    ):
        return VirtualCameraError(
            "Could not run v4l2loopback-ctl with sudo non-interactively (sudo -n). "
            "Configure passwordless sudo for v4l2loopback-ctl or run the backend with sufficient privileges."
        )
    if "permission" in combined or "operation not permitted" in combined:
        return VirtualCameraError(
            "Could not create v4l2loopback device. The backend process needs permission to run "
            "v4l2loopback-ctl add, or the service must run with sufficient privileges."
        )
    if "unknown symbol" in combined or ("modprobe" in combined and "v4l2loopback" in combined):
        return VirtualCameraError(
            "v4l2loopback kernel module is not loaded or not installed."
        )
    if "no such file" in combined or "not found" in combined or "cannot access" in combined:
        if "v4l2loopback" in combined or "loopback" in combined:
            return VirtualCameraError(
                "v4l2loopback kernel module is not loaded or not installed."
            )
    return VirtualCameraError(
        "Could not create v4l2loopback device. The backend process needs permission to run "
        "v4l2loopback-ctl add, or the service must run with sufficient privileges."
        + (f" Details: {(stderr or stdout or '').strip()}" if (stderr or stdout) else "")
    )


def verify_device_matches_label(device_path: str, expected_label: str) -> None:
    """
    Ensure /dev/videoX exists and sysfs name matches expected_label exactly.
    """
    p = Path(device_service.normalize_device_path(device_path))
    try:
        st = os.stat(p, follow_symlinks=False)
    except OSError as e:
        logger.error("Label verification failed: cannot stat %s: %s (expected label=%r)", device_path, e, expected_label)
        raise VirtualCameraError(
            "Created device verification failed: node missing or invalid after v4l2loopback-ctl add."
        ) from e
    if not stat.S_ISCHR(st.st_mode):
        logger.error(
            "Label verification failed: %s is not a character device (expected label=%r)",
            device_path,
            expected_label,
        )
        raise VirtualCameraError(
            "Created device verification failed: node missing or invalid after v4l2loopback-ctl add."
        )

    actual = read_sysfs_device_label(device_path)
    if actual is None:
        logger.error(
            "Label verification failed: no sysfs name for %s (expected label=%r)",
            device_path,
            expected_label,
        )
        raise VirtualCameraError(
            "Created device verification failed: /sys/class/video4linux/*/name is missing."
        )

    if actual != expected_label:
        logger.error(
            "Label verification failed: %s sysfs name %r != expected %r",
            device_path,
            actual,
            expected_label,
        )
        raise VirtualCameraError(
            f"Created device verification failed: sysfs label is {actual!r}, expected {expected_label!r}."
        )


def _run_ctl_add(ctl_path: str, device_path: str, label: str) -> None:
    settings = get_settings()
    if settings.v4l2loopback_use_sudo:
        cmd = ["sudo", "-n", ctl_path, "add", "-n", label, device_path]
    else:
        cmd = [ctl_path, "add", "-n", label, device_path]

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except FileNotFoundError as e:
        if settings.v4l2loopback_use_sudo and e.filename == "sudo":
            raise VirtualCameraError(
                "sudo was not found but V4L2LOOPBACK_USE_SUDO=true. Install sudo or disable sudo mode."
            ) from e
        _raise_ctl_not_found()
    except subprocess.CalledProcessError as e:
        err = (e.stderr or "") + "\n" + (e.stdout or "")
        logger.warning("v4l2loopback-ctl add failed rc=%s cmd=%s err=%s", e.returncode, cmd, err.strip())
        raise _classify_ctl_failure(e.stderr or "", e.stdout or "") from e


def create_virtual_camera_device(device_path: str, label: str) -> None:
    """Run v4l2loopback-ctl add and rely on caller to verify sysfs label."""
    ctl_path = _resolve_ctl_binary()
    if not ctl_path:
        _raise_ctl_not_found()

    if not _v4l2loopback_module_present():
        raise VirtualCameraError(
            "v4l2loopback kernel module is not loaded or not installed."
        )

    _run_ctl_add(ctl_path, device_path, label)


def _validate_requested_linux_device(device_path: str) -> str:
    dp = device_service.normalize_device_path(device_path)
    m = _DEVICE_PATH_RE.match(dp)
    if not m:
        raise VirtualCameraError(
            f"Invalid device path '{device_path}': expected /dev/video<number> on Linux."
        )
    n = int(m.group(1))
    settings = get_settings()
    if n < settings.virtual_camera_start_nr or n > settings.virtual_camera_end_nr:
        raise VirtualCameraError(
            f"Device '{dp}' is outside allowed range "
            f"/dev/video{settings.virtual_camera_start_nr}–"
            f"{settings.virtual_camera_end_nr}."
        )
    return dp


def _camera_row_owning_device(db: Session, device_path: str) -> Optional[Camera]:
    dp = device_service.normalize_device_path(device_path)
    return db.query(Camera).filter(Camera.device_path == dp).first()


def _ensure_device_not_registered_to_other_camera(
    db: Session,
    device_path: str,
    client_id: str,
    video_id: str,
) -> None:
    """
    If device_path is already stored for a different (client_id, video_id), refuse.
    Same pair should have been handled by create_camera idempotency before allocation.
    """
    row = _camera_row_owning_device(db, device_path)
    if row is None:
        return
    if row.client_id == client_id and row.video_id == video_id:
        return
    raise VirtualCameraError(
        f"Device {device_path} is already registered to another camera (different client or video)."
    )


def get_or_create_virtual_camera_device(
    *,
    db: Session,
    client_id: str,
    video_id: str,
    video_name: str,
    requested_device_path: Optional[str] = None,
) -> tuple[str, str]:
    """
    Returns (device_path, device_label).

    Linux policy:
    - Only reuses a node if sysfs card name matches the built label exactly.
    - Otherwise creates a new node with v4l2loopback-ctl add -n <label> /dev/videoN.
    - Never assigns an existing generic (wrong label) /dev/videoX to this client.
    """
    settings = get_settings()
    label = build_device_label(client_id, video_name)

    if not settings.virtual_camera_dynamic_create:
        raise VirtualCameraError(
            "Labeled per-client virtual cameras require dynamic creation. "
            "Set VIRTUAL_CAMERA_DYNAMIC_CREATE=true (default). "
            "Pre-created unlabeled device pools are not supported for this flow."
        )

    # --- Optional manual path (advanced): sysfs label must match exactly ---
    if requested_device_path and requested_device_path.strip():
        dp = _validate_requested_linux_device(requested_device_path)
        with _ALLOCATION_LOCK:
            _ensure_device_not_registered_to_other_camera(db, dp, client_id, video_id)
            p = Path(dp)
            if p.exists():
                actual = read_sysfs_device_label(dp)
                if actual != label:
                    raise VirtualCameraError(
                        f"Device {dp} exists but its label is {actual!r}; "
                        f"expected {label!r}. Refusing to use a generic or mismatched device."
                    )
                verify_device_matches_label(dp, label)
                return dp, label
            _ensure_module_and_ctl_for_linux()
            create_virtual_camera_device(dp, label)
            verify_device_matches_label(dp, label)
            return dp, label

    # --- Default: find by label first (no module required), else create with correct label only ---
    with _ALLOCATION_LOCK:
        existing = find_existing_device_by_label(label)
        if existing:
            _ensure_device_not_registered_to_other_camera(db, existing, client_id, video_id)
            verify_device_matches_label(existing, label)
            return existing, label

        _ensure_module_and_ctl_for_linux()

        for n in range(settings.virtual_camera_start_nr, settings.virtual_camera_end_nr + 1):
            candidate = f"/dev/video{n}"
            _ensure_device_not_registered_to_other_camera(db, candidate, client_id, video_id)

            p = Path(candidate)
            if p.exists():
                sysfs_name = read_sysfs_device_label(candidate)
                if sysfs_name is None:
                    continue
                if sysfs_name == label:
                    verify_device_matches_label(candidate, label)
                    return candidate, label
                # Occupied by another card label — do not steal.
                continue

            # Free minor: create node with exact label (single implementation path)
            try:
                create_virtual_camera_device(candidate, label)
            except VirtualCameraError:
                raise
            except Exception:
                logger.exception("Unexpected failure creating %s", candidate)
                raise VirtualCameraError(
                    "Could not create v4l2loopback device. The backend process needs permission to run "
                    "v4l2loopback-ctl add, or the service must run with sufficient privileges."
                )

            try:
                verify_device_matches_label(candidate, label)
            except VirtualCameraError:
                logger.error("Verification failed after add for %s label=%r", candidate, label)
                raise

            return candidate, label

        raise VirtualCameraError(
            f"No free video minor in range "
            f"{settings.virtual_camera_start_nr}–{settings.virtual_camera_end_nr} "
            "for a new labeled device. Delete unused cameras or widen the range."
        )


def _ensure_module_and_ctl_for_linux() -> None:
    """Fast-fail hints before scanning minors (also used by manual path)."""
    if not _v4l2loopback_module_present():
        raise VirtualCameraError(
            "v4l2loopback kernel module is not loaded or not installed."
        )
    if not _resolve_ctl_binary():
        _raise_ctl_not_found()
