from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class DbJanitorQuery(BaseModel):
    execute: bool = False


class DbJanitorResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    dry_run: bool | None = None
    totals: dict[str, int] | None = None
