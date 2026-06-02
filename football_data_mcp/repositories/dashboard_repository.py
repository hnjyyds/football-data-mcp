from __future__ import annotations

from typing import Any

from football_data_mcp import sources


class DashboardRepository:
    """Read dashboard projections from the learning and snapshot stores."""

    def snapshot_reader(self):
        return sources.dashboard_snapshot

    def snapshot(self) -> dict[str, Any]:
        return sources.dashboard_snapshot()

    def record_detail_reader(self):
        return sources.dashboard_record_detail

    def record_detail(self, record_id: str) -> dict[str, Any]:
        return sources.dashboard_record_detail(record_id)

    def match_detail_reader(self):
        return sources.dashboard_match_detail

    def match_detail(self, ledger_id: str) -> dict[str, Any]:
        return sources.dashboard_match_detail(ledger_id)
