"""Unit tests for the settlement-coverage league allowlist filter."""
from __future__ import annotations

from football_data_mcp.sources import (
    SETTLEMENT_COVERED_LEAGUES_DEFAULT,
    _league_in_allowlist,
    _match_hard_exclusion_reason,
    _normalize_league_for_match,
)


# ─── Normalization ─────────────────────────────────────────────────────────────


def test_normalize_strips_suffixes_and_whitespace():
    assert _normalize_league_for_match("英超联赛") == "英超"
    assert _normalize_league_for_match("  英超 ") == "英超"
    assert _normalize_league_for_match("Premier League") == "premier league"


def test_normalize_handles_none():
    assert _normalize_league_for_match(None) == ""
    assert _normalize_league_for_match("") == ""


# ─── Exact + fuzzy matching ────────────────────────────────────────────────────


def test_exact_chinese_match():
    assert _league_in_allowlist("英超", SETTLEMENT_COVERED_LEAGUES_DEFAULT)
    assert _league_in_allowlist("西甲", SETTLEMENT_COVERED_LEAGUES_DEFAULT)
    assert _league_in_allowlist("欧冠", SETTLEMENT_COVERED_LEAGUES_DEFAULT)


def test_exact_english_match():
    assert _league_in_allowlist("Premier League", SETTLEMENT_COVERED_LEAGUES_DEFAULT)
    assert _league_in_allowlist("Champions League", SETTLEMENT_COVERED_LEAGUES_DEFAULT)


def test_substring_match_chinese():
    # Real-world variations should match
    assert _league_in_allowlist("英超联赛", SETTLEMENT_COVERED_LEAGUES_DEFAULT)
    assert _league_in_allowlist("意甲联赛", SETTLEMENT_COVERED_LEAGUES_DEFAULT)


def test_minor_leagues_rejected():
    """The whole reason this filter exists."""
    assert not _league_in_allowlist("澳昆女超", SETTLEMENT_COVERED_LEAGUES_DEFAULT)
    assert not _league_in_allowlist("中乙", SETTLEMENT_COVERED_LEAGUES_DEFAULT)
    assert not _league_in_allowlist("哈萨克甲", SETTLEMENT_COVERED_LEAGUES_DEFAULT)
    assert not _league_in_allowlist("巴青锦", SETTLEMENT_COVERED_LEAGUES_DEFAULT)
    assert not _league_in_allowlist("阿后备", SETTLEMENT_COVERED_LEAGUES_DEFAULT)
    assert not _league_in_allowlist("伊朗甲", SETTLEMENT_COVERED_LEAGUES_DEFAULT)


def test_empty_league_rejected():
    """Conservative: no league info → reject (would create unsettleable record)."""
    assert not _league_in_allowlist("", SETTLEMENT_COVERED_LEAGUES_DEFAULT)
    assert not _league_in_allowlist(None, SETTLEMENT_COVERED_LEAGUES_DEFAULT)


def test_empty_allowlist_disables_filter():
    """Empty allowlist = no filter, allow everything."""
    assert _league_in_allowlist("澳昆女超", frozenset())
    assert _league_in_allowlist("anything", frozenset())


def test_custom_allowlist():
    """User-provided allowlist takes precedence."""
    custom = frozenset({"英超", "西甲"})
    assert _league_in_allowlist("英超", custom)
    assert _league_in_allowlist("西甲", custom)
    assert not _league_in_allowlist("意甲", custom)
    assert not _league_in_allowlist("德甲", custom)


def test_default_allowlist_covers_top_5_european():
    """Top 5 European leagues must always be in the default allowlist."""
    top5_zh = ["英超", "西甲", "意甲", "德甲", "法甲"]
    top5_en = ["Premier League", "La Liga", "Serie A", "Bundesliga", "Ligue 1"]
    for league in top5_zh + top5_en:
        assert _league_in_allowlist(league, SETTLEMENT_COVERED_LEAGUES_DEFAULT), f"missing: {league}"


def test_default_allowlist_covers_uefa_competitions():
    for league in ["欧冠", "欧联", "Champions League", "Europa League"]:
        assert _league_in_allowlist(league, SETTLEMENT_COVERED_LEAGUES_DEFAULT), f"missing: {league}"


def test_default_allowlist_covers_brazilian_top_tier():
    for league in ["巴甲", "Brasileirão", "Série A"]:
        assert _league_in_allowlist(league, SETTLEMENT_COVERED_LEAGUES_DEFAULT), f"missing: {league}"


def test_hard_exclusion_blocks_noisy_match_categories():
    cases = [
        (
            {"league": "阿后备", "home_team": "河床后备队", "away_team": "博卡后备队"},
            "excluded_reserve_or_youth_match",
        ),
        (
            {"league": "冰岛U19", "home_team": "青年主队", "away_team": "青年客队"},
            "excluded_reserve_or_youth_match",
        ),
        (
            {"league": "澳昆女超", "home_team": "布里斯班女足", "away_team": "黄金海岸女足"},
            "excluded_women_match",
        ),
        (
            {"league": "国际友谊", "home_team": "A队", "away_team": "B队"},
            "excluded_friendly_match",
        ),
        (
            {"league": "奥地利业余杯", "home_team": "A队", "away_team": "B队"},
            "excluded_low_tier_or_regional_match",
        ),
        (
            {"league": "澳大利亚足总杯预选赛", "home_team": "A队", "away_team": "B队"},
            "excluded_low_tier_or_regional_cup",
        ),
    ]

    for match, expected_reason in cases:
        assert _match_hard_exclusion_reason(match) == expected_reason


def test_hard_exclusion_keeps_mainstream_leagues_and_cups():
    for match in [
        {"league": "英超", "home_team": "阿森纳", "away_team": "切尔西"},
        {"league": "英冠", "home_team": "利兹联", "away_team": "莱斯特城"},
        {"league": "中甲", "home_team": "广州豹", "away_team": "深圳青年人"},
        {"league": "欧冠", "home_team": "皇马", "away_team": "拜仁"},
        {"league": "英足总杯", "home_team": "曼城", "away_team": "利物浦"},
        {"league": "Copa Libertadores", "home_team": "Flamengo", "away_team": "River Plate"},
        {"league": "World Cup", "home_team": "France", "away_team": "Brazil"},
    ]:
        assert _match_hard_exclusion_reason(match) is None
