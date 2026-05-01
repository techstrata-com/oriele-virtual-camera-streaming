from __future__ import annotations

import os
import signal
import time
from typing import Optional


def is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        # Assume alive if we can't signal it.
        return True


def stop_process(pid: int, timeout_s: float = 2.0) -> None:
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return

    start = time.time()
    while time.time() - start < timeout_s:
        if not is_alive(pid):
            return
        time.sleep(0.05)

    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        return


def safe_int(value: Optional[object]) -> Optional[int]:
    try:
        return int(value) if value is not None else None
    except Exception:
        return None

