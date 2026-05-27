"""
Data sources registry: enumerate free/paid sources, probe their health, and
implement graceful degradation when a source fails.

Free sources documented:
- football-data.co.uk: CSV with odds (primary, used by sources.py)
- football-data.org: REST API with fixtures/standings (free tier 10 req/min)
- The Odds API: REST API with odds snapshots (free tier 500 req/month)
- Sportmonks: REST API with odds, lineups, stats (paid, optional)
- Leisu (live.leisu.com): Chinese mobile API + HTML (gated)
- Dongqiudi (dongqiudi.com): Chinese fixture schedule + lineups
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

import httpx

logger = logging.getLogger(__name__)


@dataclass
class SourceConfig:
    """Configuration for a single data source."""
    name: str                                # short identifier
    label: str                               # human-readable label
    category: str                            # "fixture" | "odds" | "lineup" | "schedule"
    cost_tier: str                           # "free" | "freemium" | "paid"
    required_env: list[str] = field(default_factory=list)  # env vars that must be set
    probe_url: str | None = None             # URL to ping for health check
    probe_headers: dict[str, str] = field(default_factory=dict)
    rate_limit_per_minute: int | None = None
    rate_limit_per_day: int | None = None
    timeout_seconds: float = 8.0
    notes: str = ""


REGISTRY: list[SourceConfig] = [
    SourceConfig(
        name="football_data_csv",
        label="Football-Data.co.uk",
        category="odds",
        cost_tier="free",
        probe_url="https://www.football-data.co.uk/mmz4281/2425/E0.csv",
        rate_limit_per_minute=60,
        notes="Primary numeric odds source (1X2, AH, O/U) across 18 European leagues.",
    ),
    SourceConfig(
        name="football_data_org",
        label="football-data.org",
        category="fixture",
        cost_tier="free",
        required_env=["FOOTBALL_DATA_ORG_TOKEN"],
        probe_url="https://api.football-data.org/v4/competitions",
        rate_limit_per_minute=10,
        notes="Fixtures, standings, lineups. Free tier 10 req/min, 10 leagues.",
    ),
    SourceConfig(
        name="the_odds_api",
        label="The Odds API",
        category="odds",
        cost_tier="freemium",
        required_env=["THE_ODDS_API_KEY"],
        probe_url="https://api.the-odds-api.com/v4/sports?apiKey={THE_ODDS_API_KEY}",
        rate_limit_per_day=500,
        notes="Multi-bookmaker odds snapshots. Free tier 500 req/month.",
    ),
    SourceConfig(
        name="sportmonks",
        label="Sportmonks",
        category="odds",
        cost_tier="paid",
        required_env=["SPORTMONKS_API_TOKEN"],
        probe_url="https://api.sportmonks.com/v3/football/fixtures?api_token={SPORTMONKS_API_TOKEN}",
        notes="Premium tier provides lineups, xG, odds. Optional.",
    ),
    SourceConfig(
        name="leisu_mobile",
        label="Leisu Mobile API",
        category="odds",
        cost_tier="free",
        required_env=[],
        probe_url="https://m.leisu.com/api/match-list",
        notes="Chinese multi-bookmaker odds. WAF-gated, mobile API path.",
    ),
    SourceConfig(
        name="dongqiudi",
        label="Dongqiudi",
        category="schedule",
        cost_tier="free",
        probe_url="https://www.dongqiudi.com/match/schedule",
        notes="Chinese fixture schedule + lineups. Used for context corroboration.",
    ),
    SourceConfig(
        name="oddsportal",
        label="OddsPortal",
        category="odds",
        cost_tier="free",
        probe_url="https://www.oddsportal.com/soccer/",
        notes="Public corroboration of pre-match odds (HTML scrape).",
    ),
]


def configured_sources() -> list[SourceConfig]:
    """Return only the sources whose required env vars are set."""
    return [s for s in REGISTRY if all(os.getenv(env) for env in s.required_env)]


def _interpolate_url(url: str) -> str:
    """Replace {ENV_VAR} placeholders with actual env values."""
    result = url
    while "{" in result and "}" in result:
        start = result.index("{")
        end = result.index("}", start)
        key = result[start + 1 : end]
        result = result[:start] + (os.getenv(key) or "") + result[end + 1 :]
    return result


async def probe_source(client: httpx.AsyncClient, source: SourceConfig) -> dict[str, Any]:
    """Ping a single source and return health summary."""
    if not source.probe_url:
        return {
            "name": source.name,
            "label": source.label,
            "status": "no_probe",
            "available": False,
            "reason": "no probe URL configured",
        }
    if source.required_env and any(not os.getenv(env) for env in source.required_env):
        return {
            "name": source.name,
            "label": source.label,
            "status": "not_configured",
            "available": False,
            "reason": f"missing env: {[e for e in source.required_env if not os.getenv(e)]}",
            "cost_tier": source.cost_tier,
        }

    url = _interpolate_url(source.probe_url)
    t0 = time.time()
    try:
        response = await client.get(
            url,
            headers=source.probe_headers,
            timeout=source.timeout_seconds,
            follow_redirects=True,
        )
        latency_ms = round((time.time() - t0) * 1000)
        if response.status_code < 400:
            return {
                "name": source.name,
                "label": source.label,
                "status": "ok",
                "available": True,
                "http_status": response.status_code,
                "latency_ms": latency_ms,
                "category": source.category,
                "cost_tier": source.cost_tier,
            }
        return {
            "name": source.name,
            "label": source.label,
            "status": "degraded",
            "available": False,
            "http_status": response.status_code,
            "latency_ms": latency_ms,
            "reason": f"HTTP {response.status_code}",
            "category": source.category,
            "cost_tier": source.cost_tier,
        }
    except (httpx.TimeoutException, asyncio.TimeoutError) as exc:
        return {
            "name": source.name,
            "label": source.label,
            "status": "timeout",
            "available": False,
            "latency_ms": round((time.time() - t0) * 1000),
            "reason": str(exc) or "timeout",
            "category": source.category,
            "cost_tier": source.cost_tier,
        }
    except Exception as exc:
        return {
            "name": source.name,
            "label": source.label,
            "status": "error",
            "available": False,
            "latency_ms": round((time.time() - t0) * 1000),
            "reason": str(exc),
            "category": source.category,
            "cost_tier": source.cost_tier,
        }


async def probe_all_sources(timeout: float = 10.0) -> dict[str, Any]:
    """Probe all registered sources concurrently."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        results = await asyncio.gather(
            *(probe_source(client, s) for s in REGISTRY),
            return_exceptions=False,
        )
    available_count = sum(1 for r in results if r.get("available"))
    return {
        "status": "ok",
        "total_sources": len(REGISTRY),
        "available_count": available_count,
        "configured_count": len(configured_sources()),
        "sources": results,
        "by_category": _group_by_category(results),
        "probed_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def _group_by_category(results: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Group results by data category for the dashboard."""
    by_cat: dict[str, list[dict[str, Any]]] = {}
    for r in results:
        cat = r.get("category", "unknown")
        by_cat.setdefault(cat, []).append(r)
    return {
        cat: {
            "total": len(items),
            "available": sum(1 for it in items if it.get("available")),
            "sources": items,
        }
        for cat, items in sorted(by_cat.items())
    }


# ─── football-data.org adapter ────────────────────────────────────────────────

FOOTBALL_DATA_ORG_BASE = "https://api.football-data.org/v4"


async def fetch_football_data_org_fixtures(
    competition_code: str = "PL",
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    """
    Fetch fixtures from football-data.org free API.

    Free tier covers: PL (Premier League), BL1 (Bundesliga), SA (Serie A),
    PD (La Liga), FL1 (Ligue 1), DED (Eredivisie), PPL (Primeira), ELC,
    CL (Champions League), BSA (Brasileirão).
    """
    token = os.getenv("FOOTBALL_DATA_ORG_TOKEN")
    if not token:
        return {
            "status": "not_configured",
            "reason": "FOOTBALL_DATA_ORG_TOKEN env var not set",
            "fixtures": [],
        }

    params: dict[str, Any] = {}
    if date_from: params["dateFrom"] = date_from
    if date_to: params["dateTo"] = date_to

    url = f"{FOOTBALL_DATA_ORG_BASE}/competitions/{competition_code}/matches"
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(
                url,
                params=params,
                headers={"X-Auth-Token": token},
            )
            if response.status_code == 429:
                return {
                    "status": "rate_limited",
                    "reason": "free tier limit 10 req/min reached; back off",
                    "fixtures": [],
                }
            response.raise_for_status()
            data = response.json()
            return {
                "status": "ok",
                "competition": competition_code,
                "result_count": len(data.get("matches") or []),
                "fixtures": data.get("matches") or [],
                "source": "football-data.org",
            }
        except httpx.HTTPStatusError as exc:
            return {
                "status": "error",
                "reason": f"HTTP {exc.response.status_code}",
                "fixtures": [],
            }
        except Exception as exc:
            return {
                "status": "error",
                "reason": str(exc),
                "fixtures": [],
            }


# ─── Degradation strategy ─────────────────────────────────────────────────────

@dataclass
class SourceFallbackTier:
    """A priority tier for graceful degradation."""
    primary: str        # source name
    fallbacks: list[str]  # ordered list of fallback source names
    purpose: str        # what we're trying to obtain


FALLBACK_TIERS = [
    SourceFallbackTier(
        primary="football_data_csv",
        fallbacks=["football_data_org", "the_odds_api"],
        purpose="match_fixtures_and_odds",
    ),
    SourceFallbackTier(
        primary="leisu_mobile",
        fallbacks=["dongqiudi", "oddsportal"],
        purpose="chinese_market_odds",
    ),
    SourceFallbackTier(
        primary="dongqiudi",
        fallbacks=["football_data_org"],
        purpose="lineups_and_context",
    ),
]


async def fetch_with_fallback(
    tier: SourceFallbackTier,
    fetchers: dict[str, Callable[[], Awaitable[dict[str, Any]]]],
) -> dict[str, Any]:
    """
    Try the primary source; if it fails, walk fallbacks in order.
    `fetchers` maps source name to an async function returning a dict.
    The dict must contain a 'status' key — "ok" means success.
    """
    chain = [tier.primary, *tier.fallbacks]
    attempts: list[dict[str, Any]] = []
    for source_name in chain:
        fetcher = fetchers.get(source_name)
        if not fetcher:
            attempts.append({"source": source_name, "skipped": True, "reason": "no fetcher"})
            continue
        try:
            result = await fetcher()
            attempts.append({
                "source": source_name,
                "status": result.get("status"),
                "succeeded": result.get("status") == "ok",
            })
            if result.get("status") == "ok":
                return {
                    "status": "ok",
                    "source_used": source_name,
                    "data": result,
                    "attempts": attempts,
                    "purpose": tier.purpose,
                }
        except Exception as exc:
            attempts.append({"source": source_name, "succeeded": False, "error": str(exc)})
            logger.warning("Source %s failed for %s: %s", source_name, tier.purpose, exc)

    return {
        "status": "all_sources_failed",
        "purpose": tier.purpose,
        "attempts": attempts,
    }
