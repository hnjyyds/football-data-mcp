import asyncio
from datetime import datetime, timezone

from football_data_mcp import external_sources
from football_data_mcp import snapshot_store
from football_data_mcp import sources as sources_module


def test_snapshot_store_configures_sqlite_for_concurrent_dashboard_reads(tmp_path):
    db_path = str(tmp_path / "snapshots.sqlite3")

    with snapshot_store._connect(str(db_path)) as conn:
        snapshot_store.ensure_schema(conn)
        journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        busy_timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]

    assert str(journal_mode).lower() == "wal"
    assert int(busy_timeout) >= 10000


def test_normalize_the_odds_api_event_extracts_core_markets():
    event = {
        "id": "evt_1",
        "sport_key": "soccer_epl",
        "sport_title": "EPL",
        "commence_time": "2026-05-23T12:30:00Z",
        "home_team": "Arsenal",
        "away_team": "Chelsea",
        "bookmakers": [
            {
                "key": "bet365",
                "title": "Bet365",
                "last_update": "2026-05-23T08:00:00Z",
                "markets": [
                    {
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Arsenal", "price": 1.91},
                            {"name": "Chelsea", "price": 4.2},
                            {"name": "Draw", "price": 3.4},
                        ],
                    },
                    {
                        "key": "spreads",
                        "outcomes": [
                            {"name": "Arsenal", "price": 1.95, "point": -0.5},
                            {"name": "Chelsea", "price": 1.87, "point": 0.5},
                        ],
                    },
                    {
                        "key": "totals",
                        "outcomes": [
                            {"name": "Over", "price": 1.83, "point": 2.5},
                            {"name": "Under", "price": 2.01, "point": 2.5},
                        ],
                    },
                ],
            }
        ],
    }

    snapshots = external_sources.normalize_the_odds_api_event(
        event,
        fetched_at=datetime(2026, 5, 23, 8, 1, tzinfo=timezone.utc),
    )

    assert {item.market_type for item in snapshots} == {"h2h", "spreads", "totals"}
    assert [item.selection for item in snapshots if item.market_type == "h2h"] == [
        "Arsenal",
        "Chelsea",
        "Draw",
    ]
    spread = next(item for item in snapshots if item.market_type == "spreads" and item.selection == "Arsenal")
    assert spread.line == -0.5
    assert spread.decimal_odds == 1.95
    assert spread.source_time_utc == "2026-05-23T08:00:00+00:00"


def test_snapshot_store_persists_and_builds_consensus(tmp_path):
    db_path = tmp_path / "snapshots.sqlite3"
    snapshot_store.save_market_snapshots(
        [
            snapshot_store.MarketSnapshot(
                provider="the_odds_api",
                source_key="soccer_epl",
                event_id="evt_1",
                league="EPL",
                home_team="Arsenal",
                away_team="Chelsea",
                kickoff_utc="2026-05-23T12:30:00+00:00",
                bookmaker="Bet365",
                market_type="h2h",
                selection="Arsenal",
                decimal_odds=1.9,
                line=None,
                source_time_utc="2026-05-23T08:00:00+00:00",
                fetched_at_utc="2026-05-23T08:01:00+00:00",
                raw={"sample": 1},
            ),
            snapshot_store.MarketSnapshot(
                provider="the_odds_api",
                source_key="soccer_epl",
                event_id="evt_1",
                league="EPL",
                home_team="Arsenal",
                away_team="Chelsea",
                kickoff_utc="2026-05-23T12:30:00+00:00",
                bookmaker="Pinnacle",
                market_type="h2h",
                selection="Arsenal",
                decimal_odds=1.98,
                line=None,
                source_time_utc="2026-05-23T08:02:00+00:00",
                fetched_at_utc="2026-05-23T08:03:00+00:00",
                raw={"sample": 2},
            ),
        ],
        db_path=str(db_path),
    )

    rows = snapshot_store.find_market_snapshots("Arsenal", "Chelsea", db_path=str(db_path))
    consensus = snapshot_store.build_market_consensus(rows)

    assert len(rows) == 2
    assert consensus["h2h"]["Arsenal"]["bookmaker_count"] == 2
    assert consensus["h2h"]["Arsenal"]["median_decimal_odds"] == 1.94
    assert consensus["h2h"]["Arsenal"]["latest_source_time_utc"] == "2026-05-23T08:02:00+00:00"


def test_snapshot_store_calculates_closing_line_value_from_snapshots(tmp_path):
    db_path = tmp_path / "snapshots.sqlite3"
    snapshot_store.save_market_snapshots(
        [
            snapshot_store.MarketSnapshot(
                provider="the_odds_api",
                source_key="soccer_epl",
                event_id="evt_1",
                league="EPL",
                home_team="Arsenal",
                away_team="Chelsea",
                kickoff_utc="2026-05-23T12:30:00+00:00",
                bookmaker="Bet365",
                market_type="h2h",
                selection="Arsenal",
                decimal_odds=2.10,
                line=None,
                source_time_utc="2026-05-23T11:20:00+00:00",
                fetched_at_utc="2026-05-23T11:21:00+00:00",
                raw={"phase": "prediction"},
            ),
            snapshot_store.MarketSnapshot(
                provider="the_odds_api",
                source_key="soccer_epl",
                event_id="evt_1",
                league="EPL",
                home_team="Arsenal",
                away_team="Chelsea",
                kickoff_utc="2026-05-23T12:30:00+00:00",
                bookmaker="Bet365",
                market_type="h2h",
                selection="Arsenal",
                decimal_odds=1.90,
                line=None,
                source_time_utc="2026-05-23T12:20:00+00:00",
                fetched_at_utc="2026-05-23T12:21:00+00:00",
                raw={"phase": "closing"},
            ),
            snapshot_store.MarketSnapshot(
                provider="the_odds_api",
                source_key="soccer_epl",
                event_id="evt_1",
                league="EPL",
                home_team="Arsenal",
                away_team="Chelsea",
                kickoff_utc="2026-05-23T12:30:00+00:00",
                bookmaker="Pinnacle",
                market_type="h2h",
                selection="Arsenal",
                decimal_odds=1.94,
                line=None,
                source_time_utc="2026-05-23T12:24:00+00:00",
                fetched_at_utc="2026-05-23T12:25:00+00:00",
                raw={"phase": "closing"},
            ),
        ],
        db_path=str(db_path),
    )

    clv = snapshot_store.closing_line_value_for_pick(
        home_team="Arsenal",
        away_team="Chelsea",
        selection="home",
        prediction_decimal_odds=2.10,
        market_type="h2h",
        kickoff_utc="2026-05-23T12:30:00+00:00",
        prediction_time_utc="2026-05-23T11:22:00+00:00",
        db_path=str(db_path),
    )

    assert clv["status"] == "available"
    assert clv["method"] == "closing_line_value_from_market_snapshots_v1"
    assert clv["selection"] == "Arsenal"
    assert clv["closing_decimal_odds"] == 1.92
    assert clv["closing_bookmaker_count"] == 2
    assert clv["clv_return"] == round(2.10 / 1.92 - 1.0, 6)
    assert clv["clv_return"] > 0

    tracking = snapshot_store.closing_line_value_for_records(
        [
            {
                "id": 7,
                "record_key": "rec_7",
                "league": "EPL",
                "home_team": "Arsenal",
                "away_team": "Chelsea",
                "kickoff_utc": "2026-05-23T12:30:00+00:00",
                "market": "1x2",
                "selection": "Arsenal",
                "selection_key": "home",
                "decimal_odds": 2.10,
                "created_at_utc": "2026-05-23T11:22:00+00:00",
            }
        ],
        db_path=str(db_path),
    )

    assert tracking["status"] == "ok"
    assert tracking["method"] == "closing_line_value_batch_tracking_v1"
    assert tracking["available_count"] == 1
    assert tracking["positive_clv_count"] == 1
    assert tracking["records"][0]["clv"]["closing_decimal_odds"] == 1.92


def test_sync_market_snapshots_degrades_when_the_odds_api_key_missing(monkeypatch, tmp_path):
    monkeypatch.delenv("THE_ODDS_API_KEY", raising=False)
    monkeypatch.setenv("FOOTBALL_DATA_SNAPSHOT_DB", str(tmp_path / "snapshots.sqlite3"))

    result = asyncio.run(sources_module.sync_market_snapshots(limit_per_sport=1))

    assert result["status"] == "partial"
    assert result["providers"]["the_odds_api"]["status"] == "not_configured"
    assert result["saved_snapshot_count"] == 0


def test_snapshot_store_deduplicates_and_summarizes_provider_coverage(tmp_path):
    db_path = tmp_path / "snapshots.sqlite3"
    snapshot = snapshot_store.MarketSnapshot(
        provider="leisu",
        source_key="leisu_odds",
        event_id="4512919",
        league="中乙",
        home_team="大连英博B队",
        away_team="泰安天贶",
        kickoff_utc="2026-05-25T11:00:00+00:00",
        bookmaker="Bet365",
        market_type="asian_handicap",
        selection="大连英博B队",
        decimal_odds=1.9,
        line=-0.25,
        source_time_utc="2026-05-25T04:03:00+00:00",
        fetched_at_utc="2026-05-25T04:05:00+00:00",
        raw={"side": "home_cover"},
    )

    assert snapshot_store.save_market_snapshots([snapshot, snapshot], db_path=str(db_path)) == 1

    summary = snapshot_store.market_snapshot_summary(db_path=str(db_path))

    assert summary["total_snapshot_count"] == 1
    assert summary["event_count"] == 1
    assert summary["bookmaker_count"] == 1
    assert summary["providers"][0]["provider"] == "leisu"
    assert summary["providers"][0]["market_types"] == ["asian_handicap"]


def test_sync_leisu_odds_snapshots_persists_accessible_probe(monkeypatch, tmp_path):
    monkeypatch.setenv("FOOTBALL_DATA_SNAPSHOT_DB", str(tmp_path / "snapshots.sqlite3"))

    async def fake_load_leisu_schedule_for_date(local_date):
        return [
            {
                "source_name": "leisu",
                "match_id": "4512919",
                "league": "中乙",
                "home_team": "大连英博B队",
                "away_team": "泰安天贶",
                "kickoff_utc": "2026-05-25T11:00:00+00:00",
                "kickoff_utc_plus_8": "2026-05-25T19:00:00+08:00",
                "odds_url": "https://odds.leisu.com/3in1-4512919",
            }
        ], {"source": "leisu.com", "fetched_at_utc": "2026-05-25T03:55:00+00:00"}

    async def fake_probe_leisu_odds(**kwargs):
        odds = sources_module.odds_from_leisu_odds_payload(
            {
                "matchId": "4512919",
                "euro": [
                    {
                        "name": "竞彩官方",
                        "area": "中国",
                        "now": {"homeWin": "2.30", "draw": "3.10", "awayWin": "2.85", "ts": "2026-05-25 12:00"},
                        "begin": {"homeWin": "2.20", "draw": "3.20", "awayWin": "2.90", "ts": "2026-05-24 18:00"},
                    }
                ],
                "asia": [
                    {
                        "name": "Bet365",
                        "area": "英国",
                        "now": {"homeWin": "0.90", "draw": "平/半", "awayWin": "0.90", "ts": "2026-05-25 12:03"},
                        "begin": {"homeWin": "0.94", "draw": "平手", "awayWin": "0.86", "ts": "2026-05-24 18:03"},
                    }
                ],
                "size": [
                    {
                        "name": "澳门",
                        "area": "澳门",
                        "now": {"homeWin": "0.86", "draw": "2.5", "awayWin": "0.94", "ts": "2026-05-25 12:02"},
                        "begin": {"homeWin": "0.90", "draw": "2.25", "awayWin": "0.90", "ts": "2026-05-24 18:02"},
                    }
                ],
            },
            match_id="4512919",
        )
        return {
            "status": "ok",
            "match_id": kwargs["match_id"],
            "odds_url": kwargs["odds_url"],
            "available": True,
            "odds": odds,
            "quality_gate": {"can_promote_to_model_input": True},
            "fetch": {
                "source": {
                    "url": kwargs["odds_url"],
                    "fetched_at_utc": "2026-05-25T04:05:00+00:00",
                    "source": "leisu.com",
                }
            },
        }

    monkeypatch.setattr(sources_module, "load_leisu_schedule_for_date", fake_load_leisu_schedule_for_date)
    monkeypatch.setattr(sources_module, "probe_leisu_odds", fake_probe_leisu_odds)

    result = asyncio.run(
        sources_module.sync_leisu_odds_snapshots(
            as_of="2026-05-25T17:00:00+08:00",
            timezone_name="Asia/Shanghai",
            window_minutes=60,
            limit=1,
        )
    )

    assert result["status"] == "ok"
    assert result["saved_snapshot_count"] == 7
    assert result["providers"]["leisu"]["probed_match_count"] == 1
    assert result["snapshot_store"]["provider_counts"]["leisu"]["snapshot_count"] == 7
    dashboard = sources_module.dashboard_snapshot(db_path=str(tmp_path / "learning.sqlite3"), limit=10)
    assert dashboard["market_snapshot_summary"]["providers"][0]["provider"] == "leisu"
    assert dashboard["market_snapshot_summary"]["total_snapshot_count"] == 7


def test_sync_leisu_odds_snapshots_prioritizes_prediction_ledger_alias_match(monkeypatch, tmp_path):
    monkeypatch.setenv("FOOTBALL_DATA_SNAPSHOT_DB", str(tmp_path / "snapshots.sqlite3"))

    schedule = [
        {
            "source_name": "leisu",
            "match_id": "wrong-first",
            "league": "波黑U19",
            "home_team": "伯拉治U19",
            "away_team": "兹维耶达U19",
            "odds_url": "https://odds.leisu.com/3in1-wrong-first",
        },
        {
            "source_name": "leisu",
            "match_id": "4545782",
            "league": "冰岛U19",
            "home_team": "伊米尔U19",
            "away_team": "伏尔松古U19",
            "odds_url": "https://odds.leisu.com/3in1-4545782",
        },
    ]

    async def fake_load_leisu_schedule_for_date(local_date):
        return schedule, {"source": "leisu.com", "fetched_at_utc": "2026-05-25T12:00:00+00:00"}

    probed_match_ids = []

    async def fake_probe_leisu_odds(**kwargs):
        probed_match_ids.append(kwargs["match_id"])
        odds = sources_module.odds_from_leisu_odds_payload(
            {
                "matchId": kwargs["match_id"],
                "asia": [
                    {
                        "name": "36*",
                        "area": "雷速移动端",
                        "now": {"homeWin": "0.78", "draw": "-0.25", "awayWin": "1.03", "ts": ""},
                        "begin": {"homeWin": "0.85", "draw": "0.0", "awayWin": "0.95", "ts": ""},
                    }
                ],
            },
            match_id=kwargs["match_id"],
        )
        return {
            "status": "ok",
            "match_id": kwargs["match_id"],
            "odds_url": kwargs["odds_url"],
            "available": True,
            "odds": odds,
            "quality_gate": {"can_promote_to_model_input": True},
            "fetch": {
                "source": {
                    "url": kwargs["odds_url"],
                    "fetched_at_utc": "2026-05-25T12:05:00+00:00",
                    "source": "leisu.com",
                }
            },
        }

    monkeypatch.setattr(sources_module, "load_leisu_schedule_for_date", fake_load_leisu_schedule_for_date)
    monkeypatch.setattr(sources_module, "probe_leisu_odds", fake_probe_leisu_odds)
    monkeypatch.setattr(
        sources_module.learning_store,
        "list_recommendation_records",
        lambda **kwargs: [
            {
                "id": 1413,
                "league": "冰岛U19",
                "home_team": "科帕沃于尔U19",
                "away_team": "伏尔松古U19",
                "kickoff_utc_plus_8": "2026-05-26T00:00:00+08:00",
            }
        ],
    )
    monkeypatch.setattr(sources_module.learning_store, "list_shadow_prediction_records", lambda **kwargs: [])

    result = asyncio.run(
        sources_module.sync_leisu_odds_snapshots(
            as_of="2026-05-25T20:00:00+08:00",
            timezone_name="Asia/Shanghai",
            window_minutes=360,
            limit=1,
        )
    )

    assert probed_match_ids == ["4545782"]
    assert result["saved_snapshot_count"] == 2
    rows = snapshot_store.find_market_snapshots(
        "科帕沃于尔U19",
        "伏尔松古U19",
        db_path=str(tmp_path / "snapshots.sqlite3"),
    )
    assert len(rows) == 2
    assert rows[0]["event_id"] == "4545782"
    assert rows[0]["home_team"] == "科帕沃于尔U19"
    assert rows[0]["raw"]["leisu_home_team"] == "伊米尔U19"


def test_sync_leisu_odds_snapshots_refreshes_prediction_target_with_existing_snapshots(monkeypatch, tmp_path):
    snapshot_db_path = str(tmp_path / "snapshots.sqlite3")
    monkeypatch.setenv("FOOTBALL_DATA_SNAPSHOT_DB", snapshot_db_path)
    snapshot_store.save_market_snapshots(
        [
            snapshot_store.MarketSnapshot(
                provider="leisu",
                source_key="leisu:4545782",
                event_id="4545782",
                league="冰岛U19",
                home_team="科帕沃于尔U19",
                away_team="伏尔松古U19",
                kickoff_utc="2026-05-25T16:00:00+00:00",
                bookmaker="36*",
                market_type="asian_handicap",
                selection="科帕沃于尔U19 +0.25",
                decimal_odds=1.86,
                line=0.25,
                source_time_utc="2026-05-25T11:00:00+00:00",
                fetched_at_utc="2026-05-25T11:00:00+00:00",
                raw={},
            )
        ],
        db_path=snapshot_db_path,
    )

    schedule = [
        {
            "source_name": "leisu",
            "match_id": "wrong-first",
            "league": "波黑U19",
            "home_team": "伯拉治U19",
            "away_team": "兹维耶达U19",
            "odds_url": "https://odds.leisu.com/3in1-wrong-first",
        },
        {
            "source_name": "leisu",
            "match_id": "4545782",
            "league": "冰岛U19",
            "home_team": "伊米尔U19",
            "away_team": "伏尔松古U19",
            "odds_url": "https://odds.leisu.com/3in1-4545782",
        },
    ]

    async def fake_load_leisu_schedule_for_date(local_date):
        return schedule, {"source": "leisu.com", "fetched_at_utc": "2026-05-25T12:00:00+00:00"}

    probed_match_ids = []

    async def fake_probe_leisu_odds(**kwargs):
        probed_match_ids.append(kwargs["match_id"])
        odds = sources_module.odds_from_leisu_odds_payload(
            {
                "matchId": kwargs["match_id"],
                "asia": [
                    {
                        "name": "36*",
                        "area": "雷速移动端",
                        "now": {"homeWin": "0.80", "draw": "+0.25", "awayWin": "1.00", "ts": "2026-05-25 20:05"},
                    }
                ],
            },
            match_id=kwargs["match_id"],
        )
        return {
            "status": "ok",
            "match_id": kwargs["match_id"],
            "odds_url": kwargs["odds_url"],
            "available": True,
            "odds": odds,
            "quality_gate": {"can_promote_to_model_input": True},
            "fetch": {"source": {"fetched_at_utc": "2026-05-25T12:05:00+00:00"}},
        }

    monkeypatch.setattr(sources_module, "load_leisu_schedule_for_date", fake_load_leisu_schedule_for_date)
    monkeypatch.setattr(sources_module, "probe_leisu_odds", fake_probe_leisu_odds)
    monkeypatch.setattr(
        sources_module.learning_store,
        "list_recommendation_records",
        lambda **kwargs: [
            {
                "id": 1413,
                "league": "冰岛U19",
                "home_team": "科帕沃于尔U19",
                "away_team": "伏尔松古U19",
                "kickoff_utc_plus_8": "2026-05-26T00:00:00+08:00",
            }
        ],
    )
    monkeypatch.setattr(sources_module.learning_store, "list_shadow_prediction_records", lambda **kwargs: [])

    asyncio.run(
        sources_module.sync_leisu_odds_snapshots(
            as_of="2026-05-25T20:00:00+08:00",
            timezone_name="Asia/Shanghai",
            window_minutes=24 * 60,
            limit=1,
        )
    )

    assert probed_match_ids == ["4545782"]


def test_fetch_sportmonks_context_degrades_when_token_missing(monkeypatch):
    monkeypatch.delenv("SPORTMONKS_API_TOKEN", raising=False)

    result = asyncio.run(external_sources.fetch_sportmonks_fixture_context("Arsenal vs Chelsea"))

    assert result["status"] == "not_configured"
    assert result["provider"] == "sportmonks"
    assert result["required_env"] == "SPORTMONKS_API_TOKEN"


def test_fetch_api_football_context_degrades_when_key_missing(monkeypatch):
    monkeypatch.delenv("API_FOOTBALL_KEY", raising=False)

    result = asyncio.run(external_sources.fetch_api_football_fixture_context("Arsenal vs Chelsea"))

    assert result["status"] == "not_configured"
    assert result["provider"] == "api_football"
    assert result["required_env"] == "API_FOOTBALL_KEY"
    assert result["context"]["available"] is False


def test_normalize_api_football_fixture_context_extracts_match_blocks():
    payload = {
        "response": [
            {
                "fixture": {
                    "id": 9001,
                    "date": "2026-05-23T12:30:00+00:00",
                    "timezone": "UTC",
                    "status": {"short": "NS", "long": "Not Started", "elapsed": None},
                    "venue": {"name": "Emirates Stadium", "city": "London"},
                },
                "league": {"id": 39, "name": "Premier League", "country": "England", "season": 2026},
                "teams": {
                    "home": {"id": 42, "name": "Arsenal", "logo": "https://img.example.com/arsenal.png", "winner": None},
                    "away": {"id": 49, "name": "Chelsea", "logo": "https://img.example.com/chelsea.png", "winner": None},
                },
                "goals": {"home": None, "away": None},
                "score": {"fulltime": {"home": None, "away": None}},
            }
        ]
    }

    context = external_sources.normalize_api_football_fixture_context(payload, "Arsenal", "Chelsea")

    assert context["available"] is True
    assert context["fixture"]["id"] == 9001
    assert context["fixture"]["home_team"] == "Arsenal"
    assert context["fixture"]["away_team"] == "Chelsea"
    assert context["fixture"]["home_team_logo_url"] == "https://img.example.com/arsenal.png"
    assert context["fixture"]["away_team_logo_url"] == "https://img.example.com/chelsea.png"
    assert context["fixture"]["starting_at"] == "2026-05-23T12:30:00+00:00"
    assert context["coverage"]["fixture"] is True
    assert context["coverage"]["score"] is False


def test_normalize_api_football_fixture_context_selects_matching_fixture():
    payload = {
        "response": [
            {
                "fixture": {"id": 1, "date": "2026-05-23T10:00:00+00:00", "status": {"short": "NS"}},
                "league": {"name": "Premier League"},
                "teams": {
                    "home": {"name": "Liverpool"},
                    "away": {"name": "Everton"},
                },
                "goals": {"home": None, "away": None},
            },
            {
                "fixture": {"id": 2, "date": "2026-05-23T12:30:00+00:00", "status": {"short": "NS"}},
                "league": {"name": "Premier League"},
                "teams": {
                    "home": {"name": "Arsenal"},
                    "away": {"name": "Chelsea"},
                },
                "goals": {"home": None, "away": None},
            },
        ]
    }

    context = external_sources.normalize_api_football_fixture_context(payload, "Arsenal", "Chelsea")

    assert context["fixture"]["id"] == 2
    assert context["raw_counts"]["fixtures"] == 2


def test_fetch_api_football_context_queries_date_and_filters_match(monkeypatch):
    calls = []

    class FakeResponse:
        url = "https://v3.football.api-sports.io/fixtures"

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "response": [
                    {
                        "fixture": {"id": 2, "date": "2026-05-23T12:30:00+00:00", "status": {"short": "NS"}},
                        "league": {"name": "Premier League"},
                        "teams": {"home": {"name": "Arsenal"}, "away": {"name": "Chelsea"}},
                        "goals": {"home": None, "away": None},
                    }
                ]
            }

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, *, params=None, headers=None):
            calls.append({"url": url, "params": params, "headers": headers})
            return FakeResponse()

    monkeypatch.setenv("API_FOOTBALL_KEY", "free-key")
    monkeypatch.setattr(external_sources.httpx, "AsyncClient", FakeClient)

    result = asyncio.run(
        external_sources.fetch_api_football_fixture_context(
            "Arsenal vs Chelsea",
            home_team="Arsenal",
            away_team="Chelsea",
            date="2026-05-23",
        )
    )

    assert result["status"] == "ok"
    assert result["context"]["fixture"]["id"] == 2
    assert calls[0]["params"] == {"date": "2026-05-23"}
    assert calls[0]["headers"] == {"x-apisports-key": "free-key"}


def test_fetch_football_data_org_context_degrades_when_token_missing(monkeypatch):
    monkeypatch.delenv("FOOTBALL_DATA_ORG_TOKEN", raising=False)

    result = asyncio.run(external_sources.fetch_football_data_org_match_context("Arsenal vs Chelsea"))

    assert result["status"] == "not_configured"
    assert result["provider"] == "football_data_org"
    assert result["required_env"] == "FOOTBALL_DATA_ORG_TOKEN"
    assert result["context"]["available"] is False


def test_normalize_football_data_org_match_context_extracts_match_blocks():
    payload = {
        "matches": [
            {
                "id": 12345,
                "utcDate": "2026-05-23T12:30:00Z",
                "status": "TIMED",
                "competition": {"id": 2021, "name": "Premier League", "code": "PL"},
                "homeTeam": {"id": 57, "name": "Arsenal FC", "shortName": "Arsenal", "crest": "https://img.example.com/arsenal-crest.svg"},
                "awayTeam": {"id": 61, "name": "Chelsea FC", "shortName": "Chelsea", "crest": "https://img.example.com/chelsea-crest.svg"},
                "score": {"fullTime": {"home": None, "away": None}, "winner": None},
            }
        ]
    }

    context = external_sources.normalize_football_data_org_match_context(payload, "Arsenal", "Chelsea")

    assert context["available"] is True
    assert context["fixture"]["id"] == 12345
    assert context["fixture"]["home_team"] == "Arsenal FC"
    assert context["fixture"]["away_team"] == "Chelsea FC"
    assert context["fixture"]["home_team_logo_url"] == "https://img.example.com/arsenal-crest.svg"
    assert context["fixture"]["away_team_logo_url"] == "https://img.example.com/chelsea-crest.svg"
    assert context["fixture"]["competition_code"] == "PL"
    assert context["coverage"]["fixture"] is True
    assert context["coverage"]["score"] is False


def test_normalize_football_data_org_match_context_selects_matching_fixture():
    payload = {
        "matches": [
            {
                "id": 1,
                "utcDate": "2026-05-23T10:00:00Z",
                "status": "TIMED",
                "competition": {"name": "Premier League", "code": "PL"},
                "homeTeam": {"name": "Liverpool FC", "shortName": "Liverpool"},
                "awayTeam": {"name": "Everton FC", "shortName": "Everton"},
                "score": {"fullTime": {"home": None, "away": None}},
            },
            {
                "id": 2,
                "utcDate": "2026-05-23T12:30:00Z",
                "status": "TIMED",
                "competition": {"name": "Premier League", "code": "PL"},
                "homeTeam": {"name": "Arsenal FC", "shortName": "Arsenal"},
                "awayTeam": {"name": "Chelsea FC", "shortName": "Chelsea"},
                "score": {"fullTime": {"home": None, "away": None}},
            },
        ]
    }

    context = external_sources.normalize_football_data_org_match_context(payload, "Arsenal", "Chelsea")

    assert context["fixture"]["id"] == 2
    assert context["raw_counts"]["matches"] == 2


def test_fetch_football_data_org_context_queries_date_window_and_filters_match(monkeypatch):
    calls = []

    class FakeResponse:
        url = "https://api.football-data.org/v4/matches"

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "matches": [
                    {
                        "id": 2,
                        "utcDate": "2026-05-23T12:30:00Z",
                        "status": "TIMED",
                        "competition": {"name": "Premier League", "code": "PL"},
                        "homeTeam": {"name": "Arsenal FC", "shortName": "Arsenal"},
                        "awayTeam": {"name": "Chelsea FC", "shortName": "Chelsea"},
                        "score": {"fullTime": {"home": None, "away": None}},
                    }
                ]
            }

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, *, params=None, headers=None):
            calls.append({"url": url, "params": params, "headers": headers})
            return FakeResponse()

    monkeypatch.setenv("FOOTBALL_DATA_ORG_TOKEN", "free-token")
    monkeypatch.setattr(external_sources.httpx, "AsyncClient", FakeClient)

    result = asyncio.run(
        external_sources.fetch_football_data_org_match_context(
            "Arsenal vs Chelsea",
            home_team="Arsenal",
            away_team="Chelsea",
            date_from="2026-05-23",
            date_to="2026-05-24",
        )
    )

    assert result["status"] == "ok"
    assert result["context"]["fixture"]["id"] == 2
    assert calls[0]["params"] == {"dateFrom": "2026-05-23", "dateTo": "2026-05-24"}
    assert calls[0]["headers"] == {"X-Auth-Token": "free-token"}


def test_external_provider_health_marks_free_adapters_as_configured(monkeypatch):
    monkeypatch.setenv("API_FOOTBALL_KEY", "free-key")
    monkeypatch.setenv("FOOTBALL_DATA_ORG_TOKEN", "free-token")

    health = external_sources.external_provider_health()

    assert health["api_football"]["status"] == "configured"
    assert health["football_data_org"]["status"] == "configured"


def test_normalize_sportmonks_fixture_context_extracts_core_blocks():
    payload = {
        "data": [
            {
                "id": 123,
                "name": "Arsenal vs Chelsea",
                "starting_at": "2026-05-23 12:30:00",
                "participants": [
                    {"id": 1, "name": "Arsenal", "image_path": "https://img.example.com/arsenal-sportmonks.png", "meta": {"location": "home"}},
                    {"id": 2, "name": "Chelsea", "image_path": "https://img.example.com/chelsea-sportmonks.png", "meta": {"location": "away"}},
                ],
                "league": {"id": 8, "name": "Premier League"},
                "lineups": [{"player_name": "Player A"}],
                "sidelined": [{"player_name": "Player B", "category": "injury"}],
                "weather_report": {"temperature": {"day": 18}},
                "statistics": [{"type": {"name": "Shots"}, "data": {"value": 12}}],
                "formations": [{"formation": "4-3-3"}],
            }
        ]
    }

    context = external_sources.normalize_sportmonks_fixture_context(payload)

    assert context["available"] is True
    assert context["fixture"]["name"] == "Arsenal vs Chelsea"
    assert context["fixture"]["home_team"] == "Arsenal"
    assert context["fixture"]["away_team"] == "Chelsea"
    assert context["fixture"]["home_team_logo_url"] == "https://img.example.com/arsenal-sportmonks.png"
    assert context["fixture"]["away_team_logo_url"] == "https://img.example.com/chelsea-sportmonks.png"
    assert context["coverage"]["lineups"] is True
    assert context["coverage"]["sidelined"] is True
    assert context["coverage"]["weather"] is True
    assert context["raw_counts"]["statistics"] == 1


def test_normalize_clubelo_csv_extracts_latest_rating():
    csv_text = (
        "Rank,Club,Country,Level,Elo,From,To\n"
        "17,Arsenal,ENG,1,1891.22,2026-05-20,2026-05-25\n"
        "18,Arsenal,ENG,1,1888.10,2026-05-15,2026-05-19\n"
    )

    rating = external_sources.normalize_clubelo_rating("Arsenal", csv_text)

    assert rating["available"] is True
    assert rating["team"] == "Arsenal"
    assert rating["elo"] == 1891.22
    assert rating["rank"] == 17
    assert rating["valid_to"] == "2026-05-25"


def test_free_team_strength_context_uses_clubelo(monkeypatch):
    async def fake_fetch_clubelo_rating(team):
        return {
            "available": True,
            "provider": "clubelo",
            "team": team,
            "elo": 1900.0 if team == "Arsenal" else 1810.0,
            "rank": 10 if team == "Arsenal" else 28,
        }

    monkeypatch.setattr(external_sources, "fetch_clubelo_rating", fake_fetch_clubelo_rating)

    context = asyncio.run(external_sources.free_team_strength_context("Arsenal", "Chelsea"))

    assert context["status"] == "ok"
    assert context["provider"] == "clubelo"
    assert context["home"]["elo"] == 1900.0
    assert context["away"]["elo"] == 1810.0
    assert context["elo_diff_home_minus_away"] == 90.0


def test_get_match_data_bundle_uses_local_snapshot_consensus(monkeypatch, tmp_path):
    db_path = tmp_path / "snapshots.sqlite3"
    snapshot_store.save_market_snapshots(
        [
            snapshot_store.MarketSnapshot(
                provider="the_odds_api",
                source_key="soccer_epl",
                event_id="evt_1",
                league="EPL",
                home_team="Arsenal",
                away_team="Chelsea",
                kickoff_utc="2026-05-23T12:30:00+00:00",
                bookmaker="Bet365",
                market_type="h2h",
                selection="Arsenal",
                decimal_odds=1.9,
                line=None,
                source_time_utc="2026-05-23T08:00:00+00:00",
                fetched_at_utc="2026-05-23T08:01:00+00:00",
                raw={},
            ),
        ],
        db_path=str(db_path),
    )
    monkeypatch.setenv("FOOTBALL_DATA_SNAPSHOT_DB", str(db_path))
    monkeypatch.delenv("API_FOOTBALL_KEY", raising=False)
    monkeypatch.delenv("FOOTBALL_DATA_ORG_TOKEN", raising=False)

    async def fake_free_team_strength_context(home_team, away_team):
        return {
            "status": "ok",
            "provider": "clubelo",
            "home": {"available": True, "team": home_team, "elo": 1900.0},
            "away": {"available": True, "team": away_team, "elo": 1810.0},
            "elo_diff_home_minus_away": 90.0,
        }

    monkeypatch.setattr(external_sources, "free_team_strength_context", fake_free_team_strength_context)

    bundle = asyncio.run(
        sources_module.get_match_data_bundle(
            query="Arsenal vs Chelsea",
            home_team="Arsenal",
            away_team="Chelsea",
        )
    )

    assert bundle["status"] == "ok"
    assert bundle["snapshot_store"]["matching_snapshot_count"] == 1
    assert bundle["market_consensus"]["h2h"]["Arsenal"]["median_decimal_odds"] == 1.9
    assert bundle["source_coverage"]["odds"]["the_odds_api"]["status"] == "snapshot_available"
    assert bundle["external_context"]["sportmonks"]["status"] == "not_configured"
    assert bundle["external_context"]["api_football"]["status"] == "not_configured"
    assert bundle["external_context"]["football_data_org"]["status"] == "not_configured"
    assert bundle["external_context"]["free_team_strength"]["provider"] == "clubelo"
    assert bundle["external_context"]["free_team_strength"]["elo_diff_home_minus_away"] == 90.0


def test_get_match_data_bundle_reads_full_snapshot_history_beyond_recent_global_limit(monkeypatch, tmp_path):
    db_path = tmp_path / "snapshots.sqlite3"
    snapshots = [
        snapshot_store.MarketSnapshot(
            provider="leisu",
            source_key=f"leisu:noise-{index}",
            event_id=f"noise-{index}",
            league="Noise",
            home_team=f"Noise Home {index}",
            away_team=f"Noise Away {index}",
            kickoff_utc="2026-05-23T12:30:00+00:00",
            bookmaker="NoiseBook",
            market_type="asian_handicap",
            selection=f"Noise Home {index} -0.5",
            decimal_odds=1.8 + (index % 5) / 100,
            line=-0.5,
            source_time_utc=f"2026-05-23T09:{index % 60:02d}:00+00:00",
            fetched_at_utc=f"2026-05-23T10:{index % 60:02d}:00+00:00",
            raw={},
        )
        for index in range(501)
    ]
    snapshots.append(
        snapshot_store.MarketSnapshot(
            provider="leisu",
            source_key="leisu:arsenal-chelsea",
            event_id="arsenal-chelsea",
            league="EPL",
            home_team="Arsenal",
            away_team="Chelsea",
            kickoff_utc="2026-05-23T12:30:00+00:00",
            bookmaker="Bet365",
            market_type="asian_handicap",
            selection="Arsenal -0.5",
            decimal_odds=1.92,
            line=-0.5,
            source_time_utc="2026-05-23T07:30:00+00:00",
            fetched_at_utc="2026-05-23T07:31:00+00:00",
            raw={},
        )
    )
    snapshot_store.save_market_snapshots(snapshots, db_path=str(db_path))
    monkeypatch.setenv("FOOTBALL_DATA_SNAPSHOT_DB", str(db_path))

    bundle = asyncio.run(
        sources_module.get_match_data_bundle(
            query="Arsenal vs Chelsea",
            home_team="Arsenal",
            away_team="Chelsea",
            include_context_refresh=False,
        )
    )

    assert bundle["snapshot_store"]["matching_snapshot_count"] == 1
    assert bundle["market_consensus"]["asian_handicap"]["Arsenal -0.5"]["latest_fetched_at_utc"] == "2026-05-23T07:31:00+00:00"


def test_get_match_data_bundle_exposes_leisu_odds_candidate_without_auto_probe(monkeypatch, tmp_path):
    monkeypatch.setenv("FOOTBALL_DATA_SNAPSHOT_DB", str(tmp_path / "snapshots.sqlite3"))
    monkeypatch.delenv("FOOTBALL_DATA_LEISU_ODDS_AUTO_PROBE", raising=False)

    async def fake_load_leisu_schedule_for_date(local_date):
        return (
            [
                {
                    "source_name": "leisu",
                    "match_id": "4512919",
                    "league": "英超",
                    "home_team": "Arsenal",
                    "away_team": "Chelsea",
                    "odds_url": "https://odds.leisu.com/3in1-4512919",
                }
            ],
            {"url": "https://live.leisu.com/saicheng", "source": "leisu.com"},
        )

    async def fake_free_team_strength_context(home_team, away_team):
        return {"status": "skipped", "provider": "clubelo"}

    monkeypatch.setattr(sources_module, "load_leisu_schedule_for_date", fake_load_leisu_schedule_for_date)
    monkeypatch.setattr(external_sources, "free_team_strength_context", fake_free_team_strength_context)

    bundle = asyncio.run(
        sources_module.get_match_data_bundle(
            query="Arsenal vs Chelsea",
            home_team="Arsenal",
            away_team="Chelsea",
            include_context_refresh=True,
        )
    )

    leisu_odds = bundle["external_context"]["leisu_odds"]

    assert leisu_odds["status"] == "candidate_found"
    assert leisu_odds["match"]["match_id"] == "4512919"
    assert leisu_odds["auto_probe_enabled"] is False


def test_get_match_data_bundle_auto_probes_leisu_odds_when_enabled(monkeypatch, tmp_path):
    monkeypatch.setenv("FOOTBALL_DATA_SNAPSHOT_DB", str(tmp_path / "snapshots.sqlite3"))
    monkeypatch.setenv("FOOTBALL_DATA_LEISU_ODDS_AUTO_PROBE", "true")

    async def fake_load_leisu_schedule_for_date(local_date):
        return (
            [
                {
                    "source_name": "leisu",
                    "match_id": "4512919",
                    "league": "英超",
                    "home_team": "Arsenal",
                    "away_team": "Chelsea",
                    "odds_url": "https://odds.leisu.com/3in1-4512919",
                }
            ],
            {"url": "https://live.leisu.com/saicheng", "source": "leisu.com"},
        )

    async def fake_probe_leisu_odds(**kwargs):
        return {
            "status": "ok",
            "match_id": kwargs["match_id"],
            "odds_url": kwargs["odds_url"],
            "quality_gate": {"can_promote_to_model_input": True},
        }

    async def fake_free_team_strength_context(home_team, away_team):
        return {"status": "skipped", "provider": "clubelo"}

    monkeypatch.setattr(sources_module, "load_leisu_schedule_for_date", fake_load_leisu_schedule_for_date)
    monkeypatch.setattr(sources_module, "probe_leisu_odds", fake_probe_leisu_odds)
    monkeypatch.setattr(external_sources, "free_team_strength_context", fake_free_team_strength_context)

    bundle = asyncio.run(
        sources_module.get_match_data_bundle(
            query="Arsenal vs Chelsea",
            home_team="Arsenal",
            away_team="Chelsea",
            include_context_refresh=True,
        )
    )

    leisu_odds = bundle["external_context"]["leisu_odds"]

    assert leisu_odds["status"] == "ok"
    assert leisu_odds["match_id"] == "4512919"
    assert leisu_odds["quality_gate"]["can_promote_to_model_input"] is True


def test_analyze_single_match_exposes_snapshot_data_bundle(monkeypatch, tmp_path):
    db_path = tmp_path / "snapshots.sqlite3"
    snapshot_store.save_market_snapshots(
        [
            snapshot_store.MarketSnapshot(
                provider="the_odds_api",
                source_key="soccer_epl",
                event_id="evt_1",
                league="EPL",
                home_team="Arsenal",
                away_team="Chelsea",
                kickoff_utc="2026-05-23T12:30:00+00:00",
                bookmaker="Bet365",
                market_type="h2h",
                selection="Arsenal",
                decimal_odds=1.9,
                line=None,
                source_time_utc="2026-05-23T08:00:00+00:00",
                fetched_at_utc="2026-05-23T08:01:00+00:00",
                raw={},
            ),
        ],
        db_path=str(db_path),
    )
    monkeypatch.setenv("FOOTBALL_DATA_SNAPSHOT_DB", str(db_path))

    async def fake_get_best_match(*args, **kwargs):
        odds = sources_module.with_odds_quality_contract(
            {
                "moneyline_1x2": [
                    {
                        "provider": "Fixture odds",
                        "home": 1.9,
                        "draw": 3.4,
                        "away": 4.2,
                        "columns": ["fixture"],
                    }
                ],
                "preferred_moneyline_1x2": {
                    "provider": "Fixture odds",
                    "current": {"home": 1.9, "draw": 3.4, "away": 4.2, "timestamp": "2026-05-23 08:00"},
                },
                "has_valid_numeric_odds": True,
            }
        )
        return (
            {
                "source_name": "football_data",
                "home_team": "Arsenal",
                "away_team": "Chelsea",
                "league": "EPL",
                "division": "",
                "kickoff_utc": "2026-05-23T12:30:00+00:00",
                "kickoff_utc_plus_8": "2026-05-23 20:30",
                "time_window": {"in_window": True},
                "match_score": 1.0,
                "odds_summary": odds,
            },
            {"candidate_count": 1, "candidates": [], "time_window_policy": {}},
        )

    monkeypatch.setattr(sources_module, "get_best_match", fake_get_best_match)

    result = asyncio.run(
        sources_module.analyze_single_match(
            "Arsenal vs Chelsea",
            include_source_probe=False,
        )
    )

    assert result["status"] == "ok"
    assert result["data_bundle"]["snapshot_store"]["matching_snapshot_count"] == 1
    assert result["analysis_pack"]["data_coverage"]["blocks"]["multi_bookmaker_snapshot"] is True
    assert result["agent_brief"]["data_bundle"]["market_consensus"]["h2h"]["Arsenal"]["median_decimal_odds"] == 1.9
