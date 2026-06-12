from __future__ import annotations

from football_data_mcp import league_strategy


def test_manual_blocked_leagues_include_repo_defaults(monkeypatch):
    monkeypatch.delenv("FOOTBALL_DATA_LEAGUE_BLOCKLIST", raising=False)

    blocked = league_strategy._manual_blocked_leagues()

    assert "南球杯" in blocked
    assert "阿大都乙" in blocked
    assert "解放者杯" in blocked
    assert "澳足总" in blocked
    assert "冈比亚超" in blocked


def test_is_league_allowed_blocks_effective_blocklist(monkeypatch):
    monkeypatch.setattr(
        league_strategy,
        "compute_league_breakdown",
        lambda db_path=None: {
            "by_league": {"南球杯": {"classification": "losing", "log_loss_diff": 0.02}},
            "manual_blocked_leagues": [],
            "effective_blocked_leagues": ["南球杯"],
        },
    )

    result = league_strategy.is_league_allowed("南球杯")

    assert result["allowed"] is False
    assert result["mode"] == "blocked"
    assert result["reason"] == "league_in_blocklist"
    assert result["classification"] == "losing"


def test_is_league_allowed_blocks_manual_blocklist(monkeypatch):
    monkeypatch.setattr(
        league_strategy,
        "compute_league_breakdown",
        lambda db_path=None: {
            "by_league": {},
            "manual_blocked_leagues": ["澳足总"],
            "effective_blocked_leagues": ["澳足总"],
        },
    )

    result = league_strategy.is_league_allowed("澳足总")

    assert result["allowed"] is False
    assert result["classification"] == "manual_blocked"


def test_is_league_allowed_blocks_negative_trend_league(monkeypatch):
    monkeypatch.setattr(
        league_strategy,
        "compute_league_breakdown",
        lambda db_path=None: {
            "by_league": {"澳足总": {"classification": "insufficient_data", "log_loss_diff": None}},
            "manual_blocked_leagues": [],
            "losing_leagues": [],
            "negative_trend_blocked_leagues": ["澳足总"],
            "effective_blocked_leagues": ["澳足总"],
        },
    )

    result = league_strategy.is_league_allowed("澳足总")

    assert result["allowed"] is False
    assert result["classification"] == "negative_trend_blocked"


def test_manual_blocked_leagues_merge_env_override(monkeypatch):
    monkeypatch.setenv("FOOTBALL_DATA_LEAGUE_BLOCKLIST", "自定义联赛,澳足总")

    blocked = league_strategy._manual_blocked_leagues()

    assert "自定义联赛" in blocked
    assert "澳足总" in blocked
    assert "南球杯" in blocked
