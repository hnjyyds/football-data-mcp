from __future__ import annotations

import base64
import gzip
import html
import json
import os
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from typing import Any
from urllib.parse import unquote, urljoin

import httpx
from cryptography.hazmat.primitives import hashes, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from dateutil import parser as date_parser

from football_data_mcp.snapshot_store import MarketSnapshot


ODDSPORTAL_BASE_URL = "https://www.oddsportal.com"
ODDSPORTAL_RESPONSE_PASSWORD = os.getenv(
    "FOOTBALL_DATA_ODDSPORTAL_RESPONSE_PASSWORD",
    "J*8sQ!p$7aD_fR2yW@gHn*3bVp#sAdLd_k",
)
ODDSPORTAL_RESPONSE_SALT = os.getenv(
    "FOOTBALL_DATA_ODDSPORTAL_RESPONSE_SALT",
    "5b9a8f2c3e6d1a4b7c8e9d0f1a2b3c4d",
)
ODDSPORTAL_PROVIDER = "oddsportal_scraper"
ODDSPORTAL_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8,*/*;q=0.7",
}

MARKET_TYPE_BY_BETTING_TYPE = {
    1: "h2h",
    2: "over_under",
    5: "asian_handicap",
}

SCOPE_NAME_BY_ID = {
    1: "ft_including_ot",
    2: "full_time",
    3: "first_half",
    4: "second_half",
}

ODDSPORTAL_DISCOVERY_PATH_BY_LEAGUE = {
    # Top European leagues
    "england premier league": "/football/england/premier-league/",
    "premier league": "/football/england/premier-league/",
    "e0": "/football/england/premier-league/",
    "england championship": "/football/england/championship/",
    "championship": "/football/england/championship/",
    "e1": "/football/england/championship/",
    "spain la liga": "/football/spain/laliga/",
    "la liga": "/football/spain/laliga/",
    "laliga": "/football/spain/laliga/",
    "sp1": "/football/spain/laliga/",
    "germany bundesliga": "/football/germany/bundesliga/",
    "bundesliga": "/football/germany/bundesliga/",
    "d1": "/football/germany/bundesliga/",
    "italy serie a": "/football/italy/serie-a/",
    "serie a": "/football/italy/serie-a/",
    "i1": "/football/italy/serie-a/",
    "france ligue 1": "/football/france/ligue-1/",
    "ligue 1": "/football/france/ligue-1/",
    "f1": "/football/france/ligue-1/",
    "netherlands eredivisie": "/football/netherlands/eredivisie/",
    "eredivisie": "/football/netherlands/eredivisie/",
    "n1": "/football/netherlands/eredivisie/",
    "portugal primeira liga": "/football/portugal/liga-portugal/",
    "primeira liga": "/football/portugal/liga-portugal/",
    "p1": "/football/portugal/liga-portugal/",
    "turkey super lig": "/football/turkey/super-lig/",
    "super lig": "/football/turkey/super-lig/",
    "t1": "/football/turkey/super-lig/",
    # International / continental
    "uefa champions league": "/football/europe/champions-league/",
    "champions league": "/football/europe/champions-league/",
    "uefa europa league": "/football/europe/europa-league/",
    "europa league": "/football/europe/europa-league/",
    "uefa europa conference league": "/football/europe/europa-conference-league/",
    "europa conference league": "/football/europe/europa-conference-league/",
    "copa libertadores": "/football/south-america/copa-libertadores/",
    "international friendly": "/football/world/friendly-international/",
    "friendly international": "/football/world/friendly-international/",
    "world friendly international": "/football/world/friendly-international/",
    "friendlies": "/football/world/friendly-international/",
    "国际友谊": "/football/world/friendly-international/",
    # Americas / Asia
    "brazil serie a": "/football/brazil/serie-a/",
    "brasileirao": "/football/brazil/serie-a/",
    "mls": "/football/usa/mls/",
    "major league soccer": "/football/usa/mls/",
    "japan j1 league": "/football/japan/j1-league/",
    "j1 league": "/football/japan/j1-league/",
    "j league": "/football/japan/j1-league/",
    "k league 1": "/football/south-korea/k-league-1/",
    "south korea k league 1": "/football/south-korea/k-league-1/",
    "china super league": "/football/china/super-league/",
    "chinese super league": "/football/china/super-league/",
}

ODDSPORTAL_TEAM_NAME_ALIASES = {
    # International fixtures often arrive from Chinese sources while OddsPortal
    # lists national teams in English; normalize common country/team names here.
    "比利时": "Belgium",
    "格鲁吉亚": "Georgia",
    "克罗地亚": "Croatia",
    "罗马尼亚": "Romania",
    "马达加斯加": "Madagascar",
    "摩洛哥": "Morocco",
    "吉尔吉斯斯坦": "Kyrgyzstan",
    "肯尼亚": "Kenya",
    "菲律宾": "Philippines",
    "关岛": "Guam",
    "海地": "Haiti",
    "新西兰": "New Zealand",
    "威尔士": "Wales",
    "加纳": "Ghana",
    "中国女足": "China W",
    "俄罗斯女足": "Russia W",
    "坦桑尼亚女足": "Tanzania W",
    "马拉维女足": "Malawi W",
    "印度尼西亚女足": "Indonesia W",
    "新加坡女足": "Singapore W",
    "缅甸女足": "Myanmar W",
    "乌兹别克斯坦女足": "Uzbekistan W",
}


@dataclass(frozen=True)
class OddsPortalEventContext:
    event_id: str
    version_id: str
    sport_id: str
    event_url: str
    xhash: str
    xhashf: str
    league: str
    home_team: str
    away_team: str
    kickoff_utc: str


def decrypt_oddsportal_response(
    encrypted_text: str,
    *,
    password: str = ODDSPORTAL_RESPONSE_PASSWORD,
    salt: str = ODDSPORTAL_RESPONSE_SALT,
) -> str:
    """Decode OddsPortal's encrypted AJAX envelope into plaintext JSON.

    OddsPortal wraps the response as base64("ciphertextBase64:ivHex"). The
    browser derives an AES-CBC key through PBKDF2/SHA256 and sometimes gzips
    the decrypted payload. Keeping this in one function makes the crawler easy
    to disable or replace if the upstream contract changes.
    """
    decoded = base64.b64decode(encrypted_text.strip()).decode("utf-8")
    ciphertext_base64, iv_hex = decoded.split(":", 1)
    iv = bytes.fromhex(iv_hex)
    key = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt.encode("utf-8"),
        iterations=1000,
    ).derive(password.encode("utf-8"))
    decryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    padded = decryptor.update(base64.b64decode(ciphertext_base64)) + decryptor.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    raw = unpadder.update(padded) + unpadder.finalize()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return raw.decode("utf-8")


def oddsportal_match_event_url(
    event_context: OddsPortalEventContext,
    *,
    betting_type_id: int,
    scope_id: int,
) -> str:
    path = (
        f"/match-event/{event_context.version_id}-{event_context.sport_id}-{event_context.event_id}-"
        f"{int(betting_type_id)}-{int(scope_id)}-{event_context.xhashf}.dat"
    )
    return urljoin(ODDSPORTAL_BASE_URL, path)


def extract_oddsportal_event_context(page_html: str, *, event_url: str = "") -> OddsPortalEventContext | None:
    match = re.search(r"<Event\s+:data=\"([^\"]+)\"", page_html)
    if not match:
        return None
    payload = json.loads(html.unescape(match.group(1)))
    event_data = _as_dict(payload.get("eventData"))
    event_body = _as_dict(payload.get("eventBody"))
    return OddsPortalEventContext(
        event_id=str(payload.get("h2hEncodedEventId") or event_data.get("id") or ""),
        version_id=str(event_data.get("versionId") or "1"),
        sport_id=str(event_data.get("sportId") or "1"),
        event_url=event_url,
        xhash=unquote(str(event_data.get("xhash") or "")),
        xhashf=unquote(str(event_data.get("xhashf") or "")),
        league=str(event_data.get("tournamentName") or ""),
        home_team=_participant_name(event_data.get("home")) or str(event_data.get("homeName") or ""),
        away_team=_participant_name(event_data.get("away")) or str(event_data.get("awayName") or ""),
        kickoff_utc=_iso_utc(event_body.get("startDate") or event_data.get("startDate")),
    )


def extract_oddsportal_next_match_events(page_html: str) -> list[dict[str, Any]]:
    match = re.search(r"<next-matches[^>]*:comp-data=\"([^\"]+)\"", page_html)
    if not match:
        return []
    payload = json.loads(html.unescape(match.group(1)))
    rows = _as_dict(payload.get("d")).get("rows") or []
    events = []
    for row in rows:
        item = _as_dict(row)
        encoded_event_id = str(item.get("encodeEventId") or "")
        if not encoded_event_id:
            continue
        events.append(
            {
                "event_id": encoded_event_id,
                "numeric_event_id": item.get("id"),
                "name": item.get("name"),
                "home_team": item.get("home-name") or item.get("homeName") or "",
                "away_team": item.get("away-name") or item.get("awayName") or "",
                "league": item.get("tournament-name") or "",
                "event_url": urljoin(ODDSPORTAL_BASE_URL, str(item.get("url") or "")),
                "kickoff_utc": _iso_utc(item.get("date-start-timestamp")),
            }
        )
    return events


def match_oddsportal_events_to_targets(
    events: list[dict[str, Any]],
    targets: list[dict[str, Any]],
    *,
    limit: int = 20,
    min_score: float = 0.82,
) -> list[dict[str, Any]]:
    """Match OddsPortal listing events to local prediction targets.

    The target list comes from the local paper-learning ledger. We prioritize
    team-pair similarity, use league and kickoff as secondary guardrails, and
    dedupe by OddsPortal event URL so one upstream match is queued once.
    """
    bounded_limit = max(1, min(int(limit or 20), 100))
    matches: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for target in targets:
        scored: list[tuple[float, dict[str, Any], str]] = []
        for event in events:
            event_url = str(event.get("event_url") or "").strip()
            if not event_url or event_url in seen_urls:
                continue
            score, reason = _oddsportal_event_target_score(event, target)
            if score >= min_score:
                scored.append((score, event, reason))
        if not scored:
            continue
        scored.sort(key=lambda item: item[0], reverse=True)
        score, event, reason = scored[0]
        event_url = str(event.get("event_url") or "")
        seen_urls.add(event_url)
        matches.append(
            {
                "event_url": event_url,
                "event_id": event.get("event_id") or "",
                "match_score": round(score, 6),
                "match_reason": reason,
                "home_team": event.get("home_team") or "",
                "away_team": event.get("away_team") or "",
                "league": event.get("league") or "",
                "kickoff_utc": event.get("kickoff_utc") or "",
                "target": {
                    "home_team": target.get("home_team") or "",
                    "away_team": target.get("away_team") or "",
                    "league": target.get("league") or "",
                    "kickoff_utc": target.get("kickoff_utc") or target.get("kickoff_utc_plus_8") or "",
                },
            }
        )
        if len(matches) >= bounded_limit:
            break
    return matches


def oddsportal_discovery_urls_for_targets(
    targets: list[dict[str, Any]],
    *,
    include_generic: bool = True,
    limit: int = 20,
) -> list[str]:
    """Return low-volume OddsPortal listing URLs suggested by target leagues."""
    bounded_limit = max(1, min(int(limit or 20), 100))
    urls: list[str] = []
    seen: set[str] = set()
    for target in targets:
        for value in (target.get("league"), target.get("division"), target.get("competition")):
            path = _oddsportal_discovery_path_for_league(value)
            if not path:
                continue
            url = urljoin(ODDSPORTAL_BASE_URL, path)
            if url in seen:
                continue
            seen.add(url)
            urls.append(url)
            if len(urls) >= bounded_limit:
                return urls
    if include_generic and len(urls) < bounded_limit:
        generic_url = urljoin(ODDSPORTAL_BASE_URL, "/football/")
        if generic_url not in seen:
            urls.append(generic_url)
    return urls[:bounded_limit]


async def discover_oddsportal_event_urls(
    *,
    targets: list[dict[str, Any]],
    discovery_urls: list[str],
    limit: int = 20,
    timeout_seconds: float = 15.0,
) -> dict[str, Any]:
    """Discover OddsPortal event URLs from configured listing pages.

    This deliberately crawls only caller-provided low-volume listing URLs. It
    returns the match evidence separately from the final URL list so operators
    can see whether discovery failed because targets, pages, or fuzzy matching
    were missing.
    """
    bounded_limit = max(1, min(int(limit or 20), 100))
    selected_urls = [str(url).strip() for url in discovery_urls if str(url or "").strip()]
    if not targets:
        return {
            "status": "no_targets",
            "event_urls": [],
            "matches": [],
            "discovery_urls": selected_urls,
            "message": "No open prediction targets were available for OddsPortal discovery.",
        }
    if not selected_urls:
        return {
            "status": "no_discovery_urls",
            "event_urls": [],
            "matches": [],
            "discovery_urls": [],
            "message": "No OddsPortal discovery listing URLs were configured.",
        }

    fetched_pages = []
    discovery_errors = []
    events: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True, headers=ODDSPORTAL_HEADERS) as client:
        for discovery_url in selected_urls[:bounded_limit]:
            try:
                response = await client.get(discovery_url)
                response.raise_for_status()
                page_events = extract_oddsportal_next_match_events(response.text)
                events.extend(page_events)
                fetched_pages.append(
                    {
                        "url": str(response.url),
                        "status": "ok",
                        "event_count": len(page_events),
                    }
                )
            except Exception as exc:
                discovery_errors.append(
                    {
                        "url": discovery_url,
                        "status": "failed",
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )

    matches = match_oddsportal_events_to_targets(events, targets, limit=bounded_limit)
    event_urls = [str(match.get("event_url") or "") for match in matches if str(match.get("event_url") or "").strip()]
    if event_urls:
        status = "ok"
    elif fetched_pages:
        status = "no_matches"
    else:
        status = "error"
    return {
        "status": status,
        "event_urls": event_urls,
        "matches": matches,
        "candidate_event_count": len(events),
        "target_count": len(targets),
        "fetched_pages": fetched_pages,
        "discovery_errors": discovery_errors,
        "discovery_urls": selected_urls,
    }


def provider_names_from_bonus_payload(payload: dict[str, Any]) -> dict[str, str]:
    data = _as_dict(payload.get("d", payload))
    providers = _as_dict(data.get("providersNames"))
    return {str(key): str(value) for key, value in providers.items() if str(value or "").strip()}


def oddsportal_market_snapshots_from_payload(
    payload: dict[str, Any],
    *,
    event_context: OddsPortalEventContext,
    provider_names: dict[str, str] | None = None,
    fetched_at: datetime | None = None,
) -> list[MarketSnapshot]:
    provider_names = provider_names or {}
    fetched_at = fetched_at or datetime.now(timezone.utc)
    fetched_at_utc = fetched_at.astimezone(timezone.utc).isoformat()
    data = _as_dict(payload.get("d", payload))
    oddsdata = _as_dict(data.get("oddsdata") or data.get("oddsData"))
    back_rows = _as_dict(oddsdata.get("back"))
    snapshots: list[MarketSnapshot] = []

    for row_key, raw_row in back_rows.items():
        row = _as_dict(raw_row)
        betting_type_id = _int_or_none(row.get("bettingTypeId")) or _int_or_none(data.get("bt"))
        scope_id = _int_or_none(row.get("scopeId")) or _int_or_none(data.get("sc"))
        market_type = MARKET_TYPE_BY_BETTING_TYPE.get(int(betting_type_id or 0))
        if not market_type:
            continue
        line = _float_or_none(row.get("handicapValue"))
        odds_by_provider = _as_dict(row.get("odds"))
        opening_by_provider = _as_dict(row.get("openingOdd"))
        for provider_id, odds_value in odds_by_provider.items():
            snapshots.extend(
                _snapshots_for_provider_market(
                    row=row,
                    row_key=str(row_key),
                    provider_id=str(provider_id),
                    provider_name=provider_names.get(str(provider_id), str(provider_id)),
                    market_type=market_type,
                    betting_type_id=int(betting_type_id or 0),
                    scope_id=int(scope_id or 0),
                    line=line,
                    event_context=event_context,
                    fetched_at_utc=fetched_at_utc,
                    odds_value=odds_value,
                    phase="current",
                )
            )
            if provider_id in opening_by_provider:
                snapshots.extend(
                    _snapshots_for_provider_market(
                        row=row,
                        row_key=str(row_key),
                        provider_id=str(provider_id),
                        provider_name=provider_names.get(str(provider_id), str(provider_id)),
                        market_type=market_type,
                        betting_type_id=int(betting_type_id or 0),
                        scope_id=int(scope_id or 0),
                        line=line,
                        event_context=event_context,
                        fetched_at_utc=fetched_at_utc,
                        odds_value=opening_by_provider.get(provider_id),
                        phase="opening",
                    )
                )
    return snapshots


async def fetch_oddsportal_event_market_snapshots(
    event_url: str,
    *,
    betting_type_id: int = 5,
    scope_id: int = 2,
    timeout_seconds: float = 15.0,
) -> dict[str, Any]:
    fetched_at = datetime.now(timezone.utc)
    async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True, headers=ODDSPORTAL_HEADERS) as client:
        page_response = await client.get(event_url)
        page_response.raise_for_status()
        event_context = extract_oddsportal_event_context(page_response.text, event_url=str(page_response.url))
        if not event_context:
            return {
                "status": "event_context_missing",
                "provider": ODDSPORTAL_PROVIDER,
                "event_url": event_url,
                "snapshots": [],
            }
        market_url = oddsportal_match_event_url(
            event_context,
            betting_type_id=betting_type_id,
            scope_id=scope_id,
        )
        market_response = await client.get(
            market_url,
            params={"geo": os.getenv("FOOTBALL_DATA_ODDSPORTAL_GEO", "CN"), "lang": "en"},
            headers={"Referer": event_context.event_url or event_url},
        )
        market_response.raise_for_status()
        market_payload = json.loads(decrypt_oddsportal_response(market_response.text))
        provider_names = await _fetch_provider_names(client)
        snapshots = oddsportal_market_snapshots_from_payload(
            market_payload,
            event_context=event_context,
            provider_names=provider_names,
            fetched_at=fetched_at,
        )
        return {
            "status": "ok" if snapshots else "empty",
            "provider": ODDSPORTAL_PROVIDER,
            "event_id": event_context.event_id,
            "event_url": event_context.event_url or event_url,
            "market_url": market_url,
            "betting_type_id": betting_type_id,
            "scope_id": scope_id,
            "snapshot_count": len(snapshots),
            "snapshots": snapshots,
        }


async def _fetch_provider_names(client: httpx.AsyncClient) -> dict[str, str]:
    try:
        response = await client.get(urljoin(ODDSPORTAL_BASE_URL, "/ajax-providers-bonus-data/0/"), params={"logged": "false"})
        response.raise_for_status()
        payload = json.loads(decrypt_oddsportal_response(response.text))
        return provider_names_from_bonus_payload(payload)
    except Exception:
        return {}


def _snapshots_for_provider_market(
    *,
    row: dict[str, Any],
    row_key: str,
    provider_id: str,
    provider_name: str,
    market_type: str,
    betting_type_id: int,
    scope_id: int,
    line: float | None,
    event_context: OddsPortalEventContext,
    fetched_at_utc: str,
    odds_value: Any,
    phase: str,
) -> list[MarketSnapshot]:
    snapshots = []
    for outcome in _market_outcomes(market_type, event_context, odds_value, line):
        decimal_odds = _float_or_none(outcome.get("decimal_odds"))
        if decimal_odds is None or decimal_odds <= 1:
            continue
        source_time = _provider_source_time(row, provider_id=provider_id, outcome_index=outcome["index"], phase=phase)
        snapshots.append(
            MarketSnapshot(
                provider=ODDSPORTAL_PROVIDER,
                source_key=f"oddsportal:{event_context.event_id}:{betting_type_id}:{scope_id}",
                event_id=event_context.event_id,
                league=event_context.league,
                home_team=event_context.home_team,
                away_team=event_context.away_team,
                kickoff_utc=event_context.kickoff_utc,
                bookmaker=provider_name,
                market_type=market_type,
                selection=str(outcome["selection"]),
                decimal_odds=round(decimal_odds, 4),
                line=outcome.get("line"),
                source_time_utc=source_time or fetched_at_utc,
                fetched_at_utc=fetched_at_utc,
                raw={
                    "source": ODDSPORTAL_PROVIDER,
                    "phase": phase,
                    "row_key": row_key,
                    "provider_id": provider_id,
                    "betting_type_id": betting_type_id,
                    "scope_id": scope_id,
                    "scope_name": SCOPE_NAME_BY_ID.get(scope_id, str(scope_id)),
                    "movement": _provider_nested_value(row.get("movement"), provider_id, outcome["index"]),
                    "outcome_index": outcome["index"],
                    "upstream_event_url": event_context.event_url,
                },
            )
        )
    return snapshots


def _market_outcomes(
    market_type: str,
    event_context: OddsPortalEventContext,
    odds_value: Any,
    line: float | None,
) -> list[dict[str, Any]]:
    values = _odds_value_to_sequence(odds_value)
    if market_type == "h2h":
        return [
            {"index": 0, "selection": event_context.home_team, "line": None, "decimal_odds": _sequence_value(values, 0)},
            {"index": 1, "selection": "Draw", "line": None, "decimal_odds": _sequence_value(values, 1)},
            {"index": 2, "selection": event_context.away_team, "line": None, "decimal_odds": _sequence_value(values, 2)},
        ]
    if market_type == "asian_handicap":
        return [
            {"index": 0, "selection": event_context.home_team, "line": line, "decimal_odds": _sequence_value(values, 0)},
            {
                "index": 1,
                "selection": event_context.away_team,
                "line": -line if line is not None else None,
                "decimal_odds": _sequence_value(values, 1),
            },
        ]
    if market_type == "over_under":
        return [
            {"index": 0, "selection": "Over", "line": line, "decimal_odds": _sequence_value(values, 0)},
            {"index": 1, "selection": "Under", "line": line, "decimal_odds": _sequence_value(values, 1)},
        ]
    return []


def _odds_value_to_sequence(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        # OddsPortal uses key 0 for draw/second side in several handicap rows.
        if {"1", "0", "2"} & set(value.keys()):
            return [value.get("1"), value.get("0"), value.get("2")]
        return list(value.values())
    return []


def _provider_source_time(row: dict[str, Any], *, provider_id: str, outcome_index: int, phase: str) -> str:
    field = "openingChangeTime" if phase == "opening" else "changeTime"
    value = _provider_nested_value(row.get(field), provider_id, outcome_index)
    return _iso_utc(value)


def _provider_nested_value(value: Any, provider_id: str, outcome_index: int) -> Any:
    provider_value = _as_dict(value).get(provider_id) if isinstance(value, dict) else None
    if isinstance(provider_value, list):
        return _sequence_value(provider_value, outcome_index)
    if isinstance(provider_value, dict):
        return _sequence_value(_odds_value_to_sequence(provider_value), outcome_index)
    return provider_value


def _sequence_value(values: list[Any], index: int) -> Any:
    return values[index] if 0 <= index < len(values) else None


def _participant_name(value: Any) -> str:
    if isinstance(value, dict):
        for key in ("name", "participantName", "fullName", "title"):
            text = str(value.get(key) or "").strip()
            if text:
                return text
    return str(value or "").strip()


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


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


def _iso_utc(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, (int, float)) or (isinstance(value, str) and value.strip().isdigit()):
        parsed = datetime.fromtimestamp(float(value), tz=timezone.utc)
    else:
        try:
            parsed = date_parser.parse(str(value))
        except (TypeError, ValueError):
            return ""
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def _oddsportal_event_target_score(event: dict[str, Any], target: dict[str, Any]) -> tuple[float, str]:
    home_score = _text_similarity(event.get("home_team"), target.get("home_team"))
    away_score = _text_similarity(event.get("away_team"), target.get("away_team"))
    swapped_home_score = _text_similarity(event.get("home_team"), target.get("away_team"))
    swapped_away_score = _text_similarity(event.get("away_team"), target.get("home_team"))
    direct_pair_score = (home_score + away_score) / 2
    swapped_pair_score = (swapped_home_score + swapped_away_score) / 2
    pair_score = max(direct_pair_score, swapped_pair_score * 0.92)
    pair_reason = "team_pair" if direct_pair_score >= swapped_pair_score else "swapped_team_pair"
    league_score = _text_similarity(event.get("league"), target.get("league"))
    kickoff_score = _kickoff_similarity(event.get("kickoff_utc"), target.get("kickoff_utc") or target.get("kickoff_utc_plus_8"))
    score = pair_score * 0.76 + league_score * 0.10 + kickoff_score * 0.14
    if pair_score >= 0.98 and kickoff_score >= 0.6:
        score = max(score, 0.94)
    return score, pair_reason


def _text_similarity(left: Any, right: Any) -> float:
    left_normalized = _normalize_match_text(left)
    right_normalized = _normalize_match_text(right)
    if not left_normalized or not right_normalized:
        return 0.0
    if left_normalized == right_normalized:
        return 1.0
    left_tokens = set(left_normalized.split())
    right_tokens = set(right_normalized.split())
    token_score = len(left_tokens & right_tokens) / max(1, len(left_tokens | right_tokens))
    sequence_score = SequenceMatcher(None, left_normalized, right_normalized).ratio()
    return max(token_score, sequence_score)


def _normalize_match_text(value: Any) -> str:
    raw_text = str(value or "").strip().lower()
    text = ODDSPORTAL_TEAM_NAME_ALIASES.get(raw_text, raw_text)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
    stopwords = {"fc", "cf", "sc", "club", "football", "soccer"}
    tokens = [token for token in text.split() if token not in stopwords]
    return " ".join(tokens)


def _oddsportal_discovery_path_for_league(value: Any) -> str:
    raw_text = str(value or "").strip().lower()
    path = ODDSPORTAL_DISCOVERY_PATH_BY_LEAGUE.get(raw_text)
    if path:
        return path
    normalized = _normalize_match_text(value)
    if not normalized:
        return ""
    path = ODDSPORTAL_DISCOVERY_PATH_BY_LEAGUE.get(normalized)
    if path:
        return path
    for key, candidate_path in ODDSPORTAL_DISCOVERY_PATH_BY_LEAGUE.items():
        if key in normalized or normalized in key:
            return candidate_path
    return ""


def _kickoff_similarity(left: Any, right: Any) -> float:
    left_dt = _parse_datetime_utc(left)
    right_dt = _parse_datetime_utc(right)
    if left_dt is None or right_dt is None:
        return 0.5
    diff = abs(left_dt - right_dt)
    if diff <= timedelta(hours=3):
        return 1.0
    if diff <= timedelta(hours=12):
        return 0.7
    if diff <= timedelta(hours=24):
        return 0.4
    return 0.0


def _parse_datetime_utc(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        if isinstance(value, datetime):
            parsed = value
        else:
            parsed = date_parser.parse(str(value))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
