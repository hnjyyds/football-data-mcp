from __future__ import annotations

import time
from typing import Any

from football_data_mcp.repositories.data_source_repository import DataSourceRepository


class DataSourceService:
    def __init__(self, repository: DataSourceRepository | None = None) -> None:
        self._repository = repository or DataSourceRepository()

    async def fdo_matches(self, *, date_from: str | None, date_to: str | None) -> dict[str, Any]:
        return await self._repository.fetch_fdo_matches(date_from=date_from, date_to=date_to)

    async def source_probe(self) -> tuple[dict[str, Any], float]:
        start = time.time()
        result = await self._repository.probe_all_sources()
        return result, time.time() - start
