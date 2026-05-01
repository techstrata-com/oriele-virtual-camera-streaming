from __future__ import annotations

import logging
import os
import platform
import signal
import subprocess
import time
from typing import Optional


logger = logging.getLogger(__name__)


def _is_windows() -> bool:
    return platform.system().lower().startswith("win")


def is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        # Assume alive if we can't signal it.
        return True
    except OSError:
        # On Windows, os.kill can raise OSError for invalid/non-existent PIDs.
        return False


def stop_process(pid: int, timeout_s: float = 2.0) -> None:
    os_name = platform.system()
    current_pid = os.getpid()
    logger.info(
        "Stopping process target_pid=%s current_backend_pid=%s os=%s timeout_s=%s",
        pid,
        current_pid,
        os_name,
        timeout_s,
    )

    if pid == current_pid:
        logger.error(
            "Refusing to stop pid=%s because it is the current backend process.",
            pid,
        )
        return

    # If it's already dead, treat as success.
    if not is_alive(pid):
        logger.info("Process already stopped pid=%s", pid)
        return

    if _is_windows():
        # Windows: use taskkill so we don't depend on Unix-only signals.
        # NOTE: do NOT use /T (process tree) because it can kill the backend too.
        logger.info("Windows stop attempt (taskkill) pid=%s", pid)
        try:
            result = subprocess.run(
                ["taskkill", "/PID", str(pid), "/F"],
                capture_output=True,
                text=True,
                check=False,
            )
            logger.info("taskkill returncode pid=%s: %s", pid, result.returncode)
            if result.stdout:
                logger.info("taskkill stdout pid=%s: %s", pid, result.stdout.strip())
            if result.stderr:
                logger.warning("taskkill stderr pid=%s: %s", pid, result.stderr.strip())
            # "process not found" -> already stopped; treat as success.
            combined = f"{result.stdout}\n{result.stderr}".lower()
            if "not found" in combined or "no running instance" in combined:
                logger.info("taskkill reports not found; treating as already stopped pid=%s", pid)
                return
        except Exception:
            logger.exception("taskkill failed pid=%s", pid)
            return

        # Give the OS a moment to tear it down.
        start = time.time()
        while time.time() - start < timeout_s:
            if not is_alive(pid):
                logger.info("Windows process stopped pid=%s", pid)
                return
            time.sleep(0.05)

        # If still alive, don't raise—just log. (We already attempted taskkill /F.)
        logger.warning("Windows process still alive after taskkill pid=%s", pid)
        return

    # Unix-like (Linux/macOS): graceful SIGTERM then SIGKILL if needed.
    logger.info("Unix graceful terminate (SIGTERM) pid=%s", pid)
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        logger.info("Process exited before SIGTERM pid=%s", pid)
        return
    except Exception:
        logger.exception("SIGTERM failed pid=%s", pid)
        return

    start = time.time()
    while time.time() - start < timeout_s:
        if not is_alive(pid):
            logger.info("Process stopped after SIGTERM pid=%s", pid)
            return
        time.sleep(0.05)

    logger.warning("Graceful stop timed out; force kill (SIGKILL) pid=%s", pid)
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        logger.info("Process exited before SIGKILL pid=%s", pid)
        return
    except Exception:
        logger.exception("SIGKILL failed pid=%s", pid)
        return

    # Best-effort final check.
    start = time.time()
    while time.time() - start < 0.5:
        if not is_alive(pid):
            break
        time.sleep(0.05)
    logger.info("Force kill done pid=%s alive=%s", pid, is_alive(pid))


def safe_int(value: Optional[object]) -> Optional[int]:
    try:
        return int(value) if value is not None else None
    except Exception:
        return None

