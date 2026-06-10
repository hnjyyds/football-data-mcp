from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any
from urllib.parse import urljoin

import httpx
import json
from datetime import datetime, timezone
from bs4 import BeautifulSoup

from football_data_mcp.snapshot_store import MarketSnapshot


BETEXPLORER_BASE_URL = "https://www.betexplorer.com"
BETEXPLORER_PROVIDER = "betexplorer_scraper"
BETEXPLORER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def extract_betexplorer_market_tab_urls(page_html: str, *, page_url: str = "") -> dict[str, str]:
    if not page_html:
        return {}
    tabs = {
        "1x2": r'href=["\'](?P<href>/football/[^"\']+/[^"\']+/[A-Za-z0-9]+/1x2/)["\']',
        "over_under": r'href=["\'](?P<href>/football/[^"\']+/[^"\']+/[A-Za-z0-9]+/over-under/)["\']',
        "asian_handicap": r'href=["\'](?P<href>/football/[^"\']+/[^"\']+/[A-Za-z0-9]+/asian-handicap/)["\']',
    }
    extracted: dict[str, str] = {}
    for key, pattern in tabs.items():
        match = re.search(pattern, page_html, re.I)
        if not match:
            continue
        extracted[key] = urljoin(page_url or BETEXPLORER_BASE_URL, match.group("href").strip())
    return extracted


def extract_betexplorer_match_urls(page_html: str, *, page_url: str = "") -> list[str]:
    if not page_html:
        return []
    pattern = re.compile(r'href=["\'](?P<href>/football/[^"\']+/[^"\']+/[A-Za-z0-9]+/)["\']', re.I)
    seen: set[str] = set()
    urls: list[str] = []
    for match in pattern.finditer(page_html):
        href = match.group("href").strip()
        absolute = urljoin(page_url or BETEXPLORER_BASE_URL, href)
        if absolute in seen:
            continue
        seen.add(absolute)
        urls.append(absolute)
    return urls


def _normalize_name(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[\s\-_/]+", " ", text)
    return text


def _match_score(event_url: str, target: dict[str, Any]) -> tuple[float, str]:
    normalized = _normalize_name(event_url)
    home = _normalize_name(target.get("home_team"))
    away = _normalize_name(target.get("away_team"))
    if not home or not away:
        return 0.0, "missing_home_or_away"
    score = 0.0
    if home in normalized:
        score += 0.45
    else:
        score += 0.25 * SequenceMatcher(None, home, normalized).ratio()
    if away in normalized:
        score += 0.45
    else:
        score += 0.25 * SequenceMatcher(None, away, normalized).ratio()
    league = _normalize_name(target.get("league"))
    if league and league in normalized:
        score += 0.1
        reason = "home_away_league_match"
    else:
        reason = "home_away_match"
    return score, reason


def match_betexplorer_events_to_targets(
    event_urls: list[str],
    targets: list[dict[str, Any]],
    *,
    limit: int = 20,
) -> list[dict[str, Any]]:
    bounded_limit = max(1, min(int(limit or 20), 100))
    matches: list[dict[str, Any]] = []
    used_urls: set[str] = set()
    for target in targets:
        best_url = ""
        best_score = 0.0
        best_reason = ""
        for event_url in event_urls:
            if event_url in used_urls:
                continue
            score, reason = _match_score(event_url, target)
            if score > best_score:
                best_url = event_url
                best_score = score
                best_reason = reason
        if best_url and best_score >= 0.55:
            used_urls.add(best_url)
            matches.append(
                {
                    "event_url": best_url,
                    "score": round(best_score, 4),
                    "reason": best_reason,
                    "target": target,
                }
            )
        if len(matches) >= bounded_limit:
            break
    return matches


async def fetch_betexplorer_match_tabs(
    event_url: str,
    *,
    timeout_seconds: float = 15.0,
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True, headers=BETEXPLORER_HEADERS) as client:
        response = await client.get(event_url)
        response.raise_for_status()
    tab_urls = extract_betexplorer_market_tab_urls(response.text, page_url=str(response.url))
    return {
        "status": "ok" if tab_urls else "no_tabs",
        "provider": BETEXPLORER_PROVIDER,
        "event_url": str(response.url),
        "tab_urls": tab_urls,
    }


def extract_betexplorer_match_load_args(page_html: str) -> dict[str, str]:
    if not page_html:
        return {}
    match = re.search(
        r"match_load_tabs\('(?P<event_id>[^']+)'\s*,\s*'(?P<bet_type>[^']+)'\s*,\s*'(?P<stage_id>[^']+)'\s*,\s*'(?P<hp_h>[^']+)'\s*,\s*'(?P<hp_a>[^']+)'\s*,",
        page_html,
        re.I,
    )
    if not match:
        return {}
    return {
        "event_id": match.group("event_id"),
        "bet_type": match.group("bet_type"),
        "stage_id": match.group("stage_id"),
        "hp_h": match.group("hp_h"),
        "hp_a": match.group("hp_a"),
    }


async def fetch_betexplorer_best_odds_html(
    event_url: str,
    *,
    market_type: str = "1x2",
    timeout_seconds: float = 15.0,
) -> dict[str, Any]:
    market_aliases = {
        "1x2": "1x2",
        "h2h": "1x2",
        "over_under": "ou",
        "ou": "ou",
        "asian_handicap": "ah",
        "ah": "ah",
    }
    normalized_market = market_aliases.get(str(market_type or "").strip().lower(), "1x2")
    async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True, headers=BETEXPLORER_HEADERS) as client:
        response = await client.get(event_url)
        response.raise_for_status()
        args = extract_betexplorer_match_load_args(response.text)
        if not args:
            return {
                "status": "match_load_args_missing",
                "provider": BETEXPLORER_PROVIDER,
                "event_url": str(response.url),
                "market_type": normalized_market,
                "odds_html": "",
            }
        odds_response = await client.get(
            f"{BETEXPLORER_BASE_URL}/match-odds/{args['event_id']}/0/{normalized_market}/bestOdds/?lang=en",
            headers={
                **BETEXPLORER_HEADERS,
                "X-Requested-With": "XMLHttpRequest",
                "Referer": str(response.url),
            },
        )
        odds_response.raise_for_status()
    payload = json.loads(odds_response.text)
    odds_html = str(payload.get("odds") or "")
    return {
        "status": "ok" if odds_html else "empty",
        "provider": BETEXPLORER_PROVIDER,
        "event_url": str(response.url),
        "market_type": normalized_market,
        "event_id": args.get("event_id") or "",
        "odds_html": odds_html,
        "raw_payload": payload,
    }


def _event_context_from_url(event_url: str) -> dict[str, str]:
    # /football/<country>/<league>/<home-away>/<event_id>/
    match = re.search(
        r"/football/(?P<country>[^/]+)/(?P<league>[^/]+)/(?P<teams>[^/]+)/(?P<event_id>[A-Za-z0-9]+)/?$",
        event_url,
        re.I,
    )
    if not match:
        return {"league": "", "event_id": "", "teams_slug": ""}
    return {
        "league": match.group("league").replace("-", " ").strip(),
        "event_id": match.group("event_id").strip(),
        "teams_slug": match.group("teams").strip(),
    }


def _bookmaker_name_from_row(row: Any) -> str:
    link = row.find("a", class_=re.compile(r"in-bookmaker-logo-link", re.I))
    if link:
        text = link.get_text(" ", strip=True)
        if text:
            return text
    span = row.find("span", class_=re.compile(r"in-bookmaker-logo", re.I))
    if span:
        title = str(span.get("title") or "").strip()
        if title:
            return title
    return ""


def _selection_labels_for_market(market_type: str) -> list[str]:
    if market_type == "1x2":
        return ["1", "X", "2"]
    if market_type == "over_under":
        return ["over", "under"]
    if market_type == "asian_handicap":
        return ["home_cover", "away_cover"]
    return []


def _parse_line_value(text: str) -> float | None:
    raw = str(text or "").strip()
    if not raw:
        return None
    raw = raw.replace("−", "-").replace(",", ".")
    if re.fullmatch(r"[+-]?\d+(?:\.\d+)?", raw):
        return float(raw)
    parts = [part for part in re.split(r"\s*/\s*|\s*,\s*", str(text or "").replace("−", "-").strip()) if part]
    numeric: list[float] = []
    for part in parts:
        normalized = part.replace(",", ".")
        if re.fullmatch(r"[+-]?\d+(?:\.\d+)?", normalized):
            numeric.append(float(normalized))
    if numeric:
        return sum(numeric) / len(numeric)
    return None


def betexplorer_market_snapshots_from_html(
    odds_html: str,
    *,
    event_url: str,
    market_type: str,
    fetched_at_utc: str | None = None,
) -> list[MarketSnapshot]:
    if not odds_html:
        return []
    fetched_at_utc = fetched_at_utc or datetime.now(timezone.utc).isoformat()
    soup = BeautifulSoup(odds_html, "html.parser")
    context = _event_context_from_url(event_url)
    snapshots: list[MarketSnapshot] = []
    selection_labels = _selection_labels_for_market(market_type)
    for table in soup.find_all("table", class_=re.compile(r"table-main", re.I)):
        rows = table.find_all("tr")
        if not rows:
            continue
        for row in rows[1:]:
            bookmaker = _bookmaker_name_from_row(row)
            if not bookmaker:
                continue
            cells = row.find_all("td")
            odds_cells = [cell for cell in cells if cell.has_attr("data-odd")]
            if not odds_cells:
                continue
            line_value = None
            if market_type in {"over_under", "asian_handicap"}:
                # BetExplorer best-odds rows keep the shared line in the cell
                # immediately before the odds columns.
                if len(cells) >= 5:
                    line_value = _parse_line_value(cells[4].get_text(" ", strip=True))
            for idx, odds_cell in enumerate(odds_cells[: len(selection_labels)]):
                odd = str(odds_cell.get("data-odd") or "").strip()
                created = str(odds_cell.get("data-created") or "").strip()
                try:
                    decimal_odds = float(odd)
                except ValueError:
                    continue
                if decimal_odds <= 1:
                    continue
                selection = selection_labels[idx]
                snapshots.append(
                    MarketSnapshot(
                        provider=BETEXPLORER_PROVIDER,
                        source_key=f"betexplorer:{context['event_id']}:{market_type}",
                        event_id=context["event_id"],
                        league=context["league"],
                        home_team="",
                        away_team="",
                        kickoff_utc="",
                        bookmaker=bookmaker,
                        market_type="h2h" if market_type == "1x2" else market_type,
                        selection=selection,
                        decimal_odds=decimal_odds,
                        line=line_value,
                        source_time_utc=created,
                        fetched_at_utc=fetched_at_utc,
                        raw={
                            "event_url": event_url,
                            "market_type": market_type,
                            "bookmaker": bookmaker,
                            "selection": selection,
                            "data_created": created,
                        },
                    )
                )
    return snapshots


async def fetch_betexplorer_event_market_snapshots(
    event_url: str,
    *,
    market_type: str = "1x2",
    timeout_seconds: float = 15.0,
) -> dict[str, Any]:
    result = await fetch_betexplorer_best_odds_html(
        event_url,
        market_type=market_type,
        timeout_seconds=timeout_seconds,
    )
    if result.get("status") != "ok":
        return {
            **result,
            "snapshot_count": 0,
            "snapshots": [],
        }
    snapshots = betexplorer_market_snapshots_from_html(
        str(result.get("odds_html") or ""),
        event_url=str(result.get("event_url") or event_url),
        market_type=str(market_type or "1x2"),
    )
    return {
        **result,
        "status": "ok" if snapshots else "empty",
        "snapshot_count": len(snapshots),
        "snapshots": snapshots,
    }


async def discover_betexplorer_event_urls(
    *,
    targets: list[dict[str, Any]],
    discovery_urls: list[str],
    limit: int = 20,
    timeout_seconds: float = 15.0,
) -> dict[str, Any]:
    bounded_limit = max(1, min(int(limit or 20), 100))
    selected_urls = [str(url).strip() for url in discovery_urls if str(url or "").strip()]
    if not targets:
        return {
            "status": "no_targets",
            "event_urls": [],
            "matches": [],
            "discovery_urls": selected_urls,
            "message": "No open prediction targets were available for BetExplorer discovery.",
        }
    if not selected_urls:
        return {
            "status": "no_discovery_urls",
            "event_urls": [],
            "matches": [],
            "discovery_urls": [],
            "message": "No BetExplorer discovery listing URLs were configured.",
        }

    fetched_pages = []
    discovery_errors = []
    discovered_urls: list[str] = []
    async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True, headers=BETEXPLORER_HEADERS) as client:
        for discovery_url in selected_urls[:bounded_limit]:
            try:
                response = await client.get(discovery_url)
                response.raise_for_status()
                page_urls = extract_betexplorer_match_urls(response.text, page_url=str(response.url))
                discovered_urls.extend(page_urls)
                fetched_pages.append(
                    {
                        "url": str(response.url),
                        "status": "ok",
                        "event_count": len(page_urls),
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

    matches = match_betexplorer_events_to_targets(discovered_urls, targets, limit=bounded_limit)
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
        "candidate_event_count": len(discovered_urls),
        "target_count": len(targets),
        "fetched_pages": fetched_pages,
        "discovery_errors": discovery_errors,
        "discovery_urls": selected_urls,
        "provider": BETEXPLORER_PROVIDER,
    }
