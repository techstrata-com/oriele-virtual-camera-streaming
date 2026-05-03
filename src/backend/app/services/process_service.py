from __future__ import annotations

import logging
import os
import platform
import signal
import subprocess
import time
import csv
from io import StringIO
from typing import Optional


logger = logging.getLogger(__name__)


def _is_windows() -> bool:
    return platform.system().lower().startswith("win")


def is_alive(pid: int) -> bool:
    if pid is None:
        return False
    try:
        pid_int = int(pid)
    except Exception:
        return False
    if pid_int <= 0:
        return False

    # Windows: os.kill(pid, 0) is not reliable. Use tasklist.
    if _is_windows():
        try:
            # /FO CSV makes parsing reliable; /NH removes header.
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid_int}", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                check=False,
            )
            out = (result.stdout or "").strip()
            if not out:
                return False
            # When no tasks match, tasklist typically returns an INFO line.
            if out.lower().startswith("info:"):
                return False

            # Parse CSV rows; expect PID in second column.
            reader = csv.reader(StringIO(out))
            for row in reader:
                if len(row) >= 2:
                    try:
                        if int(row[1]) == pid_int:
                            return True
                    except Exception:
                        continue
            return False
        except Exception:
            # Fail closed on Windows to avoid stale \"running\" states.
            return False

    # POSIX: keep os.kill(pid, 0) semantics.
    try:
        os.kill(pid_int, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        # Assume alive if we can't signal it.
        return True
    except OSError:
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


def stop_stream_worker(pid: int, timeout_s: float = 4.0) -> None:
    """
    Stop the dedicated stream worker and its FFmpeg child.

    Windows: taskkill /T /F terminates the worker process tree (never the backend when pid is correct).
    POSIX: SIGTERM/SIGKILL on the worker's process group (start_new_session worker).
    """
    current_pid = os.getpid()
    logger.info(
        "stop_stream_worker target_pid=%s backend_pid=%s os=%s timeout_s=%s",
        pid,
        current_pid,
        platform.system(),
        timeout_s,
    )
    if pid == current_pid:
        logger.error(
            "Refusing to stop stream worker pid=%s because it matches the backend process.",
            pid,
        )
        return

    if not is_alive(pid):
        logger.info("Stream worker already stopped pid=%s", pid)
        return

    if _is_windows():
        try:
            result = subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                text=True,
                check=False,
            )
            logger.info("taskkill tree returncode pid=%s: %s", pid, result.returncode)
            if result.stdout:
                logger.info("taskkill stdout pid=%s: %s", pid, result.stdout.strip())
            if result.stderr:
                logger.warning("taskkill stderr pid=%s: %s", pid, result.stderr.strip())
        except Exception:
            logger.exception("taskkill /T failed pid=%s", pid)
        start = time.time()
        while time.time() - start < timeout_s:
            if not is_alive(pid):
                return
            time.sleep(0.05)
        logger.warning("Stream worker still alive after taskkill pid=%s", pid)
        return

    # POSIX: terminate whole process group led by the worker.
    try:
        pgid = os.getpgid(pid)
    except OSError as e:
        logger.warning("Could not getpgid for pid=%s: %s; falling back to single process", pid, e)
        pgid = pid

    logger.info("POSIX killpg SIGTERM pgid=%s (worker pid=%s)", pgid, pid)
    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        logger.info("Process group already gone pgid=%s", pgid)
        return
    except Exception:
        logger.exception("SIGTERM process group pgid=%s", pgid)
        stop_process(pid, timeout_s=timeout_s)
        return

    start = time.time()
    while time.time() - start < timeout_s:
        if not is_alive(pid):
            logger.info("Stream worker stopped after SIGTERM pgid=%s pid=%s", pgid, pid)
            return
        time.sleep(0.05)

    logger.warning("SIGKILL process group pgid=%s pid=%s", pgid, pid)
    try:
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        return
    except Exception:
        logger.exception("SIGKILL process group pgid=%s", pgid)

    wait_end = time.time() + 0.5
    while time.time() < wait_end:
        if not is_alive(pid):
            return
        time.sleep(0.05)


def safe_int(value: Optional[object]) -> Optional[int]:
    try:
        return int(value) if value is not None else None
    except Exception:
        return None

