"""Unit tests for the settlement-coverage league allowlist filter."""
from __future__ import annotations

from football_data_mcp.sources import (
    SETTLEMENT_COVERED_LEAGUES_DEFAULT,
    _league_in_allowlist,
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
    for l in top5_zh + top5_en:
        assert _league_in_allowlist(l, SETTLEMENT_COVERED_LEAGUES_DEFAULT), f"missing: {l}"


def test_default_allowlist_covers_uefa_competitions():
    for l in ["欧冠", "欧联", "Champions League", "Europa League"]:
        assert _league_in_allowlist(l, SETTLEMENT_COVERED_LEAGUES_DEFAULT), f"missing: {l}"


def test_default_allowlist_covers_brazilian_top_tier():
    for l in ["巴甲", "Brasileirão", "Série A"]:
        assert _league_in_allowlist(l, SETTLEMENT_COVERED_LEAGUES_DEFAULT), f"missing: {l}"
