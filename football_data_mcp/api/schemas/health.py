from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from typing import Any


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    uptime_seconds: int
    db_path: str
    db_accessible: bool
    last_learning_cycle_at: str | None
    last_learning_cycle_error: str | None
    auto_learning_enabled: bool
    task_queue: dict[str, Any]
    odds_source_status: dict[str, Any]
    generated_at_utc: str
