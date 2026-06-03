from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class HoldoutValidationJobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    divisions: list[str] = Field(default_factory=lambda: ["E0", "SP1", "I1", "D1", "F1"])
    training_seasons: list[str] = Field(default_factory=lambda: ["2122", "2223", "2324", "2425"])
    validation_seasons: list[str] = Field(default_factory=lambda: ["2526"])
    edge_thresholds: list[float] = Field(default_factory=lambda: [0.01, 0.02, 0.03, 0.04, 0.05])
    min_training_samples_options: list[int] = Field(default_factory=lambda: [20, 40, 80, 120])
    max_samples: int | None = None
    min_selection_bets: int = 30
    min_selection_evaluated: int = 100
    min_validation_bets: int = 50
    min_validation_evaluated: int = 100
    historical_rho_min_samples: int = 20
    use_cache: bool = True
    resume: bool = True
    start: bool = True


class ValidationJobProgressResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    total_leagues: int = 0
    completed_leagues: int = 0
    failed_leagues: int = 0
    running_leagues: int = 0
    pending_leagues: int = 0
    cancelled_leagues: int = 0
    processed_leagues: int = 0
    progress_ratio: float = 0.0
    success_ratio: float = 0.0


class ValidationLeagueResultResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    division: str | None = None
    league: str | None = None
    status: str | None = None
    cache_hit: bool = False
    error: str | None = None
    result: dict[str, Any] | None = None
    started_at_utc: str | None = None
    updated_at_utc: str | None = None
    finished_at_utc: str | None = None


class ValidationJobFailureLeagueResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    division: str | None = None
    league: str | None = None
    status: str | None = None
    error: str | None = None


class ValidationJobFailureSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    failed_count: int = 0
    recoverable: bool = False
    recoverable_count: int = 0
    latest_error: str | None = None
    category: str = "none"
    stage: str = "none"
    severity: str = "info"
    title: str = "暂无失败"
    detail: str = ""
    next_action: str = ""
    failed_leagues: list[ValidationJobFailureLeagueResponse] = Field(default_factory=list)


class ValidationJobExecutionHealthResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    state: str = "pending"
    severity: str = "warning"
    title: str = "等待入队"
    detail: str = ""
    next_action: str = ""
    is_stale: bool = False
    age_seconds: int | None = None
    queue_wait_seconds: int | None = None
    run_seconds: int | None = None
    updated_age_seconds: int | None = None
    heartbeat_age_seconds: int | None = None
    stale_after_seconds: int = 3900


class ValidationJobEventResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: int | None = None
    event_type: str | None = None
    severity: str = "info"
    message: str | None = None
    division: str | None = None
    runner_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at_utc: str | None = None


class ValidationJobResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    job_id: str | None = None
    status: str | None = None
    method: str | None = None
    current_runner_id: str | None = None
    attempt_count: int = 0
    retry_count: int = 0
    last_claim_reason: str | None = None
    last_retry_at_utc: str | None = None
    runner_heartbeat_at_utc: str | None = None
    recovered_at_utc: str | None = None
    failure_summary: ValidationJobFailureSummaryResponse | None = None
    execution_health: ValidationJobExecutionHealthResponse | None = None
    queue_backend: str | None = None
    queue_job_id: str | None = None
    queued_at_utc: str | None = None
    queue_status_message: str | None = None
    progress: ValidationJobProgressResponse | None = None
    league_results: list[ValidationLeagueResultResponse] = Field(default_factory=list)
    events: list[ValidationJobEventResponse] = Field(default_factory=list)
