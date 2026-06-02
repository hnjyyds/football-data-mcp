from __future__ import annotations

import asyncio
from typing import Any

from football_data_mcp.config import load_server_settings
from football_data_mcp.core.errors import AuthorizationError
from football_data_mcp.repositories.maintenance_repository import MaintenanceRepository


class MaintenanceService:
    def __init__(self, repository: MaintenanceRepository | None = None) -> None:
        self._repository = repository or MaintenanceRepository()

    async def run_db_janitor(self, *, execute: bool, provided_admin_token: str) -> dict[str, Any]:
        """Run janitor in dry-run by default and require admin token for writes."""
        if execute:
            expected = load_server_settings().admin_token
            if not expected:
                raise AuthorizationError(
                    code="admin_token_not_configured",
                    message="Admin token is required before executing database cleanup.",
                )
            if provided_admin_token != expected:
                raise AuthorizationError(code="admin_token_invalid", message="Admin token is invalid.")
        return await asyncio.to_thread(self._repository.run_db_janitor, dry_run=not execute)
