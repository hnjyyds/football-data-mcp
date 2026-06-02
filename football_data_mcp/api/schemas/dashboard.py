from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class DashboardSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    generated_at_utc: str | None
    kpis: dict[str, Any]
    prediction_kpis: dict[str, Any]
    strategy_status: str | None
    strategy_sample_count: int | None


class DashboardSnapshotResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str | None = None
    tool: str | None = None
    generated_at_utc: str | None = None


class DashboardRecordResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str | None = None
    tool: str | None = None


class DashboardMatchResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str | None = None
    tool: str | None = None


class DashboardLarkPredictionResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str
    tool: str
    sent: bool
    channel: str
    ledger_id: str
