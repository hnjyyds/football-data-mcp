from __future__ import annotations

import csv
import io
import os
import asyncio
import re
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any
from urllib.parse import quote

import httpx
from dateutil import parser as date_parser

from football_data_mcp.snapshot_store import MarketSnapshot


THE_ODDS_API_BASE_URL = "https://api.the-odds-api.com/v4"
SPORTMONKS_BASE_URL = "https://api.sportmonks.com/v3/football"
API_FOOTBALL_BASE_URL = "https://v3.football.api-sports.io"
FOOTBALL_DATA_ORG_BASE_URL = "https://api.football-data.org/v4"
CLUBELO_BASE_URL = "http://api.clubelo.com"
FREE_SOURCE_TIMEOUT_SECONDS = float(os.getenv("FOOTBALL_DATA_FREE_SOURCE_TIMEOUT", "2.0"))
SPORTMONKS_FIXTURE_INCLUDES = [
    "participants",
    "league",
    "lineups",
    "formations",
    "sidelined",
    "weatherReport",
    "statistics",
]
DEFAULT_THE_ODDS_API_SPORT_KEYS = [
    "soccer_epl",
    "soccer_spain_la_liga",
    "soccer_italy_serie_a",
    "soccer_germany_bundesliga",
    "soccer_france_ligue_one",
]
DEFAULT_MARKETS = ["h2h", "spreads", "totals"]


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value: Any) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _normalize_team_name(value: str) -> str:
    value = (value or "").lower()
    value = re.sub(r"\b(fc|cf|afc|sc|u23|u21|club)\b", " ", value)
    value = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _split_match_query(query: str) -> tuple[str, str]:
    parts = [
        part.strip()
        for part in re.split(r"\s+(?:vs?\.?|v)\s+|[-–—]", query or "", maxsplit=1, flags=re.IGNORECASE)
        if part.strip()
    ]
    if len(parts) >= 2:
        return parts[0], parts[1]
    return "", ""


def _team_name_score(expected: str, candidate: str) -> float:
    expected_norm = _normalize_team_name(expected)
    candidate_norm = _normalize_team_name(candidate)
    if not expected_norm or not candidate_norm:
        return 0.0
    if expected_norm == candidate_norm:
        return 1.0
    if expected_norm in candidate_norm or candidate_norm in expected_norm:
        return 0.92
    return SequenceMatcher(None, expected_norm, candidate_norm).ratio()


def _matchup_score(home_team: str, away_team: str, candidate_home: str, candidate_away: str) -> float:
    if not home_team and not away_team:
        return 0.0
    home_score = _team_name_score(home_team, candidate_home) if home_team else 0.0
    away_score = _team_name_score(away_team, candidate_away) if away_team else 0.0
    if home_team and away_team:
        direct = (home_score + away_score) / 2
        swapped = (
            _team_name_score(home_team, candidate_away)
            + _team_name_score(away_team, candidate_home)
        ) / 2
        return max(direct, swapped * 0.85)
    return max(home_score, away_score)


def _best_match_item(
    items: list[dict[str, Any]],
    *,
    home_team: str = "",
    away_team: str = "",
    get_home,
    get_away,
) -> dict[str, Any]:
    if not items:
        return {}
    if not home_team and not away_team:
        return items[0]
    scored = [
        (
            _matchup_score(home_team, away_team, str(get_home(item) or ""), str(get_away(item) or "")),
            item,
        )
        for item in items
    ]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    if scored[0][0] < 0.58:
        return {}
    return scored[0][1]


def _iso_utc(value: Any, *, fallback: datetime | None = None) -> str:
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value or "").strip()
        if not text:
            parsed = fallback or datetime.now(timezone.utc)
        else:
            parsed = date_parser.parse(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def the_odds_api_sport_keys() -> list[str]:
    configured = os.getenv("THE_ODDS_API_SPORT_KEYS", "")
    if configured.strip():
        return [item.strip() for item in configured.split(",") if item.strip()]
    return DEFAULT_THE_ODDS_API_SPORT_KEYS


def normalize_the_odds_api_event(event: dict[str, Any], *, fetched_at: datetime | None = None) -> list[MarketSnapshot]:
    fetched_at = fetched_at or datetime.now(timezone.utc)
    fetched_at_utc = _iso_utc(fetched_at)
    kickoff_utc = _iso_utc(event.get("commence_time"), fallback=fetched_at)
    home_team = str(event.get("home_team") or "")
    away_team = str(event.get("away_team") or "")
    snapshots: list[MarketSnapshot] = []
    for bookmaker in event.get("bookmakers") or []:
        bookmaker_name = str(bookmaker.get("title") or bookmaker.get("key") or "")
        source_time_utc = _iso_utc(bookmaker.get("last_update"), fallback=fetched_at)
        for market in bookmaker.get("markets") or []:
            market_type = str(market.get("key") or "")
            if market_type not in {"h2h", "spreads", "totals"}:
                continue
            for outcome in market.get("outcomes") or []:
                price = outcome.get("price")
                try:
                    decimal_odds = float(price)
                except (TypeError, ValueError):
                    continue
                if decimal_odds <= 1:
                    continue
                snapshots.append(
                    MarketSnapshot(
                        provider="the_odds_api",
                        source_key=str(event.get("sport_key") or ""),
                        event_id=str(event.get("id") or ""),
                        league=str(event.get("sport_title") or event.get("sport_key") or ""),
                        home_team=home_team,
                        away_team=away_team,
                        kickoff_utc=kickoff_utc,
                        bookmaker=bookmaker_name,
                        market_type=market_type,
                        selection=str(outcome.get("name") or ""),
                        decimal_odds=decimal_odds,
                        line=float(outcome["point"]) if outcome.get("point") is not None else None,
                        source_time_utc=source_time_utc,
                        fetched_at_utc=fetched_at_utc,
                        raw={
                            "event": {
                                "id": event.get("id"),
                                "sport_key": event.get("sport_key"),
                                "sport_title": event.get("sport_title"),
                                "commence_time": event.get("commence_time"),
                            },
                            "bookmaker": {
                                "key": bookmaker.get("key"),
                                "title": bookmaker.get("title"),
                                "last_update": bookmaker.get("last_update"),
                            },
                            "market": {
                                "key": market.get("key"),
                                "last_update": market.get("last_update"),
                            },
                            "outcome": outcome,
                        },
                    )
                )
    return snapshots


async def fetch_the_odds_api_snapshots(
    *,
    sport_keys: list[str] | None = None,
    regions: str | None = None,
    markets: list[str] | None = None,
    limit_per_sport: int | None = None,
    timeout_seconds: float = 15,
) -> dict[str, Any]:
    api_key = os.getenv("THE_ODDS_API_KEY", "").strip()
    if not api_key:
        return {
            "status": "not_configured",
            "provider": "the_odds_api",
            "required_env": "THE_ODDS_API_KEY",
            "snapshots": [],
            "message": "THE_ODDS_API_KEY is not set; keeping existing public sources active.",
        }

    sport_keys = sport_keys or the_odds_api_sport_keys()
    regions = regions or os.getenv("THE_ODDS_API_REGIONS", "uk,eu,us")
    markets = markets or DEFAULT_MARKETS
    fetched_at = datetime.now(timezone.utc)
    snapshots: list[MarketSnapshot] = []
    errors = []
    async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True) as client:
        for sport_key in sport_keys:
            try:
                response = await client.get(
                    f"{THE_ODDS_API_BASE_URL}/sports/{sport_key}/odds",
                    params={
                        "apiKey": api_key,
                        "regions": regions,
                        "markets": ",".join(markets),
                        "oddsFormat": "decimal",
                        "dateFormat": "iso",
                    },
                )
                response.raise_for_status()
                events = response.json()
                if limit_per_sport:
                    events = events[:limit_per_sport]
                for event in events:
                    snapshots.extend(normalize_the_odds_api_event(event, fetched_at=fetched_at))
            except Exception as exc:
                errors.append(
                    {
                        "sport_key": sport_key,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )

    return {
        "status": "ok" if snapshots else "empty",
        "provider": "the_odds_api",
        "sport_keys": sport_keys,
        "regions": regions,
        "markets": markets,
        "snapshot_count": len(snapshots),
        "snapshots": snapshots,
        "errors": errors,
    }


def external_provider_health(snapshot_counts: dict[str, Any] | None = None) -> dict[str, Any]:
    snapshot_counts = snapshot_counts or {}
    sportmonks_token = os.getenv("SPORTMONKS_API_TOKEN", "").strip()
    api_football_key = os.getenv("API_FOOTBALL_KEY", "").strip()
    football_data_org_token = os.getenv("FOOTBALL_DATA_ORG_TOKEN", "").strip()
    the_odds_api_key = os.getenv("THE_ODDS_API_KEY", "").strip()
    return {
        "the_odds_api": {
            "configured": bool(the_odds_api_key),
            "status": "configured" if the_odds_api_key else "not_configured",
            "role": "multi-bookmaker h2h/spreads/totals odds snapshots",
            "snapshot_count": (snapshot_counts.get("the_odds_api") or {}).get("snapshot_count", 0),
            "latest_fetched_at_utc": (snapshot_counts.get("the_odds_api") or {}).get("latest_fetched_at_utc"),
            "required_env": "THE_ODDS_API_KEY",
        },
        "sportmonks": {
            "configured": bool(sportmonks_token),
            "status": "configured_pending_adapter" if sportmonks_token else "not_configured",
            "role": "fixtures, lineups, formations, sidelined/injuries, weather, statistics context",
            "required_env": "SPORTMONKS_API_TOKEN",
            "base_url": SPORTMONKS_BASE_URL,
        },
        "api_football": {
            "configured": bool(api_football_key),
            "status": "configured" if api_football_key else "not_configured",
            "role": "backup fixtures, standings, lineups, injuries, odds, statistics context",
            "required_env": "API_FOOTBALL_KEY",
            "base_url": API_FOOTBALL_BASE_URL,
        },
        "football_data_org": {
            "configured": bool(football_data_org_token),
            "status": "configured" if football_data_org_token else "not_configured",
            "role": "backup fixtures, match status, competition, and score context",
            "required_env": "FOOTBALL_DATA_ORG_TOKEN",
            "base_url": FOOTBALL_DATA_ORG_BASE_URL,
        },
        "clubelo": {
            "configured": True,
            "status": "free_source_available",
            "role": "free club-strength Elo rating context",
            "base_url": CLUBELO_BASE_URL,
            "timeout_seconds": FREE_SOURCE_TIMEOUT_SECONDS,
        },
    }


def _score_available(*values: Any) -> bool:
    return all(value is not None for value in values)


def normalize_api_football_fixture_context(payload: dict[str, Any], home_team: str = "", away_team: str = "") -> dict[str, Any]:
    fixtures = payload.get("response") or []
    item = _best_match_item(
        fixtures,
        home_team=home_team,
        away_team=away_team,
        get_home=lambda row: (((row.get("teams") or {}).get("home") or {}).get("name")),
        get_away=lambda row: (((row.get("teams") or {}).get("away") or {}).get("name")),
    )
    if not item:
        return {
            "available": False,
            "provider": "api_football",
            "reason": "fixture_not_found",
            "coverage": {"fixture": False, "score": False},
        }

    fixture = item.get("fixture") or {}
    league = item.get("league") or {}
    teams = item.get("teams") or {}
    home = teams.get("home") or {}
    away = teams.get("away") or {}
    goals = item.get("goals") or {}
    fulltime = ((item.get("score") or {}).get("fulltime") or {})
    score_home = goals.get("home") if goals.get("home") is not None else fulltime.get("home")
    score_away = goals.get("away") if goals.get("away") is not None else fulltime.get("away")
    return {
        "available": True,
        "provider": "api_football",
        "fixture": {
            "id": fixture.get("id"),
            "starting_at": fixture.get("date") or "",
            "timezone": fixture.get("timezone") or "",
            "status_short": (fixture.get("status") or {}).get("short"),
            "status_long": (fixture.get("status") or {}).get("long"),
            "venue": fixture.get("venue") or {},
            "league": league.get("name") or "",
            "league_country": league.get("country") or "",
            "season": league.get("season"),
            "home_team": home.get("name") or home_team,
            "away_team": away.get("name") or away_team,
        },
        "score": {
            "home": score_home,
            "away": score_away,
            "fulltime": fulltime,
        },
        "coverage": {
            "fixture": True,
            "league": bool(league),
            "teams": bool(home or away),
            "score": _score_available(score_home, score_away),
        },
        "raw_counts": {
            "fixtures": len(fixtures),
        },
    }


async def fetch_api_football_fixture_context(
    query: str,
    *,
    home_team: str = "",
    away_team: str = "",
    date: str | None = None,
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    api_key = os.getenv("API_FOOTBALL_KEY", "").strip()
    if not api_key:
        return {
            "status": "not_configured",
            "provider": "api_football",
            "required_env": "API_FOOTBALL_KEY",
            "context": normalize_api_football_fixture_context({}),
            "message": "API_FOOTBALL_KEY is not set; context layer will use existing public sources only.",
        }

    parsed_home, parsed_away = _split_match_query(query)
    home_team = home_team or parsed_home
    away_team = away_team or parsed_away
    fixture_date = date or datetime.now(timezone.utc).date().isoformat()
    timeout_seconds = FREE_SOURCE_TIMEOUT_SECONDS if timeout_seconds is None else timeout_seconds
    async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True) as client:
        try:
            response = await client.get(
                f"{API_FOOTBALL_BASE_URL}/fixtures",
                params={"date": fixture_date},
                headers={"x-apisports-key": api_key},
            )
            response.raise_for_status()
            payload = response.json()
            context = normalize_api_football_fixture_context(payload, home_team, away_team)
            return {
                "status": "ok" if context.get("available") else "not_found",
                "provider": "api_football",
                "query": query,
                "date": fixture_date,
                "context": context,
            }
        except Exception as exc:
            return {
                "status": "error",
                "provider": "api_football",
                "query": query,
                "error": f"{type(exc).__name__}: {exc}",
                "context": normalize_api_football_fixture_context({}),
            }


def normalize_football_data_org_match_context(payload: dict[str, Any], home_team: str = "", away_team: str = "") -> dict[str, Any]:
    matches = payload.get("matches") or []
    match = _best_match_item(
        matches,
        home_team=home_team,
        away_team=away_team,
        get_home=lambda row: ((row.get("homeTeam") or {}).get("name") or (row.get("homeTeam") or {}).get("shortName")),
        get_away=lambda row: ((row.get("awayTeam") or {}).get("name") or (row.get("awayTeam") or {}).get("shortName")),
    )
    if not match:
        return {
            "available": False,
            "provider": "football_data_org",
            "reason": "match_not_found",
            "coverage": {"fixture": False, "score": False},
        }

    competition = match.get("competition") or {}
    home = match.get("homeTeam") or {}
    away = match.get("awayTeam") or {}
    fulltime = ((match.get("score") or {}).get("fullTime") or {})
    score_home = fulltime.get("home")
    score_away = fulltime.get("away")
    return {
        "available": True,
        "provider": "football_data_org",
        "fixture": {
            "id": match.get("id"),
            "starting_at": match.get("utcDate") or "",
            "status": match.get("status") or "",
            "competition": competition.get("name") or "",
            "competition_code": competition.get("code") or "",
            "home_team": home.get("name") or home.get("shortName") or home_team,
            "away_team": away.get("name") or away.get("shortName") or away_team,
        },
        "score": {
            "home": score_home,
            "away": score_away,
            "winner": ((match.get("score") or {}).get("winner")),
        },
        "coverage": {
            "fixture": True,
            "competition": bool(competition),
            "teams": bool(home or away),
            "score": _score_available(score_home, score_away),
        },
        "raw_counts": {
            "matches": len(matches),
        },
    }


async def fetch_football_data_org_match_context(
    query: str,
    *,
    home_team: str = "",
    away_team: str = "",
    date_from: str | None = None,
    date_to: str | None = None,
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    token = os.getenv("FOOTBALL_DATA_ORG_TOKEN", "").strip()
    if not token:
        return {
            "status": "not_configured",
            "provider": "football_data_org",
            "required_env": "FOOTBALL_DATA_ORG_TOKEN",
            "context": normalize_football_data_org_match_context({}),
            "message": "FOOTBALL_DATA_ORG_TOKEN is not set; context layer will use existing public sources only.",
        }

    parsed_home, parsed_away = _split_match_query(query)
    home_team = home_team or parsed_home
    away_team = away_team or parsed_away
    start_date = date_from or datetime.now(timezone.utc).date().isoformat()
    end_date = date_to or start_date
    timeout_seconds = FREE_SOURCE_TIMEOUT_SECONDS if timeout_seconds is None else timeout_seconds
    async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True) as client:
        try:
            response = await client.get(
                f"{FOOTBALL_DATA_ORG_BASE_URL}/matches",
                params={"dateFrom": start_date, "dateTo": end_date},
                headers={"X-Auth-Token": token},
            )
            response.raise_for_status()
            payload = response.json()
            context = normalize_football_data_org_match_context(payload, home_team, away_team)
            return {
                "status": "ok" if context.get("available") else "not_found",
                "provider": "football_data_org",
                "query": query,
                "date_from": start_date,
                "date_to": end_date,
                "context": context,
            }
        except Exception as exc:
            return {
                "status": "error",
                "provider": "football_data_org",
                "query": query,
                "error": f"{type(exc).__name__}: {exc}",
                "context": normalize_football_data_org_match_context({}),
            }


def _participant_name_by_location(fixture: dict[str, Any], location: str) -> str:
    for participant in fixture.get("participants") or []:
        meta = participant.get("meta") or {}
        if str(meta.get("location") or "").lower() == location:
            return str(participant.get("name") or "")
    return ""


def normalize_sportmonks_fixture_context(payload: dict[str, Any]) -> dict[str, Any]:
    fixtures = payload.get("data") or []
    fixture = fixtures[0] if fixtures else {}
    if not fixture:
        return {
            "available": False,
            "provider": "sportmonks",
            "reason": "fixture_not_found",
            "coverage": {},
            "raw_counts": {},
        }

    weather = fixture.get("weather_report") or fixture.get("weatherReport") or {}
    lineups = fixture.get("lineups") or []
    sidelined = fixture.get("sidelined") or []
    statistics = fixture.get("statistics") or []
    formations = fixture.get("formations") or []
    participants = fixture.get("participants") or []
    return {
        "available": True,
        "provider": "sportmonks",
        "fixture": {
            "id": fixture.get("id"),
            "name": fixture.get("name") or "",
            "starting_at": fixture.get("starting_at") or "",
            "league": (fixture.get("league") or {}).get("name") or "",
            "home_team": _participant_name_by_location(fixture, "home"),
            "away_team": _participant_name_by_location(fixture, "away"),
        },
        "coverage": {
            "participants": bool(participants),
            "league": bool(fixture.get("league")),
            "lineups": bool(lineups),
            "formations": bool(formations),
            "sidelined": bool(sidelined),
            "weather": bool(weather),
            "statistics": bool(statistics),
        },
        "raw_counts": {
            "participants": len(participants),
            "lineups": len(lineups),
            "formations": len(formations),
            "sidelined": len(sidelined),
            "statistics": len(statistics),
        },
        "lineups": lineups,
        "formations": formations,
        "sidelined": sidelined,
        "weather_report": weather,
        "statistics": statistics,
        "agent_contract": {
            "lineup_rule": "Use lineups only when coverage.lineups is true; otherwise say Sportmonks lineup data is unavailable.",
            "injury_rule": "Use sidelined only when coverage.sidelined is true; do not infer injuries from missing data.",
            "weather_rule": "Use weather_report only when coverage.weather is true.",
        },
    }


async def fetch_sportmonks_fixture_context(
    query: str,
    *,
    timeout_seconds: float = 15,
) -> dict[str, Any]:
    token = os.getenv("SPORTMONKS_API_TOKEN", "").strip()
    if not token:
        return {
            "status": "not_configured",
            "provider": "sportmonks",
            "required_env": "SPORTMONKS_API_TOKEN",
            "context": normalize_sportmonks_fixture_context({}),
            "message": "SPORTMONKS_API_TOKEN is not set; context layer will use existing public sources only.",
        }

    async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True) as client:
        try:
            response = await client.get(
                f"{SPORTMONKS_BASE_URL}/fixtures/search/{query}",
                params={
                    "api_token": token,
                    "include": ";".join(SPORTMONKS_FIXTURE_INCLUDES),
                },
            )
            response.raise_for_status()
            payload = response.json()
            context = normalize_sportmonks_fixture_context(payload)
            return {
                "status": "ok" if context.get("available") else "not_found",
                "provider": "sportmonks",
                "query": query,
                "context": context,
            }
        except Exception as exc:
            return {
                "status": "error",
                "provider": "sportmonks",
                "query": query,
                "error": f"{type(exc).__name__}: {exc}",
                "context": normalize_sportmonks_fixture_context({}),
            }


def normalize_clubelo_rating(team: str, csv_text: str) -> dict[str, Any]:
    rows = [
        {str(key or "").strip(): str(value or "").strip() for key, value in row.items()}
        for row in csv.DictReader(io.StringIO(csv_text or ""))
        if row
    ]
    if not rows:
        return {
            "available": False,
            "provider": "clubelo",
            "team": team,
            "reason": "empty_csv",
        }

    rows.sort(key=lambda row: (row.get("To") or "", row.get("From") or ""), reverse=True)
    row = rows[0]
    return {
        "available": True,
        "provider": "clubelo",
        "team": row.get("Club") or team,
        "country": row.get("Country") or "",
        "level": _int_or_none(row.get("Level")),
        "elo": _float_or_none(row.get("Elo")),
        "rank": _int_or_none(row.get("Rank")),
        "valid_from": row.get("From") or "",
        "valid_to": row.get("To") or "",
        "source_url": f"{CLUBELO_BASE_URL}/{quote(team)}",
    }


async def fetch_clubelo_rating(team: str, *, timeout_seconds: float | None = None) -> dict[str, Any]:
    if not (team or "").strip():
        return {
            "available": False,
            "provider": "clubelo",
            "team": team,
            "reason": "team_missing",
        }
    url = f"{CLUBELO_BASE_URL}/{quote(team.strip())}"
    timeout_seconds = FREE_SOURCE_TIMEOUT_SECONDS if timeout_seconds is None else timeout_seconds
    async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True) as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            rating = normalize_clubelo_rating(team, response.text)
            return {
                **rating,
                "source_url": str(response.url),
            }
        except Exception as exc:
            return {
                "available": False,
                "provider": "clubelo",
                "team": team,
                "source_url": url,
                "reason": f"{type(exc).__name__}: {exc}",
            }


async def free_team_strength_context(home_team: str, away_team: str) -> dict[str, Any]:
    home, away = await asyncio.gather(
        fetch_clubelo_rating(home_team),
        fetch_clubelo_rating(away_team),
    )
    home_elo = _float_or_none(home.get("elo"))
    away_elo = _float_or_none(away.get("elo"))
    diff = round(home_elo - away_elo, 3) if home_elo is not None and away_elo is not None else None
    status = "ok" if home.get("available") or away.get("available") else "unavailable"
    return {
        "status": status,
        "provider": "clubelo",
        "home": home,
        "away": away,
        "elo_diff_home_minus_away": diff,
        "coverage": {
            "home_available": bool(home.get("available")),
            "away_available": bool(away.get("available")),
            "both_available": bool(home.get("available") and away.get("available")),
        },
        "agent_contract": {
            "usage": "Use ClubElo only as a free team-strength context signal; do not convert Elo difference into a standalone betting probability unless MCP model fields already do so.",
            "missing_rule": "If either team is unavailable, state the missing ClubElo side instead of inventing a strength gap.",
        },
    }
