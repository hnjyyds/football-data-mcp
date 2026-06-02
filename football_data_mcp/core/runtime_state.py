from __future__ import annotations

import threading
import time


_SERVER_START_TIME = time.time()
_learning_cycle_status_lock = threading.Lock()
_last_learning_cycle_time: float | None = None
_last_learning_cycle_error: str | None = None


def server_start_time() -> float:
    return _SERVER_START_TIME


def learning_cycle_status() -> tuple[float | None, str | None]:
    """Read daemon status as one consistent pair."""
    with _learning_cycle_status_lock:
        return _last_learning_cycle_time, _last_learning_cycle_error


def reset_learning_cycle_status() -> None:
    """Reset daemon status for process bootstrap and reload-based tests."""
    global _last_learning_cycle_time, _last_learning_cycle_error
    with _learning_cycle_status_lock:
        _last_learning_cycle_time = None
        _last_learning_cycle_error = None


def record_learning_cycle_status(*, finished_at: float | None, error: str | None) -> None:
    """Write daemon status through one lock so health checks never see torn data."""
    global _last_learning_cycle_time, _last_learning_cycle_error
    with _learning_cycle_status_lock:
        if finished_at is not None:
            _last_learning_cycle_time = finished_at
        _last_learning_cycle_error = error


def auto_learning_state_cycle_status() -> tuple[str | None, str | None]:
    """Read the latest self-reported auto-learning cycle status."""
    from football_data_mcp import sources

    state = sources.AUTO_LEARNING_STATE
    finished_at = state.get("last_finished_at_utc")
    last_error = state.get("last_error")
    return (
        str(finished_at) if finished_at else None,
        str(last_error) if last_error else None,
    )
