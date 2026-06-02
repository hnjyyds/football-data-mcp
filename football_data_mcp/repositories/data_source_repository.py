from __future__ import annotations

from typing import Any

from football_data_mcp import data_sources_registry


class DataSourceRepository:
    """Gateway for fixture and source-health reads."""

    async def fetch_fdo_matches(self, *, date_from: str | None, date_to: str | None) -> dict[str, Any]:
        return await data_sources_registry.fetch_all_upcoming_matches(date_from=date_from, date_to=date_to)

    async def probe_all_sources(self) -> dict[str, Any]:
        return await data_sources_registry.probe_all_sources()
