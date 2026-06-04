from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class MobileMatchesResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str
    generatedAtUTC: str
    matches: list[dict[str, Any]]


class MobileAnalysisResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str
    generatedAtUTC: str
    analysis: dict[str, Any]
