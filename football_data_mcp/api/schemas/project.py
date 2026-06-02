from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ProjectArchitectureLayer(BaseModel):
    name: str
    responsibility: str


class ProjectResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    name: str
    version: str
    architecture: list[ProjectArchitectureLayer]
    controllers: list[str]
    generated_at_utc: str
