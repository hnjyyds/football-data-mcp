from __future__ import annotations

from pathlib import Path

from football_data_mcp.learning_store import learning_db_path


class LearningRepository:
    """Small adapter for learning database metadata used by health checks."""

    def db_path(self) -> str:
        return learning_db_path()

    def db_accessible(self) -> bool:
        path = self.db_path()
        return Path(path).exists() if path else False
