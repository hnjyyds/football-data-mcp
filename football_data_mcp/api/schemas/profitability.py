from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ProfitabilityForecastResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str | None = None
