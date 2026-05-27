from __future__ import annotations

import asyncio
import base64
from collections import Counter
import csv
import gzip
import hashlib
import io
from itertools import combinations
import json
import math
import os
import re
import shutil
import subprocess
import threading
import time
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

from football_data_mcp import external_sources, learning_store, model_engine, snapshot_store


FIXTURES_URL = "https://www.football-data.co.uk/fixtures.csv"
SEASON_URL_TEMPLATE = "https://www.football-data.co.uk/mmz4281/{season}/{division}.csv"
DONGQIUDI_SCHEDULE_URL = "https://www.dongqiudi.com/magicball/v1/list/schedule_list"
DONGQIUDI_DETAIL_URL = "https://www.dongqiudi.com/magicball/v1/match/app/detail"
DONGQIUDI_PRE_ANALYSIS_URL_TEMPLATE = "https://www.dongqiudi.com/api/data/match/pre_analysis_v1/{match_id}"
DONGQIUDI_ODDS_URL_TEMPLATE = "https://www.dongqiudi.com/sport-data/soccer/biz/dqd/v1/match/odds/index/{match_id}"
DONGQIUDI_LINEUP_URL_TEMPLATE = "https://www.dongqiudi.com/sport-data/soccer/biz/dqd/v1/match/lineup/{match_id}"
LEISU_SCHEDULE_URL = "https://live.leisu.com/saicheng"
LEISU_SCHEDULE_DATE_URL_TEMPLATE = "https://live.leisu.com/saicheng-{date}"
LEISU_ODDS_URL_TEMPLATE = "https://odds.leisu.com/3in1-{match_id}"
SPORTTERY_MATCH_LIST_URL = "https://webapi.sporttery.cn/gateway/uniform/football/getMatchListV1.qry?clientCode=3001"
SOURCE_TIMEZONE = ZoneInfo("Europe/London")
DEFAULT_USER_TIMEZONE = ZoneInfo("Asia/Shanghai")
MATCH_SCORE_THRESHOLD = float(os.getenv("FOOTBALL_DATA_MATCH_SCORE_THRESHOLD", "0.68"))
PRICE_OUTLIER_DEVIATION_THRESHOLD = float(os.getenv("FOOTBALL_DATA_PRICE_OUTLIER_DEVIATION_THRESHOLD", "0.22"))
JINGCAI_PARLAY_DEFAULT_WINDOW_MINUTES = 24 * 60
AUTO_LEARNING_STATE: dict[str, Any] = {
    "enabled": False,
    "run_count": 0,
    "last_started_at_utc": None,
    "last_finished_at_utc": None,
    "last_error": None,
    "last_result_summary": None,
}

CACHE_SECONDS = int(os.getenv("FOOTBALL_DATA_CACHE_SECONDS", "300"))
HTTP_TIMEOUT_SECONDS = float(os.getenv("FOOTBALL_DATA_HTTP_TIMEOUT", "20"))
LEISU_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    ),
    "Referer": "https://live.leisu.com/",
}
LEISU_ODDS_HEADERS = {
    **LEISU_HEADERS,
    "Referer": "https://live.leisu.com/",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8,*/*;q=0.7",
}
LEISU_MOBILE_API_BASE_URL = "https://api-gateway.leisu.com"
LEISU_MOBILE_WEBSITE_URL = "https://m.leisu.com"
LEISU_MOBILE_API_SECRET = "NcFebvke4S9vZJ8sR4QvrVKGAxkmqIo4"
LEISU_MOBILE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
    ),
    "Origin": LEISU_MOBILE_WEBSITE_URL,
    "Referer": f"{LEISU_MOBILE_WEBSITE_URL}/",
    "Accept": "application/json,text/plain,*/*",
}
LEISU_MOBILE_ODDS_LIST_PATH = "/v1/web/match/common/odds_list"
LEISU_MOBILE_ODDS_DETAIL_PATH = "/v1/web/match/common/odds_detail"
LEISU_MOBILE_MARKET_HANDICAPS = {"asia": 1, "eu": 2, "bs": 3}
_LEISU_MOBILE_WAF_STATE: dict[str, Any] = {}
SPORTTERY_HEADERS = {
    "User-Agent": LEISU_HEADERS["User-Agent"],
    "Referer": "https://www.sporttery.cn/",
}


LEAGUE_NAMES = {
    "E0": "England Premier League",
    "E1": "England Championship",
    "E2": "England League One",
    "E3": "England League Two",
    "EC": "England National League",
    "SC0": "Scotland Premiership",
    "SC1": "Scotland Championship",
    "SC2": "Scotland League One",
    "SC3": "Scotland League Two",
    "D1": "Germany Bundesliga",
    "D2": "Germany 2. Bundesliga",
    "I1": "Italy Serie A",
    "I2": "Italy Serie B",
    "SP1": "Spain La Liga",
    "SP2": "Spain La Liga 2",
    "F1": "France Ligue 1",
    "F2": "France Ligue 2",
    "N1": "Netherlands Eredivisie",
    "B1": "Belgium First Division A",
    "P1": "Portugal Primeira Liga",
    "T1": "Turkey Super Lig",
    "G1": "Greece Super League",
}

TEAM_ALIASES = {
    "阿森纳": "Arsenal",
    "利物浦": "Liverpool",
    "曼城": "Man City",
    "曼联": "Man United",
    "切尔西": "Chelsea",
    "热刺": "Tottenham",
    "托特纳姆": "Tottenham",
    "纽卡斯尔": "Newcastle",
    "阿斯顿维拉": "Aston Villa",
    "伯恩茅斯": "Bournemouth",
    "布莱顿": "Brighton",
    "埃弗顿": "Everton",
    "富勒姆": "Fulham",
    "狼队": "Wolves",
    "西汉姆": "West Ham",
    "水晶宫": "Crystal Palace",
    "诺丁汉森林": "Nottingham Forest",
    "皇马": "Real Madrid",
    "皇家马德里": "Real Madrid",
    "巴萨": "Barcelona",
    "巴塞罗那": "Barcelona",
    "马竞": "Ath Madrid",
    "马德里竞技": "Ath Madrid",
    "拜仁": "Bayern Munich",
    "多特": "Dortmund",
    "多特蒙德": "Dortmund",
    "巴黎": "Paris SG",
    "巴黎圣日耳曼": "Paris SG",
    "国际米兰": "Inter",
    "国米": "Inter",
    "AC米兰": "Milan",
    "尤文": "Juventus",
    "尤文图斯": "Juventus",
    "町田泽维亚": "Machida Zelvia",
    "町田ゼルビア": "Machida Zelvia",
    "FC町田ゼルビア": "Machida Zelvia",
    "ＦＣ町田ゼルビア": "Machida Zelvia",
    "machida zelvia": "Machida Zelvia",
    "町田": "Machida Zelvia",
    "浦和红钻": "Urawa Red Diamonds",
    "浦和レッズ": "Urawa Red Diamonds",
    "urawa reds": "Urawa Red Diamonds",
    "urawa red diamonds": "Urawa Red Diamonds",
    "浦和": "Urawa Red Diamonds",
}

BOOKMAKER_FIELDS = {
    "Bet365": ("B365H", "B365D", "B365A"),
    "Betfair": ("BFDH", "BFDD", "BFDA"),
    "BetMGM": ("BMGMH", "BMGMD", "BMGMA"),
    "Bovada": ("BVH", "BVD", "BVA"),
    "Betway": ("BWH", "BWD", "BWA"),
    "Ladbrokes": ("LBH", "LBD", "LBA"),
    "Pinnacle": ("PSH", "PSD", "PSA"),
    "Max": ("MaxH", "MaxD", "MaxA"),
    "Average": ("AvgH", "AvgD", "AvgA"),
    "Betfair Exchange": ("BFEH", "BFED", "BFEA"),
    "Bet365 closing": ("B365CH", "B365CD", "B365CA"),
    "Pinnacle closing": ("PSCH", "PSCD", "PSCA"),
    "Max closing": ("MaxCH", "MaxCD", "MaxCA"),
    "Average closing": ("AvgCH", "AvgCD", "AvgCA"),
}

OVER_UNDER_FIELDS = {
    "Bet365 over/under 2.5": ("B365>2.5", "B365<2.5"),
    "Pinnacle over/under 2.5": ("P>2.5", "P<2.5"),
    "Max over/under 2.5": ("Max>2.5", "Max<2.5"),
    "Average over/under 2.5": ("Avg>2.5", "Avg<2.5"),
    "Betfair Exchange over/under 2.5": ("BFE>2.5", "BFE<2.5"),
}

HANDICAP_FIELDS = {
    "Asian handicap line": "AHh",
    "Bet365 AH home": "B365AHH",
    "Bet365 AH away": "B365AHA",
    "Pinnacle AH home": "PAHH",
    "Pinnacle AH away": "PAHA",
    "Max AH home": "MaxAHH",
    "Max AH away": "MaxAHA",
    "Average AH home": "AvgAHH",
    "Average AH away": "AvgAHA",
}

PROBE_SOURCES = [
    {
        "key": "football_data_fixtures",
        "name": "Football-Data fixtures.csv",
        "url": FIXTURES_URL,
        "kind": "csv_odds",
        "role": "primary_numeric_odds_and_schedule",
    },
    {
        "key": "oddsportal_football",
        "name": "OddsPortal football",
        "url": "https://www.oddsportal.com/football/",
        "kind": "html_odds_directory",
        "role": "secondary_odds_directory_if_parseable",
    },
    {
        "key": "scorebat_football",
        "name": "ScoreBat football",
        "url": "https://www.scorebat.com/football/",
        "kind": "html_schedule_context",
        "role": "schedule_and_context_if_parseable",
    },
    {
        "key": "soccerway",
        "name": "Soccerway",
        "url": "https://www.soccerway.com/?lang=us",
        "kind": "html_schedule_context",
        "role": "schedule_and_league_context_if_parseable",
    },
    {
        "key": "flashscore_mobile",
        "name": "Flashscore mobile",
        "url": "https://m.flashscore.co.uk/football/",
        "kind": "html_schedule_context",
        "role": "schedule_status_if_accessible",
    },
    {
        "key": "sky_sports_fixtures",
        "name": "Sky Sports fixtures",
        "url": "https://www.skysports.com/football/fixtures-results",
        "kind": "html_schedule_news",
        "role": "schedule_and_news_if_parseable",
    },
    {
        "key": "leisu_schedule",
        "name": "Leisu football schedule",
        "url": LEISU_SCHEDULE_URL,
        "kind": "html_schedule_context_leisu",
        "role": "chinese_schedule_team_names_status_and_links_corroboration",
    },
    {
        "key": "jleague_machida_official",
        "name": "J.LEAGUE official Machida fixtures",
        "url": "https://www.jleague.jp/club/machida/day/",
        "kind": "html_schedule_context",
        "role": "official_jleague_schedule_if_relevant",
    },
]

BLOCK_PATTERNS = [
    "cloudflare",
    "attention required",
    "just a moment",
    "enable javascript",
    "access denied",
    "403 forbidden",
    "denied by rate limit",
    "rate limit",
    "captcha",
]


@dataclass
class CachedText:
    fetched_at: float
    text: str
    url: str


_TEXT_CACHE: dict[str, CachedText] = {}
_CLIENT: httpx.AsyncClient | None = None


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


async def get_client() -> httpx.AsyncClient:
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = httpx.AsyncClient(
            timeout=HTTP_TIMEOUT_SECONDS,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (compatible; FootballDataMCP/0.1; "
                    "+https://www.football-data.co.uk/)"
                )
            },
        )
    return _CLIENT


_HTTP_RETRY_ATTEMPTS = 3
_HTTP_RETRY_BACKOFF_BASE = 1.5  # seconds


async def _fetch_with_retry(
    client: httpx.AsyncClient,
    url: str,
    *,
    method: str = "GET",
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    last_exc: Exception | None = None
    for attempt in range(_HTTP_RETRY_ATTEMPTS):
        try:
            response = await client.request(method, url, params=params, headers=headers)
            # Don't retry on client errors (4xx) \u2014 they're permanent
            if response.status_code < 500:
                response.raise_for_status()
                return response
            # 5xx: retry with backoff
            if attempt < _HTTP_RETRY_ATTEMPTS - 1:
                await asyncio.sleep(_HTTP_RETRY_BACKOFF_BASE ** attempt)
            else:
                response.raise_for_status()
        except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError) as exc:
            last_exc = exc
            if attempt < _HTTP_RETRY_ATTEMPTS - 1:
                await asyncio.sleep(_HTTP_RETRY_BACKOFF_BASE ** attempt)
        except httpx.HTTPStatusError:
            raise
    if last_exc is not None:
        raise last_exc
    raise httpx.RequestError(f"fetch failed after {_HTTP_RETRY_ATTEMPTS} attempts: {url}")


async def fetch_text(url: str, *, use_cache: bool = True, headers: dict[str, str] | None = None) -> CachedText:
    cached = _TEXT_CACHE.get(url)
    if use_cache and cached and time.time() - cached.fetched_at <= CACHE_SECONDS:
        return cached

    client = await get_client()
    response = await _fetch_with_retry(client, url, headers=headers)
    text = response.text
    if text.startswith("\ufeff"):
        text = text.lstrip("\ufeff")
    cached = CachedText(fetched_at=time.time(), text=text, url=url)
    _TEXT_CACHE[url] = cached
    return cached


async def fetch_json(url: str, *, params: dict[str, Any] | None = None, use_cache: bool = True) -> tuple[Any, dict[str, str]]:
    cache_key = url
    if params:
        cache_key += "?" + "&".join(f"{key}={params[key]}" for key in sorted(params))
    cached = _TEXT_CACHE.get(cache_key)
    if use_cache and cached and time.time() - cached.fetched_at <= CACHE_SECONDS:
        source_name = "dongqiudi.com" if "dongqiudi.com" in cached.url else "football-data.co.uk"
        return httpx.Response(200, text=cached.text).json(), evidence(cached.url, cached.fetched_at, source_name)

    client = await get_client()
    response = await _fetch_with_retry(
        client, url, params=params,
        headers={"Referer": "https://www.dongqiudi.com/match/schedule"},
    )
    cached = CachedText(fetched_at=time.time(), text=response.text, url=str(response.url))
    _TEXT_CACHE[cache_key] = cached
    return response.json(), evidence(cached.url, cached.fetched_at, "dongqiudi.com")


def parse_csv(text: str) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(text))
    return [
        {str(k or "").strip(): str(v or "").strip() for k, v in row.items()}
        for row in reader
        if row
    ]


async def load_fixtures() -> tuple[list[dict[str, str]], dict[str, Any]]:
    fetched = await fetch_text(FIXTURES_URL)
    rows = parse_csv(fetched.text)
    return rows, evidence(fetched.url, fetched.fetched_at)


async def load_season(division: str, kickoff: datetime | None = None) -> tuple[list[dict[str, str]], dict[str, Any]]:
    season = season_code_for(kickoff or now_utc())
    url = SEASON_URL_TEMPLATE.format(season=season, division=division.lower())
    fetched = await fetch_text(url)
    rows = parse_csv(fetched.text)
    return rows, evidence(fetched.url, fetched.fetched_at)


def evidence(url: str, fetched_at: float, source_name: str = "football-data.co.uk") -> dict[str, str]:
    fetched_dt = datetime.fromtimestamp(fetched_at, tz=timezone.utc)
    return {
        "url": url,
        "fetched_at_utc": fetched_dt.isoformat(),
        "source": source_name,
    }


def html_title(text: str) -> str:
    soup = BeautifulSoup(text or "", "html.parser")
    title = soup.find("title")
    return title.get_text(" ", strip=True) if title else ""


def block_reason(text: str) -> str | None:
    lowered = (text or "").lower()
    for pattern in BLOCK_PATTERNS:
        if pattern in lowered:
            return pattern
    return None


def source_block_reason(source_key: str, text: str, *, parsed_match_count: int = 0) -> str | None:
    reason = block_reason(text)
    if source_key == "leisu_schedule" and parsed_match_count > 0:
        return None
    return reason


def clean_leisu_text(value: str) -> str:
    value = re.sub(r"\s+", " ", value or "")
    return value.replace("\xa0", " ").strip()


def leisu_analysis_readiness(*, has_match_id: bool, has_kickoff: bool, has_odds: bool) -> dict[str, Any]:
    missing = []
    if not has_kickoff:
        missing.append("kickoff_time_missing")
    if not has_odds:
        missing.append("odds_missing")
    if not has_match_id:
        missing.append("match_id_missing")
    return {
        "can_run_single_match_analysis": not missing,
        "grade": "schedule_and_odds_ready" if not missing else "corroboration_only",
        "guaranteed_inputs": {
            "schedule": has_kickoff,
            "match_id": has_match_id,
            "odds_snapshot": has_odds,
        },
        "missing": missing,
        "rule": "Leisu HTML schedule is a corroborating source unless kickoff and odds are resolved by stronger structured sources.",
    }


def parse_leisu_schedule_html(text: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(text or "", "html.parser")
    matches = []
    seen: set[str] = set()
    for row in soup.select(".dd-item.data"):
        detail_link = row.select_one('a[href*="live.leisu.com/detail-"], a[href*="/detail-"]')
        if not detail_link:
            continue
        detail_href = str(detail_link.get("href") or "")
        match_id_match = re.search(r"detail-(\d+)", detail_href)
        if not match_id_match:
            continue
        match_id = match_id_match.group(1)
        if match_id in seen:
            continue
        league_el = row.select_one(".lier-event-name .event-name") or row.select_one(".event-name")
        home_el = row.select_one(".lier-team-home .name")
        away_el = row.select_one(".lier-team-away .name")
        home = clean_leisu_text(home_el.get_text(" ", strip=True) if home_el else "")
        away = clean_leisu_text(away_el.get_text(" ", strip=True) if away_el else "")
        if not home or not away:
            continue
        analysis_link = row.select_one('a[href*="live.leisu.com/shujufenxi-"], a[href*="/shujufenxi-"]')
        analysis_url = str(analysis_link.get("href") or "") if analysis_link else f"https://live.leisu.com/shujufenxi-{match_id}"
        detail_url = detail_href if detail_href.startswith("http") else f"https://live.leisu.com/detail-{match_id}"
        matches.append(
            {
                "source_name": "leisu",
                "match_id": match_id,
                "league": clean_leisu_text(league_el.get_text(" ", strip=True) if league_el else ""),
                "home_team": home,
                "away_team": away,
                "detail_url": detail_url,
                "analysis_url": analysis_url if analysis_url.startswith("http") else f"https://live.leisu.com/shujufenxi-{match_id}",
                "odds_url": f"https://odds.leisu.com/3in1-{match_id}",
                "kickoff_utc": None,
                "kickoff_utc_plus_8": None,
                "analysis_readiness": leisu_analysis_readiness(
                    has_match_id=True,
                    has_kickoff=False,
                    has_odds=False,
                ),
            }
        )
        seen.add(match_id)
    return matches


async def load_leisu_schedule_for_date(local_date: datetime) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    date_str = local_date.astimezone(DEFAULT_USER_TIMEZONE).strftime("%Y%m%d")
    today_str = datetime.now(DEFAULT_USER_TIMEZONE).strftime("%Y%m%d")
    url = LEISU_SCHEDULE_URL if date_str == today_str else LEISU_SCHEDULE_DATE_URL_TEMPLATE.format(date=date_str)
    fetched = await fetch_text(url, headers=LEISU_HEADERS)
    return parse_leisu_schedule_html(fetched.text), evidence(fetched.url, fetched.fetched_at, "leisu.com")


def leisu_odds_access_status(text: str) -> dict[str, Any]:
    lower = (text or "").lower()
    if not text:
        return {
            "status": "empty_response",
            "blocked": True,
            "requires_cookie_or_proxy": True,
            "reason": "empty_response",
        }
    if "aliyun_waf" in lower or "acw_sc__v2" in lower or 'id="renderdata"' in lower:
        return {
            "status": "waf_challenge",
            "blocked": True,
            "requires_cookie_or_proxy": True,
            "reason": "aliyun_waf_acw_sc_v2",
        }
    reason = block_reason(text)
    if reason:
        return {
            "status": "blocked",
            "blocked": True,
            "requires_cookie_or_proxy": True,
            "reason": reason,
        }
    return {
        "status": "ok",
        "blocked": False,
        "requires_cookie_or_proxy": False,
        "reason": "",
    }


def _leisu_mobile_api_enabled() -> bool:
    return os.getenv("LEISU_MOBILE_API_ENABLED", "true").strip().lower() not in {"0", "false", "no", "off"}


def _leisu_mobile_detail_company_limit() -> int:
    raw = os.getenv("LEISU_MOBILE_DETAIL_COMPANY_LIMIT", "3").strip()
    try:
        return max(0, min(int(raw), 30))
    except ValueError:
        return 3


def _leisu_mobile_auth_key(path: str, *, timestamp: int | None = None, nonce: str | None = None) -> str:
    ts = int(timestamp or (time.time() + 10))
    random_nonce = (nonce or uuid.uuid4().hex).replace("-", "")
    digest = hashlib.md5(f"{path}-{ts}-{random_nonce}-0-{LEISU_MOBILE_API_SECRET}".encode("utf-8")).hexdigest()
    return f"{ts}-{random_nonce}-0-{digest}"


def _leisu_mobile_cookie_header() -> str:
    configured_cookie = os.getenv("LEISU_COOKIE", "").strip()
    cookies: list[str] = [configured_cookie] if configured_cookie else ["source=m_leisu"]
    env_acw = os.getenv("LEISU_ACW_SC_V2", "").strip()
    cached_acw = str(_LEISU_MOBILE_WAF_STATE.get("acw_sc__v2") or "").strip()
    cached_tc = str(_LEISU_MOBILE_WAF_STATE.get("acw_tc") or "").strip()
    if env_acw and "acw_sc__v2=" not in configured_cookie:
        cookies.append(f"acw_sc__v2={env_acw}")
    elif cached_acw and "acw_sc__v2=" not in configured_cookie:
        cookies.append(f"acw_sc__v2={cached_acw}")
    if cached_tc and "acw_tc=" not in configured_cookie:
        cookies.append(f"acw_tc={cached_tc}")
    return "; ".join(part for part in cookies if part)


def _leisu_mobile_headers(*, referer: str | None = None) -> dict[str, str]:
    headers = dict(LEISU_MOBILE_HEADERS)
    headers["Referer"] = referer or f"{LEISU_MOBILE_WEBSITE_URL}/"
    cookie_header = _leisu_mobile_cookie_header()
    if cookie_header:
        headers["Cookie"] = cookie_header
    return headers


def _leisu_mobile_caesar(text: str, shift: int) -> str:
    output = []
    for char in str(text or ""):
        code = ord(char)
        if 65 <= code <= 90:
            output.append(chr((code - 65 + shift) % 26 + 65))
        elif 97 <= code <= 122:
            output.append(chr((code - 97 + shift) % 26 + 97))
        else:
            output.append(char)
    return "".join(output)


def decode_leisu_mobile_api_response(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return payload
    try:
        code = int(payload.get("code"))
    except (TypeError, ValueError):
        return payload.get("data", payload)
    data = payload.get("data")
    if code == 0:
        return data
    if not (1 <= code <= 130 and isinstance(data, str)):
        return payload
    shifted = _leisu_mobile_caesar(data, -(code - 100))
    try:
        inflated = gzip.decompress(base64.b64decode(shifted))
    except Exception:
        return payload
    text = inflated.decode("utf-8", errors="replace")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _encode_leisu_mobile_api_payload_for_test(payload: Any, *, shift: int = 14) -> str:
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    encoded = base64.b64encode(gzip.compress(raw)).decode("ascii")
    return _leisu_mobile_caesar(encoded, shift)


def _leisu_mobile_waf_cookie_from_html(text: str, *, url: str, referer: str) -> str:
    node_path = shutil.which("node")
    if not node_path:
        return ""
    script = r"""
const fs = require('fs');
const vm = require('vm');
const html = fs.readFileSync(0, 'utf8');
const url = process.argv[1] || '';
const referer = process.argv[2] || '';
const scripts = [...html.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/g)].map((m) => m[1]);
const renderData = (html.match(/<textarea id="renderData"[^>]*>([\s\S]*?)<\/textarea>/) || [])[1] || '';
let cookie = '';
const document = {
  referrer: referer,
  getElementById(id) {
    return id === 'renderData' ? { innerHTML: renderData } : null;
  },
  location: { reload() {} },
};
Object.defineProperty(document, 'cookie', {
  set(value) {
    if (String(value).startsWith('acw_sc__v2=')) {
      cookie = String(value).split(';')[0].split('=')[1] || '';
    }
  },
  get() { return ''; },
});
const context = {
  document,
  location: { href: url, reload() {} },
  Date,
  JSON,
  String,
  Number,
  Math,
  RegExp,
  Array,
  Object,
  decodeURIComponent,
  encodeURIComponent,
  setTimeout,
  clearTimeout,
  console: { log() {}, error() {} },
  navigator: { userAgent: 'Mozilla/5.0' },
  atob: (value) => Buffer.from(value, 'base64').toString('binary'),
  btoa: (value) => Buffer.from(value, 'binary').toString('base64'),
};
context.window = context;
vm.createContext(context);
if (scripts.length >= 2 && renderData) {
  vm.runInContext(scripts[0], context, { timeout: 5000 });
  vm.runInContext(scripts[1], context, { timeout: 10000 });
}
process.stdout.write(cookie);
"""
    try:
        completed = subprocess.run(
            [node_path, "-e", script, url, referer],
            input=text,
            capture_output=True,
            text=True,
            timeout=12,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return completed.stdout.strip() if completed.returncode == 0 else ""


async def fetch_leisu_mobile_api(
    path: str,
    params: dict[str, Any],
    *,
    referer: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    referer = referer or f"{LEISU_MOBILE_WEBSITE_URL}/"
    active_client = client or await get_client()
    url = f"{LEISU_MOBILE_API_BASE_URL}{path}"

    async def request_once(extra_params: dict[str, Any] | None = None) -> httpx.Response:
        signed_params = dict(params)
        signed_params["auth_key"] = _leisu_mobile_auth_key(path)
        if extra_params:
            signed_params.update(extra_params)
        return await active_client.get(url, params=signed_params, headers=_leisu_mobile_headers(referer=referer))

    response = await request_once()
    if response.cookies.get("acw_tc"):
        _LEISU_MOBILE_WAF_STATE["acw_tc"] = response.cookies.get("acw_tc")

    text = response.text
    waf_solved = False
    if leisu_odds_access_status(text).get("status") == "waf_challenge":
        acw_cookie = _leisu_mobile_waf_cookie_from_html(text, url=str(response.url), referer=referer)
        if not acw_cookie:
            return {
                "status": "waf_challenge",
                "method": "mobile_api",
                "data": None,
                "access": {
                    "status": "waf_challenge",
                    "blocked": True,
                    "requires_cookie_or_proxy": True,
                    "reason": "aliyun_waf_acw_sc_v2_node_unavailable_or_failed",
                },
                "source": evidence(str(response.url), time.time(), "leisu.com"),
            }
        _LEISU_MOBILE_WAF_STATE["acw_sc__v2"] = acw_cookie
        waf_solved = True
        response = await request_once({"alichlgref": referer})
        text = response.text

    access = leisu_odds_access_status(text)
    if access.get("blocked"):
        return {
            "status": access.get("status") or "blocked",
            "method": "mobile_api",
            "data": None,
            "access": access,
            "source": evidence(str(response.url), time.time(), "leisu.com"),
            "waf_solved": waf_solved,
        }
    try:
        raw_payload = response.json()
    except ValueError as exc:
        return {
            "status": "error",
            "method": "mobile_api",
            "data": None,
            "access": {
                "status": "error",
                "blocked": True,
                "requires_cookie_or_proxy": False,
                "reason": f"json_decode_error:{exc}",
            },
            "source": evidence(str(response.url), time.time(), "leisu.com"),
            "waf_solved": waf_solved,
        }
    decoded = decode_leisu_mobile_api_response(raw_payload)
    return {
        "status": "ok" if decoded is not None else "empty",
        "method": "mobile_api",
        "data": decoded,
        "raw_code": raw_payload.get("code") if isinstance(raw_payload, dict) else None,
        "access": {"status": "ok", "blocked": False, "requires_cookie_or_proxy": False, "reason": ""},
        "source": evidence(str(response.url), time.time(), "leisu.com"),
        "waf_solved": waf_solved,
    }


def _balanced_json_after(text: str, start_index: int) -> str:
    start = text.find("{", start_index)
    if start < 0:
        return ""
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return ""


def _find_leisu_market_payload(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        if any(isinstance(value.get(key), list) for key in ("euro", "asia", "size")):
            return value
        for child in value.values():
            found = _find_leisu_market_payload(child)
            if found:
                return found
    if isinstance(value, list):
        for child in value:
            found = _find_leisu_market_payload(child)
            if found:
                return found
    return None


def extract_leisu_odds_payload(text: str) -> dict[str, Any] | None:
    raw = (text or "").strip()
    if not raw:
        return None
    candidates: list[str] = []
    if raw.startswith("{"):
        candidates.append(raw)
    soup = BeautifulSoup(text or "", "html.parser")
    for script in soup.find_all("script"):
        script_text = script.string or script.get_text("\n", strip=False)
        script_type = str(script.get("type") or "").lower()
        script_id = str(script.get("id") or "").lower()
        if "json" in script_type or "odds" in script_id:
            candidates.append(script_text.strip())
        for marker in ("__LEISU_ODDS__", "leisuOddsData", "oddsData"):
            marker_index = script_text.find(marker)
            if marker_index >= 0:
                balanced = _balanced_json_after(script_text, marker_index)
                if balanced:
                    candidates.append(balanced)
    if not candidates and any(key in raw for key in ('"euro"', '"asia"', '"size"')):
        balanced = _balanced_json_after(raw, 0)
        if balanced:
            candidates.append(balanced)

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        found = _find_leisu_market_payload(parsed)
        if found:
            return found
    return None


def _leisu_mobile_primary_values(item: dict[str, Any]) -> list[Any]:
    for key in ("r", "n", "f"):
        value = item.get(key)
        if isinstance(value, list) and value:
            if isinstance(value[0], list):
                return list(value[0])
            return list(value)
    return []


def _leisu_mobile_opening_values(item: dict[str, Any]) -> list[Any]:
    value = item.get("f")
    return list(value) if isinstance(value, list) else []


def _leisu_mobile_bookmaker_name(coop: dict[str, Any], cid: Any) -> str:
    record = coop.get(str(cid)) or coop.get(cid) or {}
    return str(record.get("name") or cid or "").strip()


def _leisu_mobile_detail_rows(detail_payloads: dict[str, Any], market_key: str, cid: Any) -> list[list[Any]]:
    market_details = detail_payloads.get(market_key) or {}
    rows = market_details.get(cid) or market_details.get(str(cid)) or []
    return [row for row in rows if isinstance(row, list) and len(row) >= 5]


def _leisu_mobile_history(market_key: str, rows: list[list[Any]]) -> list[dict[str, Any]]:
    history: list[dict[str, Any]] = []
    for row in rows:
        base = {
            "timestamp": row[0],
            "match_clock": row[1] if len(row) > 1 else "",
            "state": row[5] if len(row) > 5 else "",
            "score": row[7] if len(row) > 7 else "",
        }
        if market_key == "eu":
            history.append(
                {
                    **base,
                    "home": parse_float(row[2]),
                    "draw": parse_float(row[3]),
                    "away": parse_float(row[4]),
                }
            )
        elif market_key == "asia":
            line_label = str(row[3] if len(row) > 3 else "")
            history.append(
                {
                    **base,
                    "home_water": parse_float(row[2]),
                    "line": parse_asian_handicap_line(line_label),
                    "line_label": line_label,
                    "away_water": parse_float(row[4]),
                }
            )
        elif market_key == "bs":
            line_label = str(row[3] if len(row) > 3 else "")
            history.append(
                {
                    **base,
                    "over_water": parse_float(row[2]),
                    "line": parse_goal_line(line_label),
                    "line_label": line_label,
                    "under_water": parse_float(row[4]),
                }
            )
    return history


def _leisu_moneyline_favorite_side(moneyline: list[dict[str, Any]]) -> str:
    """Infer only a clear favorite for Leisu numeric handicap sign recovery."""
    for market in moneyline:
        current = market.get("current") or {}
        home = parse_float(current.get("home"))
        away = parse_float(current.get("away"))
        if home is None or away is None or home <= 1 or away <= 1:
            continue
        gap = abs(home - away)
        relative_gap = gap / max(home, away)
        if gap < 0.1 and relative_gap < 0.03:
            continue
        return "home" if home < away else "away"
    return ""


def _leisu_unsigned_positive_numeric_label(value: Any, line: float | None) -> bool:
    if line is None or line <= 0:
        return False
    if isinstance(value, (int, float)):
        return True
    text = str(value or "").strip()
    if not text or text.startswith(("-", "+")):
        return False
    return parse_float(text) is not None


def _normalize_leisu_numeric_handicap_line(
    line: float | None,
    line_label: Any,
    favorite_side: str,
) -> tuple[float | None, str]:
    if not _leisu_unsigned_positive_numeric_label(line_label, line):
        return line, ""
    if favorite_side == "home":
        return -abs(line or 0.0), "moneyline_favorite"
    if favorite_side == "away":
        return abs(line or 0.0), "moneyline_favorite"
    return line, ""


def _normalize_leisu_asian_history_point(point: dict[str, Any], favorite_side: str) -> dict[str, Any]:
    line_label = point.get("line_label", point.get("line"))
    normalized, source = _normalize_leisu_numeric_handicap_line(
        parse_float(point.get("line")),
        line_label,
        favorite_side,
    )
    if not source:
        return point
    return {**point, "line": normalized, "line_sign_source": source}


def odds_from_leisu_mobile_payload(
    data: dict[str, Any] | None,
    *,
    match_id: str = "",
    detail_payloads: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = data or {}
    detail_payloads = detail_payloads or {}
    coop = data.get("coop") or {}
    payload: dict[str, Any] = {
        "source": "leisu_mobile_api",
        "matchId": str(data.get("matchId") or data.get("match_id") or match_id or ""),
        "euro": [],
        "asia": [],
        "size": [],
    }

    for item in data.get("eu") or []:
        if not isinstance(item, dict):
            continue
        cid = item.get("cid")
        current = _leisu_mobile_primary_values(item)
        opening = _leisu_mobile_opening_values(item)
        history = _leisu_mobile_history("eu", _leisu_mobile_detail_rows(detail_payloads, "eu", cid))
        timestamp = history[0]["timestamp"] if history else ""
        payload["euro"].append(
            {
                "name": _leisu_mobile_bookmaker_name(coop, cid),
                "area": "雷速移动端",
                "cid": cid,
                "now": {
                    "homeWin": current[0] if len(current) > 0 else None,
                    "draw": current[1] if len(current) > 1 else None,
                    "awayWin": current[2] if len(current) > 2 else None,
                    "ts": timestamp,
                },
                "begin": {
                    "homeWin": opening[0] if len(opening) > 0 else None,
                    "draw": opening[1] if len(opening) > 1 else None,
                    "awayWin": opening[2] if len(opening) > 2 else None,
                    "ts": "",
                },
                "history": history,
            }
        )

    for item in data.get("asia") or []:
        if not isinstance(item, dict):
            continue
        cid = item.get("cid")
        current = _leisu_mobile_primary_values(item)
        opening = _leisu_mobile_opening_values(item)
        history = _leisu_mobile_history("asia", _leisu_mobile_detail_rows(detail_payloads, "asia", cid))
        timestamp = history[0]["timestamp"] if history else ""
        payload["asia"].append(
            {
                "name": _leisu_mobile_bookmaker_name(coop, cid),
                "area": "雷速移动端",
                "cid": cid,
                "now": {
                    "homeWin": current[0] if len(current) > 0 else None,
                    "draw": current[1] if len(current) > 1 else None,
                    "awayWin": current[2] if len(current) > 2 else None,
                    "ts": timestamp,
                },
                "begin": {
                    "homeWin": opening[0] if len(opening) > 0 else None,
                    "draw": opening[1] if len(opening) > 1 else None,
                    "awayWin": opening[2] if len(opening) > 2 else None,
                    "ts": "",
                },
                "history": history,
            }
        )

    for item in data.get("bs") or []:
        if not isinstance(item, dict):
            continue
        cid = item.get("cid")
        current = _leisu_mobile_primary_values(item)
        opening = _leisu_mobile_opening_values(item)
        history = _leisu_mobile_history("bs", _leisu_mobile_detail_rows(detail_payloads, "bs", cid))
        timestamp = history[0]["timestamp"] if history else ""
        payload["size"].append(
            {
                "name": _leisu_mobile_bookmaker_name(coop, cid),
                "area": "雷速移动端",
                "cid": cid,
                "now": {
                    "homeWin": current[0] if len(current) > 0 else None,
                    "draw": current[1] if len(current) > 1 else None,
                    "awayWin": current[2] if len(current) > 2 else None,
                    "ts": timestamp,
                },
                "begin": {
                    "homeWin": opening[0] if len(opening) > 0 else None,
                    "draw": opening[1] if len(opening) > 1 else None,
                    "awayWin": opening[2] if len(opening) > 2 else None,
                    "ts": "",
                },
                "history": history,
            }
        )

    return odds_from_leisu_odds_payload(payload, match_id=match_id)


def odds_from_leisu_odds_payload(data: dict[str, Any] | None, *, match_id: str = "") -> dict[str, Any]:
    data = data or {}
    source_name = str(data.get("source") or "leisu_odds")
    moneyline = []
    for item in data.get("euro") or []:
        compact = compact_dongqiudi_market(item)
        current = compact["current"]
        if any(value is not None for value in [current["home"], current["draw"], current["away"]]):
            market = {**compact, "columns": ["leisu_euro"]}
            if item.get("history"):
                market["history"] = item.get("history")
            moneyline.append(market)

    favorite_side = _leisu_moneyline_favorite_side(moneyline)
    asian_handicap = []
    for item in data.get("asia") or []:
        now = item.get("now") or {}
        begin = item.get("begin") or {}
        current_line_label = now.get("draw") or ""
        opening_line_label = begin.get("draw") or ""
        current_line, current_sign_source = _normalize_leisu_numeric_handicap_line(
            parse_asian_handicap_line(current_line_label),
            current_line_label,
            favorite_side,
        )
        opening_line, opening_sign_source = _normalize_leisu_numeric_handicap_line(
            parse_asian_handicap_line(opening_line_label),
            opening_line_label,
            favorite_side,
        )
        history = [
            _normalize_leisu_asian_history_point(point, favorite_side)
            for point in (item.get("history") or [])
            if isinstance(point, dict)
        ]
        market = {
            "provider": item.get("name") or "",
            "area": item.get("area") or "",
            "current": {
                "home_water": parse_float(now.get("homeWin")),
                "line": current_line,
                "line_label": current_line_label,
                "away_water": parse_float(now.get("awayWin")),
                "timestamp": now.get("ts") or "",
            },
            "opening": {
                "home_water": parse_float(begin.get("homeWin")),
                "line": opening_line,
                "line_label": opening_line_label,
                "away_water": parse_float(begin.get("awayWin")),
                "timestamp": begin.get("ts") or "",
            },
            "columns": ["leisu_asia"],
        }
        if current_sign_source:
            market["current"]["line_sign_source"] = current_sign_source
        if opening_sign_source:
            market["opening"]["line_sign_source"] = opening_sign_source
        if history:
            market["history"] = history
        asian_handicap.append(market)

    over_under = []
    for item in data.get("size") or []:
        now = item.get("now") or {}
        begin = item.get("begin") or {}
        current_line_label = now.get("draw") or ""
        opening_line_label = begin.get("draw") or ""
        market = {
            "provider": item.get("name") or "",
            "area": item.get("area") or "",
            "current": {
                "over_water": parse_float(now.get("homeWin")),
                "line": parse_goal_line(current_line_label),
                "line_label": current_line_label,
                "under_water": parse_float(now.get("awayWin")),
                "timestamp": now.get("ts") or "",
            },
            "opening": {
                "over_water": parse_float(begin.get("homeWin")),
                "line": parse_goal_line(opening_line_label),
                "line_label": opening_line_label,
                "under_water": parse_float(begin.get("awayWin")),
                "timestamp": begin.get("ts") or "",
            },
            "columns": ["leisu_size"],
        }
        if item.get("history"):
            market["history"] = item.get("history")
        over_under.append(market)

    preferred_moneyline = select_preferred_moneyline(moneyline)
    preferred_asian_handicap = select_preferred_asian_handicap(asian_handicap)
    preferred_over_under = select_preferred_over_under(over_under)
    odds_payload = with_odds_quality_contract(
        {
            "moneyline_1x2": moneyline,
            "preferred_moneyline_1x2": preferred_moneyline,
            "asian_handicap_markets": asian_handicap,
            "preferred_asian_handicap": preferred_asian_handicap,
            "asian_handicap_consensus": build_asian_handicap_consensus(asian_handicap, preferred_asian_handicap),
            "over_under_markets": over_under,
            "preferred_over_under": preferred_over_under,
            "over_under_consensus": build_over_under_consensus(over_under, preferred_over_under),
            "has_valid_numeric_odds": bool(moneyline or asian_handicap or over_under),
            "market_policy": {
                "moneyline_1x2": "Use preferred_moneyline_1x2 for calculations only after leisu_quality_gate permits promotion.",
                "asian_handicap": "Use preferred_asian_handicap only after inspecting leisu_quality_gate and asian_handicap_consensus.",
                "over_under": "Use preferred_over_under only after inspecting leisu_quality_gate and over_under_consensus.",
                "source": source_name,
            },
            "source_detail": {
                "source": source_name,
                "match_id": str(data.get("matchId") or data.get("match_id") or match_id or ""),
                "raw_market_counts": {
                    "euro": len(data.get("euro") or []),
                    "asia": len(data.get("asia") or []),
                    "size": len(data.get("size") or []),
                },
            },
        }
    )
    return {
        **odds_payload,
        "market_intelligence": build_market_intelligence(odds_payload),
    }


def leisu_odds_quality_gate(odds: dict[str, Any], access: dict[str, Any]) -> dict[str, Any]:
    contract = odds.get("quality_contract") or {}
    hard_flags = list(contract.get("hard_flags") or [])
    soft_flags = list(contract.get("soft_flags") or [])
    if access.get("blocked"):
        hard_flags.append(f"leisu_access_{access.get('status')}")
    if not odds.get("has_valid_numeric_odds"):
        hard_flags.append("leisu_numeric_odds_missing")
    if access.get("requires_cookie_or_proxy"):
        soft_flags.append("leisu_requires_cookie_or_proxy")
    supported = contract.get("supported_markets") or {}
    market_count = len(odds.get("moneyline_1x2") or []) + len(odds.get("asian_handicap_markets") or []) + len(odds.get("over_under_markets") or [])
    return {
        "can_promote_to_model_input": bool(
            odds.get("has_valid_numeric_odds")
            and contract.get("can_use_for_calculation", False)
            and not access.get("blocked")
            and not hard_flags
        ),
        "supported_markets": supported,
        "market_count": market_count,
        "hard_flags": hard_flags,
        "soft_flags": soft_flags,
        "promotion_rule": (
            "Promote Leisu odds only when access is ok, numeric markets are present, "
            "and the shared odds quality contract has no hard flags. Otherwise keep it as audit/context only."
        ),
    }


def parse_leisu_odds_html(text: str, *, match_id: str = "", source_url: str = "") -> dict[str, Any]:
    payload = extract_leisu_odds_payload(text)
    access = leisu_odds_access_status(text)
    if payload:
        access = {**access, "status": "ok", "blocked": False, "requires_cookie_or_proxy": False, "reason": ""}
    odds = odds_from_leisu_odds_payload(payload or {}, match_id=match_id)
    quality_gate = leisu_odds_quality_gate(odds, access)
    return {
        "available": bool(payload and odds.get("has_valid_numeric_odds")),
        "provider": "leisu",
        "match_id": str((payload or {}).get("matchId") or (payload or {}).get("match_id") or match_id or ""),
        "source_url": source_url,
        "access": access,
        "odds": odds,
        "quality_gate": quality_gate,
        "agent_contract": {
            "source_role": "Leisu odds are a high-value multi-company odds source candidate, but require access and quality gates before model promotion.",
            "blocked_rule": "If access.status is waf_challenge or blocked, report that Leisu needs cookie/proxy-assisted fetch instead of inventing odds.",
            "promotion_rule": quality_gate["promotion_rule"],
        },
    }


def _iso_utc_or_empty(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        parsed = date_parser.parse(raw)
    except (TypeError, ValueError):
        return ""
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=DEFAULT_USER_TIMEZONE)
    return parsed.astimezone(timezone.utc).isoformat()


def _leisu_snapshot_source_time(raw_timestamp: Any, fallback_utc: str) -> str:
    parsed = parse_market_timestamp_for_selection(raw_timestamp)
    return parsed.isoformat() if parsed else fallback_utc


def leisu_market_snapshots_from_odds(
    odds: dict[str, Any],
    *,
    match: dict[str, Any] | None = None,
    fetched_at_utc: str | None = None,
) -> list[snapshot_store.MarketSnapshot]:
    match = match or {}
    source_detail = odds.get("source_detail") or {}
    match_id = str(match.get("match_id") or source_detail.get("match_id") or "").strip()
    fetched_at = _iso_utc_or_empty(fetched_at_utc) or now_utc().isoformat()
    home_team = str(match.get("home_team") or "").strip()
    away_team = str(match.get("away_team") or "").strip()
    kickoff_utc = _iso_utc_or_empty(match.get("kickoff_utc") or "")
    if not kickoff_utc and match.get("kickoff_utc_plus_8"):
        kickoff_utc = _iso_utc_or_empty(match.get("kickoff_utc_plus_8"))
    common = {
        "provider": "leisu",
        "source_key": "leisu_odds",
        "event_id": match_id,
        "league": str(match.get("league") or "").strip(),
        "home_team": home_team,
        "away_team": away_team,
        "kickoff_utc": kickoff_utc,
        "fetched_at_utc": fetched_at,
    }
    match_resolution_raw = {
        key: match.get(key)
        for key in (
            "prediction_record_id",
            "leisu_home_team",
            "leisu_away_team",
            "leisu_league",
            "match_resolution_score",
            "match_resolution_reason",
        )
        if match.get(key) not in (None, "")
    }
    snapshots: list[snapshot_store.MarketSnapshot] = []

    def append_snapshot(
        *,
        market: dict[str, Any],
        current: dict[str, Any],
        market_type: str,
        selection: str,
        decimal_odds: float | None,
        line: float | None,
        side: str,
        timestamp: Any,
    ) -> None:
        if decimal_odds is None or decimal_odds <= 1:
            return
        raw_extra = {
            key: current.get(key)
            for key in ("score", "match_clock", "state")
            if current.get(key) not in (None, "")
        }
        snapshots.append(
            snapshot_store.MarketSnapshot(
                **common,
                bookmaker=str(market.get("provider") or market.get("name") or "").strip() or "unknown",
                market_type=market_type,
                selection=selection,
                decimal_odds=round_metric(decimal_odds, 4) or decimal_odds,
                line=line,
                source_time_utc=_leisu_snapshot_source_time(timestamp, fetched_at),
                raw={
                    "source": "leisu_odds",
                    "side": side,
                    "area": market.get("area") or "",
                    "current": current or {},
                    "opening": market.get("opening") or {},
                    "unit_policy": "Asian handicap and totals HK water are normalized to decimal odds before persistence.",
                    **match_resolution_raw,
                    **raw_extra,
                },
            )
        )

    def market_points(market: dict[str, Any]) -> list[dict[str, Any]]:
        history = [item for item in (market.get("history") or []) if isinstance(item, dict)]
        return history or [market.get("current") or {}]

    for market in odds.get("moneyline_1x2") or []:
        for current in market_points(market):
            timestamp = current.get("timestamp")
            append_snapshot(
                market=market,
                current=current,
                market_type="h2h",
                selection=home_team or "home",
                decimal_odds=parse_float(current.get("home")),
                line=None,
                side="home",
                timestamp=timestamp,
            )
            append_snapshot(
                market=market,
                current=current,
                market_type="h2h",
                selection="Draw",
                decimal_odds=parse_float(current.get("draw")),
                line=None,
                side="draw",
                timestamp=timestamp,
            )
            append_snapshot(
                market=market,
                current=current,
                market_type="h2h",
                selection=away_team or "away",
                decimal_odds=parse_float(current.get("away")),
                line=None,
                side="away",
                timestamp=timestamp,
            )

    for market in odds.get("asian_handicap_markets") or []:
        for current in market_points(market):
            line = parse_float(current.get("line"))
            timestamp = current.get("timestamp")
            append_snapshot(
                market=market,
                current=current,
                market_type="asian_handicap",
                selection=home_team or "home",
                decimal_odds=asian_water_to_decimal(current.get("home_water")),
                line=line,
                side="home_cover",
                timestamp=timestamp,
            )
            append_snapshot(
                market=market,
                current=current,
                market_type="asian_handicap",
                selection=away_team or "away",
                decimal_odds=asian_water_to_decimal(current.get("away_water")),
                line=-line if line is not None else None,
                side="away_cover",
                timestamp=timestamp,
            )

    for market in odds.get("over_under_markets") or []:
        for current in market_points(market):
            line = parse_float(current.get("line"))
            timestamp = current.get("timestamp")
            append_snapshot(
                market=market,
                current=current,
                market_type="over_under",
                selection="Over",
                decimal_odds=asian_water_to_decimal(current.get("over_water")),
                line=line,
                side="over",
                timestamp=timestamp,
            )
            append_snapshot(
                market=market,
                current=current,
                market_type="over_under",
                selection="Under",
                decimal_odds=asian_water_to_decimal(current.get("under_water")),
                line=line,
                side="under",
                timestamp=timestamp,
            )

    return snapshots


def _leisu_odds_headers() -> dict[str, str]:
    headers = dict(LEISU_ODDS_HEADERS)
    cookie = os.getenv("LEISU_COOKIE", "").strip()
    acw_cookie = os.getenv("LEISU_ACW_SC_V2", "").strip()
    if cookie:
        headers["Cookie"] = cookie
    elif acw_cookie:
        headers["Cookie"] = f"acw_sc__v2={acw_cookie}"
    return headers


def _leisu_proxy_url(proxy_url: str, *, match_id: str, odds_url: str) -> str:
    if "{match_id}" in proxy_url or "{odds_url}" in proxy_url:
        return proxy_url.format(match_id=match_id, odds_url=odds_url)
    separator = "&" if "?" in proxy_url else "?"
    return f"{proxy_url}{separator}match_id={match_id}"


async def fetch_leisu_mobile_odds_payload(
    *,
    match_id: str,
    detail_company_limit: int | None = None,
) -> dict[str, Any]:
    match_id = str(match_id or "").strip()
    if not match_id:
        return {
            "status": "missing_match_id",
            "method": "mobile_api",
            "payload": None,
            "access": leisu_odds_access_status(""),
        }
    referer = f"{LEISU_MOBILE_WEBSITE_URL}/live/odds-{match_id}"
    list_result = await fetch_leisu_mobile_api(
        LEISU_MOBILE_ODDS_LIST_PATH,
        {"sport_id": 1, "match_id": match_id},
        referer=referer,
    )
    if list_result.get("status") != "ok" or not isinstance(list_result.get("data"), dict):
        return {
            "status": list_result.get("status") or "error",
            "method": "mobile_api",
            "payload": None,
            "access": list_result.get("access") or leisu_odds_access_status(""),
            "source": list_result.get("source") or {},
            "waf_solved": list_result.get("waf_solved", False),
        }

    list_payload = dict(list_result["data"])
    limit = _leisu_mobile_detail_company_limit() if detail_company_limit is None else max(0, int(detail_company_limit))
    detail_payloads: dict[str, dict[Any, Any]] = {"asia": {}, "eu": {}, "bs": {}}
    detail_errors: list[dict[str, Any]] = []

    for market_key, handicap in LEISU_MOBILE_MARKET_HANDICAPS.items():
        market_items = [item for item in (list_payload.get(market_key) or []) if isinstance(item, dict)]
        selected_items = market_items if limit <= 0 else market_items[:limit]
        for item in selected_items:
            cid = item.get("cid")
            if cid in (None, ""):
                continue
            try:
                detail_result = await fetch_leisu_mobile_api(
                    LEISU_MOBILE_ODDS_DETAIL_PATH,
                    {"sport_id": 1, "match_id": match_id, "cid": cid, "handicap": handicap},
                    referer=referer,
                )
            except Exception as exc:
                detail_errors.append(
                    {"market": market_key, "cid": cid, "error": f"{type(exc).__name__}: {exc}"}
                )
                continue
            if detail_result.get("status") == "ok" and isinstance(detail_result.get("data"), list):
                detail_payloads[market_key][cid] = detail_result["data"]
            elif detail_result.get("status") not in {"empty", None}:
                detail_errors.append(
                    {
                        "market": market_key,
                        "cid": cid,
                        "status": detail_result.get("status"),
                        "reason": (detail_result.get("access") or {}).get("reason", ""),
                    }
                )

    odds = odds_from_leisu_mobile_payload(list_payload, match_id=match_id, detail_payloads=detail_payloads)
    classic_payload = {
        "source": "leisu_mobile_api",
        "matchId": match_id,
        "euro": [],
        "asia": [],
        "size": [],
    }
    for market in odds.get("moneyline_1x2") or []:
        classic_payload["euro"].append(
            {
                "name": market.get("provider") or "",
                "area": market.get("area") or "",
                "now": {
                    "homeWin": (market.get("current") or {}).get("home"),
                    "draw": (market.get("current") or {}).get("draw"),
                    "awayWin": (market.get("current") or {}).get("away"),
                    "ts": (market.get("current") or {}).get("timestamp"),
                },
                "begin": {
                    "homeWin": (market.get("opening") or {}).get("home"),
                    "draw": (market.get("opening") or {}).get("draw"),
                    "awayWin": (market.get("opening") or {}).get("away"),
                    "ts": (market.get("opening") or {}).get("timestamp"),
                },
                "history": market.get("history") or [],
            }
        )
    for market in odds.get("asian_handicap_markets") or []:
        classic_payload["asia"].append(
            {
                "name": market.get("provider") or "",
                "area": market.get("area") or "",
                "now": {
                    "homeWin": (market.get("current") or {}).get("home_water"),
                    "draw": (market.get("current") or {}).get("line_label") or (market.get("current") or {}).get("line"),
                    "awayWin": (market.get("current") or {}).get("away_water"),
                    "ts": (market.get("current") or {}).get("timestamp"),
                },
                "begin": {
                    "homeWin": (market.get("opening") or {}).get("home_water"),
                    "draw": (market.get("opening") or {}).get("line_label") or (market.get("opening") or {}).get("line"),
                    "awayWin": (market.get("opening") or {}).get("away_water"),
                    "ts": (market.get("opening") or {}).get("timestamp"),
                },
                "history": market.get("history") or [],
            }
        )
    for market in odds.get("over_under_markets") or []:
        classic_payload["size"].append(
            {
                "name": market.get("provider") or "",
                "area": market.get("area") or "",
                "now": {
                    "homeWin": (market.get("current") or {}).get("over_water"),
                    "draw": (market.get("current") or {}).get("line_label") or (market.get("current") or {}).get("line"),
                    "awayWin": (market.get("current") or {}).get("under_water"),
                    "ts": (market.get("current") or {}).get("timestamp"),
                },
                "begin": {
                    "homeWin": (market.get("opening") or {}).get("over_water"),
                    "draw": (market.get("opening") or {}).get("line_label") or (market.get("opening") or {}).get("line"),
                    "awayWin": (market.get("opening") or {}).get("under_water"),
                    "ts": (market.get("opening") or {}).get("timestamp"),
                },
                "history": market.get("history") or [],
            }
        )

    detail_count = sum(len(rows) for rows_by_cid in detail_payloads.values() for rows in rows_by_cid.values())
    return {
        "status": "ok" if odds.get("has_valid_numeric_odds") else "empty",
        "method": "mobile_api",
        "payload": classic_payload,
        "odds": odds,
        "access": {"status": "ok", "blocked": False, "requires_cookie_or_proxy": False, "reason": ""},
        "source": list_result.get("source") or {},
        "waf_solved": list_result.get("waf_solved", False),
        "mobile_api": {
            "list_market_counts": {
                "asia": len(list_payload.get("asia") or []),
                "eu": len(list_payload.get("eu") or []),
                "bs": len(list_payload.get("bs") or []),
            },
            "detail_company_limit": limit,
            "detail_snapshot_row_count": detail_count,
            "detail_error_count": len(detail_errors),
            "detail_errors": detail_errors[:10],
        },
    }


async def fetch_leisu_odds_page(
    *,
    match_id: str = "",
    odds_url: str = "",
    use_cache: bool = False,
) -> dict[str, Any]:
    match_id = str(match_id or "").strip()
    odds_url = str(odds_url or "").strip() or (LEISU_ODDS_URL_TEMPLATE.format(match_id=match_id) if match_id else "")
    if not odds_url:
        return {
            "status": "missing_match_id",
            "method": "none",
            "match_id": match_id,
            "odds_url": odds_url,
            "text": "",
            "source": {},
            "access": leisu_odds_access_status(""),
        }
    proxy_url = os.getenv("LEISU_ODDS_PROXY_URL", "").strip()
    direct_access_configured = bool(
        proxy_url
        or os.getenv("LEISU_COOKIE", "").strip()
        or os.getenv("LEISU_ACW_SC_V2", "").strip()
    )
    if _leisu_mobile_api_enabled() and match_id and not proxy_url:
        try:
            mobile_result = await fetch_leisu_mobile_odds_payload(match_id=match_id)
        except Exception as exc:
            mobile_result = {
                "status": "error",
                "method": "mobile_api",
                "payload": None,
                "source": {"url": LEISU_MOBILE_API_BASE_URL, "source": "leisu.com"},
                "access": {
                    "status": "error",
                    "blocked": True,
                    "requires_cookie_or_proxy": False,
                    "reason": f"{type(exc).__name__}: {exc}",
                },
                "error": f"{type(exc).__name__}: {exc}",
            }
        if mobile_result.get("payload"):
            source = mobile_result.get("source") or {}
            return {
                "status": "ok",
                "method": "mobile_api",
                "match_id": match_id,
                "odds_url": odds_url,
                "fetch_url": str(source.get("url") or f"{LEISU_MOBILE_API_BASE_URL}{LEISU_MOBILE_ODDS_LIST_PATH}"),
                "source": source,
                "access": mobile_result.get("access") or leisu_odds_access_status(json.dumps(mobile_result.get("payload") or {})),
                "text": json.dumps(mobile_result.get("payload") or {}, ensure_ascii=False),
                "mobile_api": mobile_result.get("mobile_api") or {},
                "waf_solved": mobile_result.get("waf_solved", False),
            }
        if not direct_access_configured:
            source = mobile_result.get("source") or {}
            return {
                "status": mobile_result.get("status") or "empty",
                "method": "mobile_api",
                "match_id": match_id,
                "odds_url": odds_url,
                "fetch_url": str(source.get("url") or f"{LEISU_MOBILE_API_BASE_URL}{LEISU_MOBILE_ODDS_LIST_PATH}"),
                "source": source,
                "access": mobile_result.get("access") or {"status": "ok", "blocked": False, "requires_cookie_or_proxy": False, "reason": ""},
                "text": "",
                "mobile_api": mobile_result.get("mobile_api") or {},
                "waf_solved": mobile_result.get("waf_solved", False),
            }
    method = "proxy" if proxy_url else "direct_http"
    fetch_url = _leisu_proxy_url(proxy_url, match_id=match_id, odds_url=odds_url) if proxy_url else odds_url
    headers = {"Accept": "application/json,text/html,*/*"} if proxy_url else _leisu_odds_headers()
    try:
        fetched = await fetch_text(fetch_url, use_cache=use_cache, headers=headers)
        access = leisu_odds_access_status(fetched.text)
        return {
            "status": "ok" if access.get("status") == "ok" else access.get("status"),
            "method": method,
            "match_id": match_id,
            "odds_url": odds_url,
            "fetch_url": fetch_url,
            "source": evidence(fetched.url, fetched.fetched_at, "leisu.com"),
            "access": access,
            "text": fetched.text,
        }
    except Exception as exc:
        return {
            "status": "error",
            "method": method,
            "match_id": match_id,
            "odds_url": odds_url,
            "fetch_url": fetch_url,
            "source": {"url": fetch_url, "source": "leisu.com"},
            "access": {
                "status": "error",
                "blocked": True,
                "requires_cookie_or_proxy": True,
                "reason": f"{type(exc).__name__}: {exc}",
            },
            "text": "",
            "error": f"{type(exc).__name__}: {exc}",
        }


async def probe_leisu_odds(
    *,
    match_id: str = "",
    odds_url: str = "",
    include_snippet: bool = False,
    snippet_chars: int = 600,
) -> dict[str, Any]:
    fetched = await fetch_leisu_odds_page(match_id=match_id, odds_url=odds_url)
    parsed = parse_leisu_odds_html(
        fetched.get("text") or "",
        match_id=str(fetched.get("match_id") or match_id or ""),
        source_url=str((fetched.get("source") or {}).get("url") or odds_url or ""),
    )
    if not parsed.get("available") and fetched.get("method") == "mobile_api" and fetched.get("access"):
        parsed["access"] = fetched.get("access") or {}
        parsed["quality_gate"] = leisu_odds_quality_gate(parsed.get("odds") or {}, parsed["access"])
    status = "ok" if parsed.get("available") else fetched.get("status") or parsed.get("access", {}).get("status") or "unavailable"
    result = {
        "tool": "probe_leisu_odds",
        "status": status,
        "match_id": parsed.get("match_id") or match_id,
        "odds_url": fetched.get("odds_url") or odds_url,
        "fetch": {key: value for key, value in fetched.items() if key != "text"},
        "available": parsed.get("available"),
        "access": parsed.get("access"),
        "odds": parsed.get("odds"),
        "quality_gate": parsed.get("quality_gate"),
        "agent_contract": parsed.get("agent_contract"),
    }
    if include_snippet:
        result["html_snippet"] = (fetched.get("text") or "")[: max(0, int(snippet_chars or 600))]
    return result


async def fetch_sporttery_match_list() -> tuple[dict[str, Any], dict[str, Any]]:
    cached = _TEXT_CACHE.get(SPORTTERY_MATCH_LIST_URL)
    if cached and time.time() - cached.fetched_at <= CACHE_SECONDS:
        return json.loads(cached.text), evidence(cached.url, cached.fetched_at, "sporttery.cn")

    http_error: Exception | None = None
    proxy_url = os.getenv("SPORTTERY_PROXY_URL", "").strip()
    if proxy_url:
        try:
            fetched = await fetch_text(proxy_url, headers={"Accept": "application/json"})
            data = json.loads(fetched.text)
            cached = CachedText(fetched_at=fetched.fetched_at, text=fetched.text, url=fetched.url)
            _TEXT_CACHE[SPORTTERY_MATCH_LIST_URL] = cached
            return data, evidence(cached.url, cached.fetched_at, "sporttery.cn")
        except Exception as exc:
            http_error = exc

    try:
        fetched = await fetch_text(SPORTTERY_MATCH_LIST_URL, headers=SPORTTERY_HEADERS)
        return json.loads(fetched.text), evidence(fetched.url, fetched.fetched_at, "sporttery.cn")
    except Exception as exc:
        http_error = exc

    process = await asyncio.create_subprocess_exec(
        "curl",
        "-sS",
        "-L",
        "--max-time",
        str(max(3, int(HTTP_TIMEOUT_SECONDS))),
        "-H",
        f"User-Agent: {SPORTTERY_HEADERS['User-Agent']}",
        "-H",
        "Accept: application/json, text/plain, */*",
        "-H",
        "Referer: https://www.sporttery.cn/",
        SPORTTERY_MATCH_LIST_URL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        raise RuntimeError(
            f"Sporttery httpx failed with {type(http_error).__name__}: {http_error}; "
            f"curl failed with code {process.returncode}: {stderr.decode('utf-8', errors='ignore')[:300]}"
        )
    text = stdout.decode("utf-8", errors="replace")
    data = json.loads(text)
    cached = CachedText(fetched_at=time.time(), text=text, url=SPORTTERY_MATCH_LIST_URL)
    _TEXT_CACHE[SPORTTERY_MATCH_LIST_URL] = cached
    return data, evidence(cached.url, cached.fetched_at, "sporttery.cn")


def parse_sporttery_kickoff(match_date: str | None, match_time: str | None) -> datetime | None:
    raw_date = str(match_date or "").strip()
    raw_time = str(match_time or "").strip() or "00:00"
    if not raw_date:
        return None
    try:
        parsed = datetime.strptime(f"{raw_date} {raw_time}", "%Y-%m-%d %H:%M")
    except ValueError:
        return None
    return parsed.replace(tzinfo=DEFAULT_USER_TIMEZONE).astimezone(timezone.utc)


def _sporttery_pool_decimal_odds(item: dict[str, Any]) -> dict[str, Any]:
    odds = {
        "home": parse_float(item.get("h")),
        "draw": parse_float(item.get("d")),
        "away": parse_float(item.get("a")),
    }
    if item.get("goalLine") not in (None, ""):
        odds["goal_line"] = parse_float(item.get("goalLine"))
    return odds


def _sporttery_three_way_probability(odds: dict[str, Any]) -> dict[str, float]:
    values = {key: parse_float(odds.get(key)) for key in ("home", "draw", "away")}
    if any(value is None or value <= 1 for value in values.values()):
        return {}
    raw = {key: 1 / float(value) for key, value in values.items()}
    total = sum(raw.values())
    if not total:
        return {}
    return {key: round_metric(value / total) or 0.0 for key, value in raw.items()}


def _three_way_raw_implied_probability(odds: dict[str, Any]) -> dict[str, float]:
    values = {key: parse_float(odds.get(key)) for key in ("home", "draw", "away")}
    if any(value is None or value <= 1 for value in values.values()):
        return {}
    return {key: round_metric(1 / float(value)) or 0.0 for key, value in values.items()}


def sporttery_analysis_readiness(match: dict[str, Any]) -> dict[str, Any]:
    missing = []
    if not match.get("match_id"):
        missing.append("match_id_missing")
    if not (match.get("home_team") and match.get("away_team") and match.get("kickoff_utc")):
        missing.append("schedule_anchor_missing")
    if "HAD" not in (match.get("selling_pools") or []):
        missing.append("official_had_not_selling")
    had = (match.get("official_odds") or {}).get("HAD") or {}
    if not _sporttery_three_way_probability(had):
        missing.append("official_had_odds_missing")
    return {
        "can_run_single_match_analysis": not missing,
        "grade": "official_jingcai_had_ready" if not missing else "official_jingcai_incomplete",
        "guaranteed_inputs": {
            "schedule": bool(match.get("home_team") and match.get("away_team") and match.get("kickoff_utc")),
            "match_id": bool(match.get("match_id")),
            "official_had_odds": bool(_sporttery_three_way_probability(had)),
        },
        "missing": missing,
        "rule": "Sporttery official Selling HAD fixtures are the primary source for 竞彩胜平负串关 candidates.",
    }


def parse_sporttery_match_list(data: dict[str, Any] | None, source: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for group in (((data or {}).get("value") or {}).get("matchInfoList") or []):
        business_date = group.get("businessDate") or ""
        for item in group.get("subMatchList") or []:
            if item.get("matchStatus") != "Selling":
                continue
            kickoff = parse_sporttery_kickoff(item.get("matchDate"), item.get("matchTime"))
            odds_by_pool = {
                str(odds.get("poolCode") or ""): _sporttery_pool_decimal_odds(odds)
                for odds in item.get("oddsList") or []
                if odds.get("poolCode")
            }
            selling_pools = sorted(
                str(pool.get("poolCode") or "")
                for pool in item.get("poolList") or []
                if pool.get("poolStatus") == "Selling" and pool.get("poolCode")
            )
            match = {
                "source_name": "sporttery",
                "match_id": str(item.get("matchId") or ""),
                "match_num_str": item.get("matchNumStr") or "",
                "business_date": business_date,
                "league": item.get("leagueAbbName") or item.get("leagueAllName") or "",
                "league_full_name": item.get("leagueAllName") or "",
                "home_team": item.get("homeTeamAbbName") or item.get("homeTeamAllName") or "",
                "away_team": item.get("awayTeamAbbName") or item.get("awayTeamAllName") or "",
                "match_status": item.get("matchStatus") or "",
                "match_date": item.get("matchDate") or "",
                "match_time": item.get("matchTime") or "",
                "kickoff_source_timezone": "Asia/Shanghai",
                "kickoff_utc": kickoff.isoformat() if kickoff else None,
                "kickoff_utc_plus_8": kickoff.astimezone(DEFAULT_USER_TIMEZONE).isoformat() if kickoff else None,
                "selling_pools": selling_pools,
                "official_odds": odds_by_pool,
                "source": source,
            }
            match["analysis_readiness"] = sporttery_analysis_readiness(match)
            matches.append(match)
    matches.sort(key=lambda item: (item.get("kickoff_utc_plus_8") or "", item.get("match_num_str") or ""))
    return matches


async def load_sporttery_official_matches(
    as_of: datetime,
    window_minutes: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    data, source = await fetch_sporttery_match_list()
    all_matches = parse_sporttery_match_list(data, source)
    end = as_of + timedelta(minutes=int(window_minutes or JINGCAI_PARLAY_DEFAULT_WINDOW_MINUTES))
    windowed = []
    for match in all_matches:
        kickoff_raw = match.get("kickoff_utc")
        if not kickoff_raw:
            continue
        kickoff = date_parser.parse(kickoff_raw).astimezone(as_of.tzinfo or DEFAULT_USER_TIMEZONE)
        if as_of <= kickoff <= end:
            windowed.append(match)
    return windowed, source


def score_leisu_matches(
    matches: list[dict[str, Any]],
    query: str,
    home_team: str = "",
    away_team: str = "",
    league: str | None = None,
) -> float:
    scores = [
        row_match_score(
            {
                "HomeTeam": str(item.get("home_team") or ""),
                "AwayTeam": str(item.get("away_team") or ""),
                "Div": str(item.get("league") or ""),
            },
            query,
            home_team,
            away_team,
            league,
        )
        for item in matches
    ]
    return max(scores, default=0.0)


async def leisu_schedule_status(local_date: datetime) -> dict[str, Any]:
    try:
        matches, source = await load_leisu_schedule_for_date(local_date)
        return {
            "available": True,
            "source": source,
            "parsed_count": len(matches),
            "sample_matches": matches[:5],
            "role": "Supplemental Chinese schedule/team-name/status/link corroboration. Do not use as the sole analysis or odds source.",
        }
    except Exception as exc:
        return {
            "available": False,
            "source": {"url": LEISU_SCHEDULE_URL, "source": "leisu.com"},
            "error": f"{type(exc).__name__}: {exc}",
            "role": "Supplemental source only; primary analysis should continue from structured sources.",
        }


async def leisu_odds_candidate_for_match(
    *,
    query: str,
    home_team: str = "",
    away_team: str = "",
    league: str | None = None,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    as_of = as_of or datetime.now(DEFAULT_USER_TIMEZONE)
    try:
        matches, source = await load_leisu_schedule_for_date(as_of)
    except Exception as exc:
        return {
            "status": "schedule_unavailable",
            "available": False,
            "source": {"url": LEISU_SCHEDULE_URL, "source": "leisu.com"},
            "error": f"{type(exc).__name__}: {exc}",
        }
    scored = []
    for item in matches:
        score = row_match_score(
            {
                "HomeTeam": str(item.get("home_team") or ""),
                "AwayTeam": str(item.get("away_team") or ""),
                "Div": str(item.get("league") or ""),
            },
            query,
            home_team,
            away_team,
            league,
        )
        scored.append((score, item))
    scored.sort(key=lambda row: row[0], reverse=True)
    if not scored or scored[0][0] < MATCH_SCORE_THRESHOLD:
        return {
            "status": "not_found",
            "available": False,
            "source": source,
            "candidate_count": len(matches),
            "best_score": round_metric(scored[0][0]) if scored else None,
        }
    return {
        "status": "candidate_found",
        "available": True,
        "source": source,
        "match_score": round_metric(scored[0][0]),
        "match": scored[0][1],
        "candidate_count": len(matches),
    }


async def leisu_odds_context_for_match(
    *,
    query: str,
    home_team: str = "",
    away_team: str = "",
    league: str | None = None,
    as_of: datetime | None = None,
) -> dict[str, Any]:
    candidate = await leisu_odds_candidate_for_match(
        query=query,
        home_team=home_team,
        away_team=away_team,
        league=league,
        as_of=as_of,
    )
    auto_probe = os.getenv("FOOTBALL_DATA_LEISU_ODDS_AUTO_PROBE", "").strip().lower() in {"1", "true", "yes", "on"}
    if not candidate.get("available"):
        return {
            **candidate,
            "provider": "leisu",
            "auto_probe_enabled": auto_probe,
        }
    match = candidate.get("match") or {}
    if not auto_probe:
        return {
            **candidate,
            "provider": "leisu",
            "auto_probe_enabled": False,
            "guidance": (
                "Leisu odds candidate is available. Call probe_leisu_odds explicitly, "
                "or set FOOTBALL_DATA_LEISU_ODDS_AUTO_PROBE=true to auto-probe from data bundles."
            ),
        }
    probed = await probe_leisu_odds(
        match_id=str(match.get("match_id") or ""),
        odds_url=str(match.get("odds_url") or ""),
    )
    return {
        **probed,
        "provider": "leisu",
        "auto_probe_enabled": True,
        "schedule_candidate": candidate,
    }


def snippet_for_query(text: str, query: str, *, max_chars: int = 500) -> str:
    soup = BeautifulSoup(text or "", "html.parser")
    visible = soup.get_text(" ", strip=True)
    visible = re.sub(r"\s+", " ", visible)
    if not visible:
        return ""
    tokens = [token for token in normalize_text(query).split() if len(token) > 2]
    lowered = visible.lower()
    positions = [lowered.find(token) for token in tokens if lowered.find(token) >= 0]
    if positions:
        start = max(min(positions) - 160, 0)
        return visible[start:start + max_chars]
    return visible[:max_chars]


def parse_visible_match_score(text: str, query: str, home_team: str = "", away_team: str = "") -> float:
    visible = BeautifulSoup(text or "", "html.parser").get_text(" ", strip=True)
    visible_norm = normalize_text(visible)
    if not visible_norm:
        return 0.0
    terms = []
    for item in [query, home_team, away_team]:
        terms.extend(token for token in normalize_text(item).split() if len(token) > 2)
    unique_terms = list(dict.fromkeys(terms))
    if not unique_terms:
        return 0.0
    hits = sum(1 for term in unique_terms if term in visible_norm)
    return round(hits / len(unique_terms), 4)


async def probe_sources(
    query: str = "",
    *,
    home_team: str | None = None,
    away_team: str | None = None,
    limit_chars: int = 500,
) -> dict[str, Any]:
    """Probe configured public data sources and report current parseability."""

    translated_query, parsed_home, parsed_away = parse_match_query(query, home_team, away_team)

    async def probe_one(source: dict[str, str]) -> dict[str, Any]:
        started = time.time()
        try:
            is_leisu = source.get("key") == "leisu_schedule"
            fetched = await fetch_text(source["url"], headers=LEISU_HEADERS if is_leisu else None)
            text = fetched.text
            title = html_title(text) if source["kind"].startswith("html") else "CSV"
            rows = parse_csv(text) if source["kind"] == "csv_odds" else []
            leisu_matches = parse_leisu_schedule_html(text) if is_leisu else []
            reason = source_block_reason(source.get("key") or "", text, parsed_match_count=len(leisu_matches))
            numeric_rows = (
                sum(1 for row in rows if odds_from_row(row)["has_valid_numeric_odds"])
                if rows
                else None
            )
            if rows:
                match_hint_score = max(
                    [
                        row_match_score(row, translated_query, parsed_home, parsed_away)
                        for row in rows[:5000]
                    ],
                    default=0.0,
                )
            elif leisu_matches:
                match_hint_score = score_leisu_matches(
                    leisu_matches,
                    translated_query,
                    parsed_home,
                    parsed_away,
                )
            else:
                match_hint_score = parse_visible_match_score(text, translated_query, parsed_home, parsed_away)
            return {
                **source,
                "ok": reason is None and bool(text) and (not is_leisu or bool(leisu_matches)),
                "blocked_or_low_value_reason": reason,
                "http_parse": {
                    "title": title,
                    "bytes": len(text.encode("utf-8", errors="ignore")),
                    "latency_ms": round((time.time() - started) * 1000),
                    "fetched_at_utc": datetime.fromtimestamp(fetched.fetched_at, tz=timezone.utc).isoformat(),
                },
                "csv_rows": len(rows) if rows else None,
                "rows_with_numeric_odds": numeric_rows,
                "parsed_matches": len(leisu_matches) if is_leisu else None,
                "sample_matches": leisu_matches[:3] if is_leisu else None,
                "match_hint_score": match_hint_score,
                "snippet": (
                    snippet_for_query(text, translated_query, max_chars=limit_chars)
                    if source["kind"].startswith("html")
                    else ""
                ),
            }
        except Exception as exc:
            return {
                **source,
                "ok": False,
                "blocked_or_low_value_reason": type(exc).__name__,
                "error": str(exc),
                "http_parse": {"latency_ms": round((time.time() - started) * 1000)},
            }

    probes = await asyncio.gather(*(probe_one(source) for source in PROBE_SOURCES))
    usable = [item for item in probes if item.get("ok")]
    return {
        "query": query,
        "translated_query": translated_query,
        "parsed_home_team": parsed_home,
        "parsed_away_team": parsed_away,
        "usable_source_count": len(usable),
        "sources": probes,
        "selection_policy": {
            "primary_numeric_odds": "football_data_fixtures",
            "corroborating_sources": [
                item["key"]
                for item in probes
                if item.get("ok") and item.get("key") != "football_data_fixtures"
            ],
            "rule": (
                "Use numeric odds only when a source exposes concrete numbers. "
                "Use other sources for schedule/context corroboration when parseable."
            ),
        },
    }


def season_code_for(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    year = dt.astimezone(timezone.utc).year
    if dt.month >= 7:
        start_year = year
        end_year = year + 1
    else:
        start_year = year - 1
        end_year = year
    return f"{start_year % 100:02d}{end_year % 100:02d}"


def parse_as_of(as_of: str | None, timezone_name: str | None = None) -> datetime:
    tz = ZoneInfo(timezone_name or "Asia/Shanghai")
    if not as_of:
        return datetime.now(tz)
    parsed = date_parser.parse(as_of)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=tz)
    return parsed.astimezone(tz)


def time_window_policy(as_of: datetime, window_hours: int, *, as_of_supplied: bool = False) -> dict[str, Any]:
    """Return one canonical time-window description for downstream agents."""
    tz = as_of.tzinfo or DEFAULT_USER_TIMEZONE
    local = as_of.astimezone(tz)
    end = local + timedelta(hours=window_hours)
    return {
        "as_of": local.isoformat(),
        "as_of_utc": local.astimezone(timezone.utc).isoformat(),
        "window_end": end.isoformat(),
        "window_end_utc": end.astimezone(timezone.utc).isoformat(),
        "timezone": getattr(tz, "key", str(tz)),
        "window_hours": window_hours,
        "as_of_source": "caller_supplied" if as_of_supplied else "server_current_time",
        "definition": "[T0, T0+24h] by default. T0 is the user's current request time; agents should not invent or relabel timezones.",
    }


def parse_kickoff(row: dict[str, str]) -> datetime | None:
    raw_date = row.get("Date") or ""
    raw_time = row.get("Time") or "00:00"
    if not raw_date:
        return None
    try:
        naive = datetime.strptime(f"{raw_date} {raw_time}", "%d/%m/%Y %H:%M")
    except ValueError:
        try:
            naive = datetime.strptime(raw_date, "%d/%m/%Y")
        except ValueError:
            return None
    return naive.replace(tzinfo=SOURCE_TIMEZONE)


def parse_dongqiudi_kickoff(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        parsed = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        try:
            parsed = date_parser.parse(raw)
        except (ValueError, TypeError):
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def normalize_text(value: str) -> str:
    value = value or ""
    for cn_name, english in sorted(TEAM_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        value = value.replace(cn_name, english)
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.lower()
    value = re.sub(r"\b(fc|cf|afc|sc)\b", " ", value)
    value = re.sub(r"u(?:23|21|20|19|18|17|16|15|14|13)(?=\s|$)", " ", value)
    value = re.sub(r"[^\w]+", " ", value, flags=re.UNICODE)
    return re.sub(r"\s+", " ", value).strip()


def parse_match_query(query: str, home_team: str | None = None, away_team: str | None = None) -> tuple[str, str, str]:
    query = query or ""
    if home_team and away_team:
        return query, home_team, away_team

    translated = query
    for cn_name, english in sorted(TEAM_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        translated = translated.replace(cn_name, f" {english} ")
    translated = re.sub(r"\s+", " ", translated).strip()

    parts = re.split(
        r"\s*(?<![A-Za-z])(?:vs\.?|v\.?|versus)(?![A-Za-z])\s*|\s*(?:对阵|對陣|主场对|客场对|对)\s*|[-–—]",
        translated,
        maxsplit=1,
        flags=re.I,
    )
    if len(parts) >= 2:
        left = parts[0].strip(" :，,")
        right = parts[1].strip(" :，,")
        return translated, home_team or left, away_team or right
    return translated, home_team or "", away_team or ""


def similarity(a: str, b: str) -> float:
    raw_a = (a or "").strip().lower()
    raw_b = (b or "").strip().lower()
    if raw_a and raw_b:
        if raw_a == raw_b:
            return 1.0
        if raw_a in raw_b or raw_b in raw_a:
            return 0.92
    a_norm = normalize_text(a)
    b_norm = normalize_text(b)
    if not a_norm or not b_norm:
        return 0.0
    if a_norm == b_norm:
        return 1.0
    if a_norm in b_norm or b_norm in a_norm:
        return 0.92
    return SequenceMatcher(None, a_norm, b_norm).ratio()


def row_match_score(
    row: dict[str, str],
    query: str,
    home_team: str = "",
    away_team: str = "",
    league: str | None = None,
) -> float:
    home = row.get("HomeTeam") or ""
    away = row.get("AwayTeam") or ""
    division = row.get("Div") or ""
    scores: list[float] = []
    if home_team:
        scores.append(similarity(home_team, home))
    if away_team:
        scores.append(similarity(away_team, away))
    if not scores:
        combined = f"{home} vs {away}"
        scores.append(similarity(query, combined))
    score = sum(scores) / len(scores)
    if league:
        league_name = LEAGUE_NAMES.get(division, division)
        score = score * 0.85 + similarity(league, league_name) * 0.15
    return round(score, 4)


def odds_from_row(row: dict[str, str]) -> dict[str, Any]:
    moneyline = []
    for name, (home_key, draw_key, away_key) in BOOKMAKER_FIELDS.items():
        home = parse_float(row.get(home_key))
        draw = parse_float(row.get(draw_key))
        away = parse_float(row.get(away_key))
        if any(value is not None for value in [home, draw, away]):
            moneyline.append(
                {
                    "provider": name,
                    "home": home,
                    "draw": draw,
                    "away": away,
                    "columns": [home_key, draw_key, away_key],
                }
            )

    over_under = []
    for name, (over_key, under_key) in OVER_UNDER_FIELDS.items():
        over = parse_float(row.get(over_key))
        under = parse_float(row.get(under_key))
        if over is not None or under is not None:
            over_under.append(
                {
                    "provider": name,
                    "over_2_5": over,
                    "under_2_5": under,
                    "columns": [over_key, under_key],
                }
            )

    handicap = {
        label: parse_float(row.get(key))
        for label, key in HANDICAP_FIELDS.items()
        if parse_float(row.get(key)) is not None
    }

    return {
        "moneyline_1x2": moneyline,
        "over_under": over_under,
        "asian_handicap": handicap,
        "has_valid_numeric_odds": bool(moneyline or over_under or handicap),
    }


def parse_comma_floats(value: str | None, expected: int = 3) -> list[float | None]:
    parts = str(value or "").split(",")
    parsed = [parse_float(part) for part in parts]
    while len(parsed) < expected:
        parsed.append(None)
    return parsed[:expected]


def odds_from_dongqiudi_match(match: dict[str, Any]) -> dict[str, Any]:
    score_odds = match.get("score_odds") or {}
    origin = score_odds.get("origin") or []
    spot = score_odds.get("spot") or []

    moneyline = []
    for label, values in [("Dongqiudi opening 1X2", origin[1] if len(origin) > 1 else ""), ("Dongqiudi current 1X2", spot[1] if len(spot) > 1 else "")]:
        home, draw, away = parse_comma_floats(values)
        if any(value is not None and value > 0 for value in [home, draw, away]):
            moneyline.append({"provider": label, "home": home, "draw": draw, "away": away, "columns": ["score_odds"]})

    asian_handicap = {}
    for prefix, values in [("opening", origin[0] if origin else ""), ("current", spot[0] if spot else "")]:
        home_water, line, away_water = parse_comma_floats(values)
        if any(value is not None and value > 0 for value in [home_water, line, away_water]):
            asian_handicap[f"Dongqiudi {prefix} AH home water"] = home_water
            asian_handicap[f"Dongqiudi {prefix} AH line"] = line
            asian_handicap[f"Dongqiudi {prefix} AH away water"] = away_water

    over_under = []
    for label, values in [("Dongqiudi opening over/under", origin[2] if len(origin) > 2 else ""), ("Dongqiudi current over/under", spot[2] if len(spot) > 2 else "")]:
        over_water, line, under_water = parse_comma_floats(values)
        if any(value is not None and value > 0 for value in [over_water, line, under_water]):
            over_under.append(
                {
                    "provider": label,
                    "line": line,
                    "over": over_water,
                    "under": under_water,
                    "columns": ["score_odds"],
                }
            )

    return {
        "moneyline_1x2": moneyline,
        "over_under": over_under,
        "asian_handicap": asian_handicap,
        "has_valid_numeric_odds": bool(moneyline or over_under or asian_handicap),
        "raw_fields": {
            "score_odds": score_odds,
            "sporttery_str": match.get("sporttery_str") or "",
            "hdp_odds": match.get("hdp_odds") or "",
            "total_odds": match.get("total_odds") or "",
        },
    }


def odds_from_sporttery_fixture(match: dict[str, Any]) -> dict[str, Any]:
    had = ((match.get("official_odds") or {}).get("HAD") or {})
    hhad = ((match.get("official_odds") or {}).get("HHAD") or {})
    home = parse_float(had.get("home"))
    draw = parse_float(had.get("draw"))
    away = parse_float(had.get("away"))
    moneyline = []
    preferred_moneyline = None
    if all(value is not None and value > 1 for value in [home, draw, away]):
        snapshot_timestamp = str(((match.get("source") or {}).get("fetched_at_utc") or "")).strip()
        moneyline.append(
            {
                "provider": "Sporttery official HAD",
                "home": home,
                "draw": draw,
                "away": away,
                "columns": ["official_odds.HAD"],
            }
        )
        preferred_moneyline = {
            "provider": "Sporttery official HAD",
            "current": {
                "home": home,
                "draw": draw,
                "away": away,
                "timestamp": snapshot_timestamp,
            },
            "opening": {},
            "market_scope": "jingcai_supported",
        }
    official_hhad = None
    hhad_home = parse_float(hhad.get("home"))
    hhad_draw = parse_float(hhad.get("draw"))
    hhad_away = parse_float(hhad.get("away"))
    hhad_goal_line = parse_float(hhad.get("goal_line"))
    if all(value is not None and value > 1 for value in [hhad_home, hhad_draw, hhad_away]) and hhad_goal_line is not None:
        hhad_raw = _three_way_raw_implied_probability(hhad)
        hhad_normalized = _sporttery_three_way_probability(hhad)
        hhad_sum = sum(hhad_raw.values())
        official_hhad = {
            "market_type": "official_let_goal_3way",
            "pool_code": "HHAD",
            "provider": "Sporttery official HHAD",
            "home_goal_line": hhad_goal_line,
            "current": {
                "home": hhad_home,
                "draw": hhad_draw,
                "away": hhad_away,
                "timestamp": str(((match.get("source") or {}).get("fetched_at_utc") or "")).strip(),
            },
            "current_metrics": {
                "available": True,
                "odds": {"home": hhad_home, "draw": hhad_draw, "away": hhad_away},
                "raw_implied_probability": hhad_raw,
                "raw_probability_sum": round_metric(hhad_sum),
                "overround": round_metric(hhad_sum - 1) if hhad_sum else None,
                "payout_rate": round_metric(1 / hhad_sum) if hhad_sum else None,
                "normalized_probability": hhad_normalized,
            },
            "settlement_rule": (
                "竞彩让球胜平负按 home_score + home_goal_line 与 away_score 比较结算；"
                "home/draw/away 分别对应让胜/让平/让负。"
            ),
            "agent_rule": (
                "This is Sporttery official let-goal 3-way HHAD, not an Asian handicap market. "
                "Do not relabel it as 亚盘 or convert it into two-way Asian handicap cover probabilities."
            ),
        }
    return {
        "moneyline_1x2": moneyline,
        "preferred_moneyline_1x2": preferred_moneyline,
        "official_jingcai_hhad": official_hhad,
        "over_under": [],
        "asian_handicap": {},
        "has_valid_numeric_odds": bool(moneyline),
        "market_policy": {
            "moneyline_1x2": "Sporttery official HAD is the primary official Jingcai 胜平负 price for this fixture.",
            "official_jingcai_hhad": (
                "Sporttery official HHAD is 竞彩让球胜平负, a home-goal-line 3-way market; "
                "it is not an Asian handicap market."
            ),
            "source": "sporttery_official_match_list",
        },
        "raw_fields": {
            "source_name": "sporttery",
            "match_num_str": match.get("match_num_str") or "",
            "selling_pools": match.get("selling_pools") or [],
            "official_odds": match.get("official_odds") or {},
        },
    }


def compact_dongqiudi_market(item: dict[str, Any]) -> dict[str, Any]:
    now = item.get("now") or {}
    begin = item.get("begin") or {}
    return {
        "provider": item.get("name") or "",
        "area": item.get("area") or "",
        "current": {
            "home": parse_float(now.get("homeWin")),
            "draw": parse_float(now.get("draw")),
            "away": parse_float(now.get("awayWin")),
            "timestamp": now.get("ts") or "",
        },
        "opening": {
            "home": parse_float(begin.get("homeWin")),
            "draw": parse_float(begin.get("draw")),
            "away": parse_float(begin.get("awayWin")),
            "timestamp": begin.get("ts") or "",
        },
    }


CHINESE_HANDICAP_LINES = {
    "平": 0.0,
    "平手": 0.0,
    "平/半": 0.25,
    "平半": 0.25,
    "半": 0.5,
    "半球": 0.5,
    "半/一": 0.75,
    "半一": 0.75,
    "一": 1.0,
    "一球": 1.0,
    "一/球半": 1.25,
    "一/半": 1.25,
    "一半": 1.25,
    "球半": 1.5,
    "球半/两": 1.75,
    "球半/两球": 1.75,
    "两": 2.0,
    "两球": 2.0,
    "两/两半": 2.25,
    "两球/两球半": 2.25,
    "两半": 2.5,
    "两球半": 2.5,
    "两半/三": 2.75,
    "两球半/三球": 2.75,
    "三": 3.0,
    "三球": 3.0,
}


def parse_asian_handicap_line(value: Any) -> float | None:
    numeric = parse_float(value)
    if numeric is not None:
        return numeric
    text = re.sub(r"\s+", "", str(value or ""))
    if not text:
        return None
    is_home_underdog = text.startswith("受")
    if is_home_underdog:
        text = text[1:]
    magnitude = CHINESE_HANDICAP_LINES.get(text)
    if magnitude is None:
        return None
    if magnitude == 0:
        return 0.0
    return magnitude if is_home_underdog else -magnitude


def parse_goal_line(value: Any) -> float | None:
    numeric = parse_float(value)
    if numeric is not None:
        return numeric
    text = re.sub(r"\s+", "", str(value or ""))
    if not text:
        return None
    parts = text.split("/")
    parsed = [parse_float(part) for part in parts]
    parsed = [part for part in parsed if part is not None]
    if len(parsed) == len(parts) and parsed:
        return round_metric(sum(parsed) / len(parsed))
    return None


def odds_from_dongqiudi_odds_index(data: dict[str, Any] | None) -> dict[str, Any]:
    data = data or {}
    euro = data.get("euro") or []
    asia = data.get("asia") or []
    size = data.get("size") or []
    moneyline = []

    preferred_names = {"竞彩官方", "平均值", "最高值", "最低值"}
    for item in euro:
        compact = compact_dongqiudi_market(item)
        current = compact["current"]
        if item.get("name") in preferred_names or item.get("area") in {"中国", "英国", "澳门", "亚洲"}:
            if any(value is not None for value in [current["home"], current["draw"], current["away"]]):
                moneyline.append({**compact, "columns": ["euro"]})
        if len(moneyline) >= 10:
            break

    for key in ["avg", "max", "min"]:
        if isinstance(data.get(key), dict):
            compact = compact_dongqiudi_market(data[key])
            current = compact["current"]
            if any(value is not None for value in [current["home"], current["draw"], current["away"]]):
                moneyline.append({**compact, "columns": [key]})

    asian_handicap = []
    for item in asia:
        now = item.get("now") or {}
        begin = item.get("begin") or {}
        current_line_label = now.get("draw") or ""
        opening_line_label = begin.get("draw") or ""
        asian_handicap.append(
            {
                "provider": item.get("name") or "",
                "area": item.get("area") or "",
                "current": {
                    "home_water": parse_float(now.get("homeWin")),
                    "line": parse_asian_handicap_line(current_line_label),
                    "line_label": current_line_label,
                    "away_water": parse_float(now.get("awayWin")),
                    "timestamp": now.get("ts") or "",
                },
                "opening": {
                    "home_water": parse_float(begin.get("homeWin")),
                    "line": parse_asian_handicap_line(opening_line_label),
                    "line_label": opening_line_label,
                    "away_water": parse_float(begin.get("awayWin")),
                    "timestamp": begin.get("ts") or "",
                },
                "columns": ["asia"],
            }
        )

    over_under = []
    for item in size[:10]:
        now = item.get("now") or {}
        begin = item.get("begin") or {}
        current_line_label = now.get("draw") or ""
        opening_line_label = begin.get("draw") or ""
        over_under.append(
            {
                "provider": item.get("name") or "",
                "area": item.get("area") or "",
                "current": {
                    "over_water": parse_float(now.get("homeWin")),
                    "line": parse_goal_line(current_line_label),
                    "line_label": current_line_label,
                    "under_water": parse_float(now.get("awayWin")),
                    "timestamp": now.get("ts") or "",
                },
                "opening": {
                    "over_water": parse_float(begin.get("homeWin")),
                    "line": parse_goal_line(opening_line_label),
                    "line_label": opening_line_label,
                    "under_water": parse_float(begin.get("awayWin")),
                    "timestamp": begin.get("ts") or "",
                },
            }
        )

    preferred_moneyline = select_preferred_moneyline(moneyline)
    preferred_asian_handicap = select_preferred_asian_handicap(asian_handicap)
    asian_handicap_consensus = build_asian_handicap_consensus(asian_handicap, preferred_asian_handicap)
    preferred_over_under = select_preferred_over_under(over_under)
    over_under_consensus = build_over_under_consensus(over_under, preferred_over_under)

    odds_payload = with_odds_quality_contract({
        "moneyline_1x2": moneyline,
        "preferred_moneyline_1x2": preferred_moneyline,
        "asian_handicap_markets": asian_handicap,
        "preferred_asian_handicap": preferred_asian_handicap,
        "asian_handicap_consensus": asian_handicap_consensus,
        "over_under_markets": over_under,
        "preferred_over_under": preferred_over_under,
        "over_under_consensus": over_under_consensus,
        "has_valid_numeric_odds": bool(data.get("has_odds")) and bool(moneyline or asian_handicap or over_under),
        "market_policy": {
            "moneyline_1x2": "Use preferred_moneyline_1x2 for calculations and recommendations. Keep moneyline_1x2 as audit evidence only.",
            "asian_handicap": "Use the freshest complete non-outlier preferred_asian_handicap from the main consensus line. Do not mix handicap waters with 1X2 prices.",
            "asian_handicap_consensus": "Read asian_handicap_consensus together with preferred_asian_handicap before any Asian handicap recommendation.",
            "over_under_consensus": "Read over_under_consensus together with preferred_over_under before any totals recommendation.",
            "preferred_order": ["main_consensus_line", "exclude_decimal_price_outliers", "freshest_complete_market", "竞彩官方", "平均值", "最高值", "最低值"],
            "source": "dongqiudi_odds_index",
        },
        "source_detail": {
            "match_id": data.get("matchId"),
            "is_spe": data.get("is_spe"),
        },
    })
    return {
        **odds_payload,
        "market_intelligence": build_market_intelligence(odds_payload),
    }


def select_preferred_moneyline(markets: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Pick one 1X2 market so agents do not mix official odds with schedule snapshots."""
    complete = [
        market
        for market in markets
        if all((market.get("current") or {}).get(key) is not None for key in ("home", "draw", "away"))
    ]
    candidates = complete or markets
    for provider in ["竞彩官方", "平均值", "最高值", "最低值"]:
        for market in candidates:
            if market.get("provider") == provider:
                return market
    return candidates[0] if candidates else None


def is_complete_asian_handicap_market(market: dict[str, Any]) -> bool:
    current = market.get("current") or {}
    return all(current.get(key) is not None for key in ("home_water", "line", "away_water"))


def is_complete_over_under_market(market: dict[str, Any]) -> bool:
    current = market.get("current") or {}
    return all(current.get(key) is not None for key in ("over_water", "line", "under_water"))


def average_metric(values: list[float]) -> float | None:
    if not values:
        return None
    return round_metric(sum(values) / len(values))


def median_metric(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        return round_metric(ordered[midpoint])
    return round_metric((ordered[midpoint - 1] + ordered[midpoint]) / 2)


def line_label_for_group(markets: list[dict[str, Any]]) -> str:
    labels = [
        str((market.get("current") or {}).get("line_label") or "").strip()
        for market in markets
        if str((market.get("current") or {}).get("line_label") or "").strip()
    ]
    if not labels:
        return ""
    return Counter(labels).most_common(1)[0][0]


def compact_asian_handicap_market_for_consensus(market: dict[str, Any] | None) -> dict[str, Any] | None:
    if not market:
        return None
    current = market.get("current") or {}
    parsed_timestamp = parse_market_timestamp_for_selection(current.get("timestamp"))
    metrics = asian_handicap_probability_metrics(current)
    return {
        "provider": market.get("provider") or "",
        "area": market.get("area") or "",
        "line": current.get("line"),
        "line_label": current.get("line_label") or "",
        "home_water": current.get("home_water"),
        "away_water": current.get("away_water"),
        "decimal_odds": metrics.get("decimal_odds") or {},
        "normalized_probability": metrics.get("normalized_probability") or {},
        "timestamp": current.get("timestamp") or "",
        "parsed_timestamp_utc": parsed_timestamp.isoformat() if parsed_timestamp else None,
    }


def _price_deviation(value: float | None, median_value: float | None) -> float | None:
    if value is None or median_value is None or median_value <= 0:
        return None
    return round_metric(abs(value - median_value) / median_value)


def _max_deviation(deviations: list[float | None]) -> float | None:
    usable = [item for item in deviations if item is not None]
    return max(usable) if usable else None


def _normalized_two_way_probability(first_decimal: float | None, second_decimal: float | None) -> dict[str, float]:
    if not first_decimal or not second_decimal or first_decimal <= 1 or second_decimal <= 1:
        return {}
    first_raw = 1 / first_decimal
    second_raw = 1 / second_decimal
    total = first_raw + second_raw
    if not total:
        return {}
    return {
        "first": round_metric(first_raw / total) or 0,
        "second": round_metric(second_raw / total) or 0,
    }


def _asian_market_decimal_odds(market: dict[str, Any]) -> dict[str, float | None]:
    current = market.get("current") or {}
    return {
        "home_cover": asian_water_to_decimal(current.get("home_water")),
        "away_cover": asian_water_to_decimal(current.get("away_water")),
    }


def _asian_price_consensus_for_group(group_markets: list[dict[str, Any]]) -> dict[str, Any]:
    home_decimals = [
        asian_water_to_decimal((market.get("current") or {}).get("home_water"))
        for market in group_markets
    ]
    away_decimals = [
        asian_water_to_decimal((market.get("current") or {}).get("away_water"))
        for market in group_markets
    ]
    home_decimals = [item for item in home_decimals if item is not None]
    away_decimals = [item for item in away_decimals if item is not None]
    median_home = median_metric(home_decimals)
    median_away = median_metric(away_decimals)
    probability = _normalized_two_way_probability(median_home, median_away)
    line = parse_float((group_markets[0].get("current") or {}).get("line")) if group_markets else None
    outliers = []
    for market in group_markets:
        current = market.get("current") or {}
        decimal_odds = _asian_market_decimal_odds(market)
        home_deviation = _price_deviation(decimal_odds.get("home_cover"), median_home)
        away_deviation = _price_deviation(decimal_odds.get("away_cover"), median_away)
        max_deviation = _max_deviation([home_deviation, away_deviation])
        if max_deviation is not None and max_deviation >= PRICE_OUTLIER_DEVIATION_THRESHOLD:
            outliers.append(
                {
                    "provider": market.get("provider") or "",
                    "area": market.get("area") or "",
                    "line": current.get("line"),
                    "line_label": current.get("line_label") or "",
                    "timestamp": current.get("timestamp") or "",
                    "decimal_odds": decimal_odds,
                    "deviation_from_median": {
                        "home_cover": home_deviation,
                        "away_cover": away_deviation,
                        "max": max_deviation,
                    },
                    "reason": "decimal_price_deviation_from_consensus",
                }
            )

    return {
        "main_line": line,
        "main_line_label": line_label_for_group(group_markets),
        "market_count": len(group_markets),
        "usable_market_count": len(group_markets) - len(outliers),
        "median_decimal_odds": {
            "home_cover": median_home,
            "away_cover": median_away,
        },
        "normalized_probability": {
            "home_cover": probability.get("first"),
            "away_cover": probability.get("second"),
        } if probability else {},
        "outlier_threshold": PRICE_OUTLIER_DEVIATION_THRESHOLD,
        "outlier_provider_count": len(outliers),
        "unit_policy": "HK water is converted to decimal odds before any cross-provider comparison.",
        "outliers": outliers,
    }


def _over_under_market_decimal_odds(market: dict[str, Any]) -> dict[str, float | None]:
    current = market.get("current") or {}
    return {
        "over": asian_water_to_decimal(current.get("over_water")),
        "under": asian_water_to_decimal(current.get("under_water")),
    }


def _over_under_price_consensus_for_group(group_markets: list[dict[str, Any]]) -> dict[str, Any]:
    over_decimals = [
        asian_water_to_decimal((market.get("current") or {}).get("over_water"))
        for market in group_markets
    ]
    under_decimals = [
        asian_water_to_decimal((market.get("current") or {}).get("under_water"))
        for market in group_markets
    ]
    over_decimals = [item for item in over_decimals if item is not None]
    under_decimals = [item for item in under_decimals if item is not None]
    median_over = median_metric(over_decimals)
    median_under = median_metric(under_decimals)
    probability = _normalized_two_way_probability(median_over, median_under)
    line = parse_float((group_markets[0].get("current") or {}).get("line")) if group_markets else None
    outliers = []
    for market in group_markets:
        current = market.get("current") or {}
        decimal_odds = _over_under_market_decimal_odds(market)
        over_deviation = _price_deviation(decimal_odds.get("over"), median_over)
        under_deviation = _price_deviation(decimal_odds.get("under"), median_under)
        max_deviation = _max_deviation([over_deviation, under_deviation])
        if max_deviation is not None and max_deviation >= PRICE_OUTLIER_DEVIATION_THRESHOLD:
            outliers.append(
                {
                    "provider": market.get("provider") or "",
                    "area": market.get("area") or "",
                    "line": current.get("line"),
                    "line_label": current.get("line_label") or "",
                    "timestamp": current.get("timestamp") or "",
                    "decimal_odds": decimal_odds,
                    "deviation_from_median": {
                        "over": over_deviation,
                        "under": under_deviation,
                        "max": max_deviation,
                    },
                    "reason": "decimal_price_deviation_from_consensus",
                }
            )
    return {
        "main_line": line,
        "main_line_label": line_label_for_group(group_markets),
        "market_count": len(group_markets),
        "usable_market_count": len(group_markets) - len(outliers),
        "median_decimal_odds": {
            "over": median_over,
            "under": median_under,
        },
        "normalized_probability": {
            "over": probability.get("first"),
            "under": probability.get("second"),
        } if probability else {},
        "outlier_threshold": PRICE_OUTLIER_DEVIATION_THRESHOLD,
        "outlier_provider_count": len(outliers),
        "unit_policy": "HK water is converted to decimal odds before any cross-provider comparison.",
        "outliers": outliers,
    }


def parse_market_timestamp_for_selection(raw_timestamp: Any) -> datetime | None:
    """Parse a market timestamp for ranking rows from the same source response."""
    if isinstance(raw_timestamp, (int, float)) and raw_timestamp > 10_000_000:
        return datetime.fromtimestamp(float(raw_timestamp), tz=timezone.utc)
    raw = str(raw_timestamp or "").strip()
    if not raw:
        return None
    if re.fullmatch(r"\d{10,13}", raw):
        try:
            numeric = int(raw)
            if numeric > 10_000_000:
                if numeric > 10_000_000_000:
                    numeric = numeric / 1000
                return datetime.fromtimestamp(float(numeric), tz=timezone.utc)
        except (TypeError, ValueError, OSError):
            return None
    try:
        short_match = re.fullmatch(r"(\d{1,2})-(\d{1,2})\s+(\d{1,2}):(\d{2})", raw)
        if short_match:
            anchor = now_utc().astimezone(DEFAULT_USER_TIMEZONE)
            month, day, hour, minute = (int(part) for part in short_match.groups())
            parsed = datetime(anchor.year, month, day, hour, minute, tzinfo=DEFAULT_USER_TIMEZONE)
        else:
            parsed = date_parser.parse(raw)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=DEFAULT_USER_TIMEZONE)
    except (TypeError, ValueError):
        return None
    return parsed.astimezone(timezone.utc)


def build_asian_handicap_consensus(
    markets: list[dict[str, Any]],
    preferred: dict[str, Any] | None,
) -> dict[str, Any]:
    complete = [market for market in markets if is_complete_asian_handicap_market(market)]
    if not complete:
        return {
            "available": False,
            "market_count": len(markets),
            "complete_market_count": 0,
            "incomplete_market_count": len(markets),
            "warnings": ["asian_handicap_complete_market_missing"],
            "guidance": "No complete Asian handicap market is available; do not make Asian handicap recommendations.",
        }

    latest_market = max(
        complete,
        key=lambda market: (
            parse_market_timestamp_for_selection((market.get("current") or {}).get("timestamp"))
            or datetime.min.replace(tzinfo=timezone.utc)
        ),
    )

    grouped: dict[float, list[dict[str, Any]]] = {}
    for market in complete:
        line = parse_float((market.get("current") or {}).get("line"))
        if line is None:
            continue
        grouped.setdefault(line, []).append(market)

    distribution = []
    distribution_sort_keys = []
    for line, group_markets in grouped.items():
        latest_in_group = max(
            group_markets,
            key=lambda market: (
                parse_market_timestamp_for_selection((market.get("current") or {}).get("timestamp"))
                or datetime.min.replace(tzinfo=timezone.utc)
            ),
        )
        latest_parsed = parse_market_timestamp_for_selection((latest_in_group.get("current") or {}).get("timestamp"))
        home_waters = [
            parse_float((market.get("current") or {}).get("home_water"))
            for market in group_markets
            if parse_float((market.get("current") or {}).get("home_water")) is not None
        ]
        away_waters = [
            parse_float((market.get("current") or {}).get("away_water"))
            for market in group_markets
            if parse_float((market.get("current") or {}).get("away_water")) is not None
        ]
        item = {
            "line": line,
            "line_label": line_label_for_group(group_markets),
            "market_count": len(group_markets),
            "providers": [market.get("provider") or "" for market in group_markets],
            "latest_timestamp": (latest_in_group.get("current") or {}).get("timestamp") or "",
            "latest_parsed_timestamp_utc": latest_parsed.isoformat() if latest_parsed else None,
            "avg_home_water": average_metric(home_waters),
            "median_home_water": median_metric(home_waters),
            "avg_away_water": average_metric(away_waters),
            "median_away_water": median_metric(away_waters),
        }
        distribution.append(item)
        distribution_sort_keys.append(
            (
                item,
                len(group_markets),
                latest_parsed or datetime.min.replace(tzinfo=timezone.utc),
            )
        )

    distribution = [
        item
        for item, _, _ in sorted(
            distribution_sort_keys,
            key=lambda row: (row[1], row[2]),
            reverse=True,
        )
    ]

    main_line = distribution[0] if distribution else None
    main_line_value = parse_float(main_line.get("line")) if main_line else None
    main_line_markets = grouped.get(main_line_value, []) if main_line_value is not None else []
    price_consensus = _asian_price_consensus_for_group(main_line_markets) if main_line_markets else {}
    outlier_markets = price_consensus.get("outliers") or []
    preferred_compact = compact_asian_handicap_market_for_consensus(preferred)
    latest_compact = compact_asian_handicap_market_for_consensus(latest_market)
    warnings = []
    if len(distribution) > 1:
        warnings.append("market_line_split")
    if outlier_markets:
        warnings.append("price_outlier_detected")
    if preferred_compact and latest_compact and preferred_compact.get("provider") != latest_compact.get("provider"):
        warnings.append("preferred_not_latest")
    if preferred_compact and main_line and preferred_compact.get("line") != main_line.get("line"):
        warnings.append("preferred_line_differs_from_main")
    if latest_compact and main_line and latest_compact.get("line") != main_line.get("line"):
        warnings.append("latest_line_differs_from_main")

    parsed_times = [
        parse_market_timestamp_for_selection((market.get("current") or {}).get("timestamp"))
        for market in complete
    ]
    parsed_times = [item for item in parsed_times if item is not None]
    oldest_time = min(parsed_times) if parsed_times else None
    latest_time = max(parsed_times) if parsed_times else None
    timestamp_span_minutes = None
    if oldest_time and latest_time:
        timestamp_span_minutes = round_metric((latest_time - oldest_time).total_seconds() / 60)

    return {
        "available": True,
        "market_count": len(markets),
        "complete_market_count": len(complete),
        "incomplete_market_count": len(markets) - len(complete),
        "latest_market": latest_compact,
        "main_line": main_line,
        "line_distribution": distribution,
        "price_consensus": {
            key: value for key, value in price_consensus.items() if key != "outliers"
        } if price_consensus else {},
        "outlier_markets": outlier_markets,
        "preferred": {
            **(preferred_compact or {}),
            "matches_latest": bool(
                preferred_compact
                and latest_compact
                and preferred_compact.get("provider") == latest_compact.get("provider")
                and preferred_compact.get("timestamp") == latest_compact.get("timestamp")
            ),
            "matches_main_line": bool(
                preferred_compact
                and main_line
                and preferred_compact.get("line") == main_line.get("line")
            ),
        } if preferred_compact else None,
        "freshness": {
            "oldest_timestamp_utc": oldest_time.isoformat() if oldest_time else None,
            "latest_timestamp_utc": latest_time.isoformat() if latest_time else None,
            "timestamp_span_minutes": timestamp_span_minutes,
        },
        "warnings": warnings,
        "guidance": (
            "Use preferred_asian_handicap for a single default calculation, but inspect "
            "asian_handicap_consensus.price_consensus, outlier_markets, line_distribution, and warnings. "
            "All cross-provider price comparisons must use normalized decimal odds, never raw HK water."
        ),
    }


def compact_over_under_market_for_consensus(market: dict[str, Any] | None) -> dict[str, Any] | None:
    if not market:
        return None
    current = market.get("current") or {}
    parsed_timestamp = parse_market_timestamp_for_selection(current.get("timestamp"))
    metrics = over_under_probability_metrics(current)
    return {
        "provider": market.get("provider") or "",
        "area": market.get("area") or "",
        "line": current.get("line"),
        "line_label": current.get("line_label") or "",
        "over_water": current.get("over_water"),
        "under_water": current.get("under_water"),
        "decimal_odds": metrics.get("decimal_odds") or {},
        "normalized_probability": metrics.get("normalized_probability") or {},
        "timestamp": current.get("timestamp") or "",
        "parsed_timestamp_utc": parsed_timestamp.isoformat() if parsed_timestamp else None,
    }


def build_over_under_consensus(
    markets: list[dict[str, Any]],
    preferred: dict[str, Any] | None,
) -> dict[str, Any]:
    complete = [market for market in markets if is_complete_over_under_market(market)]
    if not complete:
        return {
            "available": False,
            "market_count": len(markets),
            "complete_market_count": 0,
            "incomplete_market_count": len(markets),
            "warnings": ["over_under_complete_market_missing"],
            "guidance": "No complete over/under market is available; do not make totals recommendations.",
        }

    latest_market = max(
        complete,
        key=lambda market: (
            parse_market_timestamp_for_selection((market.get("current") or {}).get("timestamp"))
            or datetime.min.replace(tzinfo=timezone.utc)
        ),
    )

    grouped: dict[float, list[dict[str, Any]]] = {}
    for market in complete:
        line = parse_float((market.get("current") or {}).get("line"))
        if line is None:
            continue
        grouped.setdefault(line, []).append(market)

    distribution = []
    for line, group_markets in grouped.items():
        latest_in_group = max(
            group_markets,
            key=lambda market: (
                parse_market_timestamp_for_selection((market.get("current") or {}).get("timestamp"))
                or datetime.min.replace(tzinfo=timezone.utc)
            ),
        )
        latest_parsed = parse_market_timestamp_for_selection((latest_in_group.get("current") or {}).get("timestamp"))
        over_waters = [
            parse_float((market.get("current") or {}).get("over_water"))
            for market in group_markets
            if parse_float((market.get("current") or {}).get("over_water")) is not None
        ]
        under_waters = [
            parse_float((market.get("current") or {}).get("under_water"))
            for market in group_markets
            if parse_float((market.get("current") or {}).get("under_water")) is not None
        ]
        distribution.append(
            {
                "line": line,
                "line_label": line_label_for_group(group_markets),
                "market_count": len(group_markets),
                "providers": [market.get("provider") or "" for market in group_markets],
                "latest_timestamp": (latest_in_group.get("current") or {}).get("timestamp") or "",
                "latest_parsed_timestamp_utc": latest_parsed.isoformat() if latest_parsed else None,
                "avg_over_water": average_metric(over_waters),
                "median_over_water": median_metric(over_waters),
                "avg_under_water": average_metric(under_waters),
                "median_under_water": median_metric(under_waters),
            }
        )

    distribution.sort(
        key=lambda item: (
            item.get("market_count") or 0,
            parse_market_timestamp_for_selection(item.get("latest_timestamp")) or datetime.min.replace(tzinfo=timezone.utc),
        ),
        reverse=True,
    )
    main_line = distribution[0] if distribution else None
    main_line_value = parse_float(main_line.get("line")) if main_line else None
    main_line_markets = grouped.get(main_line_value, []) if main_line_value is not None else []
    price_consensus = _over_under_price_consensus_for_group(main_line_markets) if main_line_markets else {}
    outlier_markets = price_consensus.get("outliers") or []
    preferred_compact = compact_over_under_market_for_consensus(preferred)
    latest_compact = compact_over_under_market_for_consensus(latest_market)
    warnings = []
    if len(distribution) > 1:
        warnings.append("total_line_split")
    if outlier_markets:
        warnings.append("price_outlier_detected")
    if preferred_compact and latest_compact and preferred_compact.get("provider") != latest_compact.get("provider"):
        warnings.append("preferred_not_latest")
    if preferred_compact and main_line and preferred_compact.get("line") != main_line.get("line"):
        warnings.append("preferred_line_differs_from_main")

    parsed_times = [
        parse_market_timestamp_for_selection((market.get("current") or {}).get("timestamp"))
        for market in complete
    ]
    parsed_times = [item for item in parsed_times if item is not None]
    oldest_time = min(parsed_times) if parsed_times else None
    latest_time = max(parsed_times) if parsed_times else None
    timestamp_span_minutes = None
    if oldest_time and latest_time:
        timestamp_span_minutes = round_metric((latest_time - oldest_time).total_seconds() / 60)

    return {
        "available": True,
        "market_count": len(markets),
        "complete_market_count": len(complete),
        "incomplete_market_count": len(markets) - len(complete),
        "latest_market": latest_compact,
        "main_line": main_line,
        "line_distribution": distribution,
        "price_consensus": {
            key: value for key, value in price_consensus.items() if key != "outliers"
        } if price_consensus else {},
        "outlier_markets": outlier_markets,
        "preferred": {
            **(preferred_compact or {}),
            "matches_latest": bool(
                preferred_compact
                and latest_compact
                and preferred_compact.get("provider") == latest_compact.get("provider")
                and preferred_compact.get("timestamp") == latest_compact.get("timestamp")
            ),
            "matches_main_line": bool(
                preferred_compact
                and main_line
                and preferred_compact.get("line") == main_line.get("line")
            ),
        } if preferred_compact else None,
        "freshness": {
            "oldest_timestamp_utc": oldest_time.isoformat() if oldest_time else None,
            "latest_timestamp_utc": latest_time.isoformat() if latest_time else None,
            "timestamp_span_minutes": timestamp_span_minutes,
        },
        "warnings": warnings,
        "guidance": (
            "Use preferred_over_under for a single default calculation, but inspect "
            "over_under_consensus.price_consensus, outlier_markets, line_distribution, and warnings. "
            "All cross-provider price comparisons must use normalized decimal odds, never raw HK water."
        ),
    }


def _market_identity(market: dict[str, Any]) -> tuple[str, Any, str]:
    current = market.get("current") or {}
    return (
        str(market.get("provider") or ""),
        current.get("line"),
        str(current.get("timestamp") or ""),
    )


def _main_line_group(markets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[float, list[dict[str, Any]]] = {}
    for market in markets:
        line = parse_float((market.get("current") or {}).get("line"))
        if line is not None:
            grouped.setdefault(line, []).append(market)
    if not grouped:
        return markets
    return max(
        grouped.values(),
        key=lambda group: (
            len(group),
            max(
                [
                    parse_market_timestamp_for_selection((market.get("current") or {}).get("timestamp"))
                    or datetime.min.replace(tzinfo=timezone.utc)
                    for market in group
                ]
            ),
        ),
    )


def _select_freshest_preferred_market(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    provider_priority = ["竞彩官方", "平均值", "最高值", "最低值"]
    ranked = []
    for index, market in enumerate(candidates):
        parsed_timestamp = parse_market_timestamp_for_selection((market.get("current") or {}).get("timestamp"))
        if parsed_timestamp is None:
            continue
        provider_rank = provider_priority.index(market.get("provider")) if market.get("provider") in provider_priority else len(provider_priority)
        ranked.append((parsed_timestamp, -provider_rank, -index, market))
    if ranked:
        return max(ranked, key=lambda item: item[:3])[3]
    for provider in provider_priority:
        for market in candidates:
            if market.get("provider") == provider:
                return market
    return candidates[0] if candidates else None


def select_preferred_asian_handicap(markets: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Pick one Asian handicap market so agents have a stable, non-outlier handicap source."""
    complete = [
        market
        for market in markets
        if all((market.get("current") or {}).get(key) is not None for key in ("home_water", "line", "away_water"))
    ]
    if complete:
        main_group = _main_line_group(complete)
        price_consensus = _asian_price_consensus_for_group(main_group)
        outlier_keys = {
            (str(item.get("provider") or ""), item.get("line"), str(item.get("timestamp") or ""))
            for item in price_consensus.get("outliers") or []
        }
        candidates = [market for market in main_group if _market_identity(market) not in outlier_keys]
        return _select_freshest_preferred_market(candidates or main_group)
    return _select_freshest_preferred_market(markets)


def select_preferred_over_under(markets: list[dict[str, Any]]) -> dict[str, Any] | None:
    complete = [market for market in markets if is_complete_over_under_market(market)]
    if complete:
        main_group = _main_line_group(complete)
        price_consensus = _over_under_price_consensus_for_group(main_group)
        outlier_keys = {
            (str(item.get("provider") or ""), item.get("line"), str(item.get("timestamp") or ""))
            for item in price_consensus.get("outliers") or []
        }
        candidates = [market for market in main_group if _market_identity(market) not in outlier_keys]
        return _select_freshest_preferred_market(candidates or main_group)
    return _select_freshest_preferred_market(markets)


def round_metric(value: float | None, ndigits: int = 6) -> float | None:
    return round(value, ndigits) if value is not None else None


def asian_water_to_decimal(value: Any) -> float | None:
    water = parse_float(value)
    if water is None or water <= 0:
        return None
    if water < 1.5:
        return round_metric(1 + water, 4)
    return round_metric(water, 4)


def moneyline_probability_metrics(prices: dict[str, Any] | None) -> dict[str, Any]:
    prices = prices or {}
    odds = {
        "home": parse_float(prices.get("home")),
        "draw": parse_float(prices.get("draw")),
        "away": parse_float(prices.get("away")),
    }
    if not all(value and value > 1 for value in odds.values()):
        return {
            "available": False,
            "reason": "incomplete_or_invalid_1x2_prices",
            "odds": odds,
        }

    implied = {key: 1 / float(value) for key, value in odds.items()}
    probability_sum = sum(implied.values())
    return {
        "available": True,
        "odds": odds,
        "raw_implied_probability": {key: round_metric(value) for key, value in implied.items()},
        "raw_probability_sum": round_metric(probability_sum),
        "overround": round_metric(probability_sum - 1),
        "payout_rate": round_metric(1 / probability_sum if probability_sum else None),
        "normalized_probability": {
            key: round_metric(value / probability_sum if probability_sum else None)
            for key, value in implied.items()
        },
        "formula": {
            "raw_implied_probability": "1 / decimal_odds",
            "overround": "sum(raw_implied_probability) - 1",
            "payout_rate": "1 / sum(raw_implied_probability)",
        },
    }


def asian_handicap_probability_metrics(prices: dict[str, Any] | None) -> dict[str, Any]:
    prices = prices or {}
    decimal_odds = {
        "home_cover": asian_water_to_decimal(prices.get("home_water")),
        "away_cover": asian_water_to_decimal(prices.get("away_water")),
    }
    raw_water = {
        "home_cover": parse_float(prices.get("home_water")),
        "away_cover": parse_float(prices.get("away_water")),
    }
    line = parse_float(prices.get("line"))
    if not all(value and value > 1 for value in decimal_odds.values()) or line is None:
        return {
            "available": False,
            "reason": "incomplete_or_invalid_asian_handicap_prices",
            "line": line,
            "raw_water": raw_water,
            "decimal_odds": decimal_odds,
        }

    implied = {key: 1 / float(value) for key, value in decimal_odds.items()}
    probability_sum = sum(implied.values())
    return {
        "available": True,
        "line": line,
        "home_handicap": line,
        "away_handicap": -line,
        "raw_water": raw_water,
        "decimal_odds": decimal_odds,
        "raw_implied_probability": {key: round_metric(value) for key, value in implied.items()},
        "raw_probability_sum": round_metric(probability_sum),
        "overround": round_metric(probability_sum - 1),
        "payout_rate": round_metric(1 / probability_sum if probability_sum else None),
        "normalized_probability": {
            key: round_metric(value / probability_sum if probability_sum else None)
            for key, value in implied.items()
        },
        "formula": {
            "decimal_odds": "asian_water + 1 when water is HK-style; already-decimal values are kept",
            "raw_implied_probability": "1 / decimal_odds",
            "overround": "sum(raw_implied_probability) - 1",
            "payout_rate": "1 / sum(raw_implied_probability)",
        },
    }


def over_under_probability_metrics(prices: dict[str, Any] | None) -> dict[str, Any]:
    prices = prices or {}
    decimal_odds = {
        "over": asian_water_to_decimal(prices.get("over_water")),
        "under": asian_water_to_decimal(prices.get("under_water")),
    }
    raw_water = {
        "over": parse_float(prices.get("over_water")),
        "under": parse_float(prices.get("under_water")),
    }
    line = parse_float(prices.get("line"))
    if not all(value and value > 1 for value in decimal_odds.values()) or line is None:
        return {
            "available": False,
            "reason": "incomplete_or_invalid_over_under_prices",
            "line": line,
            "raw_water": raw_water,
            "decimal_odds": decimal_odds,
        }

    implied = {key: 1 / float(value) for key, value in decimal_odds.items()}
    probability_sum = sum(implied.values())
    return {
        "available": True,
        "line": line,
        "raw_water": raw_water,
        "decimal_odds": decimal_odds,
        "raw_implied_probability": {key: round_metric(value) for key, value in implied.items()},
        "raw_probability_sum": round_metric(probability_sum),
        "overround": round_metric(probability_sum - 1),
        "payout_rate": round_metric(1 / probability_sum if probability_sum else None),
        "normalized_probability": {
            key: round_metric(value / probability_sum if probability_sum else None)
            for key, value in implied.items()
        },
        "formula": {
            "decimal_odds": "asian_water + 1 when water is HK-style; already-decimal values are kept",
            "raw_implied_probability": "1 / decimal_odds",
            "overround": "sum(raw) - 1",
            "payout_rate": "1 / sum(raw)",
        },
    }


def moneyline_price_movement(
    current: dict[str, Any] | None,
    opening: dict[str, Any] | None,
) -> dict[str, Any]:
    current = current or {}
    opening = opening or {}
    movement: dict[str, Any] = {}
    for key in ["home", "draw", "away"]:
        current_value = parse_float(current.get(key))
        opening_value = parse_float(opening.get(key))
        if current_value is None or opening_value is None or opening_value == 0:
            continue
        movement[key] = {
            "opening": opening_value,
            "current": current_value,
            "absolute": round_metric(current_value - opening_value),
            "percent": round_metric((current_value / opening_value) - 1),
        }
    return movement


def asian_handicap_price_movement(
    current: dict[str, Any] | None,
    opening: dict[str, Any] | None,
) -> dict[str, Any]:
    current = current or {}
    opening = opening or {}
    movement: dict[str, Any] = {}
    for key in ["home_water", "line", "away_water"]:
        current_value = parse_float(current.get(key))
        opening_value = parse_float(opening.get(key))
        if current_value is None or opening_value is None:
            continue
        item: dict[str, Any] = {
            "opening": opening_value,
            "current": current_value,
            "absolute": round_metric(current_value - opening_value),
        }
        if opening_value:
            item["percent"] = round_metric((current_value / opening_value) - 1)
        movement[key] = item
    return movement


def over_under_price_movement(
    current: dict[str, Any] | None,
    opening: dict[str, Any] | None,
) -> dict[str, Any]:
    current = current or {}
    opening = opening or {}
    movement: dict[str, Any] = {}
    for key in ["over_water", "line", "under_water"]:
        current_value = parse_float(current.get(key))
        opening_value = parse_float(opening.get(key))
        if current_value is None or opening_value is None:
            continue
        item: dict[str, Any] = {
            "opening": opening_value,
            "current": current_value,
            "absolute": round_metric(current_value - opening_value),
        }
        if opening_value:
            item["percent"] = round_metric((current_value / opening_value) - 1)
        movement[key] = item
    return movement


def parse_source_fetched_at(source: dict[str, Any] | None) -> datetime | None:
    raw = (source or {}).get("fetched_at_utc")
    if not raw:
        return None
    try:
        parsed = date_parser.parse(str(raw))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def market_timestamp_quality(raw_timestamp: str | None, source: dict[str, Any] | None = None) -> dict[str, Any]:
    raw = str(raw_timestamp or "").strip()
    fetched_at = parse_source_fetched_at(source)
    if not raw:
        return {
            "raw": raw,
            "parsed_utc": None,
            "quality": "missing",
            "flags": ["timestamp_missing"],
        }

    parsed_utc = parse_market_timestamp_for_selection(raw_timestamp)
    if not parsed_utc:
        return {
            "raw": raw,
            "parsed_utc": None,
            "quality": "unparseable",
            "flags": ["timestamp_unparseable"],
        }

    flags: list[str] = []
    quality = "unchecked"
    relation_to_fetch = "unknown"
    seconds_from_fetch = None
    if fetched_at:
        seconds_from_fetch = int((parsed_utc - fetched_at).total_seconds())
        if seconds_from_fetch > 0:
            relation_to_fetch = "after_fetch"
        elif seconds_from_fetch < 0:
            relation_to_fetch = "before_fetch"
        else:
            relation_to_fetch = "same_as_fetch"
        quality = "ok"
        if parsed_utc > fetched_at + timedelta(minutes=10):
            flags.append("timestamp_after_fetch")
            flags.append("future_source_timestamp")
            quality = "future_inconsistent"
        elif parsed_utc < fetched_at - timedelta(days=14):
            flags.append("timestamp_stale")
            quality = "stale"

    return {
        "raw": raw,
        "parsed_utc": parsed_utc.isoformat(),
        "quality": quality,
        "relation_to_fetch": relation_to_fetch,
        "seconds_from_fetch": seconds_from_fetch,
        "flags": flags,
        "fetched_at_utc": fetched_at.isoformat() if fetched_at else None,
        "human_explanation": (
            "source returned a future market timestamp; treat this source timestamp as inconsistent, use fetched_at as the observation time for the returned price snapshot, and do not use this source timestamp for freshness or time-series analysis"
            if "future_source_timestamp" in flags
            else ""
        ),
    }


def build_odds_quality_contract(odds: dict[str, Any], source: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return a compact machine-checkable contract so agents do less arithmetic guessing."""
    preferred_moneyline = odds.get("preferred_moneyline_1x2") or None
    preferred_asian = odds.get("preferred_asian_handicap") or None
    preferred_over_under = odds.get("preferred_over_under") or None
    hard_flags: list[str] = []
    soft_flags: list[str] = []
    moneyline_contract: dict[str, Any] = {"available": bool(preferred_moneyline)}
    asian_contract: dict[str, Any] = {"available": bool(preferred_asian)}
    over_under_contract: dict[str, Any] = {"available": bool(preferred_over_under)}
    source_fetched_at = parse_source_fetched_at(source)
    moneyline_calculable = False
    asian_calculable = False
    over_under_calculable = False

    if preferred_moneyline:
        current = preferred_moneyline.get("current") or {}
        opening = preferred_moneyline.get("opening") or {}
        current_metrics = moneyline_probability_metrics(current)
        opening_metrics = moneyline_probability_metrics(opening) if opening else {"available": False}
        moneyline_calculable = bool(current_metrics.get("available"))
        moneyline_contract.update(
            {
                "provider": preferred_moneyline.get("provider") or "",
                "current_metrics": current_metrics,
                "opening_metrics": opening_metrics,
                "opening_to_current_movement": moneyline_price_movement(current, opening),
                "price_observed_at_utc": source_fetched_at.isoformat() if source_fetched_at else None,
            }
        )
        phases = [("current", current)]
        if opening:
            phases.append(("opening", opening))
        for phase, prices in phases:
            timestamp_result = market_timestamp_quality((prices or {}).get("timestamp"), source)
            moneyline_contract[f"{phase}_timestamp_quality"] = timestamp_result
            for flag in timestamp_result.get("flags") or []:
                soft_flags.append(f"preferred_moneyline_{phase}_{flag}")

    if preferred_asian:
        current = preferred_asian.get("current") or {}
        opening = preferred_asian.get("opening") or {}
        current_metrics = asian_handicap_probability_metrics(current)
        opening_metrics = asian_handicap_probability_metrics(opening) if opening else {"available": False}
        asian_calculable = bool(current_metrics.get("available"))
        asian_contract.update(
            {
                "provider": preferred_asian.get("provider") or "",
                "current_metrics": current_metrics,
                "opening_metrics": opening_metrics,
                "opening_to_current_movement": asian_handicap_price_movement(current, opening),
                "price_observed_at_utc": source_fetched_at.isoformat() if source_fetched_at else None,
            }
        )
        phases = [("current", current)]
        if opening:
            phases.append(("opening", opening))
        for phase, prices in phases:
            timestamp_result = market_timestamp_quality((prices or {}).get("timestamp"), source)
            asian_contract[f"{phase}_timestamp_quality"] = timestamp_result
            for flag in timestamp_result.get("flags") or []:
                soft_flags.append(f"preferred_asian_handicap_{phase}_{flag}")

    if preferred_over_under:
        current = preferred_over_under.get("current") or {}
        opening = preferred_over_under.get("opening") or {}
        current_metrics = over_under_probability_metrics(current)
        opening_metrics = over_under_probability_metrics(opening) if opening else {"available": False}
        over_under_calculable = bool(current_metrics.get("available"))
        over_under_contract.update(
            {
                "provider": preferred_over_under.get("provider") or "",
                "current_metrics": current_metrics,
                "opening_metrics": opening_metrics,
                "opening_to_current_movement": over_under_price_movement(current, opening),
                "price_observed_at_utc": source_fetched_at.isoformat() if source_fetched_at else None,
            }
        )
        phases = [("current", current)]
        if opening:
            phases.append(("opening", opening))
        for phase, prices in phases:
            timestamp_result = market_timestamp_quality((prices or {}).get("timestamp"), source)
            over_under_contract[f"{phase}_timestamp_quality"] = timestamp_result
            for flag in timestamp_result.get("flags") or []:
                soft_flags.append(f"preferred_over_under_{phase}_{flag}")

    if not moneyline_calculable and not asian_calculable and not over_under_calculable:
        if not preferred_moneyline and not preferred_asian and not preferred_over_under:
            hard_flags.append("supported_market_missing")
        else:
            if preferred_moneyline and not moneyline_calculable:
                hard_flags.append("preferred_moneyline_current_prices_invalid")
            if preferred_asian and not asian_calculable:
                hard_flags.append("preferred_asian_handicap_current_prices_invalid")
            if preferred_over_under and not over_under_calculable:
                hard_flags.append("preferred_over_under_current_prices_invalid")

    freshness_blocking_flags = {
        "preferred_moneyline_current_timestamp_after_fetch",
        "preferred_moneyline_current_future_source_timestamp",
        "preferred_moneyline_current_timestamp_unparseable",
        "preferred_moneyline_current_timestamp_missing",
        "preferred_asian_handicap_current_timestamp_after_fetch",
        "preferred_asian_handicap_current_future_source_timestamp",
        "preferred_asian_handicap_current_timestamp_unparseable",
        "preferred_asian_handicap_current_timestamp_missing",
        "preferred_over_under_current_timestamp_after_fetch",
        "preferred_over_under_current_future_source_timestamp",
        "preferred_over_under_current_timestamp_unparseable",
        "preferred_over_under_current_timestamp_missing",
    }

    return {
        "can_use_for_calculation": not hard_flags,
        "can_use_timestamp_for_freshness": not any(
            flag in set(soft_flags)
            for flag in freshness_blocking_flags
        ),
        "hard_flags": hard_flags,
        "soft_flags": soft_flags,
        "supported_markets": {
            "moneyline_1x2": moneyline_calculable,
            "asian_handicap": asian_calculable,
            "over_under": over_under_calculable,
        },
        "preferred_moneyline_1x2": moneyline_contract,
        "preferred_asian_handicap": asian_contract,
        "preferred_over_under": over_under_contract,
        "calculation_policy": (
            "Supported betting markets are 1X2 and Asian handicap. For 1X2 use preferred_moneyline_1x2.current only. "
            "For Asian handicap calculation use preferred_asian_handicap.current only after checking asian_handicap_consensus; "
            "For totals use preferred_over_under.current only after checking over_under_consensus; "
            "convert HK-style water to decimal_odds=water+1 before probability math. "
            "Do not mix 1X2, handicap, schedule_snapshot, or bookmaker rows in one calculation. "
            "raw_implied_probability=1/odds; overround=sum(raw)-1; payout_rate=1/sum(raw). "
            "If current timestamp quality is inconsistent, "
            "the prices may still be used as the fetched response snapshot, but not as a reliable freshness or time-series timestamp."
        ),
    }


def _max_probability_side(probabilities: dict[str, Any], labels: dict[str, str]) -> dict[str, Any]:
    parsed = {key: parse_float(value) for key, value in (probabilities or {}).items()}
    parsed = {key: value for key, value in parsed.items() if value is not None}
    if not parsed:
        return {"key": "", "label": "", "probability": None}
    key = max(parsed, key=lambda item: parsed[item])
    return {"key": key, "label": labels.get(key, key), "probability": round_metric(parsed[key])}


def _agreement_ratio(consensus: dict[str, Any]) -> float | None:
    main = consensus.get("main_line") or {}
    complete = parse_float(consensus.get("complete_market_count"))
    main_count = parse_float(main.get("market_count"))
    if not complete or not main_count:
        return None
    return round_metric(main_count / complete)


def build_market_intelligence(odds: dict[str, Any]) -> dict[str, Any]:
    contract = odds.get("quality_contract") or {}
    moneyline = contract.get("preferred_moneyline_1x2") or {}
    asian = contract.get("preferred_asian_handicap") or {}
    over_under = contract.get("preferred_over_under") or {}
    moneyline_metrics = moneyline.get("current_metrics") or {}
    asian_metrics = asian.get("current_metrics") or {}
    over_under_metrics = over_under.get("current_metrics") or {}
    asian_consensus = odds.get("asian_handicap_consensus") or {}
    over_under_consensus = odds.get("over_under_consensus") or {}
    asian_consensus_probability = (asian_consensus.get("price_consensus") or {}).get("normalized_probability") or {}
    over_under_consensus_probability = (over_under_consensus.get("price_consensus") or {}).get("normalized_probability") or {}

    return {
        "moneyline_1x2": {
            "available": bool(moneyline_metrics.get("available")),
            "provider": moneyline.get("provider") or "",
            "favorite": _max_probability_side(
                moneyline_metrics.get("normalized_probability") or {},
                {"home": "主胜", "draw": "平局", "away": "客胜"},
            ),
            "overround": moneyline_metrics.get("overround"),
            "payout_rate": moneyline_metrics.get("payout_rate"),
            "movement": moneyline.get("opening_to_current_movement") or {},
        },
        "asian_handicap": {
            "available": bool(asian_metrics.get("available")),
            "provider": asian.get("provider") or "",
            "preferred_line": asian_metrics.get("line"),
            "main_line": (asian_consensus.get("main_line") or {}).get("line"),
            "agreement_ratio": _agreement_ratio(asian_consensus),
            "warnings": asian_consensus.get("warnings") or [],
            "overround": asian_metrics.get("overround"),
            "payout_rate": asian_metrics.get("payout_rate"),
            "side_bias": _max_probability_side(
                asian_consensus_probability or asian_metrics.get("normalized_probability") or {},
                {"home_cover": "主队方向", "away_cover": "客队方向"},
            ),
            "movement": asian.get("opening_to_current_movement") or {},
            "price_consensus": asian_consensus.get("price_consensus") or {},
            "outlier_count": len(asian_consensus.get("outlier_markets") or []),
        },
        "over_under": {
            "available": bool(over_under_metrics.get("available")),
            "provider": over_under.get("provider") or "",
            "preferred_line": over_under_metrics.get("line"),
            "main_line": (over_under_consensus.get("main_line") or {}).get("line"),
            "agreement_ratio": _agreement_ratio(over_under_consensus),
            "warnings": over_under_consensus.get("warnings") or [],
            "overround": over_under_metrics.get("overround"),
            "payout_rate": over_under_metrics.get("payout_rate"),
            "side_bias": _max_probability_side(
                over_under_consensus_probability or over_under_metrics.get("normalized_probability") or {},
                {"over": "大球", "under": "小球"},
            ),
            "movement": over_under.get("opening_to_current_movement") or {},
            "price_consensus": over_under_consensus.get("price_consensus") or {},
            "outlier_count": len(over_under_consensus.get("outlier_markets") or []),
        },
        "usage_policy": (
            "Use this object as market analysis scaffolding. It summarizes probabilities, movement, consensus, "
            "and warnings without replacing raw odds or quality_contract."
        ),
    }


def _append_unique(items: list[str], value: str | None) -> None:
    value = str(value or "").strip()
    if value and value not in items:
        items.append(value)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _normalize_probabilities(probabilities: dict[str, float | None]) -> dict[str, float]:
    usable = {key: float(value) for key, value in probabilities.items() if value is not None and value > 0}
    total = sum(usable.values())
    if not total:
        return {}
    return {key: round_metric(value / total) or 0 for key, value in usable.items()}


def _parse_score_pair(item: dict[str, Any]) -> tuple[float | None, float | None]:
    for left_key, right_key in [
        ("team_A_score", "team_B_score"),
        ("home_score", "away_score"),
        ("score_home", "score_away"),
        ("fs_A", "fs_B"),
    ]:
        left = parse_float(item.get(left_key))
        right = parse_float(item.get(right_key))
        if left is not None and right is not None:
            return left, right
    team_a = item.get("team_A") or {}
    team_b = item.get("team_B") or {}
    left = parse_float(team_a.get("fs"))
    right = parse_float(team_b.get("fs"))
    if left is not None and right is not None:
        return left, right
    score_text = str(item.get("score") or item.get("full_score") or "").strip()
    match = re.search(r"(\d+)\s*[-:]\s*(\d+)", score_text)
    if match:
        return float(match.group(1)), float(match.group(2))
    return None, None


def _recent_record_strength(items: list[dict[str, Any]], *, side: str) -> dict[str, Any]:
    points = 0.0
    goal_diff = 0.0
    samples = 0
    for item in items[:5]:
        if not isinstance(item, dict):
            continue
        result = str(item.get("result_for_team") or item.get("result") or "").upper()
        if result in {"W", "WIN"}:
            points += 3
            samples += 1
            continue
        if result in {"D", "DRAW"}:
            points += 1
            samples += 1
            continue
        if result in {"L", "LOSS"}:
            samples += 1
            continue

        left, right = _parse_score_pair(item)
        if left is None or right is None:
            continue
        target_score, opponent_score = (left, right) if side == "home" else (right, left)
        if target_score > opponent_score:
            points += 3
        elif target_score == opponent_score:
            points += 1
        goal_diff += target_score - opponent_score
        samples += 1

    return {
        "sample_size": samples,
        "points_per_match": round_metric(points / samples if samples else None),
        "goal_diff_per_match": round_metric(goal_diff / samples if samples else None),
    }


def _extract_recent_items(form: dict[str, Any], side: str) -> list[dict[str, Any]]:
    if not isinstance(form, dict):
        return []
    recent = form.get("recent_record") or {}
    if isinstance(recent, dict):
        items = recent.get(side) or recent.get("team_A" if side == "home" else "team_B") or []
        if isinstance(items, dict):
            items = items.get("list") or []
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
    team = form.get(side) or {}
    matches = team.get("matches") if isinstance(team, dict) else []
    return [item for item in (matches or []) if isinstance(item, dict)]


def _form_signal(form: dict[str, Any]) -> dict[str, Any]:
    home_strength = _recent_record_strength(_extract_recent_items(form, "home"), side="home")
    away_strength = _recent_record_strength(_extract_recent_items(form, "away"), side="away")
    home_ppm = home_strength.get("points_per_match")
    away_ppm = away_strength.get("points_per_match")
    home_gd = home_strength.get("goal_diff_per_match")
    away_gd = away_strength.get("goal_diff_per_match")
    edge = 0.0
    reasons: list[str] = []
    if home_ppm is not None and away_ppm is not None:
        edge += _clamp((float(home_ppm) - float(away_ppm)) / 3, -1, 1) * 0.09
        reasons.append("recent_points")
    if home_gd is not None and away_gd is not None:
        edge += _clamp((float(home_gd) - float(away_gd)) / 4, -1, 1) * 0.04
        reasons.append("recent_goal_diff")
    if not reasons:
        reasons.append("market_only_no_recent_form_signal")
    return {
        "home_probability_delta": round_metric(_clamp(edge, -0.1, 0.1)),
        "home_recent": home_strength,
        "away_recent": away_strength,
        "reasons": reasons,
        "guidance": "Heuristic context signal only; use it as a small adjustment to market probabilities, not as a standalone model.",
    }


def _adjust_moneyline_probabilities(market_probabilities: dict[str, Any], form: dict[str, Any]) -> dict[str, float]:
    market = {
        "home": parse_float(market_probabilities.get("home")),
        "draw": parse_float(market_probabilities.get("draw")),
        "away": parse_float(market_probabilities.get("away")),
    }
    if not all(value is not None for value in market.values()):
        return {}
    signal = _form_signal(form)
    delta = parse_float(signal.get("home_probability_delta")) or 0.0
    return _normalize_probabilities(
        {
            "home": float(market["home"]) + delta,
            "draw": float(market["draw"]) - abs(delta) * 0.25,
            "away": float(market["away"]) - delta * 0.75,
        }
    )


def _moneyline_movement_delta(moneyline_contract: dict[str, Any]) -> float:
    movement = moneyline_contract.get("opening_to_current_movement") or {}
    home_pct = parse_float((movement.get("home") or {}).get("percent"))
    away_pct = parse_float((movement.get("away") or {}).get("percent"))
    if home_pct is None or away_pct is None:
        return 0.0
    # Shortening home odds and drifting away odds are a small pro-home market signal.
    return _clamp((away_pct - home_pct) * 0.12, -0.05, 0.05)


def _apply_home_delta(probabilities: dict[str, float], delta: float) -> dict[str, float]:
    if not probabilities or not delta:
        return probabilities
    return _normalize_probabilities(
        {
            "home": (probabilities.get("home") or 0) + delta,
            "draw": (probabilities.get("draw") or 0) - abs(delta) * 0.2,
            "away": (probabilities.get("away") or 0) - delta * 0.8,
        }
    )


def _asian_model_cover_probabilities(line: float, model_1x2: dict[str, float]) -> dict[str, float]:
    home = model_1x2.get("home") or 0
    draw = model_1x2.get("draw") or 0
    away = model_1x2.get("away") or 0
    if line <= -0.75:
        home_cover = home * 0.9
    elif line == -0.5:
        home_cover = home
    elif line == -0.25:
        home_cover = home + draw * 0.25
    elif line == 0:
        home_cover = home + draw * 0.5
    elif line == 0.25:
        home_cover = home + draw * 0.75
    else:
        home_cover = home + draw
    away_cover = 1 - home_cover
    return {
        "home_cover": round_metric(_clamp(home_cover, 0.01, 0.99)) or 0,
        "away_cover": round_metric(_clamp(away_cover, 0.01, 0.99)) or 0,
    }


def _expected_total_goals(form: dict[str, Any]) -> float | None:
    summary = (form or {}).get("recent_record_summary") or {}
    home = summary.get("home") or {}
    away = summary.get("away") or {}
    use_same_competition = (
        (parse_float(home.get("same_competition_sample_size")) or 0) >= 2
        and (parse_float(away.get("same_competition_sample_size")) or 0) >= 2
    )
    prefix = "same_competition_" if use_same_competition else ""
    home_for = parse_float(home.get(f"{prefix}goals_for_per_match"))
    home_against = parse_float(home.get(f"{prefix}goals_against_per_match"))
    away_for = parse_float(away.get(f"{prefix}goals_for_per_match"))
    away_against = parse_float(away.get(f"{prefix}goals_against_per_match"))
    estimates = []
    if home_for is not None and away_against is not None:
        estimates.append((home_for + away_against) / 2)
    if away_for is not None and home_against is not None:
        estimates.append((away_for + home_against) / 2)
    if estimates:
        return round_metric(sum(estimates))
    totals = [
        parse_float(home.get(f"{prefix}avg_total_goals")),
        parse_float(away.get(f"{prefix}avg_total_goals")),
    ]
    totals = [item for item in totals if item is not None]
    return round_metric(sum(totals) / len(totals)) if totals else None


def _over_under_model_probabilities(line: float, form: dict[str, Any]) -> dict[str, float]:
    expected_total = _expected_total_goals(form)
    if expected_total is None:
        return {}
    delta = _clamp((expected_total - line) * 0.12, -0.16, 0.16)
    over = _clamp(0.5 + delta, 0.34, 0.66)
    return {"over": round_metric(over) or 0, "under": round_metric(1 - over) or 0}


def _recommendation_from_edge(edge: float | None, confidence: float, blocking_flags: list[str]) -> str:
    if blocking_flags:
        return "no_bet"
    if edge is None:
        return "no_value"
    if edge >= 0.035 and confidence >= 0.52:
        return "immediate_bet"
    if edge >= 0.006:
        return "condition_observe"
    return "no_value"


def _candidate_value_metrics(
    *,
    model_probability: Any,
    market_probability: Any,
    decimal_odds: Any,
    probability_edge: Any = None,
) -> dict[str, Any]:
    model_probability_float = parse_float(model_probability)
    market_probability_float = parse_float(market_probability)
    decimal_odds_float = parse_float(decimal_odds)
    probability_edge_float = parse_float(probability_edge)
    if probability_edge_float is None and model_probability_float is not None and market_probability_float is not None:
        probability_edge_float = model_probability_float - market_probability_float

    expected_multiplier = None
    value_edge = None
    edge_basis = "no_vig_probability_edge"
    if model_probability_float is not None and decimal_odds_float is not None and decimal_odds_float > 1:
        expected_multiplier = round_metric(model_probability_float * decimal_odds_float, 6)
        value_edge = round_metric((expected_multiplier or 0) - 1, 4)
        edge_basis = "expected_multiplier_minus_1"
    else:
        value_edge = round_metric(probability_edge_float)

    return {
        "probability_edge": round_metric(probability_edge_float),
        "expected_multiplier": expected_multiplier,
        "edge": value_edge,
        "edge_basis": edge_basis,
    }


def _official_hhad_model_probabilities(distribution: list[dict[str, Any]], goal_line: float) -> dict[str, float]:
    totals = {"home": 0.0, "draw": 0.0, "away": 0.0}
    for row in distribution or []:
        probability = parse_float(row.get("probability")) or 0.0
        adjusted_margin = (parse_float(row.get("home_goals")) or 0.0) + goal_line - (parse_float(row.get("away_goals")) or 0.0)
        if adjusted_margin > 1e-9:
            totals["home"] += probability
        elif adjusted_margin < -1e-9:
            totals["away"] += probability
        else:
            totals["draw"] += probability
    return {key: round_metric(value) or 0.0 for key, value in totals.items()}


def _stake_level(recommendation: str, confidence: float, caution_count: int) -> str:
    if recommendation in {"no_bet", "no_value"}:
        return "none"
    if recommendation == "condition_observe":
        return "watch_only_until_condition"
    if confidence >= 0.66 and caution_count <= 2:
        return "small_to_normal"
    return "small"


def _market_label(market: str) -> str:
    return {
        "1x2": "胜平负",
        "jingcai_hhad": "竞彩让球胜平负",
        "asian_handicap": "亚盘",
        "over_under": "大小球",
        "none": "无",
    }.get(str(market or ""), str(market or ""))


def _movement_market_key(market: Any) -> str:
    normalized = str(market or "").strip().lower()
    if normalized in {"1x2", "h2h", "moneyline", "moneyline_1x2"}:
        return "h2h"
    if normalized in {"asian_handicap", "spreads", "spread"}:
        return "asian_handicap"
    if normalized in {"over_under", "totals", "total"}:
        return "over_under"
    return normalized


def _movement_selection_key(candidate: dict[str, Any]) -> str:
    selection_key = str(candidate.get("selection_key") or "").strip().lower()
    market = _movement_market_key(candidate.get("market"))
    if market == "h2h":
        if selection_key in {"home", "h"}:
            return "home"
        if selection_key in {"draw", "d", "x"}:
            return "draw"
        if selection_key in {"away", "a"}:
            return "away"
    if market == "asian_handicap":
        if selection_key in {"home_cover", "home", "h"}:
            return "home_cover"
        if selection_key in {"away_cover", "away", "a"}:
            return "away_cover"
    if market == "over_under":
        if selection_key in {"over", "o"}:
            return "over"
        if selection_key in {"under", "u"}:
            return "under"
    return selection_key


def _candidate_market_movement(
    candidate: dict[str, Any],
    market_movement: dict[str, Any] | None,
) -> dict[str, Any]:
    movement = market_movement or {}
    markets = movement.get("markets") if isinstance(movement.get("markets"), dict) else {}
    market = _movement_market_key(candidate.get("market"))
    selection_key = _movement_selection_key(candidate)
    market_summary = markets.get(market) if isinstance(markets, dict) else None
    selections = market_summary.get("selections") if isinstance(market_summary, dict) else {}
    selection_summary = selections.get(selection_key) if isinstance(selections, dict) else None
    return selection_summary if isinstance(selection_summary, dict) else {}


def _candidate_market_movement_signal(movement: dict[str, Any]) -> str:
    status = str(movement.get("status") or "")
    if status != "available":
        return status or "unavailable"
    probability_delta = parse_float(movement.get("implied_probability_delta"))
    if probability_delta is None:
        return "unavailable"
    if abs(probability_delta) < 0.005:
        return "stable"
    if probability_delta > 0:
        return "supports_selection"
    return "against_selection"


def _candidate_market_movement_note(candidate: dict[str, Any], movement: dict[str, Any]) -> str:
    signal = _candidate_market_movement_signal(movement)
    if signal in {"unavailable", "insufficient_history"}:
        return ""
    odds_text = ""
    opening = parse_float(movement.get("opening_decimal_odds"))
    latest = parse_float(movement.get("latest_decimal_odds"))
    if opening is not None and latest is not None:
        odds_text = f"赔率 {opening:g}->{latest:g}"
    probability_delta = _edge_text(movement.get("implied_probability_delta"))
    line_delta = parse_float(movement.get("line_delta"))
    line_text = f"，盘口线变化 {line_delta:+g}" if line_delta is not None and abs(line_delta) > 0 else ""
    direction = str(movement.get("direction_label") or "")
    selection = str(candidate.get("selection") or movement.get("selection") or "").strip()
    probability_text = f"，隐含概率 {probability_delta}" if probability_delta else ""
    return "盘口走势：{}{}{}{}。".format(
        f"{selection} " if selection else "",
        direction,
        f"，{odds_text}" if odds_text else "",
        f"{probability_text}{line_text}",
    )


def _enrich_candidate_with_market_movement(
    candidate: dict[str, Any],
    market_movement: dict[str, Any] | None,
) -> dict[str, Any]:
    movement = _candidate_market_movement(candidate, market_movement)
    signal = _candidate_market_movement_signal(movement)
    if not movement:
        return {
            **candidate,
            "market_movement_signal": "unavailable",
            "market_movement_note": "",
        }
    evidence_keys = (
        "status",
        "direction",
        "direction_label",
        "opening_decimal_odds",
        "latest_decimal_odds",
        "odds_delta",
        "opening_line",
        "latest_line",
        "line_delta",
        "implied_probability_delta",
        "bookmaker_count",
        "snapshot_count",
        "first_observed_at_utc",
        "latest_observed_at_utc",
    )
    movement_evidence = {key: movement.get(key) for key in evidence_keys if key in movement}
    return {
        **candidate,
        "market_movement": movement_evidence,
        "market_movement_signal": signal,
        "market_movement_probability_delta": movement.get("implied_probability_delta"),
        "market_movement_note": _candidate_market_movement_note(candidate, movement),
    }


def _percent_text(value: Any) -> str:
    number = parse_float(value)
    if number is None:
        return ""
    return f"{round(number * 100, 1)}%"


def _signed_decimal_text(value: Any) -> str:
    number = parse_float(value)
    if number is None:
        return ""
    return f"{number:+.4f}"


def _edge_text(value: Any) -> str:
    number = parse_float(value)
    if number is None:
        return ""
    return f"{round(number * 100, 1)}%"


def _decision_action_text(recommendation: str) -> str:
    if recommendation == "immediate_bet":
        return "立即投注"
    if recommendation == "condition_observe":
        return "条件观察"
    return "不投注"


def _build_final_decision(
    best_candidate: dict[str, Any],
    *,
    blocking_flags: list[str],
    caution_flags: list[str],
) -> dict[str, Any]:
    recommendation = str(best_candidate.get("recommendation") or "no_bet")
    action = _decision_action_text(recommendation)
    market = str(best_candidate.get("market") or "none")
    market_label = _market_label(market)
    selection = str(best_candidate.get("selection") or "").strip()
    stake_level = str(best_candidate.get("stake_level") or "none")
    provider = str(best_candidate.get("provider") or "").strip()
    decimal_odds = best_candidate.get("decimal_odds")
    line = best_candidate.get("line")

    odds_part = f" @ {decimal_odds:g}" if isinstance(decimal_odds, (int, float)) else ""
    provider_part = f"（{provider}）" if provider else ""
    if recommendation == "immediate_bet":
        headline = f"立即投注：{market_label} {selection}{odds_part}，{stake_level}{provider_part}"
    elif recommendation == "condition_observe":
        condition = str(best_candidate.get("condition") or "等待盘口与 MCP 共识保持一致且无新增 blocking_flags")
        headline = f"现在不下单：{market_label} {selection} 条件观察，触发条件：{condition}"
    else:
        reason = str(best_candidate.get("reason") or "无正边际或存在硬阻断")
        headline = f"不投注：{reason}"

    rationale = []
    market_probability = _percent_text(best_candidate.get("market_probability"))
    model_probability = _percent_text(best_candidate.get("model_probability"))
    edge = _edge_text(best_candidate.get("edge"))
    probability_edge = _edge_text(best_candidate.get("probability_edge"))
    if model_probability and market_probability:
        rationale.append(f"MCP 模型概率 {model_probability} vs 市场隐含 {market_probability}")
    if edge:
        edge_label = "MCP EV边际" if best_candidate.get("edge_basis") == "expected_multiplier_minus_1" else "MCP 概率边际"
        rationale.append(f"{edge_label} {edge}")
    if probability_edge and best_candidate.get("edge_basis") == "expected_multiplier_minus_1":
        rationale.append(f"MCP 去水概率差 {probability_edge}")
    expected_total = best_candidate.get("expected_total_goals")
    if expected_total is not None:
        rationale.append(f"MCP 预期总进球 {expected_total}")
    if line is not None:
        rationale.append(f"盘口线 {line}")
    market_movement_note = str(best_candidate.get("market_movement_note") or "").strip()
    if market_movement_note:
        rationale.append(market_movement_note)

    return {
        "action": action,
        "recommendation": recommendation,
        "headline": headline,
        "market": market,
        "market_label": market_label,
        "selection": selection,
        "provider": provider,
        "decimal_odds": decimal_odds,
        "line": line,
        "stake_level": stake_level,
        "rationale": rationale,
        "blocking_flags": blocking_flags,
        "caution_flags": caution_flags,
        "agent_instruction": (
            "Final agents must use this object as the visible conclusion anchor. "
            "They may explain it with MCP facts, but must not override it with self-made probability adjustments."
        ),
    }


def _build_risk_overlay(
    *,
    odds: dict[str, Any],
    blocking_flags: list[str],
    caution_flags: list[str],
    best_candidate: dict[str, Any],
    confidence: float,
) -> dict[str, Any]:
    asian_consensus = odds.get("asian_handicap_consensus") or {}
    totals_consensus = odds.get("over_under_consensus") or {}
    outlier_count = len(asian_consensus.get("outlier_markets") or []) + len(totals_consensus.get("outlier_markets") or [])
    structured_market_warnings = [
        flag
        for flag in caution_flags
        if "consensus_" in flag or "timestamp_" in flag or "price_outlier" in flag
    ]
    severity = "low"
    if blocking_flags:
        severity = "high"
    elif outlier_count >= 3 or len(caution_flags) >= 5 or confidence < 0.5:
        severity = "medium"
    elif structured_market_warnings or len(caution_flags) >= 3:
        severity = "medium"

    stake_adjustment = "none"
    if severity == "medium" and best_candidate.get("stake_level") == "small_to_normal":
        stake_adjustment = "cap_to_small"
    if best_candidate.get("recommendation") in {"no_bet", "no_value"}:
        stake_adjustment = "none"

    return {
        "source": "mcp_calculated_risk_overlay",
        "severity": severity,
        "blocking_flags": blocking_flags,
        "caution_flags": caution_flags,
        "structured_market_warnings": structured_market_warnings,
        "asian_outlier_count": len(asian_consensus.get("outlier_markets") or []),
        "over_under_outlier_count": len(totals_consensus.get("outlier_markets") or []),
        "stake_adjustment": stake_adjustment,
        "agent_rule": (
            "Agents may quote this overlay but must not invent new risk facts or independently change the final action."
        ),
    }


def _build_final_execution_advice(
    *,
    final_decision: dict[str, Any],
    best_candidate: dict[str, Any],
    risk_overlay: dict[str, Any],
) -> dict[str, Any]:
    raw_recommendation = str(final_decision.get("recommendation") or best_candidate.get("recommendation") or "no_bet")
    if risk_overlay.get("blocking_flags"):
        action = "skip"
        action_label = "不投注"
    elif raw_recommendation == "immediate_bet":
        action = "bet_now"
        action_label = "立即投注"
    elif raw_recommendation == "condition_observe":
        action = "observe"
        action_label = "条件观察"
    else:
        action = "skip"
        action_label = "不投注"

    stake_level = str(final_decision.get("stake_level") or best_candidate.get("stake_level") or "none")
    if risk_overlay.get("stake_adjustment") == "cap_to_small" and stake_level == "small_to_normal":
        stake_level = "small"
    if action == "skip":
        stake_level = "none"
    elif action == "observe" and stake_level == "none":
        stake_level = "watch_only_until_condition"

    market_label = str(final_decision.get("market_label") or _market_label(str(best_candidate.get("market") or "none")))
    selection = str(final_decision.get("selection") or best_candidate.get("selection") or "").strip()
    decimal_odds = final_decision.get("decimal_odds", best_candidate.get("decimal_odds"))
    odds_part = f" @ {decimal_odds:g}" if isinstance(decimal_odds, (int, float)) else ""

    if action == "bet_now":
        headline = f"最终执行：立即投注 {market_label} {selection}{odds_part}，仓位 {stake_level}"
    elif action == "observe":
        condition = str(best_candidate.get("condition") or "等待 MCP 最新盘口仍满足当前条件且无 blocking_flags")
        headline = f"最终执行：条件观察 {market_label} {selection}，触发条件：{condition}"
    else:
        reason = str(best_candidate.get("reason") or "无正边际或存在硬阻断")
        headline = f"最终执行：不投注，原因：{reason}"

    return {
        "source": "mcp_calculated_final_execution_advice",
        "action": action,
        "action_label": action_label,
        "headline": headline,
        "raw_mcp_recommendation": raw_recommendation,
        "market": final_decision.get("market") or best_candidate.get("market") or "none",
        "market_label": market_label,
        "selection": selection,
        "provider": final_decision.get("provider") or best_candidate.get("provider") or "",
        "decimal_odds": decimal_odds,
        "line": final_decision.get("line", best_candidate.get("line")),
        "stake_level": stake_level,
        "risk_overlay_severity": risk_overlay.get("severity"),
        "risk_overlay_applied": risk_overlay.get("stake_adjustment"),
        "agent_can_override": False,
        "agent_instruction": (
            "All downstream agents must use this object as the only final execution conclusion. "
            "They may compare it with final_decision as raw MCP recommendation, but must not rewrite action or stake_level."
        ),
    }


def _minutes_to_kickoff(time_window: dict[str, Any] | None) -> float | None:
    time_window = time_window or {}
    try:
        as_of_raw = time_window.get("as_of")
        kickoff_raw = time_window.get("kickoff")
        if not as_of_raw or not kickoff_raw:
            return None
        as_of = date_parser.parse(str(as_of_raw))
        kickoff = date_parser.parse(str(kickoff_raw))
        if as_of.tzinfo is None:
            as_of = as_of.replace(tzinfo=DEFAULT_USER_TIMEZONE)
        if kickoff.tzinfo is None:
            kickoff = kickoff.replace(tzinfo=DEFAULT_USER_TIMEZONE)
    except (TypeError, ValueError):
        return None
    return round_metric((kickoff.astimezone(timezone.utc) - as_of.astimezone(timezone.utc)).total_seconds() / 60)


def build_betting_decision_support(
    *,
    match: dict[str, Any],
    odds: dict[str, Any],
    form: dict[str, Any],
    match_context: dict[str, Any] | None,
    quality_flags: list[str],
    quality_warnings: list[str],
    market_movement: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build deterministic betting guardrails so agents do not turn every caution into no-bet."""
    market_movement = market_movement or {}
    blocking_flags: list[str] = []
    caution_flags: list[str] = []
    for flag in quality_flags:
        _append_unique(blocking_flags, flag)
    for warning in quality_warnings:
        _append_unique(caution_flags, warning)

    odds_quality = odds.get("quality_contract") or {}
    supported = odds_quality.get("supported_markets") or {}
    if odds_quality and not odds_quality.get("can_use_for_calculation", True):
        for flag in odds_quality.get("hard_flags") or []:
            _append_unique(blocking_flags, flag)
    if not supported.get("moneyline_1x2") and not supported.get("asian_handicap"):
        _append_unique(blocking_flags, "supported_market_missing")

    consensus = odds.get("asian_handicap_consensus") or {}
    for warning in consensus.get("warnings") or []:
        _append_unique(caution_flags, f"asian_handicap_consensus_{warning}")
    totals_consensus = odds.get("over_under_consensus") or {}
    for warning in totals_consensus.get("warnings") or []:
        _append_unique(caution_flags, f"over_under_consensus_{warning}")

    lineup = (match_context or {}).get("lineup") or {}
    lineup_analysis = lineup.get("lineup_analysis") or {}
    if match_context is not None:
        if not lineup.get("available"):
            _append_unique(caution_flags, "lineup_unavailable")
        elif lineup_analysis and not lineup_analysis.get("can_use_for_analysis"):
            _append_unique(caution_flags, "lineup_context_limited")
        for warning in lineup_analysis.get("warnings") or []:
            normalized_warning = re.sub(r"\s+", "_", str(warning or "").strip())
            if normalized_warning == "lineup_unavailable":
                _append_unique(caution_flags, "lineup_unavailable")
            else:
                _append_unique(caution_flags, f"lineup_{normalized_warning}")

    if not (form or {}).get("available"):
        _append_unique(caution_flags, "form_context_limited")

    minutes = _minutes_to_kickoff(match.get("time_window") or {})
    if minutes is not None and 0 <= minutes < 60:
        _append_unique(caution_flags, "near_kickoff_under_60m")

    confidence = 0.56
    if supported.get("moneyline_1x2"):
        confidence += 0.05
    if supported.get("asian_handicap"):
        confidence += 0.05
    if supported.get("over_under"):
        confidence += 0.03
    if consensus.get("available") and not consensus.get("warnings"):
        confidence += 0.03
    if (form or {}).get("available"):
        confidence += 0.03
    confidence -= min(len(caution_flags), 6) * 0.015
    confidence = round_metric(_clamp(confidence, 0.35, 0.72)) or 0.0

    model_projection = model_engine.build_model_projection(
        match=match,
        odds=odds,
        form=form,
    )
    model_projection_available = bool(model_projection.get("available"))
    projection_probabilities = model_projection.get("derived_probabilities") or {}
    projection_edges = model_projection.get("market_edges") or {}
    projection_source = str(
        model_projection.get("probability_source") or "MCP Dixon-Coles adjusted scoreline distribution"
    )

    candidates: list[dict[str, Any]] = []
    moneyline = odds_quality.get("preferred_moneyline_1x2") or {}
    moneyline_metrics = (moneyline.get("current_metrics") or {})
    market_1x2 = moneyline_metrics.get("normalized_probability") or {}
    if model_projection_available and projection_probabilities.get("1x2"):
        model_1x2 = projection_probabilities.get("1x2") or {}
        movement_delta = 0.0
        probability_source = projection_source
        edge_source = "model_engine"
    else:
        model_1x2 = _adjust_moneyline_probabilities(market_1x2, form)
        movement_delta = _moneyline_movement_delta(moneyline)
        model_1x2 = _apply_home_delta(model_1x2, movement_delta)
        probability_source = "MCP market probability plus bounded recent-form and market-movement heuristic"
        edge_source = "bounded_heuristic"
    if moneyline_metrics.get("available") and model_1x2:
        moneyline_decimal_odds = (moneyline.get("current") or {}) or (moneyline_metrics.get("odds") or {})
        labels = {"home": "主胜", "draw": "平局", "away": "客胜"}
        side_names = {
            "home": f"{match.get('home_team') or '主队'} 主胜",
            "draw": "平局",
            "away": f"{match.get('away_team') or '客队'} 客胜",
        }
        edges = {
            key: round_metric(
                parse_float((projection_edges.get("1x2") or {}).get(key))
                if edge_source == "model_engine" and (projection_edges.get("1x2") or {}).get(key) is not None
                else (model_1x2.get(key) or 0) - (parse_float(market_1x2.get(key)) or 0)
            )
            for key in ("home", "draw", "away")
        }
        value_by_side = {}
        for key, probability_edge in edges.items():
            value_by_side[key] = _candidate_value_metrics(
                model_probability=model_1x2.get(key),
                market_probability=market_1x2.get(key),
                decimal_odds=moneyline_decimal_odds.get(key),
                probability_edge=probability_edge,
            )
        best_side = max(value_by_side, key=lambda key: parse_float((value_by_side[key] or {}).get("edge")) or -999)
        value_metrics = value_by_side.get(best_side) or {}
        edge = value_metrics.get("edge")
        recommendation = _recommendation_from_edge(edge, confidence, blocking_flags)
        candidates.append(
            {
                "market": "1x2",
                "selection": side_names.get(best_side) or labels[best_side],
                "selection_key": best_side,
                "provider": moneyline.get("provider") or "",
                "recommendation": recommendation,
                "stake_level": _stake_level(recommendation, confidence, len(caution_flags)),
                "edge": edge,
                "probability_edge": value_metrics.get("probability_edge"),
                "expected_multiplier": value_metrics.get("expected_multiplier"),
                "edge_basis": value_metrics.get("edge_basis"),
                "decimal_odds": parse_float(moneyline_decimal_odds.get(best_side)),
                "market_probability": round_metric(parse_float(market_1x2.get(best_side))),
                "model_probability": round_metric(model_1x2.get(best_side)),
                "probability_source": probability_source,
                "edge_source": edge_source,
                "market_movement_home_delta": round_metric(movement_delta),
                "condition": (
                    "Only act if latest 1X2 price stays within 3% of this snapshot and no new blocking flag appears."
                    if recommendation == "condition_observe"
                    else ""
                ),
            }
        )

    official_hhad = odds.get("official_jingcai_hhad") or {}
    hhad_metrics = official_hhad.get("current_metrics") or {}
    hhad_market = hhad_metrics.get("normalized_probability") or {}
    hhad_goal_line = parse_float(official_hhad.get("home_goal_line"))
    scoreline_distribution = model_projection.get("scoreline_distribution") or []
    if model_projection_available and hhad_metrics.get("available") and hhad_goal_line is not None and scoreline_distribution:
        hhad_model = _official_hhad_model_probabilities(scoreline_distribution, hhad_goal_line)
        hhad_edges = {
            key: round_metric((hhad_model.get(key) or 0) - (parse_float(hhad_market.get(key)) or 0))
            for key in ("home", "draw", "away")
        }
        hhad_value_by_side = {
            key: _candidate_value_metrics(
                model_probability=hhad_model.get(key),
                market_probability=hhad_market.get(key),
                decimal_odds=(official_hhad.get("current") or {}).get(key),
                probability_edge=hhad_edges.get(key),
            )
            for key in ("home", "draw", "away")
        }
        hhad_best_side = max(
            hhad_value_by_side,
            key=lambda key: parse_float((hhad_value_by_side[key] or {}).get("edge")) or -999,
        )
        hhad_value_metrics = hhad_value_by_side.get(hhad_best_side) or {}
        hhad_edge = hhad_value_metrics.get("edge")
        hhad_recommendation = _recommendation_from_edge(hhad_edge, confidence, blocking_flags)
        hhad_selection_labels = {
            "home": f"{match.get('home_team') or '主队'}({hhad_goal_line:+g}) 让胜",
            "draw": f"{match.get('home_team') or '主队'}({hhad_goal_line:+g}) 让平",
            "away": f"{match.get('home_team') or '主队'}({hhad_goal_line:+g}) 让负",
        }
        candidates.append(
            {
                "market": "jingcai_hhad",
                "selection": hhad_selection_labels.get(hhad_best_side) or "",
                "selection_key": hhad_best_side,
                "provider": official_hhad.get("provider") or "",
                "recommendation": hhad_recommendation,
                "stake_level": _stake_level(hhad_recommendation, confidence, len(caution_flags)),
                "edge": hhad_edge,
                "probability_edge": hhad_value_metrics.get("probability_edge"),
                "expected_multiplier": hhad_value_metrics.get("expected_multiplier"),
                "edge_basis": hhad_value_metrics.get("edge_basis"),
                "decimal_odds": parse_float((official_hhad.get("current") or {}).get(hhad_best_side)),
                "line": hhad_goal_line,
                "market_probability": round_metric(parse_float(hhad_market.get(hhad_best_side))),
                "model_probability": round_metric(hhad_model.get(hhad_best_side)),
                "probability_source": projection_source,
                "edge_source": "model_engine",
                "condition": (
                    "Only act if latest Sporttery HHAD price stays within 3% of this snapshot and no new blocking flag appears."
                    if hhad_recommendation == "condition_observe"
                    else ""
                ),
                "official_pool": "HHAD",
                "odds_source": "sporttery_official_hhad",
                "settlement_rule": official_hhad.get("settlement_rule") or "",
                "agent_rule": official_hhad.get("agent_rule") or "",
            }
        )

    asian = odds_quality.get("preferred_asian_handicap") or {}
    asian_metrics = asian.get("current_metrics") or {}
    market_asian = asian_metrics.get("normalized_probability") or {}
    line = parse_float(asian_metrics.get("line"))
    projection_asian = projection_probabilities.get("asian_handicap") or {}
    if (
        model_projection_available
        and projection_asian
        and line is not None
        and parse_float(projection_asian.get("line")) == line
    ):
        model_asian = projection_asian
        asian_probability_source = projection_source
        asian_edge_source = "model_engine"
    elif line is not None and model_1x2:
        model_asian = _asian_model_cover_probabilities(line, model_1x2)
        asian_probability_source = "MCP Asian handicap price plus 1X2/recent-form/market-movement cover approximation"
        asian_edge_source = "bounded_heuristic"
    else:
        model_asian = {}
        asian_probability_source = "unavailable"
        asian_edge_source = "unavailable"
    if asian_metrics.get("available") and line is not None and model_asian:
        edges = {
            key: round_metric(
                parse_float((projection_edges.get("asian_handicap") or {}).get(key))
                if asian_edge_source == "model_engine" and (projection_edges.get("asian_handicap") or {}).get(key) is not None
                else (model_asian.get(key) or 0) - (parse_float(market_asian.get(key)) or 0)
            )
            for key in ("home_cover", "away_cover")
        }
        value_by_side = {
            key: _candidate_value_metrics(
                model_probability=model_asian.get(key),
                market_probability=market_asian.get(key),
                decimal_odds=(asian_metrics.get("decimal_odds") or {}).get(key),
                probability_edge=edges.get(key),
            )
            for key in ("home_cover", "away_cover")
        }
        best_side = max(value_by_side, key=lambda key: parse_float((value_by_side[key] or {}).get("edge")) or -999)
        value_metrics = value_by_side.get(best_side) or {}
        edge = value_metrics.get("edge")
        recommendation = _recommendation_from_edge(edge, confidence, blocking_flags)
        side_label = match.get("home_team") if best_side == "home_cover" else match.get("away_team")
        if not side_label:
            side_label = "主队" if best_side == "home_cover" else "客队"
        handicap = line if best_side == "home_cover" else -line
        decimal_odds = (asian_metrics.get("decimal_odds") or {}).get(best_side)
        candidates.append(
            {
                "market": "asian_handicap",
                "selection": f"{side_label} {handicap:+g}",
                "selection_key": best_side,
                "provider": asian.get("provider") or "",
                "recommendation": recommendation,
                "stake_level": _stake_level(recommendation, confidence, len(caution_flags)),
                "edge": edge,
                "probability_edge": value_metrics.get("probability_edge"),
                "expected_multiplier": value_metrics.get("expected_multiplier"),
                "edge_basis": value_metrics.get("edge_basis"),
                "decimal_odds": parse_float(decimal_odds),
                "line": handicap,
                "market_probability": round_metric(parse_float(market_asian.get(best_side))),
                "model_probability": round_metric(model_asian.get(best_side)),
                "probability_source": asian_probability_source,
                "edge_source": asian_edge_source,
                "condition": (
                    "Only act if preferred line still matches asian_handicap_consensus.main_line and no new line split appears."
                    if recommendation == "condition_observe"
                    else ""
                ),
                "consensus_main_line": (consensus.get("main_line") or {}).get("line"),
                "consensus_complete_market_count": consensus.get("complete_market_count"),
            }
        )

    totals = odds_quality.get("preferred_over_under") or {}
    totals_metrics = totals.get("current_metrics") or {}
    totals_market = totals_metrics.get("normalized_probability") or {}
    totals_line = parse_float(totals_metrics.get("line"))
    projection_totals = projection_probabilities.get("over_under") or {}
    if (
        model_projection_available
        and projection_totals
        and totals_line is not None
        and parse_float(projection_totals.get("line")) == totals_line
    ):
        totals_model = projection_totals
        totals_probability_source = projection_source
        totals_edge_source = "model_engine"
        expected_total_goals = (model_projection.get("expected_goals") or {}).get("total")
    else:
        totals_model = _over_under_model_probabilities(totals_line, form) if totals_line is not None else {}
        totals_probability_source = "MCP totals price plus recent goals heuristic"
        totals_edge_source = "bounded_heuristic"
        expected_total_goals = _expected_total_goals(form)
    if totals_metrics.get("available") and totals_model:
        edges = {
            key: round_metric(
                parse_float((projection_edges.get("over_under") or {}).get(key))
                if totals_edge_source == "model_engine" and (projection_edges.get("over_under") or {}).get(key) is not None
                else (totals_model.get(key) or 0) - (parse_float(totals_market.get(key)) or 0)
            )
            for key in ("over", "under")
        }
        value_by_side = {
            key: _candidate_value_metrics(
                model_probability=totals_model.get(key),
                market_probability=totals_market.get(key),
                decimal_odds=(totals_metrics.get("decimal_odds") or {}).get(key),
                probability_edge=edges.get(key),
            )
            for key in ("over", "under")
        }
        best_side = max(value_by_side, key=lambda key: parse_float((value_by_side[key] or {}).get("edge")) or -999)
        value_metrics = value_by_side.get(best_side) or {}
        edge = value_metrics.get("edge")
        recommendation = _recommendation_from_edge(edge, confidence, blocking_flags)
        labels = {"over": "大球", "under": "小球"}
        decimal_odds = (totals_metrics.get("decimal_odds") or {}).get(best_side)
        candidates.append(
            {
                "market": "over_under",
                "selection": f"{labels[best_side]} {totals_line:g}",
                "selection_key": best_side,
                "provider": totals.get("provider") or "",
                "recommendation": recommendation,
                "stake_level": _stake_level(recommendation, confidence, len(caution_flags)),
                "edge": edge,
                "probability_edge": value_metrics.get("probability_edge"),
                "expected_multiplier": value_metrics.get("expected_multiplier"),
                "edge_basis": value_metrics.get("edge_basis"),
                "decimal_odds": parse_float(decimal_odds),
                "line": totals_line,
                "market_probability": round_metric(parse_float(totals_market.get(best_side))),
                "model_probability": round_metric(totals_model.get(best_side)),
                "expected_total_goals": expected_total_goals,
                "probability_source": totals_probability_source,
                "edge_source": totals_edge_source,
                "condition": (
                    "Only act if preferred total line still matches over_under_consensus.main_line and no new total-line split appears."
                    if recommendation == "condition_observe"
                    else ""
                ),
                "consensus_main_line": (totals_consensus.get("main_line") or {}).get("line"),
                "consensus_complete_market_count": totals_consensus.get("complete_market_count"),
            }
        )

    if candidates:
        candidates = [
            _enrich_candidate_with_market_movement(candidate, market_movement)
            for candidate in candidates
        ]

    if blocking_flags:
        best_candidate = {
            "market": "none",
            "selection": "",
            "recommendation": "no_bet",
            "stake_level": "none",
            "reason": "blocking_flags_present",
        }
    else:
        ranked = sorted(
            candidates,
            key=lambda item: (
                {"immediate_bet": 2, "condition_observe": 1, "no_value": 0}.get(str(item.get("recommendation")), 0),
                parse_float(item.get("edge")) or -999,
            ),
            reverse=True,
        )
        best_candidate = ranked[0] if ranked else {
            "market": "none",
            "selection": "",
            "recommendation": "no_bet",
            "stake_level": "none",
            "reason": "no_supported_candidate",
        }
        if best_candidate.get("recommendation") == "no_value":
            best_candidate = {
                **best_candidate,
                "recommendation": "no_bet",
                "stake_level": "none",
                "reason": "no_positive_edge",
            }
        movement_delta = parse_float(best_candidate.get("market_movement_probability_delta"))
        movement_signal = str(best_candidate.get("market_movement_signal") or "")
        if movement_signal == "against_selection" and abs(movement_delta or 0.0) >= 0.02:
            _append_unique(caution_flags, "market_movement_against_selection")
    final_decision = _build_final_decision(
        best_candidate,
        blocking_flags=blocking_flags,
        caution_flags=caution_flags,
    )
    risk_overlay = _build_risk_overlay(
        odds=odds,
        blocking_flags=blocking_flags,
        caution_flags=caution_flags,
        best_candidate=best_candidate,
        confidence=confidence,
    )
    final_execution_advice = _build_final_execution_advice(
        final_decision=final_decision,
        best_candidate=best_candidate,
        risk_overlay=risk_overlay,
    )

    return {
        "blocking_flags": blocking_flags,
        "caution_flags": caution_flags,
        "confidence": confidence,
        "minutes_to_kickoff": minutes,
        "form_signal": _form_signal(form),
        "model_engine": model_projection,
        "market_movement": market_movement,
        "market_candidates": candidates,
        "best_candidate": best_candidate,
        "final_decision": final_decision,
        "risk_overlay": risk_overlay,
        "final_execution_advice": final_execution_advice,
        "decision_rule": "Only blocking_flags can force skip/no-bet; caution_flags are handled by MCP risk_overlay and final_execution_advice.",
        "agent_guidance": (
            "Use final_execution_advice as the only final action. Do not convert caution_flags such as lineup_unavailable, "
            "near_kickoff_under_60m, tactical gaps, timestamp soft warnings, or market line split into no-bet by yourself. "
            "If final_execution_advice.action is bet_now, output how to bet with its stake_level; "
            "if observe, output the exact condition; if skip, output the MCP blocker/reason."
        ),
    }


def build_model_card(
    *,
    match: dict[str, Any],
    odds: dict[str, Any],
    form: dict[str, Any],
    quality: dict[str, Any],
    betting_decision_support: dict[str, Any],
) -> dict[str, Any]:
    supported = ((odds.get("quality_contract") or {}).get("supported_markets") or {})
    model_projection = betting_decision_support.get("model_engine") or {}
    model_available = bool(model_projection.get("available"))
    return {
        "version": "football-data-mcp-model-card-2026-05-23",
        "match_key": {
            "home_team": match.get("home_team") or "",
            "away_team": match.get("away_team") or "",
            "kickoff_utc": match.get("kickoff_utc"),
        },
        "probability_boundary": (
            "mcp_market_anchored_scoreline_model"
            if model_available
            else "mcp_market_anchored_bounded_heuristic"
        ),
        "model_engine": {
            "available": model_available,
            "version": model_projection.get("version"),
            "method": model_projection.get("method"),
            "expected_goals": model_projection.get("expected_goals") or {},
            "dixon_coles": model_projection.get("dixon_coles") or {},
            "fitted_market_targets": model_projection.get("fitted_market_targets") or {},
            "model_quality": model_projection.get("model_quality") or {},
            "probability_source": model_projection.get("probability_source") or "",
        },
        "market_inputs": {
            "moneyline_1x2": bool(supported.get("moneyline_1x2")),
            "asian_handicap": bool(supported.get("asian_handicap")),
            "over_under": bool(supported.get("over_under")),
            "asian_consensus": bool((odds.get("asian_handicap_consensus") or {}).get("available")),
            "over_under_consensus": bool((odds.get("over_under_consensus") or {}).get("available")),
        },
        "context_inputs": {
            "recent_form": bool((form or {}).get("recent_record_summary") or (form or {}).get("recent_record")),
            "league_table": bool((form or {}).get("league_table_summary", {}).get("available")),
            "battle_history": bool((form or {}).get("battle_history", {}).get("matches")),
        },
        "calculation_limits": [
            "No agent-side confidence interval, EV, Kelly, or separate probability model is authorized.",
            (
                "MCP candidates use the scoreline model when model_engine.available is true; otherwise they fall back to bounded market/form heuristics."
            ),
            "Lineup/weather/referee context may be quoted only when MCP returns structured usable fields.",
        ],
        "quality": {
            "is_bettable_input": bool((quality or {}).get("is_bettable_input")),
            "blocking_flags": betting_decision_support.get("blocking_flags") or [],
            "caution_flags": betting_decision_support.get("caution_flags") or [],
            "confidence": betting_decision_support.get("confidence"),
        },
        "agent_rule": "Downstream agents must quote this card instead of inventing model weights, EV, Kelly, or confidence intervals.",
    }


def build_professional_scorecard(
    *,
    match: dict[str, Any],
    odds: dict[str, Any],
    form: dict[str, Any],
    match_context: dict[str, Any] | None,
    source_probe: dict[str, Any],
    quality: dict[str, Any],
    betting_decision_support: dict[str, Any],
    model_card: dict[str, Any],
) -> dict[str, Any]:
    supported = ((odds.get("quality_contract") or {}).get("supported_markets") or {})
    supported_count = sum(1 for key in ["moneyline_1x2", "asian_handicap", "over_under"] if supported.get(key))
    schedule_ready = bool(match.get("home_team") and match.get("away_team") and match.get("kickoff_utc"))
    form_ready = bool((form or {}).get("recent_record_summary") or (form or {}).get("recent_record"))
    source_ready = (parse_float(source_probe.get("usable_source_count")) or 0) > 0
    context_ready = bool(match_context)
    asian_consensus = odds.get("asian_handicap_consensus") or {}
    totals_consensus = odds.get("over_under_consensus") or {}
    final_execution = betting_decision_support.get("final_execution_advice") or {}
    blockers = betting_decision_support.get("blocking_flags") or []
    cautions = betting_decision_support.get("caution_flags") or []
    confidence = parse_float(betting_decision_support.get("confidence")) or 0

    data_collection = 6.0
    data_collection += 0.4 if schedule_ready else 0
    data_collection += min(supported_count, 3) * 0.25
    data_collection += 0.4 if form_ready else 0
    data_collection += 0.35 if source_ready else 0
    data_collection += 0.3 if context_ready else 0

    market_structure = 6.4
    market_structure += 0.25 if supported.get("moneyline_1x2") else 0
    market_structure += 0.35 if supported.get("asian_handicap") and asian_consensus.get("price_consensus") else 0
    market_structure += 0.3 if supported.get("over_under") and totals_consensus.get("price_consensus") else 0
    market_structure += 0.25 if "price_outlier_detected" not in (asian_consensus.get("warnings") or []) else 0.15
    market_structure += 0.2 if asian_consensus.get("outlier_markets") is not None else 0

    model_trust = 6.7
    model_trust += 0.35 if model_card.get("probability_boundary") else 0
    model_trust += 0.25 if betting_decision_support.get("market_candidates") else 0
    model_trust += 0.25 if form_ready else 0
    model_trust += 0.25 if not blockers else -0.8
    model_trust -= min(len(cautions), 4) * 0.03

    auditability = 6.8
    auditability += 0.3 if source_ready else 0
    auditability += 0.25 if quality else 0
    auditability += 0.25 if betting_decision_support.get("risk_overlay") else 0
    auditability += 0.25 if final_execution else 0

    conclusion_reliability = 6.8
    conclusion_reliability += 0.35 if final_execution else 0
    conclusion_reliability += 0.25 if not blockers else -0.8
    conclusion_reliability += 0.2 if confidence >= 0.55 else 0
    conclusion_reliability += 0.15 if supported_count >= 2 else 0
    conclusion_reliability -= min(len(cautions), 4) * 0.02

    scores = {
        "data_collection": round_metric(_clamp(data_collection, 0, 8.6), 2),
        "market_structuring": round_metric(_clamp(market_structure, 0, 8.4), 2),
        "model_trust": round_metric(_clamp(model_trust, 0, 8.0), 2),
        "auditability": round_metric(_clamp(auditability, 0, 8.2), 2),
        "betting_conclusion_reliability": round_metric(_clamp(conclusion_reliability, 0, 8.0), 2),
    }
    return {
        "scores": scores,
        "all_scores_at_least_7": all((value or 0) >= 7 for value in scores.values()),
        "scale": "0-10; 7 means usable for cautious pre-match decision support, not guaranteed profitability.",
        "improvements_over_previous": [
            "normalized_decimal_price_consensus",
            "price_outlier_detection",
            "mcp_risk_overlay",
            "single_final_execution_advice",
            "decision_audit_contract",
        ],
        "remaining_limits": [
            "Public web odds can still be delayed or blocked by source-side controls.",
            "The model is market-anchored and bounded; it is not a professionally backtested bookmaker model.",
        ],
    }


def build_decision_audit(
    *,
    match: dict[str, Any],
    betting_decision_support: dict[str, Any],
    professional_scorecard: dict[str, Any],
    model_card: dict[str, Any],
) -> dict[str, Any]:
    seed = {
        "match": {
            "home_team": match.get("home_team"),
            "away_team": match.get("away_team"),
            "league": match.get("league"),
            "kickoff_utc": match.get("kickoff_utc"),
        },
        "best_candidate": betting_decision_support.get("best_candidate") or {},
        "final_execution_advice": betting_decision_support.get("final_execution_advice") or {},
        "scorecard_scores": professional_scorecard.get("scores") or {},
    }
    digest = hashlib.sha256(json.dumps(seed, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:16]
    return {
        "audit_id": f"football-mcp-{digest}",
        "generated_at_utc": now_utc().isoformat(),
        "model_card_version": model_card.get("version"),
        "raw_final_decision": betting_decision_support.get("final_decision") or {},
        "risk_overlay": betting_decision_support.get("risk_overlay") or {},
        "final_execution_advice": betting_decision_support.get("final_execution_advice") or {},
        "professional_scorecard": professional_scorecard,
        "agent_contract": (
            "Quote this audit object when explaining why the final answer follows MCP. "
            "Do not create a parallel conclusion outside final_execution_advice."
        ),
    }


def build_analysis_pack(
    *,
    match: dict[str, Any],
    odds: dict[str, Any],
    form: dict[str, Any],
    match_context: dict[str, Any] | None,
    quality: dict[str, Any],
    betting_decision_support: dict[str, Any],
    data_bundle: dict[str, Any] | None = None,
) -> dict[str, Any]:
    odds_quality = odds.get("quality_contract") or {}
    supported = odds_quality.get("supported_markets") or {}
    lineup = (match_context or {}).get("lineup") or {}
    lineup_analysis = lineup.get("lineup_analysis") or {}
    matching_snapshot_count = ((data_bundle or {}).get("snapshot_store") or {}).get("matching_snapshot_count") or 0
    market_movement = (data_bundle or {}).get("market_movement") or {}
    data_blocks = {
        "schedule": bool(match.get("home_team") and match.get("away_team") and match.get("kickoff_utc")),
        "moneyline_1x2": bool(supported.get("moneyline_1x2")),
        "asian_handicap": bool(supported.get("asian_handicap")),
        "over_under": bool(supported.get("over_under")),
        "multi_bookmaker_snapshot": matching_snapshot_count > 0,
        "market_movement_history": market_movement.get("status") == "available",
        "recent_form": bool((form or {}).get("recent_record_summary")),
        "league_table": bool((form or {}).get("league_table_summary", {}).get("available")),
        "battle_history": bool((form or {}).get("battle_history", {}).get("matches")),
        "lineup": bool(lineup_analysis.get("can_use_for_analysis")),
        "weather": bool((lineup.get("base") or {}).get("weather")),
        "referee": bool((lineup.get("base") or {}).get("referee")),
    }
    available_blocks = [key for key, value in data_blocks.items() if value]
    missing_blocks = [key for key, value in data_blocks.items() if not value]
    market_intelligence = odds.get("market_intelligence") or build_market_intelligence(odds)
    model_projection = betting_decision_support.get("model_engine") or {}
    model_engine_summary = {
        "available": bool(model_projection.get("available")),
        "version": model_projection.get("version"),
        "method": model_projection.get("method"),
        "expected_goals": model_projection.get("expected_goals") or {},
        "derived_probabilities": model_projection.get("derived_probabilities") or {},
        "market_edges": model_projection.get("market_edges") or {},
        "top_scorelines": model_projection.get("top_scorelines") or [],
        "dixon_coles": model_projection.get("dixon_coles") or {},
        "fitted_market_targets": model_projection.get("fitted_market_targets") or {},
        "model_quality": model_projection.get("model_quality") or {},
        "probability_source": model_projection.get("probability_source") or "",
        "penaltyblog_adapter": model_projection.get("penaltyblog_adapter") or {},
    }

    return {
        "data_coverage": {
            "blocks": data_blocks,
            "available_blocks": available_blocks,
            "missing_blocks": missing_blocks,
            "rule": "Missing non-core context blocks are cautions, not no-bet blockers. Core blockers are in betting_decision_support.blocking_flags.",
        },
        "model_inputs": {
            "recent_form_summary": (form or {}).get("recent_record_summary") or {},
            "league_table_summary": (form or {}).get("league_table_summary") or {},
            "battle_history_summary": (form or {}).get("battle_history_summary") or {},
            "lineup_analysis": lineup_analysis or {},
            "market_intelligence": market_intelligence,
            "market_snapshot_consensus": (data_bundle or {}).get("market_consensus") or {},
            "market_snapshot_movement": market_movement,
            "quality": quality,
            "model_engine": model_engine_summary,
        },
        "agent_brief": {
            "match": {
                "home_team": match.get("home_team") or "",
                "away_team": match.get("away_team") or "",
                "league": match.get("league") or "",
                "kickoff_utc_plus_8": match.get("kickoff_utc_plus_8") or "",
            },
            "best_candidate": betting_decision_support.get("best_candidate") or {},
            "final_decision": betting_decision_support.get("final_decision") or {},
            "risk_overlay": betting_decision_support.get("risk_overlay") or {},
            "final_execution_advice": betting_decision_support.get("final_execution_advice") or {},
            "market_candidates": betting_decision_support.get("market_candidates") or [],
            "model_engine": {
                "available": model_engine_summary["available"],
                "version": model_engine_summary["version"],
                "method": model_engine_summary["method"],
                "expected_goals": model_engine_summary["expected_goals"],
                "fitted_market_targets": model_engine_summary["fitted_market_targets"],
                "top_scorelines": model_engine_summary["top_scorelines"][:5],
                "probability_source": model_engine_summary["probability_source"],
            },
            "data_bundle": {
                "source_coverage": (data_bundle or {}).get("source_coverage") or {},
                "snapshot_store": (data_bundle or {}).get("snapshot_store") or {},
                "market_consensus": (data_bundle or {}).get("market_consensus") or {},
                "market_movement": market_movement,
                "external_context": (data_bundle or {}).get("external_context") or {},
                "agent_contract": (data_bundle or {}).get("agent_contract") or {},
            },
            "decision_contract": (
                "Use betting_decision_support.final_execution_advice as the visible final-action anchor. "
                "Show final_decision only as raw MCP recommendation before risk overlay. "
                "Use market_candidates for per-market facts. Do not replace MCP model_probability/edge with self-made adjustments. "
                "Only MCP blocking_flags can force skip/no-bet; caution_flags are handled by MCP risk_overlay."
            ),
            "recommended_agent_order": [
                "情报采集读取 data_coverage 与质量合同",
                "盘口 Agent 读取 market_intelligence 与完整盘口",
                "模型 Agent 读取 model_card 与 candidates",
                "风控 Agent 只解释 MCP risk_overlay",
                "汇总 Agent 输出 final_execution_advice 的 bet_now/observe/skip 之一",
            ],
        },
    }


def with_odds_quality_contract(
    odds: dict[str, Any],
    source: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        **(odds or {}),
        "quality_contract": build_odds_quality_contract(odds or {}, source),
    }


def merge_odds(primary: dict[str, Any], secondary: dict[str, Any]) -> dict[str, Any]:
    primary = primary or {}
    secondary = secondary or {}
    if secondary.get("has_valid_numeric_odds"):
        return {
            **secondary,
            "schedule_snapshot": primary,
            "has_valid_numeric_odds": True,
            "market_policy": {
                **(secondary.get("market_policy") or {}),
                "schedule_snapshot": "Backup only; do not mix with preferred market calculations.",
            },
        }
    return primary


def analysis_readiness_for_dongqiudi_match(match: dict[str, Any]) -> dict[str, Any]:
    home = ((match.get("team_A") or {}).get("name") or "")
    away = ((match.get("team_B") or {}).get("name") or "")
    kickoff = parse_dongqiudi_kickoff(match.get("start_play"))
    odds = odds_from_dongqiudi_match(match)
    missing = []
    if not match.get("match_id"):
        missing.append("match_id_missing")
    if not (home and away and kickoff):
        missing.append("schedule_anchor_missing")
    if not odds.get("has_valid_numeric_odds"):
        missing.append("odds_missing")
    return {
        "can_run_single_match_analysis": not missing,
        "grade": "schedule_and_odds_ready" if not missing else "not_analysis_ready",
        "guaranteed_inputs": {
            "schedule": bool(home and away and kickoff),
            "match_id": bool(match.get("match_id")),
            "odds_snapshot": bool(odds.get("has_valid_numeric_odds")),
        },
        "deep_context_checked": False,
        "missing": missing,
        "rule": "list_matches returns analysis-ready matches by default; deep context is checked when analyze_single_match is called.",
    }


def parse_float(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).strip())
    except ValueError:
        return None


def public_fixture(row: dict[str, str], *, score: float | None = None, source: dict[str, Any] | None = None) -> dict[str, Any]:
    kickoff = parse_kickoff(row)
    return {
        "division": row.get("Div"),
        "league": LEAGUE_NAMES.get(row.get("Div", ""), row.get("Div", "")),
        "date": row.get("Date"),
        "time": row.get("Time"),
        "home_team": row.get("HomeTeam"),
        "away_team": row.get("AwayTeam"),
        "kickoff_source_timezone": "Europe/London",
        "kickoff_utc": kickoff.astimezone(timezone.utc).isoformat() if kickoff else None,
        "kickoff_utc_plus_8": kickoff.astimezone(DEFAULT_USER_TIMEZONE).isoformat() if kickoff else None,
        "match_score": score,
        "source": source,
    }


def public_dongqiudi_fixture(match: dict[str, Any], *, score: float | None = None, source: dict[str, Any] | None = None) -> dict[str, Any]:
    kickoff = parse_dongqiudi_kickoff(match.get("start_play"))
    competition = match.get("competition") or {}
    home = match.get("team_A") or {}
    away = match.get("team_B") or {}
    return {
        "division": f"dongqiudi:{competition.get('id') or ''}",
        "league": competition.get("name") or "",
        "area": competition.get("area_name") or "",
        "date": kickoff.astimezone(DEFAULT_USER_TIMEZONE).strftime("%Y-%m-%d") if kickoff else "",
        "time": kickoff.astimezone(DEFAULT_USER_TIMEZONE).strftime("%H:%M") if kickoff else "",
        "home_team": home.get("name") or "",
        "away_team": away.get("name") or "",
        "home_team_logo_url": home.get("logo") or "",
        "away_team_logo_url": away.get("logo") or "",
        "home_team_id": home.get("id") or None,
        "away_team_id": away.get("id") or None,
        "home_rank": home.get("league_rank") or "",
        "away_rank": away.get("league_rank") or "",
        "match_id": str(match.get("match_id") or ""),
        "status": match.get("status") or "",
        "status_cn": dongqiudi_status_cn(match.get("status") or ""),
        "kickoff_source_timezone": "UTC",
        "kickoff_utc": kickoff.isoformat() if kickoff else None,
        "kickoff_utc_plus_8": kickoff.astimezone(DEFAULT_USER_TIMEZONE).isoformat() if kickoff else None,
        "match_score": score,
        "source": source,
        "source_name": "dongqiudi",
        "sporttery_str": match.get("sporttery_str") or "",
        "forecast_num": match.get("forecast_num") or "",
        "analysis_readiness": analysis_readiness_for_dongqiudi_match(match),
    }


def _dongqiudi_context_candidate_for_match(
    best: dict[str, Any],
    search: dict[str, Any],
) -> dict[str, Any] | None:
    """Find a same-match Dongqiudi candidate that can provide deep context."""
    if best.get("source_name") == "dongqiudi" and best.get("match_id"):
        return best

    candidates: list[tuple[float, int, dict[str, Any]]] = []
    best_home = str(best.get("home_team") or "")
    best_away = str(best.get("away_team") or "")
    best_league = str(best.get("league") or "")
    best_kickoff = str(best.get("kickoff_utc_plus_8") or best.get("kickoff_utc") or "")
    for index, candidate in enumerate(search.get("candidates") or []):
        if candidate.get("source_name") != "dongqiudi" or not candidate.get("match_id"):
            continue
        score = parse_float(candidate.get("match_score")) or 0.0
        if score < MATCH_SCORE_THRESHOLD:
            continue
        if best_home and best_away:
            pair_score = row_match_score(
                {
                    "HomeTeam": str(candidate.get("home_team") or ""),
                    "AwayTeam": str(candidate.get("away_team") or ""),
                    "Div": str(candidate.get("league") or ""),
                },
                f"{best_home} vs {best_away}",
                best_home,
                best_away,
                best_league,
            )
            score = max(score, pair_score)
        kickoff_bonus = 0.01 if best_kickoff and best_kickoff == str(candidate.get("kickoff_utc_plus_8") or candidate.get("kickoff_utc") or "") else 0.0
        candidates.append((score + kickoff_bonus, -index, candidate))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return candidates[0][2]


def _attach_context_match_identity(best: dict[str, Any], context_match: dict[str, Any] | None) -> dict[str, Any]:
    if not context_match:
        return best
    match_id = str(context_match.get("match_id") or "").strip()
    if not match_id:
        return best
    merged = dict(best)
    if not merged.get("match_id"):
        merged["match_id"] = match_id
    merged["context_source_name"] = context_match.get("source_name") or "dongqiudi"
    merged["context_match_id"] = match_id
    merged["context_match"] = {
        key: context_match.get(key)
        for key in (
            "source_name",
            "match_id",
            "division",
            "league",
            "area",
            "home_team",
            "away_team",
            "kickoff_utc",
            "kickoff_utc_plus_8",
            "status",
            "status_cn",
            "match_score",
            "source",
        )
        if context_match.get(key) not in (None, "", [], {})
    }
    return merged


def dongqiudi_status_cn(status: str) -> str:
    return {
        "Fixture": "未开始",
        "Playing": "进行中",
        "playing": "进行中",
        "Played": "已结束",
    }.get(status, status)


def classify_window(kickoff: datetime | None, as_of: datetime, window_hours: int) -> dict[str, Any]:
    if kickoff is None:
        return {
            "as_of": as_of.isoformat(),
            "window_end": (as_of + timedelta(hours=window_hours)).isoformat(),
            "in_window": False,
            "reason": "kickoff_time_missing",
        }
    kickoff_local = kickoff.astimezone(as_of.tzinfo or DEFAULT_USER_TIMEZONE)
    end = as_of + timedelta(hours=window_hours)
    if kickoff_local < as_of:
        reason = "already_started_or_past"
    elif kickoff_local > end:
        reason = "outside_default_window"
    else:
        reason = "in_default_window"
    return {
        "as_of": as_of.isoformat(),
        "window_end": end.isoformat(),
        "window_hours": window_hours,
        "kickoff": kickoff_local.isoformat(),
        "in_window": reason == "in_default_window",
        "reason": reason,
    }


async def load_dongqiudi_matches_for_date(
    local_date: datetime,
    *,
    tab_type: str = "fixture",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    date_str = local_date.astimezone(DEFAULT_USER_TIMEZONE).strftime("%Y-%m-%d")
    data, source = await fetch_json(
        DONGQIUDI_SCHEDULE_URL,
        params={
            "language": "zh-CN",
            "tab_type": tab_type or "fixture",
            "cmp_type": "soccer",
            "start": f"{date_str} 00:00:00",
        },
    )
    matches = ((data or {}).get("data") or {}).get("matches") or []
    return matches, source


async def load_dongqiudi_window(as_of: datetime, window_hours: int) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    end = as_of + timedelta(hours=window_hours)
    as_of_day = as_of.astimezone(DEFAULT_USER_TIMEZONE).replace(hour=0, minute=0, second=0, microsecond=0)
    cursor = as_of_day - timedelta(days=1)
    end_day = end.astimezone(DEFAULT_USER_TIMEZONE).replace(hour=0, minute=0, second=0, microsecond=0)
    merged: dict[str, dict[str, Any]] = {}
    primary_source = None
    fallback_source = None
    while cursor <= end_day:
        try:
            rows, source = await load_dongqiudi_matches_for_date(cursor)
            fallback_source = fallback_source or source
            if cursor == as_of_day:
                primary_source = source
            for row in rows:
                match_id = str(row.get("match_id") or "")
                if match_id:
                    row_with_source = dict(row)
                    row_with_source["_schedule_source"] = source
                    merged[match_id] = row_with_source
        except Exception:
            pass
        cursor += timedelta(days=1)
    return list(merged.values()), primary_source or fallback_source


async def load_dongqiudi_detail(match_id: str) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    return await fetch_json(
        DONGQIUDI_DETAIL_URL,
        params={"id": match_id, "app": "dqd", "lang": "zh-cn"},
    )


async def load_dongqiudi_pre_analysis(match_id: str) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    return await fetch_json(
        DONGQIUDI_PRE_ANALYSIS_URL_TEMPLATE.format(match_id=match_id),
        params={"platform": "iphone", "version": "718"},
    )


async def load_dongqiudi_odds_index(match_id: str) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    return await fetch_json(DONGQIUDI_ODDS_URL_TEMPLATE.format(match_id=match_id))


async def load_dongqiudi_lineup(match_id: str) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    return await fetch_json(DONGQIUDI_LINEUP_URL_TEMPLATE.format(match_id=match_id))


def _result_from_row(row: dict[str, Any]) -> str:
    color = str(row.get("color") or "").lower()
    if color in {"win", "draw", "lose"}:
        return {"win": "win", "draw": "draw", "lose": "loss"}[color]
    left, right = _parse_score_pair(row)
    if left is None or right is None:
        return ""
    main_team = str(row.get("main_team") or "team_A")
    target, opponent = (left, right) if main_team == "team_A" else (right, left)
    if target > opponent:
        return "win"
    if target == opponent:
        return "draw"
    return "loss"


def summarize_match_block(items: list[dict[str, Any]]) -> dict[str, Any]:
    wins = draws = losses = handicap_wins = large_goals = 0
    goals_for = goals_against = total_goals = 0.0
    scored_samples = 0
    same_competition_goals_for = same_competition_goals_against = same_competition_total_goals = 0.0
    same_competition_scored_samples = 0
    same_competition_samples = 0
    samples = 0
    for row in items[:5]:
        if not isinstance(row, dict):
            continue
        samples += 1
        tags = row.get("tags") or {}
        is_same_competition = parse_float(tags.get("same_competition")) == 1
        if is_same_competition:
            same_competition_samples += 1
        result = _result_from_row(row)
        if result == "win":
            wins += 1
        elif result == "draw":
            draws += 1
        elif result == "loss":
            losses += 1
        if parse_float(tags.get("win_handicap")) == 1:
            handicap_wins += 1
        if parse_float(tags.get("large_goals")) == 1:
            large_goals += 1
        left, right = _parse_score_pair(row)
        if left is None or right is None:
            continue
        main_team = str(row.get("main_team") or "team_A")
        target, opponent = (left, right) if main_team == "team_A" else (right, left)
        goals_for += target
        goals_against += opponent
        total_goals += left + right
        scored_samples += 1
        if is_same_competition:
            same_competition_goals_for += target
            same_competition_goals_against += opponent
            same_competition_total_goals += left + right
            same_competition_scored_samples += 1

    points = wins * 3 + draws
    return {
        "sample_size": samples,
        "same_competition_sample_size": same_competition_samples,
        "record": {"wins": wins, "draws": draws, "losses": losses},
        "points_per_match": round_metric(points / samples if samples else None),
        "goals_for_per_match": round_metric(goals_for / scored_samples if scored_samples else None),
        "goals_against_per_match": round_metric(goals_against / scored_samples if scored_samples else None),
        "goal_diff_per_match": round_metric((goals_for - goals_against) / scored_samples if scored_samples else None),
        "avg_total_goals": round_metric(total_goals / scored_samples if scored_samples else None),
        "same_competition_goals_for_per_match": round_metric(same_competition_goals_for / same_competition_scored_samples if same_competition_scored_samples else None),
        "same_competition_goals_against_per_match": round_metric(same_competition_goals_against / same_competition_scored_samples if same_competition_scored_samples else None),
        "same_competition_avg_total_goals": round_metric(same_competition_total_goals / same_competition_scored_samples if same_competition_scored_samples else None),
        "handicap_win_rate": round_metric(handicap_wins / samples if samples else None),
        "large_goals_rate": round_metric(large_goals / samples if samples else None),
    }


def parse_table_section(section: dict[str, Any] | None) -> dict[str, Any]:
    section = section or {}
    matches = parse_float(section.get("matches_total"))
    points = parse_float(section.get("points"))
    goals_for = parse_float(section.get("goals_pro"))
    goals_against = parse_float(section.get("goals_against"))
    return {
        "rank": parse_float(section.get("rank")),
        "last_rank": parse_float(section.get("last_rank")),
        "points": points,
        "matches_total": matches,
        "points_per_match": round_metric(points / matches if points is not None and matches else None),
        "goals_for": goals_for,
        "goals_against": goals_against,
        "goal_diff": round_metric(goals_for - goals_against if goals_for is not None and goals_against is not None else None),
        "win_rate": section.get("win_rate") or "",
    }


def summarize_league_table(league_table: dict[str, Any]) -> dict[str, Any]:
    home_total = parse_table_section(((league_table or {}).get("team_A") or {}).get("total"))
    away_total = parse_table_section(((league_table or {}).get("team_B") or {}).get("total"))
    home_rank = parse_float(home_total.get("rank"))
    away_rank = parse_float(away_total.get("rank"))
    home_points = parse_float(home_total.get("points"))
    away_points = parse_float(away_total.get("points"))
    return {
        "available": bool(home_total.get("matches_total") or away_total.get("matches_total")),
        "home_total": home_total,
        "home_home": parse_table_section(((league_table or {}).get("team_A") or {}).get("home")),
        "away_total": away_total,
        "away_away": parse_table_section(((league_table or {}).get("team_B") or {}).get("away")),
        "rank_delta_home_minus_away": round_metric(home_rank - away_rank if home_rank is not None and away_rank is not None else None),
        "points_delta_home_minus_away": round_metric(home_points - away_points if home_points is not None and away_points is not None else None),
    }


def summarize_pre_analysis(data: dict[str, Any] | None, source: dict[str, Any] | None = None) -> dict[str, Any]:
    if not data:
        return {"available": False, "reason": "pre_analysis_unavailable"}
    battle_history = data.get("battle_history") or {}
    recent_record = data.get("recent_record") or {}
    league_table = data.get("league_table") or {}
    home_recent = recent_record.get("team_A") or []
    away_recent = recent_record.get("team_B") or []
    if isinstance(home_recent, dict):
        home_recent = home_recent.get("list") or []
    if isinstance(away_recent, dict):
        away_recent = away_recent.get("list") or []
    return {
        "available": True,
        "source": source,
        "teams": {
            "home": data.get("team_A"),
            "away": data.get("team_B"),
            "kickoff_utc": data.get("start_time"),
        },
        "battle_history": {
            "name": battle_history.get("name"),
            "matches": (battle_history.get("list") or [])[:5],
        },
        "recent_record": {
            "name": recent_record.get("name"),
            "home": home_recent[:5] if isinstance(home_recent, list) else [],
            "away": away_recent[:5] if isinstance(away_recent, list) else [],
        },
        "recent_record_summary": {
            "home": summarize_match_block(home_recent if isinstance(home_recent, list) else []),
            "away": summarize_match_block(away_recent if isinstance(away_recent, list) else []),
        },
        "league_table": league_table,
        "league_table_summary": summarize_league_table(league_table),
        "battle_history_summary": summarize_match_block((battle_history.get("list") or []) if isinstance(battle_history, dict) else []),
    }


def summarize_lineup(data: dict[str, Any] | None, source: dict[str, Any] | None = None) -> dict[str, Any]:
    if not data:
        return {"available": False, "reason": "lineup_unavailable"}
    base = data.get("base") or {}
    persons = data.get("persons") or {}
    forecasts = data.get("forecasts") or {}
    home_official = _summarize_team_lineup(persons.get("team_A") or {})
    away_official = _summarize_team_lineup(persons.get("team_B") or {})
    home_forecast = _summarize_team_lineup(forecasts.get("team_A") or {})
    away_forecast = _summarize_team_lineup(forecasts.get("team_B") or {})
    official_home_available = bool(home_official["lineups"])
    official_away_available = bool(away_official["lineups"])
    forecast_home_available = bool(home_forecast["lineups"])
    forecast_away_available = bool(away_forecast["lineups"])
    lineup_status = {
        "official_home_available": official_home_available,
        "official_away_available": official_away_available,
        "forecast_home_available": forecast_home_available,
        "forecast_away_available": forecast_away_available,
        "official_lineups_published": official_home_available and official_away_available,
        "lineup_basis": (
            "official_lineups"
            if official_home_available and official_away_available
            else "forecast_lineups"
            if forecast_home_available and forecast_away_available
            else "unavailable"
        ),
    }
    official_lineups = {
        "home": home_official,
        "away": away_official,
    }
    forecast_lineups = {
        "home": home_forecast,
        "away": away_forecast,
    }
    return {
        "available": True,
        "source": source,
        "base": {
            "weather": base.get("weather") or "",
            "temperature": base.get("temperature") or "",
            "field": base.get("field") or "",
            "referee": base.get("referee") or "",
            "new_lineup": base.get("new_lineup"),
            "forecast_lineup": base.get("forecast_lineup"),
        },
        "lineup_status": lineup_status,
        "lineup_analysis": _build_lineup_analysis(lineup_status, official_lineups, forecast_lineups),
        "official_lineups": official_lineups,
        "forecast_lineups": forecast_lineups,
        "sideline": data.get("sideline") or {},
    }


def _summarize_player(player: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": player.get("person") or "",
        "shirt_number": player.get("shirtnumber") or "",
        "position": player.get("position") or "",
        "nationality": player.get("nationality_name") or "",
        "captain": bool(player.get("captain")),
    }


def _summarize_team_lineup(team: dict[str, Any]) -> dict[str, Any]:
    lineups = team.get("lineups") or []
    substitutes = team.get("sub") or []
    raw_formation = str(team.get("formation") or team.get("formation_pic") or "")
    normalized_formation = _normalize_formation(raw_formation)
    return {
        "team_name": team.get("team_name") or "",
        "coach": team.get("team_coach") or "",
        "formation": normalized_formation,
        "formation_raw": raw_formation,
        "formation_valid": bool(normalized_formation),
        "formation_warning": (
            ""
            if normalized_formation or not raw_formation
            else "raw formation code is not human-readable; do not infer tactics from it"
        ),
        "lineup_count": len(lineups),
        "substitute_count": len(substitutes),
        "lineups": [_summarize_player(player) for player in lineups[:11] if isinstance(player, dict)],
        "substitutes": [_summarize_player(player) for player in substitutes if isinstance(player, dict)],
    }


def _normalize_formation(value: str) -> str:
    cleaned = str(value or "").strip()
    if re.fullmatch(r"\d(?:-\d){2,5}", cleaned):
        return cleaned
    return ""


def _position_counts(players: list[dict[str, Any]]) -> dict[str, int]:
    counter = Counter()
    for player in players:
        position = str(player.get("position") or "").strip()
        if position:
            counter[position] += 1
    return dict(counter)


def _build_lineup_analysis(
    lineup_status: dict[str, Any],
    official_lineups: dict[str, dict[str, Any]],
    forecast_lineups: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    basis = lineup_status.get("lineup_basis")
    source_lineups = (
        official_lineups
        if basis == "official_lineups"
        else forecast_lineups
        if basis == "forecast_lineups"
        else {}
    )
    home = source_lineups.get("home") or {}
    away = source_lineups.get("away") or {}
    warnings = []
    if basis == "unavailable":
        warnings.append("lineup unavailable")
    for side, team in (("home", home), ("away", away)):
        if team and not team.get("formation_valid") and team.get("formation_raw"):
            warnings.append(f"{side} formation is an opaque source code; do not infer tactics from it")
        if team and team.get("lineup_count") not in (0, 11):
            warnings.append(f"{side} starter count is {team.get('lineup_count')}, expected 11")

    def team_analysis(team: dict[str, Any]) -> dict[str, Any]:
        starters = team.get("lineups") or []
        return {
            "team_name": team.get("team_name") or "",
            "coach": team.get("coach") or "",
            "formation": team.get("formation") or "",
            "formation_valid": bool(team.get("formation_valid")),
            "starter_count": team.get("lineup_count") or 0,
            "substitute_count": team.get("substitute_count") or 0,
            "position_counts": _position_counts(starters),
            "starters": starters,
            "quality_notes": [
                team.get("formation_warning"),
            ] if team.get("formation_warning") else [],
        }

    return {
        "available": basis in {"official_lineups", "forecast_lineups"},
        "basis": basis,
        "can_use_for_analysis": basis in {"official_lineups", "forecast_lineups"} and not any(
            warning.endswith("expected 11") for warning in warnings
        ),
        "usage_policy": (
            "Use this normalized lineup_analysis object for lineup facts. "
            "Do not use raw formation codes. Treat lineups as contextual evidence, not a standalone betting signal."
        ),
        "warnings": warnings,
        "home": team_analysis(home),
        "away": team_analysis(away),
    }


_CONTEXT_EMPTY_TEXTS = {
    "-",
    "--",
    "n/a",
    "na",
    "none",
    "null",
    "暂无",
    "暂无信息",
    "无",
    "未知",
}


def _provider_label(provider: str) -> str:
    normalized = str(provider or "").strip().lower()
    if normalized in {"dongqiudi", "dongqiudi.com", "dqd"}:
        return "懂球帝"
    if normalized in {"leisu", "leisu.com", "leisu_sports"}:
        return "雷速体育"
    if normalized in {"multi_source", "composite"}:
        return "多源融合"
    return str(provider or "来源未知")


def _context_text(value: Any) -> str:
    if value in (None, "", [], {}):
        return ""
    if isinstance(value, (str, int, float)):
        return str(value).strip()
    if isinstance(value, dict):
        pieces: list[str] = []
        for key in (
            "name",
            "name_zh",
            "venue",
            "stadium",
            "field",
            "city",
            "country",
            "weather",
            "desc",
            "description",
            "referee",
            "person",
            "text",
            "value",
        ):
            item = value.get(key)
            if isinstance(item, (str, int, float)) and str(item).strip():
                text = str(item).strip()
                if text not in pieces:
                    pieces.append(text)
        return " · ".join(pieces[:3])
    if isinstance(value, list):
        return " · ".join(piece for piece in (_context_text(item) for item in value[:3]) if piece)
    return str(value).strip()


def _context_field_status(value: Any) -> str:
    text = _context_text(value)
    if not text:
        return "not_collected"
    return "source_empty" if text.lower() in _CONTEXT_EMPTY_TEXTS else "available"


def _context_first_path(value: dict[str, Any], paths: tuple[tuple[str, ...], ...]) -> Any:
    for path in paths:
        current: Any = value
        exists = True
        for key in path:
            if not isinstance(current, dict) or key not in current:
                exists = False
                break
            current = current.get(key)
        if exists and current not in (None, "", [], {}):
            return current
    return None


def _context_path_exists(value: dict[str, Any], path: tuple[str, ...]) -> bool:
    current: Any = value
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return False
        current = current.get(key)
    return True


def _context_any_path_exists(value: dict[str, Any], paths: tuple[tuple[str, ...], ...]) -> bool:
    return any(_context_path_exists(value, path) for path in paths)


def _context_value(context: dict[str, Any], key: str) -> Any:
    paths = {
        "venue": (("venue",), ("lineup", "base", "field")),
        "weather": (("weather",), ("weather_report",), ("lineup", "base", "weather")),
        "referee": (("referee",), ("lineup", "base", "referee")),
    }
    return _context_first_path(context, paths.get(key, ((key,),)))


def _context_field_status_for_key(context: dict[str, Any], key: str) -> str:
    paths = {
        "venue": (("venue",), ("lineup", "base", "field")),
        "weather": (("weather",), ("weather_report",), ("lineup", "base", "weather")),
        "referee": (("referee",), ("lineup", "base", "referee")),
    }.get(key, ((key,),))
    status = _context_field_status(_context_value(context, key))
    if status == "not_collected" and _context_any_path_exists(context, paths):
        return "source_empty"
    return status


def _context_lineup_status(context: dict[str, Any]) -> str:
    if "lineup" not in context:
        return "not_collected"
    lineup = context.get("lineup") if isinstance(context.get("lineup"), dict) else {}
    analysis = lineup.get("lineup_analysis") if isinstance(lineup.get("lineup_analysis"), dict) else {}
    source_lineups = lineup.get("official_lineups") or lineup.get("forecast_lineups") or {}
    has_players = any(
        (source_lineups.get(side) or {}).get("lineups")
        for side in ("home", "away")
        if isinstance(source_lineups.get(side), dict)
    )
    if analysis.get("available") or analysis.get("can_use_for_analysis") or has_players:
        return "available"
    return "source_empty"


def _context_access_issue(context: dict[str, Any]) -> dict[str, Any] | None:
    sources = context.get("sources") if isinstance(context.get("sources"), dict) else {}
    for source in sources.values():
        if not isinstance(source, dict):
            continue
        access = source.get("access") if isinstance(source.get("access"), dict) else {}
        if access.get("blocked"):
            return {
                "blocked": True,
                "requires_cookie_or_proxy": bool(access.get("requires_cookie_or_proxy")),
                "reason": str(access.get("reason") or source.get("status") or "访问受限").strip(),
            }
    return None


def _context_access_reason_text(reason: str) -> str:
    lowered = (reason or "").lower()
    if "403" in lowered or "forbidden" in lowered:
        return "403 访问被拒绝"
    if "waf" in lowered or "challenge" in lowered:
        return "风控校验未通过"
    if "cookie" in lowered or "proxy" in lowered:
        return "需要 Cookie 或代理"
    return reason.strip() or "访问受限"


def _context_source_attempt(context: dict[str, Any]) -> dict[str, Any]:
    provider = str(context.get("provider") or context.get("source_name") or "").strip()
    access_issue = _context_access_issue(context)
    field_statuses = {
        "venue": _context_field_status_for_key(context, "venue"),
        "weather": _context_field_status_for_key(context, "weather"),
        "referee": _context_field_status_for_key(context, "referee"),
        "lineup": _context_lineup_status(context),
    }
    status = "matched" if context else "not_collected"
    detail = f"{_provider_label(provider)}已匹配比赛 {context.get('match_id')}" if context.get("match_id") else ""
    if access_issue:
        status = "access_blocked"
        field_statuses = {
            key: ("available" if value == "available" else "access_blocked")
            for key, value in field_statuses.items()
        }
        needs_access = "；需要雷速 Cookie 或代理" if access_issue.get("requires_cookie_or_proxy") else ""
        match_text = f"比赛 {context.get('match_id')}" if context.get("match_id") else "比赛"
        detail = (
            f"{_provider_label(provider)}已匹配{match_text}，"
            f"但详情接口访问受限：{_context_access_reason_text(str(access_issue.get('reason') or ''))}{needs_access}。"
        )
    return {
        "provider": provider,
        "label": _provider_label(provider),
        "status": status,
        "match_id": str(context.get("match_id") or ""),
        "detail": detail,
        "field_statuses": field_statuses,
        **({"access": access_issue} if access_issue else {}),
    }


def _context_available_blocks(context: dict[str, Any]) -> list[str]:
    blocks = []
    for key in ("venue", "weather", "referee"):
        if _context_field_status(_context_value(context, key)) == "available":
            blocks.append(key)
    if _context_lineup_status(context) == "available":
        blocks.append("lineup")
    return blocks


def _leisu_detail_text(detail_payload: dict[str, Any], label: str) -> str:
    for item in detail_payload.get("tlive") or []:
        if not isinstance(item, dict):
            continue
        text = str(item.get("data") or "").strip()
        if not text or label not in text:
            continue
        match = re.search(rf"{re.escape(label)}情况[：:]\s*([^，。；;\n]+)", text)
        if match:
            return match.group(1).strip()
    return ""


def _leisu_weather_text(detail_payload: dict[str, Any]) -> str:
    for key in ("weather", "environment"):
        value = detail_payload.get(key)
        if isinstance(value, dict):
            text = _context_text(value.get("weather") or value.get("desc") or value)
            if text:
                return text
        elif isinstance(value, str) and value.strip():
            return value.strip()
    return _leisu_detail_text(detail_payload, "天气")


def _leisu_venue(lineup_payload: dict[str, Any]) -> dict[str, Any]:
    venue = lineup_payload.get("venue") if isinstance(lineup_payload.get("venue"), dict) else {}
    return {
        key: value
        for key, value in {
            "name": venue.get("name") or venue.get("name_zh") or venue.get("venue_name"),
            "city": venue.get("city"),
            "country": venue.get("country"),
            "capacity": venue.get("capacity"),
        }.items()
        if value not in (None, "", [], {})
    }


def _leisu_referee(lineup_payload: dict[str, Any]) -> dict[str, Any]:
    referee = lineup_payload.get("referee") if isinstance(lineup_payload.get("referee"), dict) else {}
    name = referee.get("name") or referee.get("name_zh") or referee.get("name_en")
    return {"name": name, "id": referee.get("id")} if name else {}


def _leisu_player_for_lineup(player: dict[str, Any]) -> dict[str, Any]:
    nested = player.get("player") if isinstance(player.get("player"), dict) else {}
    return {
        "person": player.get("person") or player.get("name") or player.get("player_name") or nested.get("name") or "",
        "shirtnumber": player.get("shirtnumber") or player.get("shirt_number") or player.get("number") or nested.get("shirt_number") or "",
        "position": player.get("position_name") or player.get("position") or player.get("role") or "",
        "nationality_name": player.get("nationality_name") or nested.get("nationality_name") or "",
        "captain": bool(player.get("captain") or player.get("is_captain")),
    }


def _leisu_lineup_side(lineup_payload: dict[str, Any], side: str) -> dict[str, Any]:
    players = [
        _leisu_player_for_lineup(player)
        for player in (lineup_payload.get(side) or [])
        if isinstance(player, dict)
    ]
    substitutes = [
        _leisu_player_for_lineup(player)
        for player in (
            lineup_payload.get(f"{side}_sub")
            or lineup_payload.get(f"{side}_substitute")
            or lineup_payload.get(f"{side}_bench")
            or []
        )
        if isinstance(player, dict)
    ]
    return {
        "team_name": "",
        "team_coach": _context_text(lineup_payload.get(f"{side}_manager") or {}),
        "formation": lineup_payload.get(f"{side}_formation") or "",
        "lineups": [player for player in players if player.get("person") or player.get("shirtnumber")],
        "sub": [player for player in substitutes if player.get("person") or player.get("shirtnumber")],
    }


def normalize_leisu_match_context(
    match_id: str,
    *,
    lineup_payload: dict[str, Any] | None = None,
    detail_payload: dict[str, Any] | None = None,
    lineup_source: dict[str, Any] | None = None,
    detail_source: dict[str, Any] | None = None,
) -> dict[str, Any]:
    lineup_payload = lineup_payload or {}
    detail_payload = detail_payload or {}
    venue = _leisu_venue(lineup_payload)
    referee = _leisu_referee(lineup_payload)
    weather = _leisu_weather_text(detail_payload)
    lineup_summary = summarize_lineup(
        {
            "base": {
                "field": venue.get("name") or "",
                "weather": weather,
                "referee": referee.get("name") or "",
                "field_condition": _leisu_detail_text(detail_payload, "场地"),
            },
            "persons": {
                "team_A": _leisu_lineup_side(lineup_payload, "home"),
                "team_B": _leisu_lineup_side(lineup_payload, "away"),
            },
        },
        lineup_source or detail_source,
    )
    result = {
        "source_name": "leisu",
        "provider": "leisu",
        "match_id": str(match_id or ""),
        "venue": venue,
        "weather": weather,
        "referee": referee,
        "lineup": {**lineup_summary, "source_name": "leisu"},
        "readiness": {
            "detail_available": bool(detail_payload),
            "lineup_available": _context_lineup_status({"lineup": lineup_summary}) == "available",
            "context_available": any(
                _context_field_status(value) == "available"
                for value in (venue, weather, referee)
            ),
        },
        "sources": {
            "detail": detail_source or {},
            "lineup": lineup_source or {},
        },
    }
    result["available_blocks"] = _context_available_blocks(result)
    result["source_attempts"] = [_context_source_attempt(result)]
    return result


def _leisu_mobile_result_source(result: dict[str, Any]) -> dict[str, Any]:
    source = dict(result.get("source") or {}) if isinstance(result.get("source"), dict) else {}
    if isinstance(result.get("access"), dict):
        source["access"] = result.get("access")
    if result.get("status"):
        source["status"] = result.get("status")
    return source


async def leisu_match_context(match_id: str) -> dict[str, Any]:
    referer = f"{LEISU_MOBILE_WEBSITE_URL}/live/detail-{match_id}"
    async with httpx.AsyncClient(
        timeout=HTTP_TIMEOUT_SECONDS,
        follow_redirects=True,
    ) as client:
        lineup_result, detail_result = await asyncio.gather(
            fetch_leisu_mobile_api(
                "/v1/web/match/football/match_lineup",
                {"match_id": str(match_id)},
                referer=referer,
                client=client,
            ),
            fetch_leisu_mobile_api(
                "/v1/web/match/football/match_detail",
                {"match_id": str(match_id)},
                referer=referer,
                client=client,
            ),
        )
    return normalize_leisu_match_context(
        str(match_id),
        lineup_payload=lineup_result.get("data") if isinstance(lineup_result.get("data"), dict) else {},
        detail_payload=detail_result.get("data") if isinstance(detail_result.get("data"), dict) else {},
        lineup_source=_leisu_mobile_result_source(lineup_result),
        detail_source=_leisu_mobile_result_source(detail_result),
    )


def merge_match_contexts(primary: dict[str, Any] | None, supplemental: dict[str, Any] | None) -> dict[str, Any]:
    if not primary:
        return supplemental or {}
    if not supplemental:
        return primary
    merged = dict(primary)
    used_supplemental = False
    for key in ("venue", "weather", "referee"):
        primary_value = _context_value(primary, key)
        supplemental_value = _context_value(supplemental, key)
        if (
            _context_field_status(primary_value) != "available"
            and _context_field_status(supplemental_value) == "available"
        ):
            merged[key] = supplemental_value
            used_supplemental = True
    if _context_lineup_status(primary) != "available" and _context_lineup_status(supplemental) == "available":
        merged["lineup"] = supplemental.get("lineup") or {}
        used_supplemental = True
    if used_supplemental:
        merged["source_name"] = "multi_source"
        merged["provider"] = "multi_source"
        merged["source_ids"] = {
            str(primary.get("provider") or primary.get("source_name") or "primary"): primary.get("match_id"),
            str(supplemental.get("provider") or supplemental.get("source_name") or "supplemental"): supplemental.get("match_id"),
        }
    merged["available_blocks"] = _context_available_blocks(merged)
    merged["source_attempts"] = [
        _context_source_attempt(primary),
        _context_source_attempt(supplemental),
    ]
    return merged


def _leisu_context_enrichment_enabled() -> bool:
    return os.getenv("FOOTBALL_DATA_LEISU_CONTEXT_ENABLED", "").strip().lower() in {"1", "true", "yes", "on"}


def _match_context_needs_supplemental(context: dict[str, Any] | None) -> bool:
    if not context:
        return True
    return any(
        _context_field_status(_context_value(context, key)) != "available"
        for key in ("venue", "weather", "referee")
    ) or _context_lineup_status(context) != "available"


async def _enrich_match_context_with_leisu(
    match_context: dict[str, Any] | None,
    best: dict[str, Any],
    *,
    query: str,
    home_team: str | None = None,
    away_team: str | None = None,
    league: str | None = None,
    as_of: str | None = None,
    timezone_name: str | None = None,
) -> dict[str, Any] | None:
    if not _leisu_context_enrichment_enabled() or not _leisu_mobile_api_enabled():
        return match_context
    if not _match_context_needs_supplemental(match_context):
        return match_context

    target_home = str(best.get("home_team") or home_team or "").strip()
    target_away = str(best.get("away_team") or away_team or "").strip()
    target_league = league or str(best.get("league") or "").strip() or None
    target_query = f"{target_home} vs {target_away}".strip() if target_home or target_away else query
    if not target_query:
        return match_context

    try:
        candidate = await leisu_odds_candidate_for_match(
            query=target_query,
            home_team=target_home,
            away_team=target_away,
            league=target_league,
            as_of=parse_as_of(as_of, timezone_name),
        )
        leisu_match = candidate.get("match") if isinstance(candidate.get("match"), dict) else {}
        leisu_match_id = str(leisu_match.get("match_id") or "").strip()
        if not candidate.get("available") or not leisu_match_id:
            return match_context
        supplemental = await leisu_match_context(leisu_match_id)
    except Exception:
        return match_context
    return merge_match_contexts(match_context, supplemental)


def _run_async_blocking(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result: dict[str, Any] = {}

    def runner() -> None:
        try:
            result["value"] = asyncio.run(coro)
        except Exception as exc:  # pragma: no cover - re-raised below
            result["error"] = exc

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    thread.join()
    if "error" in result:
        raise result["error"]
    return result.get("value")


def _dashboard_leisu_event_id_from_snapshot(odds_snapshot: dict[str, Any] | None) -> str:
    if not isinstance(odds_snapshot, dict):
        return ""
    resolution = odds_snapshot.get("resolution") if isinstance(odds_snapshot.get("resolution"), dict) else {}
    provider = str(resolution.get("provider") or "").strip().lower()
    event_id = str(resolution.get("event_id") or "").strip()
    return event_id if provider == "leisu" and event_id else ""


def _dashboard_persisted_raw_match_context(record: dict[str, Any]) -> dict[str, Any] | None:
    raw = record.get("raw") if isinstance(record.get("raw"), dict) else {}
    return raw.get("match_context") if isinstance(raw.get("match_context"), dict) else None


def _dashboard_context_with_leisu_snapshot_enrichment(
    record: dict[str, Any],
    *,
    odds_snapshot: dict[str, Any] | None,
) -> dict[str, Any]:
    base_context = _dashboard_match_context(record, odds_snapshot=odds_snapshot)
    if not _leisu_context_enrichment_enabled() or not _leisu_mobile_api_enabled():
        return base_context
    event_id = _dashboard_leisu_event_id_from_snapshot(odds_snapshot)
    if not event_id:
        return base_context

    raw_match_context = _dashboard_persisted_raw_match_context(record)
    if raw_match_context and not _match_context_needs_supplemental(raw_match_context):
        return base_context

    try:
        supplemental = _run_async_blocking(leisu_match_context(event_id))
    except Exception:
        return base_context
    if not isinstance(supplemental, dict) or not supplemental:
        return base_context

    merged_context = merge_match_contexts(raw_match_context, supplemental)
    if not merged_context:
        return base_context
    raw = record.get("raw") if isinstance(record.get("raw"), dict) else {}
    enriched_raw = {**raw, "match_context": merged_context}
    if merged_context.get("source_name") or merged_context.get("provider"):
        enriched_raw["context_source_name"] = merged_context.get("source_name") or merged_context.get("provider")
    if merged_context.get("match_id"):
        enriched_raw["context_match_id"] = merged_context.get("match_id")
    enriched_record = {**record, "raw": enriched_raw}
    return _dashboard_match_context(enriched_record, odds_snapshot=odds_snapshot)


async def dongqiudi_match_context(match_id: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "source_name": "dongqiudi",
        "provider": "dongqiudi",
        "match_id": match_id,
    }

    async def safe_load(label: str, loader):
        try:
            return await loader(match_id)
        except Exception as exc:
            return None, {"error": f"{label}: {type(exc).__name__}: {exc}"}

    detail, detail_source = await safe_load("detail", load_dongqiudi_detail)
    pre_analysis, pre_source = await safe_load("pre_analysis", load_dongqiudi_pre_analysis)
    odds_index, odds_source = await safe_load("odds_index", load_dongqiudi_odds_index)
    lineup, lineup_source = await safe_load("lineup", load_dongqiudi_lineup)

    result["detail"] = {
        "available": bool(detail),
        "source": detail_source,
        "tabs": (detail or {}).get("tabs") or {},
        "match_sample": (detail or {}).get("matchSample") or {},
    }
    result["pre_analysis"] = {
        **summarize_pre_analysis(pre_analysis, pre_source),
        "source_name": "dongqiudi",
    }
    result["lineup"] = {
        **summarize_lineup(lineup, lineup_source),
        "source_name": "dongqiudi",
    }
    odds_index_odds = with_odds_quality_contract(odds_from_dongqiudi_odds_index(odds_index), odds_source)
    result["odds_index"] = {
        "available": bool(odds_index),
        "source": odds_source,
        "odds": odds_index_odds,
    }
    result["readiness"] = {
        "detail_available": bool(detail),
        "pre_analysis_available": bool(pre_analysis),
        "odds_index_available": bool(odds_index and odds_index_odds.get("has_valid_numeric_odds")),
        "odds_quality": odds_index_odds.get("quality_contract") or {},
        "lineup_available": bool(lineup),
    }
    return result


async def list_matches(
    *,
    query: str = "",
    league: str | None = None,
    as_of: str | None = None,
    timezone_name: str | None = None,
    window_hours: int = 24,
    limit: int = 50,
    analysis_ready_only: bool = True,
) -> dict[str, Any]:
    as_of_dt = parse_as_of(as_of, timezone_name)
    rows, source = await load_dongqiudi_window(as_of_dt, window_hours)
    leisu_status = await leisu_schedule_status(as_of_dt)
    translated_query, parsed_home, parsed_away = parse_match_query(query)
    matches = []
    for row in rows:
        home = ((row.get("team_A") or {}).get("name") or "")
        away = ((row.get("team_B") or {}).get("name") or "")
        competition = row.get("competition") or {}
        kickoff = parse_dongqiudi_kickoff(row.get("start_play"))
        window = classify_window(kickoff, as_of_dt, window_hours)
        if not window["in_window"]:
            continue
        score = row_match_score(
            {"HomeTeam": home, "AwayTeam": away, "Div": str(competition.get("name") or "")},
            translated_query,
            parsed_home,
            parsed_away,
            league,
        ) if query or league else 1.0
        if query and score < 0.34:
            continue
        if league and similarity(league, str(competition.get("name") or "")) < 0.45:
            continue
        item = public_dongqiudi_fixture(row, score=score, source=row.get("_schedule_source") or source)
        item["time_window"] = window
        item["odds_summary"] = odds_from_dongqiudi_match(row)
        if analysis_ready_only and not item["analysis_readiness"]["can_run_single_match_analysis"]:
            continue
        matches.append(item)

    matches.sort(key=lambda item: (item.get("kickoff_utc_plus_8") or "", item.get("league") or ""))
    returned = matches[: max(1, limit)]
    return {
        "status": "ok",
        "source": source,
        "query": query,
        "translated_query": translated_query,
        "league": league or "",
        "time_window_policy": time_window_policy(as_of_dt, window_hours, as_of_supplied=bool(as_of)),
        "total_count": len(matches),
        "returned_count": len(returned),
        "matches": returned,
        "supplemental_sources": {
            "leisu_schedule": leisu_status,
        },
        "analysis_ready_only": analysis_ready_only,
        "analysis_policy": "This endpoint lists candidate fixtures only. Betting analysis must be requested and run one match at a time.",
    }


async def sync_market_snapshots(
    *,
    sport_keys: list[str] | None = None,
    regions: str | None = None,
    markets: list[str] | None = None,
    limit_per_sport: int | None = None,
) -> dict[str, Any]:
    """Refresh paid-source market snapshots into the local store."""

    started = time.time()
    odds_result = await external_sources.fetch_the_odds_api_snapshots(
        sport_keys=sport_keys,
        regions=regions,
        markets=markets,
        limit_per_sport=limit_per_sport,
    )
    snapshots = odds_result.get("snapshots") or []
    saved_count = snapshot_store.save_market_snapshots(snapshots)
    the_odds_status = {
        key: value
        for key, value in odds_result.items()
        if key != "snapshots"
    }
    overall_status = "ok"
    if the_odds_status.get("status") in {"not_configured", "empty"}:
        overall_status = "partial"
    if the_odds_status.get("errors") and not saved_count:
        overall_status = "error"

    snapshot_counts = snapshot_store.provider_snapshot_counts()
    return {
        "tool": "sync_market_snapshots",
        "status": overall_status,
        "saved_snapshot_count": saved_count,
        "snapshot_store": {
            "db_path": snapshot_store.snapshot_db_path(),
            "provider_counts": snapshot_counts,
        },
        "providers": {
            "the_odds_api": the_odds_status,
            "coverage": external_sources.external_provider_health(snapshot_counts),
        },
        "latency_ms": round((time.time() - started) * 1000),
        "policy": {
            "refresh_cadence": "Recommended every 5-15 minutes when API keys are configured.",
            "read_path": "Analysis tools should read local snapshots first, then fall back to public sources.",
            "degrade_rule": "Missing paid-source keys must not block existing Dongqiudi/Leisu/Football-Data workflows.",
        },
    }


def _prediction_record_match_terms(record: dict[str, Any]) -> dict[str, Any]:
    raw = record.get("raw") if isinstance(record.get("raw"), dict) else {}
    raw_match = raw.get("match") if isinstance(raw.get("match"), dict) else {}
    home = str(record.get("home_team") or raw_match.get("home_team") or "").strip()
    away = str(record.get("away_team") or raw_match.get("away_team") or "").strip()
    league = str(record.get("league") or raw_match.get("league") or "").strip()
    kickoff = str(
        record.get("kickoff_utc_plus_8")
        or record.get("kickoff_utc")
        or raw_match.get("kickoff_utc_plus_8")
        or raw_match.get("kickoff_utc")
        or ""
    ).strip()
    return {
        "record_id": record.get("id"),
        "home_team": home,
        "away_team": away,
        "league": league,
        "kickoff": kickoff,
    }


def _prediction_target_in_window(target: dict[str, Any], as_of_dt: datetime, window_end: datetime) -> bool:
    raw = str(target.get("kickoff") or "").strip()
    if not raw:
        return True
    try:
        parsed = date_parser.parse(raw)
    except (TypeError, ValueError):
        return True
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=DEFAULT_USER_TIMEZONE)
    local = parsed.astimezone(as_of_dt.tzinfo or DEFAULT_USER_TIMEZONE)
    grace = timedelta(hours=6)
    return (as_of_dt - grace) <= local <= (window_end + grace)


def _leisu_prediction_match_score(match: dict[str, Any], target: dict[str, Any]) -> tuple[float, str]:
    home = str(target.get("home_team") or "")
    away = str(target.get("away_team") or "")
    league = str(target.get("league") or "")
    match_home = str(match.get("home_team") or "")
    match_away = str(match.get("away_team") or "")
    match_league = str(match.get("league") or "")
    base = row_match_score(
        {"HomeTeam": match_home, "AwayTeam": match_away, "Div": match_league},
        f"{home} vs {away}",
        home,
        away,
        league,
    )
    home_score = similarity(home, match_home) if home and match_home else 0.0
    away_score = similarity(away, match_away) if away and match_away else 0.0
    league_score = similarity(league, match_league) if league and match_league else 0.0
    if home_score >= 0.92 and away_score >= 0.92:
        return max(base, 0.98), "team_pair"
    if league_score >= 0.9 and home_score >= 0.92:
        return max(base, 0.74), "same_league_home_alias"
    if league_score >= 0.9 and away_score >= 0.92:
        return max(base, 0.74), "same_league_away_alias"
    return base, "fuzzy_pair"


def _leisu_prediction_snapshot_targets(
    matches: list[dict[str, Any]],
    *,
    as_of_dt: datetime,
    window_end: datetime,
    limit: int,
) -> list[dict[str, Any]]:
    if not matches:
        return []
    records: list[dict[str, Any]] = []
    record_limit = max(50, int(limit or 20) * 10)
    try:
        records.extend(learning_store.list_recommendation_records(status="open", limit=record_limit))
    except Exception:
        records.extend([])
    try:
        records.extend(learning_store.list_shadow_prediction_records(status="open", limit=record_limit))
    except Exception:
        records.extend([])

    targets: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for record in records:
        target = _prediction_record_match_terms(record)
        home = str(target.get("home_team") or "")
        away = str(target.get("away_team") or "")
        if not home or not away or not _prediction_target_in_window(target, as_of_dt, window_end):
            continue
        scored: list[tuple[float, str, dict[str, Any]]] = []
        for match in matches:
            score, reason = _leisu_prediction_match_score(match, target)
            if score >= MATCH_SCORE_THRESHOLD:
                scored.append((score, reason, match))
        if not scored:
            continue
        scored.sort(key=lambda item: item[0], reverse=True)
        score, reason, match = scored[0]
        match_id = str(match.get("match_id") or "")
        if not match_id or match_id in seen_ids:
            continue
        seen_ids.add(match_id)
        targets.append(
            {
                **match,
                "league": target.get("league") or match.get("league") or "",
                "home_team": home,
                "away_team": away,
                "prediction_record_id": target.get("record_id"),
                "leisu_home_team": match.get("home_team") or "",
                "leisu_away_team": match.get("away_team") or "",
                "leisu_league": match.get("league") or "",
                "match_resolution_score": round_metric(score),
                "match_resolution_reason": reason,
            }
        )
    return targets


async def sync_leisu_odds_snapshots(
    *,
    as_of: str | None = None,
    timezone_name: str | None = None,
    window_minutes: int = 24 * 60,
    limit: int = 20,
    concurrency: int = 4,
    require_quality_gate: bool = True,
) -> dict[str, Any]:
    """Probe accessible Leisu odds pages and persist multi-company time-series snapshots."""

    started = time.time()
    as_of_dt = parse_as_of(as_of, timezone_name)
    bounded_window = max(1, min(int(window_minutes or 24 * 60), 48 * 60))
    bounded_limit = max(1, min(int(limit or 20), 100))
    bounded_concurrency = max(1, min(int(concurrency or 4), 10))
    window_end = as_of_dt + timedelta(minutes=bounded_window)
    local_dates = []
    cursor_date = as_of_dt.date()
    while cursor_date <= window_end.date():
        local_dates.append(datetime.combine(cursor_date, datetime.min.time(), tzinfo=as_of_dt.tzinfo))
        cursor_date += timedelta(days=1)

    schedule_errors = []
    schedule_sources = []
    matches: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for local_date in local_dates:
        try:
            rows, source = await load_leisu_schedule_for_date(local_date)
            schedule_sources.append(source)
        except Exception as exc:
            schedule_errors.append(
                {
                    "date": local_date.date().isoformat(),
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            continue
        for row in rows:
            match_id = str(row.get("match_id") or "").strip()
            if not match_id or match_id in seen_ids:
                continue
            seen_ids.add(match_id)
            matches.append(row)

    prioritized_targets = _leisu_prediction_snapshot_targets(
        matches,
        as_of_dt=as_of_dt,
        window_end=window_end,
        limit=bounded_limit,
    )
    ordered_candidates: list[dict[str, Any]] = []
    ordered_seen_ids: set[str] = set()
    for match in [*prioritized_targets, *matches]:
        match_id = str(match.get("match_id") or "").strip()
        if not match_id or match_id in ordered_seen_ids:
            continue
        ordered_seen_ids.add(match_id)
        ordered_candidates.append(match)
    candidates = ordered_candidates[:bounded_limit]
    semaphore = asyncio.Semaphore(bounded_concurrency)

    async def probe_one(match: dict[str, Any]) -> dict[str, Any]:
        async with semaphore:
            probed = await probe_leisu_odds(
                match_id=str(match.get("match_id") or ""),
                odds_url=str(match.get("odds_url") or ""),
            )
        quality_gate = probed.get("quality_gate") or {}
        can_promote = bool(quality_gate.get("can_promote_to_model_input"))
        should_persist = bool(probed.get("available")) and (can_promote or not require_quality_gate)
        fetched_at = (((probed.get("fetch") or {}).get("source") or {}).get("fetched_at_utc") or now_utc().isoformat())
        snapshots = (
            leisu_market_snapshots_from_odds(
                probed.get("odds") or {},
                match=match,
                fetched_at_utc=str(fetched_at),
            )
            if should_persist
            else []
        )
        return {
            "match_id": str(match.get("match_id") or ""),
            "league": match.get("league") or "",
            "matchup": f"{match.get('home_team') or ''} vs {match.get('away_team') or ''}",
            "status": probed.get("status") or "unknown",
            "available": bool(probed.get("available")),
            "can_promote_to_model_input": can_promote,
            "snapshot_count": len(snapshots),
            "snapshots": snapshots,
            "hard_flags": list(quality_gate.get("hard_flags") or []),
            "soft_flags": list(quality_gate.get("soft_flags") or []),
        }

    probe_results = await asyncio.gather(*(probe_one(match) for match in candidates))
    snapshots_to_save = [
        snapshot
        for result in probe_results
        for snapshot in result.get("snapshots", [])
    ]
    saved_count = snapshot_store.save_market_snapshots(snapshots_to_save)
    public_results = [
        {key: value for key, value in result.items() if key != "snapshots"}
        for result in probe_results
    ]
    provider_counts = snapshot_store.provider_snapshot_counts()
    summary = snapshot_store.market_snapshot_summary()
    probed_count = len(public_results)
    accessible_count = sum(1 for item in public_results if item.get("available"))
    promotable_count = sum(1 for item in public_results if item.get("can_promote_to_model_input"))
    status = "ok" if saved_count > 0 else "partial"
    if not candidates and schedule_errors:
        status = "error"
    return {
        "tool": "sync_leisu_odds_snapshots",
        "status": status,
        "saved_snapshot_count": saved_count,
        "generated_snapshot_count": len(snapshots_to_save),
        "snapshot_store": {
            "db_path": snapshot_store.snapshot_db_path(),
            "provider_counts": provider_counts,
            "summary": summary,
        },
        "providers": {
            "leisu": {
                "status": status,
                "candidate_match_count": len(matches),
                "prediction_target_match_count": len(prioritized_targets),
                "probed_match_count": probed_count,
                "accessible_match_count": accessible_count,
                "promotable_match_count": promotable_count,
                "require_quality_gate": require_quality_gate,
            }
        },
        "matches": public_results,
        "schedule_sources": schedule_sources,
        "schedule_errors": schedule_errors,
        "time_window_policy": time_window_policy(as_of_dt, bounded_window / 60, as_of_supplied=bool(as_of)),
        "latency_ms": round((time.time() - started) * 1000),
        "policy": {
            "storage_rule": "Leisu odds are persisted only after numeric odds are parsed and quality gates pass unless require_quality_gate=false.",
            "dedupe_rule": "Rows are keyed by provider/event/bookmaker/market/selection/line/source time/price so repeated syncs do not over-count unchanged prices.",
            "next_use": "Dashboard and future CLV/backtest layers should read market_snapshot_summary and market_snapshots instead of scraping ad hoc page state.",
        },
    }


async def get_match_data_bundle(
    query: str,
    *,
    home_team: str | None = None,
    away_team: str | None = None,
    league: str | None = None,
    as_of: str | None = None,
    timezone_name: str | None = None,
    window_hours: int = 24,
    include_match_resolution: bool = False,
    include_context_refresh: bool = True,
) -> dict[str, Any]:
    """Return source coverage, snapshot freshness, and consensus for one match."""

    translated_query, parsed_home, parsed_away = parse_match_query(query, home_team, away_team)
    resolved_match = None
    search = None
    if include_match_resolution:
        resolved_match, search = await get_best_match(
            translated_query,
            home_team=parsed_home,
            away_team=parsed_away,
            league=league,
            as_of=as_of,
            timezone_name=timezone_name,
            window_hours=window_hours,
        )
        if resolved_match:
            parsed_home = str(resolved_match.get("home_team") or parsed_home)
            parsed_away = str(resolved_match.get("away_team") or parsed_away)

    rows = snapshot_store.find_market_snapshots(parsed_home, parsed_away, league=league, limit=20000)
    consensus = snapshot_store.build_market_consensus(rows)
    movement = snapshot_store.build_market_movement_summary(rows, home_team=parsed_home, away_team=parsed_away)
    snapshot_counts = snapshot_store.provider_snapshot_counts()
    provider_health = external_sources.external_provider_health(snapshot_counts)
    odds_status = "snapshot_available" if rows else provider_health["the_odds_api"]["status"]
    context_start = parse_as_of(as_of, timezone_name)
    if resolved_match and resolved_match.get("kickoff_utc"):
        try:
            context_start = date_parser.parse(str(resolved_match.get("kickoff_utc"))).astimezone(timezone.utc)
        except Exception:
            context_start = parse_as_of(as_of, timezone_name)
    context_end = context_start + timedelta(hours=max(1, int(window_hours or 24)))
    context_date = context_start.date().isoformat()
    context_date_to = context_end.date().isoformat()
    sportmonks_context = (
        await external_sources.fetch_sportmonks_fixture_context(f"{parsed_home} vs {parsed_away}")
        if include_context_refresh
        else {
            "status": "skipped",
            "provider": "sportmonks",
            "reason": "include_context_refresh_false",
            "context": external_sources.normalize_sportmonks_fixture_context({}),
        }
    )
    api_football_context = (
        await external_sources.fetch_api_football_fixture_context(
            f"{parsed_home} vs {parsed_away}",
            home_team=parsed_home,
            away_team=parsed_away,
            date=context_date,
        )
        if include_context_refresh
        else {
            "status": "skipped",
            "provider": "api_football",
            "reason": "include_context_refresh_false",
            "context": external_sources.normalize_api_football_fixture_context({}),
        }
    )
    football_data_org_context = (
        await external_sources.fetch_football_data_org_match_context(
            f"{parsed_home} vs {parsed_away}",
            home_team=parsed_home,
            away_team=parsed_away,
            date_from=context_date,
            date_to=context_date_to,
        )
        if include_context_refresh
        else {
            "status": "skipped",
            "provider": "football_data_org",
            "reason": "include_context_refresh_false",
            "context": external_sources.normalize_football_data_org_match_context({}),
        }
    )
    leisu_odds_context = (
        await leisu_odds_context_for_match(
            query=f"{parsed_home} vs {parsed_away}",
            home_team=parsed_home,
            away_team=parsed_away,
            league=league,
            as_of=context_start.astimezone(DEFAULT_USER_TIMEZONE),
        )
        if include_context_refresh
        else {
            "status": "skipped",
            "provider": "leisu",
            "reason": "include_context_refresh_false",
        }
    )
    free_team_strength = (
        await external_sources.free_team_strength_context(parsed_home, parsed_away)
        if include_context_refresh
        else {
            "status": "skipped",
            "provider": "clubelo",
            "reason": "include_context_refresh_false",
        }
    )
    return {
        "tool": "get_match_data_bundle",
        "status": "ok" if parsed_home and parsed_away else "missing_match_terms",
        "query": query,
        "translated_query": translated_query,
        "home_team": parsed_home,
        "away_team": parsed_away,
        "league": league,
        "resolved_match": resolved_match,
        "search": search,
        "snapshot_store": {
            "db_path": snapshot_store.snapshot_db_path(),
            "matching_snapshot_count": len(rows),
            "provider_counts": snapshot_counts,
        },
        "source_coverage": {
            "odds": {
                "the_odds_api": {
                    **provider_health["the_odds_api"],
                    "status": odds_status,
                    "matching_snapshot_count": len(rows),
                }
            },
            "context": {
                "sportmonks": provider_health["sportmonks"],
                "api_football": provider_health["api_football"],
                "football_data_org": provider_health["football_data_org"],
                "clubelo": provider_health["clubelo"],
                "dongqiudi": {
                    "status": "active_public_source",
                    "role": "Chinese fixture/team-name/odds-index supplement",
                },
                "leisu": {
                    "status": "active_public_source",
                    "role": "Chinese schedule/team-name/link corroboration",
                },
                "leisu_odds": {
                    "status": leisu_odds_context.get("status"),
                    "role": "optional multi-company odds probe with WAF/cookie/proxy quality gate",
                    "auto_probe_enabled": leisu_odds_context.get("auto_probe_enabled"),
                },
            },
        },
        "market_consensus": consensus,
        "market_movement": movement,
        "external_context": {
            "sportmonks": sportmonks_context,
            "api_football": api_football_context,
            "football_data_org": football_data_org_context,
            "leisu_odds": leisu_odds_context,
            "free_team_strength": free_team_strength,
        },
        "snapshots": rows[:50],
        "agent_contract": {
            "must_use_mcp_values": True,
            "do_not_invent_missing_fields": True,
            "no_snapshot_rule": "If matching_snapshot_count is 0, say the paid-source snapshot layer has no local data yet and fall back to existing single-match MCP fields.",
            "consensus_rule": "Use market_consensus for multi-bookmaker price spread; do not calculate odds from raw rows unless a required field is absent from consensus.",
            "movement_rule": "Use market_movement as opening-to-latest market evidence when status is available; otherwise say the analysis is current-price only.",
        },
    }


async def find_candidates(
    query: str,
    *,
    home_team: str | None = None,
    away_team: str | None = None,
    league: str | None = None,
    as_of: str | None = None,
    timezone_name: str | None = None,
    window_hours: int = 24,
    limit: int = 8,
) -> dict[str, Any]:
    as_of_dt = parse_as_of(as_of, timezone_name)
    translated_query, parsed_home, parsed_away = parse_match_query(query, home_team, away_team)
    fixtures, source = await load_fixtures()

    scored = []
    for row in fixtures:
        score = row_match_score(row, translated_query, parsed_home, parsed_away, league)
        if score < MATCH_SCORE_THRESHOLD:
            continue
        kickoff = parse_kickoff(row)
        window = classify_window(kickoff, as_of_dt, window_hours)
        scored.append(("football_data", score, window["in_window"], kickoff or datetime.min.replace(tzinfo=timezone.utc), row, window, source))

    dongqiudi_rows, dongqiudi_source = await load_dongqiudi_window(as_of_dt, window_hours)
    for row in dongqiudi_rows:
        home = ((row.get("team_A") or {}).get("name") or "")
        away = ((row.get("team_B") or {}).get("name") or "")
        competition = row.get("competition") or {}
        score = row_match_score(
            {"HomeTeam": home, "AwayTeam": away, "Div": str(competition.get("name") or "")},
            translated_query,
            parsed_home,
            parsed_away,
            league,
        )
        if score < MATCH_SCORE_THRESHOLD:
            continue
        kickoff = parse_dongqiudi_kickoff(row.get("start_play"))
        window = classify_window(kickoff, as_of_dt, window_hours)
        scored.append(("dongqiudi", score, window["in_window"], kickoff or datetime.min.replace(tzinfo=timezone.utc), row, window, row.get("_schedule_source") or dongqiudi_source))

    sporttery_source: dict[str, Any] | None = None
    try:
        sporttery_matches, sporttery_source = await load_sporttery_official_matches(
            as_of_dt,
            max(1, int(float(window_hours or 24) * 60)),
        )
    except Exception as exc:
        sporttery_matches = []
        sporttery_source = {"source": "sporttery.cn", "error": f"{type(exc).__name__}: {exc}"}
    for row in sporttery_matches:
        score = row_match_score(
            {
                "HomeTeam": str(row.get("home_team") or ""),
                "AwayTeam": str(row.get("away_team") or ""),
                "Div": str(row.get("league") or ""),
            },
            translated_query,
            parsed_home,
            parsed_away,
            league,
        )
        if score < MATCH_SCORE_THRESHOLD:
            continue
        kickoff = date_parser.parse(str(row.get("kickoff_utc"))) if row.get("kickoff_utc") else None
        if kickoff and kickoff.tzinfo is None:
            kickoff = kickoff.replace(tzinfo=timezone.utc)
        window = classify_window(kickoff, as_of_dt, window_hours)
        scored.append(("sporttery", score, window["in_window"], kickoff or datetime.min.replace(tzinfo=timezone.utc), row, window, sporttery_source))

    scored.sort(key=lambda item: (item[2], item[1], item[3]), reverse=True)
    candidates = []
    for source_key, score, _, _, row, window, item_source in scored[:limit]:
        if source_key == "dongqiudi":
            item = public_dongqiudi_fixture(row, score=score, source=item_source)
            item["odds_summary"] = odds_from_dongqiudi_match(row)
        elif source_key == "sporttery":
            item = {
                **row,
                "division": "sporttery:HAD",
                "match_score": score,
                "source": item_source,
            }
            item["odds_summary"] = odds_from_sporttery_fixture(row)
        else:
            item = public_fixture(row, score=score, source=item_source)
            item["odds_summary"] = odds_from_row(row)
        item["time_window"] = window
        candidates.append(item)

    return {
        "query": query,
        "translated_query": translated_query,
        "parsed_home_team": parsed_home,
        "parsed_away_team": parsed_away,
        "source": {
            "primary_schedule_list": "dongqiudi.com schedule_list",
            "primary_european_odds": "football-data.co.uk fixtures.csv",
            "football_data": source,
            "dongqiudi": dongqiudi_source,
            "sporttery": sporttery_source,
        },
        "time_window_policy": time_window_policy(as_of_dt, window_hours, as_of_supplied=bool(as_of)),
        "minimum_match_score": MATCH_SCORE_THRESHOLD,
        "candidate_count": len(candidates),
        "candidates": candidates,
    }


async def get_best_match(
    query: str,
    *,
    home_team: str | None = None,
    away_team: str | None = None,
    league: str | None = None,
    as_of: str | None = None,
    timezone_name: str | None = None,
    window_hours: int = 24,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    search = await find_candidates(
        query,
        home_team=home_team,
        away_team=away_team,
        league=league,
        as_of=as_of,
        timezone_name=timezone_name,
        window_hours=window_hours,
        limit=10,
    )
    candidates = search["candidates"]
    if not candidates:
        return None, search
    exactish = [candidate for candidate in candidates if (candidate.get("match_score") or 0) >= MATCH_SCORE_THRESHOLD]
    if exactish:
        return exactish[0], search
    return None, search


def _shortlist_match_query(match: dict[str, Any]) -> str:
    home = str(match.get("home_team") or "").strip()
    away = str(match.get("away_team") or "").strip()
    if home and away:
        return f"{home} vs {away}"
    return str(match.get("query") or "").strip()


def _shortlist_coverage_score(analysis: dict[str, Any]) -> dict[str, Any]:
    blocks = (((analysis.get("analysis_pack") or {}).get("data_coverage") or {}).get("blocks") or {})
    if not blocks:
        return {
            "ratio": 0.0,
            "available_blocks": [],
            "missing_blocks": [],
            "core_markets_ready": False,
        }

    available = [key for key, value in blocks.items() if bool(value)]
    missing = [key for key, value in blocks.items() if not bool(value)]
    core_markets = ["moneyline_1x2", "asian_handicap", "over_under"]
    core_ready = all(bool(blocks.get(key)) for key in core_markets)
    return {
        "ratio": round_metric(len(available) / len(blocks)) or 0.0,
        "available_blocks": available,
        "missing_blocks": missing,
        "core_markets_ready": core_ready,
    }


def _shortlist_data_block_state(analysis: dict[str, Any], key: str) -> bool | None:
    coverage = ((analysis.get("analysis_pack") or {}).get("data_coverage") or {})
    blocks = coverage.get("blocks") or {}
    if isinstance(blocks, dict) and key in blocks:
        return bool(blocks.get(key))

    missing_blocks = coverage.get("missing_blocks") or []
    if isinstance(missing_blocks, list) and key in missing_blocks:
        return False

    available_blocks = coverage.get("available_blocks") or []
    if isinstance(available_blocks, list) and key in available_blocks:
        return True
    return None


def _shortlist_caution_flag_set(analysis: dict[str, Any]) -> set[str]:
    support = analysis.get("betting_decision_support") or {}
    flags = {str(flag) for flag in support.get("caution_flags") or []}
    risk_overlay = analysis.get("risk_overlay") or support.get("risk_overlay") or {}
    flags.update(str(flag) for flag in risk_overlay.get("caution_flags") or [])
    return flags


def _shortlist_rejection_reason(
    analysis: dict[str, Any],
    *,
    min_edge: float,
    require_core_markets: bool,
    mode: str = "confidence",
    min_calibrated_probability: float = 0.58,
    min_decimal_odds: float = 1.65,
    max_decimal_odds: float = 2.05,
    min_value_edge: float = 0.02,
) -> str | None:
    if analysis.get("status") != "ok":
        return "analysis_failed"
    if analysis.get("_shortlist_target_market_missing"):
        return "target_market_missing"

    support = analysis.get("betting_decision_support") or {}
    if support.get("blocking_flags"):
        return "blocking_flags_present"

    quality = analysis.get("quality") or {}
    if quality and quality.get("is_bettable_input") is False:
        return "quality_not_bettable"

    coverage = _shortlist_coverage_score(analysis)
    if require_core_markets and not coverage.get("core_markets_ready"):
        return "core_market_missing"

    best = analysis.get("best_candidate") or support.get("best_candidate") or {}
    recommendation = str(best.get("recommendation") or "")
    if recommendation not in {"immediate_bet", "condition_observe"}:
        return "no_positive_edge"

    edge = parse_float(best.get("edge"))
    if edge is None or edge < min_edge:
        return "edge_below_threshold"

    if mode == "balanced":
        market = str(best.get("market") or analysis.get("_shortlist_target_market") or "")
        if market == "asian_handicap":
            line = parse_float(best.get("line"))
            if line is not None and abs(line) >= 2.0:
                return "large_handicap_requires_backtest"

            if _shortlist_data_block_state(analysis, "multi_bookmaker_snapshot") is False:
                return "multi_bookmaker_snapshot_missing"

            caution_flags = _shortlist_caution_flag_set(analysis)
            if (
                _shortlist_data_block_state(analysis, "lineup") is False
                or {"lineup_unavailable", "lineup_context_limited"} & caution_flags
            ):
                return "lineup_context_missing"

        confidence = _shortlist_selection_confidence(analysis, mode=mode)
        calibrated_probability = parse_float(confidence.get("calibrated_probability"))
        if calibrated_probability is None or calibrated_probability < min_calibrated_probability:
            return "calibrated_probability_below_threshold"

        decimal_odds = parse_float(confidence.get("decimal_odds"))
        if decimal_odds is None or decimal_odds < min_decimal_odds:
            return "decimal_odds_below_threshold"
        if decimal_odds > max_decimal_odds:
            return "decimal_odds_above_threshold"

        value_edge = parse_float(confidence.get("value_edge"))
        if value_edge is None or value_edge < min_value_edge:
            return "value_edge_below_threshold"

    return None


def _normalize_shortlist_target_market(target_market: str | None) -> str:
    normalized = str(target_market or "any").strip().lower()
    aliases = {
        "": "any",
        "all": "any",
        "any": "any",
        "1x2": "1x2",
        "moneyline": "1x2",
        "胜平负": "1x2",
        "asian": "asian_handicap",
        "ah": "asian_handicap",
        "asian_handicap": "asian_handicap",
        "亚盘": "asian_handicap",
        "handicap": "asian_handicap",
        "over_under": "over_under",
        "totals": "over_under",
        "大小球": "over_under",
    }
    return aliases.get(normalized, "any")


def _shortlist_candidate_rank(candidate: dict[str, Any]) -> tuple[float, float, float, float]:
    recommendation_rank = {
        "immediate_bet": 2.0,
        "condition_observe": 1.0,
        "no_value": 0.0,
        "no_bet": -1.0,
    }.get(str(candidate.get("recommendation") or ""), 0.0)
    calibrated = parse_float(candidate.get("calibrated_probability"))
    model_probability = parse_float(candidate.get("model_probability")) or 0.0
    probability = calibrated if calibrated is not None else model_probability
    edge = parse_float(candidate.get("edge")) or 0.0
    return recommendation_rank, probability or 0.0, edge, model_probability


def _shortlist_analysis_for_target_market(analysis: dict[str, Any], target_market: str) -> dict[str, Any]:
    if target_market == "any":
        return analysis

    support = analysis.get("betting_decision_support") or {}
    candidates = []
    best = analysis.get("best_candidate") or support.get("best_candidate") or {}
    if best:
        candidates.append(best)
    candidates.extend(analysis.get("market_candidates") or support.get("market_candidates") or [])
    matching = [
        candidate
        for candidate in candidates
        if str(candidate.get("market") or "") == target_market
    ]
    if not matching:
        return {
            **analysis,
            "_shortlist_target_market_missing": True,
            "_shortlist_target_market": target_market,
        }

    selected = max(matching, key=_shortlist_candidate_rank)
    blocking_flags = list(support.get("blocking_flags") or [])
    caution_flags = list(support.get("caution_flags") or [])
    confidence = parse_float(support.get("confidence")) or 0.0
    final_decision = _build_final_decision(
        selected,
        blocking_flags=blocking_flags,
        caution_flags=caution_flags,
    )
    risk_overlay = _build_risk_overlay(
        odds=analysis.get("odds") or {},
        blocking_flags=blocking_flags,
        caution_flags=caution_flags,
        best_candidate=selected,
        confidence=confidence,
    )
    final_execution_advice = _build_final_execution_advice(
        final_decision=final_decision,
        best_candidate=selected,
        risk_overlay=risk_overlay,
    )
    return {
        **analysis,
        "_shortlist_target_market": target_market,
        "best_candidate": selected,
        "final_decision": final_decision,
        "risk_overlay": risk_overlay,
        "final_execution_advice": final_execution_advice,
        "betting_decision_support": {
            **support,
            "best_candidate": selected,
            "final_decision": final_decision,
            "risk_overlay": risk_overlay,
            "final_execution_advice": final_execution_advice,
        },
    }


def _shortlist_effective_caution_flags(caution_flags: list[str], *, mode: str) -> list[str]:
    if mode in {"confidence", "balanced"}:
        return [flag for flag in caution_flags if flag != "near_kickoff_under_60m"]
    return caution_flags


def _shortlist_selection_confidence(analysis: dict[str, Any], *, mode: str = "confidence") -> dict[str, Any]:
    support = analysis.get("betting_decision_support") or {}
    best = analysis.get("best_candidate") or support.get("best_candidate") or {}
    raw_model_probability = parse_float(best.get("model_probability"))
    calibrated_probability = parse_float(best.get("calibrated_probability"))
    if calibrated_probability is None:
        calibrated_probability = raw_model_probability
    if calibrated_probability is None:
        calibrated_probability = parse_float(support.get("confidence"))

    coverage = _shortlist_coverage_score(analysis)
    caution_flags = list(support.get("caution_flags") or [])
    effective_cautions = _shortlist_effective_caution_flags(caution_flags, mode=mode)
    coverage_ratio = parse_float(coverage.get("ratio")) or 0.0
    reliability = _clamp(
        0.35 + coverage_ratio * 0.5 - min(len(effective_cautions), 6) * 0.04,
        0.05,
        1.0,
    )
    edge = parse_float(best.get("edge")) or 0.0
    decimal_odds = parse_float(best.get("decimal_odds"))
    fair_break_even_probability = 1 / decimal_odds if decimal_odds and decimal_odds > 0 else None
    value_edge = (
        calibrated_probability - fair_break_even_probability
        if calibrated_probability is not None and fair_break_even_probability is not None
        else None
    )
    expected_return = (
        calibrated_probability * decimal_odds - 1
        if calibrated_probability is not None and decimal_odds is not None
        else None
    )
    score = (
        (calibrated_probability or 0.0) * 100
        + reliability * 10
        + max(edge, 0.0) * 5
    )
    balanced_score = (
        (calibrated_probability or 0.0) * 100
        + max(value_edge or 0.0, 0.0) * 120
        + reliability * 10
    )
    return {
        "source": (
            "historical_calibrated_probability"
            if best.get("calibrated_probability") is not None
            else "raw_model_probability_fallback"
        ),
        "raw_model_probability": round_metric(raw_model_probability),
        "calibrated_probability": round_metric(calibrated_probability),
        "decimal_odds": round_metric(decimal_odds, 4),
        "fair_break_even_probability": round_metric(fair_break_even_probability),
        "value_edge": round_metric(value_edge),
        "expected_return": round_metric(expected_return, 4),
        "reliability_score": round_metric(reliability),
        "score": round_metric(score),
        "balanced_score": round_metric(balanced_score),
        "effective_caution_flags": effective_cautions,
        "ignored_caution_flags": [
            flag for flag in caution_flags if flag not in effective_cautions
        ],
        "rule": (
            "Balanced mode requires enough calibrated probability plus fair decimal odds before ranking by balanced_score."
            if mode == "balanced"
            else "Confidence mode ranks by calibrated_probability first, then reliability, then model probability and edge."
        ),
    }


def _shortlist_value_score(analysis: dict[str, Any], *, mode: str = "confidence") -> float:
    support = analysis.get("betting_decision_support") or {}
    best = analysis.get("best_candidate") or support.get("best_candidate") or {}
    recommendation = str(best.get("recommendation") or "")
    edge = parse_float(best.get("edge")) or 0.0
    confidence = parse_float(support.get("confidence")) or 0.0
    coverage = _shortlist_coverage_score(analysis)
    caution_count = len(_shortlist_effective_caution_flags(list(support.get("caution_flags") or []), mode=mode))

    recommendation_bonus = {
        "immediate_bet": 20.0,
        "condition_observe": 8.0,
    }.get(recommendation, 0.0)
    score = (
        recommendation_bonus
        + edge * 100
        + confidence * 10
        + (parse_float(coverage.get("ratio")) or 0.0) * 10
        - min(caution_count, 8) * 1.2
    )
    return round(score, 4)


def _compact_model_engine_evidence(analysis: dict[str, Any]) -> dict[str, Any]:
    support = analysis.get("betting_decision_support") if isinstance(analysis.get("betting_decision_support"), dict) else {}
    analysis_pack = analysis.get("analysis_pack") if isinstance(analysis.get("analysis_pack"), dict) else {}
    engine_candidates = (
        analysis.get("model_engine"),
        support.get("model_engine"),
        analysis_pack.get("model_engine"),
    )
    engine = next((item for item in engine_candidates if isinstance(item, dict) and item), {})
    if not engine:
        return {}

    evidence_keys = (
        "available",
        "version",
        "method",
        "match_key",
        "expected_goals",
        "dixon_coles",
        "fitted_market_targets",
        "top_scorelines",
        "model_quality",
        "probability_source",
        "penaltyblog_adapter",
    )
    return {key: engine[key] for key in evidence_keys if key in engine}


def _shortlist_pick_from_analysis(analysis: dict[str, Any], *, mode: str = "confidence") -> dict[str, Any]:
    support = analysis.get("betting_decision_support") or {}
    coverage = _shortlist_coverage_score(analysis)
    selection_confidence = _shortlist_selection_confidence(analysis, mode=mode)
    model_engine_evidence = _compact_model_engine_evidence(analysis)
    return {
        "match": analysis.get("match") or (analysis.get("agent_brief") or {}).get("match") or {},
        "match_context": analysis.get("match_context") or {},
        "final_decision": analysis.get("final_decision") or support.get("final_decision") or {},
        "final_execution_advice": analysis.get("final_execution_advice") or support.get("final_execution_advice") or {},
        "risk_overlay": analysis.get("risk_overlay") or support.get("risk_overlay") or {},
        "best_candidate": analysis.get("best_candidate") or support.get("best_candidate") or {},
        "market_candidates": analysis.get("market_candidates") or support.get("market_candidates") or [],
        "value_score": _shortlist_value_score(analysis, mode=mode),
        "selection_confidence": selection_confidence,
        "learning_policy": analysis.get("learning_policy") or {},
        "data_completeness": coverage,
        "blocking_flags": support.get("blocking_flags") or [],
        "caution_flags": support.get("caution_flags") or [],
        "confidence": support.get("confidence"),
        "quality": analysis.get("quality") or {},
        "time_window": analysis.get("time_window") or {},
        "model_engine": model_engine_evidence,
        "rationale": {
            "ranking_inputs": [
                "MCP best_candidate recommendation",
                "MCP edge",
                "MCP confidence or calibrated_probability",
                "data coverage ratio",
                "caution flag penalty",
            ],
            "score": _shortlist_value_score(analysis, mode=mode),
        },
    }


def _append_recommendation_log(record: dict[str, Any], path: str | None) -> dict[str, Any]:
    target = path or os.getenv("FOOTBALL_DATA_MCP_RECOMMENDATION_LOG", "/tmp/football-data-mcp-recommendations.jsonl")
    try:
        directory = os.path.dirname(target)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(target, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        return {"saved": True, "path": target}
    except OSError as exc:
        return {"saved": False, "path": target, "error": f"{type(exc).__name__}: {exc}"}


def _shortlist_funnel_report(
    *,
    total_candidates: int,
    analyzed_count: int,
    not_analyzed_count: int,
    eligible_count: int,
    returned_count: int,
    rejected: list[dict[str, Any]],
) -> dict[str, Any]:
    reason_counts = Counter(str(item.get("reason") or "unknown") for item in rejected)
    hard_blocker_counts: Counter[str] = Counter()
    quality_counts: Counter[str] = Counter()
    for item in rejected:
        for flag in item.get("blocking_flags") or []:
            hard_blocker_counts[str(flag)] += 1
        quality = item.get("quality") or {}
        if quality.get("is_bettable_input") is False:
            quality_counts["quality_not_bettable"] += 1
        for flag in quality.get("hard_blockers") or []:
            hard_blocker_counts[str(flag)] += 1
        reason = str(item.get("reason") or "")
        if reason in {"core_market_missing", "target_market_missing"}:
            quality_counts[reason] += 1
    return {
        "candidate_counts": {
            "total": total_candidates,
            "analyzed": analyzed_count,
            "not_analyzed": not_analyzed_count,
            "eligible": eligible_count,
            "returned": returned_count,
            "rejected": len(rejected),
        },
        "rejection_reasons": dict(sorted(reason_counts.items())),
        "hard_blockers": dict(sorted(hard_blocker_counts.items())),
        "quality_gaps": dict(sorted(quality_counts.items())),
        "policy": (
            "Funnel counts are computed from MCP-analyzed candidates only. "
            "Returned picks stay capped by top_n; shadow learning can persist the wider analyzed set."
        ),
    }


def _pick_advice(pick: dict[str, Any]) -> dict[str, Any]:
    return pick.get("final_execution_advice") or pick.get("final_decision") or {}


def _pick_market(pick: dict[str, Any]) -> str:
    advice = _pick_advice(pick)
    best = pick.get("best_candidate") or {}
    return str(advice.get("market") or best.get("market") or "none")


def _pick_decimal_odds(pick: dict[str, Any]) -> float | None:
    advice = _pick_advice(pick)
    best = pick.get("best_candidate") or {}
    return parse_float(advice.get("decimal_odds")) or parse_float(best.get("decimal_odds"))


def _pick_model_probability(pick: dict[str, Any]) -> float | None:
    best = pick.get("best_candidate") or {}
    model_probability = parse_float(best.get("model_probability"))
    if model_probability is not None:
        return round_metric(_clamp(model_probability, 0.01, 0.95))
    market_probability = parse_float(best.get("market_probability"))
    edge = parse_float(best.get("edge"))
    if market_probability is not None and edge is not None:
        return round_metric(_clamp(market_probability + edge, 0.01, 0.95))
    decimal_odds = _pick_decimal_odds(pick)
    if decimal_odds and decimal_odds > 1:
        return round_metric(_clamp(1 / decimal_odds, 0.01, 0.95))
    return None


def _pick_line(pick: dict[str, Any]) -> float | None:
    advice = _pick_advice(pick)
    best = pick.get("best_candidate") or {}
    line = parse_float(advice.get("line"))
    if line is not None:
        return line
    line = parse_float(best.get("line"))
    if line is not None:
        return line
    selection = str(advice.get("selection") or best.get("selection") or "")
    match = re.search(r"([+-]\d+(?:\.\d+)?)", selection)
    if match:
        return parse_float(match.group(1))
    return None


def _calibrated_leg_probability(
    *,
    market: str,
    raw_probability: float,
    line: float | None,
    caution_flags: list[str],
) -> dict[str, Any]:
    probability = _clamp(raw_probability, 0.01, 0.95)
    notes: list[str] = []
    flags: list[str] = []
    cap = 0.95

    if market in {"asian_handicap", "over_under"}:
        cap = min(cap, 0.64)
        notes.append("non_official_market_cap_0.64")
    if market == "over_under":
        cap = min(cap, 0.61)
        notes.append("totals_market_cap_0.61")
    if market == "asian_handicap" and line is not None:
        abs_line = abs(line)
        if abs_line >= 2.5:
            cap = min(cap, 0.48)
            flags.append("deep_handicap_line")
            notes.append("asian_handicap_abs_line_ge_2.5_cap_0.48")
        elif abs_line >= 2.0:
            cap = min(cap, 0.52)
            flags.append("deep_handicap_line")
            notes.append("asian_handicap_abs_line_ge_2.0_cap_0.52")
        elif abs_line >= 1.5:
            cap = min(cap, 0.56)
            flags.append("aggressive_handicap_line")
            notes.append("asian_handicap_abs_line_ge_1.5_cap_0.56")
        elif abs_line >= 1.0:
            cap = min(cap, 0.60)
            flags.append("wide_handicap_line")
            notes.append("asian_handicap_abs_line_ge_1.0_cap_0.60")

    capped = min(probability, cap)
    if capped < probability:
        flags.append("leg_probability_capped")
    caution_discount = 1.0
    if caution_flags:
        caution_discount = 0.96 ** min(len(caution_flags), 5)
        notes.append(f"caution_discount_{round_metric(caution_discount, 4)}")
    calibrated = round_metric(_clamp(capped * caution_discount, 0.01, 0.95))
    return {
        "raw_model_probability": round_metric(raw_probability),
        "calibrated_model_probability": calibrated,
        "cap": round_metric(cap),
        "caution_discount": round_metric(caution_discount, 4),
        "applied": calibrated != round_metric(raw_probability),
        "notes": notes,
        "risk_flags": flags,
    }


def _parlay_market_scope(markets: list[str]) -> str:
    if markets and all(market in {"1x2", "jingcai_hhad"} for market in markets):
        return "jingcai_supported"
    return "mixed_non_official"


def _parlay_leg_from_pick(pick: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    advice = _pick_advice(pick)
    best = pick.get("best_candidate") or {}
    match = pick.get("match") or {}
    action = str(advice.get("action") or advice.get("recommendation") or "")
    if action not in {"bet_now", "immediate_bet", "observe", "condition_observe"}:
        return None, "final_action_not_actionable"
    decimal_odds = _pick_decimal_odds(pick)
    if decimal_odds is None or decimal_odds <= 1:
        return None, "decimal_odds_missing"
    model_probability = _pick_model_probability(pick)
    if model_probability is None or model_probability <= 0:
        return None, "model_probability_missing"

    market = _pick_market(pick)
    line = _pick_line(pick)
    caution_flags = pick.get("caution_flags") or []
    probability_calibration = _calibrated_leg_probability(
        market=market,
        raw_probability=model_probability,
        line=line,
        caution_flags=caution_flags,
    )
    market_scope = "jingcai_supported" if market in {"1x2", "jingcai_hhad"} else "non_official_handicap_or_totals"
    return {
        "match": match,
        "league": match.get("league") or "",
        "home_team": match.get("home_team") or "",
        "away_team": match.get("away_team") or "",
        "market": market,
        "market_label": advice.get("market_label") or _market_label(market),
        "market_scope": market_scope,
        "selection": advice.get("selection") or best.get("selection") or "",
        "decimal_odds": round_metric(decimal_odds, 4),
        "line": line,
        "raw_model_probability": model_probability,
        "model_probability": probability_calibration["calibrated_model_probability"],
        "probability_calibration": probability_calibration,
        "market_probability": parse_float(best.get("market_probability")),
        "edge": parse_float(best.get("edge")),
        "action": "bet_now" if action in {"bet_now", "immediate_bet"} else "observe",
        "confidence": parse_float(pick.get("confidence")),
        "parlay_mode": pick.get("parlay_mode") or best.get("parlay_mode"),
        "caution_flags": caution_flags,
        "source_value_score": pick.get("value_score"),
        "official_pool": advice.get("official_pool") or best.get("official_pool"),
        "match_num_str": match.get("match_num_str") or "",
        "odds_source": advice.get("odds_source") or best.get("odds_source") or "",
        "parlay_mode": best.get("parlay_mode") or (pick.get("selection_confidence") or {}).get("parlay_mode"),
        "negative_ev_allowed": bool(best.get("negative_ev_allowed")),
        "expected_multiplier": best.get("expected_multiplier"),
        "required_probability_for_1pct_ev": best.get("required_probability_for_1pct_ev"),
    }, None


def _analysis_1x2_candidates(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    support = analysis.get("betting_decision_support") or {}
    candidates = []
    for item in [analysis.get("best_candidate") or support.get("best_candidate") or {}]:
        if item:
            candidates.append(item)
    candidates.extend(analysis.get("market_candidates") or [])
    candidates.extend(support.get("market_candidates") or [])
    seen: set[str] = set()
    result = []
    for candidate in candidates:
        if str(candidate.get("market") or "") != "1x2":
            continue
        key = str(candidate.get("selection_key") or "")
        signature = f"{key}:{candidate.get('selection')}:{candidate.get('decimal_odds')}"
        if signature in seen:
            continue
        seen.add(signature)
        result.append(candidate)
    return result


def _normalize_parlay_mode(parlay_mode: str | None) -> str:
    normalized = str(parlay_mode or "confidence").strip().lower()
    aliases = {
        "": "confidence",
        "confidence": "confidence",
        "conf": "confidence",
        "balance": "confidence",
        "balanced": "confidence",
        "稳胆": "confidence",
        "稳健": "confidence",
        "hit_rate": "confidence",
        "value": "value",
        "ev": "value",
    }
    return aliases.get(normalized, "confidence")


def _analysis_model_engine_1x2_probabilities(analysis: dict[str, Any]) -> dict[str, float]:
    sources = [
        analysis.get("model_engine") or {},
        ((analysis.get("analysis_pack") or {}).get("model_engine") or {}),
        ((analysis.get("betting_decision_support") or {}).get("model_engine") or {}),
    ]
    for source in sources:
        probabilities = (source.get("derived_probabilities") or {}).get("1x2") or {}
        parsed = {
            key: parse_float(probabilities.get(key))
            for key in ("home", "draw", "away")
        }
        if any(value is not None for value in parsed.values()):
            return {key: value for key, value in parsed.items() if value is not None}
    return {}


def _official_had_enriched_candidates(fixture: dict[str, Any], analysis: dict[str, Any]) -> list[dict[str, Any]]:
    had = (fixture.get("official_odds") or {}).get("HAD") or {}
    official_market = _sporttery_three_way_probability(had)
    candidate_by_key: dict[str, dict[str, Any]] = {}
    for candidate in _analysis_1x2_candidates(analysis):
        key = _infer_1x2_selection_key(candidate, fixture)
        if key in {"home", "draw", "away"}:
            candidate_by_key[key] = candidate
    model_probabilities = _analysis_model_engine_1x2_probabilities(analysis)

    enriched = []
    for key in ("home", "draw", "away"):
        candidate = candidate_by_key.get(key) or {"market": "1x2", "selection_key": key}
        decimal_odds = parse_float(had.get(key))
        market_probability = parse_float(official_market.get(key))
        model_probability = (
            parse_float(candidate.get("calibrated_probability"))
            or parse_float(candidate.get("model_probability"))
            or parse_float(model_probabilities.get(key))
        )
        if decimal_odds is None or market_probability is None or model_probability is None:
            continue
        raw_implied_probability = round_metric(1 / decimal_odds)
        expected_multiplier = round_metric(model_probability * decimal_odds, 6)
        edge = round_metric((expected_multiplier or 0) - 1, 4)
        enriched.append(
            {
                **candidate,
                "market": "1x2",
                "selection_key": key,
                "selection": _sporttery_selection_label(fixture, key),
                "decimal_odds": decimal_odds,
                "market_probability": market_probability,
                "raw_implied_probability": raw_implied_probability,
                "model_probability": round_metric(model_probability),
                "required_probability_for_1pct_ev": round_metric(1.01 / decimal_odds),
                "expected_multiplier": expected_multiplier,
                "edge": edge,
                "edge_basis": "expected_multiplier_minus_1",
                "provider": "中国竞彩网",
                "official_pool": "HAD",
                "odds_source": "sporttery_official_had",
            }
        )
    return enriched


def _infer_1x2_selection_key(candidate: dict[str, Any], fixture: dict[str, Any]) -> str:
    key = str(candidate.get("selection_key") or "").strip().lower()
    if key in {"home", "draw", "away"}:
        return key
    selection = str(candidate.get("selection") or "")
    if "平" in selection or "draw" in selection.lower():
        return "draw"
    home = str(fixture.get("home_team") or "")
    away = str(fixture.get("away_team") or "")
    if home and home in selection:
        return "home"
    if away and away in selection:
        return "away"
    return ""


def _sporttery_selection_label(fixture: dict[str, Any], key: str) -> str:
    if key == "home":
        return f"{fixture.get('home_team') or '主队'} 主胜"
    if key == "away":
        return f"{fixture.get('away_team') or '客队'} 客胜"
    return "平局"


def _sporttery_pick_from_analysis(
    fixture: dict[str, Any],
    analysis: dict[str, Any],
    *,
    min_edge: float,
    parlay_mode: str = "confidence",
    min_confidence_leg_probability: float = 0.60,
    min_confidence_decimal_odds: float = 1.15,
    max_confidence_decimal_odds: float = 2.05,
    min_confidence_edge: float = -0.12,
) -> tuple[dict[str, Any] | None, str | None]:
    parlay_mode = _normalize_parlay_mode(parlay_mode)
    if analysis.get("status") != "ok":
        return None, f"analysis_{analysis.get('status') or 'failed'}"

    had = (fixture.get("official_odds") or {}).get("HAD") or {}
    official_market = _sporttery_three_way_probability(had)
    if not official_market:
        return None, "official_had_odds_missing"

    support = analysis.get("betting_decision_support") or {}
    blocking_flags = list(support.get("blocking_flags") or [])
    if blocking_flags:
        return None, "blocking_flags_present"

    enriched = _official_had_enriched_candidates(fixture, analysis)
    if not enriched:
        return None, "official_1x2_model_candidate_missing"

    confidence = parse_float(support.get("confidence")) or parse_float(analysis.get("confidence")) or 0.56
    caution_flags = list(support.get("caution_flags") or [])
    if parlay_mode == "confidence":
        eligible = [
            item
            for item in enriched
            if (parse_float(item.get("model_probability")) or 0.0) >= min_confidence_leg_probability
            and (parse_float(item.get("decimal_odds")) or 0.0) >= min_confidence_decimal_odds
            and (parse_float(item.get("decimal_odds")) or 999.0) <= max_confidence_decimal_odds
            and (parse_float(item.get("edge")) or -999.0) >= min_confidence_edge
        ]
        if not eligible:
            best_rejected = max(
                enriched,
                key=lambda item: (
                    parse_float(item.get("model_probability")) or 0.0,
                    parse_float(item.get("edge")) or -999.0,
                ),
            )
            if (parse_float(best_rejected.get("model_probability")) or 0.0) < min_confidence_leg_probability:
                return None, "official_had_confidence_probability_below_threshold"
            if (parse_float(best_rejected.get("decimal_odds")) or 0.0) < min_confidence_decimal_odds:
                return None, "official_had_confidence_odds_below_threshold"
            if (parse_float(best_rejected.get("decimal_odds")) or 999.0) > max_confidence_decimal_odds:
                return None, "official_had_confidence_odds_above_threshold"
            return None, "official_had_confidence_ev_too_negative"
        best = max(
            eligible,
            key=lambda item: (
                parse_float(item.get("model_probability")) or 0.0,
                parse_float(item.get("decimal_odds")) or 0.0,
                parse_float(item.get("edge")) or -999.0,
            ),
        )
        recommendation = "immediate_bet"
    else:
        best = max(
            enriched,
            key=lambda item: (
                parse_float(item.get("edge")) or -999.0,
                parse_float(item.get("model_probability")) or 0.0,
            ),
        )
        recommendation = _recommendation_from_edge(parse_float(best.get("edge")), confidence, blocking_flags)
        if parse_float(best.get("edge")) is None or parse_float(best.get("edge")) < min_edge:
            return None, "official_had_ev_below_threshold"
        if recommendation == "no_value":
            return None, "official_had_no_positive_edge"

    action = "bet_now" if recommendation == "immediate_bet" else "observe"
    best = {
        **best,
        "recommendation": recommendation,
        "stake_level": "small" if parlay_mode == "confidence" else _stake_level(recommendation, confidence, len(caution_flags)),
        "parlay_mode": parlay_mode,
        "negative_ev_allowed": parlay_mode == "confidence" and (parse_float(best.get("edge")) or 0.0) < min_edge,
    }
    execution = {
        "action": action,
        "market": "1x2",
        "market_label": "竞彩胜平负",
        "selection": best.get("selection") or "",
        "decimal_odds": best.get("decimal_odds"),
        "stake_level": best.get("stake_level"),
        "official_pool": "HAD",
        "odds_source": "sporttery_official_had",
    }
    match = {
        **fixture,
        "source_name": "sporttery",
        "official_pool": "HAD",
    }
    return {
        "match": match,
        "final_execution_advice": execution,
        "final_decision": {
            "recommendation": recommendation,
            "market": "1x2",
            "selection": best.get("selection") or "",
            "stake_level": execution["stake_level"],
        },
        "best_candidate": best,
        "market_candidates": enriched,
        "value_score": _shortlist_value_score(
            {
                "best_candidate": best,
                "betting_decision_support": {"confidence": confidence, "caution_flags": caution_flags},
                "analysis_pack": analysis.get("analysis_pack") or {},
            }
        ),
        "selection_confidence": {
            "source": "sporttery_official_had_plus_mcp_model_probability",
            "parlay_mode": parlay_mode,
            "decimal_odds": best.get("decimal_odds"),
            "market_probability": best.get("market_probability"),
            "model_probability": best.get("model_probability"),
            "value_edge": best.get("edge"),
            "expected_multiplier": best.get("expected_multiplier"),
            "required_probability_for_1pct_ev": best.get("required_probability_for_1pct_ev"),
            "negative_ev_allowed": best.get("negative_ev_allowed"),
        },
        "data_completeness": _shortlist_coverage_score(analysis),
        "blocking_flags": blocking_flags,
        "caution_flags": caution_flags,
        "confidence": confidence,
        "parlay_mode": parlay_mode,
        "quality": analysis.get("quality") or {},
    }, None


async def _official_sporttery_picks(
    fixtures: list[dict[str, Any]],
    *,
    as_of: str | None,
    timezone_name: str | None,
    window_minutes: int,
    limit: int,
    min_edge: float,
    parlay_mode: str = "confidence",
    min_confidence_leg_probability: float = 0.60,
    min_confidence_decimal_odds: float = 1.15,
    max_confidence_decimal_odds: float = 2.05,
    min_confidence_edge: float = -0.12,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    selected_fixtures = [
        fixture
        for fixture in fixtures
        if fixture.get("analysis_readiness") is None
        or (fixture.get("analysis_readiness") or {}).get("can_run_single_match_analysis")
    ][: max(1, int(limit or 30))]
    semaphore = asyncio.Semaphore(6)
    analyzed_count = 0

    async def analyze_fixture(fixture: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        nonlocal analyzed_count
        query = f"{fixture.get('home_team') or ''} vs {fixture.get('away_team') or ''}".strip()
        async with semaphore:
            try:
                analysis = await analyze_single_match(
                    query,
                    home_team=str(fixture.get("home_team") or "") or None,
                    away_team=str(fixture.get("away_team") or "") or None,
                    league=str(fixture.get("league") or "") or None,
                    as_of=as_of,
                    timezone_name=timezone_name,
                    window_hours=max(1, int((window_minutes + 59) // 60)),
                    include_source_probe=False,
                )
                analyzed_count += 1
                pick, reason = _sporttery_pick_from_analysis(
                    fixture,
                    analysis,
                    min_edge=min_edge,
                    parlay_mode=parlay_mode,
                    min_confidence_leg_probability=min_confidence_leg_probability,
                    min_confidence_decimal_odds=min_confidence_decimal_odds,
                    max_confidence_decimal_odds=max_confidence_decimal_odds,
                    min_confidence_edge=min_confidence_edge,
                )
            except Exception as exc:
                pick, reason = None, f"analysis_error:{type(exc).__name__}"
            if pick:
                return pick, None
            return None, {"match": fixture, "reason": reason or "official_pick_unavailable"}

    results = await asyncio.gather(*(analyze_fixture(fixture) for fixture in selected_fixtures))
    picks = [pick for pick, _ in results if pick]
    rejected = [rejection for _, rejection in results if rejection]
    return picks, rejected, analyzed_count


def _combined_decimal_odds(legs: tuple[dict[str, Any], ...]) -> float:
    value = 1.0
    for leg in legs:
        value *= float(leg.get("decimal_odds") or 1)
    return round_metric(value, 4) or 0.0


def _combined_probability(legs: tuple[dict[str, Any], ...]) -> float:
    value = 1.0
    for leg in legs:
        value *= float(leg.get("model_probability") or 0)
    return round_metric(value, 6) or 0.0


def _parlay_dependence_factor(legs: tuple[dict[str, Any], ...], market_scope: str) -> float:
    if market_scope == "jingcai_supported" and len(legs) == 2:
        return 1.0
    factor = 0.9 if market_scope != "jingcai_supported" else 0.95
    if len(legs) >= 3:
        factor *= 0.9
    caution_count = sum(len(leg.get("caution_flags") or []) for leg in legs)
    if caution_count:
        factor *= 0.98 ** min(caution_count, 6)
    return round_metric(_clamp(factor, 0.65, 1.0), 4) or 1.0


def _parlay_stake_level(
    *,
    recommendation: str,
    risk_level: str,
    market_scope: str,
    observe_leg_count: int,
    caution_count: int,
) -> str:
    if recommendation != "parlay_recommended":
        return "none"
    if observe_leg_count:
        return "watch_only_until_condition"
    if market_scope != "jingcai_supported" or risk_level == "high" or caution_count:
        return "tiny"
    if risk_level == "medium":
        return "small"
    return "small_to_normal"


def _build_parlay_ticket(
    legs: tuple[dict[str, Any], ...],
    *,
    min_combined_edge: float,
    parlay_mode: str = "confidence",
    min_confidence_combined_odds_2: float = 1.60,
    min_confidence_combined_odds_3: float = 2.00,
) -> dict[str, Any]:
    parlay_mode = _normalize_parlay_mode(parlay_mode)
    combined_odds = _combined_decimal_odds(legs)
    markets = [str(leg.get("market") or "") for leg in legs]
    market_scope = _parlay_market_scope(markets)
    confidence_jingcai_mode = parlay_mode == "confidence" and market_scope == "jingcai_supported"
    raw_combined_probability = _combined_probability(legs)
    dependence_factor = _parlay_dependence_factor(legs, market_scope)
    estimated_hit_probability = round_metric(raw_combined_probability * dependence_factor, 6) or 0.0
    expected_multiplier = round_metric(combined_odds * estimated_hit_probability, 6) or 0.0
    edge_proxy = round_metric(expected_multiplier - 1, 4) or 0.0
    caution_flags = []
    for leg in legs:
        for flag in leg.get("caution_flags") or []:
            _append_unique(caution_flags, flag)
    risk_flags = []
    if confidence_jingcai_mode:
        risk_flags.append("confidence_mode")
    if market_scope != "jingcai_supported":
        risk_flags.append("contains_non_official_handicap_or_totals")
    observe_leg_count = sum(1 for leg in legs if leg.get("action") == "observe")
    if observe_leg_count:
        risk_flags.append("contains_observe_condition_leg")
    if estimated_hit_probability < 0.25:
        risk_flags.append("low_combined_hit_probability")
    if caution_flags:
        risk_flags.append("leg_caution_flags_present")
    if dependence_factor < 1:
        risk_flags.append("parlay_dependence_penalty_applied")
    for leg in legs:
        for flag in (leg.get("probability_calibration") or {}).get("risk_flags") or []:
            _append_unique(risk_flags, flag)
    if confidence_jingcai_mode and (
        edge_proxy < 0
        or any((parse_float(leg.get("edge")) or 0.0) < 0 for leg in legs)
        or any(leg.get("negative_ev_allowed") for leg in legs)
    ):
        _append_unique(risk_flags, "confidence_mode_negative_ev_allowed")

    risk_level = "medium"
    if confidence_jingcai_mode:
        minimum_hit_probability = 0.34 if len(legs) == 2 else 0.20
        if estimated_hit_probability < minimum_hit_probability or len(risk_flags) >= 5:
            risk_level = "high"
    else:
        if "deep_handicap_line" in risk_flags or len(legs) >= 3 or estimated_hit_probability < 0.22 or len(risk_flags) >= 4:
            risk_level = "high"
        elif not risk_flags and estimated_hit_probability >= 0.34:
            risk_level = "medium"

    required_edge = min_combined_edge
    if market_scope != "jingcai_supported":
        required_edge = min(min_combined_edge, 0.01)
    required_combined_odds = (
        min_confidence_combined_odds_3 if confidence_jingcai_mode and len(legs) >= 3 else min_confidence_combined_odds_2
    )
    if confidence_jingcai_mode:
        recommendation = (
            "parlay_recommended"
            if combined_odds >= required_combined_odds and risk_level != "high"
            else "single_bet_preferred"
        )
    else:
        recommendation = "parlay_recommended" if edge_proxy >= required_edge and risk_level != "high" else "single_bet_preferred"
    if confidence_jingcai_mode and recommendation == "parlay_recommended" and "confidence_mode_negative_ev_allowed" in risk_flags:
        stake_level = "tiny"
    else:
        stake_level = _parlay_stake_level(
            recommendation=recommendation,
            risk_level=risk_level,
            market_scope=market_scope,
            observe_leg_count=observe_leg_count,
            caution_count=len(caution_flags),
        )
    return {
        "parlay_type": f"{len(legs)}串1",
        "parlay_mode": parlay_mode,
        "recommendation": recommendation,
        "stake_level": stake_level,
        "risk_level": risk_level,
        "market_scope": market_scope,
        "combined_decimal_odds": combined_odds,
        "raw_combined_probability": raw_combined_probability,
        "dependence_factor": dependence_factor,
        "estimated_hit_probability": estimated_hit_probability,
        "expected_multiplier": expected_multiplier,
        "edge_proxy": edge_proxy,
        "required_edge": round_metric(required_edge, 4),
        "required_combined_odds": round_metric(required_combined_odds, 4) if confidence_jingcai_mode else None,
        "risk_flags": risk_flags,
        "confidence_mode_note": (
            "置信模式推荐：优先高命中率与低波动，不代表正EV价值单；edge_proxy<0 时必须标注负EV风险。"
            if confidence_jingcai_mode
            else ""
        ),
        "caution_flags": caution_flags,
        "legs": list(legs),
        "calculation_policy": (
            "combined_decimal_odds is the product of leg decimal odds; estimated_hit_probability is the product of calibrated MCP leg probabilities "
            "after a dependence/risk discount. This is a ranking proxy, not a guarantee."
        ),
    }


def _single_fallback_from_leg(leg: dict[str, Any]) -> dict[str, Any]:
    decimal_odds = parse_float(leg.get("decimal_odds")) or 0.0
    probability = parse_float(leg.get("model_probability")) or 0.0
    expected_multiplier = round_metric(decimal_odds * probability, 6) or 0.0
    single_edge_proxy = round_metric(expected_multiplier - 1, 4)
    single_recommendation = "single_recommended" if single_edge_proxy is not None and single_edge_proxy >= 0.01 else "watch_only"
    return {
        "match": leg.get("match") or {},
        "market": leg.get("market"),
        "market_label": leg.get("market_label"),
        "selection": leg.get("selection"),
        "decimal_odds": decimal_odds,
        "raw_model_probability": leg.get("raw_model_probability"),
        "model_probability": probability,
        "single_expected_multiplier": expected_multiplier,
        "single_edge_proxy": single_edge_proxy,
        "single_recommendation": single_recommendation,
        "stake_level": (
            "none"
            if single_recommendation != "single_recommended"
            else ("tiny" if leg.get("market_scope") != "jingcai_supported" or leg.get("caution_flags") else "small")
        ),
        "risk_flags": (leg.get("probability_calibration") or {}).get("risk_flags") or [],
        "caution_flags": leg.get("caution_flags") or [],
        "probability_calibration": leg.get("probability_calibration") or {},
    }


def _recommendation_summary(recommended: list[dict[str, Any]], fallbacks: list[dict[str, Any]]) -> dict[str, Any]:
    if recommended:
        best = recommended[0]
        negative_ev_note = "（置信模式，负EV，非价值单）" if "confidence_mode_negative_ev_allowed" in (best.get("risk_flags") or []) else ""
        return {
            "action": "recommend_parlay",
            "headline": f"推荐{best.get('parlay_type')}{negative_ev_note}，仓位 {best.get('stake_level')}，总赔率 {best.get('combined_decimal_odds')}",
            "primary": {
                "parlay_type": best.get("parlay_type"),
                "stake_level": best.get("stake_level"),
                "combined_decimal_odds": best.get("combined_decimal_odds"),
                "estimated_hit_probability": best.get("estimated_hit_probability"),
            },
        }
    recommended_fallbacks = [item for item in fallbacks if item.get("single_recommendation") == "single_recommended"]
    if recommended_fallbacks:
        return {
            "action": "single_bet_fallback",
            "headline": "没有达到 MCP 风险阈值的串单；优先参考单关候选。",
            "primary": {
                "selection": recommended_fallbacks[0].get("selection"),
                "stake_level": recommended_fallbacks[0].get("stake_level"),
                "single_expected_multiplier": recommended_fallbacks[0].get("single_expected_multiplier"),
            },
        }
    return {
        "action": "no_bettable_candidate",
        "headline": "没有可用串单或单关候选。",
        "primary": {},
    }


async def recommend_jingcai_parlay(
    *,
    query: str = "",
    league: str | None = None,
    as_of: str | None = None,
    timezone_name: str | None = None,
    window_minutes: int = JINGCAI_PARLAY_DEFAULT_WINDOW_MINUTES,
    top_n: int = 3,
    limit: int = 30,
    min_edge: float = 0.01,
    min_combined_edge: float = 0.03,
    max_legs: int = 3,
    parlay_mode: str = "confidence",
    min_confidence_leg_probability: float = 0.60,
    min_confidence_decimal_odds: float = 1.15,
    max_confidence_decimal_odds: float = 2.05,
    min_confidence_edge: float = -0.12,
    min_confidence_combined_odds_2: float = 1.60,
    min_confidence_combined_odds_3: float = 2.00,
    include_non_official_markets: bool = False,
    allow_observe_legs: bool = False,
    recommendation_log_path: str | None = None,
) -> dict[str, Any]:
    """Build MCP-owned 2串1/3串1 tickets from shortlist picks without agent-side recomputation."""
    effective_window_minutes = int(window_minutes or JINGCAI_PARLAY_DEFAULT_WINDOW_MINUTES)
    parlay_mode = _normalize_parlay_mode(parlay_mode)
    official_jingcai_source: dict[str, Any] = {
        "enabled": not include_non_official_markets,
        "source": None,
        "selling_count": 0,
        "analyzed_count": 0,
        "eligible_pick_count": 0,
        "rejected_count": 0,
        "rule": (
            "Official Jingcai mode uses Sporttery Selling HAD fixtures first. "
            "It does not build official Jingcai parlays from Asian handicap or totals candidates. "
            "Default confidence mode favors higher-hit-rate HAD legs even when the strict EV proxy is slightly negative."
        ),
    }
    official_rejected: list[dict[str, Any]] = []
    if not include_non_official_markets:
        as_of_dt = parse_as_of(as_of, timezone_name)
        try:
            official_matches, sporttery_source = await load_sporttery_official_matches(as_of_dt, effective_window_minutes)
            official_jingcai_source.update(
                {
                    "status": "ok",
                    "source": sporttery_source,
                    "selling_count": len(official_matches),
                    "sample_matches": official_matches[: min(5, len(official_matches))],
                }
            )
            picks, official_rejected, official_analyzed_count = await _official_sporttery_picks(
                official_matches,
                as_of=as_of_dt.isoformat(),
                timezone_name=timezone_name or getattr(as_of_dt.tzinfo, "key", str(as_of_dt.tzinfo)),
                window_minutes=effective_window_minutes,
                limit=limit,
                min_edge=min_edge,
                parlay_mode=parlay_mode,
                min_confidence_leg_probability=min_confidence_leg_probability,
                min_confidence_decimal_odds=min_confidence_decimal_odds,
                max_confidence_decimal_odds=max_confidence_decimal_odds,
                min_confidence_edge=min_confidence_edge,
            )
            official_jingcai_source.update(
                {
                    "analyzed_count": official_analyzed_count,
                    "eligible_pick_count": len(picks),
                    "rejected_count": len(official_rejected),
                    "rejected_reasons": Counter(str(item.get("reason") or "") for item in official_rejected),
                }
            )
            shortlist = {
                "status": "ok",
                "tool": "sporttery_official_jingcai_had",
                "total_candidates": len(official_matches),
                "analyzed_count": official_analyzed_count,
                "picks": picks,
            }
        except Exception as exc:
            picks = []
            shortlist = {
                "status": "source_unavailable",
                "tool": "sporttery_official_jingcai_had",
                "total_candidates": 0,
                "analyzed_count": 0,
                "picks": [],
                "error": f"{type(exc).__name__}: {exc}",
            }
            official_jingcai_source.update(
                {
                    "status": "source_unavailable",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    else:
        shortlist = await shortlist_value_matches(
            query=query or "",
            league=league,
            as_of=as_of,
            timezone_name=timezone_name,
            window_minutes=effective_window_minutes,
            top_n=max(6, int(top_n or 3) * 3),
            limit=limit,
            min_edge=min_edge,
            mode=parlay_mode,
            require_core_markets=True,
            analysis_candidate_limit=max(8, min(int(limit or 30), 30)),
            analysis_concurrency=6,
            recommendation_log_path=None,
        )
        picks = shortlist.get("picks") or []
    eligible_legs: list[dict[str, Any]] = []
    rejected_legs: list[dict[str, Any]] = list(official_rejected)
    for pick in picks:
        leg, reason = _parlay_leg_from_pick(pick)
        if not leg:
            rejected_legs.append({"pick": pick.get("match") or {}, "reason": reason or "leg_unavailable"})
            continue
        if leg["action"] == "observe" and not allow_observe_legs:
            rejected_legs.append({"pick": leg.get("match") or {}, "reason": "observe_leg_not_allowed"})
            continue
        if leg["market_scope"] != "jingcai_supported" and not include_non_official_markets:
            rejected_legs.append({"pick": leg.get("match") or {}, "reason": "non_official_market_excluded"})
            continue
        eligible_legs.append(leg)

    max_leg_count = max(2, min(int(max_legs or 3), 4))
    tickets: list[dict[str, Any]] = []
    for leg_count in range(2, max_leg_count + 1):
        if len(eligible_legs) < leg_count:
            continue
        for combo in combinations(eligible_legs, leg_count):
            tickets.append(
                _build_parlay_ticket(
                    combo,
                    min_combined_edge=min_combined_edge,
                    parlay_mode=parlay_mode,
                    min_confidence_combined_odds_2=min_confidence_combined_odds_2,
                    min_confidence_combined_odds_3=min_confidence_combined_odds_3,
                )
            )

    if parlay_mode == "confidence":
        tickets.sort(
            key=lambda item: (
                {"parlay_recommended": 1, "single_bet_preferred": 0}.get(str(item.get("recommendation")), 0),
                parse_float(item.get("estimated_hit_probability")) or 0,
                parse_float(item.get("combined_decimal_odds")) or 0,
                parse_float(item.get("edge_proxy")) or -999,
                -len(item.get("risk_flags") or []),
            ),
            reverse=True,
        )
    else:
        tickets.sort(
            key=lambda item: (
                {"parlay_recommended": 1, "single_bet_preferred": 0}.get(str(item.get("recommendation")), 0),
                parse_float(item.get("edge_proxy")) or -999,
                parse_float(item.get("estimated_hit_probability")) or 0,
                -len(item.get("risk_flags") or []),
            ),
            reverse=True,
        )
    returned = tickets[: max(1, int(top_n or 3))]
    recommended_tickets = [ticket for ticket in tickets if ticket.get("recommendation") == "parlay_recommended"]
    risk_candidate_tickets = [ticket for ticket in tickets if ticket.get("recommendation") != "parlay_recommended"]
    single_bet_fallbacks = sorted(
        [_single_fallback_from_leg(leg) for leg in eligible_legs],
        key=lambda item: (
            parse_float(item.get("single_expected_multiplier")) or 0,
            parse_float(item.get("model_probability")) or 0,
        ),
        reverse=True,
    )[: max(1, int(top_n or 3))]
    recommendation_summary = _recommendation_summary(recommended_tickets, single_bet_fallbacks)
    confidence_thresholds = {
        "min_leg_model_probability": round_metric(min_confidence_leg_probability),
        "min_leg_decimal_odds": round_metric(min_confidence_decimal_odds),
        "max_leg_decimal_odds": round_metric(max_confidence_decimal_odds),
        "min_leg_edge": round_metric(min_confidence_edge, 4),
        "min_combined_decimal_odds_2": round_metric(min_confidence_combined_odds_2),
        "min_combined_decimal_odds_3": round_metric(min_confidence_combined_odds_3),
    }
    record = {
        "tool": "recommend_jingcai_parlay",
        "generated_at_utc": now_utc().isoformat(),
        "query": query or "",
        "league": league or "",
        "window_minutes": effective_window_minutes,
        "parlay_mode": parlay_mode,
        "confidence_thresholds": confidence_thresholds,
        "eligible_leg_count": len(eligible_legs),
        "returned_count": len(returned),
        "recommended_ticket_count": len(recommended_tickets),
        "tickets": returned,
        "recommendation_summary": recommendation_summary,
        "official_jingcai_source": official_jingcai_source,
    }
    log_result = _append_recommendation_log(record, recommendation_log_path)
    return {
        "status": "ok",
        "tool": "recommend_jingcai_parlay",
        "query": query or "",
        "league": league or "",
        "window_minutes": effective_window_minutes,
        "parlay_mode": parlay_mode,
        "confidence_thresholds": confidence_thresholds,
        "shortlist_summary": {
            "status": shortlist.get("status"),
            "total_candidates": shortlist.get("total_candidates"),
            "analyzed_count": shortlist.get("analyzed_count"),
            "eligible_single_count": len(picks),
        },
        "eligible_leg_count": len(eligible_legs),
        "rejected_leg_count": len(rejected_legs),
        "returned_count": len(returned),
        "recommended_ticket_count": len(recommended_tickets),
        "risk_candidate_ticket_count": len(risk_candidate_tickets),
        "official_jingcai_source": official_jingcai_source,
        "eligible_legs": eligible_legs,
        "rejected_legs": rejected_legs,
        "parlay_tickets": returned,
        "recommended_tickets": recommended_tickets[: max(1, int(top_n or 3))],
        "risk_candidate_tickets": risk_candidate_tickets[: max(1, int(top_n or 3))],
        "single_bet_fallbacks": single_bet_fallbacks,
        "recommendation_summary": recommendation_summary,
        "parlay_policy": {
            "supported_parlay_types": ["2串1", "3串1"] if max_leg_count >= 3 else ["2串1"],
            "default_window_rule": "Parlay uses a Jingcai day-style default window of next 24 hours; it is not limited to the live/near-kickoff 60-minute shortlist window unless the user explicitly asks.",
            "official_jingcai_rule": "Only 1x2 legs are marked jingcai_supported in this MCP because they map cleanly to 胜平负-style output.",
            "non_official_market_rule": "Asian handicap and over/under legs are excluded by default for Jingcai parlay. They are allowed only when include_non_official_markets=true and must not be described as official Jingcai odds.",
            "calculation_rule": "Combination odds and hit probability are calculated inside MCP from final_execution_advice and best_candidate fields.",
            "parlay_mode_rule": "Default confidence mode ranks by estimated hit probability first and may recommend high-probability low-odds official HAD parlays with small negative EV proxy; value mode requires the configured positive edge proxy.",
        },
        "recommendation_log": log_result,
        "agent_guidance": (
            "No recommended parlay ticket meets MCP risk thresholds; display recommendation_summary and single_bet_fallbacks first, then explain risk_candidate_tickets."
            if not recommended_tickets
            else "Use recommended_tickets as the only串单 conclusion. Display parlay_type, legs, combined_decimal_odds, "
            "estimated_hit_probability, edge_proxy, stake_level, and risk_flags. Do not build extra combinations outside MCP."
        ),
    }


def _learning_result_from_dongqiudi_row(row: dict[str, Any], source: dict[str, Any] | None = None) -> dict[str, Any] | None:
    status = str(row.get("status") or "").strip()
    left, right = _parse_score_pair(row)
    if left is None or right is None:
        return None
    if status and status not in {"Played", "After", "Finished", "Ended", "完场", "已结束"}:
        return None
    home = row.get("team_A") or {}
    away = row.get("team_B") or {}
    kickoff = parse_dongqiudi_kickoff(row.get("start_play"))
    return {
        "source": "dongqiudi",
        "source_evidence": source or row.get("_schedule_source") or {},
        "match_id": str(row.get("match_id") or ""),
        "league": ((row.get("competition") or {}).get("name") or ""),
        "home_team": home.get("name") or "",
        "away_team": away.get("name") or "",
        "kickoff_utc": kickoff.isoformat() if kickoff else None,
        "kickoff_utc_plus_8": kickoff.astimezone(DEFAULT_USER_TIMEZONE).isoformat() if kickoff else None,
        "home_score": int(left),
        "away_score": int(right),
        "status": status or "Played",
    }


_DONGQIUDI_FINAL_STATUSES = {"played", "after", "finished", "ended", "complete", "完场", "已结束"}
_DONGQIUDI_LIVE_STATUSES = {
    "playing",
    "live",
    "in progress",
    "1h",
    "2h",
    "half-time",
    "halftime",
    "进行中",
    "中场",
}
_DONGQIUDI_SCHEDULED_STATUSES = {"fixture", "not started", "scheduled", "未开始", "未开赛"}


def _dashboard_score_text(left: float | int | None, right: float | int | None) -> str:
    if left is None or right is None:
        return ""
    return f"{int(left)}-{int(right)}"


def _dongqiudi_match_state_from_sample(
    sample: dict[str, Any],
    source: dict[str, Any] | None = None,
    *,
    fallback_match_id: str = "",
) -> dict[str, Any] | None:
    if not isinstance(sample, dict) or not sample:
        return None
    raw_status = str(sample.get("status") or "").strip()
    normalized_status = raw_status.lower()
    left, right = _parse_score_pair(sample)
    score = _dashboard_score_text(left, right)
    minute = str(sample.get("minute") or "").strip()
    minute_period = str(sample.get("minute_period") or sample.get("period") or "").strip()
    period_label = {
        "1H": "上半场",
        "2H": "下半场",
        "HT": "中场",
        "ET": "加时",
        "P": "点球",
    }.get(minute_period, minute_period)
    if normalized_status in _DONGQIUDI_FINAL_STATUSES:
        phase = "final"
        label = "已完场待结算"
    elif normalized_status in _DONGQIUDI_LIVE_STATUSES or (minute and score):
        phase = "live"
        label = "比赛进行中"
    elif normalized_status in _DONGQIUDI_SCHEDULED_STATUSES:
        phase = "scheduled"
        label = "未开赛"
    else:
        phase = "unknown"
        label = "等待赛果"

    match_id = str(sample.get("match_id") or fallback_match_id or "").strip()
    return {
        "source": "dongqiudi",
        "source_evidence": source or {},
        "match_id": match_id,
        "phase": phase,
        "label": label,
        "status": raw_status,
        "minute": minute,
        "period": period_label,
        "score": score,
        "home_score": int(left) if left is not None else None,
        "away_score": int(right) if right is not None else None,
        "updated_at_utc": now_utc().isoformat(),
    }


def _learning_result_from_dongqiudi_detail(
    sample: dict[str, Any],
    source: dict[str, Any] | None = None,
    *,
    match_state: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    state = match_state or _dongqiudi_match_state_from_sample(sample, source)
    if not state or state.get("phase") != "final":
        return None
    if state.get("home_score") is None or state.get("away_score") is None:
        return None
    home = sample.get("team_A") or {}
    away = sample.get("team_B") or {}
    kickoff = parse_dongqiudi_kickoff(sample.get("start_play"))
    return {
        "source": "dongqiudi_detail",
        "source_evidence": source or {},
        "match_id": str(sample.get("match_id") or state.get("match_id") or ""),
        "league": ((sample.get("competition") or {}).get("name") or ""),
        "home_team": home.get("name") or "",
        "away_team": away.get("name") or "",
        "kickoff_utc": kickoff.isoformat() if kickoff else None,
        "kickoff_utc_plus_8": kickoff.astimezone(DEFAULT_USER_TIMEZONE).isoformat() if kickoff else None,
        "home_score": int(state["home_score"]),
        "away_score": int(state["away_score"]),
        "status": state.get("status") or "Played",
    }


async def _refresh_open_match_states_from_dongqiudi(
    *,
    db_path: str | None = None,
    limit: int = 120,
) -> dict[str, Any]:
    bounded_limit = max(1, min(int(limit or 120), 500))
    records = learning_store.list_recommendation_records(db_path=db_path, status="open", limit=bounded_limit)
    shadow_records = learning_store.list_shadow_prediction_records(db_path=db_path, status="open", limit=bounded_limit)
    match_ids: list[str] = []
    seen: set[str] = set()
    for record in [*records, *shadow_records]:
        match_id = str(record.get("match_id") or "").strip()
        if match_id and match_id not in seen:
            seen.add(match_id)
            match_ids.append(match_id)

    states: list[dict[str, Any]] = []
    final_results: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for match_id in match_ids:
        try:
            detail, source = await load_dongqiudi_detail(match_id)
        except Exception as exc:
            errors.append({"match_id": match_id, "error": f"{type(exc).__name__}: {exc}"})
            continue
        sample = (detail or {}).get("matchSample") or {}
        state = _dongqiudi_match_state_from_sample(sample, source, fallback_match_id=match_id)
        if not state:
            continue
        states.append(state)
        final_result = _learning_result_from_dongqiudi_detail(sample, source, match_state=state)
        if final_result:
            final_results.append(final_result)

    persisted = learning_store.update_open_match_states(states, db_path=db_path)
    return {
        "source": "dongqiudi_detail",
        "probed_count": len(match_ids),
        "state_count": len(states),
        "updated_count": persisted.get("updated_count", 0),
        "recommendation_count": persisted.get("recommendation_count", 0),
        "shadow_prediction_count": persisted.get("shadow_prediction_count", 0),
        "final_result_count": len(final_results),
        "results": final_results,
        "errors": errors,
    }


async def _fetch_learning_results_from_public_sources(
    *,
    as_of: str | None = None,
    timezone_name: str | None = None,
    days_back: int = 3,
    days_forward: int = 1,
) -> dict[str, Any]:
    as_of_dt = parse_as_of(as_of, timezone_name)
    fetched_results: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    start_day = as_of_dt.astimezone(DEFAULT_USER_TIMEZONE).replace(hour=0, minute=0, second=0, microsecond=0)
    for offset in range(-max(0, int(days_back or 0)), max(0, int(days_forward or 0)) + 1):
        local_day = start_day + timedelta(days=offset)
        try:
            rows, source = await load_dongqiudi_matches_for_date(local_day, tab_type="result")
            for row in rows:
                result = _learning_result_from_dongqiudi_row(row, source)
                if result:
                    fetched_results.append(result)
        except Exception as exc:
            errors.append({"date": local_day.date().isoformat(), "error": f"{type(exc).__name__}: {exc}"})
    return {
        "source": "dongqiudi_schedule_list",
        "fetched_count": len(fetched_results),
        "results": fetched_results,
        "errors": errors,
    }


async def settle_learning_recommendations(
    *,
    results: list[dict[str, Any]] | None = None,
    auto_fetch: bool = True,
    as_of: str | None = None,
    timezone_name: str | None = None,
    days_back: int = 3,
    days_forward: int = 1,
    db_path: str | None = None,
) -> dict[str, Any]:
    """Settle open paper recommendations with supplied scores and optional public-source scores."""
    supplied_results = list(results or [])
    fetched = {"source": "disabled", "fetched_count": 0, "results": [], "errors": []}
    match_state_refresh = {
        "source": "disabled",
        "probed_count": 0,
        "state_count": 0,
        "updated_count": 0,
        "final_result_count": 0,
        "results": [],
        "errors": [],
    }
    if auto_fetch:
        fetched = await _fetch_learning_results_from_public_sources(
            as_of=as_of,
            timezone_name=timezone_name,
            days_back=days_back,
            days_forward=days_forward,
        )
        match_state_refresh = await _refresh_open_match_states_from_dongqiudi(db_path=db_path)
    all_results = supplied_results + list(fetched.get("results") or []) + list(match_state_refresh.get("results") or [])
    # Mark stale open records as unsettleable so KPIs reflect reality
    unsettleable = learning_store.mark_unsettleable_stale_records(db_path=db_path)
    settlement = learning_store.settle_recommendations(all_results, db_path=db_path)
    shadow_settlement = learning_store.settle_shadow_predictions(all_results, db_path=db_path)
    calibration = learning_store.recompute_calibration(db_path=db_path)
    strategy_state = learning_store.update_strategy_state(db_path=db_path, market="asian_handicap", mode="balanced")
    shadow_prediction_metrics = learning_store.shadow_prediction_metrics(db_path=db_path)
    return {
        "status": "ok",
        "tool": "settle_learning_recommendations",
        "db_path": db_path or learning_store.learning_db_path(),
        "supplied_result_count": len(supplied_results),
        "auto_fetch": fetched,
        "match_state_refresh": match_state_refresh,
        "unsettleable_cleanup": unsettleable,
        "settlement": settlement,
        "shadow_settlement": shadow_settlement,
        "calibration": calibration,
        "strategy_state": strategy_state,
        "shadow_prediction_metrics": shadow_prediction_metrics,
    }


def _live_probability_bucket(value: float | None) -> str:
    if value is None:
        return "prob:unknown"
    start = math.floor(value / 0.05) * 0.05
    end = start + 0.05
    return f"prob:{start:.2f}-{end:.2f}"


def _live_odds_bucket(value: float | None) -> str:
    if value is None:
        return "odds:unknown"
    start = math.floor(value / 0.2) * 0.2
    end = start + 0.2
    return f"odds:{start:.2f}-{end:.2f}"


def _live_line_bucket(market: str, line: float | None) -> str:
    if line is None or market == "1x2":
        return "line:none"
    return f"line:{line:+g}"


def _live_bucket_match_score(bucket: dict[str, Any], *, pick: dict[str, Any], raw_probability: float | None) -> int | None:
    best = pick.get("best_candidate") or {}
    match = pick.get("match") or {}
    market = str(best.get("market") or "")
    if bucket.get("market") != market:
        return None

    score = 0
    league = str(match.get("league") or "")
    league_bucket = str(bucket.get("league_bucket") or "")
    if league_bucket == league and league:
        score += 12
    elif league_bucket == "ALL":
        score += 4
    else:
        return None

    line_bucket = str(bucket.get("line_bucket") or "")
    expected_line_bucket = _live_line_bucket(market, parse_float(best.get("line")))
    if line_bucket == expected_line_bucket:
        score += 8
    elif line_bucket == "line:ALL":
        score += 2
    else:
        return None

    odds_bucket = str(bucket.get("odds_bucket") or "")
    expected_odds_bucket = _live_odds_bucket(parse_float(best.get("decimal_odds")))
    if odds_bucket == expected_odds_bucket:
        score += 4
    elif odds_bucket == "odds:ALL":
        score += 1
    else:
        return None

    probability_bucket = str(bucket.get("probability_bucket") or "")
    expected_probability_bucket = _live_probability_bucket(raw_probability)
    if probability_bucket == expected_probability_bucket:
        score += 4
    elif probability_bucket == "prob:ALL":
        score += 1
    else:
        return None

    return score


def _smooth_live_probability(raw_probability: float | None, bucket: dict[str, Any], *, prior_strength: float) -> float | None:
    hit_count = parse_float(bucket.get("hit_count"))
    sample_count = parse_float(bucket.get("sample_count"))
    if hit_count is None or sample_count is None or sample_count <= 0:
        return raw_probability
    prior_probability = raw_probability
    if prior_probability is None:
        prior_probability = parse_float(bucket.get("avg_model_probability")) or parse_float(bucket.get("hit_rate"))
    if prior_probability is None:
        return parse_float(bucket.get("hit_rate"))
    return (hit_count + prior_strength * prior_probability) / (sample_count + prior_strength)


def _apply_live_calibration_to_picks(
    picks: list[dict[str, Any]],
    *,
    db_path: str | None = None,
    min_sample_count: int = 20,
    prior_strength: float = 20.0,
) -> list[dict[str, Any]]:
    status = learning_store.calibration_status(db_path=db_path, limit=2000)
    buckets = status.get("buckets") or []
    adjusted = []
    for pick in picks:
        best = pick.get("best_candidate") or {}
        confidence = pick.get("selection_confidence") or {}
        raw_probability = parse_float(confidence.get("calibrated_probability")) or parse_float(best.get("model_probability"))
        matching = []
        for bucket in buckets:
            sample_count = int(bucket.get("sample_count") or 0)
            if sample_count < min_sample_count:
                continue
            score = _live_bucket_match_score(bucket, pick=pick, raw_probability=raw_probability)
            if score is not None:
                matching.append((score, sample_count, bucket))
        best_bucket = max(matching, key=lambda item: (item[0], item[1]), default=None)
        if best_bucket:
            calibrated = _smooth_live_probability(raw_probability, best_bucket[2], prior_strength=prior_strength)
            source = "live_calibration_bucket"
            bucket = best_bucket[2]
        else:
            calibrated = raw_probability
            source = "insufficient_live_calibration_sample"
            bucket = None
        adjusted.append(
            {
                **pick,
                "live_calibration": {
                    "source": source,
                    "min_sample_count": min_sample_count,
                    "prior_strength": prior_strength,
                    "raw_probability": round_metric(raw_probability),
                    "adjusted_probability": round_metric(calibrated),
                    "bucket": bucket,
                    "rule": "Live calibration applies the most specific bucket with enough settled samples and shrinks empirical hit rate toward the raw model probability.",
                },
            }
        )
    return adjusted


def _learning_policy_for_shortlist(
    *,
    mode: str,
    target_market: str,
    use_learning_policy: bool,
    db_path: str | None = None,
) -> dict[str, Any]:
    if not use_learning_policy:
        return {"status": "disabled", "active": False, "reason": "use_learning_policy_false"}
    if mode != "balanced" or target_market != "asian_handicap":
        return {
            "status": "not_applicable",
            "active": False,
            "reason": "learning_policy_currently_targets_balanced_asian_handicap",
        }
    return learning_store.update_strategy_state(db_path=db_path, market="asian_handicap", mode="balanced")


def _apply_learning_policy_to_analysis(
    analysis: dict[str, Any],
    *,
    mode: str,
    learning_policy: dict[str, Any],
    db_path: str | None = None,
) -> dict[str, Any]:
    if not learning_policy.get("active"):
        return {**analysis, "learning_policy": learning_policy}
    try:
        temp_pick = _shortlist_pick_from_analysis(analysis, mode=mode)
        calibrated_pick = _apply_live_calibration_to_picks(
            [temp_pick],
            db_path=db_path,
            min_sample_count=int(learning_policy.get("min_live_sample_count") or 20),
            prior_strength=float(learning_policy.get("prior_strength") or 20.0),
        )[0]
    except Exception as exc:
        return {
            **analysis,
            "learning_policy": {
                **learning_policy,
                "application_error": f"{type(exc).__name__}: {exc}",
            },
        }

    live_calibration = calibrated_pick.get("live_calibration") or {}
    adjusted_probability = parse_float(live_calibration.get("adjusted_probability"))
    enriched_policy = {
        **learning_policy,
        "live_calibration": live_calibration,
    }
    if live_calibration.get("source") != "live_calibration_bucket" or adjusted_probability is None:
        return {**analysis, "learning_policy": enriched_policy}

    support = dict(analysis.get("betting_decision_support") or {})
    best = dict(analysis.get("best_candidate") or support.get("best_candidate") or {})
    original_probability = parse_float(best.get("calibrated_probability")) or parse_float(best.get("model_probability"))
    best.update(
        {
            "pre_learning_calibrated_probability": round_metric(original_probability),
            "calibrated_probability": round_metric(adjusted_probability),
            "learning_policy_applied": True,
        }
    )
    support["best_candidate"] = best
    return {
        **analysis,
        "best_candidate": best,
        "betting_decision_support": support,
        "learning_policy": enriched_policy,
    }


def _market_snapshot_sync_summary(result: dict[str, Any]) -> dict[str, Any]:
    leisu = (result.get("providers") or {}).get("leisu") or {}
    hard_flags: Counter[str] = Counter()
    soft_flags: Counter[str] = Counter()
    for item in result.get("matches") or []:
        hard_flags.update(str(flag) for flag in item.get("hard_flags") or [])
        soft_flags.update(str(flag) for flag in item.get("soft_flags") or [])

    snapshot_store_info = result.get("snapshot_store") or {}
    return {
        "enabled": True,
        "provider": "leisu",
        "status": result.get("status") or "unknown",
        "saved_snapshot_count": int(result.get("saved_snapshot_count") or 0),
        "generated_snapshot_count": int(result.get("generated_snapshot_count") or 0),
        "candidate_match_count": int(leisu.get("candidate_match_count") or 0),
        "probed_match_count": int(leisu.get("probed_match_count") or 0),
        "accessible_match_count": int(leisu.get("accessible_match_count") or 0),
        "promotable_match_count": int(leisu.get("promotable_match_count") or 0),
        "require_quality_gate": bool(leisu.get("require_quality_gate")),
        "hard_flags": [flag for flag, _count in hard_flags.most_common(5)],
        "soft_flags": [flag for flag, _count in soft_flags.most_common(5)],
        "db_path": snapshot_store_info.get("db_path") or snapshot_store.snapshot_db_path(),
        "at_utc": now_utc().isoformat(),
    }


def _reanalysis_as_of_for_record(record: dict[str, Any], explicit_as_of: str | None = None) -> str | None:
    if explicit_as_of:
        return explicit_as_of
    return now_utc().astimezone(DEFAULT_USER_TIMEZONE).isoformat()


def _record_minutes_to_kickoff(record: dict[str, Any], as_of_dt: datetime) -> float | None:
    raw_kickoff = str(record.get("kickoff_utc_plus_8") or record.get("kickoff_utc") or "").strip()
    if not raw_kickoff:
        return None
    try:
        kickoff = date_parser.parse(raw_kickoff)
    except (ValueError, TypeError, OverflowError):
        return None
    if kickoff.tzinfo is None:
        kickoff = kickoff.replace(tzinfo=DEFAULT_USER_TIMEZONE)
    return (kickoff.astimezone(timezone.utc) - as_of_dt.astimezone(timezone.utc)).total_seconds() / 60


def _snapshot_reanalysis_candidates(
    *,
    db_path: str | None = None,
    market_db_path: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    records = learning_store.list_recommendation_records(
        db_path=db_path,
        status="open",
        limit=max(1, min(int(limit or 20) * 8, 500)),
    )
    snapshot_coverage = snapshot_store.market_snapshot_coverage_for_records(records, db_path=market_db_path)
    candidates: list[dict[str, Any]] = []
    for record in records:
        if not _dashboard_is_observation(record):
            continue
        raw = record.get("raw") if isinstance(record.get("raw"), dict) else {}
        reason = str(raw.get("reason") or record.get("recommendation") or "")
        if (
            _dashboard_reconciled_rejection_reason(
                record,
                reason,
                snapshot_coverage=snapshot_coverage,
                market_db_path=market_db_path,
            )
            != "awaiting_reanalysis_after_snapshot"
        ):
            continue
        candidates.append(record)
        if len(candidates) >= max(1, int(limit or 20)):
            break
    return candidates


def _snapshot_reanalysis_thresholds(learning_policy: dict[str, Any]) -> dict[str, float]:
    min_probability = max(0.58, parse_float(learning_policy.get("min_calibrated_probability")) or 0.58)
    min_decimal_odds = max(1.65, parse_float(learning_policy.get("min_decimal_odds")) or 1.65)
    max_decimal_odds = parse_float(learning_policy.get("max_decimal_odds"))
    if max_decimal_odds is None:
        max_decimal_odds = 2.05
    else:
        max_decimal_odds = min(2.05, max(min_decimal_odds, max_decimal_odds))
    min_value_edge = max(0.02, parse_float(learning_policy.get("min_value_edge")) or 0.02)
    return {
        "min_calibrated_probability": min_probability,
        "min_decimal_odds": min_decimal_odds,
        "max_decimal_odds": max_decimal_odds,
        "min_value_edge": min_value_edge,
    }


def _snapshot_reanalysis_record_item(
    record: dict[str, Any],
    *,
    run_id: str,
    query: str,
    targeted_analysis: dict[str, Any],
    reason: str | None,
    learning_policy: dict[str, Any],
) -> dict[str, Any]:
    previous_raw = record.get("raw") if isinstance(record.get("raw"), dict) else {}
    previous_reason = str(previous_raw.get("reason") or record.get("recommendation") or "")
    if reason:
        support = targeted_analysis.get("betting_decision_support") or {}
        payload = {
            "match": targeted_analysis.get("match") or (targeted_analysis.get("agent_brief") or {}).get("match") or {},
            "match_context": targeted_analysis.get("match_context") or {},
            "query": query,
            "reason": reason,
            "model_engine": _compact_model_engine_evidence(targeted_analysis),
            "best_candidate": targeted_analysis.get("best_candidate") or support.get("best_candidate") or {},
            "blocking_flags": support.get("blocking_flags") or [],
            "quality": targeted_analysis.get("quality") or {},
            "data_completeness": _shortlist_coverage_score(targeted_analysis),
            "learning_policy": targeted_analysis.get("learning_policy") or learning_policy,
            "caution_flags": support.get("caution_flags") or [],
        }
        return {
            "record_key": record.get("record_key"),
            "match": payload["match"],
            "best_candidate": payload["best_candidate"],
            "run_id": run_id,
            "tool": "snapshot_reanalysis",
            "mode": "balanced_observation",
            "target_market": "asian_handicap",
            "caution_flags": payload["caution_flags"],
            "raw": {
                "kind": "snapshot_reanalysis",
                "previous_record_id": record.get("id"),
                "previous_reason": previous_reason,
                "result": "still_observation",
                **payload,
            },
        }

    pick = _shortlist_pick_from_analysis(targeted_analysis, mode="balanced")
    return {
        **pick,
        "record_key": record.get("record_key"),
        "run_id": run_id,
        "tool": "snapshot_reanalysis",
        "mode": "balanced",
        "target_market": "asian_handicap",
        "raw": {
            "kind": "snapshot_reanalysis",
            "previous_record_id": record.get("id"),
            "previous_reason": previous_reason,
            "result": "formal_promoted",
            **pick,
        },
    }


def _snapshot_reanalysis_update_blocker(analysis: dict[str, Any]) -> str:
    if analysis.get("status") != "ok":
        return "analysis_failed"
    match = analysis.get("match") or (analysis.get("agent_brief") or {}).get("match") or {}
    home_team = str(match.get("home_team") or "").strip()
    away_team = str(match.get("away_team") or "").strip()
    if not home_team or not away_team:
        return "match_identity_missing"
    support = analysis.get("betting_decision_support") or {}
    best = analysis.get("best_candidate") or support.get("best_candidate") or {}
    if not best:
        return "market_candidate_missing"
    if str(best.get("market") or analysis.get("_shortlist_target_market") or "") != "asian_handicap":
        return "target_market_missing"
    return ""


async def reanalyze_snapshot_backlog(
    *,
    as_of: str | None = None,
    timezone_name: str | None = None,
    limit: int = 20,
    concurrency: int = 4,
    db_path: str | None = None,
    market_db_path: str | None = None,
) -> dict[str, Any]:
    """Re-run open paper predictions whose required odds snapshots have since arrived."""
    bounded_limit = max(1, min(int(limit or 20), 100))
    bounded_concurrency = max(1, min(int(concurrency or 4), 10))
    candidates = _snapshot_reanalysis_candidates(
        db_path=db_path,
        market_db_path=market_db_path,
        limit=bounded_limit,
    )
    learning_policy = _learning_policy_for_shortlist(
        mode="balanced",
        target_market="asian_handicap",
        use_learning_policy=True,
        db_path=db_path,
    )
    thresholds = _snapshot_reanalysis_thresholds(learning_policy)
    run_id = learning_store.make_run_id("snapshot-reanalysis")
    reanalysis_as_of_dt = parse_as_of(as_of, timezone_name or "Asia/Shanghai")

    async def reanalyze_one(record: dict[str, Any]) -> dict[str, Any]:
        minutes_to_kickoff = _record_minutes_to_kickoff(record, reanalysis_as_of_dt)
        if minutes_to_kickoff is not None and not (0 <= minutes_to_kickoff <= 10):
            return {
                "record_id": record.get("id"),
                "ledger_id": f"recommendation:{record.get('id')}",
                "status": "skipped",
                "reason": "outside_near_kickoff_window",
                "minutes_to_kickoff": round_metric(minutes_to_kickoff, 2),
            }
        match = {
            "home_team": record.get("home_team") or "",
            "away_team": record.get("away_team") or "",
            "league": record.get("league") or "",
        }
        query = _shortlist_match_query(match)
        if not query:
            return {"record_id": record.get("id"), "status": "failed", "reason": "match_query_missing"}
        try:
            analysis = await analyze_single_match(
                query,
                home_team=str(record.get("home_team") or ""),
                away_team=str(record.get("away_team") or ""),
                league=str(record.get("league") or ""),
                as_of=_reanalysis_as_of_for_record(record, as_of),
                timezone_name=timezone_name or "Asia/Shanghai",
                window_hours=1,
                include_source_probe=False,
            )
            targeted_analysis = _shortlist_analysis_for_target_market(analysis, "asian_handicap")
            targeted_analysis = _apply_learning_policy_to_analysis(
                targeted_analysis,
                mode="balanced",
                learning_policy=learning_policy,
                db_path=db_path,
            )
            update_blocker = _snapshot_reanalysis_update_blocker(targeted_analysis)
            if update_blocker:
                return {
                    "record_id": record.get("id"),
                    "ledger_id": f"recommendation:{record.get('id')}",
                    "status": "failed",
                    "reason": update_blocker,
                    "query": query,
                }
            reason = _shortlist_rejection_reason(
                targeted_analysis,
                min_edge=0.01,
                require_core_markets=True,
                mode="balanced",
                min_calibrated_probability=thresholds["min_calibrated_probability"],
                min_decimal_odds=thresholds["min_decimal_odds"],
                max_decimal_odds=thresholds["max_decimal_odds"],
                min_value_edge=thresholds["min_value_edge"],
            )
            item = _snapshot_reanalysis_record_item(
                record,
                run_id=run_id,
                query=query,
                targeted_analysis=targeted_analysis,
                reason=reason,
                learning_policy=learning_policy,
            )
            updated = learning_store.update_open_recommendation_record(record.get("id"), item, db_path=db_path)
            return {
                "record_id": record.get("id"),
                "ledger_id": f"recommendation:{record.get('id')}",
                "status": "updated" if updated else "skipped",
                "result": "still_observation" if reason else "formal_promoted",
                "reason": reason or "",
                "query": query,
            }
        except Exception as exc:
            return {
                "record_id": record.get("id"),
                "ledger_id": f"recommendation:{record.get('id')}",
                "status": "failed",
                "reason": f"{type(exc).__name__}: {exc}",
                "query": query,
            }

    semaphore = asyncio.Semaphore(bounded_concurrency)

    async def run_limited(record: dict[str, Any]) -> dict[str, Any]:
        async with semaphore:
            return await reanalyze_one(record)

    results = list(await asyncio.gather(*(run_limited(record) for record in candidates))) if candidates else []
    formal_promoted_count = sum(1 for item in results if item.get("result") == "formal_promoted" and item.get("status") == "updated")
    still_observation_count = sum(1 for item in results if item.get("result") == "still_observation" and item.get("status") == "updated")
    failed_count = sum(1 for item in results if item.get("status") == "failed")
    skipped_count = sum(1 for item in results if item.get("status") == "skipped")
    return {
        "status": "ok",
        "tool": "reanalyze_snapshot_backlog",
        "run_id": run_id,
        "candidate_count": len(candidates),
        "reanalyzed_count": sum(1 for item in results if item.get("status") == "updated"),
        "formal_promoted_count": formal_promoted_count,
        "still_observation_count": still_observation_count,
        "failed_count": failed_count,
        "skipped_count": skipped_count,
        "limit": bounded_limit,
        "concurrency": bounded_concurrency,
        "thresholds": {key: round_metric(value, 4) for key, value in thresholds.items()},
        "results": results,
        "at_utc": now_utc().isoformat(),
    }


async def run_auto_learning_cycle(
    *,
    query: str = "",
    league: str | None = None,
    as_of: str | None = None,
    timezone_name: str | None = None,
    asian_window_minutes: int = 10,
    parlay_window_minutes: int = 10,
    top_n: int = 3,
    limit: int = 30,
    include_asian_shortlist: bool = True,
    include_jingcai_parlay: bool = True,
    include_learning_observations: bool = True,
    learning_observation_limit: int = 30,
    include_shadow_predictions: bool = True,
    shadow_prediction_limit: int = 100,
    analysis_candidate_limit: int = 80,
    analysis_concurrency: int = 10,
    auto_settle: bool = True,
    include_market_snapshot_sync: bool = False,
    market_snapshot_window_minutes: int | None = 24 * 60,
    market_snapshot_limit: int = 80,
    market_snapshot_concurrency: int = 4,
    market_snapshot_require_quality_gate: bool = True,
    include_snapshot_reanalysis: bool = True,
    snapshot_reanalysis_limit: int = 20,
    snapshot_reanalysis_concurrency: int = 4,
    enforce_settlement_coverage: bool = True,
    league_allowlist: list[str] | frozenset[str] | None = None,
    db_path: str | None = None,
) -> dict[str, Any]:
    """Run one paper-learning loop: recommend, persist, optionally settle, then refresh calibration."""
    run_id = learning_store.make_run_id("auto-learning")
    saved_record_count = 0
    saved_shadow_prediction_count = 0
    asian_summary: dict[str, Any] = {"enabled": include_asian_shortlist, "record_count": 0}
    parlay_summary: dict[str, Any] = {"enabled": include_jingcai_parlay, "record_count": 0}
    bounded_shadow_prediction_limit = max(0, min(int(shadow_prediction_limit or 0), 500))
    bounded_analysis_candidate_limit = max(1, min(int(analysis_candidate_limit or 80), 100))
    bounded_analysis_concurrency = max(1, min(int(analysis_concurrency or 10), 16))
    bounded_market_snapshot_window = max(
        1,
        min(int(market_snapshot_window_minutes or 24 * 60), 48 * 60),
    )
    bounded_market_snapshot_limit = max(1, min(int(market_snapshot_limit or 80), 100))
    bounded_market_snapshot_concurrency = max(1, min(int(market_snapshot_concurrency or 4), 10))
    market_snapshot_sync: dict[str, Any] = {
        "enabled": False,
        "provider": "leisu",
        "status": "disabled",
        "saved_snapshot_count": 0,
        "generated_snapshot_count": 0,
    }
    snapshot_reanalysis: dict[str, Any] = {
        "enabled": bool(include_snapshot_reanalysis),
        "status": "disabled" if not include_snapshot_reanalysis else "not_started",
        "reanalyzed_count": 0,
        "formal_promoted_count": 0,
        "still_observation_count": 0,
        "failed_count": 0,
    }

    if include_asian_shortlist:
        AUTO_LEARNING_STATE["current_step"] = "asian_shortlist"
        asian_result = await shortlist_value_matches(
            query=query or "",
            league=league,
            as_of=as_of,
            timezone_name=timezone_name,
            window_minutes=asian_window_minutes,
            top_n=top_n,
            limit=limit,
            mode="balanced",
            target_market="asian_handicap",
            require_core_markets=True,
            analysis_candidate_limit=bounded_analysis_candidate_limit,
            analysis_concurrency=bounded_analysis_concurrency,
            recommendation_log_path=None,
            enforce_settlement_coverage=enforce_settlement_coverage,
            league_allowlist=league_allowlist,
            db_path=db_path,
        )
        asian_records = learning_store.build_records_from_shortlist(asian_result, run_id=run_id)
        saved_record_count += learning_store.save_recommendation_records(asian_records, db_path=db_path)
        shadow_prediction_records = []
        if include_shadow_predictions:
            shadow_prediction_records = learning_store.build_shadow_prediction_records_from_shortlist(
                asian_result,
                run_id=run_id,
                limit=bounded_shadow_prediction_limit,
            )
            saved_shadow_prediction_count += learning_store.save_shadow_prediction_records(
                shadow_prediction_records,
                db_path=db_path,
            )
        learning_observation_records = []
        if include_learning_observations:
            learning_observation_records = learning_store.build_learning_observation_records_from_shortlist(
                asian_result,
                run_id=run_id,
                limit=learning_observation_limit,
            )
            saved_record_count += learning_store.save_recommendation_records(learning_observation_records, db_path=db_path)
        calibrated_picks = _apply_live_calibration_to_picks(asian_result.get("picks") or [], db_path=db_path)
        calibrated_picks.sort(
            key=lambda item: (
                parse_float((item.get("live_calibration") or {}).get("adjusted_probability")) or 0.0,
                parse_float((item.get("selection_confidence") or {}).get("expected_return")) or 0.0,
                parse_float((item.get("selection_confidence") or {}).get("balanced_score")) or 0.0,
            ),
            reverse=True,
        )
        asian_summary = {
            "enabled": True,
            "status": asian_result.get("status"),
            "record_count": len(asian_records),
            "learning_observation_record_count": len(learning_observation_records),
            "shadow_prediction_record_count": len(shadow_prediction_records),
            "saved_shadow_prediction_count": saved_shadow_prediction_count,
            "total_candidates": asian_result.get("total_candidates"),
            "analyzed_count": asian_result.get("analyzed_count"),
            "not_analyzed_count": asian_result.get("not_analyzed_count"),
            "eligible_count": asian_result.get("eligible_count"),
            "returned_count": asian_result.get("returned_count"),
            "rejected_count": asian_result.get("rejected_count"),
            "funnel_report": asian_result.get("funnel_report") or {},
            "target_market": asian_result.get("target_market"),
            "mode": asian_result.get("mode"),
            "picks": calibrated_picks,
        }

    if include_jingcai_parlay:
        AUTO_LEARNING_STATE["current_step"] = "jingcai_parlay"
        parlay_result = await recommend_jingcai_parlay(
            query=query or "",
            league=league,
            as_of=as_of,
            timezone_name=timezone_name,
            window_minutes=parlay_window_minutes,
            top_n=top_n,
            limit=limit,
            max_legs=3,
            parlay_mode="confidence",
            include_non_official_markets=False,
        )
        parlay_records = learning_store.build_records_from_parlay(parlay_result, run_id=run_id)
        saved_record_count += learning_store.save_recommendation_records(parlay_records, db_path=db_path)
        parlay_summary = {
            "enabled": True,
            "status": parlay_result.get("status"),
            "record_count": len(parlay_records),
            "eligible_leg_count": parlay_result.get("eligible_leg_count"),
            "recommended_ticket_count": parlay_result.get("recommended_ticket_count"),
            "recommended_tickets": parlay_result.get("recommended_tickets") or [],
        }

    if include_market_snapshot_sync:
        AUTO_LEARNING_STATE["current_step"] = "market_snapshot_sync"
        try:
            market_snapshot_sync = _market_snapshot_sync_summary(
                await sync_leisu_odds_snapshots(
                    as_of=as_of,
                    timezone_name=timezone_name,
                    window_minutes=bounded_market_snapshot_window,
                    limit=bounded_market_snapshot_limit,
                    concurrency=bounded_market_snapshot_concurrency,
                    require_quality_gate=market_snapshot_require_quality_gate,
                )
            )
            AUTO_LEARNING_STATE["last_market_snapshot_sync"] = market_snapshot_sync
        except Exception as exc:
            market_snapshot_sync = {
                "enabled": True,
                "provider": "leisu",
                "status": "error",
                "saved_snapshot_count": 0,
                "generated_snapshot_count": 0,
                "error": f"{type(exc).__name__}: {exc}",
                "db_path": snapshot_store.snapshot_db_path(),
                "at_utc": now_utc().isoformat(),
            }
            AUTO_LEARNING_STATE["last_market_snapshot_sync"] = market_snapshot_sync

    if include_snapshot_reanalysis:
        AUTO_LEARNING_STATE["current_step"] = "snapshot_reanalysis"
        try:
            snapshot_reanalysis = {
                "enabled": True,
                **(
                    await reanalyze_snapshot_backlog(
                        as_of=as_of,
                        timezone_name=timezone_name,
                        limit=snapshot_reanalysis_limit,
                        concurrency=snapshot_reanalysis_concurrency,
                        db_path=db_path,
                    )
                ),
            }
            AUTO_LEARNING_STATE["last_snapshot_reanalysis"] = snapshot_reanalysis
        except Exception as exc:
            snapshot_reanalysis = {
                "enabled": True,
                "status": "error",
                "reanalyzed_count": 0,
                "formal_promoted_count": 0,
                "still_observation_count": 0,
                "failed_count": 0,
                "error": f"{type(exc).__name__}: {exc}",
                "at_utc": now_utc().isoformat(),
            }
            AUTO_LEARNING_STATE["last_snapshot_reanalysis"] = snapshot_reanalysis

    settlement = None
    if auto_settle:
        AUTO_LEARNING_STATE["current_step"] = "settlement"
        settlement = await settle_learning_recommendations(
            auto_fetch=True,
            as_of=as_of,
            timezone_name=timezone_name,
            db_path=db_path,
        )
        calibration = settlement.get("calibration") or {}
        strategy_state = settlement.get("strategy_state") or {}
    else:
        calibration = learning_store.recompute_calibration(db_path=db_path)
        strategy_state = learning_store.update_strategy_state(db_path=db_path, market="asian_handicap", mode="balanced")
    AUTO_LEARNING_STATE["current_step"] = "idle"
    shadow_prediction_metrics = learning_store.shadow_prediction_metrics(db_path=db_path)
    learning_phase = "collecting_samples"
    if int((calibration or {}).get("settled_count") or 0) >= 20:
        learning_phase = "live_calibration_active"

    return {
        "status": "ok",
        "tool": "run_auto_learning_cycle",
        "run_id": run_id,
        "db_path": db_path or learning_store.learning_db_path(),
        "saved_record_count": saved_record_count,
        "saved_shadow_prediction_count": saved_shadow_prediction_count,
        "asian_shortlist": asian_summary,
        "jingcai_parlay": parlay_summary,
        "market_snapshot_sync": market_snapshot_sync,
        "snapshot_reanalysis": snapshot_reanalysis,
        "settlement": settlement,
        "calibration": calibration,
        "strategy_state": strategy_state,
        "shadow_prediction_metrics": shadow_prediction_metrics,
        "learning_phase": learning_phase,
        "safety_policy": "Paper-learning only. This loop records recommendations and outcomes; it never places real-money bets.",
    }


def learning_calibration_status(*, db_path: str | None = None, limit: int = 50) -> dict[str, Any]:
    status = learning_store.calibration_status(db_path=db_path, limit=limit)
    return {
        **status,
        "auto_learning_state": dict(AUTO_LEARNING_STATE),
        "shadow_prediction_metrics": learning_store.shadow_prediction_metrics(db_path=db_path, limit=max(limit or 50, 2000)),
        "trust_policy": (
            "Use live calibration only after broad buckets have enough settled samples. "
            "Before that, recommendations are still model-ranked paper signals, not verified profitable edges."
        ),
    }


def _dashboard_is_observation(record: dict[str, Any]) -> bool:
    raw = record.get("raw") or {}
    return "_observation" in str(record.get("mode") or "") or raw.get("kind") == "learning_observation"


def _dashboard_matchup(record: dict[str, Any]) -> str:
    return f"{record.get('home_team') or ''} vs {record.get('away_team') or ''}".strip()


def _dashboard_record_has_display_match(record: dict[str, Any]) -> bool:
    return bool(str(record.get("home_team") or "").strip() and str(record.get("away_team") or "").strip())


def _dashboard_logo_url(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text.startswith("//"):
        return f"https:{text}"
    if text.startswith(("http://", "https://")):
        return text
    return ""


def _ensure_fdo_index_warm() -> None:
    """Warm the FDO team enrichment index in a background-safe way."""
    try:
        from football_data_mcp.data_sources_registry import (
            build_fdo_team_index,
            _FDO_TEAM_INDEX_BUILT_AT,
            _FDO_TEAM_INDEX_TTL,
        )
    except ImportError:
        return
    if time.time() - _FDO_TEAM_INDEX_BUILT_AT < _FDO_TEAM_INDEX_TTL:
        return  # still fresh
    import asyncio as _aio
    try:
        try:
            loop = _aio.get_running_loop()
            # Already in async context: schedule and forget
            loop.create_task(build_fdo_team_index())
        except RuntimeError:
            # No loop running: run sync
            _aio.run(build_fdo_team_index())
    except Exception:
        pass  # silent — enrichment is best-effort


# ─── Dongqiudi team logo index ────────────────────────────────────────────────
# Cumulative team-name → logo URL map, persisted across daemon runs so historical
# records can be enriched with logos that were learned from any past listing.
_DONGQIUDI_TEAM_LOGO_CACHE: dict[str, str] = {}
_DONGQIUDI_LOGO_CACHE_BUILT_AT: float = 0.0
_DONGQIUDI_LOGO_CACHE_TTL = 600.0  # rebuild from listings every 10 min


async def _refresh_dongqiudi_team_logo_cache() -> dict[str, Any]:
    """Walk recent dongqiudi listings and accumulate (team_name → logo_url) pairs."""
    global _DONGQIUDI_LOGO_CACHE_BUILT_AT
    try:
        as_of_dt = now_utc()
        # Past 3 days + next 2 days
        from datetime import timedelta as _td
        learned = 0
        for offset in range(-3, 3):
            local_day = as_of_dt + _td(days=offset)
            try:
                rows, _src = await load_dongqiudi_matches_for_date(local_day, tab_type="fixture")
            except Exception:
                rows = []
            try:
                rows_r, _src = await load_dongqiudi_matches_for_date(local_day, tab_type="result")
            except Exception:
                rows_r = []
            for row in rows + rows_r:
                for side in ("team_A", "team_B"):
                    t = row.get(side) or {}
                    name = (t.get("name") or "").strip()
                    logo = (t.get("logo") or "").strip()
                    if name and logo and name not in _DONGQIUDI_TEAM_LOGO_CACHE:
                        _DONGQIUDI_TEAM_LOGO_CACHE[name] = logo
                        learned += 1
        _DONGQIUDI_LOGO_CACHE_BUILT_AT = time.time()
        return {"status": "ok", "learned": learned, "total_cached": len(_DONGQIUDI_TEAM_LOGO_CACHE)}
    except Exception as exc:
        return {"status": "error", "error": f"{type(exc).__name__}: {exc}"}


def _ensure_dongqiudi_logo_cache_warm() -> None:
    """Refresh dongqiudi team-logo cache when stale (best-effort, non-blocking)."""
    if time.time() - _DONGQIUDI_LOGO_CACHE_BUILT_AT < _DONGQIUDI_LOGO_CACHE_TTL:
        return
    import asyncio as _aio
    try:
        try:
            loop = _aio.get_running_loop()
            loop.create_task(_refresh_dongqiudi_team_logo_cache())
        except RuntimeError:
            _aio.run(_refresh_dongqiudi_team_logo_cache())
    except Exception:
        pass


def _dashboard_dongqiudi_logo_fallback(record: dict[str, Any], side: str) -> str:
    """Look up a team's logo from the cumulative dongqiudi cache."""
    team_name = (record.get(f"{side}_team") or "").strip()
    if not team_name:
        return ""
    return _DONGQIUDI_TEAM_LOGO_CACHE.get(team_name, "")


def _dashboard_fdo_logo_fallback(record: dict[str, Any], side: str) -> str:
    """If FDO index has this team, use its crest URL. Falls back to '' silently."""
    try:
        from football_data_mcp.data_sources_registry import lookup_fdo_enrichment
    except ImportError:
        return ""
    home_team = record.get("home_team") or ""
    away_team = record.get("away_team") or ""
    kickoff = record.get("kickoff_utc") or record.get("kickoff_utc_plus_8") or ""
    enrichment = lookup_fdo_enrichment(home_team, away_team, kickoff)
    if not enrichment:
        return ""
    return enrichment.get(f"{side}_team_logo_url") or ""


def _dashboard_team_logo_url(record: dict[str, Any], side: str) -> str:
    raw = record.get("raw") if isinstance(record.get("raw"), dict) else {}
    paths = (
        (f"{side}_team_logo_url",),
        (f"{side}_logo_url",),
        (f"{side}_team_logo",),
        (f"{side}_logo",),
        ("team_logos", side),
        ("logos", side),
        ("match", f"{side}_team_logo_url"),
        ("match", f"{side}_logo_url"),
        ("match", f"{side}_team_logo"),
        ("match", f"{side}_logo"),
        ("fixture", f"{side}_team_logo_url"),
        ("fixture", f"{side}_logo_url"),
        ("fixture", f"{side}_team_logo"),
        ("match_context", "fixture", f"{side}_team_logo_url"),
        ("match_context", "fixture", f"{side}_logo_url"),
        ("match_context", "teams", side, "logo_url"),
        ("match_context", "teams", side, "logo"),
        ("match_context", "teams", side, "crest"),
        ("match_context", "teams", side, "image_path"),
        ("context", "fixture", f"{side}_team_logo_url"),
        ("context", "fixture", f"{side}_logo_url"),
        ("context", "teams", side, "logo_url"),
        ("context", "teams", side, "logo"),
        ("context", "teams", side, "crest"),
        ("context", "teams", side, "image_path"),
    )
    for path in paths:
        logo_url = _dashboard_logo_url(_dashboard_get_path(record, path))
        if logo_url:
            return logo_url
        logo_url = _dashboard_logo_url(_dashboard_get_path(raw, path))
        if logo_url:
            return logo_url
    # Fallback 1: cumulative dongqiudi team-logo cache (Chinese team names)
    dq_url = _dashboard_dongqiudi_logo_fallback(record, side)
    if dq_url:
        return dq_url
    # Fallback 2: football-data.org enrichment index (English team names)
    fdo_url = _dashboard_fdo_logo_fallback(record, side)
    if fdo_url:
        return fdo_url
    return ""


def _dashboard_probability(record: dict[str, Any]) -> float | None:
    return parse_float(record.get("calibrated_probability")) or parse_float(record.get("model_probability"))


def _dashboard_governed_probability(
    record: dict[str, Any],
    probability_governance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    active_source = str((probability_governance or {}).get("active_probability_source") or "learned_probability")
    source_labels = {
        "learned_probability": "学习校准",
        "model_probability": "原始模型",
        "market_probability": "市场基准",
        "learned_market_blend": "学习/市场混合",
    }

    def value_for(source: str) -> float | None:
        if source == "learned_probability":
            return _dashboard_probability(record)
        if source == "model_probability":
            return parse_float(record.get("model_probability"))
        if source == "market_probability":
            return parse_float(record.get("market_probability"))
        if source == "learned_market_blend":
            learned = _dashboard_probability(record)
            market = parse_float(record.get("market_probability"))
            if learned is not None and market is not None:
                return (learned + market) / 2
            return learned if learned is not None else market
        return _dashboard_probability(record)

    probability = value_for(active_source)
    source = active_source
    fallback = False
    if probability is None:
        for fallback_source in ("learned_probability", "model_probability", "market_probability"):
            probability = value_for(fallback_source)
            if probability is not None:
                source = fallback_source
                fallback = True
                break
    return {
        "probability": max(0.0, min(1.0, probability)) if probability is not None else None,
        "source": source,
        "label": source_labels.get(source, source or "概率来源"),
        "fallback": fallback,
    }


def _dashboard_record_data_block_state(record: dict[str, Any], key: str) -> bool | None:
    raw = record.get("raw") if isinstance(record.get("raw"), dict) else {}
    completeness = raw.get("data_completeness") or raw.get("data_coverage") or {}
    if not isinstance(completeness, dict):
        return None

    blocks = completeness.get("blocks") or {}
    if isinstance(blocks, dict) and key in blocks:
        return bool(blocks.get(key))

    missing_blocks = completeness.get("missing_blocks") or []
    if isinstance(missing_blocks, list) and key in missing_blocks:
        return False

    available_blocks = completeness.get("available_blocks") or []
    if isinstance(available_blocks, list) and key in available_blocks:
        return True
    return None


def _dashboard_record_caution_flags(record: dict[str, Any]) -> set[str]:
    raw = record.get("raw") if isinstance(record.get("raw"), dict) else {}
    flags = {str(flag) for flag in record.get("caution_flags") or []}
    flags.update(str(flag) for flag in raw.get("caution_flags") or [])
    support = raw.get("betting_decision_support") or {}
    if isinstance(support, dict):
        flags.update(str(flag) for flag in support.get("caution_flags") or [])
    return flags


def _dashboard_snapshot_coverage_for_record(
    record: dict[str, Any],
    *,
    snapshot_coverage: dict[str, dict[str, Any]] | None = None,
    market_db_path: str | None = None,
) -> dict[str, Any]:
    coverage_key = snapshot_store.market_snapshot_match_key(
        str(record.get("home_team") or ""),
        str(record.get("away_team") or ""),
    )
    odds_coverage = (snapshot_coverage or {}).get(coverage_key) or {}
    if odds_coverage:
        return odds_coverage
    if snapshot_coverage is not None:
        return {}
    return snapshot_store.market_snapshot_coverage_for_match(
        str(record.get("home_team") or ""),
        str(record.get("away_team") or ""),
        league=str(record.get("league") or ""),
        db_path=market_db_path,
    )


def _dashboard_has_current_snapshot(
    record: dict[str, Any],
    *,
    snapshot_coverage: dict[str, dict[str, Any]] | None = None,
    market_db_path: str | None = None,
) -> bool:
    coverage = _dashboard_snapshot_coverage_for_record(
        record,
        snapshot_coverage=snapshot_coverage,
        market_db_path=market_db_path,
    )
    return int(coverage.get("snapshot_count") or 0) > 0


def _dashboard_reconciled_rejection_reason(
    record: dict[str, Any],
    reason: str,
    *,
    snapshot_coverage: dict[str, dict[str, Any]] | None = None,
    market_db_path: str | None = None,
) -> str:
    if str(record.get("settlement_status") or "open") != "open":
        return reason
    if reason == "multi_bookmaker_snapshot_missing" and _dashboard_has_current_snapshot(
        record,
        snapshot_coverage=snapshot_coverage,
        market_db_path=market_db_path,
    ):
        return "awaiting_reanalysis_after_snapshot"
    return reason


def _dashboard_open_pick_policy_rejection(
    record: dict[str, Any],
    *,
    snapshot_coverage: dict[str, dict[str, Any]] | None = None,
    market_db_path: str | None = None,
) -> str | None:
    if record.get("market") != "asian_handicap" or _dashboard_is_observation(record):
        return None

    line = parse_float(record.get("line"))
    if line is not None and abs(line) >= 2.0:
        return "large_handicap_requires_backtest"

    if _dashboard_record_data_block_state(record, "multi_bookmaker_snapshot") is False and not _dashboard_has_current_snapshot(
        record,
        snapshot_coverage=snapshot_coverage,
        market_db_path=market_db_path,
    ):
        return "multi_bookmaker_snapshot_missing"

    caution_flags = _dashboard_record_caution_flags(record)
    if (
        _dashboard_record_data_block_state(record, "lineup") is False
        or {"lineup_unavailable", "lineup_context_limited"} & caution_flags
    ):
        return "lineup_context_missing"
    return None


def _dashboard_record_row(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": record.get("id"),
        "league": record.get("league") or "",
        "matchup": _dashboard_matchup(record),
        "home_team": record.get("home_team") or "",
        "away_team": record.get("away_team") or "",
        "home_team_logo_url": _dashboard_team_logo_url(record, "home"),
        "away_team_logo_url": _dashboard_team_logo_url(record, "away"),
        "kickoff_utc_plus_8": record.get("kickoff_utc_plus_8") or "",
        "market": record.get("market") or "",
        "selection": record.get("selection") or "",
        "selection_key": record.get("selection_key") or "",
        "line": round_metric(parse_float(record.get("line")), 4),
        "decimal_odds": round_metric(parse_float(record.get("decimal_odds")), 4),
        "model_probability": round_metric(parse_float(record.get("model_probability"))),
        "learned_probability": round_metric(_dashboard_probability(record)),
        "market_probability": round_metric(parse_float(record.get("market_probability"))),
        "edge": round_metric(parse_float(record.get("edge"))),
        "recommendation": record.get("recommendation") or "",
        "stake_level": record.get("stake_level") or "",
        "risk_flags": record.get("risk_flags") or [],
        "caution_flags": record.get("caution_flags") or [],
        "settlement_status": record.get("settlement_status") or "",
        "created_at_utc": record.get("created_at_utc") or "",
    }


def _dashboard_candidate_filters(
    observations: list[dict[str, Any]],
    *,
    limit: int = 8,
    snapshot_coverage: dict[str, dict[str, Any]] | None = None,
    market_db_path: str | None = None,
) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for record in observations:
        raw = record.get("raw") or {}
        reason = _dashboard_reconciled_rejection_reason(
            record,
            str(
                record.get("_dashboard_policy_rejection_reason")
                or raw.get("reason")
                or record.get("recommendation")
                or "observed_not_recommended"
            ),
            snapshot_coverage=snapshot_coverage,
            market_db_path=market_db_path,
        )
        group = grouped.setdefault(reason, {"reason": reason, "count": 0, "examples": []})
        group["count"] += 1
        if len(group["examples"]) < 3:
            group["examples"].append(_dashboard_record_row(record))
    return sorted(grouped.values(), key=lambda item: (-int(item["count"]), str(item["reason"])))[:limit]


def _dashboard_settlement_row(record: dict[str, Any]) -> dict[str, Any]:
    row = _dashboard_record_row(record)
    row.update(
        {
            "score": f"{record.get('home_score')}-{record.get('away_score')}",
            "hit": record.get("hit"),
            "payout_multiplier": round_metric(parse_float(record.get("payout_multiplier")), 4),
            "profit_units": round_metric(parse_float(record.get("profit_units")), 4),
            "settled_at_utc": record.get("settled_at_utc") or "",
        }
    )
    return row


def _dashboard_prediction_identity(record: dict[str, Any]) -> str:
    line = parse_float(record.get("line"))
    line_key = "line:none" if line is None else f"line:{line:+.3f}"
    match_identity = str(record.get("match_id") or "").strip() or "|".join(
        str(record.get(key) or "")
        for key in ("league", "home_team", "away_team", "kickoff_utc_plus_8")
    )
    selection_identity = str(record.get("selection_key") or record.get("selection") or "")
    return "|".join(
        [
            match_identity,
            str(record.get("market") or ""),
            selection_identity,
            line_key,
        ]
    )


def _dashboard_prediction_type(record: dict[str, Any], *, source: str) -> str:
    if source == "shadow_prediction":
        return "recommendation" if str(record.get("decision") or "") == "accepted" else "observation"
    return "observation" if _dashboard_is_observation(record) else "recommendation"


def _dashboard_prediction_type_label(prediction_type: str) -> str:
    return "正式推荐" if prediction_type == "recommendation" else "纸面预测"


def _dashboard_strategy_mode(record: dict[str, Any]) -> str:
    mode = str(record.get("mode") or "balanced").strip().lower()
    if mode.endswith("_observation"):
        return mode.removesuffix("_observation") or "balanced"
    return mode or "balanced"


def _dashboard_threshold_gap(value: float | None, threshold: float | None) -> float | None:
    if value is None or threshold is None:
        return None
    return round_metric(value - threshold)


def _dashboard_learning_application(
    *,
    learning_active: bool,
    learned_adjustment: float | None,
    strategy_status: str,
) -> dict[str, str]:
    if not learning_active:
        return {
            "status": "collecting_samples",
            "label": "样本收集中",
            "detail": "学习样本还没有达到实时校准阈值，当前概率主要来自原始模型。",
        }
    if learned_adjustment is not None and learned_adjustment < -0.001:
        return {
            "status": "down_weight_only",
            "label": "学习校准仅降权",
            "detail": f"学习校准把概率降低 {_percent_text(abs(learned_adjustment)) or '若干'}，只作为风险降权和纸面验证，不代表正式推荐开放。",
        }
    if learned_adjustment is not None and learned_adjustment > 0.001:
        return {
            "status": "paper_boost_only",
            "label": "学习校准仅纸面提权",
            "detail": f"学习校准把概率提高 {_percent_text(learned_adjustment) or '若干'}，在生产闸门通过前只进入纸面预测和回测。",
        }
    return {
        "status": "neutral_watch",
        "label": "学习校准观察中",
        "detail": f"{strategy_status or '实时校准'} 已启用，但本场概率调整很小，继续以纸面回测验证。",
    }


def _signed_percent_text(value: Any) -> str:
    number = parse_float(value)
    if number is None:
        return "—"
    return f"{number * 100:+.1f}%"


def _dashboard_feature_tone(*, good: bool = False, bad: bool = False, caution: bool = False) -> str:
    if good:
        return "good"
    if bad:
        return "bad"
    if caution:
        return "caution"
    return "neutral"


def _dashboard_data_quality_for_record(record: dict[str, Any]) -> dict[str, Any]:
    raw = record.get("raw") if isinstance(record.get("raw"), dict) else {}
    completeness = raw.get("data_completeness") or raw.get("data_coverage") or raw.get("quality") or {}
    if not isinstance(completeness, dict):
        completeness = {}
    available = [str(item) for item in completeness.get("available_blocks") or []]
    missing = [str(item) for item in completeness.get("missing_blocks") or []]
    ratio = parse_float(completeness.get("ratio"))
    if ratio is None and (available or missing):
        total = len(set(available + missing))
        ratio = len(set(available)) / total if total else None
    return {
        "ratio": ratio,
        "available_count": len(set(available)),
        "missing_count": len(set(missing)),
        "available_blocks": available,
        "missing_blocks": missing,
    }


def _dashboard_prediction_feature_explanations(
    *,
    governed: dict[str, Any],
    model_probability: float | None,
    learned_probability: float | None,
    market_probability: float | None,
    learned_adjustment: float | None,
    value_edge: float | None,
    value_edge_gap: float | None,
    probability_gap: float | None,
    threshold_passed: bool,
    odds_coverage: dict[str, Any] | None,
    record: dict[str, Any],
) -> list[dict[str, Any]]:
    governed_probability = parse_float(governed.get("probability"))
    probability_label = str(governed.get("label") or "模型概率")
    odds_coverage = odds_coverage or {}
    snapshot_count = int(odds_coverage.get("snapshot_count") or record.get("odds_snapshot_count") or 0)
    bookmaker_count = int(odds_coverage.get("bookmaker_count") or record.get("odds_bookmaker_count") or 0)
    market_type_count = int(odds_coverage.get("market_type_count") or record.get("odds_market_type_count") or 0)
    data_quality = _dashboard_data_quality_for_record(record)
    data_ratio = parse_float(data_quality.get("ratio"))

    return [
        {
            "key": "probability_source",
            "label": "概率来源",
            "value": f"{probability_label} {_percent_text(governed_probability) or '—'}",
            "detail": (
                f"当前门槛使用{probability_label}；原始模型 {_percent_text(model_probability) or '—'}，"
                f"学习后 {_percent_text(learned_probability) or '—'}，市场隐含 {_percent_text(market_probability) or '—'}。"
            ),
            "tone": _dashboard_feature_tone(good=threshold_passed, caution=not threshold_passed),
        },
        {
            "key": "learning_adjustment",
            "label": "学习校准",
            "value": _signed_percent_text(learned_adjustment),
            "detail": (
                f"模型 {_percent_text(model_probability) or '—'} 调整为 {_percent_text(learned_probability) or '—'}；"
                "该调整来自已结算样本的实时校准。"
            ),
            "tone": _dashboard_feature_tone(
                good=learned_adjustment is not None and learned_adjustment > 0.001,
                caution=learned_adjustment is not None and learned_adjustment < -0.001,
            ),
        },
        {
            "key": "value_edge",
            "label": "价值边际",
            "value": _signed_percent_text(value_edge),
            "detail": (
                f"距离正式推荐边际门槛 {_signed_percent_text(value_edge_gap)}；"
                f"概率门槛差 {_signed_percent_text(probability_gap)}。"
            ),
            "tone": _dashboard_feature_tone(
                good=value_edge_gap is not None and value_edge_gap >= 0 and probability_gap is not None and probability_gap >= 0,
                bad=(value_edge_gap is not None and value_edge_gap < 0) or (probability_gap is not None and probability_gap < 0),
            ),
        },
        {
            "key": "odds_coverage",
            "label": "赔率覆盖",
            "value": f"{snapshot_count} 条" if snapshot_count else "暂无快照",
            "detail": (
                f"{bookmaker_count} 家公司、{market_type_count} 类盘口已进入时间序列。"
                if snapshot_count
                else "本场尚未匹配多公司赔率时间序列，无法观察盘口波动。"
            ),
            "tone": _dashboard_feature_tone(
                good=snapshot_count > 0 and bookmaker_count >= 3,
                caution=snapshot_count == 0 or bookmaker_count < 3,
            ),
        },
        {
            "key": "data_quality",
            "label": "情报完整度",
            "value": _percent_text(data_ratio) if data_ratio is not None else "待补充",
            "detail": (
                f"已采集 {data_quality['available_count']} 项，缺少 {data_quality['missing_count']} 项。"
                if data_ratio is not None
                else "本场未保存完整数据覆盖明细，只能按核心盘口和来源状态判断。"
            ),
            "tone": _dashboard_feature_tone(
                good=data_ratio is not None and data_ratio >= 0.8,
                caution=data_ratio is None or data_ratio < 0.6,
            ),
        },
    ]


def _dashboard_prediction_diagnostic(
    record: dict[str, Any],
    *,
    prediction_type: str,
    rejection_reason: str,
    strategy_state: dict[str, Any] | None = None,
    probability_governance: dict[str, Any] | None = None,
    odds_coverage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    strategy_state = strategy_state or learning_store.get_strategy_state(
        market=str(record.get("market") or "asian_handicap"),
        mode=_dashboard_strategy_mode(record),
    )
    model_probability = parse_float(record.get("model_probability"))
    learned_probability = _dashboard_probability(record)
    market_probability = parse_float(record.get("market_probability"))
    governed = _dashboard_governed_probability(record, probability_governance)
    governed_probability = parse_float(governed.get("probability"))
    value_edge = parse_float(record.get("edge"))
    decimal_odds = parse_float(record.get("decimal_odds"))
    min_probability = parse_float(strategy_state.get("min_calibrated_probability"))
    min_value_edge = parse_float(strategy_state.get("min_value_edge"))
    min_odds = parse_float(strategy_state.get("min_decimal_odds"))
    max_odds = parse_float(strategy_state.get("max_decimal_odds"))
    probability_gap = _dashboard_threshold_gap(governed_probability, min_probability)
    value_edge_gap = _dashboard_threshold_gap(value_edge, min_value_edge)
    min_odds_gap = _dashboard_threshold_gap(decimal_odds, min_odds)
    max_odds_gap = _dashboard_threshold_gap(max_odds, decimal_odds)
    odds_in_range = (
        decimal_odds is not None
        and (min_odds is None or decimal_odds >= min_odds)
        and (max_odds is None or decimal_odds <= max_odds)
    )
    recommended = prediction_type == "recommendation"
    backtest_eligible = (
        str(record.get("settlement_status") or "") in {"open", "settled"}
        and str(record.get("market") or "") != "parlay"
        and bool(record.get("home_team") and record.get("away_team") and record.get("selection"))
    )
    primary_reason = str(rejection_reason or "")
    if not primary_reason and not recommended:
        primary_reason = str((record.get("raw") or {}).get("reason") or record.get("recommendation") or "observed_not_recommended")
    if not primary_reason and recommended:
        primary_reason = str(record.get("recommendation") or "formal_recommendation")
    threshold_passed = bool(
        (probability_gap is None or probability_gap >= 0)
        and (value_edge_gap is None or value_edge_gap >= 0)
        and odds_in_range
        and (recommended or not primary_reason)
    )
    actionability = "formal_recommendation" if recommended else "paper_prediction"
    actionability_label = "正式推荐" if recommended else "纸面预测"
    primary_reason_label = _dashboard_reason_label(primary_reason)
    learned_adjustment = (
        round_metric(learned_probability - model_probability)
        if learned_probability is not None and model_probability is not None
        else None
    )
    learning_application = _dashboard_learning_application(
        learning_active=bool(strategy_state.get("active")),
        learned_adjustment=learned_adjustment,
        strategy_status=strategy_state.get("status") or "",
    )
    feature_explanations = _dashboard_prediction_feature_explanations(
        governed=governed,
        model_probability=model_probability,
        learned_probability=learned_probability,
        market_probability=market_probability,
        learned_adjustment=learned_adjustment,
        value_edge=value_edge,
        value_edge_gap=value_edge_gap,
        probability_gap=probability_gap,
        threshold_passed=threshold_passed,
        odds_coverage=odds_coverage,
        record=record,
    )
    return {
        "actionability": actionability,
        "actionability_label": actionability_label,
        "recommended": recommended,
        "paper_tracked": backtest_eligible,
        "backtest_eligible": backtest_eligible,
        "learning_active": bool(strategy_state.get("active")),
        "learning_application_status": learning_application["status"],
        "learning_application_label": learning_application["label"],
        "learning_application_detail": learning_application["detail"],
        "strategy_status": strategy_state.get("status") or "",
        "primary_reason": primary_reason,
        "primary_reason_label": primary_reason_label,
        "model_probability": round_metric(model_probability),
        "learned_probability": round_metric(learned_probability),
        "market_probability": round_metric(market_probability),
        "governed_probability": round_metric(governed_probability),
        "probability_source": governed.get("source") or "",
        "probability_source_label": governed.get("label") or "",
        "probability_source_fallback": bool(governed.get("fallback")),
        "probability_governance_status": str((probability_governance or {}).get("status") or ""),
        "probability_governance_detail": str((probability_governance or {}).get("detail") or ""),
        "learned_adjustment": learned_adjustment,
        "thresholds": {
            "min_calibrated_probability": round_metric(min_probability),
            "min_value_edge": round_metric(min_value_edge),
            "min_decimal_odds": round_metric(min_odds, 4),
            "max_decimal_odds": round_metric(max_odds, 4),
        },
        "threshold_gaps": {
            "probability": probability_gap,
            "value_edge": value_edge_gap,
            "min_decimal_odds": round_metric(min_odds_gap, 4),
            "max_decimal_odds": round_metric(max_odds_gap, 4),
        },
        "odds_in_range": odds_in_range,
        "threshold_passed": threshold_passed,
        "feature_explanations": feature_explanations,
        "diagnostic_summary": (
            f"{actionability_label} · {primary_reason_label}"
            if primary_reason_label
            else actionability_label
        ),
    }


def _dashboard_record_kickoff_utc(record: dict[str, Any]) -> datetime | None:
    kickoff = None
    kickoff_raw = record.get("kickoff_utc_plus_8") or record.get("kickoff_utc")
    if kickoff_raw:
        try:
            kickoff = datetime.fromisoformat(str(kickoff_raw).replace("Z", "+00:00"))
        except ValueError:
            kickoff = None
    if not kickoff:
        return None
    if kickoff.tzinfo is None:
        kickoff = kickoff.replace(tzinfo=DEFAULT_USER_TIMEZONE)
    return kickoff.astimezone(timezone.utc)


def _dashboard_time_based_open_match_state(record: dict[str, Any]) -> dict[str, Any] | None:
    if str(record.get("settlement_status") or "") != "open":
        return None
    kickoff_utc = _dashboard_record_kickoff_utc(record)
    if not kickoff_utc:
        return None
    current = now_utc()
    if kickoff_utc > current:
        return {
            "phase": "scheduled",
            "label": "未开赛",
            "score": "",
            "minute": "",
            "period": "",
            "status": "scheduled",
            "source": "kickoff",
        }
    if current - kickoff_utc <= timedelta(hours=3):
        return {
            "phase": "maybe_live",
            "label": "可能进行中",
            "score": "",
            "minute": "",
            "period": "",
            "status": "estimated",
            "source": "kickoff",
        }
    return {
        "phase": "result_pending",
        "label": "赛果待确认",
        "score": "",
        "minute": "",
        "period": "",
        "status": "result_pending",
        "source": "kickoff",
    }


def _dashboard_terminal_match_state(phase: str, source_status: str) -> dict[str, str] | None:
    normalized = f"{phase} {source_status}".strip().lower()
    if any(token in normalized for token in ("postponed", "delay", "延期", "推迟")):
        return {"phase": "postponed", "label": "比赛延期"}
    if any(token in normalized for token in ("cancelled", "canceled", "abandoned", "取消", "腰斩")):
        return {"phase": "cancelled", "label": "比赛取消"}
    if any(token in normalized for token in ("suspended", "interrupted", "中断")):
        return {"phase": "interrupted", "label": "比赛中断"}
    return None


def _dashboard_normalized_match_state(record: dict[str, Any]) -> dict[str, Any]:
    status = str(record.get("settlement_status") or "")
    final_score = _dashboard_score_text(record.get("home_score"), record.get("away_score"))
    if status == "settled" and final_score:
        return {
            "phase": "final",
            "label": "已完场",
            "score": final_score,
            "home_score": record.get("home_score"),
            "away_score": record.get("away_score"),
            "minute": "",
            "period": "",
            "status": "settled",
            "source": "settlement",
        }

    raw = record.get("raw") if isinstance(record.get("raw"), dict) else {}
    state = raw.get("match_state") if isinstance(raw.get("match_state"), dict) else {}
    time_state = _dashboard_time_based_open_match_state(record)
    if state:
        phase = str(state.get("phase") or "unknown")
        source_status = str(state.get("status") or "")
        terminal_state = _dashboard_terminal_match_state(phase, source_status)
        if terminal_state:
            return {
                **terminal_state,
                "score": str(state.get("score") or ""),
                "home_score": state.get("home_score"),
                "away_score": state.get("away_score"),
                "minute": str(state.get("minute") or ""),
                "period": str(state.get("period") or ""),
                "status": source_status,
                "source": str(state.get("source") or ""),
                "updated_at_utc": state.get("updated_at_utc") or "",
            }
        if phase == "scheduled" and time_state and time_state.get("phase") != "scheduled":
            return {
                **time_state,
                "source": "kickoff_stale_scheduled_state",
                "status": source_status or time_state.get("status") or "",
                "updated_at_utc": state.get("updated_at_utc") or "",
            }
        label = str(state.get("label") or "")
        if not label:
            label = {
                "live": "比赛进行中",
                "scheduled": "未开赛",
                "final": "已完场待结算",
                "result_pending": "赛果待确认",
            }.get(phase, "赛果待确认")
        return {
            "phase": phase,
            "label": label,
            "score": str(state.get("score") or ""),
            "home_score": state.get("home_score"),
            "away_score": state.get("away_score"),
            "minute": str(state.get("minute") or ""),
            "period": str(state.get("period") or ""),
            "status": source_status,
            "source": str(state.get("source") or ""),
            "updated_at_utc": state.get("updated_at_utc") or "",
        }

    if time_state:
        return time_state
    return {"phase": "unknown", "label": "赛果待确认", "score": "", "minute": "", "period": "", "status": status or "unknown", "source": ""}


def _dashboard_prediction_status_label(record: dict[str, Any]) -> str:
    status = str(record.get("settlement_status") or "")
    if status == "settled":
        return "命中" if int(record.get("hit") or 0) else "未命中"
    if status == "open":
        return _dashboard_normalized_match_state(record).get("label") or "等待赛果"
    labels = {
        "tracked_only": "仅跟踪",
        "unsupported_market": "不支持结算",
        "duplicate_ignored": "重复忽略",
    }
    return labels.get(status, status or "未知")


def _dashboard_final_score(record: dict[str, Any]) -> str:
    if record.get("home_score") is None or record.get("away_score") is None:
        return ""
    return _dashboard_score_text(record.get("home_score"), record.get("away_score"))


def _dashboard_prediction_score(record: dict[str, Any], match_state: dict[str, Any] | None = None) -> str:
    final_score = _dashboard_final_score(record)
    if final_score:
        return final_score
    state = match_state or _dashboard_normalized_match_state(record)
    return str(state.get("score") or "")


def _dashboard_prediction_score_type(record: dict[str, Any], match_state: dict[str, Any] | None = None) -> str:
    if _dashboard_final_score(record):
        return "final"
    state = match_state or _dashboard_normalized_match_state(record)
    phase = str(state.get("phase") or "")
    if phase == "live" and state.get("score"):
        return "live"
    if phase == "final" and state.get("score"):
        return "final_pending"
    return ""


def _dashboard_prediction_row(
    record: dict[str, Any],
    *,
    source: str,
    snapshot_coverage: dict[str, dict[str, Any]] | None = None,
    market_db_path: str | None = None,
    strategy_state: dict[str, Any] | None = None,
    probability_governance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    prediction_type = _dashboard_prediction_type(record, source=source)
    match_state = _dashboard_normalized_match_state(record)
    score = _dashboard_prediction_score(record, match_state)
    final_score = _dashboard_final_score(record)
    odds_coverage = _dashboard_snapshot_coverage_for_record(
        record,
        snapshot_coverage=snapshot_coverage,
        market_db_path=market_db_path,
    )
    odds_snapshot_count = int(odds_coverage.get("snapshot_count") or 0)
    raw_rejection_reason = str(record.get("rejection_reason") or (record.get("raw") or {}).get("reason") or "")
    rejection_reason = _dashboard_reconciled_rejection_reason(
        record,
        raw_rejection_reason,
        snapshot_coverage=snapshot_coverage,
        market_db_path=market_db_path,
    )
    if (
        source == "shadow_prediction"
        and raw_rejection_reason == "multi_bookmaker_snapshot_missing"
        and odds_snapshot_count > 0
    ):
        rejection_reason = "shadow_prediction_reference_only"
    prediction_diagnostic = _dashboard_prediction_diagnostic(
        record,
        prediction_type=prediction_type,
        rejection_reason=rejection_reason,
        strategy_state=strategy_state,
        probability_governance=probability_governance,
        odds_coverage=odds_coverage,
    )
    governed = _dashboard_governed_probability(record, probability_governance)
    return {
        "ledger_id": f"{source}:{record.get('id')}",
        "source": source,
        "source_id": record.get("id"),
        "prediction_type": prediction_type,
        "prediction_type_label": _dashboard_prediction_type_label(prediction_type),
        "status_label": _dashboard_prediction_status_label(record),
        "league": record.get("league") or "",
        "matchup": _dashboard_matchup(record),
        "home_team": record.get("home_team") or "",
        "away_team": record.get("away_team") or "",
        "home_team_logo_url": _dashboard_team_logo_url(record, "home"),
        "away_team_logo_url": _dashboard_team_logo_url(record, "away"),
        "kickoff_utc_plus_8": record.get("kickoff_utc_plus_8") or "",
        "market": record.get("market") or "",
        "selection": record.get("selection") or "",
        "selection_key": record.get("selection_key") or "",
        "line": round_metric(parse_float(record.get("line")), 4),
        "decimal_odds": round_metric(parse_float(record.get("decimal_odds")), 4),
        "model_probability": round_metric(parse_float(record.get("model_probability"))),
        "learned_probability": round_metric(_dashboard_probability(record)),
        "market_probability": round_metric(parse_float(record.get("market_probability"))),
        "governed_probability": round_metric(parse_float(governed.get("probability"))),
        "probability_source": governed.get("source") or "",
        "probability_source_label": governed.get("label") or "",
        "edge": round_metric(parse_float(record.get("edge"))),
        "recommendation": record.get("recommendation") or "",
        "rejection_reason": rejection_reason,
        "settlement_status": record.get("settlement_status") or "",
        "score": score,
        "score_type": _dashboard_prediction_score_type(record, match_state),
        "match_state": match_state,
        "true_result": {
            "home_score": record.get("home_score"),
            "away_score": record.get("away_score"),
            "score": final_score,
        },
        "hit": record.get("hit"),
        "payout_multiplier": round_metric(parse_float(record.get("payout_multiplier")), 4),
        "profit_units": round_metric(parse_float(record.get("profit_units")), 4),
        "settled_at_utc": record.get("settled_at_utc") or "",
        "created_at_utc": record.get("created_at_utc") or "",
        "has_odds_snapshot": odds_snapshot_count > 0,
        "odds_snapshot_count": odds_snapshot_count,
        "odds_bookmaker_count": int(odds_coverage.get("bookmaker_count") or 0),
        "odds_market_type_count": int(odds_coverage.get("market_type_count") or 0),
        "odds_latest_fetched_at_utc": odds_coverage.get("latest_fetched_at_utc") or "",
        "prediction_diagnostic": prediction_diagnostic,
    }


def _dashboard_prediction_ledger(
    *,
    db_path: str | None = None,
    market_db_path: str | None = None,
    limit: int = 120,
    strategy_state: dict[str, Any] | None = None,
    probability_governance: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    source_records = _dashboard_prediction_source_records(db_path=db_path, limit=limit)
    snapshot_coverage = snapshot_store.market_snapshot_coverage_for_records(
        [record for _source, record in source_records],
        db_path=market_db_path,
    )
    rows = [
        _dashboard_prediction_row(
            record,
            source=source,
            snapshot_coverage=snapshot_coverage,
            market_db_path=market_db_path,
            strategy_state=strategy_state,
            probability_governance=probability_governance,
        )
        for source, record in source_records
    ]
    rows.sort(key=lambda item: str(item.get("created_at_utc") or ""), reverse=True)
    return rows


def _dashboard_prediction_source_records(
    *,
    db_path: str | None = None,
    limit: int = 120,
) -> list[tuple[str, dict[str, Any]]]:
    bounded_limit = max(10, min(int(limit or 120), 500))
    recommendation_records = [
        record
        for record in learning_store.list_recommendation_records(db_path=db_path, limit=bounded_limit * 2)
        if record.get("market") != "parlay"
        and record.get("settlement_status") != "duplicate_ignored"
        and _dashboard_record_has_display_match(record)
    ]
    shadow_records = [
        record
        for record in learning_store.list_shadow_prediction_records(db_path=db_path, limit=bounded_limit * 2)
        if record.get("market") != "parlay"
        and record.get("settlement_status") != "duplicate_ignored"
        and _dashboard_record_has_display_match(record)
    ]
    seen: set[str] = set()
    rows: list[tuple[str, dict[str, Any]]] = []
    for record in recommendation_records:
        identity = _dashboard_prediction_identity(record)
        seen.add(identity)
        rows.append(("recommendation", record))
    for record in shadow_records:
        identity = _dashboard_prediction_identity(record)
        if identity in seen:
            continue
        seen.add(identity)
        rows.append(("shadow_prediction", record))
    rows.sort(key=lambda item: str(item[1].get("created_at_utc") or ""), reverse=True)
    return rows[:bounded_limit]


def _dashboard_display_prediction_ledger(rows: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    bounded_limit = max(10, min(int(limit or 500), 500))
    selected = list(rows[:bounded_limit])
    selected_ids = {str(row.get("ledger_id") or "") for row in selected}
    priority_rows = [
        row
        for row in rows
        if row.get("prediction_type") == "recommendation" or row.get("settlement_status") == "settled"
    ]

    for row in priority_rows:
        ledger_id = str(row.get("ledger_id") or "")
        if ledger_id in selected_ids:
            continue
        replace_index = next(
            (
                index
                for index in range(len(selected) - 1, -1, -1)
                if selected[index].get("prediction_type") != "recommendation"
                and selected[index].get("settlement_status") != "settled"
            ),
            None,
        )
        if replace_index is None:
            break
        selected_ids.discard(str(selected[replace_index].get("ledger_id") or ""))
        selected[replace_index] = row
        selected_ids.add(ledger_id)

    selected.sort(key=lambda item: str(item.get("created_at_utc") or ""), reverse=True)
    return selected[:bounded_limit]


def _dashboard_prediction_kpis(rows: list[dict[str, Any]]) -> dict[str, Any]:
    settled_rows = [row for row in rows if row.get("settlement_status") == "settled"]
    profits = [parse_float(row.get("profit_units")) for row in settled_rows]
    profits = [profit for profit in profits if profit is not None]
    hit_count = sum(1 for row in settled_rows if int(row.get("hit") or 0) == 1)
    miss_count = sum(1 for row in settled_rows if int(row.get("hit") or 0) == 0)
    recommended_settled_rows = [
        row for row in settled_rows if row.get("prediction_type") == "recommendation"
    ]
    observation_settled_rows = [
        row for row in settled_rows if row.get("prediction_type") == "observation"
    ]
    phase_counts: Counter[str] = Counter()
    live_count = scheduled_count = final_pending_count = maybe_live_count = result_pending_count = postponed_count = 0
    for row in rows:
        state = row.get("match_state") if isinstance(row.get("match_state"), dict) else {}
        phase = str(state.get("phase") or "unknown")
        phase_counts[phase] += 1
        if row.get("settlement_status") != "open":
            continue
        if phase == "live":
            live_count += 1
        elif phase == "scheduled":
            scheduled_count += 1
        elif phase == "final":
            final_pending_count += 1
        elif phase == "maybe_live":
            maybe_live_count += 1
        elif phase in {"postponed", "cancelled", "interrupted"}:
            postponed_count += 1
        else:
            result_pending_count += 1

    def segment_kpis(segment_rows: list[dict[str, Any]]) -> dict[str, Any]:
        segment_profits = [parse_float(row.get("profit_units")) for row in segment_rows]
        segment_profits = [profit for profit in segment_profits if profit is not None]
        segment_hit_count = sum(1 for row in segment_rows if int(row.get("hit") or 0) == 1)
        segment_miss_count = sum(1 for row in segment_rows if int(row.get("hit") or 0) == 0)
        return {
            "settled_count": len(segment_rows),
            "hit_count": segment_hit_count,
            "miss_count": segment_miss_count,
            "hit_rate": round_metric(segment_hit_count / len(segment_rows)) if segment_rows else None,
            "roi": round_metric(sum(segment_profits) / len(segment_profits), 4) if segment_profits else None,
        }

    recommended_segment = segment_kpis(recommended_settled_rows)
    observation_segment = segment_kpis(observation_settled_rows)
    return {
        "total_count": len(rows),
        "recommended_count": sum(1 for row in rows if row.get("prediction_type") == "recommendation"),
        "observation_count": sum(1 for row in rows if row.get("prediction_type") == "observation"),
        "open_count": sum(1 for row in rows if row.get("settlement_status") == "open"),
        "live_count": live_count,
        "scheduled_count": scheduled_count,
        "final_pending_count": final_pending_count,
        "maybe_live_count": maybe_live_count,
        "result_pending_count": result_pending_count,
        "postponed_count": postponed_count,
        "match_phase_counts": dict(sorted(phase_counts.items())),
        "settled_count": len(settled_rows),
        "hit_count": hit_count,
        "miss_count": miss_count,
        "hit_rate": round_metric(hit_count / len(settled_rows)) if settled_rows else None,
        "roi": round_metric(sum(profits) / len(profits), 4) if profits else None,
        "recommended_settled_count": recommended_segment["settled_count"],
        "recommended_hit_count": recommended_segment["hit_count"],
        "recommended_miss_count": recommended_segment["miss_count"],
        "recommended_hit_rate": recommended_segment["hit_rate"],
        "recommended_roi": recommended_segment["roi"],
        "observation_settled_count": observation_segment["settled_count"],
        "observation_hit_count": observation_segment["hit_count"],
        "observation_miss_count": observation_segment["miss_count"],
        "observation_hit_rate": observation_segment["hit_rate"],
        "observation_roi": observation_segment["roi"],
    }


def _dashboard_backtest_curve(rows: list[dict[str, Any]], *, rolling_window: int = 10) -> dict[str, Any]:
    settled_rows = [
        row
        for row in rows
        if row.get("settlement_status") == "settled" and parse_float(row.get("profit_units")) is not None
    ]
    settled_rows.sort(
        key=lambda row: (
            str(row.get("settled_at_utc") or ""),
            str(row.get("created_at_utc") or ""),
            str(row.get("ledger_id") or row.get("id") or ""),
        )
    )
    rolling_window = max(1, min(int(rolling_window or 10), 50))
    if not settled_rows:
        return {
            "status": "waiting_settlements",
            "severity": "warning",
            "title": "等待回测走势",
            "detail": "还没有可用于绘制收益曲线的已结算预测。",
            "summary": {
                "settled_count": 0,
                "hit_count": 0,
                "miss_count": 0,
                "hit_rate": None,
                "profit_units": 0.0,
                "roi": None,
                "max_drawdown_units": 0.0,
                "longest_loss_streak": 0,
                "current_streak_type": "",
                "current_streak_count": 0,
                "rolling_window": rolling_window,
            },
            "points": [],
        }

    points = []
    cumulative_profit = 0.0
    peak_profit = 0.0
    max_drawdown = 0.0
    hit_count = 0
    miss_count = 0
    current_streak_type = ""
    current_streak_count = 0
    longest_loss_streak = 0
    hits: list[int] = []
    for index, row in enumerate(settled_rows, start=1):
        profit = parse_float(row.get("profit_units")) or 0.0
        hit = 1 if int(row.get("hit") or 0) == 1 else 0
        hits.append(hit)
        if hit:
            hit_count += 1
            streak_type = "hit"
        else:
            miss_count += 1
            streak_type = "miss"
        if streak_type == current_streak_type:
            current_streak_count += 1
        else:
            current_streak_type = streak_type
            current_streak_count = 1
        if streak_type == "miss":
            longest_loss_streak = max(longest_loss_streak, current_streak_count)

        cumulative_profit += profit
        peak_profit = max(peak_profit, cumulative_profit)
        drawdown = cumulative_profit - peak_profit
        max_drawdown = min(max_drawdown, drawdown)
        rolling_hits = hits[-rolling_window:]
        rolling_hit_rate = sum(rolling_hits) / len(rolling_hits) if rolling_hits else None
        points.append(
            {
                "index": index,
                "ledger_id": row.get("ledger_id") or "",
                "matchup": row.get("matchup") or "",
                "prediction_type_label": row.get("prediction_type_label") or "",
                "at_utc": row.get("settled_at_utc") or row.get("created_at_utc") or "",
                "hit": hit,
                "profit_units": round_metric(profit, 4),
                "cumulative_profit": round_metric(cumulative_profit, 4),
                "roi": round_metric(cumulative_profit / index, 6),
                "drawdown_units": round_metric(drawdown, 4),
                "rolling_hit_rate": round_metric(rolling_hit_rate, 6),
            }
        )

    roi = cumulative_profit / len(settled_rows)
    if roi > 0:
        status = "positive_roi"
        severity = "ok"
        title = "回测走势为正"
    elif roi < 0:
        status = "negative_roi"
        severity = "warning"
        title = "回测走势承压"
    else:
        status = "flat_roi"
        severity = "info"
        title = "回测走势持平"
    return {
        "status": status,
        "severity": severity,
        "title": title,
        "detail": f"已按结算时间串联 {len(settled_rows)} 场预测，展示累计收益、最大回撤和最近 {rolling_window} 场滚动命中率。",
        "summary": {
            "settled_count": len(settled_rows),
            "hit_count": hit_count,
            "miss_count": miss_count,
            "hit_rate": round_metric(hit_count / len(settled_rows)),
            "profit_units": round_metric(cumulative_profit, 4),
            "roi": round_metric(roi, 6),
            "max_drawdown_units": round_metric(max_drawdown, 4),
            "longest_loss_streak": longest_loss_streak,
            "current_streak_type": current_streak_type,
            "current_streak_count": current_streak_count,
            "rolling_window": rolling_window,
        },
        "points": points[-120:],
    }


def _dashboard_prediction_quality_adjustment(
    *,
    reason: str,
    settled_count: int,
    hit_rate: float | None,
    roi: float | None,
    sample_quality: str,
) -> dict[str, Any]:
    label = _dashboard_reason_label(reason)
    if sample_quality != "enough_sample":
        return {
            "action": "collect_more_samples",
            "label": "继续采样",
            "detail": f"{label} 分组已回测 {settled_count} 场，样本不足 20 场，暂不自动降权。",
            "weight_multiplier": 1.0,
            "formal_gate_eligible": False,
        }
    if roi is not None and roi <= -0.05:
        return {
            "action": "suppress_reason",
            "label": "降权过滤",
            "detail": f"{label} 分组已有充分样本且负收益，进入正式推荐前需要降权或过滤。",
            "weight_multiplier": 0.5,
            "formal_gate_eligible": False,
        }
    if roi is not None and roi < 0:
        return {
            "action": "tighten_thresholds",
            "label": "收紧阈值",
            "detail": f"{label} 分组收益略负，后续候选需要更高概率和价值边际。",
            "weight_multiplier": 0.75,
            "formal_gate_eligible": False,
        }
    if roi is not None and roi > 0.05 and (hit_rate is None or hit_rate >= 0.5):
        return {
            "action": "promote_watchlist",
            "label": "保留观察",
            "detail": f"{label} 分组回测表现较好，可继续进入纸面信号池并观察是否打开正式闸门。",
            "weight_multiplier": 1.1,
            "formal_gate_eligible": True,
        }
    return {
        "action": "hold_neutral",
        "label": "中性观察",
        "detail": f"{label} 分组暂未形成明确正负收益结论，保持当前采样权重。",
        "weight_multiplier": 1.0,
        "formal_gate_eligible": False,
    }


def _dashboard_prediction_quality(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        diagnostic = row.get("prediction_diagnostic") if isinstance(row.get("prediction_diagnostic"), dict) else {}
        reason = str(diagnostic.get("primary_reason") or row.get("rejection_reason") or row.get("recommendation") or "observed_not_recommended")
        grouped.setdefault(reason, []).append(row)

    segments = []
    for reason, segment_rows in grouped.items():
        settled_rows = [row for row in segment_rows if row.get("settlement_status") == "settled"]
        open_rows = [row for row in segment_rows if row.get("settlement_status") == "open"]
        hit_count = sum(1 for row in settled_rows if int(row.get("hit") or 0) == 1)
        miss_count = sum(1 for row in settled_rows if int(row.get("hit") or 0) == 0)
        profits = [parse_float(row.get("profit_units")) for row in settled_rows]
        profits = [value for value in profits if value is not None]
        probabilities = [parse_float(row.get("learned_probability")) for row in segment_rows]
        probabilities = [value for value in probabilities if value is not None]
        edges = [parse_float(row.get("edge")) for row in segment_rows]
        edges = [value for value in edges if value is not None]
        odds_covered_count = sum(1 for row in segment_rows if bool(row.get("has_odds_snapshot")) or int(row.get("odds_snapshot_count") or 0) > 0)
        signal_count = sum(1 for row in segment_rows if str(row.get("recommendation") or "") in _DASHBOARD_SIGNAL_RECOMMENDATIONS)
        settled_count = len(settled_rows)
        roi = sum(profits) / len(profits) if profits else None
        hit_rate = hit_count / settled_count if settled_count else None
        sample_quality = "enough_sample" if settled_count >= 20 else "thin_sample"
        segments.append(
            {
                "key": reason,
                "reason": reason,
                "label": _dashboard_reason_label(reason),
                "total_count": len(segment_rows),
                "open_count": len(open_rows),
                "settled_count": settled_count,
                "hit_count": hit_count,
                "miss_count": miss_count,
                "hit_rate": round_metric(hit_rate),
                "roi": round_metric(roi, 4),
                "avg_probability": round_metric(sum(probabilities) / len(probabilities) if probabilities else None),
                "avg_edge": round_metric(sum(edges) / len(edges) if edges else None, 4),
                "odds_covered_count": odds_covered_count,
                "odds_coverage_ratio": round_metric(odds_covered_count / len(segment_rows), 6) if segment_rows else None,
                "signal_count": signal_count,
                "sample_quality": sample_quality,
                "tone": (
                    "positive"
                    if roi is not None and roi > 0
                    else "negative"
                    if roi is not None and roi < 0
                    else "neutral"
                ),
                "adjustment": _dashboard_prediction_quality_adjustment(
                    reason=reason,
                    settled_count=settled_count,
                    hit_rate=hit_rate,
                    roi=roi,
                    sample_quality=sample_quality,
                ),
            }
        )

    segments.sort(
        key=lambda item: (
            int(item.get("settled_count") or 0),
            int(item.get("total_count") or 0),
            parse_float(item.get("roi")) or -999.0,
        ),
        reverse=True,
    )
    settled_count = sum(int(segment.get("settled_count") or 0) for segment in segments)
    negative_count = sum(1 for segment in segments if parse_float(segment.get("roi")) is not None and parse_float(segment.get("roi")) < 0)
    best = max(
        (segment for segment in segments if parse_float(segment.get("roi")) is not None),
        key=lambda item: parse_float(item.get("roi")) or -999.0,
        default=None,
    )
    worst = min(
        (segment for segment in segments if parse_float(segment.get("roi")) is not None),
        key=lambda item: parse_float(item.get("roi")) or 999.0,
        default=None,
    )
    if not rows:
        status = "no_predictions"
        title = "暂无预测质量样本"
        detail = "还没有预测台账，无法按原因回测。"
        severity = "warning"
    elif settled_count == 0:
        status = "waiting_settlements"
        title = "等待预测结算"
        detail = f"已有 {len(rows)} 条预测样本，但还没有可用于分段回测的结算结果。"
        severity = "warning"
    elif negative_count:
        status = "segments_need_attention"
        title = "纸面预测分组偏弱"
        detail = f"{len(segments)} 类预测原因中有 {negative_count} 类回测收益为负，需要继续降权或过滤。"
        severity = "warning"
    else:
        status = "segments_healthy"
        title = "纸面预测分组稳定"
        detail = f"已按 {len(segments)} 类预测原因完成回测分段，暂未发现负收益分组。"
        severity = "ok"
    return {
        "status": status,
        "severity": severity,
        "title": title,
        "detail": detail,
        "summary": {
            "total_count": len(rows),
            "settled_count": settled_count,
            "open_count": sum(1 for row in rows if row.get("settlement_status") == "open"),
            "segment_count": len(segments),
            "negative_segment_count": negative_count,
            "best_reason": best.get("reason") if best else "",
            "worst_reason": worst.get("reason") if worst else "",
        },
        "segments": segments[:8],
    }


def _dashboard_probability_quality(
    rows: list[dict[str, Any]],
    probability_key: str,
) -> dict[str, Any]:
    samples: list[tuple[float, float]] = []
    for row in rows:
        probability = parse_float(row.get(probability_key))
        if probability is None:
            continue
        hit = parse_float(row.get("hit"))
        if hit is None:
            continue
        samples.append((max(0.0, min(1.0, probability)), 1.0 if hit >= 1 else 0.0))
    if not samples:
        return {
            "sample_count": 0,
            "brier_score": None,
            "calibration_error": None,
            "avg_probability": None,
            "hit_rate": None,
        }
    brier = sum((probability - hit) ** 2 for probability, hit in samples) / len(samples)
    avg_probability = sum(probability for probability, _ in samples) / len(samples)
    hit_rate = sum(hit for _, hit in samples) / len(samples)
    return {
        "sample_count": len(samples),
        "brier_score": round_metric(brier, 6),
        "calibration_error": round_metric(abs(avg_probability - hit_rate), 6),
        "avg_probability": round_metric(avg_probability),
        "hit_rate": round_metric(hit_rate),
    }


def _dashboard_probability_candidate_value(row: dict[str, Any], source: str) -> float | None:
    if source == "learned_probability":
        return parse_float(row.get("learned_probability"))
    if source == "model_probability":
        return parse_float(row.get("model_probability"))
    if source == "market_probability":
        return parse_float(row.get("market_probability"))
    if source == "learned_market_blend":
        learned = parse_float(row.get("learned_probability"))
        market = parse_float(row.get("market_probability"))
        if learned is not None and market is not None:
            return (learned + market) / 2
        return learned if learned is not None else market
    return None


def _dashboard_probability_candidate_quality(rows: list[dict[str, Any]], source: str) -> dict[str, Any]:
    samples: list[tuple[float, float]] = []
    for row in rows:
        probability = _dashboard_probability_candidate_value(row, source)
        hit = parse_float(row.get("hit"))
        if probability is None or hit is None:
            continue
        samples.append((max(0.0, min(1.0, probability)), 1.0 if hit >= 1 else 0.0))
    if not samples:
        return {
            "sample_count": 0,
            "brier_score": None,
            "calibration_error": None,
            "avg_probability": None,
            "hit_rate": None,
        }
    brier = sum((probability - hit) ** 2 for probability, hit in samples) / len(samples)
    avg_probability = sum(probability for probability, _hit in samples) / len(samples)
    hit_rate = sum(hit for _probability, hit in samples) / len(samples)
    return {
        "sample_count": len(samples),
        "brier_score": round_metric(brier, 6),
        "calibration_error": round_metric(abs(avg_probability - hit_rate), 6),
        "avg_probability": round_metric(avg_probability),
        "hit_rate": round_metric(hit_rate),
    }


def _dashboard_probability_governance(
    settled_rows: list[dict[str, Any]],
    *,
    learning_improved: bool,
    beats_market: bool,
    shadow_recalibration: dict[str, Any] | None = None,
) -> dict[str, Any]:
    labels = {
        "market_probability": "市场基准",
        "learned_probability": "学习校准",
        "model_probability": "原始模型",
        "learned_market_blend": "学习/市场混合",
    }
    candidate_sources = [
        "market_probability",
        "learned_probability",
        "model_probability",
    ]
    candidates = []
    for source in candidate_sources:
        quality = _dashboard_probability_candidate_quality(settled_rows, source)
        candidates.append(
            {
                "source": source,
                "label": labels[source],
                "sample_count": int(quality.get("sample_count") or 0),
                "brier_score": quality.get("brier_score"),
                "calibration_error": quality.get("calibration_error"),
                "avg_probability": quality.get("avg_probability"),
                "hit_rate": quality.get("hit_rate"),
                "selected": False,
            }
        )
    candidates.sort(
        key=lambda item: (
            parse_float(item.get("brier_score")) if parse_float(item.get("brier_score")) is not None else 999.0,
            parse_float(item.get("calibration_error")) if parse_float(item.get("calibration_error")) is not None else 999.0,
            -int(item.get("sample_count") or 0),
        )
    )
    for index, candidate in enumerate(candidates, start=1):
        candidate["rank"] = index

    shadow_quality = (
        shadow_recalibration.get("quality")
        if isinstance(shadow_recalibration, dict) and isinstance(shadow_recalibration.get("quality"), dict)
        else {}
    )
    shadow_delta = parse_float(shadow_quality.get("walk_forward_brier_delta"))
    shadow_failed = shadow_delta is not None and shadow_delta > 0
    market_candidate = next((candidate for candidate in candidates if candidate["source"] == "market_probability"), {})
    market_available = int(market_candidate.get("sample_count") or 0) > 0 and parse_float(market_candidate.get("brier_score")) is not None
    guardrails: list[str] = []
    if not beats_market and market_available:
        guardrails.append("学习未跑赢市场")
    if shadow_failed:
        guardrails.append("影子模型走步验证未过")

    if not settled_rows:
        active_source = "model_probability"
        status = "collecting_samples"
        severity = "warning"
        title = "样本收集中"
        detail = "还没有已结算概率样本，候选门槛暂时使用原始模型概率。"
        policy_mode = "collecting_samples"
    elif market_available and shadow_failed and beats_market:
        active_source = "market_probability"
        status = "shadow_walk_forward_guardrail_active"
        severity = "warning"
        title = "走步验证保护"
        detail = "学习概率已优于市场，但影子重校准走步验证未过；正式候选门槛暂时使用市场基准保护。"
        policy_mode = "shadow_walk_forward_guardrail"
    elif market_available and guardrails:
        active_source = "market_probability"
        status = "market_guardrail_active"
        severity = "warning"
        title = "市场基准优先"
        detail = "学习概率尚未跑赢市场，正式推荐和候选门槛暂时使用市场基准概率保护。"
        policy_mode = "market_guardrail"
    elif beats_market and learning_improved:
        active_source = "learned_probability"
        status = "learned_probability_active"
        severity = "ok"
        title = "学习概率可用"
        detail = "学习概率已优于原始模型和市场基准，可作为候选门槛概率。"
        policy_mode = "learned_gate"
    else:
        active_source = "learned_probability"
        status = "learned_probability_watch"
        severity = "info"
        title = "保守概率观察"
        detail = "学习效果仍在观察，候选门槛使用保守概率并继续纸面回测。"
        policy_mode = "conservative_watch"

    for candidate in candidates:
        candidate["selected"] = candidate["source"] == active_source

    return {
        "status": status,
        "severity": severity,
        "title": title,
        "detail": detail,
        "active_probability_source": active_source,
        "active_source_label": labels.get(active_source, active_source),
        "policy_mode": policy_mode,
        "production_ready": status == "learned_probability_active",
        "threshold_probability_field": "governed_probability",
        "guardrails": guardrails,
        "candidates": candidates,
        "rule": "按已结算样本比较 Brier 和校准误差；学习没有跑赢市场或影子模型走步变差时，正式候选门槛使用市场基准概率。预测仍持续入账并回测。",
    }


_DASHBOARD_PROBABILITY_BANDS = (
    ("under_45", "低于 45%", 0.0, 0.45),
    ("between_45_55", "45% - 55%", 0.45, 0.55),
    ("between_55_65", "55% - 65%", 0.55, 0.65),
    ("over_65", "65% 以上", 0.65, 1.0000001),
)


def _dashboard_probability_bands(rows: list[dict[str, Any]], probability_key: str = "learned_probability") -> list[dict[str, Any]]:
    band_rows: dict[str, list[dict[str, Any]]] = {key: [] for key, _label, _minimum, _maximum in _DASHBOARD_PROBABILITY_BANDS}
    for row in rows:
        probability = parse_float(row.get(probability_key))
        hit = parse_float(row.get("hit"))
        if probability is None or hit is None:
            continue
        bounded_probability = max(0.0, min(1.0, probability))
        for key, _label, minimum, maximum in _DASHBOARD_PROBABILITY_BANDS:
            if minimum <= bounded_probability < maximum:
                band_rows[key].append({**row, "_band_probability": bounded_probability})
                break

    bands = []
    for key, label, minimum, maximum in _DASHBOARD_PROBABILITY_BANDS:
        samples = band_rows[key]
        hit_values = [1.0 if parse_float(row.get("hit")) and parse_float(row.get("hit")) >= 1 else 0.0 for row in samples]
        probabilities = [parse_float(row.get("_band_probability")) for row in samples]
        probabilities = [value for value in probabilities if value is not None]
        profits = [parse_float(row.get("profit_units")) for row in samples]
        profits = [value for value in profits if value is not None]
        sample_count = len(samples)
        hit_count = int(sum(hit_values))
        avg_probability = sum(probabilities) / len(probabilities) if probabilities else None
        hit_rate = sum(hit_values) / len(hit_values) if hit_values else None
        brier = (
            sum((probability - hit) ** 2 for probability, hit in zip(probabilities, hit_values)) / sample_count
            if sample_count and len(probabilities) == len(hit_values)
            else None
        )
        calibration_error = (
            abs(avg_probability - hit_rate)
            if avg_probability is not None and hit_rate is not None
            else None
        )
        roi = sum(profits) / len(profits) if profits else None
        bands.append(
            {
                "key": key,
                "label": label,
                "min_probability": round_metric(minimum),
                "max_probability": None if key == "over_65" else round_metric(maximum),
                "sample_count": sample_count,
                "hit_count": hit_count,
                "hit_rate": round_metric(hit_rate),
                "avg_probability": round_metric(avg_probability),
                "calibration_error": round_metric(calibration_error),
                "brier_score": round_metric(brier, 6),
                "roi": round_metric(roi, 4),
                "sample_quality": "enough_sample" if sample_count >= 20 else "thin_sample",
            }
        )
    return bands


def _dashboard_probability_band_key(probability: float | None) -> str:
    if probability is None:
        return ""
    bounded_probability = max(0.0, min(1.0, probability))
    for key, _label, minimum, maximum in _DASHBOARD_PROBABILITY_BANDS:
        if minimum <= bounded_probability < maximum:
            return key
    return ""


def _dashboard_wilson_lower_bound(hit_count: int, sample_count: int, z: float = 1.28) -> float | None:
    if sample_count <= 0:
        return None
    p = hit_count / sample_count
    denominator = 1 + z * z / sample_count
    centre = p + z * z / (2 * sample_count)
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * sample_count)) / sample_count)
    return max(0.0, (centre - margin) / denominator)


def _dashboard_probability_band_health(bands: list[dict[str, Any]]) -> dict[str, Any]:
    usable_bands = [
        band
        for band in bands
        if int(band.get("sample_count") or 0) > 0 and parse_float(band.get("hit_rate")) is not None
    ]
    if not usable_bands:
        return {
            "status": "waiting_samples",
            "severity": "warning",
            "title": "等待概率分桶样本",
            "detail": "还没有足够的已结算概率分桶，暂时不能判断校准方向。",
            "recommended_action": "collect_more_samples",
            "best_band_key": "",
            "candidate_band_keys": [],
            "monotonicity_violations": 0,
            "meta_model": {
                "name": "probability_band_reliability",
                "type": "wilson_roi_band_selector",
                "min_band_sample_count": 8,
                "confidence_z": 1.28,
            },
        }

    enriched = []
    for band in usable_bands:
        sample_count = int(band.get("sample_count") or 0)
        hit_count = int(band.get("hit_count") or 0)
        roi = parse_float(band.get("roi"))
        hit_rate = parse_float(band.get("hit_rate"))
        wilson_low = _dashboard_wilson_lower_bound(hit_count, sample_count)
        enriched.append(
            {
                **band,
                "sample_count": sample_count,
                "hit_rate_value": hit_rate,
                "roi_value": roi,
                "wilson_hit_rate_low": round_metric(wilson_low),
            }
        )

    violations = 0
    for left_index, left in enumerate(enriched):
        left_hit = parse_float(left.get("hit_rate_value"))
        left_samples = int(left.get("sample_count") or 0)
        for right in enriched[left_index + 1 :]:
            right_hit = parse_float(right.get("hit_rate_value"))
            right_samples = int(right.get("sample_count") or 0)
            if left_samples >= 8 and right_samples >= 8 and left_hit is not None and right_hit is not None and left_hit > right_hit + 0.08:
                violations += 1

    best_band = max(
        enriched,
        key=lambda band: (
            parse_float(band.get("roi_value")) if parse_float(band.get("roi_value")) is not None else -999.0,
            parse_float(band.get("wilson_hit_rate_low")) if parse_float(band.get("wilson_hit_rate_low")) is not None else -999.0,
            int(band.get("sample_count") or 0),
        ),
    )
    best_band_key = str(best_band.get("key") or "")
    best_band_label = str(best_band.get("label") or "概率段")
    best_band_roi = parse_float(best_band.get("roi_value"))
    best_band_hit_rate = parse_float(best_band.get("hit_rate_value"))
    candidate_band_keys = [
        str(band.get("key") or "")
        for band in enriched
        if int(band.get("sample_count") or 0) >= 8
        and (parse_float(band.get("roi_value")) or 0.0) > 0
        and (parse_float(band.get("hit_rate_value")) or 0.0) >= 0.5
    ]
    candidate_band_keys = [key for key in candidate_band_keys if key]
    high_band_negative = any(
        str(band.get("key") or "") not in candidate_band_keys
        and int(band.get("sample_count") or 0) >= 8
        and parse_float(band.get("roi_value")) is not None
        and (parse_float(band.get("roi_value")) or 0.0) < 0
        for band in enriched
    )
    inverted = bool(violations > 0 and best_band_key in {"under_45", "between_45_55"} and best_band_roi is not None and best_band_roi > 0 and high_band_negative)
    if inverted:
        status = "inverted_probability_bands"
        severity = "warning"
        title = "校准方向异常"
        detail = (
            f"低概率分桶 {best_band_label} 当前表现最好：命中率 {_percent_text(best_band_hit_rate) or '暂无'}、"
            f"收益率 {_percent_text(best_band_roi) or '暂无'}；较高概率分桶反而走弱，正式推荐必须保持关闭。"
        )
        recommended_action = "freeze_formal_recommendations_and_run_band_recalibration"
    else:
        status = "bands_monotonic_enough" if violations == 0 else "bands_need_more_samples"
        severity = "ok" if violations == 0 else "info"
        title = "概率分桶方向正常" if violations == 0 else "概率分桶需继续验证"
        detail = (
            f"当前最佳分桶为 {best_band_label}，命中率 {_percent_text(best_band_hit_rate) or '暂无'}、"
            f"收益率 {_percent_text(best_band_roi) or '暂无'}。"
        )
        recommended_action = "continue_band_backtest"

    return {
        "status": status,
        "severity": severity,
        "title": title,
        "detail": detail,
        "recommended_action": recommended_action,
        "best_band_key": best_band_key,
        "candidate_band_keys": candidate_band_keys,
        "monotonicity_violations": violations,
        "meta_model": {
            "name": "probability_band_reliability",
            "type": "wilson_roi_band_selector",
            "min_band_sample_count": 8,
            "confidence_z": 1.28,
        },
        "bands": [
            {
                "key": str(band.get("key") or ""),
                "label": str(band.get("label") or ""),
                "sample_count": int(band.get("sample_count") or 0),
                "hit_rate": round_metric(parse_float(band.get("hit_rate_value"))),
                "roi": round_metric(parse_float(band.get("roi_value")), 4),
                "wilson_hit_rate_low": band.get("wilson_hit_rate_low"),
            }
            for band in enriched
        ],
    }


def _dashboard_band_posterior_probability(hit_count: int, sample_count: int) -> float | None:
    if sample_count <= 0:
        return None
    return (hit_count + 1.0) / (sample_count + 2.0)


def _dashboard_average(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _dashboard_shadow_row_sort_key(item: tuple[dict[str, Any], str, float, float]) -> tuple[str, str, str, int]:
    row, _band_key, _probability, _hit = item
    return (
        str(row.get("settled_at_utc") or ""),
        str(row.get("kickoff_utc_plus_8") or ""),
        str(row.get("created_at_utc") or ""),
        int(row.get("id") or 0),
    )


def _dashboard_shadow_walk_forward(
    usable_rows: list[tuple[dict[str, Any], str, float, float]],
) -> list[dict[str, Any]]:
    states: dict[str, dict[str, int]] = {}
    points: list[dict[str, Any]] = []
    for row, band_key, learned_probability, hit in sorted(usable_rows, key=_dashboard_shadow_row_sort_key):
        state = states.setdefault(band_key, {"sample_count": 0, "hit_count": 0})
        walk_probability = (state["hit_count"] + 1.0) / (state["sample_count"] + 2.0)
        points.append(
            {
                "row": row,
                "band_key": band_key,
                "learned_probability": learned_probability,
                "walk_probability": walk_probability,
                "hit": hit,
                "previous_sample_count": state["sample_count"],
            }
        )
        state["sample_count"] += 1
        state["hit_count"] += int(hit)
    return points


def _dashboard_brier_from_points(points: list[dict[str, Any]], probability_key: str) -> float | None:
    if not points:
        return None
    return sum((float(point[probability_key]) - float(point["hit"])) ** 2 for point in points) / len(points)


def _dashboard_shadow_recalibration(
    settled_rows: list[dict[str, Any]],
    calibration_health: dict[str, Any],
) -> dict[str, Any]:
    band_stats: dict[str, dict[str, Any]] = {}
    usable_rows = []
    for row in settled_rows:
        probability = parse_float(row.get("learned_probability"))
        hit = parse_float(row.get("hit"))
        if probability is None or hit is None:
            continue
        band_key = _dashboard_probability_band_key(probability)
        if not band_key:
            continue
        hit_value = 1.0 if hit >= 1 else 0.0
        band = band_stats.setdefault(
            band_key,
            {
                "key": band_key,
                "label": next((label for key, label, _minimum, _maximum in _DASHBOARD_PROBABILITY_BANDS if key == band_key), "概率段"),
                "rows": [],
                "hit_count": 0,
                "profit_units": [],
                "market_probabilities": [],
                "learned_probabilities": [],
            },
        )
        band["rows"].append(row)
        band["hit_count"] += int(hit_value)
        band["learned_probabilities"].append(max(0.0, min(1.0, probability)))
        market_probability = parse_float(row.get("market_probability"))
        if market_probability is not None:
            band["market_probabilities"].append(max(0.0, min(1.0, market_probability)))
        profit = parse_float(row.get("profit_units"))
        if profit is not None:
            band["profit_units"].append(profit)
        usable_rows.append((row, band_key, max(0.0, min(1.0, probability)), hit_value))

    selected_band_keys = {
        str(key)
        for key in (calibration_health.get("candidate_band_keys") or [])
        if str(key)
    }
    walk_points = _dashboard_shadow_walk_forward(usable_rows)
    band_models = []
    posterior_by_key: dict[str, float] = {}
    for key, band in band_stats.items():
        sample_count = len(band["rows"])
        hit_count = int(band["hit_count"])
        posterior = _dashboard_band_posterior_probability(hit_count, sample_count)
        posterior_by_key[key] = posterior if posterior is not None else 0.0
        profits = [value for value in band["profit_units"] if value is not None]
        avg_market_probability = _dashboard_average([value for value in band["market_probabilities"] if value is not None])
        avg_learned_probability = _dashboard_average([value for value in band["learned_probabilities"] if value is not None])
        roi = sum(profits) / len(profits) if profits else None
        expected_multiplier = posterior * (1 / avg_market_probability) if posterior is not None and avg_market_probability and avg_market_probability > 0 else None
        band_walk_points = [point for point in walk_points if point["band_key"] == key]
        walk_brier = _dashboard_brier_from_points(band_walk_points, "walk_probability")
        band_models.append(
            {
                "key": key,
                "label": band.get("label") or "概率段",
                "sample_count": sample_count,
                "hit_count": hit_count,
                "hit_rate": round_metric(hit_count / sample_count) if sample_count else None,
                "posterior_probability": round_metric(posterior),
                "avg_learned_probability": round_metric(avg_learned_probability),
                "avg_market_probability": round_metric(avg_market_probability),
                "posterior_edge": round_metric(posterior - avg_market_probability) if posterior is not None and avg_market_probability is not None else None,
                "expected_multiplier": round_metric(expected_multiplier, 4),
                "roi": round_metric(roi, 4),
                "selected": key in selected_band_keys,
                "confidence": "enough_sample" if sample_count >= 20 else "thin_sample",
                "walk_forward_brier_score": round_metric(walk_brier, 6),
            }
        )

    sample_count = len(usable_rows)
    if sample_count == 0:
        return {
            "status": "waiting_samples",
            "severity": "warning",
            "title": "等待影子重校准样本",
            "detail": "还没有足够的已结算概率样本，暂时不能训练影子重校准模型。",
            "method": "beta_binomial_probability_band_recalibrator_v1",
            "selected_band_keys": [],
            "quality": {
                "sample_count": 0,
                "learned_brier_score": None,
                "recalibrated_brier_score": None,
                "brier_delta": None,
                "validation_mode": "walk_forward_prequential",
                "walk_forward_sample_count": 0,
                "walk_forward_recalibrated_brier_score": None,
                "walk_forward_brier_delta": None,
            },
            "validation": {"mode": "walk_forward_prequential", "sample_count": 0, "hit_rate": None, "roi": None},
            "bands": [],
        }

    learned_brier = sum((probability - hit) ** 2 for _row, _band_key, probability, hit in usable_rows) / sample_count
    recalibrated_brier = sum((posterior_by_key.get(band_key, probability) - hit) ** 2 for _row, band_key, probability, hit in usable_rows) / sample_count
    walk_forward_brier = _dashboard_brier_from_points(walk_points, "walk_probability")
    selected_rows = [
        row
        for row, band_key, _probability, _hit in usable_rows
        if band_key in selected_band_keys
    ]
    selected_walk_points = [point for point in walk_points if point["band_key"] in selected_band_keys]
    selected_hit_count = sum(1 for row in selected_rows if int(row.get("hit") or 0) == 1)
    selected_profits = [parse_float(row.get("profit_units")) for row in selected_rows]
    selected_profits = [value for value in selected_profits if value is not None]
    selected_roi = sum(selected_profits) / len(selected_profits) if selected_profits else None
    selected_walk_brier = _dashboard_brier_from_points(selected_walk_points, "walk_probability")
    walk_forward_delta = walk_forward_brier - learned_brier if walk_forward_brier is not None else None
    walk_forward_passed = walk_forward_delta is not None and walk_forward_delta <= 0
    if selected_band_keys and walk_forward_passed:
        status = "shadow_model_ready"
        severity = "warning"
        detail = f"影子模型按概率分桶做贝塔-二项后验重校准，走步验证暂时优于原学习概率；当前选中 {len(selected_band_keys)} 个只用于纸面验证的分桶。"
    elif selected_band_keys:
        status = "shadow_model_watch_only"
        severity = "warning"
        detail = f"影子模型样本内改善，但走步验证尚未优于原学习概率；当前 {len(selected_band_keys)} 个分桶只允许观察，不允许升级正式推荐。"
    else:
        status = "shadow_model_collecting"
        severity = "info"
        detail = "影子模型已计算分桶后验，但暂未发现可验证的反向分桶。"
    return {
        "status": status,
        "severity": severity,
        "title": "影子重校准模型",
        "detail": detail,
        "method": "beta_binomial_probability_band_recalibrator_v1",
        "selected_band_keys": sorted(selected_band_keys),
        "quality": {
            "sample_count": sample_count,
            "learned_brier_score": round_metric(learned_brier, 6),
            "recalibrated_brier_score": round_metric(recalibrated_brier, 6),
            "brier_delta": round_metric(recalibrated_brier - learned_brier, 6),
            "validation_mode": "walk_forward_prequential",
            "walk_forward_sample_count": len(walk_points),
            "walk_forward_recalibrated_brier_score": round_metric(walk_forward_brier, 6),
            "walk_forward_brier_delta": round_metric(walk_forward_delta, 6),
        },
        "validation": {
            "mode": "walk_forward_prequential",
            "sample_count": len(selected_rows),
            "hit_count": selected_hit_count,
            "hit_rate": round_metric(selected_hit_count / len(selected_rows)) if selected_rows else None,
            "roi": round_metric(selected_roi, 4),
            "walk_forward_brier_score": round_metric(selected_walk_brier, 6),
        },
        "bands": sorted(
            band_models,
            key=lambda band: (
                1 if band.get("selected") else 0,
                parse_float(band.get("roi")) if parse_float(band.get("roi")) is not None else -999.0,
                int(band.get("sample_count") or 0),
            ),
            reverse=True,
        ),
    }


def _dashboard_learning_deployment_verdict(
    *,
    sample_count: int,
    roi: float | None,
    learning_improved: bool,
    beats_market: bool,
    calibration_health: dict[str, Any] | None = None,
) -> dict[str, Any]:
    reasons: list[str] = []
    if sample_count <= 0:
        return {
            "status": "waiting_settled_samples",
            "severity": "warning",
            "title": "等待回测样本",
            "detail": "还没有已结算样本，学习结果不能用于正式推荐。",
            "production_ready": False,
            "action": "collect_more_samples",
            "sample_count": sample_count,
            "roi": round_metric(roi, 4),
            "reasons": ["no_settled_samples"],
        }

    if not learning_improved:
        reasons.append("not_better_than_model")
    if not beats_market:
        reasons.append("not_better_than_market")
    if roi is not None and roi < 0:
        reasons.append("settled_roi_negative")
    calibration_status = str((calibration_health or {}).get("status") or "")
    if calibration_status == "inverted_probability_bands":
        reasons.append("probability_bands_inverted")
        return {
            "status": "calibration_inversion_guardrail",
            "severity": "warning",
            "title": "校准方向异常，保持纸面验证",
            "detail": str((calibration_health or {}).get("detail") or "概率分桶出现反向表现，暂不允许正式推荐。"),
            "production_ready": False,
            "action": "run_band_recalibration",
            "sample_count": sample_count,
            "roi": round_metric(roi, 4),
            "reasons": reasons,
        }

    if learning_improved and beats_market and (roi is None or roi >= 0):
        return {
            "status": "candidate_for_production_gate",
            "severity": "ok",
            "title": "学习质量可进入推荐闸门",
            "detail": "学习概率优于原始模型和市场，且已结算收益未触发负收益暂停。",
            "production_ready": True,
            "action": "allow_gate_evaluation",
            "sample_count": sample_count,
            "roi": round_metric(roi, 4),
            "reasons": [],
        }

    if learning_improved and not beats_market:
        title = "仅可用于保守校准"
        detail = "学习概率优于原始模型，但尚未优于市场隐含概率，只能用于降权和纸面验证。"
        action = "calibrate_down_only"
        severity = "info"
        status = "calibration_only_not_beating_market"
    elif learning_improved and beats_market:
        title = "学习有效但收益未转正"
        detail = f"学习概率优于原始模型和市场，但已结算收益率仍为 {roi:+.1%}，只能继续纸面验证。"
        action = "keep_paper_backtest"
        severity = "warning"
        status = "paper_only_negative_roi"
    else:
        title = "学习暂不可用于推荐"
        detail = "学习概率尚未证明优于原始模型，需要继续采样或调整校准策略。"
        action = "collect_or_retrain"
        severity = "warning"
        status = "learning_not_deployable"

    return {
        "status": status,
        "severity": severity,
        "title": title,
        "detail": detail,
        "production_ready": False,
        "action": action,
        "sample_count": sample_count,
        "roi": round_metric(roi, 4),
        "reasons": reasons,
    }


def _dashboard_learning_effectiveness(rows: list[dict[str, Any]]) -> dict[str, Any]:
    settled_rows = [row for row in rows if row.get("settlement_status") == "settled"]
    model_quality = _dashboard_probability_quality(settled_rows, "model_probability")
    learned_quality = _dashboard_probability_quality(settled_rows, "learned_probability")
    market_quality = _dashboard_probability_quality(settled_rows, "market_probability")
    probability_bands = _dashboard_probability_bands(settled_rows, "learned_probability")
    calibration_health = _dashboard_probability_band_health(probability_bands)
    shadow_recalibration = _dashboard_shadow_recalibration(settled_rows, calibration_health)
    profits = [parse_float(row.get("profit_units")) for row in settled_rows]
    profits = [value for value in profits if value is not None]
    roi = sum(profits) / len(profits) if profits else None
    sample_count = int(learned_quality.get("sample_count") or 0)
    model_brier = parse_float(model_quality.get("brier_score"))
    learned_brier = parse_float(learned_quality.get("brier_score"))
    market_brier = parse_float(market_quality.get("brier_score"))
    learned_minus_model = (
        round_metric(learned_brier - model_brier, 6)
        if learned_brier is not None and model_brier is not None
        else None
    )
    learned_minus_market = (
        round_metric(learned_brier - market_brier, 6)
        if learned_brier is not None and market_brier is not None
        else None
    )
    model_calibration_error = parse_float(model_quality.get("calibration_error"))
    learned_calibration_error = parse_float(learned_quality.get("calibration_error"))
    learned_calibration_minus_model = (
        round_metric(learned_calibration_error - model_calibration_error, 6)
        if learned_calibration_error is not None and model_calibration_error is not None
        else None
    )
    learning_improved = learned_minus_model is not None and learned_minus_model < 0
    beats_market = learned_minus_market is not None and learned_minus_market < 0
    probability_governance = _dashboard_probability_governance(
        settled_rows,
        learning_improved=learning_improved,
        beats_market=beats_market,
        shadow_recalibration=shadow_recalibration,
    )
    if sample_count == 0:
        status = "no_settled_samples"
        severity = "warning"
        title = "等待回测样本"
        detail = "还没有已结算预测，无法判断学习校准是否有效。"
    elif learning_improved and beats_market:
        status = "learning_improving"
        severity = "ok"
        title = "学习校准有效"
        detail = "学习后概率优于原始模型和市场隐含概率。"
    elif learning_improved:
        status = "learning_improving_vs_model"
        severity = "info"
        title = "学习校准优于原始模型"
        detail = "学习后概率优于原始模型，但暂未优于市场隐含概率。"
    else:
        status = "learning_not_improving"
        severity = "warning"
        title = "学习效果待提升"
        detail = "学习后概率暂未优于原始模型，需要继续积累样本或调整校准策略。"
    return {
        "status": status,
        "severity": severity,
        "title": title,
        "detail": detail,
        "sample_count": sample_count,
        "model": model_quality,
        "learned": learned_quality,
        "market": market_quality,
        "probability_bands": probability_bands,
        "calibration_health": calibration_health,
        "shadow_recalibration": shadow_recalibration,
        "probability_governance": probability_governance,
        "deltas": {
            "learned_brier_minus_model": learned_minus_model,
            "learned_brier_minus_market": learned_minus_market,
            "learned_calibration_error_minus_model": learned_calibration_minus_model,
        },
        "learning_improved": learning_improved,
        "beats_market": beats_market,
        "deployment_verdict": _dashboard_learning_deployment_verdict(
            sample_count=sample_count,
            roi=roi,
            learning_improved=learning_improved,
            beats_market=beats_market,
            calibration_health=calibration_health,
        ),
        "metric_rule": "Brier 分数越低越好；校准误差越低越好。只使用已结算且有概率字段的纸面样本。",
    }


_DASHBOARD_SIGNAL_RECOMMENDATIONS = {
    "immediate_bet",
    "condition_observe",
    "paper_track",
    "bet_now",
}


def _dashboard_prediction_reason(row: dict[str, Any]) -> str:
    diagnostic = row.get("prediction_diagnostic") if isinstance(row.get("prediction_diagnostic"), dict) else {}
    return str(
        diagnostic.get("primary_reason")
        or row.get("rejection_reason")
        or row.get("recommendation")
        or "observed_not_recommended"
    )


def _dashboard_prediction_quality_segment_map(prediction_quality: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not isinstance(prediction_quality, dict):
        return {}
    segments = prediction_quality.get("segments") if isinstance(prediction_quality.get("segments"), list) else []
    segment_map: dict[str, dict[str, Any]] = {}
    for segment in segments:
        if not isinstance(segment, dict):
            continue
        reason = str(segment.get("reason") or segment.get("key") or "")
        if reason:
            segment_map[reason] = segment
    return segment_map


def _dashboard_negative_quality_segment_blocker(
    row: dict[str, Any],
    segment_map: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    reason = _dashboard_prediction_reason(row)
    segment = segment_map.get(reason)
    if not segment:
        return None
    adjustment = segment.get("adjustment") if isinstance(segment.get("adjustment"), dict) else {}
    action = str(adjustment.get("action") or "")
    roi = parse_float(segment.get("roi"))
    settled_count = int(segment.get("settled_count") or 0)
    sample_quality = str(segment.get("sample_quality") or "")
    has_enough_sample = sample_quality == "enough_sample" or settled_count >= 20
    blocks_formal_gate = bool(
        action in {"suppress_reason", "tighten_thresholds"}
        or (has_enough_sample and roi is not None and roi < 0)
    )
    if not blocks_formal_gate:
        return None
    return {
        "reason": reason,
        "label": segment.get("label") or _dashboard_reason_label(reason),
        "action": action or "negative_segment",
        "settled_count": settled_count,
        "roi": round_metric(roi, 4),
        "ledger_id": row.get("ledger_id") or "",
    }


def _dashboard_quality_blocker_summary(blockers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for blocker in blockers:
        reason = str(blocker.get("reason") or "")
        if not reason:
            continue
        group = grouped.setdefault(
            reason,
            {
                "reason": reason,
                "label": blocker.get("label") or _dashboard_reason_label(reason),
                "count": 0,
                "settled_count": blocker.get("settled_count") or 0,
                "roi": blocker.get("roi"),
                "action": blocker.get("action") or "",
            },
        )
        group["count"] = int(group.get("count") or 0) + 1
    return sorted(grouped.values(), key=lambda item: (-int(item.get("count") or 0), str(item.get("reason") or "")))


def _dashboard_quality_blocker_label_text(blockers: list[dict[str, Any]]) -> str:
    labels = []
    for blocker in blockers:
        label = str(blocker.get("label") or "")
        if label and label not in labels:
            labels.append(label)
    if not labels:
        return "负收益分组"
    return "、".join(labels[:3])


def _dashboard_row_threshold_ready(row: dict[str, Any]) -> bool:
    diagnostic = row.get("prediction_diagnostic") if isinstance(row.get("prediction_diagnostic"), dict) else {}
    gaps = diagnostic.get("threshold_gaps") if isinstance(diagnostic.get("threshold_gaps"), dict) else {}
    probability_gap = parse_float(gaps.get("probability"))
    value_edge_gap = parse_float(gaps.get("value_edge"))
    min_odds_gap = parse_float(gaps.get("min_decimal_odds"))
    max_odds_gap = parse_float(gaps.get("max_decimal_odds"))
    return bool(
        (probability_gap is None or probability_gap >= 0)
        and (value_edge_gap is None or value_edge_gap >= 0)
        and (min_odds_gap is None or min_odds_gap >= 0)
        and (max_odds_gap is None or max_odds_gap >= 0)
    )


def _dashboard_opportunity_candidate(row: dict[str, Any]) -> dict[str, Any]:
    diagnostic = row.get("prediction_diagnostic") if isinstance(row.get("prediction_diagnostic"), dict) else {}
    gaps = diagnostic.get("threshold_gaps") if isinstance(diagnostic.get("threshold_gaps"), dict) else {}
    return {
        "ledger_id": row.get("ledger_id") or "",
        "league": row.get("league") or "",
        "matchup": row.get("matchup") or "",
        "home_team": row.get("home_team") or "",
        "away_team": row.get("away_team") or "",
        "home_team_logo_url": row.get("home_team_logo_url") or "",
        "away_team_logo_url": row.get("away_team_logo_url") or "",
        "selection": row.get("selection") or "",
        "recommendation": row.get("recommendation") or "",
        "primary_blocker": diagnostic.get("primary_reason") or row.get("rejection_reason") or "",
        "threshold_ready": _dashboard_row_threshold_ready(row),
        "has_odds_snapshot": bool(row.get("has_odds_snapshot") or int(row.get("odds_snapshot_count") or 0) > 0),
        "learned_probability": round_metric(parse_float(row.get("learned_probability"))),
        "probability_gap": round_metric(parse_float(gaps.get("probability"))),
        "value_edge": round_metric(parse_float(row.get("edge"))),
        "value_edge_gap": round_metric(parse_float(gaps.get("value_edge"))),
        "decimal_odds": round_metric(parse_float(row.get("decimal_odds")), 4),
        "odds_snapshot_count": int(row.get("odds_snapshot_count") or 0),
        "settlement_status": row.get("settlement_status") or "",
        "status_label": row.get("status_label") or "",
    }


def _dashboard_shadow_band(shadow_recalibration: dict[str, Any], band_key: str) -> dict[str, Any]:
    for band in shadow_recalibration.get("bands") or []:
        if isinstance(band, dict) and str(band.get("key") or "") == band_key:
            return band
    return {}


def _dashboard_counter_signal_candidate(
    row: dict[str, Any],
    calibration_health: dict[str, Any],
    shadow_recalibration: dict[str, Any] | None = None,
) -> dict[str, Any]:
    candidate = _dashboard_opportunity_candidate(row)
    candidate["meta_signal_label"] = "反向校准观察"
    candidate["meta_signal_reason"] = str(calibration_health.get("detail") or "")
    band_key = _dashboard_probability_band_key(parse_float(row.get("learned_probability")))
    candidate["probability_band_key"] = band_key
    candidate["recommendation"] = "paper_counter_signal"
    shadow_band = _dashboard_shadow_band(shadow_recalibration or {}, band_key)
    meta_probability = parse_float(shadow_band.get("posterior_probability"))
    market_probability = parse_float(row.get("market_probability"))
    decimal_odds = parse_float(row.get("decimal_odds"))
    if meta_probability is not None:
        candidate["meta_probability"] = round_metric(meta_probability)
        candidate["meta_edge"] = round_metric(meta_probability - market_probability) if market_probability is not None else None
        candidate["meta_expected_multiplier"] = round_metric(meta_probability * decimal_odds, 4) if decimal_odds is not None else None
        candidate["meta_sample_count"] = int(shadow_band.get("sample_count") or 0)
        candidate["meta_confidence"] = str(shadow_band.get("confidence") or "")
    else:
        candidate["meta_probability"] = None
        candidate["meta_edge"] = None
        candidate["meta_expected_multiplier"] = None
        candidate["meta_sample_count"] = 0
        candidate["meta_confidence"] = ""
    return candidate


def _dashboard_backtest_segment(rows: list[dict[str, Any]]) -> dict[str, Any]:
    settled_rows = [row for row in rows if row.get("settlement_status") == "settled"]
    profits = [parse_float(row.get("profit_units")) for row in settled_rows]
    profits = [value for value in profits if value is not None]
    hit_count = sum(1 for row in settled_rows if int(row.get("hit") or 0) == 1)
    miss_count = sum(1 for row in settled_rows if int(row.get("hit") or 0) == 0)
    return {
        "sample_count": len(settled_rows),
        "hit_count": hit_count,
        "miss_count": miss_count,
        "hit_rate": round_metric(hit_count / len(settled_rows)) if settled_rows else None,
        "roi": round_metric(sum(profits) / len(profits), 4) if profits else None,
    }


def _dashboard_recommendation_release_gate(
    strategy_state: dict[str, Any],
    *,
    learning_effectiveness: dict[str, Any] | None = None,
    calibration_health: dict[str, Any] | None = None,
    paper_signal_count: int = 0,
    counter_signal_count: int = 0,
    threshold_ready_count: int = 0,
    missing_snapshot_count: int = 0,
    signal_backtest: dict[str, Any] | None = None,
    negative_segment_blocked_count: int = 0,
    negative_segment_blockers: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    sample_count = int(strategy_state.get("sample_count") or 0)
    min_sample_count = int(strategy_state.get("min_live_sample_count") or 20)
    min_signal_sample_count = min_sample_count
    roi = parse_float(strategy_state.get("roi"))
    hit_rate = parse_float(strategy_state.get("hit_rate"))
    signal_backtest = signal_backtest or {}
    negative_segment_blockers = negative_segment_blockers or []
    signal_sample_count = int(signal_backtest.get("sample_count") or 0)
    signal_roi = parse_float(signal_backtest.get("roi"))
    signal_hit_rate = parse_float(signal_backtest.get("hit_rate"))
    effectiveness = learning_effectiveness or {}
    beats_market = bool(effectiveness.get("beats_market"))
    learning_improved = bool(effectiveness.get("learning_improved"))
    shadow_recalibration = (
        effectiveness.get("shadow_recalibration")
        if isinstance(effectiveness.get("shadow_recalibration"), dict)
        else {}
    )
    shadow_quality = (
        shadow_recalibration.get("quality")
        if isinstance(shadow_recalibration.get("quality"), dict)
        else {}
    )
    shadow_status = str(shadow_recalibration.get("status") or "")
    shadow_walk_sample_count = int(shadow_quality.get("walk_forward_sample_count") or 0)
    shadow_walk_delta = parse_float(shadow_quality.get("walk_forward_brier_delta"))
    shadow_walk_applicable = bool(
        shadow_recalibration
        and (
            shadow_walk_sample_count > 0
            or shadow_walk_delta is not None
            or shadow_status in {"shadow_model_ready", "shadow_model_watch_only"}
        )
    )
    shadow_walk_failed = bool(
        shadow_walk_applicable
        and (
            shadow_status == "shadow_model_watch_only"
            or (shadow_walk_delta is not None and shadow_walk_delta > 0)
        )
    )
    shadow_walk_passed = bool(
        shadow_walk_applicable
        and not shadow_walk_failed
        and shadow_walk_delta is not None
        and shadow_walk_delta <= 0
    )
    calibration_health = calibration_health or {}
    calibration_inverted = str(calibration_health.get("status") or "") == "inverted_probability_bands"
    if calibration_inverted:
        status = "paper_only_calibration_guardrail"
        formal_enabled = False
        title = "校准异常保护"
        detail = (
            f"{calibration_health.get('detail') or '概率分桶出现反向表现。'}"
            f" 当前 {counter_signal_count} 场只进入反向校准观察，不升级为正式推荐。"
        )
        severity = "warning"
    elif sample_count < min_sample_count:
        status = "collecting_samples"
        formal_enabled = False
        title = "样本收集中"
        detail = f"已结算 {sample_count} 场，达到 {min_sample_count} 场前只做预测和回测。"
        severity = "warning"
    elif shadow_walk_failed:
        status = "paper_only_shadow_walk_forward"
        formal_enabled = False
        title = "走步验证未过"
        delta_text = f"{shadow_walk_delta:+.4f}" if shadow_walk_delta is not None else "暂无"
        detail = (
            f"{shadow_recalibration.get('detail') or '影子重校准模型未通过走步验证。'}"
            f" 走步 Brier 变化 {delta_text}，当前只允许继续纸面预测、回测和观察，不升级为正式推荐。"
        )
        severity = "warning"
    elif paper_signal_count <= 0:
        status = "paper_only_no_signal"
        formal_enabled = False
        title = "等待正向纸面信号"
        detail = "当前没有可升级的纸面正向信号，继续预测并回测。"
        severity = "info"
    elif signal_sample_count < min_signal_sample_count:
        status = "collecting_signal_samples"
        formal_enabled = False
        title = "信号样本收集中"
        detail = f"正向纸面信号已回测 {signal_sample_count} 场，达到 {min_signal_sample_count} 场前不升级正式推荐。"
        severity = "warning"
    elif signal_roi is not None and signal_roi < 0:
        status = "paper_only_negative_signal_roi"
        formal_enabled = False
        title = "正式推荐暂停"
        detail = f"正向纸面信号回测收益率 {signal_roi:+.1%}，继续预测并回测，但不升级为正式推荐。"
        severity = "warning"
    elif negative_segment_blocked_count > 0 and threshold_ready_count <= 0:
        status = "paper_only_negative_segment"
        formal_enabled = False
        title = "负收益分组保护"
        blocker_text = _dashboard_quality_blocker_label_text(negative_segment_blockers)
        detail = (
            f"{blocker_text} 已有充分负收益回测，当前 {negative_segment_blocked_count} 场候选只保留观察；"
            "需要降权过滤或收紧阈值后再评估正式推荐。"
        )
        severity = "warning"
    elif threshold_ready_count <= 0:
        status = "paper_only_threshold_not_ready"
        formal_enabled = False
        title = "候选尚未过线"
        detail = f"当前纸面信号 {paper_signal_count} 场，但没有候选同时满足概率、边际和赔率门槛。"
        severity = "warning"
    elif missing_snapshot_count > 0:
        status = "paper_only_snapshot_missing"
        formal_enabled = False
        title = "等待赔率快照补齐"
        detail = f"{missing_snapshot_count} 场纸面信号缺少多公司赔率快照，继续预测并等待复算。"
        severity = "warning"
    elif effectiveness and not beats_market:
        status = "paper_only_not_beating_market"
        formal_enabled = False
        title = "等待跑赢市场"
        detail = "学习后概率尚未优于市场隐含概率，继续预测并回测，暂不升级正式推荐。"
        severity = "info"
    else:
        status = "formal_gate_open"
        formal_enabled = True
        title = "正式推荐门槛开放"
        detail = "回测和学习质量允许把达标候选升级为正式推荐。"
        severity = "ok" if learning_improved or beats_market else "info"
    gates = [
        {
            "key": "prediction_policy",
            "label": "预测策略",
            "status": "ok",
            "title": "持续预测回测",
            "detail": "正式推荐暂停时仍生成纸面预测，并持续进入结算回测。",
            "current": paper_signal_count,
            "target": None,
            "ratio": 1.0,
        },
        {
            "key": "sample_count",
            "label": "回测样本",
            "status": "ok" if sample_count >= min_sample_count else "warning",
            "title": "样本达到阈值" if sample_count >= min_sample_count else "样本继续收集",
            "detail": f"已结算样本 {sample_count} 场，正式推荐至少需要 {min_sample_count} 场。",
            "current": sample_count,
            "target": min_sample_count,
            "ratio": _dashboard_ratio(sample_count, min_sample_count),
        },
        {
            "key": "signal_backtest",
            "label": "信号回测",
            "status": (
                "warning"
                if signal_sample_count < min_signal_sample_count
                else "blocked"
                if signal_roi is not None and signal_roi < 0
                else "ok"
            ),
            "title": (
                "信号样本不足"
                if signal_sample_count < min_signal_sample_count
                else "信号收益为负"
                if signal_roi is not None and signal_roi < 0
                else "信号收益未阻断"
            ),
            "detail": (
                f"正向纸面信号已回测 {signal_sample_count} 场，至少需要 {min_signal_sample_count} 场。"
                if signal_sample_count < min_signal_sample_count
                else "正向纸面信号收益为负，正式推荐保持暂停。"
                if signal_roi is not None and signal_roi < 0
                else "正向纸面信号回测未触发暂停。"
            ),
            "current": round_metric(signal_roi, 4),
            "target": 0,
            "ratio": None,
        },
        {
            "key": "prediction_quality_segment",
            "label": "分组质量",
            "status": (
                "blocked"
                if negative_segment_blocked_count > 0 and threshold_ready_count <= 0
                else "warning"
                if negative_segment_blocked_count > 0
                else "ok"
            ),
            "title": (
                "负收益分组阻断"
                if negative_segment_blocked_count > 0 and threshold_ready_count <= 0
                else "部分候选被过滤"
                if negative_segment_blocked_count > 0
                else "分组质量未阻断"
            ),
            "detail": (
                f"{_dashboard_quality_blocker_label_text(negative_segment_blockers)} 分组过滤 "
                f"{negative_segment_blocked_count} 场候选，暂不升级为正式推荐。"
                if negative_segment_blocked_count > 0
                else "当前纸面候选未命中已确认负收益分组。"
            ),
            "current": max(0, paper_signal_count - negative_segment_blocked_count),
            "target": paper_signal_count,
            "ratio": _dashboard_ratio(max(0, paper_signal_count - negative_segment_blocked_count), paper_signal_count)
            if paper_signal_count
            else 1.0,
        },
        {
            "key": "global_backtest_roi",
            "label": "全局回测",
            "status": "warning" if roi is not None and roi < 0 else "ok",
            "title": "全局收益为负" if roi is not None and roi < 0 else "全局收益未阻断",
            "detail": "包含无价值纸面样本的全局收益仅作为风险提示，不单独阻断正向候选升级。"
            if roi is not None and roi < 0
            else "全局回测收益未触发风险提示。",
            "current": round_metric(roi, 4),
            "target": 0,
            "ratio": None,
        },
        {
            "key": "calibration_health",
            "label": "校准健康",
            "status": "blocked" if calibration_inverted else "ok",
            "title": "校准方向异常" if calibration_inverted else "校准方向未阻断",
            "detail": str(calibration_health.get("detail") or "概率分桶未触发反向校准保护。"),
            "current": 0 if calibration_inverted else 1,
            "target": 1,
            "ratio": 0.0 if calibration_inverted else 1.0,
        },
    ]
    if shadow_walk_applicable:
        gates.append(
            {
                "key": "shadow_walk_forward",
                "label": "走步验证",
                "status": "blocked" if shadow_walk_failed else "ok" if shadow_walk_passed else "warning",
                "title": (
                    "走步验证未过"
                    if shadow_walk_failed
                    else "走步验证通过"
                    if shadow_walk_passed
                    else "走步验证观察中"
                ),
                "detail": (
                    f"影子重校准模型走步验证 {shadow_walk_sample_count} 场，"
                    f"Brier 变化 {_signed_decimal_text(shadow_walk_delta) or '暂无'}。"
                    + (
                        " 样本内改善但走步验证变差，正式推荐保持关闭。"
                        if shadow_walk_failed
                        else " 走步验证没有变差，可继续作为候选门禁参考。"
                        if shadow_walk_passed
                        else " 样本仍需继续累积。"
                    )
                ),
                "current": round_metric(shadow_walk_delta, 6),
                "target": 0,
                "ratio": 0.0 if shadow_walk_failed else 1.0 if shadow_walk_passed else None,
            }
        )
    gates.extend(
        [
            {
                "key": "market_quality",
                "label": "市场对比",
                "status": "ok" if beats_market else "blocked",
                "title": "已优于市场" if beats_market else "尚未跑赢市场",
                "detail": "学习后概率优于市场隐含概率。" if beats_market else "学习后概率尚未优于市场隐含概率。",
                "current": 1 if beats_market else 0,
                "target": 1,
                "ratio": 1.0 if beats_market else 0.0,
            },
            {
                "key": "candidate_threshold",
                "label": "候选门槛",
                "status": "ok" if threshold_ready_count > 0 else "warning",
                "title": "有候选过线" if threshold_ready_count > 0 else "暂无候选过线",
                "detail": f"当前纸面信号 {paper_signal_count} 场，其中 {threshold_ready_count} 场满足概率、边际和赔率门槛。",
                "current": threshold_ready_count,
                "target": 1,
                "ratio": 1.0 if threshold_ready_count > 0 else 0.0,
            },
            {
                "key": "snapshot_coverage",
                "label": "赔率快照",
                "status": "ok" if missing_snapshot_count == 0 else "warning",
                "title": "快照就绪" if missing_snapshot_count == 0 else "仍缺快照",
                "detail": f"{missing_snapshot_count} 场纸面信号缺少多公司赔率快照。",
                "current": max(0, paper_signal_count - missing_snapshot_count),
                "target": paper_signal_count,
                "ratio": _dashboard_ratio(max(0, paper_signal_count - missing_snapshot_count), paper_signal_count) if paper_signal_count else 1.0,
            },
        ]
    )
    return {
        "status": status,
        "formal_enabled": formal_enabled,
        "severity": severity,
        "title": title,
        "detail": detail,
        "sample_count": sample_count,
        "min_sample_count": min_sample_count,
        "hit_rate": round_metric(hit_rate),
        "roi": round_metric(roi, 4),
        "signal_settled_count": signal_sample_count,
        "signal_hit_rate": round_metric(signal_hit_rate),
        "signal_roi": round_metric(signal_roi, 4),
        "min_signal_sample_count": min_signal_sample_count,
        "negative_segment_blocked_count": negative_segment_blocked_count,
        "negative_segment_blockers": _dashboard_quality_blocker_summary(negative_segment_blockers)[:6],
        "learning_improved": learning_improved,
        "beats_market": beats_market,
        "prediction_policy": "always_predict_and_backtest",
        "gates": gates,
    }


def _dashboard_recommendation_opportunity(
    rows: list[dict[str, Any]],
    *,
    strategy_state: dict[str, Any],
    candidate_filters: list[dict[str, Any]],
    learning_effectiveness: dict[str, Any] | None = None,
    prediction_quality: dict[str, Any] | None = None,
) -> dict[str, Any]:
    calibration_health = (
        learning_effectiveness.get("calibration_health")
        if isinstance(learning_effectiveness, dict) and isinstance(learning_effectiveness.get("calibration_health"), dict)
        else {}
    )
    shadow_recalibration = (
        learning_effectiveness.get("shadow_recalibration")
        if isinstance(learning_effectiveness, dict) and isinstance(learning_effectiveness.get("shadow_recalibration"), dict)
        else {}
    )
    candidate_band_keys = {
        str(key)
        for key in (calibration_health.get("candidate_band_keys") or [])
        if str(key)
    }
    current_rows = [row for row in rows if row.get("settlement_status") == "open"]
    formal_rows = [row for row in current_rows if row.get("prediction_type") == "recommendation"]
    paper_rows = [row for row in current_rows if row.get("prediction_type") == "observation"]
    signal_rows = [
        row
        for row in paper_rows
        if str(row.get("recommendation") or "") in _DASHBOARD_SIGNAL_RECOMMENDATIONS
    ]
    quality_segment_map = _dashboard_prediction_quality_segment_map(prediction_quality)
    negative_segment_blockers_by_ledger = {
        str(row.get("ledger_id") or id(row)): blocker
        for row in signal_rows
        if (
            blocker := _dashboard_negative_quality_segment_blocker(row, quality_segment_map)
        )
    }
    eligible_signal_rows = [
        row
        for row in signal_rows
        if str(row.get("ledger_id") or id(row)) not in negative_segment_blockers_by_ledger
    ]
    negative_segment_blockers = list(negative_segment_blockers_by_ledger.values())
    historical_signal_rows = [
        row
        for row in rows
        if row.get("prediction_type") == "observation"
        and row.get("settlement_status") != "open"
        and str(row.get("recommendation") or "") in _DASHBOARD_SIGNAL_RECOMMENDATIONS
    ]
    signal_backtest = _dashboard_backtest_segment(historical_signal_rows)
    threshold_ready_rows = [row for row in eligible_signal_rows if _dashboard_row_threshold_ready(row)]
    counter_signal_rows = [
        row
        for row in paper_rows
        if str(row.get("recommendation") or "") == "no_value"
        and _dashboard_probability_band_key(parse_float(row.get("learned_probability"))) in candidate_band_keys
    ]
    reason_counts = {
        str(group.get("reason") or "observed_not_recommended"): int(group.get("count") or 0)
        for group in candidate_filters
    }
    reanalysis_backlog_count = int(reason_counts.get("awaiting_reanalysis_after_snapshot") or 0)
    missing_snapshot_count = int(reason_counts.get("multi_bookmaker_snapshot_missing") or 0)
    no_value_count = sum(1 for row in current_rows if str(row.get("recommendation") or "") == "no_value")
    top_blockers = [
        {"reason": reason, "count": count}
        for reason, count in sorted(reason_counts.items(), key=lambda item: (-item[1], item[0]))[:6]
    ]

    if formal_rows:
        status = "formal_recommendations_available"
        severity = "ok"
        title = "已有正式推荐"
        detail = f"当前有 {len(formal_rows)} 场正式推荐，同时保留 {len(paper_rows)} 场纸面预测用于回测。"
    elif signal_rows:
        status = "paper_signals_pending"
        severity = "warning"
        title = "有纸面信号，尚未升为正式推荐"
        detail = (
            f"{len(signal_rows)} 场纸面信号已进入回测台账，其中 "
            f"{reanalysis_backlog_count} 场赔率补齐后等待复算，"
            f"{len(threshold_ready_rows)} 场已满足当前概率/边际/赔率门槛。"
        )
    elif counter_signal_rows:
        status = "counter_calibration_watchlist"
        severity = "warning"
        title = "发现反向校准观察样本"
        detail = (
            f"当前 {len(counter_signal_rows)} 场落在历史表现较好的低概率分桶；"
            "这只作为反向校准纸面观察，不作为正式推荐。"
        )
    elif rows:
        status = "no_positive_opportunity"
        severity = "info"
        title = "暂无正向推荐机会"
        detail = f"当前 {len(current_rows)} 场仍在等待赛果并进入回测台账，但没有达到正向边际或推荐动作。"
    else:
        status = "no_predictions"
        severity = "warning"
        title = "暂无预测样本"
        detail = "自动学习循环还没有写入预测样本。"

    candidates = sorted(
        eligible_signal_rows,
        key=lambda row: (
            1 if _dashboard_row_threshold_ready(row) else 0,
            parse_float(row.get("edge")) or -999.0,
            parse_float(row.get("learned_probability")) or -999.0,
            str(row.get("created_at_utc") or ""),
        ),
        reverse=True,
    )
    return {
        "status": status,
        "severity": severity,
        "title": title,
        "detail": detail,
        "formal_count": len(formal_rows),
        "paper_count": len(paper_rows),
        "paper_signal_count": len(signal_rows),
        "counter_signal_count": len(counter_signal_rows),
        "current_open_count": len(current_rows),
        "historical_paper_signal_count": len(historical_signal_rows),
        "settled_signal_count": len(historical_signal_rows),
        "no_value_count": no_value_count,
        "threshold_ready_count": len(threshold_ready_rows),
        "negative_segment_blocked_count": len(negative_segment_blockers),
        "negative_segment_blockers": _dashboard_quality_blocker_summary(negative_segment_blockers)[:6],
        "reanalysis_backlog_count": reanalysis_backlog_count,
        "missing_snapshot_count": missing_snapshot_count,
        "gate_thresholds": {
            "min_calibrated_probability": round_metric(parse_float(strategy_state.get("min_calibrated_probability"))),
            "min_value_edge": round_metric(parse_float(strategy_state.get("min_value_edge"))),
            "min_decimal_odds": round_metric(parse_float(strategy_state.get("min_decimal_odds")), 4),
            "max_decimal_odds": round_metric(parse_float(strategy_state.get("max_decimal_odds")), 4),
        },
        "release_gate": _dashboard_recommendation_release_gate(
            strategy_state,
            learning_effectiveness=learning_effectiveness,
            calibration_health=calibration_health,
            paper_signal_count=len(signal_rows),
            counter_signal_count=len(counter_signal_rows),
            threshold_ready_count=len(threshold_ready_rows),
            missing_snapshot_count=missing_snapshot_count,
            signal_backtest=signal_backtest,
            negative_segment_blocked_count=len(negative_segment_blockers),
            negative_segment_blockers=negative_segment_blockers,
        ),
        "top_blockers": top_blockers,
        "top_candidates": [_dashboard_opportunity_candidate(row) for row in candidates[:6]],
        "counter_signal_rule": {
            "status": calibration_health.get("status") or "",
            "title": calibration_health.get("title") or "",
            "detail": calibration_health.get("detail") or "",
            "candidate_band_keys": sorted(candidate_band_keys),
            "meta_model": calibration_health.get("meta_model") or {},
            "shadow_recalibration": {
                "status": shadow_recalibration.get("status") or "",
                "method": shadow_recalibration.get("method") or "",
                "quality": shadow_recalibration.get("quality") or {},
                "validation": shadow_recalibration.get("validation") or {},
            },
        },
        "counter_signal_candidates": [
            _dashboard_counter_signal_candidate(row, calibration_health, shadow_recalibration)
            for row in sorted(
                counter_signal_rows,
                key=lambda row: (
                    parse_float(row.get("decimal_odds")) or 0.0,
                    str(row.get("created_at_utc") or ""),
                ),
                reverse=True,
            )[:6]
        ],
    }


def _dashboard_contract_section(
    key: str,
    label: str,
    status: str,
    title: str,
    detail: str,
    *,
    current: int | float | None = None,
    target: int | float | None = None,
    ratio: float | None = None,
    required: bool = True,
    frontend_visible: bool = True,
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "status": status,
        "title": title,
        "detail": detail,
        "current": round_metric(current, 6) if isinstance(current, float) else current,
        "target": round_metric(target, 6) if isinstance(target, float) else target,
        "ratio": ratio,
        "required": required,
        "frontend_visible": frontend_visible,
    }


def _dashboard_contract_status(sections: list[dict[str, Any]]) -> str:
    statuses = {str(section.get("status") or "") for section in sections if section.get("required", True)}
    if "missing" in statuses or "error" in statuses:
        return "error"
    if "blocked" in statuses or "warning" in statuses:
        return "warning"
    if "info" in statuses:
        return "info"
    return "ok"


def _dashboard_contract_health(
    *,
    prediction_kpis: dict[str, Any],
    learning_effectiveness: dict[str, Any],
    prediction_quality: dict[str, Any],
    adaptive_learning_plan: dict[str, Any],
    recommendation_opportunity: dict[str, Any],
    market_snapshot_summary: dict[str, Any],
    context_coverage: dict[str, Any],
) -> dict[str, Any]:
    total_predictions = int(prediction_kpis.get("total_count") or 0)
    settled_count = int(prediction_kpis.get("settled_count") or 0)
    open_count = int(prediction_kpis.get("open_count") or 0)
    release_gate = recommendation_opportunity.get("release_gate") if isinstance(recommendation_opportunity.get("release_gate"), dict) else {}
    formal_enabled = bool(release_gate.get("formal_enabled"))
    snapshot_count = int(market_snapshot_summary.get("total_snapshot_count") or 0)
    snapshot_event_count = int(market_snapshot_summary.get("event_count") or 0)
    context_total = int(context_coverage.get("total_count") or 0)
    context_fields = context_coverage.get("fields") if isinstance(context_coverage.get("fields"), list) else []
    context_available = sum(int(field.get("available_count") or 0) for field in context_fields if isinstance(field, dict))
    context_possible = max(0, context_total * max(1, len(context_fields))) if context_fields else 0
    context_ratio = _dashboard_ratio(context_available, context_possible) if context_possible else None
    release_gate_status = str(release_gate.get("status") or "")
    gate_blocked = any(
        str(gate.get("status") or "") == "blocked"
        for gate in (release_gate.get("gates") or [])
        if isinstance(gate, dict)
    )
    recommendation_status = (
        "ok"
        if formal_enabled
        else "blocked"
        if gate_blocked and settled_count > 0
        else "warning"
    )
    sections = [
        _dashboard_contract_section(
            "prediction_policy",
            "预测策略",
            "ok" if total_predictions > 0 else "warning",
            "持续预测回测",
            "正式推荐暂停时仍生成纸面预测，并持续进入结算回测。",
            current=total_predictions,
            target=1,
            ratio=1.0 if total_predictions > 0 else 0.0,
        ),
        _dashboard_contract_section(
            "prediction_ledger",
            "预测台账",
            "ok" if total_predictions > 0 else "missing",
            "台账已对齐" if total_predictions > 0 else "台账为空",
            f"前端可读取 {total_predictions} 条预测，其中 {open_count} 条等待赛果、{settled_count} 条已回测。",
            current=total_predictions,
            target=1,
            ratio=1.0 if total_predictions > 0 else 0.0,
        ),
        _dashboard_contract_section(
            "settlement_backtest",
            "回测结算",
            "ok" if settled_count >= 20 else "info" if settled_count > 0 else "warning",
            "回测样本可用" if settled_count > 0 else "等待首批回测",
            f"已回测 {settled_count} 场，{open_count} 场等待赛果；20 场以上才适合打开稳定推荐闸门。",
            current=settled_count,
            target=20,
            ratio=_dashboard_ratio(settled_count, 20),
        ),
        _dashboard_contract_section(
            "learning_effectiveness",
            "学习效果",
            str(learning_effectiveness.get("severity") or "warning"),
            str(learning_effectiveness.get("title") or "等待学习评估"),
            str(learning_effectiveness.get("detail") or "后端未返回学习效果说明。"),
            current=int(learning_effectiveness.get("sample_count") or 0),
            target=20,
            ratio=_dashboard_ratio(int(learning_effectiveness.get("sample_count") or 0), 20),
        ),
        _dashboard_contract_section(
            "prediction_quality",
            "预测质量",
            str(prediction_quality.get("severity") or "warning"),
            str(prediction_quality.get("title") or "等待质量分段"),
            str(prediction_quality.get("detail") or "后端未返回预测质量分组。"),
            current=int((prediction_quality.get("summary") or {}).get("settled_count") or 0),
            target=20,
            ratio=_dashboard_ratio(int((prediction_quality.get("summary") or {}).get("settled_count") or 0), 20),
        ),
        _dashboard_contract_section(
            "adaptive_learning_plan",
            "自学习修正",
            str(adaptive_learning_plan.get("severity") or "warning"),
            str(adaptive_learning_plan.get("title") or "等待修正计划"),
            str(adaptive_learning_plan.get("detail") or "后端未返回自学习修正动作。"),
            current=int((adaptive_learning_plan.get("summary") or {}).get("action_count") or 0),
            target=1,
            ratio=1.0 if int((adaptive_learning_plan.get("summary") or {}).get("action_count") or 0) > 0 else 0.0,
        ),
        _dashboard_contract_section(
            "recommendation_gate",
            "正式推荐闸门",
            recommendation_status,
            str(release_gate.get("title") or "等待推荐闸门"),
            (
                f"{release_gate.get('detail') or '后端未返回推荐闸门说明'}"
                " 当前策略仍继续预测并回测，不会因为暂停正式推荐而停止验证准确率。"
            ),
            current=1 if formal_enabled else 0,
            target=1,
            ratio=1.0 if formal_enabled else 0.0,
        ),
        _dashboard_contract_section(
            "odds_snapshots",
            "赔率快照",
            "ok" if snapshot_count > 0 else "warning",
            "快照已入库" if snapshot_count > 0 else "等待赔率快照",
            f"本地赔率快照 {snapshot_count} 条，覆盖 {snapshot_event_count} 场。",
            current=snapshot_count,
            target=1,
            ratio=1.0 if snapshot_count > 0 else 0.0,
        ),
        _dashboard_contract_section(
            "context_coverage",
            "赛事情报",
            "ok" if context_ratio is not None and context_ratio > 0 else "warning",
            "情报字段已对齐" if context_ratio is not None and context_ratio > 0 else "等待情报字段",
            str(context_coverage.get("summary") or "暂无赛事情报覆盖统计。"),
            current=context_available,
            target=context_possible or None,
            ratio=context_ratio,
        ),
    ]
    status = _dashboard_contract_status(sections)
    required_sections = [section for section in sections if section.get("required", True)]
    missing_count = sum(1 for section in required_sections if section.get("status") == "missing")
    warning_count = sum(1 for section in required_sections if section.get("status") == "warning")
    blocked_count = sum(1 for section in required_sections if section.get("status") == "blocked")
    ok_count = sum(1 for section in required_sections if section.get("status") == "ok")
    return {
        "contract_version": "dashboard_contract_v1",
        "status": status,
        "severity": status,
        "title": "数据契约已对齐" if missing_count == 0 else "数据契约缺字段",
        "detail": (
            f"前端必需 {len(required_sections)} 个模块，缺失 {missing_count} 个；"
            f"正式推荐{'已开放' if formal_enabled else '未开放'}，预测与回测策略保持开启。"
        ),
        "policy": {
            "prediction_policy": "always_predict_and_backtest",
            "formal_recommendation_enabled": formal_enabled,
            "release_gate_status": release_gate_status,
            "read_only": True,
        },
        "summary": {
            "required_count": len(required_sections),
            "ok_count": ok_count,
            "warning_count": warning_count,
            "blocked_count": blocked_count,
            "missing_required_count": missing_count,
            "frontend_visible_count": sum(1 for section in sections if section.get("frontend_visible")),
        },
        "sections": sections,
    }


def _dashboard_record_model_engine(record: dict[str, Any]) -> dict[str, Any]:
    raw = record.get("raw") if isinstance(record.get("raw"), dict) else {}
    candidate_paths = (
        ("model_engine",),
        ("model_card", "model_engine"),
        ("professional_scorecard", "model_inputs", "model_engine"),
        ("professional_scorecard", "agent_brief", "model_engine"),
        ("betting_decision_support", "model_engine"),
        ("analysis_pack", "model_engine"),
    )
    for path in candidate_paths:
        value = _dashboard_get_path(raw, path)
        if isinstance(value, dict) and value:
            return value
    return _dashboard_legacy_candidate_model_engine(record, raw)


def _dashboard_legacy_candidate_model_engine(record: dict[str, Any], raw: dict[str, Any]) -> dict[str, Any]:
    best = raw.get("best_candidate") if isinstance(raw.get("best_candidate"), dict) else {}
    if not best:
        return {}

    probability_source = str(best.get("probability_source") or "")
    edge_source = str(best.get("edge_source") or "")
    has_model_probability = parse_float(best.get("model_probability")) is not None
    if edge_source != "model_engine" and "Dixon-Coles" not in probability_source and not has_model_probability:
        return {}

    market = str(best.get("market") or record.get("market") or "")
    fitted_targets = {
        "moneyline_1x2": market in {"1x2", "jingcai_had", "jingcai_hhad"},
        "asian_handicap": market == "asian_handicap",
        "over_under": market == "over_under",
        "side_neutrality_prior": False,
    }
    if not any(fitted_targets.values()) and parse_float(best.get("market_probability")) is not None:
        fitted_targets["asian_handicap"] = str(record.get("market") or "") == "asian_handicap"

    dixon_coles = {
        "rho_source": "not_persisted_legacy_candidate",
        "low_score_adjustment": "Dixon-Coles" in probability_source,
        "historical_rho": {},
    }
    return {
        "available": True,
        "version": "legacy_shortlist_candidate_summary",
        "method": model_engine.MODEL_ENGINE_METHOD,
        "dixon_coles": dixon_coles,
        "fitted_market_targets": fitted_targets,
        "model_quality": {
            "fallback_used": False,
            "evidence_scope": "legacy_best_candidate",
            "limits": [
                "This legacy row predates compact model_engine persistence; dashboard governance inferred model usage from the stored best_candidate summary.",
                "Historical rho and expected-goal internals are unavailable for this row unless the compact model_engine object was persisted.",
            ],
        },
        "probability_source": probability_source or "stored best_candidate model_probability",
    }


def _dashboard_model_governance_check(
    key: str,
    label: str,
    status: str,
    title: str,
    detail: str,
    *,
    current: int | float | None = None,
    target: int | float | None = None,
) -> dict[str, Any]:
    ratio = None
    if current is not None and target not in (None, 0):
        try:
            ratio = max(0.0, min(float(current) / float(target), 1.0))
        except (TypeError, ValueError, ZeroDivisionError):
            ratio = None
    return {
        "key": key,
        "label": label,
        "status": status,
        "title": title,
        "detail": detail,
        "current": round_metric(current, 6) if isinstance(current, float) else current,
        "target": round_metric(target, 6) if isinstance(target, float) else target,
        "ratio": round_metric(ratio, 6),
    }


def _dashboard_model_governance(
    records: list[dict[str, Any]],
    *,
    learning_effectiveness: dict[str, Any],
    clv_tracking: dict[str, Any],
) -> dict[str, Any]:
    model_rows = []
    for record in records:
        engine = _dashboard_record_model_engine(record)
        if engine:
            model_rows.append((record, engine))

    record_count = len(records)
    model_engine_count = len(model_rows)
    available_count = sum(1 for _record, engine in model_rows if bool(engine.get("available", True)))
    method_counts = Counter(str(engine.get("method") or "unknown") for _record, engine in model_rows)
    version_counts = Counter(str(engine.get("version") or "unknown") for _record, engine in model_rows)
    rho_source_counts: Counter[str] = Counter()
    rho_values: list[float] = []
    historical_rho_values: list[float] = []
    historical_sample_counts: list[int] = []
    market_anchor_count = 0
    fallback_count = 0
    for _record, engine in model_rows:
        dixon_coles = engine.get("dixon_coles") if isinstance(engine.get("dixon_coles"), dict) else {}
        rho_source = str(dixon_coles.get("rho_source") or "unknown")
        rho_source_counts[rho_source] += 1
        rho_value = parse_float(dixon_coles.get("rho"))
        if rho_value is not None:
            rho_values.append(rho_value)
        historical_rho = dixon_coles.get("historical_rho") if isinstance(dixon_coles.get("historical_rho"), dict) else {}
        historical_value = parse_float(historical_rho.get("rho"))
        if historical_value is not None:
            historical_rho_values.append(historical_value)
        historical_sample_count = int(historical_rho.get("sample_count") or 0)
        if historical_sample_count > 0:
            historical_sample_counts.append(historical_sample_count)
        fitted_targets = engine.get("fitted_market_targets") if isinstance(engine.get("fitted_market_targets"), dict) else {}
        if any(bool(value) for value in fitted_targets.values()):
            market_anchor_count += 1
        quality = engine.get("model_quality") if isinstance(engine.get("model_quality"), dict) else {}
        if bool(quality.get("fallback_used")):
            fallback_count += 1

    historical_rho_count = len(historical_rho_values)
    calibration_sample_count = int(learning_effectiveness.get("sample_count") or 0)
    learning_improved = bool(learning_effectiveness.get("learning_improved"))
    beats_market = bool(learning_effectiveness.get("beats_market"))
    probability_governance = (
        learning_effectiveness.get("probability_governance")
        if isinstance(learning_effectiveness.get("probability_governance"), dict)
        else {}
    )
    shadow_recalibration = (
        learning_effectiveness.get("shadow_recalibration")
        if isinstance(learning_effectiveness.get("shadow_recalibration"), dict)
        else {}
    )
    shadow_quality = shadow_recalibration.get("quality") if isinstance(shadow_recalibration.get("quality"), dict) else {}
    clv_available_count = int(clv_tracking.get("available_count") or 0)
    clv_tracked_count = int(clv_tracking.get("tracked_count") or 0)
    avg_clv_return = parse_float(clv_tracking.get("avg_clv_return"))
    positive_clv_rate = parse_float(clv_tracking.get("positive_clv_rate"))

    rho_status = "ok" if historical_rho_count > 0 else "warning" if model_engine_count > 0 else "missing"
    calibration_status = (
        "ok"
        if calibration_sample_count >= 20 and learning_improved and beats_market
        else "warning"
        if calibration_sample_count > 0
        else "missing"
    )
    clv_status = "ok" if clv_available_count > 0 else "warning" if clv_tracked_count > 0 else "missing"
    checks = [
        _dashboard_model_governance_check(
            "dixon_coles_rho",
            "Dixon-Coles rho",
            rho_status,
            "历史联赛 rho 已接入" if historical_rho_count > 0 else "等待历史 rho 样本" if model_engine_count > 0 else "未发现模型证据",
            (
                f"{historical_rho_count}/{model_engine_count} 条模型记录使用历史联赛 MLE rho；"
                f"其余记录继续使用盘口网格拟合。"
                if model_engine_count
                else "台账样本尚未持久化模型引擎输出。"
            ),
            current=historical_rho_count,
            target=max(1, model_engine_count),
        ),
        _dashboard_model_governance_check(
            "market_anchoring",
            "盘口锚定",
            "ok" if market_anchor_count > 0 else "warning" if model_engine_count > 0 else "missing",
            "模型读取盘口目标" if market_anchor_count > 0 else "盘口目标不足",
            f"{market_anchor_count}/{model_engine_count} 条模型记录带有 1X2、亚盘或大小球盘口锚定。",
            current=market_anchor_count,
            target=max(1, model_engine_count),
        ),
        _dashboard_model_governance_check(
            "holdout_calibration",
            "样本外校准",
            calibration_status,
            "校准通过发布评估" if calibration_status == "ok" else "校准仍在验证",
            (
                f"已结算可评估样本 {calibration_sample_count} 场；"
                f"学习改善：{'是' if learning_improved else '否'}；市场基准：{'已跑赢' if beats_market else '未跑赢'}。"
                "历史回测工具使用留出集分桶校准，实时面板展示当前样本的走步/分桶校准状态。"
            ),
            current=calibration_sample_count,
            target=20,
        ),
        _dashboard_model_governance_check(
            "clv_tracking",
            "CLV 追踪",
            clv_status,
            "已追踪收盘价" if clv_available_count > 0 else "等待收盘价对齐",
            (
                f"{clv_available_count}/{clv_tracked_count} 条可计算收盘价价值；"
                f"平均 CLV {_percent_text(avg_clv_return) or '暂无'}，正 CLV {_percent_text(positive_clv_rate) or '暂无'}。"
            ),
            current=clv_available_count,
            target=max(1, clv_tracked_count),
        ),
    ]
    blocked_or_missing = sum(1 for item in checks if item["status"] in {"blocked", "missing"})
    warning_count = sum(1 for item in checks if item["status"] == "warning")
    if model_engine_count <= 0:
        status = "model_evidence_missing"
        severity = "warning"
        title = "模型证据待入库"
        detail = "当前台账没有可解析的模型引擎输出，无法审计 rho、盘口锚定和模型降级情况。"
    elif blocked_or_missing:
        status = "professional_audit_collecting"
        severity = "warning"
        title = "专业模型审计采集中"
        detail = "Dixon-Coles、校准和 CLV 审计已经接入，但部分样本还缺少历史 rho 或收盘价证据。"
    elif warning_count:
        status = "professional_audit_watch"
        severity = "warning"
        title = "专业模型审计观察中"
        detail = "模型引擎证据已入库，仍需更多历史样本、校准样本或 CLV 样本通过发布评估。"
    else:
        status = "professional_audit_ready"
        severity = "ok"
        title = "专业模型审计已接入"
        detail = "历史 rho、校准评估、市场基准和 CLV 追踪均有可审计样本。"

    return {
        "status": status,
        "severity": severity,
        "title": title,
        "detail": detail,
        "summary": {
            "record_count": record_count,
            "model_engine_count": model_engine_count,
            "model_available_count": available_count,
            "historical_rho_count": historical_rho_count,
            "market_anchor_count": market_anchor_count,
            "fallback_count": fallback_count,
            "calibration_sample_count": calibration_sample_count,
            "clv_tracked_count": clv_tracked_count,
            "clv_available_count": clv_available_count,
            "avg_clv_return": round_metric(avg_clv_return, 6),
            "positive_clv_rate": round_metric(positive_clv_rate, 6),
        },
        "rho": {
            "source_counts": dict(rho_source_counts),
            "avg_rho": round_metric(_dashboard_average(rho_values), 6),
            "historical_avg_rho": round_metric(_dashboard_average(historical_rho_values), 6),
            "historical_avg_sample_count": round_metric(_dashboard_average(historical_sample_counts), 2),
        },
        "calibration": {
            "status": learning_effectiveness.get("status") or "",
            "title": learning_effectiveness.get("title") or "",
            "detail": learning_effectiveness.get("detail") or "",
            "sample_count": calibration_sample_count,
            "learning_improved": learning_improved,
            "beats_market": beats_market,
            "active_probability_source": probability_governance.get("active_source_label") or "",
            "shadow_method": shadow_recalibration.get("method") or "",
            "shadow_status": shadow_recalibration.get("status") or "",
            "walk_forward_sample_count": int(shadow_quality.get("walk_forward_sample_count") or 0),
            "walk_forward_brier_delta": shadow_quality.get("walk_forward_brier_delta"),
        },
        "clv": {
            "status": clv_tracking.get("status") or "",
            "available_count": clv_available_count,
            "positive_clv_rate": round_metric(positive_clv_rate, 6),
            "avg_clv_return": round_metric(avg_clv_return, 6),
        },
        "method_counts": dict(method_counts),
        "version_counts": dict(version_counts),
        "checks": checks,
        "rule": "模型审计只读取已入库的 compact model_engine、旧样本候选级模型摘要、结算校准指标和赔率快照，不会创建新的推荐信号。",
    }


def _dashboard_production_readiness(
    *,
    prediction_kpis: dict[str, Any],
    learning_effectiveness: dict[str, Any],
    recommendation_opportunity: dict[str, Any],
    dashboard_contract: dict[str, Any],
    clv_tracking: dict[str, Any] | None = None,
) -> dict[str, Any]:
    total_predictions = int(prediction_kpis.get("total_count") or 0)
    settled_count = int(prediction_kpis.get("settled_count") or 0)
    open_count = int(prediction_kpis.get("open_count") or 0)
    hit_rate = parse_float(prediction_kpis.get("hit_rate"))
    roi = parse_float(prediction_kpis.get("roi"))
    learning_improved = bool(learning_effectiveness.get("learning_improved"))
    beats_market = bool(learning_effectiveness.get("beats_market"))
    release_gate = recommendation_opportunity.get("release_gate") if isinstance(recommendation_opportunity.get("release_gate"), dict) else {}
    formal_enabled = bool(release_gate.get("formal_enabled"))
    release_gate_items = [
        gate for gate in (release_gate.get("gates") or [])
        if isinstance(gate, dict)
    ]
    shadow_walk_gate = next(
        (gate for gate in release_gate_items if str(gate.get("key") or "") == "shadow_walk_forward"),
        None,
    )
    shadow_walk_blocked = bool(shadow_walk_gate and str(shadow_walk_gate.get("status") or "") == "blocked")
    contract_status = str(dashboard_contract.get("status") or "")
    contract_ok = contract_status not in {"error", "missing"}
    clv_required = clv_tracking is not None
    clv_available_count = int((clv_tracking or {}).get("available_count") or 0)
    clv_tracked_count = int((clv_tracking or {}).get("tracked_count") or 0)
    avg_clv_return = parse_float((clv_tracking or {}).get("avg_clv_return"))
    positive_clv_rate = parse_float((clv_tracking or {}).get("positive_clv_rate"))
    # Stricter CLV gate: not just "non-negative" but "demonstrably positive"
    # CLV is the strongest leading indicator of true model edge
    # - 30+ samples (was 20; lower variance threshold)
    # - avg CLV >= +0.5% (was 0)
    # - positive_clv_rate >= 55% (was 50%)
    clv_ready = bool(
        clv_available_count >= 30
        and avg_clv_return is not None
        and avg_clv_return >= 0.005
        and positive_clv_rate is not None
        and positive_clv_rate >= 0.55
    )
    is_empty_loop = total_predictions <= 0
    production_ready = bool(
        total_predictions > 0
        and settled_count >= 20
        and learning_improved
        and beats_market
        and (roi is not None and roi >= 0)
        and (not clv_required or clv_ready)
        and formal_enabled
        and not shadow_walk_blocked
        and contract_ok
    )

    def gate(
        key: str,
        label: str,
        status: str,
        title: str,
        detail: str,
        *,
        current: int | float | None = None,
        target: int | float | None = None,
        ratio: float | None = None,
    ) -> dict[str, Any]:
        return {
            "key": key,
            "label": label,
            "status": status,
            "title": title,
            "detail": detail,
            "current": round_metric(current, 6) if isinstance(current, float) else current,
            "target": round_metric(target, 6) if isinstance(target, float) else target,
            "ratio": ratio,
        }

    gates = [
        gate(
            "prediction_loop",
            "预测闭环",
            "ok" if total_predictions > 0 else "missing",
            "已持续预测" if total_predictions > 0 else "没有预测样本",
            f"台账共有 {total_predictions} 条预测；不推荐也必须落台账，才能后续回测。",
            current=total_predictions,
            target=1,
            ratio=1.0 if total_predictions > 0 else 0.0,
        ),
        gate(
            "backtest_sample",
            "回测样本",
            "ok" if settled_count >= 20 else "warning" if settled_count > 0 else "blocked",
            "回测样本可用" if settled_count >= 20 else "样本不足" if settled_count > 0 else "尚未回测",
            f"已结算 {settled_count} 场，等待赛果 {open_count} 场；生产推荐至少需要 20 场稳定样本。",
            current=settled_count,
            target=20,
            ratio=_dashboard_ratio(settled_count, 20),
        ),
        gate(
            "learning_effectiveness",
            "学习效果",
            "ok" if learning_improved else "blocked" if settled_count >= 20 else "warning",
            "学习优于原始模型" if learning_improved else "学习未证明有效",
            str(learning_effectiveness.get("detail") or "学习效果尚未返回。"),
            current=1 if learning_improved else 0,
            target=1,
            ratio=1.0 if learning_improved else 0.0,
        ),
        gate(
            "market_benchmark",
            "市场基准",
            "ok" if beats_market else "blocked" if settled_count >= 20 else "warning",
            "已跑赢市场" if beats_market else "尚未跑赢市场",
            "学习后概率必须至少优于市场隐含概率，才能进入正式推荐闸门。",
            current=1 if beats_market else 0,
            target=1,
            ratio=1.0 if beats_market else 0.0,
        ),
        gate(
            "paper_roi",
            "纸面收益",
            "ok" if roi is not None and roi >= 0 else "blocked" if settled_count >= 20 else "warning",
            "纸面收益非负" if roi is not None and roi >= 0 else "纸面收益为负",
            f"当前纸面收益率 {_percent_text(roi) or '暂无'}；负收益时只能继续采样或重训。",
            current=roi,
            target=0,
            ratio=None if roi is None else (1.0 if roi >= 0 else 0.0),
        ),
    ]
    if clv_required:
        if clv_ready:
            clv_status = "ok"
            clv_title = "CLV 验证通过 — 强信号"
        elif clv_available_count < 30:
            clv_status = "warning"
            clv_title = "CLV 样本积累中"
        elif avg_clv_return is None or avg_clv_return < 0.005:
            clv_status = "blocked"
            clv_title = "CLV 边际不足 — 模型可能没有真实优势"
        else:
            clv_status = "blocked"
            clv_title = "正 CLV 比例不足 55%"
        gates.append(
            gate(
                "closing_line_value",
                "CLV 收盘线价值（强信号）",
                clv_status,
                clv_title,
                (
                    f"已对齐 {clv_available_count}/{clv_tracked_count} 条收盘价；"
                    f"平均 CLV {_percent_text(avg_clv_return) or '暂无'}，"
                    f"正 CLV 比例 {_percent_text(positive_clv_rate) or '暂无'}。"
                    "CLV 是统计上最早出现的模型质量信号 — 生产发布要求 ≥30 条样本、"
                    "平均 CLV ≥ +0.5%、正 CLV 比例 ≥ 55%。"
                ),
                current=clv_available_count,
                target=30,
                ratio=_dashboard_ratio(clv_available_count, 30),
            )
        )
    if shadow_walk_gate:
        gates.append(
            gate(
                "shadow_walk_forward",
                "走步验证",
                str(shadow_walk_gate.get("status") or "warning"),
                str(shadow_walk_gate.get("title") or "影子模型走步验证"),
                str(shadow_walk_gate.get("detail") or "影子重校准模型需要通过走步验证后才能进入生产推荐。"),
                current=parse_float(shadow_walk_gate.get("current")),
                target=parse_float(shadow_walk_gate.get("target")),
                ratio=parse_float(shadow_walk_gate.get("ratio")),
            )
        )
    gates.extend(
        [
            gate(
                "recommendation_gate",
                "推荐闸门",
                "ok" if formal_enabled else "blocked" if settled_count >= 20 else "warning",
                "正式推荐开放" if formal_enabled else "正式推荐关闭",
                str(release_gate.get("detail") or "正式推荐闸门尚未开放。"),
                current=1 if formal_enabled else 0,
                target=1,
                ratio=1.0 if formal_enabled else 0.0,
            ),
            gate(
                "data_contract",
                "数据契约",
                "ok" if contract_ok else "blocked",
                "前后端契约可用" if contract_ok else "前后端契约缺失",
                str(dashboard_contract.get("detail") or "后端未返回数据契约。"),
                current=0 if contract_status == "error" else 1,
                target=1,
                ratio=1.0 if contract_ok else 0.0,
            ),
        ]
    )
    blocked_count = sum(1 for item in gates if item["status"] == "blocked")
    warning_count = sum(1 for item in gates if item["status"] == "warning")
    if is_empty_loop:
        status = "prediction_loop_empty"
        severity = "error"
        title = "预测闭环未启动"
        detail = "当前没有预测样本，既不能发布推荐信号，也无法进行回测验证。"
    elif production_ready:
        status = "production_candidate"
        severity = "ok"
        title = "可进入生产推荐候选"
        detail = (
            "预测、回测、学习效果、市场基准、收益、CLV 和推荐闸门均通过。"
            if clv_required
            else "预测、回测、学习效果、市场基准、收益和推荐闸门均通过。"
        )
    else:
        status = "paper_validation"
        severity = "warning" if blocked_count else "info"
        title = "预测闭环运行中，未达推荐发布标准"
        detail = (
            f"已有 {total_predictions} 条预测和 {settled_count} 条回测；"
            f"但仍有 {blocked_count} 个阻断项、{warning_count} 个观察项，正式推荐应保持关闭。"
        )
    return {
        "status": status,
        "severity": severity,
        "title": title,
        "detail": detail,
        "is_toy": is_empty_loop,
        "is_empty_loop": is_empty_loop,
        "production_ready": production_ready,
        "recommended_action": (
            "start_prediction_loop"
            if is_empty_loop
            else "allow_formal_recommendations"
            if production_ready
            else "continue_paper_validation_or_retrain"
        ),
        "summary": {
            "prediction_total": total_predictions,
            "settled_count": settled_count,
            "open_count": open_count,
            "hit_rate": round_metric(hit_rate),
            "roi": round_metric(roi, 4),
            "learning_improved": learning_improved,
            "beats_market": beats_market,
            "clv_available_count": clv_available_count if clv_required else None,
            "clv_tracked_count": clv_tracked_count if clv_required else None,
            "avg_clv_return": round_metric(avg_clv_return) if clv_required else None,
            "positive_clv_rate": round_metric(positive_clv_rate) if clv_required else None,
            "clv_ready": clv_ready if clv_required else None,
            "formal_recommendation_enabled": formal_enabled,
            "blocked_count": blocked_count,
            "warning_count": warning_count,
        },
        "gates": gates,
    }


def _dashboard_profitability_forecast(
    *,
    prediction_kpis: dict[str, Any],
    strategy_state: dict[str, Any],
    clv_tracking: dict[str, Any],
) -> dict[str, Any]:
    """Project how many more bets/days are needed to statistically prove profitability."""
    from football_data_mcp.profitability_calculator import (
        EdgeAssumptions,
        required_bets_bayesian,
        implied_roi,
    )

    settled_count = int(prediction_kpis.get("settled_count") or 0)
    hit_rate = parse_float(prediction_kpis.get("hit_rate")) or 0.55
    avg_odds = 1.85  # default working assumption
    if (strategy_state or {}).get("min_decimal_odds") and (strategy_state or {}).get("max_decimal_odds"):
        avg_odds = (
            float(strategy_state["min_decimal_odds"]) + float(strategy_state["max_decimal_odds"])
        ) / 2

    # Estimate settled bets per day based on recent rate
    settled_per_day = max(1, min(20, int(settled_count / max(7, 1))))  # rough fallback

    # If we have CLV samples, use that as proxy for settlement velocity
    clv_summary = (clv_tracking or {}).get("summary") or {}
    if clv_summary.get("sample_count"):
        # CLV samples roughly track settled count - normalize to per-day rate
        sample_count = int(clv_summary.get("sample_count") or 0)
        if sample_count >= 5:
            # If we have N samples over (recent history), assume span is ~30 days
            settled_per_day = max(1, min(20, int(sample_count / 30)))

    if settled_count >= 5 and hit_rate > 0:
        # Compute implied ROI before deciding what scenario to forecast
        observed_roi_per_bet = implied_roi(hit_rate, avg_odds)

        # Critical: if observed ROI is non-positive, the model is currently
        # losing money. Don't try to "forecast time to profitability" —
        # there's no statistical path from here.
        if observed_roi_per_bet <= 0:
            return {
                "available": True,
                "model_state": "losing",
                "method": "diagnostic_only",
                "observed_hit_rate": round(hit_rate, 4),
                "assumed_avg_odds": round(avg_odds, 3),
                "implied_roi_per_bet": round(observed_roi_per_bet, 4),
                "settled_per_day_estimate": settled_per_day,
                "settled_bets_so_far": settled_count,
                "required_bets_total": None,
                "remaining_bets": None,
                "remaining_days": None,
                "confidence_level": 0.95,
                "break_even_hit_rate_needed": round(1.0 / avg_odds, 4),
                "hit_rate_gap": round((1.0 / avg_odds) - hit_rate, 4),
                "interpretation": (
                    f"模型当前在亏损（命中率 {hit_rate*100:.1f}% < 盈亏平衡线 "
                    f"{100.0/avg_odds:.1f}%）。无法证明盈利路径——需要先改进模型，"
                    f"而不是积累更多样本。建议：重跑 holdout validation 检查 log-loss vs market。"
                ),
            }

        edge = EdgeAssumptions(
            true_win_rate=max(0.51, min(0.70, hit_rate)),
            average_decimal_odds=avg_odds,
            bets_per_cycle=1,
            cycles_per_day=settled_per_day,
        )
        forecast = required_bets_bayesian(edge)
        # Cap absurd values: if N > 100000, the edge is too small to forecast
        if forecast.required_bets > 100000:
            return {
                "available": True,
                "model_state": "marginal_edge",
                "method": "edge_too_small_to_forecast",
                "observed_hit_rate": round(hit_rate, 4),
                "assumed_avg_odds": round(avg_odds, 3),
                "implied_roi_per_bet": round(observed_roi_per_bet, 4),
                "settled_per_day_estimate": settled_per_day,
                "settled_bets_so_far": settled_count,
                "required_bets_total": None,
                "remaining_bets": None,
                "remaining_days": None,
                "confidence_level": 0.95,
                "interpretation": (
                    f"边际过小（命中率 {hit_rate*100:.1f}%，仅略高于平衡线）。"
                    f"统计上需要 >100000 笔才能证明，远超合理时间窗口。"
                ),
            }

        remaining_bets = max(0, forecast.required_bets - settled_count)
        remaining_days = (
            round(remaining_bets / settled_per_day, 1) if settled_per_day else None
        )
        return {
            "available": True,
            "model_state": "profitable",
            "method": "bayesian_beta_binomial_v1",
            "observed_hit_rate": round(hit_rate, 4),
            "assumed_avg_odds": round(avg_odds, 3),
            "implied_roi_per_bet": round(observed_roi_per_bet, 4),
            "settled_per_day_estimate": settled_per_day,
            "required_bets_total": forecast.required_bets,
            "settled_bets_so_far": settled_count,
            "remaining_bets": remaining_bets,
            "remaining_days": remaining_days,
            "confidence_level": forecast.confidence_level,
            "notes": forecast.notes,
            "interpretation": (
                "已达到统计置信度。可以暂停验证。"
                if remaining_bets == 0
                else f"按当前速率，约 {int(remaining_days)} 天达到 {int(forecast.confidence_level*100)}% 置信度。"
                if remaining_days is not None
                else "需要更多数据估算时间线。"
            ),
        }
    return {
        "available": False,
        "model_state": "insufficient_data",
        "reason": "insufficient_settled_samples",
        "settled_count": settled_count,
        "min_required": 5,
        "interpretation": "需要 ≥5 笔已结算样本才能预估时间线。",
    }


def _dashboard_market_breakdown(prediction_ledger: list[dict[str, Any]]) -> dict[str, Any]:
    """Per-market hit rate / ROI / sample-size for the HeatMap visualization."""
    by_market: dict[str, dict[str, Any]] = {}
    by_league_market: dict[tuple[str, str], dict[str, Any]] = {}

    for row in prediction_ledger or []:
        if row.get("settlement_status") != "settled":
            continue
        market = str(row.get("market") or "unknown")
        league = str(row.get("league") or "unknown")
        hit = 1 if int(row.get("hit") or 0) == 1 else 0
        profit = parse_float(row.get("profit_units")) or 0.0

        # Per-market
        m = by_market.setdefault(market, {"hits": 0, "samples": 0, "profit": 0.0})
        m["hits"] += hit
        m["samples"] += 1
        m["profit"] += profit

        # Per league × market
        key = (league, market)
        lm = by_league_market.setdefault(key, {"hits": 0, "samples": 0, "profit": 0.0})
        lm["hits"] += hit
        lm["samples"] += 1
        lm["profit"] += profit

    market_rows = [
        {
            "market": market,
            "sample_count": data["samples"],
            "hit_count": data["hits"],
            "hit_rate": round(data["hits"] / data["samples"], 4) if data["samples"] else None,
            "roi": round(data["profit"] / data["samples"], 4) if data["samples"] else None,
        }
        for market, data in sorted(by_market.items())
    ]
    cell_rows = [
        {
            "league": league,
            "market": market,
            "sample_count": data["samples"],
            "hit_rate": round(data["hits"] / data["samples"], 4) if data["samples"] else None,
            "roi": round(data["profit"] / data["samples"], 4) if data["samples"] else None,
        }
        for (league, market), data in sorted(by_league_market.items())
    ]
    return {
        "by_market": market_rows,
        "heatmap_cells": cell_rows,
        "total_settled": sum(d["samples"] for d in by_market.values()),
        "markets": sorted(by_market.keys()),
        "leagues": sorted(set(league for league, _ in by_league_market.keys())),
    }


def _dashboard_prediction_accountability(
    *,
    prediction_kpis: dict[str, Any],
    strategy_state: dict[str, Any],
    learning_effectiveness: dict[str, Any],
    recommendation_opportunity: dict[str, Any],
    candidate_filters: list[dict[str, Any]],
) -> dict[str, Any]:
    total_predictions = int(prediction_kpis.get("total_count") or 0)
    formal_count = int(prediction_kpis.get("recommended_count") or 0)
    paper_count = int(prediction_kpis.get("observation_count") or 0)
    settled_count = int(prediction_kpis.get("settled_count") or 0)
    open_count = int(prediction_kpis.get("open_count") or 0)
    hit_rate = parse_float(prediction_kpis.get("hit_rate"))
    roi = parse_float(prediction_kpis.get("roi"))
    learning_active = bool(strategy_state.get("active"))
    learning_improved = bool(learning_effectiveness.get("learning_improved"))
    beats_market = bool(learning_effectiveness.get("beats_market"))
    release_gate = recommendation_opportunity.get("release_gate") if isinstance(recommendation_opportunity.get("release_gate"), dict) else {}
    formal_enabled = bool(release_gate.get("formal_enabled"))
    primary_blocker = str((candidate_filters[0] or {}).get("reason") or "") if candidate_filters else ""
    primary_blocker_label = _dashboard_reason_label(primary_blocker) if primary_blocker else "暂无主要阻断"

    def check(
        key: str,
        label: str,
        status: str,
        title: str,
        detail: str,
        *,
        current: int | float | None = None,
        target: int | float | None = None,
    ) -> dict[str, Any]:
        return {
            "key": key,
            "label": label,
            "status": status,
            "title": title,
            "detail": detail,
            "current": round_metric(current, 6) if isinstance(current, float) else current,
            "target": round_metric(target, 6) if isinstance(target, float) else target,
            "ratio": _dashboard_ratio(current, target) if target not in (None, 0) else None,
        }

    checks = [
        check(
            "prediction_loop",
            "预测闭环",
            "ok" if total_predictions > 0 else "missing",
            "正在持续预测" if total_predictions > 0 else "没有预测样本",
            f"已生成 {total_predictions} 条预测；正式推荐为 0 时仍保留纸面预测。",
            current=total_predictions,
            target=1,
        ),
        check(
            "backtest_visibility",
            "回测可见",
            "ok" if settled_count > 0 else "warning" if open_count > 0 else "blocked",
            "已有结算回测" if settled_count > 0 else "等待赛果回测",
            f"{settled_count} 条已结算，{open_count} 条等待赛果；真实比分和命中结果会写入台账。",
            current=settled_count,
            target=max(1, settled_count + open_count),
        ),
        check(
            "learning_effect",
            "学习效果",
            "ok" if learning_improved else "warning" if settled_count > 0 else "blocked",
            "学习校准有改善" if learning_improved else "学习效果待验证",
            str(learning_effectiveness.get("detail") or "等待已结算样本计算学习效果。"),
            current=1 if learning_improved else 0,
            target=1,
        ),
        check(
            "market_benchmark",
            "市场基准",
            "ok" if beats_market else "blocked" if settled_count >= 20 else "warning",
            "已优于市场" if beats_market else "尚未优于市场",
            "正式推荐必须证明学习后概率优于市场隐含概率；未通过时只能纸面回测。",
            current=1 if beats_market else 0,
            target=1,
        ),
        check(
            "formal_gate",
            "推荐闸门",
            "ok" if formal_enabled or formal_count > 0 else "blocked" if settled_count >= 20 else "warning",
            "正式推荐开放" if formal_enabled or formal_count > 0 else "正式推荐关闭",
            (
                f"当前正式推荐 {formal_count} 条；主要阻断为 {primary_blocker_label}。"
                "关闭闸门不会停止预测，只会防止不可靠信号进入正式推荐。"
            ),
            current=formal_count,
            target=1,
        ),
    ]
    blocked_count = sum(1 for item in checks if item["status"] == "blocked")
    if total_predictions <= 0:
        status = "prediction_loop_empty"
        severity = "error"
        title = "没有预测闭环"
        conclusion = "没有预测样本，无法回测。"
    elif formal_count <= 0:
        status = "active_paper_validation"
        severity = "warning" if blocked_count else "info"
        title = "不推荐不等于不预测"
        conclusion = (
            f"当前无正式推荐，但已有 {paper_count} 条纸面预测；"
            f"{settled_count} 条已回测，{open_count} 条等待赛果。"
        )
    else:
        status = "formal_and_paper_tracking"
        severity = "ok"
        title = "正式推荐与纸面预测并行"
        conclusion = f"正式推荐 {formal_count} 条，纸面预测 {paper_count} 条，继续统一回测。"
    return {
        "status": status,
        "severity": severity,
        "headline": "不推荐不等于不预测",
        "title": title,
        "detail": conclusion,
        "summary": {
            "total_predictions": total_predictions,
            "formal_recommendations": formal_count,
            "paper_predictions": paper_count,
            "settled_predictions": settled_count,
            "open_predictions": open_count,
            "hit_rate": round_metric(hit_rate),
            "roi": round_metric(roi, 4),
            "learning_active": learning_active,
            "learning_improved": learning_improved,
            "beats_market": beats_market,
            "formal_gate_enabled": formal_enabled,
            "primary_blocker": primary_blocker,
            "primary_blocker_label": primary_blocker_label,
        },
        "checks": checks,
        "policy": {
            "prediction_policy": "always_predict_and_backtest",
            "formal_recommendation_policy": "gate_formal_recommendations_when_learning_or_roi_is_unproven",
            "paper_prediction_policy": "persist_every_analysis_ready_signal_for_settlement_backtest",
            "no_real_bet": True,
        },
    }


def _dashboard_action_status_rank(status: str) -> int:
    return {"blocked": 0, "warning": 1, "info": 2, "ok": 3}.get(status, 2)


def _dashboard_adaptive_learning_plan(
    *,
    learning_effectiveness: dict[str, Any],
    prediction_quality: dict[str, Any],
    recommendation_opportunity: dict[str, Any],
) -> dict[str, Any]:
    """Translate quality gates into concrete self-learning actions for the dashboard."""
    actions: list[dict[str, Any]] = [
        {
            "key": "continue_prediction_backtest",
            "label": "持续预测回测",
            "status": "ok",
            "title": "不推荐也继续预测",
            "detail": "正式推荐关闭时仍写入纸面预测台账，等待赛果后继续回测命中和收益。",
            "reason": "always_predict_and_backtest",
            "applies_to": "prediction_loop",
            "evidence": "预测策略保持开启",
            "current": None,
            "target": None,
            "policy_effect": "继续采样，不投注",
        }
    ]
    release_gate = recommendation_opportunity.get("release_gate") if isinstance(recommendation_opportunity.get("release_gate"), dict) else {}
    release_gates = [
        gate for gate in (release_gate.get("gates") or [])
        if isinstance(gate, dict)
    ]
    shadow_gate = next((gate for gate in release_gates if str(gate.get("key") or "") == "shadow_walk_forward"), {})
    shadow_recalibration = (
        learning_effectiveness.get("shadow_recalibration")
        if isinstance(learning_effectiveness.get("shadow_recalibration"), dict)
        else {}
    )
    shadow_quality = (
        shadow_recalibration.get("quality")
        if isinstance(shadow_recalibration.get("quality"), dict)
        else {}
    )
    shadow_delta = parse_float(shadow_gate.get("current"))
    if shadow_delta is None:
        shadow_delta = parse_float(shadow_quality.get("walk_forward_brier_delta"))
    shadow_failed = bool(
        str(shadow_gate.get("status") or "") == "blocked"
        or str(shadow_recalibration.get("status") or "") == "shadow_model_watch_only"
        or (shadow_delta is not None and shadow_delta > 0)
    )
    if shadow_failed:
        actions.append(
            {
                "key": "freeze_shadow_recalibration",
                "label": "冻结影子重校准",
                "status": "blocked",
                "title": "走步验证未过",
                "detail": "影子重校准只允许继续纸面观察，不能替换正式推荐概率。",
                "reason": "shadow_walk_forward_failed",
                "applies_to": "shadow_recalibration",
                "evidence": f"走步 Brier 变化 {_signed_decimal_text(shadow_delta) or '暂无'}",
                "current": round_metric(shadow_delta, 6),
                "target": 0,
                "policy_effect": "冻结升级，只继续纸面回测",
            }
        )

    learned_minus_market = parse_float((learning_effectiveness.get("deltas") or {}).get("learned_brier_minus_market"))
    if not bool(learning_effectiveness.get("beats_market")):
        actions.append(
            {
                "key": "keep_market_baseline",
                "label": "保留市场基准",
                "status": "blocked",
                "title": "学习概率尚未跑赢市场",
                "detail": "学习后概率不能替代市场隐含概率，只能用于降权、排序和纸面验证。",
                "reason": "not_beating_market",
                "applies_to": "probability_calibration",
                "evidence": f"学习 Brier 相对市场 {_signed_decimal_text(learned_minus_market) or '暂无'}",
                "current": round_metric(learned_minus_market, 6),
                "target": 0,
                "policy_effect": "市场基准保留为推荐闸门",
            }
        )

    for segment in (prediction_quality.get("segments") or [])[:8]:
        if not isinstance(segment, dict):
            continue
        adjustment = segment.get("adjustment") if isinstance(segment.get("adjustment"), dict) else {}
        action = str(adjustment.get("action") or "")
        reason = str(segment.get("reason") or "observed_not_recommended")
        label = str(segment.get("label") or _dashboard_reason_label(reason))
        settled_count = int(segment.get("settled_count") or 0)
        roi = parse_float(segment.get("roi"))
        if action in {"suppress_reason", "tighten_thresholds"}:
            weight = parse_float(adjustment.get("weight_multiplier"))
            status = "blocked" if action == "suppress_reason" else "warning"
            actions.append(
                {
                    "key": f"suppress_{reason}",
                    "label": f"降权{label}",
                    "status": status,
                    "title": str(adjustment.get("label") or "降权过滤"),
                    "detail": str(adjustment.get("detail") or f"{label} 分组回测偏弱，进入正式推荐前需要降权。"),
                    "reason": reason,
                    "applies_to": "prediction_quality_segment",
                    "evidence": f"{label} 已回测 {settled_count} 场，收益率 {_percent_text(roi) or '暂无'}",
                    "current": round_metric(roi, 4),
                    "target": 0,
                    "policy_effect": f"正式推荐前权重 {weight:.2f}" if weight is not None else "正式推荐前降权",
                }
            )
        elif action == "collect_more_samples":
            actions.append(
                {
                    "key": f"collect_more_{reason}",
                    "label": f"补足{label}样本",
                    "status": "warning",
                    "title": "样本继续收集",
                    "detail": str(adjustment.get("detail") or f"{label} 分组样本不足，暂不做正式升降级结论。"),
                    "reason": reason,
                    "applies_to": "prediction_quality_segment",
                    "evidence": f"{label} 已回测 {settled_count} 场，目标 20 场",
                    "current": settled_count,
                    "target": 20,
                    "policy_effect": "样本未满不开放正式推荐",
                }
            )

    signal_count = int(release_gate.get("signal_settled_count") or 0)
    min_signal_count = int(release_gate.get("min_signal_sample_count") or 0)
    if min_signal_count and signal_count < min_signal_count:
        actions.append(
            {
                "key": "collect_signal_samples",
                "label": "补足正向信号样本",
                "status": "warning",
                "title": "信号样本未满",
                "detail": f"正向纸面信号已回测 {signal_count} 场，达到 {min_signal_count} 场前不升级正式推荐。",
                "reason": "signal_sample_count_below_threshold",
                "applies_to": "recommendation_release_gate",
                "evidence": f"正向信号 {signal_count}/{min_signal_count} 场",
                "current": signal_count,
                "target": min_signal_count,
                "policy_effect": "继续纸面验证",
            }
        )

    actions.sort(key=lambda item: (_dashboard_action_status_rank(str(item.get("status") or "")), str(item.get("key") or "")))
    blocked_count = sum(1 for action in actions if action.get("status") == "blocked")
    warning_count = sum(1 for action in actions if action.get("status") == "warning")
    collection_count = sum(1 for action in actions if str(action.get("key") or "").startswith("collect"))
    frozen_count = sum(1 for action in actions if "冻结" in str(action.get("label") or ""))
    if blocked_count:
        status = "retrain_required"
        severity = "warning"
        title = "需要重训或冻结部分策略"
        detail = f"发现 {blocked_count} 个阻断动作、{warning_count} 个采样动作；正式推荐继续关闭，纸面预测和回测继续运行。"
    elif warning_count:
        status = "collecting_samples"
        severity = "info"
        title = "样本收集中"
        detail = f"当前没有硬阻断，但仍有 {warning_count} 个动作需要继续补样本或复算。"
    else:
        status = "monitoring"
        severity = "ok"
        title = "策略继续监控"
        detail = "当前自学习计划没有硬阻断动作，保持纸面验证和生产闸门监控。"
    return {
        "status": status,
        "severity": severity,
        "title": title,
        "detail": detail,
        "summary": {
            "action_count": len(actions),
            "blocked_action_count": blocked_count,
            "warning_action_count": warning_count,
            "collection_action_count": collection_count,
            "frozen_model_count": frozen_count,
        },
        "actions": actions[:10],
    }


def _dashboard_ratio(current: int | float, target: int | float) -> float | None:
    if target <= 0:
        return None
    return round_metric(max(0.0, min(1.0, float(current) / float(target))), 6)


def _dashboard_reason_label(reason: str) -> str:
    labels = {
        "no_positive_edge": "无正向边际",
        "edge_below_threshold": "边际不足",
        "value_edge_below_threshold": "价值边际不足",
        "large_handicap_requires_backtest": "大盘口需回测",
        "multi_bookmaker_snapshot_missing": "缺少多公司赔率快照",
        "awaiting_reanalysis_after_snapshot": "赔率快照已补齐，等待下一轮复算",
        "shadow_prediction_reference_only": "影子预测仅用于对照回测",
        "lineup_context_missing": "阵容信息不足",
        "calibrated_probability_below_threshold": "概率不足",
        "decimal_odds_below_threshold": "赔率过低",
        "decimal_odds_above_threshold": "赔率过高",
        "observed_not_recommended": "纸面预测未推荐",
    }
    return labels.get(str(reason or ""), str(reason or "未知原因"))


def _dashboard_decision_audit(
    *,
    prediction_kpis: dict[str, Any],
    strategy_state: dict[str, Any],
    candidate_filters: list[dict[str, Any]],
    prediction_ledger: list[dict[str, Any]],
    market_snapshot_summary: dict[str, Any],
) -> dict[str, Any]:
    recommended_count = int(prediction_kpis.get("recommended_count") or 0)
    observation_count = int(prediction_kpis.get("observation_count") or 0)
    total_count = int(prediction_kpis.get("total_count") or 0)
    open_count = int(prediction_kpis.get("open_count") or 0)
    live_count = int(prediction_kpis.get("live_count") or 0)
    scheduled_count = int(prediction_kpis.get("scheduled_count") or 0)
    final_pending_count = int(prediction_kpis.get("final_pending_count") or 0)
    result_pending_count = int(prediction_kpis.get("result_pending_count") or 0)
    maybe_live_count = int(prediction_kpis.get("maybe_live_count") or 0)
    settled_count = int(prediction_kpis.get("settled_count") or 0)
    sample_count = int(strategy_state.get("sample_count") or 0)
    min_sample_count = int(strategy_state.get("min_live_sample_count") or 20)
    learning_active = bool(strategy_state.get("active"))
    top_rejection_reasons = [
        {
            "reason": str(group.get("reason") or "observed_not_recommended"),
            "count": int(group.get("count") or 0),
        }
        for group in candidate_filters[:6]
    ]

    if total_count > 0:
        prediction_status = "ok"
        prediction_title = "预测样本已入库"
        prediction_detail = (
            f"已形成 {total_count} 条预测样本，其中正式推荐 {recommended_count} 条、"
            f"纸面预测 {observation_count} 条；所有可结算样本都会进入回测。"
        )
    else:
        prediction_status = "warning"
        prediction_title = "暂无预测样本"
        prediction_detail = "自动学习循环还没有形成可回测预测，无法验证准确率。"

    if recommended_count > 0:
        recommendation_status = "ok"
        recommendation_title = "已有正式推荐"
        recommendation_detail = f"正式推荐 {recommended_count} 场，纸面预测 {observation_count} 场。"
    elif observation_count > 0:
        recommendation_status = "warning"
        recommendation_title = "当前无正式推荐"
        main_reason = top_rejection_reasons[0]["reason"] if top_rejection_reasons else "observed_not_recommended"
        recommendation_detail = f"{observation_count} 场进入纸面预测，主要原因：{_dashboard_reason_label(main_reason)}。"
    else:
        recommendation_status = "info"
        recommendation_title = "暂无预测样本"
        recommendation_detail = "自动学习循环还没有写入可审计样本。"

    if learning_active:
        learning_status = "ok"
        learning_title = "学习校准已生效"
        learning_detail = f"已结算 {settled_count} 场，实时校准正在参与概率调整。"
    elif settled_count == 0 or sample_count == 0:
        learning_status = "warning"
        learning_title = "学习尚未生效"
        learning_detail = "还没有已结算样本，模型不会根据命中结果调整概率。"
    else:
        learning_status = "info"
        learning_title = "学习样本收集中"
        learning_detail = f"已结算 {settled_count} 场，达到 {min_sample_count} 场后才启用实时校准。"

    if settled_count > 0:
        settlement_status = "ok"
        settlement_title = "结算闭环已启动"
        settlement_detail = f"已结算 {settled_count} 场，等待赛果 {open_count} 场。"
    elif open_count > 0:
        settlement_status = "warning"
        settlement_title = "等待首批赛果"
        settlement_detail = f"{open_count} 场仍在等待赛果。"
    else:
        settlement_status = "info"
        settlement_title = "暂无待结算样本"
        settlement_detail = "当前台账为空或没有等待赛果的样本。"

    ledger_count = len(prediction_ledger)
    covered_count = sum(1 for row in prediction_ledger if row.get("has_odds_snapshot") or int(row.get("odds_snapshot_count") or 0) > 0)
    odds_ratio = _dashboard_ratio(covered_count, ledger_count) if ledger_count else None
    snapshot_count = int(market_snapshot_summary.get("total_snapshot_count") or 0)
    bookmaker_count = int(market_snapshot_summary.get("bookmaker_count") or 0)
    if ledger_count and covered_count == ledger_count:
        odds_status = "ok"
        odds_title = "赔率快照已覆盖"
    elif covered_count > 0:
        odds_status = "info"
        odds_title = "部分赔率已覆盖"
    elif ledger_count > 0:
        odds_status = "warning"
        odds_title = "赔率覆盖不足"
    else:
        odds_status = "info"
        odds_title = "暂无赔率样本"
    odds_detail = f"台账 {covered_count}/{ledger_count} 场有赔率快照，共 {snapshot_count} 条。"

    health_items = [
        {
            "key": "prediction",
            "label": "预测",
            "status": prediction_status,
            "title": prediction_title,
            "detail": prediction_detail,
            "current": total_count,
            "target": None,
            "ratio": 1.0 if total_count > 0 else 0.0,
        },
        {
            "key": "recommendation",
            "label": "推荐",
            "status": recommendation_status,
            "title": recommendation_title,
            "detail": recommendation_detail,
            "current": recommended_count,
            "target": 1,
            "ratio": 1.0 if recommended_count > 0 else 0.0,
        },
        {
            "key": "learning",
            "label": "学习",
            "status": learning_status,
            "title": learning_title,
            "detail": learning_detail,
            "current": sample_count,
            "target": min_sample_count,
            "ratio": _dashboard_ratio(sample_count, min_sample_count),
        },
        {
            "key": "settlement",
            "label": "结算",
            "status": settlement_status,
            "title": settlement_title,
            "detail": settlement_detail,
            "current": settled_count,
            "target": settled_count + open_count,
            "ratio": _dashboard_ratio(settled_count, settled_count + open_count),
        },
        {
            "key": "odds",
            "label": "赔率",
            "status": odds_status,
            "title": odds_title,
            "detail": odds_detail,
            "current": covered_count,
            "target": ledger_count,
            "ratio": odds_ratio,
        },
    ]

    return {
        "generated_at_utc": now_utc().isoformat(),
        "prediction": {
            "status": prediction_status,
            "title": prediction_title,
            "detail": prediction_detail,
            "total_count": total_count,
            "evaluation_count": total_count,
            "recommended_count": recommended_count,
            "observation_count": observation_count,
            "open_count": open_count,
            "settled_count": settled_count,
        },
        "recommendation": {
            "status": recommendation_status,
            "title": recommendation_title,
            "detail": recommendation_detail,
            "recommended_count": recommended_count,
            "observation_count": observation_count,
            "open_count": open_count,
            "top_rejection_reasons": top_rejection_reasons,
        },
        "learning": {
            "status": learning_status,
            "title": learning_title,
            "detail": learning_detail,
            "active": learning_active,
            "sample_count": sample_count,
            "min_sample_count": min_sample_count,
            "settled_count": settled_count,
            "hit_rate": prediction_kpis.get("hit_rate"),
            "roi": prediction_kpis.get("roi"),
        },
        "settlement": {
            "status": settlement_status,
            "title": settlement_title,
            "detail": settlement_detail,
            "open_count": open_count,
            "settled_count": settled_count,
            "hit_count": int(prediction_kpis.get("hit_count") or 0),
            "miss_count": int(prediction_kpis.get("miss_count") or 0),
        },
        "odds": {
            "status": odds_status,
            "title": odds_title,
            "detail": odds_detail,
            "covered_count": covered_count,
            "ledger_count": ledger_count,
            "coverage_ratio": odds_ratio,
            "snapshot_count": snapshot_count,
            "bookmaker_count": bookmaker_count,
        },
        "health_items": health_items,
    }


def _dashboard_learning_diagnostics(
    *,
    prediction_kpis: dict[str, Any],
    strategy_state: dict[str, Any],
    candidate_filters: list[dict[str, Any]],
    prediction_ledger: list[dict[str, Any]],
    market_snapshot_summary: dict[str, Any],
) -> dict[str, Any]:
    total_count = int(prediction_kpis.get("total_count") or 0)
    formal_count = int(prediction_kpis.get("recommended_count") or 0)
    observation_count = int(prediction_kpis.get("observation_count") or 0)
    open_count = int(prediction_kpis.get("open_count") or 0)
    live_count = int(prediction_kpis.get("live_count") or 0)
    scheduled_count = int(prediction_kpis.get("scheduled_count") or 0)
    final_pending_count = int(prediction_kpis.get("final_pending_count") or 0)
    result_pending_count = int(prediction_kpis.get("result_pending_count") or 0)
    maybe_live_count = int(prediction_kpis.get("maybe_live_count") or 0)
    settled_count = int(prediction_kpis.get("settled_count") or 0)
    hit_count = int(prediction_kpis.get("hit_count") or 0)
    miss_count = int(prediction_kpis.get("miss_count") or 0)
    sample_count = int(strategy_state.get("sample_count") or 0)
    min_sample_count = int(strategy_state.get("min_live_sample_count") or 20)
    learning_active = bool(strategy_state.get("active"))
    covered_count = sum(
        1
        for row in prediction_ledger
        if row.get("has_odds_snapshot") or int(row.get("odds_snapshot_count") or 0) > 0
    )
    ledger_count = len(prediction_ledger)
    odds_ratio = _dashboard_ratio(covered_count, ledger_count) if ledger_count else None
    reanalysis_backlog_count = sum(
        int(group.get("count") or 0)
        for group in candidate_filters
        if str(group.get("reason") or "") == "awaiting_reanalysis_after_snapshot"
    )
    remaining_to_live_calibration = max(min_sample_count - sample_count, 0)

    if total_count <= 0:
        status = "no_predictions"
        severity = "warning"
        title = "暂无可回测样本"
        detail = "自动学习循环还没有写入预测样本，因此无法验证命中率或收益。"
    elif settled_count <= 0:
        status = "waiting_results"
        severity = "warning"
        title = "等待赛果形成回测样本"
        detail = (
            f"当前未结算 {open_count} 场：进行中 {live_count} 场、未开赛 {scheduled_count} 场、"
            f"完场待结算 {final_pending_count} 场；结算后才会产生命中、错误和收益数据。"
        )
    elif not learning_active:
        status = "collecting_backtest_samples"
        severity = "info"
        title = "回测样本收集中"
        detail = f"已回测 {settled_count} 场，还差 {remaining_to_live_calibration} 场达到实时校准阈值。"
    else:
        status = "live_calibrating"
        severity = "ok"
        title = "学习校准已生效"
        detail = f"已回测 {settled_count} 场，命中率和收益会参与后续概率校准。"

    odds_status = "ok" if ledger_count and covered_count == ledger_count else "info" if covered_count > 0 else "warning"
    reanalysis_status = "ok" if reanalysis_backlog_count == 0 else "warning"
    recommendation_status = "ok" if formal_count > 0 else "info" if observation_count > 0 else "warning"

    readiness_items = [
        {
            "key": "prediction_samples",
            "label": "预测样本",
            "status": "ok" if total_count > 0 else "warning",
            "title": "样本已入库" if total_count > 0 else "暂无样本",
            "detail": f"当前共有 {total_count} 场预测样本，正式 {formal_count} 场、纸面 {observation_count} 场。",
            "current": total_count,
            "target": None,
            "ratio": 1.0 if total_count > 0 else 0.0,
        },
        {
            "key": "settled_backtest",
            "label": "回测结算",
            "status": "ok" if learning_active else "info" if settled_count > 0 else "warning",
            "title": "已进入学习校准" if learning_active else "等待更多赛果" if settled_count > 0 else "等待首批赛果",
            "detail": f"已回测 {settled_count} 场，等待赛果 {open_count} 场；校准阈值 {min_sample_count} 场。",
            "current": sample_count,
            "target": min_sample_count,
            "ratio": _dashboard_ratio(sample_count, min_sample_count),
        },
        {
            "key": "odds_snapshots",
            "label": "赔率快照",
            "status": odds_status,
            "title": "赔率覆盖完整" if odds_status == "ok" else "赔率覆盖中" if covered_count > 0 else "缺少赔率快照",
            "detail": f"台账 {covered_count}/{ledger_count} 场有赔率快照，共 {int(market_snapshot_summary.get('total_snapshot_count') or 0)} 条。",
            "current": covered_count,
            "target": ledger_count,
            "ratio": odds_ratio,
        },
        {
            "key": "reanalysis_queue",
            "label": "待复算",
            "status": reanalysis_status,
            "title": "无需复算" if reanalysis_backlog_count == 0 else "赔率补齐后待复算",
            "detail": f"{reanalysis_backlog_count} 场赔率已补齐但还需下一轮重新分析。",
            "current": reanalysis_backlog_count,
            "target": 0,
            "ratio": 1.0 if reanalysis_backlog_count == 0 else 0.0,
        },
        {
            "key": "recommendation_gate",
            "label": "正式推荐",
            "status": recommendation_status,
            "title": "已有正式推荐" if formal_count > 0 else "当前只做纸面预测" if observation_count > 0 else "暂无推荐",
            "detail": f"正式推荐 {formal_count} 场，纸面预测 {observation_count} 场。",
            "current": formal_count,
            "target": 1,
            "ratio": 1.0 if formal_count > 0 else 0.0,
        },
    ]

    top_blockers = [
        {
            "reason": str(group.get("reason") or "observed_not_recommended"),
            "count": int(group.get("count") or 0),
        }
        for group in candidate_filters[:5]
    ]

    return {
        "status": status,
        "severity": severity,
        "title": title,
        "detail": detail,
        "prediction_total": total_count,
        "formal_count": formal_count,
        "observation_count": observation_count,
        "open_count": open_count,
        "live_count": live_count,
        "scheduled_count": scheduled_count,
        "final_pending_count": final_pending_count,
        "result_pending_count": result_pending_count,
        "maybe_live_count": maybe_live_count,
        "settled_count": settled_count,
        "hit_count": hit_count,
        "miss_count": miss_count,
        "backtested_count": settled_count,
        "waiting_result_count": open_count,
        "ready_for_backtest_count": total_count,
        "sample_count": sample_count,
        "settled_sample_target": min_sample_count,
        "remaining_to_live_calibration": remaining_to_live_calibration,
        "live_calibration_active": learning_active,
        "odds_covered_count": covered_count,
        "odds_ledger_count": ledger_count,
        "odds_coverage_ratio": odds_ratio,
        "snapshot_count": int(market_snapshot_summary.get("total_snapshot_count") or 0),
        "bookmaker_count": int(market_snapshot_summary.get("bookmaker_count") or 0),
        "reanalysis_backlog_count": reanalysis_backlog_count,
        "hit_rate": prediction_kpis.get("hit_rate"),
        "roi": prediction_kpis.get("roi"),
        "readiness_items": readiness_items,
        "top_blockers": top_blockers,
    }


def _dashboard_record_core_metrics(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "line": round_metric(parse_float(record.get("line")), 4),
        "decimal_odds": round_metric(parse_float(record.get("decimal_odds")), 4),
        "model_probability": round_metric(parse_float(record.get("model_probability"))),
        "learned_probability": round_metric(_dashboard_probability(record)),
        "market_probability": round_metric(parse_float(record.get("market_probability"))),
        "edge": round_metric(parse_float(record.get("edge"))),
        "expected_multiplier": round_metric(parse_float(record.get("expected_multiplier")), 4),
    }


def _dashboard_live_calibration(raw: dict[str, Any], strategy_state: dict[str, Any]) -> dict[str, Any]:
    learning_policy = raw.get("learning_policy") if isinstance(raw.get("learning_policy"), dict) else {}
    live_calibration = learning_policy.get("live_calibration") if isinstance(learning_policy.get("live_calibration"), dict) else None
    if live_calibration is None and isinstance(raw.get("live_calibration"), dict):
        live_calibration = raw.get("live_calibration")
    if live_calibration is not None:
        return dict(live_calibration)
    return {
        "active": bool(strategy_state.get("active")),
        "sample_count": int(strategy_state.get("sample_count") or 0),
        "status": strategy_state.get("status"),
    }


def _dashboard_advice_reason(advice: dict[str, Any]) -> str:
    for key in ("reason", "primary_reason", "blocked_or_low_value_reason"):
        reason = str(advice.get(key) or "").strip()
        if reason:
            return reason
    return ""


def _dashboard_raw_advice_is_current(raw_advice: dict[str, Any], diagnostic: dict[str, Any]) -> bool:
    raw_reason = _dashboard_advice_reason(raw_advice)
    diagnostic_reason = str(diagnostic.get("primary_reason") or "").strip()
    if (
        raw_reason == "multi_bookmaker_snapshot_missing"
        and diagnostic_reason
        and diagnostic_reason != raw_reason
    ):
        return False
    return True


def _dashboard_final_execution_advice(
    record: dict[str, Any],
    raw: dict[str, Any],
    diagnostic: dict[str, Any],
) -> dict[str, Any]:
    raw_advice = raw.get("final_execution_advice")
    if isinstance(raw_advice, dict) and raw_advice and _dashboard_raw_advice_is_current(raw_advice, diagnostic):
        return raw_advice

    raw_decision = raw.get("final_decision")
    if (
        isinstance(raw_decision, dict)
        and str(raw_decision.get("action") or "") in {"bet_now", "observe", "skip", "paper_track"}
        and _dashboard_raw_advice_is_current(raw_decision, diagnostic)
    ):
        return raw_decision

    recommendation = str(record.get("recommendation") or "")
    selection = str(record.get("selection") or "").strip()
    reason_label = str(diagnostic.get("primary_reason_label") or _dashboard_reason_label(recommendation) or "原因待确认")
    backtest_eligible = bool(diagnostic.get("backtest_eligible"))
    formal = bool(diagnostic.get("recommended"))
    if formal:
        if recommendation in {"immediate_bet", "bet_now"}:
            action = "bet_now"
            action_label = "正式推荐"
        elif recommendation in {"condition_observe", "observe"}:
            action = "observe"
            action_label = "条件观察"
        else:
            action = "skip"
            action_label = "不推荐"
        headline = f"{action_label}：{selection or _dashboard_matchup(record)}，{reason_label}。"
    else:
        action = "paper_track"
        action_label = "纸面预测"
        headline = f"纸面预测：{selection or _dashboard_matchup(record)}，{reason_label}，继续进入回测但不升级为正式推荐。"

    return {
        "source": "dashboard_synthesized_advice",
        "action": action,
        "action_label": action_label,
        "headline": headline,
        "raw_mcp_recommendation": recommendation,
        "formal_recommendation": formal,
        "paper_tracked": not formal,
        "backtest_eligible": backtest_eligible,
        "reason": str(diagnostic.get("primary_reason") or recommendation),
        "reason_label": reason_label,
        "selection": selection,
        "market": record.get("market") or "",
        "decimal_odds": round_metric(parse_float(record.get("decimal_odds")), 4),
        "no_real_bet": True,
    }


def _dashboard_context_reconciled_completeness(
    completeness: dict[str, Any],
    match_context: dict[str, Any] | None,
) -> dict[str, Any]:
    if not isinstance(completeness, dict):
        return {}
    if not match_context:
        return dict(completeness)

    result = dict(completeness)
    available_blocks = result.get("available_blocks")
    missing_blocks = result.get("missing_blocks")
    if not isinstance(available_blocks, list) or not isinstance(missing_blocks, list):
        return result

    available = [str(item) for item in available_blocks]
    missing = [str(item) for item in missing_blocks]
    context_available = set(match_context.get("available_blocks") or [])
    for key in ("venue", "weather", "referee", "lineup"):
        if key in available and key not in context_available:
            available = [item for item in available if item != key]
            if key not in missing:
                missing.append(key)

    result["available_blocks"] = available
    result["missing_blocks"] = missing
    total = len(set(available + missing))
    if total:
        result["ratio"] = round_metric(len(set(available)) / total) or 0.0
    return result


def _dashboard_detail_timeline(record: dict[str, Any], strategy_state: dict[str, Any]) -> list[dict[str, Any]]:
    timeline = [
        {
            "title": "推荐入库",
            "detail": f"{record.get('tool') or 'unknown'} · {record.get('mode') or 'unknown'}",
            "at_utc": record.get("created_at_utc") or "",
        },
        {
            "title": "策略阈值",
            "detail": (
                f"{strategy_state.get('status')} · samples={strategy_state.get('sample_count')} · "
                f"minP={strategy_state.get('min_calibrated_probability')}"
            ),
            "at_utc": strategy_state.get("updated_at_utc") or record.get("created_at_utc") or "",
        },
    ]
    if record.get("settlement_status") == "settled":
        timeline.append(
            {
                "title": "赛果结算",
                "detail": (
                    f"{record.get('home_score')}-{record.get('away_score')} · "
                    f"profit={record.get('profit_units')}"
                ),
                "at_utc": record.get("settled_at_utc") or "",
            }
        )
    return timeline


def _dashboard_record_evidence(
    record: dict[str, Any],
    strategy_state: dict[str, Any],
    *,
    match_context: dict[str, Any] | None = None,
    prediction_type: str | None = None,
    rejection_reason: str | None = None,
    odds_coverage: dict[str, Any] | None = None,
    probability_governance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    raw = record.get("raw") if isinstance(record.get("raw"), dict) else {}
    market_candidates = raw.get("market_candidates") or raw.get("candidates") or []
    if not market_candidates and isinstance(raw.get("best_candidate"), dict) and raw.get("best_candidate"):
        market_candidates = [raw["best_candidate"]]
    data_completeness = raw.get("data_completeness") or raw.get("data_coverage") or raw.get("quality") or {}
    evidence_prediction_type = prediction_type or _dashboard_prediction_type(record, source="recommendation")
    evidence_rejection_reason = str(
        rejection_reason
        if rejection_reason is not None
        else record.get("rejection_reason") or raw.get("reason") or ""
    )
    prediction_diagnostic = _dashboard_prediction_diagnostic(
        record,
        prediction_type=evidence_prediction_type,
        rejection_reason=evidence_rejection_reason,
        strategy_state=strategy_state,
        probability_governance=probability_governance,
        odds_coverage=odds_coverage,
    )
    return {
        "core_metrics": _dashboard_record_core_metrics(record),
        "final_execution_advice": _dashboard_final_execution_advice(record, raw, prediction_diagnostic),
        "final_decision": raw.get("final_decision") or {},
        "data_completeness": _dashboard_context_reconciled_completeness(data_completeness, match_context),
        "live_calibration": _dashboard_live_calibration(raw, strategy_state),
        "prediction_diagnostic": prediction_diagnostic,
        "market_candidates": market_candidates,
        "risk_flags": record.get("risk_flags") or [],
        "caution_flags": record.get("caution_flags") or [],
    }


def _dashboard_shadow_record(record_id: int | str, *, db_path: str | None = None) -> dict[str, Any] | None:
    target_id = str(record_id)
    for record in learning_store.list_shadow_prediction_records(db_path=db_path, limit=5000):
        if str(record.get("id")) == target_id:
            return record
    return None


def _dashboard_record_from_ledger_id(
    ledger_id: str,
    *,
    db_path: str | None = None,
) -> tuple[str, dict[str, Any]] | None:
    source, separator, source_id = str(ledger_id or "").partition(":")
    if not separator or not source_id:
        return None
    if source == "recommendation":
        record = learning_store.get_recommendation_record(source_id, db_path=db_path)
        return (source, record) if record else None
    if source in {"shadow", "shadow_prediction"}:
        record = _dashboard_shadow_record(source_id, db_path=db_path)
        return ("shadow_prediction", record) if record else None
    return None


def _dashboard_get_path(value: dict[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = value
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _dashboard_first_path(value: dict[str, Any], paths: tuple[tuple[str, ...], ...]) -> Any:
    for path in paths:
        found = _dashboard_get_path(value, path)
        if found not in (None, "", [], {}):
            return found
    return None


def _dashboard_path_exists(value: dict[str, Any], path: tuple[str, ...]) -> bool:
    current: Any = value
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return False
        current = current.get(key)
    return True


def _dashboard_context_path_value(value: dict[str, Any], paths: tuple[tuple[str, ...], ...]) -> Any:
    first_empty_found = False
    for path in paths:
        if not _dashboard_path_exists(value, path):
            continue
        found = _dashboard_get_path(value, path)
        if found not in (None, "", [], {}):
            return found
        first_empty_found = True
    return "暂无信息" if first_empty_found else None


def _dashboard_trim_context_text(value: Any, *, max_length: int = 160) -> str:
    text = str(value or "").strip()
    if len(text) <= max_length:
        return text
    return f"{text[: max_length - 1]}…"


def _dashboard_context_text(value: Any) -> str:
    if value in (None, "", [], {}):
        return ""
    if isinstance(value, (str, int, float)):
        return _dashboard_trim_context_text(value)
    if isinstance(value, dict):
        keys = (
            "name",
            "venue",
            "stadium",
            "field",
            "city",
            "weather",
            "weather_report",
            "description",
            "referee",
            "person",
            "text",
            "value",
        )
        pieces: list[str] = []
        for key in keys:
            item = value.get(key)
            if isinstance(item, (str, int, float)) and str(item).strip():
                text = _dashboard_trim_context_text(item, max_length=80)
                if text not in pieces:
                    pieces.append(text)
        return " · ".join(pieces[:3])
    if isinstance(value, list):
        pieces = [_dashboard_context_text(item) for item in value[:3]]
        return " · ".join(piece for piece in pieces if piece)
    return _dashboard_trim_context_text(value)


_DASHBOARD_SOURCE_EMPTY_TEXTS = {
    "-",
    "--",
    "n/a",
    "na",
    "none",
    "null",
    "暂无",
    "暂无信息",
    "无",
    "未知",
}


def _dashboard_context_is_source_empty(text: str) -> bool:
    normalized = str(text or "").strip().lower()
    return normalized in _DASHBOARD_SOURCE_EMPTY_TEXTS


def _dashboard_context_field(value: Any) -> dict[str, Any]:
    text = _dashboard_context_text(value)
    if _dashboard_context_is_source_empty(text):
        return {
            "available": False,
            "status": "source_empty",
            "text": "源站暂无信息",
            "source_text": text,
        }
    return {
        "available": bool(text),
        "status": "available" if text else "not_collected",
        "text": text or "暂未采集",
    }


def _dashboard_context_provider_label(provider: str) -> str:
    normalized = provider.strip().lower()
    if normalized in {"dongqiudi", "dongqiudi.com", "dqd"}:
        return "懂球帝"
    if normalized in {"leisu", "leisu.com", "leisu_sports"}:
        return "雷速体育"
    if normalized in {"multi_source", "composite"}:
        return "多源融合"
    if normalized in {"football-data.org", "football_data_org"}:
        return "football-data.org"
    return provider or "来源未知"


def _dashboard_context_source(record: dict[str, Any], raw: dict[str, Any], match_context: dict[str, Any] | None) -> dict[str, Any]:
    if not match_context:
        return {
            "status": "not_collected",
            "provider": "",
            "label": "暂未采集",
            "match_id": str(record.get("match_id") or ""),
            "detail": "本地样本还没有持久化赛事情报。",
        }
    provider = str(
        raw.get("context_source_name")
        or match_context.get("source_name")
        or match_context.get("provider")
        or "dongqiudi"
    ).strip()
    match_id = str(
        raw.get("context_match_id")
        or match_context.get("match_id")
        or record.get("match_id")
        or ""
    ).strip()
    label = _dashboard_context_provider_label(provider)
    return {
        "status": "matched",
        "provider": provider,
        "label": label,
        "match_id": match_id,
        "detail": f"{label}已匹配比赛 {match_id}" if match_id else f"{label}已匹配比赛",
    }


def _dashboard_context_source_attempts(
    *,
    source: dict[str, Any],
    venue_field: dict[str, Any],
    weather_field: dict[str, Any],
    referee_field: dict[str, Any],
    lineup_summary: dict[str, Any],
    raw_source_attempts: list[dict[str, Any]] | None = None,
    odds_snapshot: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    lineup_status = "available" if lineup_summary.get("available") else (
        "not_collected" if source.get("status") == "not_collected" else "source_empty"
    )
    field_statuses = {
        "venue": venue_field.get("status") or "not_collected",
        "weather": weather_field.get("status") or "not_collected",
        "referee": referee_field.get("status") or "not_collected",
        "lineup": lineup_status,
    }
    attempts: list[dict[str, Any]] = []
    if raw_source_attempts:
        for item in raw_source_attempts:
            if not isinstance(item, dict):
                continue
            provider = str(item.get("provider") or "").strip()
            label = str(item.get("label") or _dashboard_context_provider_label(provider)).strip()
            statuses = item.get("field_statuses") if isinstance(item.get("field_statuses"), dict) else {}
            attempts.append(
                {
                    "provider": provider,
                    "label": label or "来源未知",
                    "status": item.get("status") or "matched",
                    "match_id": str(item.get("match_id") or ""),
                    "detail": item.get("detail") or "",
                    "field_statuses": {
                        "venue": statuses.get("venue") or "not_collected",
                        "weather": statuses.get("weather") or "not_collected",
                        "referee": statuses.get("referee") or "not_collected",
                        "lineup": statuses.get("lineup") or "not_collected",
                    },
                    **({"urls": item.get("urls")} if isinstance(item.get("urls"), dict) else {}),
                    **({"access": item.get("access")} if isinstance(item.get("access"), dict) else {}),
                }
            )
    if not attempts:
        attempts = [
            {
                "provider": source.get("provider") or "",
                "label": source.get("label") or "来源未知",
                "status": source.get("status") or "not_collected",
                "match_id": source.get("match_id") or "",
                "detail": source.get("detail") or "",
                "field_statuses": field_statuses,
            }
        ]

    resolution = odds_snapshot.get("resolution") if isinstance(odds_snapshot, dict) else {}
    provider = str((resolution or {}).get("provider") or "").strip().lower()
    event_id = str((resolution or {}).get("event_id") or "").strip()
    snapshot_count = int((odds_snapshot or {}).get("snapshot_count") or 0) if isinstance(odds_snapshot, dict) else 0
    has_leisu_attempt = any(str(item.get("provider") or "").strip().lower() == "leisu" for item in attempts)
    if (provider == "leisu" or (event_id and snapshot_count)) and not has_leisu_attempt:
        detail = (
            f"已匹配雷速赔率赛事 {event_id}，赔率快照 {snapshot_count} 条；"
            "本条记录尚未保存雷速赛事情报，后续复算会尝试从雷速移动端补齐。"
        ) if event_id else (
            f"已匹配雷速赔率快照 {snapshot_count} 条；本条记录尚未保存雷速赛事情报，后续复算会尝试从雷速移动端补齐。"
        )
        urls = {}
        if event_id:
            urls = {
                "mobile_detail": f"https://m.leisu.com/live/detail-{event_id}",
                "mobile_data": f"https://m.leisu.com/live/data-{event_id}",
                "mobile_odds": f"https://m.leisu.com/live/odds-{event_id}",
            }
        attempts.append(
            {
                "provider": "leisu",
                "label": "雷速体育",
                "status": "odds_matched_context_not_collected",
                "match_id": event_id,
                "detail": detail,
                "field_statuses": {
                    "venue": "not_collected",
                    "weather": "not_collected",
                    "referee": "not_collected",
                    "lineup": "not_collected",
                },
                "urls": urls,
            }
        )
    return attempts


def _dashboard_player_summary(player: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": str(player.get("name") or player.get("person") or "").strip(),
        "position": str(player.get("position") or "").strip(),
        "shirt_number": str(player.get("shirt_number") or player.get("shirtnumber") or "").strip(),
        "nationality": str(player.get("nationality") or player.get("nationality_name") or "").strip(),
        "captain": bool(player.get("captain")),
    }


def _dashboard_lineup_source(lineup: dict[str, Any]) -> dict[str, Any]:
    status = lineup.get("lineup_status") if isinstance(lineup.get("lineup_status"), dict) else {}
    basis = str(status.get("lineup_basis") or "")
    if basis == "official_lineups" and isinstance(lineup.get("official_lineups"), dict):
        return lineup.get("official_lineups") or {}
    if basis == "forecast_lineups" and isinstance(lineup.get("forecast_lineups"), dict):
        return lineup.get("forecast_lineups") or {}
    if isinstance(lineup.get("official_lineups"), dict):
        return lineup.get("official_lineups") or {}
    if isinstance(lineup.get("forecast_lineups"), dict):
        return lineup.get("forecast_lineups") or {}
    return {}


def _dashboard_lineup_side(lineup: dict[str, Any], side: str) -> dict[str, Any]:
    analysis = lineup.get("lineup_analysis") if isinstance(lineup.get("lineup_analysis"), dict) else {}
    analysis_side = analysis.get(side) if isinstance(analysis.get(side), dict) else {}
    source_side = _dashboard_lineup_source(lineup).get(side) or {}
    starters = [
        _dashboard_player_summary(player)
        for player in source_side.get("lineups") or []
        if isinstance(player, dict)
    ][:11]
    return {
        "formation": analysis_side.get("formation") or source_side.get("formation") or "",
        "starter_count": analysis_side.get("starter_count") or source_side.get("lineup_count") or len(starters),
        "starters": starters,
    }


def _dashboard_lineup_summary(lineup: Any) -> dict[str, Any]:
    if not isinstance(lineup, dict) or not lineup:
        return {
            "available": False,
            "basis": "",
            "home": {"formation": "", "starter_count": 0, "starters": []},
            "away": {"formation": "", "starter_count": 0, "starters": []},
            "warnings": ["lineup_unavailable"],
        }
    analysis = lineup.get("lineup_analysis") if isinstance(lineup.get("lineup_analysis"), dict) else {}
    status = lineup.get("lineup_status") if isinstance(lineup.get("lineup_status"), dict) else {}
    home = _dashboard_lineup_side(lineup, "home")
    away = _dashboard_lineup_side(lineup, "away")
    available = bool(
        analysis.get("available")
        or analysis.get("can_use_for_analysis")
        or home.get("starters")
        or away.get("starters")
    )
    return {
        "available": available,
        "basis": status.get("lineup_basis") or "",
        "home": home,
        "away": away,
        "warnings": analysis.get("warnings") or [],
        "analysis": analysis,
    }


def _dashboard_match_context(record: dict[str, Any], *, odds_snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
    raw = record.get("raw") if isinstance(record.get("raw"), dict) else {}
    raw_match_context = raw.get("match_context") if isinstance(raw.get("match_context"), dict) else None
    venue_paths = (
        ("match_context", "venue"),
        ("match_context", "lineup", "base", "field"),
        ("context", "venue"),
        ("venue",),
        ("match", "venue"),
        ("fixture", "venue"),
    )
    venue = _dashboard_context_path_value(raw, venue_paths)
    lineup = _dashboard_first_path(
        raw,
        (
            ("match_context", "lineup"),
            ("context", "lineup"),
            ("lineup",),
        ),
    )
    weather_paths = (
        ("match_context", "weather"),
        ("match_context", "weather_report"),
        ("match_context", "lineup", "base", "weather"),
        ("context", "weather"),
        ("context", "weather_report"),
        ("weather",),
        ("weather_report",),
    )
    weather = _dashboard_context_path_value(raw, weather_paths)
    referee_paths = (
        ("match_context", "referee"),
        ("match_context", "lineup", "base", "referee"),
        ("context", "referee"),
        ("referee",),
    )
    referee = _dashboard_context_path_value(raw, referee_paths)
    lineup_summary = _dashboard_lineup_summary(lineup)
    venue_field = _dashboard_context_field(venue)
    weather_field = _dashboard_context_field(weather)
    referee_field = _dashboard_context_field(referee)
    source = _dashboard_context_source(record, raw, raw_match_context)
    return {
        "source": source,
        "venue": venue_field,
        "weather": weather_field,
        "referee": referee_field,
        "lineup": lineup_summary,
        "players": {
            "available": bool(lineup_summary["home"]["starters"] or lineup_summary["away"]["starters"]),
            "home": lineup_summary["home"]["starters"],
            "away": lineup_summary["away"]["starters"],
        },
        "source_attempts": _dashboard_context_source_attempts(
            source=source,
            venue_field=venue_field,
            weather_field=weather_field,
            referee_field=referee_field,
            lineup_summary=lineup_summary,
            raw_source_attempts=(
                raw_match_context.get("source_attempts")
                if isinstance(raw_match_context, dict) and isinstance(raw_match_context.get("source_attempts"), list)
                else None
            ),
            odds_snapshot=odds_snapshot,
        ),
        "available_blocks": [
            key
            for key, field in (
                ("venue", venue_field),
                ("weather", weather_field),
                ("referee", referee_field),
                ("lineup", {"available": lineup_summary["available"]}),
            )
            if field.get("available")
        ],
    }


_DASHBOARD_CONTEXT_COVERAGE_LABELS = {
    "venue": "比赛场地",
    "weather": "天气",
    "referee": "裁判",
    "lineup": "阵容",
}


def _dashboard_context_coverage_status(context: dict[str, Any], key: str) -> str:
    if key == "lineup":
        if (context.get("lineup") or {}).get("available"):
            return "available"
        return "not_collected" if (context.get("source") or {}).get("status") == "not_collected" else "source_empty"
    field = context.get(key) if isinstance(context.get(key), dict) else {}
    status = str(field.get("status") or "").strip()
    return status if status in {"available", "source_empty", "not_collected"} else "not_collected"


def _dashboard_coverage_odds_snapshot(coverage: dict[str, Any]) -> dict[str, Any] | None:
    snapshot_count = int(coverage.get("snapshot_count") or 0)
    if snapshot_count <= 0:
        return None
    provider = str(coverage.get("provider") or "").strip()
    event_id = str(coverage.get("event_id") or "").strip()
    return {
        "snapshot_count": snapshot_count,
        "bookmaker_count": int(coverage.get("bookmaker_count") or 0),
        "market_types": [],
        "resolution": {
            "status": "matched",
            "provider": provider,
            "event_id": event_id,
            "league": str(coverage.get("league") or ""),
            "home_team": str(coverage.get("home_team") or ""),
            "away_team": str(coverage.get("away_team") or ""),
            "source_home_team": "",
            "source_away_team": "",
            "source_league": "",
            "match_score": None,
            "reason": "snapshot_coverage_match" if event_id else "",
        },
    }


def _dashboard_context_coverage(
    records: list[dict[str, Any]],
    *,
    snapshot_coverage: dict[str, dict[str, Any]] | None = None,
    market_db_path: str | None = None,
) -> dict[str, Any]:
    total = len(records)
    if not total:
        return {
            "total_count": 0,
            "source_counts": [],
            "fields": [
                {
                    "key": key,
                    "label": label,
                    "total_count": 0,
                    "available_count": 0,
                    "source_empty_count": 0,
                    "not_collected_count": 0,
                    "coverage_ratio": 0.0,
                    "summary": "暂无样本",
                }
                for key, label in _DASHBOARD_CONTEXT_COVERAGE_LABELS.items()
            ],
            "summary": "暂无赛事情报样本。",
        }

    source_counts_by_key: dict[tuple[str, str, str], int] = {}
    field_counts = {
        key: {"available": 0, "source_empty": 0, "not_collected": 0}
        for key in _DASHBOARD_CONTEXT_COVERAGE_LABELS
    }

    for record in records:
        odds_coverage = _dashboard_snapshot_coverage_for_record(
            record,
            snapshot_coverage=snapshot_coverage,
            market_db_path=market_db_path,
        )
        context = _dashboard_match_context(record, odds_snapshot=_dashboard_coverage_odds_snapshot(odds_coverage))
        source = context.get("source") if isinstance(context.get("source"), dict) else {}
        attempts = context.get("source_attempts") if isinstance(context.get("source_attempts"), list) else []
        counted_sources: set[tuple[str, str, str]] = set()
        for attempt in attempts:
            if not isinstance(attempt, dict):
                continue
            source_key = (
                str(attempt.get("status") or source.get("status") or ""),
                str(attempt.get("provider") or source.get("provider") or ""),
                str(attempt.get("label") or _dashboard_context_provider_label(str(attempt.get("provider") or ""))),
            )
            counted_sources.add(source_key)
        if not counted_sources:
            counted_sources.add(
                (
                    str(source.get("status") or ""),
                    str(source.get("provider") or ""),
                    str(source.get("label") or "来源未知"),
                )
            )
        for source_key in counted_sources:
            source_counts_by_key[source_key] = source_counts_by_key.get(source_key, 0) + 1
        for key in _DASHBOARD_CONTEXT_COVERAGE_LABELS:
            status = _dashboard_context_coverage_status(context, key)
            field_counts[key][status] = field_counts[key].get(status, 0) + 1

    source_counts = [
        {
            "status": status,
            "provider": provider,
            "label": label,
            "count": count,
        }
        for (status, provider, label), count in sorted(
            source_counts_by_key.items(),
            key=lambda item: (-item[1], item[0][2]),
        )
    ]
    fields = []
    for key, label in _DASHBOARD_CONTEXT_COVERAGE_LABELS.items():
        counts = field_counts[key]
        available_count = int(counts.get("available") or 0)
        source_empty_count = int(counts.get("source_empty") or 0)
        not_collected_count = int(counts.get("not_collected") or 0)
        summary_parts = [f"{available_count}/{total} 已采集"]
        if source_empty_count:
            summary_parts.append(f"{source_empty_count} 源站暂无")
        if not_collected_count:
            summary_parts.append(f"{not_collected_count} 本地未采集")
        fields.append(
            {
                "key": key,
                "label": label,
                "total_count": total,
                "available_count": available_count,
                "source_empty_count": source_empty_count,
                "not_collected_count": not_collected_count,
                "coverage_ratio": round_metric(available_count / total, 6) or 0.0,
                "summary": " · ".join(summary_parts),
            }
        )

    matched_source = next((item for item in source_counts if item["status"] == "matched"), source_counts[0])
    matched_count = int(matched_source.get("count") or 0) if matched_source.get("status") == "matched" else 0
    summary_priority = {"weather": 0, "venue": 1, "referee": 2, "lineup": 3}
    best_field = max(
        fields,
        key=lambda item: (
            int(item["available_count"]),
            -summary_priority.get(str(item.get("key") or ""), 99),
        ),
    )
    summary_parts = [f"{matched_source.get('label') or '源站'}已匹配 {matched_count}/{total} 场"]
    leisu_odds_count = sum(
        int(item.get("count") or 0)
        for item in source_counts
        if str(item.get("provider") or "").strip().lower() == "leisu"
        and str(item.get("status") or "") == "odds_matched_context_not_collected"
    )
    if leisu_odds_count:
        summary_parts.append(f"雷速体育赔率已匹配 {leisu_odds_count}/{total} 场")
    summary_parts.append(f"{best_field['label']} {best_field['available_count']}/{total} 场有值")
    summary = "；".join(summary_parts) + "。"
    return {
        "total_count": total,
        "source_counts": source_counts,
        "fields": fields,
        "summary": summary,
    }


def _dashboard_match_odds_snapshot(
    record: dict[str, Any],
    *,
    market_db_path: str | None = None,
) -> dict[str, Any]:
    rows = snapshot_store.find_market_snapshots(
        str(record.get("home_team") or ""),
        str(record.get("away_team") or ""),
        league=str(record.get("league") or ""),
        db_path=market_db_path,
        limit=20000,
    )
    rows.sort(
        key=lambda item: (
            str(item.get("fetched_at_utc") or ""),
            str(item.get("source_time_utc") or ""),
            str(item.get("bookmaker") or ""),
        ),
        reverse=True,
    )
    bookmakers = sorted({str(row.get("bookmaker") or "") for row in rows if row.get("bookmaker")})
    market_types = sorted({str(row.get("market_type") or "") for row in rows if row.get("market_type")})
    resolution_row = next(
        (
            row
            for row in rows
            if isinstance(row.get("raw"), dict)
            and any(
                (row.get("raw") or {}).get(key)
                for key in ("leisu_home_team", "leisu_away_team", "match_resolution_reason")
            )
        ),
        rows[0] if rows else None,
    )
    resolution_raw = (resolution_row or {}).get("raw") if isinstance((resolution_row or {}).get("raw"), dict) else {}
    record_home = str(record.get("home_team") or "")
    record_away = str(record.get("away_team") or "")
    record_league = str(record.get("league") or "")
    resolved_home = str((resolution_row or {}).get("home_team") or "")
    resolved_away = str((resolution_row or {}).get("away_team") or "")
    resolved_league = str((resolution_row or {}).get("league") or "")
    source_home = str(resolution_raw.get("leisu_home_team") or (resolved_home if resolved_home and resolved_home != record_home else ""))
    source_away = str(resolution_raw.get("leisu_away_team") or (resolved_away if resolved_away and resolved_away != record_away else ""))
    source_league = str(resolution_raw.get("leisu_league") or (resolved_league if resolved_league and resolved_league != record_league else ""))
    alias_match = bool(source_home or source_away or source_league)
    resolution = {
        "status": "matched" if rows else "local_snapshot_missing",
        "provider": "leisu" if rows else "",
        "event_id": str((resolution_row or {}).get("event_id") or ""),
        "league": resolved_league,
        "home_team": str(resolved_home or record_home),
        "away_team": str(resolved_away or record_away),
        "source_home_team": source_home,
        "source_away_team": source_away,
        "source_league": source_league,
        "match_score": round_metric(parse_float(resolution_raw.get("match_resolution_score"))),
        "reason": str(resolution_raw.get("match_resolution_reason") or ("snapshot_alias_match" if alias_match else "direct_snapshot_match" if rows else "")),
    }
    latest_rows = [
        {
            "provider": row.get("provider") or "",
            "bookmaker": row.get("bookmaker") or "",
            "market_type": row.get("market_type") or "",
            "selection": row.get("selection") or "",
            "decimal_odds": round_metric(parse_float(row.get("decimal_odds")), 4),
            "line": round_metric(parse_float(row.get("line")), 4),
            "source_time_utc": row.get("source_time_utc") or "",
            "fetched_at_utc": row.get("fetched_at_utc") or "",
        }
        for row in rows[:200]
    ]
    return {
        "snapshot_count": len(rows),
        "bookmaker_count": len(bookmakers),
        "bookmakers": bookmakers,
        "market_types": market_types,
        "latest_fetched_at_utc": max((str(row.get("fetched_at_utc") or "") for row in rows), default=""),
        "latest_source_time_utc": max((str(row.get("source_time_utc") or "") for row in rows), default=""),
        "latest_rows": latest_rows,
        "resolution": resolution,
        "consensus": snapshot_store.build_market_consensus(rows) if rows else {},
        "movement": snapshot_store.build_market_movement_summary(
            rows,
            home_team=str(record.get("home_team") or ""),
            away_team=str(record.get("away_team") or ""),
        ),
    }


def dashboard_record_detail(record_id: int | str, *, db_path: str | None = None) -> dict[str, Any]:
    """Return persisted evidence for one dashboard recommendation row."""
    record = learning_store.get_recommendation_record(record_id, db_path=db_path)
    if not record:
        return {
            "status": "not_found",
            "tool": "dashboard_record_detail",
            "record_id": str(record_id),
            "generated_at_utc": now_utc().isoformat(),
        }

    strategy_state = learning_store.get_strategy_state(
        db_path=db_path,
        market=str(record.get("market") or "asian_handicap"),
        mode=_dashboard_strategy_mode(record),
    )
    evidence = _dashboard_record_evidence(record, strategy_state)
    return {
        "status": "ok",
        "tool": "dashboard_record_detail",
        "generated_at_utc": now_utc().isoformat(),
        "record": _dashboard_settlement_row(record)
        if record.get("settlement_status") == "settled"
        else _dashboard_record_row(record),
        "evidence": evidence,
        "strategy_state": strategy_state,
        "timeline": _dashboard_detail_timeline(record, strategy_state),
        "policy": {
            "read_only": True,
            "no_real_bet": True,
            "data_rule": "Details read persisted MCP recommendation evidence; they do not trigger new analysis or betting actions.",
        },
    }


def _dashboard_probability_governance_for_detail(
    *,
    db_path: str | None = None,
    market_db_path: str | None = None,
    strategy_state: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    preliminary_prediction_ledger = _dashboard_prediction_ledger(
        db_path=db_path,
        market_db_path=market_db_path,
        limit=2000,
        strategy_state=strategy_state,
    )
    learning_effectiveness = _dashboard_learning_effectiveness(preliminary_prediction_ledger)
    probability_governance = learning_effectiveness.get("probability_governance") if isinstance(learning_effectiveness, dict) else None
    return probability_governance if isinstance(probability_governance, dict) else None


def dashboard_match_detail(
    ledger_id: str,
    *,
    db_path: str | None = None,
    market_db_path: str | None = None,
    enrich_live_context: bool = False,
) -> dict[str, Any]:
    """Return the full persisted sample detail behind one prediction ledger row."""
    resolved = _dashboard_record_from_ledger_id(ledger_id, db_path=db_path)
    if not resolved:
        return {
            "status": "not_found",
            "tool": "dashboard_match_detail",
            "ledger_id": str(ledger_id),
            "generated_at_utc": now_utc().isoformat(),
        }

    source, record = resolved
    if not _dashboard_record_has_display_match(record):
        return {
            "status": "not_found",
            "tool": "dashboard_match_detail",
            "ledger_id": str(ledger_id),
            "reason": "match_identity_missing",
            "generated_at_utc": now_utc().isoformat(),
        }
    strategy_state = learning_store.get_strategy_state(
        db_path=db_path,
        market=str(record.get("market") or "asian_handicap"),
        mode=_dashboard_strategy_mode(record),
    )
    probability_governance = _dashboard_probability_governance_for_detail(
        db_path=db_path,
        market_db_path=market_db_path,
        strategy_state=strategy_state,
    )
    odds_snapshot = _dashboard_match_odds_snapshot(record, market_db_path=market_db_path)
    clv_tracking = snapshot_store.closing_line_value_for_records(
        [record],
        db_path=market_db_path,
        limit=1,
    )
    match_context = (
        _dashboard_context_with_leisu_snapshot_enrichment(record, odds_snapshot=odds_snapshot)
        if enrich_live_context
        else _dashboard_match_context(record, odds_snapshot=odds_snapshot)
    )
    detail_odds_coverage = {
        "snapshot_count": odds_snapshot.get("snapshot_count") or 0,
        "bookmaker_count": odds_snapshot.get("bookmaker_count") or 0,
        "market_type_count": len(odds_snapshot.get("market_types") or []),
        "latest_fetched_at_utc": odds_snapshot.get("latest_fetched_at_utc") or "",
    }
    timeline = _dashboard_detail_timeline(record, strategy_state)
    if odds_snapshot["snapshot_count"]:
        timeline.append(
            {
                "title": "赔率快照",
                "detail": (
                    f"{odds_snapshot['snapshot_count']} 条 · "
                    f"{odds_snapshot['bookmaker_count']} 家公司 · "
                    f"{', '.join(odds_snapshot['market_types']) or 'unknown'}"
                ),
                "at_utc": odds_snapshot.get("latest_fetched_at_utc") or "",
            }
        )
    clv_record = (clv_tracking.get("records") or [{}])[0] if isinstance(clv_tracking, dict) else {}
    clv = clv_record.get("clv") if isinstance(clv_record, dict) and isinstance(clv_record.get("clv"), dict) else {}
    if clv.get("status") == "available":
        timeline.append(
            {
                "title": "CLV 收盘价",
                "detail": (
                    f"推荐价 {clv.get('prediction_decimal_odds')} · 收盘价 {clv.get('closing_decimal_odds')} · "
                    f"CLV {_percent_text(clv.get('clv_return')) or '暂无'}"
                ),
                "at_utc": clv.get("latest_closing_snapshot_utc") or "",
            }
        )

    snapshot_coverage = snapshot_store.market_snapshot_coverage_by_match(db_path=market_db_path)
    record_row = _dashboard_prediction_row(
        record,
        source=source,
        snapshot_coverage=snapshot_coverage,
        strategy_state=strategy_state,
        probability_governance=probability_governance,
    )

    return {
        "status": "ok",
        "tool": "dashboard_match_detail",
        "generated_at_utc": now_utc().isoformat(),
        "record": record_row,
        "match_context": match_context,
        "odds_snapshot": odds_snapshot,
        "clv_tracking": clv_tracking,
        "evidence": _dashboard_record_evidence(
            record,
            strategy_state,
            match_context=match_context,
            prediction_type=str(record_row.get("prediction_type") or ""),
            rejection_reason=str(record_row.get("rejection_reason") or ""),
            odds_coverage=detail_odds_coverage,
            probability_governance=probability_governance,
        ),
        "strategy_state": strategy_state,
        "timeline": timeline,
        "policy": {
            "read_only": True,
            "no_real_bet": True,
            "data_rule": (
                "Match details read persisted prediction samples, context, and odds snapshots only."
                if not enrich_live_context
                else "Match details read persisted samples and explicitly requested supplemental context enrichment."
            ),
        },
    }


def _dashboard_learning_events(
    *,
    strategy_state: dict[str, Any],
    observations: list[dict[str, Any]],
    settlements: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    if strategy_state:
        events.append(
            {
                "kind": "strategy",
                "severity": "ok" if strategy_state.get("active") else "info",
                "title": "策略状态刷新",
                "detail": (
                    f"{strategy_state.get('status')} · samples={strategy_state.get('sample_count')} · "
                    f"minP={strategy_state.get('min_calibrated_probability')}"
                ),
                "at_utc": strategy_state.get("updated_at_utc") or "",
            }
        )
    snapshot_reanalysis = AUTO_LEARNING_STATE.get("last_snapshot_reanalysis")
    if isinstance(snapshot_reanalysis, dict) and snapshot_reanalysis:
        reanalyzed_count = int(snapshot_reanalysis.get("reanalyzed_count") or 0)
        formal_promoted_count = int(snapshot_reanalysis.get("formal_promoted_count") or 0)
        still_observation_count = int(snapshot_reanalysis.get("still_observation_count") or 0)
        failed_count = int(snapshot_reanalysis.get("failed_count") or 0)
        events.append(
            {
                "kind": "snapshot_reanalysis",
                "severity": "warning" if failed_count else "ok",
                "title": "赔率补齐复算",
                "detail": (
                    f"已复算 {reanalyzed_count} 场，升级正式推荐 {formal_promoted_count} 场，"
                    f"继续观察 {still_observation_count} 场，失败 {failed_count} 场。"
                ),
                "at_utc": snapshot_reanalysis.get("at_utc") or "",
            }
        )
    for record in observations[:5]:
        raw = record.get("raw") or {}
        events.append(
            {
                "kind": "observation",
                "severity": "info",
                "title": "新增纸面预测",
                "detail": f"{_dashboard_matchup(record)} · {raw.get('reason') or record.get('recommendation') or 'observed'}",
                "at_utc": record.get("created_at_utc") or "",
            }
        )
    for record in settlements[:5]:
        events.append(
            {
                "kind": "settlement",
                "severity": "ok" if int(record.get("hit") or 0) else "warning",
                "title": "自动结算",
                "detail": f"{_dashboard_matchup(record)} · {record.get('home_score')}-{record.get('away_score')} · profit={record.get('profit_units')}",
                "at_utc": record.get("settled_at_utc") or record.get("created_at_utc") or "",
            }
        )
    return sorted(events, key=lambda item: str(item.get("at_utc") or ""), reverse=True)[:12]


def dashboard_snapshot(
    *,
    db_path: str | None = None,
    market_db_path: str | None = None,
    limit: int = 500,
) -> dict[str, Any]:
    """Build a read-only dashboard snapshot from persisted paper-learning state."""
    bounded_limit = max(10, min(int(limit or 500), 500))
    # Warm enrichment indexes in the background; safe to fail
    _ensure_fdo_index_warm()
    _ensure_dongqiudi_logo_cache_warm()
    calibration = learning_store.calibration_status(db_path=db_path, limit=20)
    strategy_states = calibration.get("strategy_states") or []
    strategy_state = next(
        (
            item
            for item in strategy_states
            if item.get("market") == "asian_handicap" and item.get("mode") == "balanced"
        ),
        learning_store.get_strategy_state(db_path=db_path, market="asian_handicap", mode="balanced"),
    )
    open_records = [
        record
        for record in learning_store.list_recommendation_records(db_path=db_path, status="open", limit=bounded_limit)
        if _dashboard_record_has_display_match(record)
    ]
    settled_records = [
        record
        for record in learning_store.list_recommendation_records(db_path=db_path, status="settled", limit=bounded_limit)
        if _dashboard_record_has_display_match(record)
    ]
    snapshot_coverage = snapshot_store.market_snapshot_coverage_for_records(
        open_records + settled_records,
        db_path=market_db_path,
    )
    observations = [record for record in open_records if _dashboard_is_observation(record)]
    asian_picks: list[dict[str, Any]] = []
    policy_rejected_picks: list[dict[str, Any]] = []
    for record in open_records:
        if record.get("market") != "asian_handicap" or _dashboard_is_observation(record):
            continue
        policy_rejection = _dashboard_open_pick_policy_rejection(
            record,
            snapshot_coverage=snapshot_coverage,
            market_db_path=market_db_path,
        )
        if policy_rejection:
            policy_rejected_picks.append({**record, "_dashboard_policy_rejection_reason": policy_rejection})
        else:
            asian_picks.append(record)
    record_counts = calibration.get("record_counts") or {}
    recent_settlements = [_dashboard_settlement_row(record) for record in settled_records[:12]]
    preliminary_prediction_ledger = _dashboard_prediction_ledger(
        db_path=db_path,
        market_db_path=market_db_path,
        limit=max(bounded_limit, 2000),
        strategy_state=strategy_state,
    )
    learning_effectiveness = _dashboard_learning_effectiveness(preliminary_prediction_ledger)
    full_prediction_ledger = _dashboard_prediction_ledger(
        db_path=db_path,
        market_db_path=market_db_path,
        limit=max(bounded_limit, 2000),
        strategy_state=strategy_state,
        probability_governance=learning_effectiveness.get("probability_governance")
        if isinstance(learning_effectiveness.get("probability_governance"), dict)
        else None,
    )
    full_prediction_source_records = _dashboard_prediction_source_records(
        db_path=db_path,
        limit=max(bounded_limit, 2000),
    )
    prediction_kpis = _dashboard_prediction_kpis(full_prediction_ledger)
    prediction_ledger = _dashboard_display_prediction_ledger(full_prediction_ledger, limit=bounded_limit)
    market_snapshot_summary = snapshot_store.market_snapshot_summary(db_path=market_db_path)
    last_market_snapshot_sync = AUTO_LEARNING_STATE.get("last_market_snapshot_sync") or (
        AUTO_LEARNING_STATE.get("last_result_summary") or {}
    ).get("market_snapshot_sync")
    if isinstance(last_market_snapshot_sync, dict):
        market_snapshot_summary = {**market_snapshot_summary, "last_sync": last_market_snapshot_sync}
    kpis = {
        "open_records": len(open_records),
        "settled_records": len(settled_records),
        "tracked_only_records": int(record_counts.get("tracked_only") or 0),
        "duplicate_ignored_records": int(record_counts.get("duplicate_ignored") or 0),
        "asian_pick_count": len(asian_picks),
        "observation_count": len(observations),
        "calibration_bucket_count": int(calibration.get("bucket_count") or 0),
        "strategy_sample_count": int(strategy_state.get("sample_count") or 0),
        "live_calibration_active": bool(strategy_state.get("active")),
    }
    candidate_filters = _dashboard_candidate_filters(
        observations + policy_rejected_picks,
        snapshot_coverage=snapshot_coverage,
        market_db_path=market_db_path,
    )
    decision_audit = _dashboard_decision_audit(
        prediction_kpis=prediction_kpis,
        strategy_state=strategy_state,
        candidate_filters=candidate_filters,
        prediction_ledger=full_prediction_ledger,
        market_snapshot_summary=market_snapshot_summary,
    )
    learning_diagnostics = _dashboard_learning_diagnostics(
        prediction_kpis=prediction_kpis,
        strategy_state=strategy_state,
        candidate_filters=candidate_filters,
        prediction_ledger=full_prediction_ledger,
        market_snapshot_summary=market_snapshot_summary,
    )
    backtest_curve = _dashboard_backtest_curve(full_prediction_ledger)
    prediction_quality = _dashboard_prediction_quality(full_prediction_ledger)
    recommendation_opportunity = _dashboard_recommendation_opportunity(
        full_prediction_ledger,
        strategy_state=strategy_state,
        candidate_filters=candidate_filters,
        learning_effectiveness=learning_effectiveness,
        prediction_quality=prediction_quality,
    )
    adaptive_learning_plan = _dashboard_adaptive_learning_plan(
        learning_effectiveness=learning_effectiveness,
        prediction_quality=prediction_quality,
        recommendation_opportunity=recommendation_opportunity,
    )
    full_prediction_records = [record for _source, record in full_prediction_source_records]
    context_snapshot_coverage = snapshot_store.market_snapshot_coverage_for_records(
        full_prediction_records,
        db_path=market_db_path,
    )
    context_coverage = _dashboard_context_coverage(
        full_prediction_records,
        snapshot_coverage=context_snapshot_coverage,
        market_db_path=market_db_path,
    )
    clv_tracking = snapshot_store.closing_line_value_for_records(
        full_prediction_records,
        db_path=market_db_path,
        limit=min(bounded_limit, 30),
        allow_fuzzy_match=False,
    )
    model_governance = _dashboard_model_governance(
        full_prediction_records,
        learning_effectiveness=learning_effectiveness,
        clv_tracking=clv_tracking,
    )
    dashboard_contract = _dashboard_contract_health(
        prediction_kpis=prediction_kpis,
        learning_effectiveness=learning_effectiveness,
        prediction_quality=prediction_quality,
        adaptive_learning_plan=adaptive_learning_plan,
        recommendation_opportunity=recommendation_opportunity,
        market_snapshot_summary=market_snapshot_summary,
        context_coverage=context_coverage,
    )
    production_readiness = _dashboard_production_readiness(
        prediction_kpis=prediction_kpis,
        learning_effectiveness=learning_effectiveness,
        recommendation_opportunity=recommendation_opportunity,
        dashboard_contract=dashboard_contract,
        clv_tracking=clv_tracking,
    )
    prediction_accountability = _dashboard_prediction_accountability(
        prediction_kpis=prediction_kpis,
        strategy_state=strategy_state,
        learning_effectiveness=learning_effectiveness,
        recommendation_opportunity=recommendation_opportunity,
        candidate_filters=candidate_filters,
    )
    profitability_forecast = _dashboard_profitability_forecast(
        prediction_kpis=prediction_kpis,
        strategy_state=strategy_state,
        clv_tracking=clv_tracking,
    )
    market_breakdown = _dashboard_market_breakdown(full_prediction_ledger)
    try:
        from football_data_mcp import validation_store
        latest_validation = validation_store.get_latest_validation(db_path=db_path)
    except Exception:
        latest_validation = None
    try:
        from football_data_mcp import league_strategy
        league_breakdown = league_strategy.compute_league_breakdown(db_path=db_path)
    except Exception:
        league_breakdown = None
    return {
        "status": "ok",
        "tool": "dashboard_snapshot",
        "generated_at_utc": now_utc().isoformat(),
        "db_path": db_path or learning_store.learning_db_path(),
        "kpis": kpis,
        "prediction_kpis": prediction_kpis,
        "market_snapshot_summary": market_snapshot_summary,
        "context_coverage": context_coverage,
        "strategy_state": strategy_state,
        "asian_picks": [_dashboard_record_row(record) for record in asian_picks[:20]],
        "candidate_filters": candidate_filters,
        "recent_settlements": recent_settlements,
        "prediction_ledger": prediction_ledger,
        "learning_events": _dashboard_learning_events(
            strategy_state=strategy_state,
            observations=observations,
            settlements=settled_records,
        ),
        "auto_learning_state": dict(AUTO_LEARNING_STATE),
        "decision_audit": decision_audit,
        "learning_diagnostics": learning_diagnostics,
        "learning_effectiveness": learning_effectiveness,
        "model_governance": model_governance,
        "clv_tracking": clv_tracking,
        "backtest_curve": backtest_curve,
        "prediction_quality": prediction_quality,
        "adaptive_learning_plan": adaptive_learning_plan,
        "recommendation_opportunity": recommendation_opportunity,
        "dashboard_contract": dashboard_contract,
        "production_readiness": production_readiness,
        "prediction_accountability": prediction_accountability,
        "profitability_forecast": profitability_forecast,
        "market_breakdown": market_breakdown,
        "latest_validation": latest_validation,
        "league_breakdown": league_breakdown,
        "buckets": calibration.get("buckets") or [],
        "policy": {
            "read_only": True,
            "no_search_inputs": True,
            "data_rule": "Dashboard reads persisted MCP paper-learning state; it does not place bets or trigger user-query analysis.",
        },
    }


async def auto_learning_daemon(
    *,
    interval_seconds: int = 600,
    timezone_name: str | None = None,
    top_n: int = 12,
    limit: int = 80,
    asian_window_minutes: int = 10,
    parlay_window_minutes: int = 10,
    learning_observation_limit: int = 30,
    shadow_prediction_limit: int = 100,
    analysis_candidate_limit: int = 80,
    analysis_concurrency: int = 10,
    include_market_snapshot_sync: bool = True,
    market_snapshot_window_minutes: int = 24 * 60,
    market_snapshot_limit: int = 80,
    market_snapshot_concurrency: int = 4,
    market_snapshot_require_quality_gate: bool = True,
    include_snapshot_reanalysis: bool = True,
    snapshot_reanalysis_limit: int = 20,
    snapshot_reanalysis_concurrency: int = 4,
    enforce_settlement_coverage: bool = True,
    league_allowlist: list[str] | frozenset[str] | None = None,
) -> None:
    bounded_asian_window_minutes = max(1, min(int(asian_window_minutes or 60), 48 * 60))
    bounded_parlay_window_minutes = max(1, min(int(parlay_window_minutes or JINGCAI_PARLAY_DEFAULT_WINDOW_MINUTES), 48 * 60))
    bounded_learning_observation_limit = max(0, min(int(learning_observation_limit or 0), 100))
    bounded_shadow_prediction_limit = max(0, min(int(shadow_prediction_limit or 0), 500))
    bounded_analysis_candidate_limit = max(1, min(int(analysis_candidate_limit or 80), 100))
    bounded_analysis_concurrency = max(1, min(int(analysis_concurrency or 10), 16))
    bounded_market_snapshot_window = max(1, min(int(market_snapshot_window_minutes or 24 * 60), 48 * 60))
    bounded_market_snapshot_limit = max(1, min(int(market_snapshot_limit or 80), 100))
    bounded_market_snapshot_concurrency = max(1, min(int(market_snapshot_concurrency or 4), 10))
    bounded_snapshot_reanalysis_limit = max(1, min(int(snapshot_reanalysis_limit or 20), 100))
    bounded_snapshot_reanalysis_concurrency = max(1, min(int(snapshot_reanalysis_concurrency or 4), 10))
    AUTO_LEARNING_STATE.update(
        {
            "enabled": True,
            "interval_seconds": max(60, int(interval_seconds or 600)),
            "timezone_name": timezone_name or "Asia/Shanghai",
            "top_n": top_n,
            "limit": limit,
            "asian_window_minutes": bounded_asian_window_minutes,
            "parlay_window_minutes": bounded_parlay_window_minutes,
            "learning_observation_limit": bounded_learning_observation_limit,
            "shadow_prediction_limit": bounded_shadow_prediction_limit,
            "analysis_candidate_limit": bounded_analysis_candidate_limit,
            "analysis_concurrency": bounded_analysis_concurrency,
            "market_snapshot_sync_enabled": bool(include_market_snapshot_sync),
            "market_snapshot_window_minutes": bounded_market_snapshot_window,
            "market_snapshot_limit": bounded_market_snapshot_limit,
            "market_snapshot_concurrency": bounded_market_snapshot_concurrency,
            "market_snapshot_require_quality_gate": bool(market_snapshot_require_quality_gate),
            "snapshot_reanalysis_enabled": bool(include_snapshot_reanalysis),
            "snapshot_reanalysis_limit": bounded_snapshot_reanalysis_limit,
            "snapshot_reanalysis_concurrency": bounded_snapshot_reanalysis_concurrency,
            "enforce_settlement_coverage": bool(enforce_settlement_coverage),
            "league_allowlist_size": (
                len(league_allowlist) if league_allowlist is not None
                else (
                    _empirical_allowlist_size() if enforce_settlement_coverage else 0
                )
            ),
        }
    )
    janitor_interval_seconds = int(os.getenv("FOOTBALL_DATA_JANITOR_INTERVAL_SECONDS", "21600"))  # 6h
    last_janitor_ts = 0.0
    while True:
        AUTO_LEARNING_STATE["last_started_at_utc"] = now_utc().isoformat()
        # Periodic DB janitor (every 6h by default) — runs before the learning
        # cycle so cleanup happens on a freshly settled DB
        now_ts = time.time()
        if now_ts - last_janitor_ts >= janitor_interval_seconds:
            try:
                from football_data_mcp import db_janitor
                janitor_report = await asyncio.to_thread(db_janitor.run_janitor, dry_run=False)
                AUTO_LEARNING_STATE["last_janitor"] = {
                    "at_utc": now_utc().isoformat(),
                    "deleted": janitor_report["totals"]["deleted"],
                    "marked": janitor_report["totals"]["marked"],
                    "inspected": janitor_report["totals"]["inspected"],
                }
                last_janitor_ts = now_ts
            except Exception as exc:
                AUTO_LEARNING_STATE["last_janitor_error"] = f"{type(exc).__name__}: {exc}"

        try:
            result = await run_auto_learning_cycle(
                timezone_name=timezone_name or "Asia/Shanghai",
                asian_window_minutes=bounded_asian_window_minutes,
                parlay_window_minutes=bounded_parlay_window_minutes,
                learning_observation_limit=bounded_learning_observation_limit,
                shadow_prediction_limit=bounded_shadow_prediction_limit,
                analysis_candidate_limit=bounded_analysis_candidate_limit,
                analysis_concurrency=bounded_analysis_concurrency,
                include_market_snapshot_sync=include_market_snapshot_sync,
                market_snapshot_window_minutes=bounded_market_snapshot_window,
                market_snapshot_limit=bounded_market_snapshot_limit,
                market_snapshot_concurrency=bounded_market_snapshot_concurrency,
                market_snapshot_require_quality_gate=market_snapshot_require_quality_gate,
                include_snapshot_reanalysis=include_snapshot_reanalysis,
                snapshot_reanalysis_limit=bounded_snapshot_reanalysis_limit,
                snapshot_reanalysis_concurrency=bounded_snapshot_reanalysis_concurrency,
                top_n=top_n,
                limit=limit,
                auto_settle=True,
                enforce_settlement_coverage=enforce_settlement_coverage,
                league_allowlist=league_allowlist,
            )
            AUTO_LEARNING_STATE["run_count"] = int(AUTO_LEARNING_STATE.get("run_count") or 0) + 1
            AUTO_LEARNING_STATE["last_error"] = None
            AUTO_LEARNING_STATE["last_result_summary"] = {
                "run_id": result.get("run_id"),
                "saved_record_count": result.get("saved_record_count"),
                "saved_shadow_prediction_count": result.get("saved_shadow_prediction_count"),
                "learning_phase": result.get("learning_phase"),
                "asian_record_count": (result.get("asian_shortlist") or {}).get("record_count"),
                "asian_learning_observation_record_count": (result.get("asian_shortlist") or {}).get(
                    "learning_observation_record_count"
                ),
                "asian_shadow_prediction_record_count": (result.get("asian_shortlist") or {}).get(
                    "shadow_prediction_record_count"
                ),
                "asian_total_candidates": (result.get("asian_shortlist") or {}).get("total_candidates"),
                "asian_analyzed_count": (result.get("asian_shortlist") or {}).get("analyzed_count"),
                "asian_not_analyzed_count": (result.get("asian_shortlist") or {}).get("not_analyzed_count"),
                "asian_eligible_count": (result.get("asian_shortlist") or {}).get("eligible_count"),
                "asian_returned_count": (result.get("asian_shortlist") or {}).get("returned_count"),
                "asian_rejected_count": (result.get("asian_shortlist") or {}).get("rejected_count"),
                "asian_rejection_reasons": (
                    ((result.get("asian_shortlist") or {}).get("funnel_report") or {}).get("rejection_reasons")
                    or {}
                ),
                "parlay_record_count": (result.get("jingcai_parlay") or {}).get("record_count"),
                "market_snapshot_sync": result.get("market_snapshot_sync"),
                "snapshot_reanalysis": result.get("snapshot_reanalysis"),
                "settled_count": ((result.get("settlement") or {}).get("settlement") or {}).get("settled_count"),
                "shadow_settled_count": ((result.get("settlement") or {}).get("shadow_settlement") or {}).get("settled_count"),
            }
        except Exception as exc:
            AUTO_LEARNING_STATE["last_error"] = f"{type(exc).__name__}: {exc}"
            print(f"football-data auto-learning error: {AUTO_LEARNING_STATE['last_error']}", flush=True)
        finally:
            AUTO_LEARNING_STATE["current_step"] = "idle"
            AUTO_LEARNING_STATE["last_finished_at_utc"] = now_utc().isoformat()
        await asyncio.sleep(max(60, int(interval_seconds or 600)))


## ─── Settlement-coverage allowlist ────────────────────────────────────────────
# Leagues where we can reliably get post-match scores from public sources
# (football-data.co.uk CSV + dongqiudi schedule_list + football-data.org).
# Recommendations outside this list are filtered out by default, because
# they'd accumulate as 'unsettleable' and skew KPIs without ever closing.
#
# Sources of coverage:
# - football-data.co.uk: top 18 European leagues (PL, BL1, SA, PD, FL1, etc.)
# - football-data.org free tier: PL, BL1, SA, PD, FL1, DED, PPL, ELC, CL, BSA, EC, CLI, WC
# - dongqiudi: mainstream men's leagues (CSL, JL, etc.) + UEFA competitions
#
# Use Chinese names from dongqiudi or league codes — _league_in_allowlist
# normalizes both with fuzzy matching.

SETTLEMENT_COVERED_LEAGUES_DEFAULT = frozenset({
    # ── Top 5 European leagues ──
    "英超", "英冠", "英甲", "英乙", "Premier League", "Championship",
    "西甲", "西乙", "La Liga", "Segunda División", "Primera División",
    "意甲", "意乙", "Serie A", "Serie B",
    "德甲", "德乙", "Bundesliga", "2. Bundesliga",
    "法甲", "法乙", "Ligue 1", "Ligue 2",
    # ── Other major European ──
    "荷甲", "葡超", "Eredivisie", "Primeira Liga",
    "苏超", "比甲", "土超", "希超", "瑞超", "挪超", "丹超", "奥甲",
    # ── European cups ──
    "欧冠", "欧联", "欧协", "欧国联", "Champions League", "Europa League",
    "Europa Conference League", "UEFA Champions League", "UEFA Europa League",
    "Nations League",
    # ── Top South American ──
    "巴甲", "Brasileirão", "Série A", "Campeonato Brasileiro",
    "Copa Libertadores", "解放者杯", "南美杯", "Sudamericana",
    "阿超", "阿甲",  # Argentina top tier
    # ── East Asian top tiers ──
    "中超", "Chinese Super League",
    "日职", "J联赛", "J-League", "J1",
    "韩K联", "K-League",
    # ── Top international ──
    "世界杯", "World Cup", "亚洲杯", "Asian Cup", "美洲杯", "Copa America",
    "欧洲杯", "Euro",
})

# League name normalization for fuzzy matching
_LEAGUE_NAME_SUFFIXES_TO_STRIP = ("联赛", " ", "  ")


def _normalize_league_for_match(name: str | None) -> str:
    """Normalize a league name for fuzzy comparison."""
    s = str(name or "").strip().lower()
    for suf in _LEAGUE_NAME_SUFFIXES_TO_STRIP:
        if suf and s.endswith(suf):
            s = s[: -len(suf)]
    return s.strip()


def _empirical_allowlist_size() -> int:
    """Return current merged allowlist size for daemon state reporting."""
    try:
        from football_data_mcp.empirical_allowlist import merged_allowlist
        return len(merged_allowlist(SETTLEMENT_COVERED_LEAGUES_DEFAULT))
    except Exception:
        return len(SETTLEMENT_COVERED_LEAGUES_DEFAULT)


def _league_in_allowlist(league: str | None, allowlist: frozenset[str] | set[str] | list[str]) -> bool:
    """Check if a league is in the allowlist with bidirectional substring match."""
    if not league:
        return False  # No league info → conservatively reject
    if not allowlist:
        return True   # Empty allowlist = no filter
    canonical = _normalize_league_for_match(league)
    if not canonical:
        return False
    for allowed in allowlist:
        allowed_norm = _normalize_league_for_match(allowed)
        if not allowed_norm:
            continue
        if canonical == allowed_norm:
            return True
        if canonical in allowed_norm or allowed_norm in canonical:
            return True
    return False


async def shortlist_value_matches(
    *,
    query: str = "",
    league: str | None = None,
    as_of: str | None = None,
    timezone_name: str | None = None,
    window_minutes: int = 60,
    top_n: int = 3,
    limit: int = 30,
    min_edge: float = 0.01,
    mode: str = "confidence",
    target_market: str = "any",
    min_calibrated_probability: float = 0.58,
    min_decimal_odds: float = 1.65,
    max_decimal_odds: float = 2.05,
    min_value_edge: float = 0.02,
    require_core_markets: bool = True,
    analysis_candidate_limit: int = 30,
    analysis_concurrency: int = 6,
    recommendation_log_path: str | None = None,
    use_learning_policy: bool = True,
    league_allowlist: list[str] | frozenset[str] | None = None,
    enforce_settlement_coverage: bool = False,
    db_path: str | None = None,
) -> dict[str, Any]:
    """List imminent matches, analyze each with MCP calculations, and rank actionable value picks."""
    mode = str(mode or "value").strip().lower()
    mode = {"balance": "balanced"}.get(mode, mode)
    if mode not in {"value", "confidence", "balanced"}:
        mode = "value"
    target_market = _normalize_shortlist_target_market(target_market)
    learning_policy = _learning_policy_for_shortlist(
        mode=mode,
        target_market=target_market,
        use_learning_policy=use_learning_policy,
        db_path=db_path,
    )
    min_calibrated_probability = _clamp(parse_float(min_calibrated_probability) or 0.0, 0.0, 1.0)
    min_decimal_odds = max(1.01, parse_float(min_decimal_odds) or 1.65)
    max_decimal_odds = max(min_decimal_odds, parse_float(max_decimal_odds) or 2.05)
    min_value_edge = max(0.0, parse_float(min_value_edge) or 0.0)
    if learning_policy.get("active"):
        min_calibrated_probability = max(
            min_calibrated_probability,
            parse_float(learning_policy.get("min_calibrated_probability")) or min_calibrated_probability,
        )
        min_decimal_odds = max(
            min_decimal_odds,
            parse_float(learning_policy.get("min_decimal_odds")) or min_decimal_odds,
        )
        policy_max_odds = parse_float(learning_policy.get("max_decimal_odds"))
        if policy_max_odds is not None:
            max_decimal_odds = min(max_decimal_odds, max(min_decimal_odds, policy_max_odds))
        min_value_edge = max(
            min_value_edge,
            parse_float(learning_policy.get("min_value_edge")) or min_value_edge,
        )
    bounded_window_minutes = max(1, min(int(window_minutes or 60), 24 * 60))
    window_hours: float | int
    if bounded_window_minutes % 60 == 0:
        window_hours = bounded_window_minutes // 60
    else:
        window_hours = bounded_window_minutes / 60

    match_list = await list_matches(
        query=query or "",
        league=league,
        as_of=as_of,
        timezone_name=timezone_name,
        window_hours=window_hours,
        limit=limit,
        analysis_ready_only=False,
    )
    matches = match_list.get("matches") or []
    picks: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    # Apply settlement-coverage allowlist filter BEFORE analysis to save compute
    # and prevent unsettleable records from entering the recommendation pool.
    # The effective allowlist combines the curated default with empirically-
    # proven leagues (>=3 settled records in past 60 days).
    effective_allowlist: frozenset[str] | None = None
    if league_allowlist is not None:
        effective_allowlist = frozenset(league_allowlist)
    elif enforce_settlement_coverage:
        try:
            from football_data_mcp.empirical_allowlist import merged_allowlist
            effective_allowlist = merged_allowlist(
                SETTLEMENT_COVERED_LEAGUES_DEFAULT,
                db_path=db_path,
            )
        except Exception:
            effective_allowlist = SETTLEMENT_COVERED_LEAGUES_DEFAULT

    if effective_allowlist:
        allowed_matches = []
        for m in matches:
            m_league = str(m.get("league") or m.get("competition_name") or "")
            if _league_in_allowlist(m_league, effective_allowlist):
                allowed_matches.append(m)
            else:
                rejected.append({
                    "match": m,
                    "reason": "league_not_in_settlement_allowlist",
                    "rejected_league": m_league,
                })
        matches = allowed_matches

    bounded_limit = max(1, int(limit or 30))
    bounded_analysis_limit = max(1, min(bounded_limit, int(analysis_candidate_limit or 30), 100))
    bounded_concurrency = max(1, min(int(analysis_concurrency or 6), 16))
    analysis_matches = matches[:bounded_analysis_limit]

    async def analyze_for_shortlist(match: dict[str, Any]) -> dict[str, Any]:
        match_query = _shortlist_match_query(match)
        if not match_query:
            return {"kind": "rejected", "payload": {"match": match, "reason": "match_query_missing"}}
        try:
            analysis = await analyze_single_match(
                match_query,
                league=match.get("league") or league,
                as_of=as_of,
                timezone_name=timezone_name,
                window_hours=window_hours,
                include_source_probe=False,
            )
        except Exception as exc:
            return {
                "kind": "rejected",
                "payload": {
                    "match": match,
                    "query": match_query,
                    "reason": "analysis_exception",
                    "error": f"{type(exc).__name__}: {exc}",
                },
            }

        targeted_analysis = _shortlist_analysis_for_target_market(analysis, target_market)
        targeted_analysis = _apply_learning_policy_to_analysis(
            targeted_analysis,
            mode=mode,
            learning_policy=learning_policy,
            db_path=db_path,
        )
        reason = _shortlist_rejection_reason(
            targeted_analysis,
            min_edge=min_edge,
            require_core_markets=require_core_markets,
            mode=mode,
            min_calibrated_probability=min_calibrated_probability,
            min_decimal_odds=min_decimal_odds,
            max_decimal_odds=max_decimal_odds,
            min_value_edge=min_value_edge,
        )
        if reason:
            return {
                "kind": "rejected",
                "payload": {
                    "match": targeted_analysis.get("match") or (targeted_analysis.get("agent_brief") or {}).get("match") or match,
                    "match_context": targeted_analysis.get("match_context") or {},
                    "query": match_query,
                    "reason": reason,
                    "model_engine": _compact_model_engine_evidence(targeted_analysis),
                    "best_candidate": targeted_analysis.get("best_candidate")
                    or (targeted_analysis.get("betting_decision_support") or {}).get("best_candidate")
                    or {},
                    "blocking_flags": (targeted_analysis.get("betting_decision_support") or {}).get("blocking_flags") or [],
                    "quality": targeted_analysis.get("quality") or {},
                    "data_completeness": _shortlist_coverage_score(targeted_analysis),
                    "learning_policy": targeted_analysis.get("learning_policy") or learning_policy,
                },
            }
        return {"kind": "pick", "payload": _shortlist_pick_from_analysis(targeted_analysis, mode=mode)}

    semaphore = asyncio.Semaphore(bounded_concurrency)

    async def run_limited(match: dict[str, Any]) -> dict[str, Any]:
        async with semaphore:
            return await analyze_for_shortlist(match)

    if analysis_matches:
        for result in await asyncio.gather(*(run_limited(match) for match in analysis_matches)):
            if result.get("kind") == "pick":
                picks.append(result.get("payload") or {})
            else:
                rejected.append(result.get("payload") or {})

    if mode == "confidence":
        picks.sort(
            key=lambda item: (
                parse_float((item.get("selection_confidence") or {}).get("calibrated_probability")) or 0.0,
                parse_float((item.get("selection_confidence") or {}).get("reliability_score")) or 0.0,
                parse_float((item.get("selection_confidence") or {}).get("raw_model_probability")) or 0.0,
                parse_float((item.get("best_candidate") or {}).get("edge")) or 0.0,
            ),
            reverse=True,
        )
    elif mode == "balanced":
        picks.sort(
            key=lambda item: (
                parse_float((item.get("selection_confidence") or {}).get("balanced_score")) or 0.0,
                parse_float((item.get("selection_confidence") or {}).get("value_edge")) or 0.0,
                parse_float((item.get("selection_confidence") or {}).get("calibrated_probability")) or 0.0,
                parse_float((item.get("selection_confidence") or {}).get("reliability_score")) or 0.0,
            ),
            reverse=True,
        )
    else:
        picks.sort(
            key=lambda item: (
                parse_float(item.get("value_score")) or 0.0,
                parse_float((item.get("best_candidate") or {}).get("edge")) or 0.0,
                parse_float(item.get("confidence")) or 0.0,
            ),
            reverse=True,
        )
    returned = picks[: max(1, int(top_n or 3))]
    funnel_report = _shortlist_funnel_report(
        total_candidates=len(matches),
        analyzed_count=len(analysis_matches),
        not_analyzed_count=max(0, len(matches) - len(analysis_matches)),
        eligible_count=len(picks),
        returned_count=len(returned),
        rejected=rejected,
    )
    record = {
        "tool": "shortlist_value_matches",
        "generated_at_utc": now_utc().isoformat(),
        "query": query or "",
        "league": league or "",
        "mode": mode,
        "target_market": target_market,
        "balanced_thresholds": {
            "min_calibrated_probability": round_metric(min_calibrated_probability),
            "min_decimal_odds": round_metric(min_decimal_odds, 4),
            "max_decimal_odds": round_metric(max_decimal_odds, 4),
            "min_value_edge": round_metric(min_value_edge),
        },
        "learning_policy": learning_policy,
        "window_minutes": bounded_window_minutes,
        "time_window_policy": match_list.get("time_window_policy") or {},
        "total_candidates": len(matches),
        "analyzed_count": len(analysis_matches),
        "not_analyzed_count": max(0, len(matches) - len(analysis_matches)),
        "eligible_count": len(picks),
        "returned_count": len(returned),
        "rejected_count": len(rejected),
        "funnel_report": funnel_report,
        "picks": returned,
    }
    log_result = _append_recommendation_log(record, recommendation_log_path)

    return {
        "status": "ok",
        "tool": "shortlist_value_matches",
        "query": query or "",
        "league": league or "",
        "mode": mode,
        "target_market": target_market,
        "balanced_thresholds": {
            "min_calibrated_probability": round_metric(min_calibrated_probability),
            "min_decimal_odds": round_metric(min_decimal_odds, 4),
            "max_decimal_odds": round_metric(max_decimal_odds, 4),
            "min_value_edge": round_metric(min_value_edge),
        },
        "learning_policy": learning_policy,
        "window_minutes": bounded_window_minutes,
        "time_window_policy": match_list.get("time_window_policy") or {},
        "source": match_list.get("source") or {},
        "total_candidates": len(matches),
        "analyzed_count": len(analysis_matches),
        "analysis_candidate_limit": bounded_analysis_limit,
        "analysis_concurrency": bounded_concurrency,
        "not_analyzed_count": max(0, len(matches) - len(analysis_matches)),
        "eligible_count": len(picks),
        "returned_count": len(returned),
        "rejected_count": len(rejected),
        "funnel_report": funnel_report,
        "picks": returned,
        "rejected": rejected,
        "analysis_input_policy": (
            "The shortlist scans all schedule-anchored fixtures in the time window, then analyze_single_match tries to "
            "resolve usable odds from fixture odds, detail pages, and supplemental sources. Matches without calculable "
            "odds are rejected as data-blocked and are not given a betting direction."
        ),
        "ranking_policy": (
            "MCP lightly lists upcoming matches, concurrently analyzes up to 100 listed candidates, "
            "rejects hard blockers/missing core markets/no positive edge, then ranks by calibrated_probability, "
            "reliability_score, raw model probability, and edge. near_kickoff_under_60m is ignored in confidence mode because the requested window is near-kickoff. "
            f"target_market={target_market}."
            if mode == "confidence"
            else "MCP lightly lists upcoming matches, concurrently analyzes up to 100 listed candidates, "
            "rejects hard blockers/missing core markets/no positive edge, then requires calibrated_probability, decimal odds, "
            "and value_edge thresholds before ranking by balanced_score. near_kickoff_under_60m is ignored in balanced mode because the requested window is near-kickoff. "
            f"target_market={target_market}."
            if mode == "balanced"
            else "MCP lightly lists upcoming matches, concurrently analyzes up to 100 listed candidates, "
            "rejects hard blockers/missing core markets/no positive edge, then ranks by recommendation strength, "
            "edge, confidence, data coverage, and caution penalties. shortlist fast path skips repeated per-match source probes."
        ),
        "recommendation_log": log_result,
        "agent_guidance": (
            "Use picks as the shortlist conclusion. For each pick, display final_execution_advice.headline as the final action, "
            "final_decision.headline only as raw MCP pre-risk recommendation, plus best_candidate, value_score, and main caution flags. "
            "Do not recalculate probabilities outside MCP."
        ),
    }


async def team_form(division: str, home_team: str, away_team: str, kickoff_utc: str | None) -> dict[str, Any]:
    if not division or not kickoff_utc:
        return {"available": False, "reason": "division_or_kickoff_missing"}
    if division.startswith("dongqiudi:"):
        return {
            "available": False,
            "reason": "season_form_source_not_available_for_dongqiudi_fixture",
            "guidance": "Use Dongqiudi schedule/odds as the fixture anchor, then corroborate form with a dedicated team stats source.",
        }
    kickoff = date_parser.parse(kickoff_utc)
    try:
        rows, source = await load_season(division, kickoff)
    except Exception as exc:
        return {"available": False, "reason": f"season_csv_unavailable: {exc}"}

    return {
        "available": True,
        "source": source,
        "home": summarize_team(rows, home_team, kickoff),
        "away": summarize_team(rows, away_team, kickoff),
    }


def summarize_team(rows: list[dict[str, str]], team: str, kickoff: datetime, limit: int = 5) -> dict[str, Any]:
    completed = []
    for row in rows:
        if not row.get("FTR"):
            continue
        row_kickoff = parse_kickoff(row)
        if not row_kickoff or row_kickoff.astimezone(timezone.utc) >= kickoff.astimezone(timezone.utc):
            continue
        if row.get("HomeTeam") != team and row.get("AwayTeam") != team:
            continue
        completed.append((row_kickoff, row))
    completed.sort(key=lambda item: item[0], reverse=True)

    matches = []
    wins = draws = losses = goals_for = goals_against = 0
    for _, row in completed[:limit]:
        is_home = row.get("HomeTeam") == team
        fthg = int(row.get("FTHG") or 0)
        ftag = int(row.get("FTAG") or 0)
        gf = fthg if is_home else ftag
        ga = ftag if is_home else fthg
        if gf > ga:
            result = "W"
            wins += 1
        elif gf == ga:
            result = "D"
            draws += 1
        else:
            result = "L"
            losses += 1
        goals_for += gf
        goals_against += ga
        matches.append(
            {
                "date": row.get("Date"),
                "home_team": row.get("HomeTeam"),
                "away_team": row.get("AwayTeam"),
                "score": f"{fthg}-{ftag}",
                "result_for_team": result,
            }
        )

    return {
        "team": team,
        "sample_size": len(matches),
        "record": {"wins": wins, "draws": draws, "losses": losses},
        "goals_for": goals_for,
        "goals_against": goals_against,
        "matches": matches,
    }


async def analyze_single_match(
    query: str,
    *,
    home_team: str | None = None,
    away_team: str | None = None,
    league: str | None = None,
    as_of: str | None = None,
    timezone_name: str | None = None,
    window_hours: int = 24,
    include_source_probe: bool = True,
) -> dict[str, Any]:
    best, search = await get_best_match(
        query,
        home_team=home_team,
        away_team=away_team,
        league=league,
        as_of=as_of,
        timezone_name=timezone_name,
        window_hours=window_hours,
    )
    if not best:
        return {
            "status": "not_found",
            "message": "No matching fixture found in Football-Data fixtures.csv.",
            "search": search,
        }

    odds = best.get("odds_summary") or {}
    match_context = None
    context_match = _dongqiudi_context_candidate_for_match(best, search)
    if context_match and context_match.get("match_id"):
        match_context = await dongqiudi_match_context(str(context_match["match_id"]))
        best = _attach_context_match_identity(best, context_match)
        odds = merge_odds(odds, ((match_context.get("odds_index") or {}).get("odds") or {}))
    match_context = await _enrich_match_context_with_leisu(
        match_context,
        best,
        query=query,
        home_team=home_team,
        away_team=away_team,
        league=league,
        as_of=as_of,
        timezone_name=timezone_name,
    )
    if odds.get("has_valid_numeric_odds") and not odds.get("quality_contract"):
        odds = with_odds_quality_contract(odds, best.get("source") or {})
    if include_source_probe:
        probes = await probe_sources(
            query,
            home_team=home_team,
            away_team=away_team,
            limit_chars=300,
        )
    else:
        probes = {
            "usable_source_count": 0,
            "sources": [],
            "selection_policy": {
                "skipped": True,
                "reason": "shortlist_fast_path_avoids_repeated_source_probe",
            },
        }
    if match_context and (match_context.get("pre_analysis") or {}).get("available"):
        form = (match_context.get("pre_analysis") or {"available": False, "reason": "pre_analysis_unavailable"})
    else:
        form = await team_form(
            str(best.get("division") or ""),
            str(best.get("home_team") or ""),
            str(best.get("away_team") or ""),
            best.get("kickoff_utc"),
        )
    quality_flags = []
    quality_warnings = []
    if not best["time_window"]["in_window"]:
        quality_flags.append(best["time_window"]["reason"])
    if not odds.get("has_valid_numeric_odds"):
        quality_flags.append("odds_missing")
    odds_quality_contract = odds.get("quality_contract") or {}
    if odds_quality_contract and not odds_quality_contract.get("can_use_for_calculation", True):
        quality_flags.extend(
            flag
            for flag in odds_quality_contract.get("hard_flags", [])
            if flag not in quality_flags
        )
    if odds_quality_contract:
        quality_warnings.extend(
            flag
            for flag in odds_quality_contract.get("soft_flags", [])
            if flag not in quality_warnings
        )
    if (best.get("match_score") or 0) < 0.68:
        quality_flags.append("low_match_confidence")
    if match_context and not ((match_context.get("readiness") or {}).get("pre_analysis_available")):
        quality_flags.append("deep_context_limited")
    quality = {
        "is_bettable_input": not quality_flags,
        "flags": quality_flags,
        "warnings": quality_warnings,
        "guidance": (
            "If is_bettable_input is false, downstream agents should output observation/no-bet "
            "unless they can resolve the specific missing item with explicit evidence. "
            "Warnings mean the price snapshot may be usable, but the affected metadata must not be overstated."
        ),
    }
    data_bundle = await get_match_data_bundle(
        query,
        home_team=str(best.get("home_team") or home_team or ""),
        away_team=str(best.get("away_team") or away_team or ""),
        league=league or str(best.get("league") or ""),
        as_of=as_of,
        timezone_name=timezone_name,
        window_hours=window_hours,
        include_match_resolution=False,
        include_context_refresh=include_source_probe,
    )
    betting_decision_support = build_betting_decision_support(
        match=best,
        odds=odds,
        form=form,
        match_context=match_context,
        quality_flags=quality_flags,
        quality_warnings=quality_warnings,
        market_movement=data_bundle.get("market_movement") or {},
    )
    analysis_pack = build_analysis_pack(
        match=best,
        odds=odds,
        form=form,
        match_context=match_context,
        quality=quality,
        betting_decision_support=betting_decision_support,
        data_bundle=data_bundle,
    )
    source_probe_summary = {
        "usable_source_count": probes["usable_source_count"],
        "sources": [
            {
                "key": item.get("key"),
                "name": item.get("name"),
                "ok": item.get("ok"),
                "role": item.get("role"),
                "match_hint_score": item.get("match_hint_score"),
                "blocked_or_low_value_reason": item.get("blocked_or_low_value_reason"),
                "url": item.get("url"),
            }
            for item in probes["sources"]
        ],
        "selection_policy": probes["selection_policy"],
    }
    model_card = build_model_card(
        match=best,
        odds=odds,
        form=form,
        quality=quality,
        betting_decision_support=betting_decision_support,
    )
    professional_scorecard = build_professional_scorecard(
        match=best,
        odds=odds,
        form=form,
        match_context=match_context,
        source_probe=source_probe_summary,
        quality=quality,
        betting_decision_support=betting_decision_support,
        model_card=model_card,
    )
    decision_audit = build_decision_audit(
        match=best,
        betting_decision_support=betting_decision_support,
        professional_scorecard=professional_scorecard,
        model_card=model_card,
    )
    analysis_pack["model_card"] = model_card
    analysis_pack["professional_scorecard"] = professional_scorecard
    analysis_pack["decision_audit"] = {
        "audit_id": decision_audit["audit_id"],
        "agent_contract": decision_audit["agent_contract"],
    }
    analysis_pack["agent_brief"]["model_card"] = model_card
    analysis_pack["agent_brief"]["professional_scorecard"] = professional_scorecard
    analysis_pack["agent_brief"]["decision_audit_id"] = decision_audit["audit_id"]

    return {
        "status": "ok",
        "agent_brief": analysis_pack.get("agent_brief") or {},
        "final_decision": betting_decision_support.get("final_decision") or {},
        "market_candidates": betting_decision_support.get("market_candidates") or [],
        "best_candidate": betting_decision_support.get("best_candidate") or {},
        "final_execution_advice": betting_decision_support.get("final_execution_advice") or {},
        "risk_overlay": betting_decision_support.get("risk_overlay") or {},
        "professional_scorecard": professional_scorecard,
        "model_card": model_card,
        "decision_audit": decision_audit,
        "match": best,
        "analysis_pack": analysis_pack,
        "betting_decision_support": betting_decision_support,
        "model_engine": betting_decision_support.get("model_engine") or {},
        "quality": quality,
        "data_bundle": data_bundle,
        "time_window": best.get("time_window"),
        "time_window_policy": search.get("time_window_policy"),
        "odds": {
            **odds,
            "validity_rule": (
                "Use the fixture's own source when it exposes concrete numeric odds. "
                "Dongqiudi schedule_list covers broad match lists including J.League; "
                "Football-Data fixtures.csv remains the primary numeric source for its covered European leagues."
            ),
        },
        "form": form,
        "match_context": match_context,
        "source_probe": source_probe_summary,
        "search_audit": {
            "candidate_count": search["candidate_count"],
            "top_candidates": search["candidates"][:3],
        },
    }


async def source_health() -> dict[str, Any]:
    checks = []
    started = time.time()
    try:
        fixtures, source = await load_fixtures()
        odds_rows = sum(1 for row in fixtures if odds_from_row(row)["has_valid_numeric_odds"])
        checks.append(
            {
                "source": "football-data fixtures.csv",
                "required": True,
                "ok": True,
                "url": FIXTURES_URL,
                "row_count": len(fixtures),
                "rows_with_numeric_odds": odds_rows,
                "fetched_at_utc": source["fetched_at_utc"],
            }
        )
    except Exception as exc:
        checks.append({"source": "football-data fixtures.csv", "required": True, "ok": False, "url": FIXTURES_URL, "error": str(exc)})

    try:
        as_of = datetime.now(DEFAULT_USER_TIMEZONE)
        matches, source = await load_dongqiudi_window(as_of, 24)
        checks.append(
            {
                "source": "dongqiudi schedule_list",
                "required": True,
                "ok": True,
                "url": source.get("url") if source else DONGQIUDI_SCHEDULE_URL,
                "row_count": len(matches),
                "rows_with_numeric_odds": sum(1 for row in matches if odds_from_dongqiudi_match(row)["has_valid_numeric_odds"]),
                "fetched_at_utc": source.get("fetched_at_utc") if source else None,
            }
        )
    except Exception as exc:
        checks.append({"source": "dongqiudi schedule_list", "required": True, "ok": False, "url": DONGQIUDI_SCHEDULE_URL, "error": str(exc)})

    try:
        as_of = datetime.now(DEFAULT_USER_TIMEZONE)
        matches, source = await load_leisu_schedule_for_date(as_of)
        checks.append(
            {
                "source": "leisu schedule",
                "required": False,
                "ok": bool(matches),
                "url": source.get("url") if source else LEISU_SCHEDULE_URL,
                "row_count": len(matches),
                "rows_with_match_ids": sum(1 for row in matches if row.get("match_id")),
                "rows_with_numeric_odds": 0,
                "fetched_at_utc": source.get("fetched_at_utc") if source else None,
                "role": "supplemental_chinese_schedule_and_links",
            }
        )
    except Exception as exc:
        checks.append({"source": "leisu schedule", "required": False, "ok": False, "url": LEISU_SCHEDULE_URL, "error": str(exc)})

    leisu_proxy = os.getenv("LEISU_ODDS_PROXY_URL", "").strip()
    leisu_cookie = os.getenv("LEISU_COOKIE", "").strip()
    leisu_acw = os.getenv("LEISU_ACW_SC_V2", "").strip()
    checks.append(
        {
            "source": "leisu odds",
            "required": False,
            "ok": bool(leisu_proxy or leisu_cookie or leisu_acw),
            "url_template": LEISU_ODDS_URL_TEMPLATE,
            "status": "proxy_configured"
            if leisu_proxy
            else "cookie_configured"
            if leisu_cookie or leisu_acw
            else "direct_probe_only",
            "role": "optional multi-company 1X2/AH/totals odds probe; direct HTTP may hit Aliyun WAF",
            "required_env_for_stable_fetch": ["LEISU_ODDS_PROXY_URL", "LEISU_COOKIE", "LEISU_ACW_SC_V2"],
        }
    )

    snapshot_counts = snapshot_store.provider_snapshot_counts()
    external_health = external_sources.external_provider_health(snapshot_counts)
    checks.extend(
        [
            {
                "source": "The Odds API",
                "required": False,
                "ok": external_health["the_odds_api"]["configured"] or external_health["the_odds_api"]["snapshot_count"] > 0,
                **external_health["the_odds_api"],
            },
            {
                "source": "Sportmonks Football API",
                "required": False,
                "ok": external_health["sportmonks"]["configured"],
                **external_health["sportmonks"],
            },
            {
                "source": "API-Football",
                "required": False,
                "ok": external_health["api_football"]["configured"],
                **external_health["api_football"],
            },
            {
                "source": "football-data.org",
                "required": False,
                "ok": external_health["football_data_org"]["configured"],
                **external_health["football_data_org"],
            },
        ]
    )

    probes = await probe_sources()
    return {
        "ok": all(item.get("ok") for item in checks if item.get("required", True)),
        "latency_ms": round((time.time() - started) * 1000),
        "checks": checks,
        "snapshot_store": {
            "db_path": snapshot_store.snapshot_db_path(),
            "provider_counts": snapshot_counts,
        },
        "external_provider_health": external_health,
        "source_probe": probes,
        "policy": {
            "primary_numeric_odds_source": "football-data.co.uk fixtures.csv",
            "paid_odds_snapshot_source": "The Odds API when THE_ODDS_API_KEY is configured",
            "paid_context_source": "Sportmonks or API-Football when configured",
            "secondary_probe_sources": [
                source["name"]
                for source in PROBE_SOURCES
                if source["key"] != "football_data_fixtures"
            ],
            "reason": "The MCP probes multiple sources, but only promotes sources that return parseable concrete evidence.",
            "leisu_policy": "Leisu is used for Chinese schedule/team-name/status/link corroboration; it is not promoted as an odds source unless concrete odds are parsed.",
            "leisu_odds_policy": "Leisu odds are probed through probe_leisu_odds and promoted only when access and quality gates pass; WAF challenges require cookie/proxy-assisted fetch.",
        },
    }


def run(coro):
    return asyncio.run(coro)
