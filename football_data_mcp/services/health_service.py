from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from football_data_mcp.config import env_bool
from football_data_mcp.repositories.learning_repository import LearningRepository
from football_data_mcp.services.task_queue import task_queue_health_snapshot


LearningCycleStatusReader = Callable[[], tuple[float | None, str | None]]
AutoLearningStateReader = Callable[[], tuple[str | None, str | None]]


class HealthService:
    def __init__(
        self,
        *,
        learning_repository: LearningRepository | None = None,
        server_start_time: float,
        learning_cycle_status: LearningCycleStatusReader,
        auto_learning_state_status: AutoLearningStateReader,
    ) -> None:
        self._learning_repository = learning_repository or LearningRepository()
        self._server_start_time = server_start_time
        self._learning_cycle_status = learning_cycle_status
        self._auto_learning_state_status = auto_learning_state_status

    def health_snapshot(self) -> dict[str, Any]:
        """Build a health snapshot from infrastructure state and daemon status.

        主要阶段：
        - 读取学习数据库位置和可访问性；
        - 用同一份守护循环状态兜底 AUTO_LEARNING_STATE；
        - 生成前端和 Docker healthcheck 都能稳定解析的响应。
        """
        last_cycle_time, last_cycle_error = self._learning_cycle_status()
        last_learning_cycle_at = (
            datetime.fromtimestamp(last_cycle_time, tz=timezone.utc).isoformat()
            if last_cycle_time
            else None
        )
        state_cycle_at, state_cycle_error = self._auto_learning_state_status()
        if last_learning_cycle_at is None:
            last_learning_cycle_at = state_cycle_at
        if last_cycle_error is None:
            last_cycle_error = state_cycle_error
        return {
            "status": "ok",
            "uptime_seconds": int(time.time() - self._server_start_time),
            "db_path": self._learning_repository.db_path(),
            "db_accessible": self._learning_repository.db_accessible(),
            "last_learning_cycle_at": last_learning_cycle_at,
            "last_learning_cycle_error": last_cycle_error,
            "auto_learning_enabled": env_bool("FOOTBALL_DATA_AUTO_LEARNING_ENABLED", False),
            "task_queue": task_queue_health_snapshot(),
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        }
