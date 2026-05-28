"""Unit tests for football-data.org adapter — covers normalization and caching."""
from __future__ import annotations

from football_data_mcp import data_sources_registry as fdo


def test_normalize_fdo_match_extracts_all_fields():
    raw = {
        "id": 557106,
        "utcDate": "2026-05-27T00:30:00Z",
        "status": "FINISHED",
        "matchday": 6,
        "stage": "GROUP_STAGE",
        "lastUpdated": "2026-05-27T02:59:18Z",
        "competition": {"id": 2152, "name": "Copa Libertadores", "code": "CLI"},
        "homeTeam": {
            "id": 4268, "name": "Club Universitario de Deportes",
            "shortName": "Universitario", "tla": "CUD",
            "crest": "https://crests.football-data.org/4268.png",
        },
        "awayTeam": {
            "id": 4437, "name": "CD Tolima", "shortName": "Tolima",
            "tla": "TOL", "crest": "https://crests.football-data.org/4437.png",
        },
        "score": {"fullTime": {"home": 1, "away": 2}},
        "referees": [{"name": "Juan Benítez"}, {"name": "Other Ref"}],
    }
    out = fdo._normalize_fdo_match(raw)
    assert out["match_id"] == "fdo:557106"
    assert out["fdo_id"] == 557106
    assert out["kickoff_utc"] == "2026-05-27T00:30:00Z"
    assert out["status"] == "FINISHED"
    assert out["league"] == "Copa Libertadores"
    assert out["league_code"] == "CLI"
    assert out["home_team"] == "Club Universitario de Deportes"
    assert out["home_team_logo_url"] == "https://crests.football-data.org/4268.png"
    assert out["away_team"] == "CD Tolima"
    assert out["home_score"] == 1
    assert out["away_score"] == 2
    assert out["referees"] == ["Juan Benítez", "Other Ref"]
    assert out["source"] == "football-data.org"


def test_normalize_handles_missing_score_and_referees():
    raw = {
        "id": 1,
        "utcDate": "2026-06-01T18:00:00Z",
        "status": "SCHEDULED",
        "competition": {"name": "Premier League", "code": "PL"},
        "homeTeam": {"name": "Arsenal", "tla": "ARS"},
        "awayTeam": {"name": "Chelsea", "tla": "CHE"},
        "score": {"fullTime": {"home": None, "away": None}},
        "referees": [],
    }
    out = fdo._normalize_fdo_match(raw)
    assert out["home_score"] is None
    assert out["away_score"] is None
    assert out["referees"] == []
    assert out["home_team_logo_url"] is None


def test_cache_get_returns_none_when_expired():
    fdo._FDO_CACHE.clear()
    fdo._fdo_cache_put("test_key", {"status": "ok"})
    # Simulate time travel by mutating cached timestamp
    cached_ts, payload = fdo._FDO_CACHE["test_key"]
    fdo._FDO_CACHE["test_key"] = (cached_ts - 1000, payload)
    assert fdo._fdo_cache_get("test_key", ttl=60) is None


def test_cache_get_returns_payload_when_fresh():
    fdo._FDO_CACHE.clear()
    fdo._fdo_cache_put("fresh_key", {"status": "ok", "fixtures": []})
    assert fdo._fdo_cache_get("fresh_key", ttl=60) == {"status": "ok", "fixtures": []}


def test_free_competitions_constant_includes_top_leagues():
    assert "PL" in fdo.FOOTBALL_DATA_ORG_FREE_COMPETITIONS
    assert "BL1" in fdo.FOOTBALL_DATA_ORG_FREE_COMPETITIONS
    assert "SA" in fdo.FOOTBALL_DATA_ORG_FREE_COMPETITIONS
    assert "CL" in fdo.FOOTBALL_DATA_ORG_FREE_COMPETITIONS


def test_fdo_token_reads_from_env(monkeypatch):
    monkeypatch.setenv("FOOTBALL_DATA_ORG_TOKEN", "test_token_123")
    assert fdo._fdo_token() == "test_token_123"
    monkeypatch.delenv("FOOTBALL_DATA_ORG_TOKEN", raising=False)
    assert fdo._fdo_token() is None
