from __future__ import annotations

from typing import Any

from football_data_mcp import profitability_calculator


class ProfitabilityRepository:
    """Read profitability forecast calculations."""

    def full_profitability_report(self) -> dict[str, Any]:
        return profitability_calculator.full_profitability_report()
