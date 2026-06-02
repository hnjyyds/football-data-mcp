from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class FdoMatchesQuery(BaseModel):
    date_from: str | None = Field(default=None, max_length=32)
    date_to: str | None = Field(default=None, max_length=32)


class FdoMatchesResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str | None = None


class SourcesProbeResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    available_count: int | None = None
