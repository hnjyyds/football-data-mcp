from __future__ import annotations

from typing import Any

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


class OddsSourceSyncStateSchema(BaseModel):
    model_config = ConfigDict(extra="allow")

    latest_status: str | None = None
    attempt_count: int | None = None
    snapshot_count: int | None = None
    latest_started_at_utc: str | None = None
    latest_finished_at_utc: str | None = None
    latest_error: str | None = None


class OddsSourceStatusEntrySchema(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str
    role: str | None = None
    snapshot_count: int = 0
    operational_status: str | None = None
    latest_fetched_at_utc: str | None = None
    fresh_after_hours: float | None = None
    freshness_status: str | None = None
    age_hours: float | None = None
    age_seconds: float | None = None
    usable_for_analysis: bool | None = None
    retryable_url_count: int | None = None
    queued_count: int | None = None
    running_count: int | None = None
    failed_count: int | None = None
    empty_count: int | None = None
    scraper_enabled: bool | None = None
    auto_sync_enabled: bool | None = None
    discovery_ready: bool | None = None
    configured_discovery_url_count: int | None = None
    suggested_discovery_url_count: int | None = None
    effective_discovery_url_count: int | None = None
    discovery_urls: list[str] | None = None
    suggested_discovery_urls: list[str] | None = None
    effective_discovery_urls: list[str] | None = None
    open_target_count: int | None = None
    analysis_target_count: int | None = None
    discovery_target_count: int | None = None
    discovery_target_source: str | None = None
    last_error: str | None = None
    next_action: str | None = None
    sync: OddsSourceSyncStateSchema | None = None


class OddsSourceStatusPolicySchema(BaseModel):
    model_config = ConfigDict(extra="allow")

    read_path: str | None = None
    fallback_rule: str | None = None
    resume_rule: str | None = None
    freshness_rule: str | None = None


class OddsSourceClosureEntrySchema(BaseModel):
    model_config = ConfigDict(extra="allow")

    source: str
    operational_status: str | None = None
    freshness_status: str | None = None
    snapshot_count: int = 0
    latest_fetched_at_utc: str | None = None
    usable_for_analysis: bool = False


class OddsSourceClosureSchema(BaseModel):
    model_config = ConfigDict(extra="allow")

    active_source: str | None = None
    production_ready: bool
    reason: str
    checked_at_utc: str
    fresh_after_hours: float
    ordered_sources: list[OddsSourceClosureEntrySchema] = Field(default_factory=list)


class OddsSourceStatusResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str
    snapshot_summary: dict[str, Any] = Field(default_factory=dict)
    provider_counts: dict[str, Any] = Field(default_factory=dict)
    sync_state: dict[str, Any] = Field(default_factory=dict)
    sources: dict[str, OddsSourceStatusEntrySchema] = Field(default_factory=dict)
    closure: OddsSourceClosureSchema | None = None
    policy: OddsSourceStatusPolicySchema | None = None


class OddsPortalSyncRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_urls: list[str] = Field(default_factory=list)
    markets: list[str] = Field(default_factory=lambda: ["asian_handicap"])
    limit: int = Field(default=10, ge=1, le=20)
    force: bool = False
    resume_failed: bool = False
    resume_statuses: list[str] = Field(default_factory=lambda: ["failed", "empty"])
    auto_discover: bool = False
    discovery_urls: list[str] = Field(default_factory=list)
    target_limit: int = Field(default=50, ge=1, le=500)
    start: bool = True


class OddsPortalSyncResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    status: str
    provider: str | None = None
    job_id: str | None = None
    backend: str | None = None
    queue_job_id: str | None = None
