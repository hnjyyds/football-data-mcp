from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Literal


TRUTHY_ENV_VALUES = {"1", "true", "yes", "on"}
DEFAULT_DASHBOARD_CORS_ORIGINS = ("http://localhost:8920", "http://127.0.0.1:8920")


def env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name, "true" if default else "false").strip().lower()
    return raw in TRUTHY_ENV_VALUES


def env_int(name: str, default: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    if not raw:
        return default
    return int(raw)


def env_str(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def env_csv(name: str, default: tuple[str, ...] = ()) -> list[str]:
    raw = env_str(name)
    if not raw:
        return list(default)
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class ServerSettings:
    host: str = field(default_factory=lambda: env_str("FOOTBALL_DATA_MCP_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: env_int("FOOTBALL_DATA_MCP_PORT", 8910))
    transport: Literal["stdio", "sse", "streamable-http"] = field(default_factory=lambda: _transport_from_env())
    dashboard_cors_origins: list[str] = field(
        default_factory=lambda: env_csv("FOOTBALL_DATA_DASHBOARD_CORS_ORIGINS", DEFAULT_DASHBOARD_CORS_ORIGINS)
    )
    admin_token: str = field(default_factory=lambda: env_str("FOOTBALL_DATA_ADMIN_TOKEN"))


@dataclass(frozen=True)
class AutoLearningSettings:
    interval_seconds: int = field(default_factory=lambda: env_int("FOOTBALL_DATA_AUTO_LEARNING_INTERVAL_SECONDS", 120))
    top_n: int = field(default_factory=lambda: env_int("FOOTBALL_DATA_AUTO_LEARNING_TOP_N", 12))
    limit: int = field(default_factory=lambda: env_int("FOOTBALL_DATA_AUTO_LEARNING_LIMIT", 80))
    timezone_name: str = field(default_factory=lambda: env_str("FOOTBALL_DATA_AUTO_LEARNING_TIMEZONE", "Asia/Shanghai"))
    asian_window_minutes: int = field(
        default_factory=lambda: env_int("FOOTBALL_DATA_AUTO_LEARNING_ASIAN_WINDOW_MINUTES", 10)
    )
    parlay_window_minutes: int = field(
        default_factory=lambda: env_int("FOOTBALL_DATA_AUTO_LEARNING_PARLAY_WINDOW_MINUTES", 10)
    )
    learning_observation_limit: int = field(
        default_factory=lambda: env_int("FOOTBALL_DATA_AUTO_LEARNING_OBSERVATION_LIMIT", 30)
    )
    analysis_candidate_limit: int = field(
        default_factory=lambda: env_int("FOOTBALL_DATA_AUTO_LEARNING_ANALYSIS_CANDIDATE_LIMIT", 80)
    )
    analysis_concurrency: int = field(
        default_factory=lambda: env_int("FOOTBALL_DATA_AUTO_LEARNING_ANALYSIS_CONCURRENCY", 10)
    )
    shadow_prediction_limit: int = field(
        default_factory=lambda: env_int("FOOTBALL_DATA_AUTO_LEARNING_SHADOW_PREDICTION_LIMIT", 100)
    )
    include_market_snapshot_sync: bool = field(
        default_factory=lambda: env_bool("FOOTBALL_DATA_AUTO_SYNC_LEISU_ODDS", True)
    )
    market_snapshot_window_minutes: int = field(
        default_factory=lambda: env_int("FOOTBALL_DATA_AUTO_LEARNING_SNAPSHOT_WINDOW_MINUTES", 1440)
    )
    market_snapshot_limit: int = field(
        default_factory=lambda: env_int("FOOTBALL_DATA_AUTO_LEARNING_SNAPSHOT_LIMIT", 80)
    )
    market_snapshot_concurrency: int = field(
        default_factory=lambda: env_int("FOOTBALL_DATA_AUTO_LEARNING_SNAPSHOT_CONCURRENCY", 4)
    )
    market_snapshot_require_quality_gate: bool = field(
        default_factory=lambda: env_bool("FOOTBALL_DATA_AUTO_LEARNING_SNAPSHOT_REQUIRE_QUALITY_GATE", True)
    )
    include_snapshot_reanalysis: bool = field(
        default_factory=lambda: env_bool("FOOTBALL_DATA_AUTO_LEARNING_SNAPSHOT_REANALYSIS", True)
    )
    snapshot_reanalysis_limit: int = field(
        default_factory=lambda: env_int("FOOTBALL_DATA_AUTO_LEARNING_REANALYSIS_LIMIT", 20)
    )
    snapshot_reanalysis_concurrency: int = field(
        default_factory=lambda: env_int("FOOTBALL_DATA_AUTO_LEARNING_REANALYSIS_CONCURRENCY", 4)
    )
    enforce_settlement_coverage: bool = field(
        default_factory=lambda: env_bool("FOOTBALL_DATA_AUTO_ENFORCE_SETTLEMENT_COVERAGE", True)
    )

    def as_dict(self, *, league_allowlist: list[str] | None = None) -> dict[str, Any]:
        return {
            "interval_seconds": self.interval_seconds,
            "top_n": self.top_n,
            "limit": self.limit,
            "timezone_name": self.timezone_name,
            "asian_window_minutes": self.asian_window_minutes,
            "parlay_window_minutes": self.parlay_window_minutes,
            "learning_observation_limit": self.learning_observation_limit,
            "analysis_candidate_limit": self.analysis_candidate_limit,
            "analysis_concurrency": self.analysis_concurrency,
            "shadow_prediction_limit": self.shadow_prediction_limit,
            "include_market_snapshot_sync": self.include_market_snapshot_sync,
            "market_snapshot_window_minutes": self.market_snapshot_window_minutes,
            "market_snapshot_limit": self.market_snapshot_limit,
            "market_snapshot_concurrency": self.market_snapshot_concurrency,
            "market_snapshot_require_quality_gate": self.market_snapshot_require_quality_gate,
            "include_snapshot_reanalysis": self.include_snapshot_reanalysis,
            "snapshot_reanalysis_limit": self.snapshot_reanalysis_limit,
            "snapshot_reanalysis_concurrency": self.snapshot_reanalysis_concurrency,
            "enforce_settlement_coverage": self.enforce_settlement_coverage,
            "league_allowlist": league_allowlist,
        }


def load_server_settings() -> ServerSettings:
    return ServerSettings()


def load_auto_learning_settings() -> AutoLearningSettings:
    return AutoLearningSettings()


def _transport_from_env() -> Literal["stdio", "sse", "streamable-http"]:
    raw = env_str("FOOTBALL_DATA_MCP_TRANSPORT", "streamable-http")
    if raw == "stdio":
        return "stdio"
    if raw == "sse":
        return "sse"
    if raw == "streamable-http":
        return "streamable-http"
    raise ValueError(f"Unsupported transport: {raw}")
