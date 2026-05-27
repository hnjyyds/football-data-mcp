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

# Free-tier competitions (verified 2026-05-27 with token: 13 competitions across
# Brazil, England, Spain, France, Germany, Italy, Netherlands, Portugal, etc.)
# Codes: BSA, ELC, PL, PD, FL1, BL1, SA, DED, PPL, CL, EC, CLI, WC (subject to season)
FOOTBALL_DATA_ORG_FREE_COMPETITIONS = ("PL", "BL1", "SA", "PD", "FL1", "DED", "PPL", "ELC", "CL", "BSA")

# Cache to respect 10 req/min limit (60s TTL for matches, 5min for competitions)
_FDO_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_FDO_MATCH_TTL = 90.0       # 90s for live match data
_FDO_COMP_TTL = 3600.0      # 1h for competition metadata


def _fdo_cache_get(key: str, ttl: float) -> dict[str, Any] | None:
    entry = _FDO_CACHE.get(key)
    if not entry:
        return None
    ts, payload = entry
    if time.time() - ts > ttl:
        return None
    return payload


def _fdo_cache_put(key: str, payload: dict[str, Any]) -> None:
    _FDO_CACHE[key] = (time.time(), payload)


def _fdo_token() -> str | None:
    return os.getenv("FOOTBALL_DATA_ORG_TOKEN")


def _normalize_fdo_match(raw: dict[str, Any]) -> dict[str, Any]:
    """Transform football-data.org match payload into a standard fixture dict."""
    home = raw.get("homeTeam") or {}
    away = raw.get("awayTeam") or {}
    competition = raw.get("competition") or {}
    score = (raw.get("score") or {}).get("fullTime") or {}
    return {
        "source": "football-data.org",
        "match_id": f"fdo:{raw.get('id')}",
        "fdo_id": raw.get("id"),
        "kickoff_utc": raw.get("utcDate"),
        "status": raw.get("status"),
        "matchday": raw.get("matchday"),
        "stage": raw.get("stage"),
        "competition_code": competition.get("code"),
        "competition_name": competition.get("name"),
        "league": competition.get("name"),
        "league_code": competition.get("code"),
        "home_team": home.get("name") or home.get("shortName"),
        "home_team_short": home.get("shortName"),
        "home_team_tla": home.get("tla"),
        "home_team_logo_url": home.get("crest"),
        "home_team_id": home.get("id"),
        "away_team": away.get("name") or away.get("shortName"),
        "away_team_short": away.get("shortName"),
        "away_team_tla": away.get("tla"),
        "away_team_logo_url": away.get("crest"),
        "away_team_id": away.get("id"),
        "home_score": score.get("home"),
        "away_score": score.get("away"),
        "referees": [r.get("name") for r in (raw.get("referees") or []) if r.get("name")],
        "last_updated": raw.get("lastUpdated"),
    }


async def fetch_football_data_org_fixtures(
    competition_code: str = "PL",
    date_from: str | None = None,
    date_to: str | None = None,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Fetch fixtures from football-data.org free API (one competition)."""
    token = _fdo_token()
    if not token:
        return {
            "status": "not_configured",
            "reason": "FOOTBALL_DATA_ORG_TOKEN env var not set",
            "fixtures": [],
        }

    cache_key = f"fixtures:{competition_code}:{date_from or ''}:{date_to or ''}"
    cached = _fdo_cache_get(cache_key, _FDO_MATCH_TTL)
    if cached is not None:
        return {**cached, "from_cache": True}

    params: dict[str, Any] = {}
    if date_from: params["dateFrom"] = date_from
    if date_to: params["dateTo"] = date_to
    url = f"{FOOTBALL_DATA_ORG_BASE}/competitions/{competition_code}/matches"

    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient(timeout=10.0)
    try:
        response = await client.get(url, params=params, headers={"X-Auth-Token": token})
        if response.status_code == 429:
            payload = {
                "status": "rate_limited",
                "reason": "free tier limit 10 req/min reached; back off",
                "fixtures": [],
                "competition": competition_code,
            }
            return payload
        response.raise_for_status()
        data = response.json()
        raw_matches = data.get("matches") or []
        fixtures = [_normalize_fdo_match(m) for m in raw_matches]
        result = {
            "status": "ok",
            "competition": competition_code,
            "competition_name": (data.get("competition") or {}).get("name"),
            "result_count": len(fixtures),
            "fixtures": fixtures,
            "source": "football-data.org",
            "from_cache": False,
        }
        _fdo_cache_put(cache_key, result)
        return result
    except httpx.HTTPStatusError as exc:
        return {
            "status": "error",
            "reason": f"HTTP {exc.response.status_code}",
            "fixtures": [],
            "competition": competition_code,
        }
    except Exception as exc:
        return {
            "status": "error",
            "reason": str(exc),
            "fixtures": [],
            "competition": competition_code,
        }
    finally:
        if owns_client and client:
            await client.aclose()


async def fetch_all_upcoming_matches(
    *,
    date_from: str | None = None,
    date_to: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """
    Fetch upcoming matches across all available competitions in a single batched call.

    This uses the /matches endpoint (rather than per-competition) which is cheaper:
    1 request vs N requests. Free tier covers the same competitions automatically.
    """
    token = _fdo_token()
    if not token:
        return {"status": "not_configured", "fixtures": [], "competitions_covered": []}

    cache_key = f"all_matches:{date_from or ''}:{date_to or ''}"
    cached = _fdo_cache_get(cache_key, _FDO_MATCH_TTL)
    if cached is not None:
        return {**cached, "from_cache": True}

    params: dict[str, Any] = {}
    if date_from: params["dateFrom"] = date_from
    if date_to: params["dateTo"] = date_to
    url = f"{FOOTBALL_DATA_ORG_BASE}/matches"

    owns_client = client is None
    if owns_client:
        client = httpx.AsyncClient(timeout=10.0)
    try:
        response = await client.get(url, params=params, headers={"X-Auth-Token": token})
        if response.status_code == 429:
            return {"status": "rate_limited", "fixtures": [], "competitions_covered": []}
        response.raise_for_status()
        data = response.json()
        raw_matches = data.get("matches") or []
        fixtures = [_normalize_fdo_match(m) for m in raw_matches]
        result_set = data.get("resultSet") or {}
        result = {
            "status": "ok",
            "result_count": len(fixtures),
            "fixtures": fixtures,
            "competitions_covered": (result_set.get("competitions") or "").split(",") if result_set.get("competitions") else [],
            "played_count": result_set.get("played"),
            "date_range": [result_set.get("first"), result_set.get("last")],
            "source": "football-data.org",
            "from_cache": False,
        }
        _fdo_cache_put(cache_key, result)
        return result
    except Exception as exc:
        return {
            "status": "error",
            "reason": str(exc),
            "fixtures": [],
            "competitions_covered": [],
        }
    finally:
        if owns_client and client:
            await client.aclose()


async def fetch_competitions() -> dict[str, Any]:
    """List all competitions the current API key has access to (cached 1h)."""
    token = _fdo_token()
    if not token:
        return {"status": "not_configured", "competitions": []}

    cached = _fdo_cache_get("competitions", _FDO_COMP_TTL)
    if cached is not None:
        return {**cached, "from_cache": True}

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(
                f"{FOOTBALL_DATA_ORG_BASE}/competitions",
                headers={"X-Auth-Token": token},
            )
            response.raise_for_status()
            data = response.json()
            comps = [
                {
                    "code": c.get("code"),
                    "name": c.get("name"),
                    "area": (c.get("area") or {}).get("name"),
                    "type": c.get("type"),
                    "plan": c.get("plan"),
                    "current_season": (c.get("currentSeason") or {}).get("currentMatchday"),
                    "emblem": c.get("emblem"),
                }
                for c in data.get("competitions") or []
            ]
            result = {
                "status": "ok",
                "count": len(comps),
                "competitions": comps,
                "from_cache": False,
            }
            _fdo_cache_put("competitions", result)
            return result
        except Exception as exc:
            return {"status": "error", "reason": str(exc), "competitions": []}


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
