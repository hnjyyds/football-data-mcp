from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from typing import Any


MAINSTREAM_CUP_KEYWORDS = frozenset({
    "欧冠",
    "欧联",
    "欧协",
    "欧国联",
    "世界杯",
    "欧洲杯",
    "亚洲杯",
    "美洲杯",
    "解放者杯",
    "南美杯",
    "南球杯",
    "英足总杯",
    "英联杯",
    "德国杯",
    "意大利杯",
    "法国杯",
    "国王杯",
    "uefa champions league",
    "champions league",
    "uefa europa league",
    "europa league",
    "europa conference league",
    "conference league",
    "nations league",
    "world cup",
    "euro",
    "asian cup",
    "copa america",
    "copa libertadores",
    "libertadores",
    "copa sudamericana",
    "sudamericana",
    "fa cup",
    "efl cup",
    "dfb pokal",
    "coppa italia",
    "copa del rey",
    "coupe de france",
})

LOW_TIER_ALLOW_EXCEPTIONS = frozenset({
    "英冠",
    "英甲",
    "英乙",
    "西乙",
    "意乙",
    "德乙",
    "法乙",
    "championship",
    "league one",
    "league two",
    "segunda división",
    "segunda division",
    "serie b",
    "2. bundesliga",
    "ligue 2",
})

RESERVE_YOUTH_TERMS = (
    "后备",
    "預備",
    "预备",
    "青年",
    "青锦",
    "reserve",
    "reserves",
    "youth",
    "academy",
)
TEAM_RESERVE_YOUTH_TERMS = (
    "后备",
    "預備",
    "预备",
    "后备队",
    "预备队",
    "青年队",
    "青年军",
    "青年梯队",
    "reserve",
    "reserves",
    "academy",
)
WOMEN_TERMS = ("女足", "女超", "女甲", "女子", "women", "women's", "womens", "ladies")
FRIENDLY_TERMS = ("友谊", "友誼", "热身", "friendly", "friendlies")
LOW_TIER_REGIONAL_TERMS = (
    "地区",
    "地区联赛",
    "州联",
    "州超",
    "省联",
    "县联",
    "业余",
    "業餘",
    "半职业",
    "阿后备",
    "中乙",
    "美乙2",
    "美乙",
    "巴丙",
    "巴丁",
    "阿丙",
    "阿丁",
    "澳维",
    "澳昆",
    "澳南",
    "澳威",
    "澳西",
    "regional",
    "state league",
    "county league",
    "amateur",
    "semi pro",
    "semipro",
    "division 3",
    "division 4",
    "third division",
    "fourth division",
)
LOW_TIER_CUP_TERMS = (
    "地区杯",
    "州杯",
    "省杯",
    "县杯",
    "业余杯",
    "業餘杯",
    "预备杯",
    "青年杯",
    "资格赛",
    "资格杯",
    "预选赛",
    "预选杯",
    "regional cup",
    "state cup",
    "county cup",
    "amateur cup",
    "qualifying cup",
)


def match_policy_text(*parts: str | None) -> str:
    """Fold source text into one comparable policy string."""
    folded = unicodedata.normalize("NFKC", " ".join(str(part or "") for part in parts))
    folded = folded.lower()
    folded = re.sub(r"[\s\-_/·]+", " ", folded)
    return folded.strip()


def contains_any_policy_term(text: str, terms: Iterable[str]) -> bool:
    return any(str(term).lower() in text for term in terms)


def is_mainstream_cup_text(text: str) -> bool:
    return contains_any_policy_term(text, MAINSTREAM_CUP_KEYWORDS)


def is_low_tier_exception_text(text: str) -> bool:
    return contains_any_policy_term(text, LOW_TIER_ALLOW_EXCEPTIONS)


def league_hard_exclusion_reason(
    league: str | None,
    *,
    home_team: str | None = None,
    away_team: str | None = None,
) -> str | None:
    """Return a hard exclusion reason for match categories we do not want to learn from.

    These are product-level exclusions, not recommendation thresholds: even if
    empirical samples exist, reserve/youth/women/friendlies and obvious
    lower-tier regional competitions should not enter the analysis queue.
    """
    league_text = match_policy_text(league)
    team_text = match_policy_text(home_team, away_team)
    match_text = match_policy_text(league, home_team, away_team)
    if re.search(r"(?<![a-z0-9])u\s*(?:17|18|19|20|21|22|23)(?![a-z0-9])", match_text):
        return "excluded_reserve_or_youth_match"
    if contains_any_policy_term(league_text, RESERVE_YOUTH_TERMS):
        return "excluded_reserve_or_youth_match"
    if contains_any_policy_term(team_text, TEAM_RESERVE_YOUTH_TERMS):
        return "excluded_reserve_or_youth_match"
    if contains_any_policy_term(match_text, WOMEN_TERMS):
        return "excluded_women_match"
    if contains_any_policy_term(match_text, FRIENDLY_TERMS):
        return "excluded_friendly_match"

    if league_text and not is_low_tier_exception_text(league_text):
        if contains_any_policy_term(league_text, LOW_TIER_REGIONAL_TERMS):
            return "excluded_low_tier_or_regional_match"
        if re.search(
            r"(?<![a-z0-9])(?:[3-9](?:rd|th)\s+division|division\s+[3-9]|tier\s+[3-9])(?![a-z0-9])",
            league_text,
        ):
            return "excluded_low_tier_or_regional_match"

    has_cup_word = "杯" in league_text or re.search(r"(?<![a-z0-9])cup(?![a-z0-9])", league_text) is not None
    if has_cup_word and not is_mainstream_cup_text(league_text):
        if contains_any_policy_term(league_text, LOW_TIER_CUP_TERMS):
            return "excluded_low_tier_or_regional_cup"
        return "excluded_non_mainstream_cup"
    return None


def match_hard_exclusion_reason(match: dict[str, Any]) -> str | None:
    """Return the hard exclusion reason for a schedule/database match, if any."""
    return league_hard_exclusion_reason(
        str(match.get("league") or match.get("competition_name") or ""),
        home_team=str(match.get("home_team") or match.get("home") or ""),
        away_team=str(match.get("away_team") or match.get("away") or ""),
    )
