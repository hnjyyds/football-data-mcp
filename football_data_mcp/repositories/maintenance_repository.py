from __future__ import annotations

from typing import Any

from football_data_mcp import db_janitor


class MaintenanceRepository:
    """Persistence maintenance operations."""

    def run_db_janitor(self, *, dry_run: bool) -> dict[str, Any]:
        return db_janitor.run_janitor(dry_run=dry_run)
