from __future__ import annotations

import asyncio
from typing import Any

from football_data_mcp.repositories.profitability_repository import ProfitabilityRepository


class ProfitabilityService:
    def __init__(self, repository: ProfitabilityRepository | None = None) -> None:
        self._repository = repository or ProfitabilityRepository()

    async def forecast(self) -> dict[str, Any]:
        return await asyncio.to_thread(self._repository.full_profitability_report)
