import base64
import asyncio
import gzip
import html
import json
from datetime import datetime, timedelta, timezone

from cryptography.hazmat.primitives import hashes, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from football_data_mcp import browser_session_runtime, oddsportal_source, snapshot_store
from football_data_mcp import sources as sources_module
from football_data_mcp.repositories.data_source_repository import DataSourceRepository
from football_data_mcp.services.data_source_service import DataSourceService
from football_data_mcp.services.task_queue import OddsSourceSyncJobStartResult


def _encrypt_oddsportal_fixture(payload: dict) -> str:
    password = oddsportal_source.ODDSPORTAL_RESPONSE_PASSWORD.encode()
    salt = oddsportal_source.ODDSPORTAL_RESPONSE_SALT.encode()
    iv = bytes.fromhex("00112233445566778899aabbccddeeff")
    raw = gzip.compress(json.dumps(payload).encode())
    padder = padding.PKCS7(128).padder()
    padded = padder.update(raw) + padder.finalize()
    key = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=1000,
    ).derive(password)
    encryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    encrypted = encryptor.update(padded) + encryptor.finalize()
    return base64.b64encode(base64.b64encode(encrypted) + b":" + iv.hex().encode()).decode()


def test_oddsportal_decrypts_encrypted_payload():
    encrypted = _encrypt_oddsportal_fixture({"s": 1, "d": {"bt": 5}})

    decrypted = oddsportal_source.decrypt_oddsportal_response(encrypted)

    assert json.loads(decrypted) == {"s": 1, "d": {"bt": 5}}


def test_oddsportal_asian_handicap_payload_normalizes_to_market_snapshots():
    payload = {
        "s": 1,
        "d": {
            "bt": 5,
            "sc": 2,
            "time-base": 1780402623,
            "encodeventId": "Oj63Qw3D",
            "oddsdata": {
                "back": {
                    "E-5-2-0--0.25-0": {
                        "bettingTypeId": 5,
                        "scopeId": 2,
                        "handicapTypeId": 0,
                        "handicapValue": -0.25,
                        "odds": {
                            "16": [1.88, 1.95],
                            "573": [1.90, 1.91],
                        },
                        "openingOdd": {
                            "16": [1.94, 1.86],
                            "573": [1.96, 1.84],
                        },
                        "changeTime": {
                            "16": [1780402623, 1780402623],
                            "573": [1780402600, 1780402600],
                        },
                        "openingChangeTime": {
                            "16": [1780128705, 1780128705],
                            "573": [1780128722, 1780128722],
                        },
                        "movement": {
                            "16": ["down", "up"],
                            "573": ["down", "up"],
                        },
                        "outcomeId": ["home-outcome", "away-outcome"],
                    }
                }
            },
        },
    }
    context = oddsportal_source.OddsPortalEventContext(
        event_id="Oj63Qw3D",
        version_id="1",
        sport_id="1",
        event_url="https://www.oddsportal.com/football/h2h/example/#Oj63Qw3D",
        xhash="yjbd7",
        xhashf="yj4df",
        league="J1 League",
        home_team="Kashima Antlers",
        away_team="Vissel Kobe",
        kickoff_utc="2026-06-06T05:00:00+00:00",
    )

    snapshots = oddsportal_source.oddsportal_market_snapshots_from_payload(
        payload,
        event_context=context,
        provider_names={"16": "bet365", "573": "Melbet"},
        fetched_at=datetime(2026, 6, 2, 12, 0, tzinfo=timezone.utc),
    )

    assert len(snapshots) == 8
    assert {item.provider for item in snapshots} == {"oddsportal_scraper"}
    assert {item.bookmaker for item in snapshots} == {"bet365", "Melbet"}
    assert {item.market_type for item in snapshots} == {"asian_handicap"}
    bet365_current_home = next(
        item
        for item in snapshots
        if item.bookmaker == "bet365" and item.selection == "Kashima Antlers" and item.raw["phase"] == "current"
    )
    assert bet365_current_home.line == -0.25
    assert bet365_current_home.decimal_odds == 1.88
    assert bet365_current_home.source_time_utc == "2026-06-02T12:17:03+00:00"
    assert bet365_current_home.raw["movement"] == "down"
    bet365_opening_away = next(
        item
        for item in snapshots
        if item.bookmaker == "bet365" and item.selection == "Vissel Kobe" and item.raw["phase"] == "opening"
    )
    assert bet365_opening_away.line == 0.25
    assert bet365_opening_away.decimal_odds == 1.86


def test_oddsportal_next_match_events_match_prediction_targets():
    comp_data = {
        "d": {
            "rows": [
                {
                    "encodeEventId": "Oj63Qw3D",
                    "id": 1001,
                    "name": "Kashima Antlers - Vissel Kobe",
                    "home-name": "Kashima Antlers",
                    "away-name": "Vissel Kobe",
                    "tournament-name": "J1 League",
                    "url": "/football/japan/j1-league/kashima-vissel-kobe-Oj63Qw3D/",
                    "date-start-timestamp": 1780405200,
                },
                {
                    "encodeEventId": "Other",
                    "home-name": "FC Tokyo",
                    "away-name": "Gamba Osaka",
                    "tournament-name": "J1 League",
                    "url": "/football/japan/j1-league/tokyo-gamba-Other/",
                    "date-start-timestamp": 1780405200,
                },
            ]
        }
    }
    page_html = f'<next-matches :comp-data="{html.escape(json.dumps(comp_data), quote=True)}"></next-matches>'
    targets = [
        {
            "home_team": "Kashima Antlers",
            "away_team": "Vissel Kobe",
            "league": "Japan J1 League",
            "kickoff_utc": "2026-06-02T12:00:00+00:00",
        }
    ]

    events = oddsportal_source.extract_oddsportal_next_match_events(page_html)
    matches = oddsportal_source.match_oddsportal_events_to_targets(events, targets, limit=5)

    assert len(events) == 2
    assert len(matches) == 1
    assert matches[0]["event_url"] == "https://www.oddsportal.com/football/japan/j1-league/kashima-vissel-kobe-Oj63Qw3D/"
    assert matches[0]["match_score"] >= 0.9
    assert matches[0]["target"]["home_team"] == "Kashima Antlers"


def test_oddsportal_matches_chinese_country_alias_targets():
    events = [
        {
            "league": "Friendly International",
            "home_team": "Georgia",
            "away_team": "Romania",
            "kickoff_utc": "2026-06-02T17:00:00+00:00",
            "event_url": "https://www.oddsportal.com/football/h2h/georgia/romania/#abc",
        }
    ]
    targets = [
        {
            "league": "国际友谊",
            "home_team": "格鲁吉亚",
            "away_team": "罗马尼亚",
            "kickoff_utc": "2026-06-02T17:00:00+00:00",
        }
    ]

    matches = oddsportal_source.match_oddsportal_events_to_targets(events, targets, limit=5)

    assert matches[0]["event_url"] == "https://www.oddsportal.com/football/h2h/georgia/romania/#abc"
    assert matches[0]["match_score"] >= 0.9


def test_oddsportal_matches_current_chinese_international_targets():
    events = [
        {
            "league": "Friendly International",
            "home_team": "Kyrgyzstan",
            "away_team": "Kenya",
            "kickoff_utc": "2026-06-03T12:30:00+00:00",
            "event_url": "https://www.oddsportal.com/football/world/friendly-international/kyrgyzstan-kenya/#abc",
        },
        {
            "league": "Friendly International",
            "home_team": "China W",
            "away_team": "Russia W",
            "kickoff_utc": "2026-06-03T11:35:00+00:00",
            "event_url": "https://www.oddsportal.com/football/world/friendly-international/china-w-russia-w/#def",
        },
    ]
    targets = [
        {
            "league": "国际友谊",
            "home_team": "吉尔吉斯斯坦",
            "away_team": "肯尼亚",
            "kickoff_utc": "2026-06-03T12:30:00+00:00",
        },
        {
            "league": "国际友谊",
            "home_team": "中国女足",
            "away_team": "俄罗斯女足",
            "kickoff_utc": "2026-06-03T11:35:00+00:00",
        },
    ]

    matches = oddsportal_source.match_oddsportal_events_to_targets(events, targets, limit=5)

    assert [match["event_url"] for match in matches] == [
        "https://www.oddsportal.com/football/world/friendly-international/kyrgyzstan-kenya/#abc",
        "https://www.oddsportal.com/football/world/friendly-international/china-w-russia-w/#def",
    ]
    assert all(match["match_score"] >= 0.9 for match in matches)


def test_market_snapshot_coverage_matches_oddsportal_chinese_aliases(tmp_path):
    db_path = str(tmp_path / "snapshots.sqlite3")
    snapshot_store.save_market_snapshots(
        [
            snapshot_store.MarketSnapshot(
                provider="oddsportal_scraper",
                source_key="oddsportal:2Jr7PLmg:5:2",
                event_id="2Jr7PLmg",
                league="Friendly International",
                home_team="Philippines",
                away_team="Guam",
                kickoff_utc="2026-06-03T11:30:00+00:00",
                bookmaker="Example",
                market_type="asian_handicap",
                selection="home",
                decimal_odds=1.91,
                line=-1.0,
                source_time_utc="2026-06-03T07:00:00+00:00",
                fetched_at_utc="2026-06-03T07:10:00+00:00",
                raw={},
            )
        ],
        db_path=db_path,
    )

    coverage = snapshot_store.market_snapshot_coverage_for_records(
        [
            {
                "league": "国际友谊",
                "home_team": "菲律宾",
                "away_team": "关岛",
            }
        ],
        db_path=db_path,
    )

    item = coverage[snapshot_store.market_snapshot_match_key("菲律宾", "关岛")]
    assert item["provider"] == "oddsportal_scraper"
    assert item["snapshot_count"] == 1


def test_oddsportal_recommends_discovery_urls_from_prediction_targets():
    targets = [
        {"league": "England Premier League", "home_team": "Arsenal", "away_team": "Chelsea"},
        {"league": "J1 League", "home_team": "Kashima Antlers", "away_team": "Vissel Kobe"},
        {"league": "Unmapped Cup", "home_team": "A", "away_team": "B"},
    ]

    urls = oddsportal_source.oddsportal_discovery_urls_for_targets(targets)

    assert urls[:2] == [
        "https://www.oddsportal.com/football/england/premier-league/",
        "https://www.oddsportal.com/football/japan/j1-league/",
    ]
    assert "https://www.oddsportal.com/football/" in urls


def test_oddsportal_recommends_discovery_urls_from_chinese_league_aliases():
    targets = [
        {"league": "国际友谊", "home_team": "格鲁吉亚", "away_team": "罗马尼亚"},
    ]

    urls = oddsportal_source.oddsportal_discovery_urls_for_targets(targets, include_generic=False)

    assert urls == ["https://www.oddsportal.com/football/world/friendly-international/"]


def test_snapshot_store_records_source_sync_state_for_resume(tmp_path):
    db_path = str(tmp_path / "snapshots.sqlite3")

    first = snapshot_store.upsert_odds_source_sync_state(
        source="oddsportal_scraper",
        scope_key="j1-league",
        external_id="Oj63Qw3D",
        status="running",
        cursor={"market": "asian_handicap"},
        db_path=db_path,
    )
    second = snapshot_store.upsert_odds_source_sync_state(
        source="oddsportal_scraper",
        scope_key="j1-league",
        external_id="Oj63Qw3D",
        status="succeeded",
        snapshot_count=8,
        cursor={"market": "asian_handicap", "scope": "full_time"},
        db_path=db_path,
    )

    states = snapshot_store.list_odds_source_sync_state(source="oddsportal_scraper", db_path=db_path)

    assert first["attempt_count"] == 1
    assert second["attempt_count"] == 2
    assert len(states) == 1
    assert states[0]["status"] == "succeeded"
    assert states[0]["snapshot_count"] == 8
    assert states[0]["cursor"]["scope"] == "full_time"


def test_data_source_repository_builds_recent_analysis_odds_targets(tmp_path):
    db_path = str(tmp_path / "snapshots.sqlite3")
    snapshot_store.save_market_snapshots(
        [
            snapshot_store.MarketSnapshot(
                provider="analysis_odds",
                source_key="dongqiudi_odds_index",
                event_id="analysis-1",
                league="England Premier League",
                home_team="Arsenal",
                away_team="Chelsea",
                kickoff_utc="2026-06-02T18:00:00+00:00",
                bookmaker="36*",
                market_type="asian_handicap",
                selection="Arsenal",
                decimal_odds=1.9,
                line=-0.25,
                source_time_utc="2026-06-02T12:00:00+00:00",
                fetched_at_utc="2026-06-02T12:00:00+00:00",
                raw={"source": "analysis_odds"},
            ),
            snapshot_store.MarketSnapshot(
                provider="leisu",
                source_key="leisu",
                event_id="leisu-1",
                league="Japan J1 League",
                home_team="Kashima Antlers",
                away_team="Vissel Kobe",
                kickoff_utc="2026-06-02T18:00:00+00:00",
                bookmaker="bet365",
                market_type="asian_handicap",
                selection="Kashima Antlers",
                decimal_odds=1.8,
                line=-0.25,
                source_time_utc="2026-06-02T12:01:00+00:00",
                fetched_at_utc="2026-06-02T12:01:00+00:00",
                raw={"source": "leisu"},
            ),
        ],
        db_path=db_path,
    )

    targets = DataSourceRepository().recent_analysis_odds_targets(limit=10, db_path=db_path)

    assert targets == [
        {
            "target_source": "analysis_odds",
            "match_id": "analysis-1",
            "source_key": "dongqiudi_odds_index",
            "league": "England Premier League",
            "home_team": "Arsenal",
            "away_team": "Chelsea",
            "kickoff_utc": "2026-06-02T18:00:00+00:00",
            "latest_fetched_at_utc": "2026-06-02T12:00:00+00:00",
            "snapshot_count": 1,
            "bookmaker_count": 1,
        }
    ]


def test_data_source_service_reports_odds_source_status(tmp_path):
    db_path = str(tmp_path / "snapshots.sqlite3")
    snapshot_store.upsert_odds_source_sync_state(
        source="oddsportal_scraper",
        scope_key="j1-league",
        external_id="Oj63Qw3D",
        status="failed",
        error="timeout",
        db_path=db_path,
    )

    status = DataSourceService().odds_source_status(db_path=db_path)

    assert status["status"] == "ok"
    assert status["sync_state"]["total_count"] == 1
    assert status["sync_state"]["by_status"]["failed"] == 1
    assert status["sources"]["oddsportal_scraper"]["status"] == "failed"
    assert status["sources"]["oddsportal_scraper"]["retryable_url_count"] == 1
    assert status["sources"]["oddsportal_scraper"]["failed_count"] == 1
    assert "resume_failed=true" in status["sources"]["oddsportal_scraper"]["next_action"]
    assert status["sources"]["oddsportal_scraper"]["last_error"] == "timeout"


def test_data_source_service_marks_stale_primary_source_and_selects_fresh_fallback():
    now = datetime(2026, 6, 2, 12, 0, tzinfo=timezone.utc)

    class FakeRepository:
        def odds_source_status(self, *, db_path: str | None = None) -> dict[str, object]:
            return {
                "snapshot_summary": {},
                "provider_counts": {
                    "leisu": {
                        "provider": "leisu",
                        "snapshot_count": 240240,
                        "latest_fetched_at_utc": (now - timedelta(days=4)).isoformat(),
                    },
                    "analysis_odds": {
                        "provider": "analysis_odds",
                        "snapshot_count": 126407,
                        "latest_fetched_at_utc": (now - timedelta(minutes=5)).isoformat(),
                    },
                },
                "sync_state": {"by_source": {}, "recent": []},
            }

        def open_prediction_odds_targets(self, *, limit: int) -> list[dict[str, object]]:
            return []

    status = DataSourceService(repository=FakeRepository()).odds_source_status(now=now)

    leisu = status["sources"]["leisu"]
    analysis_odds = status["sources"]["analysis_odds"]
    closure = status["closure"]

    assert leisu["operational_status"] == "stale"
    assert leisu["freshness_status"] == "stale"
    assert leisu["usable_for_analysis"] is False
    assert "4.0 天" in leisu["next_action"]
    assert analysis_odds["operational_status"] == "derived_fallback"
    assert analysis_odds["usable_for_analysis"] is True
    assert closure["active_source"] == "analysis_odds"
    assert closure["production_ready"] is False
    assert closure["reason"] == "主赔率源已过期，当前只能使用分析过程沉淀的快照兜底。"


def test_data_source_service_selects_fresh_leisu_as_production_source():
    now = datetime(2026, 6, 2, 12, 0, tzinfo=timezone.utc)

    class FakeRepository:
        def odds_source_status(self, *, db_path: str | None = None) -> dict[str, object]:
            return {
                "snapshot_summary": {},
                "provider_counts": {
                    "leisu": {
                        "provider": "leisu",
                        "snapshot_count": 5000,
                        "latest_fetched_at_utc": (now - timedelta(minutes=10)).isoformat(),
                    },
                    "analysis_odds": {
                        "provider": "analysis_odds",
                        "snapshot_count": 6000,
                        "latest_fetched_at_utc": (now - timedelta(minutes=2)).isoformat(),
                    },
                },
                "sync_state": {"by_source": {}, "recent": []},
            }

        def open_prediction_odds_targets(self, *, limit: int) -> list[dict[str, object]]:
            return []

    status = DataSourceService(repository=FakeRepository()).odds_source_status(now=now)

    assert status["sources"]["leisu"]["operational_status"] == "available"
    assert status["sources"]["leisu"]["freshness_status"] == "fresh"
    assert status["closure"]["active_source"] == "leisu"
    assert status["closure"]["production_ready"] is True
    assert status["closure"]["reason"] == "雷速主赔率源新鲜可用。"


def test_data_source_service_surfaces_ready_leisu_browser_session(monkeypatch, tmp_path):
    session_path = tmp_path / "leisu-browser-session.json"
    monkeypatch.setenv("LEISU_BROWSER_SESSION_STATUS_PATH", str(session_path))
    monkeypatch.setenv("LEISU_ODDS_PROXY_URL", "http://127.0.0.1:8918/leisu/odds/{match_id}")
    browser_session_runtime.record_provider_status(
        "leisu",
        "ready",
        path=session_path,
        message="浏览器会话已就绪",
        last_fetch_at_utc="2026-06-02T11:58:00+00:00",
    )

    class FakeRepository:
        def odds_source_status(self, *, db_path: str | None = None) -> dict[str, object]:
            return {
                "snapshot_summary": {},
                "provider_counts": {},
                "sync_state": {"by_source": {}, "recent": []},
            }

        def open_prediction_odds_targets(self, *, limit: int) -> list[dict[str, object]]:
            return []

    status = DataSourceService(repository=FakeRepository()).odds_source_status()
    leisu = status["sources"]["leisu"]

    assert leisu["operational_status"] == "session_ready"
    assert leisu["browser_session_status"] == "ready"
    assert leisu["browser_session"]["message"] == "浏览器会话已就绪"
    assert leisu["runtime_support"]["provider"] == "leisu"
    assert leisu["runtime_support"]["browser_proxy_status_url"] == "http://127.0.0.1:8918/leisu/session"
    assert "浏览器辅助会话已就绪" in leisu["next_action"]


def test_data_source_service_surfaces_auth_required_leisu_browser_session(monkeypatch, tmp_path):
    session_path = tmp_path / "leisu-browser-session.json"
    monkeypatch.setenv("LEISU_BROWSER_SESSION_STATUS_PATH", str(session_path))
    browser_session_runtime.record_provider_status(
        "leisu",
        "auth_required",
        path=session_path,
        message="需要人工验证",
        last_verification_url="https://m.leisu.com/live/odds-4512919",
    )

    class FakeRepository:
        def odds_source_status(self, *, db_path: str | None = None) -> dict[str, object]:
            return {
                "snapshot_summary": {},
                "provider_counts": {},
                "sync_state": {"by_source": {}, "recent": []},
            }

        def open_prediction_odds_targets(self, *, limit: int) -> list[dict[str, object]]:
            return []

    status = DataSourceService(repository=FakeRepository()).odds_source_status()
    leisu = status["sources"]["leisu"]

    assert leisu["operational_status"] == "needs_auth"
    assert leisu["browser_session_status"] == "auth_required"
    assert leisu["browser_session"]["last_verification_url"] == "https://m.leisu.com/live/odds-4512919"
    assert "人工验证" in leisu["next_action"]


def test_data_source_service_reports_oddsportal_discovery_readiness(monkeypatch):
    monkeypatch.setenv("FOOTBALL_DATA_ODDSPORTAL_SCRAPER_ENABLED", "true")
    monkeypatch.setenv("FOOTBALL_DATA_AUTO_SYNC_ODDSPORTAL_ODDS", "true")
    monkeypatch.setenv(
        "FOOTBALL_DATA_ODDSPORTAL_DISCOVERY_URLS",
        "https://www.oddsportal.com/football/japan/j1-league/",
    )

    class FakeRepository:
        def odds_source_status(self, *, db_path: str | None = None) -> dict[str, object]:
            return {
                "snapshot_summary": {},
                "provider_counts": {},
                "sync_state": {"by_source": {}, "recent": []},
            }

        def open_prediction_odds_targets(self, *, limit: int) -> list[dict[str, object]]:
            assert limit == 100
            return [
                {
                    "home_team": "Kashima Antlers",
                    "away_team": "Vissel Kobe",
                    "league": "J1 League",
                }
            ]

    status = DataSourceService(repository=FakeRepository()).odds_source_status()
    oddsportal = status["sources"]["oddsportal_scraper"]

    assert oddsportal["scraper_enabled"] is True
    assert oddsportal["auto_sync_enabled"] is True
    assert oddsportal["discovery_ready"] is True
    assert oddsportal["configured_discovery_url_count"] == 1
    assert oddsportal["effective_discovery_url_count"] == 1
    assert oddsportal["open_target_count"] == 1
    assert "自动发现已就绪" in oddsportal["next_action"]


def test_data_source_service_uses_built_in_oddsportal_discovery_urls(monkeypatch):
    monkeypatch.setenv("FOOTBALL_DATA_ODDSPORTAL_SCRAPER_ENABLED", "true")
    monkeypatch.setenv("FOOTBALL_DATA_AUTO_SYNC_ODDSPORTAL_ODDS", "true")
    monkeypatch.delenv("FOOTBALL_DATA_ODDSPORTAL_DISCOVERY_URLS", raising=False)

    class FakeRepository:
        def odds_source_status(self, *, db_path: str | None = None) -> dict[str, object]:
            return {
                "snapshot_summary": {},
                "provider_counts": {},
                "sync_state": {"by_source": {}, "recent": []},
            }

        def open_prediction_odds_targets(self, *, limit: int) -> list[dict[str, object]]:
            return [{"home_team": "Arsenal", "away_team": "Chelsea", "league": "England Premier League"}]

    status = DataSourceService(repository=FakeRepository()).odds_source_status()
    oddsportal = status["sources"]["oddsportal_scraper"]

    assert oddsportal["configured_discovery_url_count"] == 0
    assert oddsportal["suggested_discovery_url_count"] == 1
    assert oddsportal["effective_discovery_url_count"] == 1
    assert oddsportal["discovery_ready"] is True
    assert oddsportal["suggested_discovery_urls"] == [
        "https://www.oddsportal.com/football/england/premier-league/"
    ]


def test_data_source_service_uses_recent_analysis_odds_as_discovery_seed(monkeypatch):
    monkeypatch.setenv("FOOTBALL_DATA_ODDSPORTAL_SCRAPER_ENABLED", "true")
    monkeypatch.setenv("FOOTBALL_DATA_AUTO_SYNC_ODDSPORTAL_ODDS", "true")
    monkeypatch.delenv("FOOTBALL_DATA_ODDSPORTAL_DISCOVERY_URLS", raising=False)

    class FakeRepository:
        def odds_source_status(self, *, db_path: str | None = None) -> dict[str, object]:
            return {
                "snapshot_summary": {},
                "provider_counts": {},
                "sync_state": {"by_source": {}, "recent": []},
            }

        def open_prediction_odds_targets(self, *, limit: int) -> list[dict[str, object]]:
            return []

        def recent_analysis_odds_targets(self, *, limit: int) -> list[dict[str, object]]:
            assert limit == 100
            return [{"home_team": "Arsenal", "away_team": "Chelsea", "league": "England Premier League"}]

    status = DataSourceService(repository=FakeRepository()).odds_source_status()
    oddsportal = status["sources"]["oddsportal_scraper"]

    assert oddsportal["open_target_count"] == 0
    assert oddsportal["analysis_target_count"] == 1
    assert oddsportal["discovery_target_count"] == 1
    assert oddsportal["discovery_target_source"] == "analysis_odds"
    assert oddsportal["suggested_discovery_urls"] == [
        "https://www.oddsportal.com/football/england/premier-league/"
    ]
    assert oddsportal["discovery_ready"] is True


def test_data_source_service_can_queue_oddsportal_sync_job():
    calls: list[dict[str, object]] = []

    class FakeStarter:
        async def start_oddsportal_snapshot_sync_job(self, job_id: str, payload: dict[str, object]) -> object:
            calls.append({"job_id": job_id, "payload": payload})
            return OddsSourceSyncJobStartResult(backend="arq", queue_job_id=f"oddsportal-sync:{job_id}")

    service = DataSourceService(odds_sync_job_starter=FakeStarter())

    queued = asyncio.run(
        service.start_oddsportal_sync(
            event_urls=[" https://www.oddsportal.com/football/h2h/example/#abc "],
            markets=["asian_handicap", "unsupported"],
            limit=5,
            force=True,
            start_background=True,
        )
    )

    assert queued["status"] == "queued"
    assert queued["provider"] == "oddsportal_scraper"
    assert queued["backend"] == "arq"
    assert queued["queue_job_id"].startswith("oddsportal-sync:")
    assert queued["payload"]["event_urls"] == ["https://www.oddsportal.com/football/h2h/example/#abc"]
    assert queued["payload"]["markets"] == ["asian_handicap"]
    assert calls[0]["payload"] == queued["payload"]


def test_data_source_service_does_not_queue_empty_oddsportal_sync_job():
    calls: list[dict[str, object]] = []

    class FakeStarter:
        async def start_oddsportal_snapshot_sync_job(self, job_id: str, payload: dict[str, object]) -> object:
            calls.append({"job_id": job_id, "payload": payload})
            return OddsSourceSyncJobStartResult(backend="arq", queue_job_id=f"oddsportal-sync:{job_id}")

    service = DataSourceService(odds_sync_job_starter=FakeStarter())

    result = asyncio.run(
        service.start_oddsportal_sync(
            event_urls=[],
            markets=["asian_handicap"],
            limit=5,
            force=False,
            start_background=True,
        )
    )

    assert result["status"] == "empty"
    assert result["provider"] == "oddsportal_scraper"
    assert "No OddsPortal event URLs" in result["message"]
    assert calls == []


def test_data_source_service_can_resume_failed_oddsportal_urls():
    calls: list[dict[str, object]] = []

    class FakeRepository:
        def retryable_oddsportal_event_urls(self, *, statuses: list[str], limit: int) -> list[str]:
            assert statuses == ["failed", "empty"]
            assert limit == 3
            return ["https://www.oddsportal.com/football/h2h/resume/#abc"]

        def mark_oddsportal_sync_queued(self, **kwargs) -> None:
            calls.append({"function": "mark_queued", "kwargs": kwargs})

    class FakeStarter:
        async def start_oddsportal_snapshot_sync_job(self, job_id: str, payload: dict[str, object]) -> object:
            calls.append({"function": "start", "job_id": job_id, "payload": payload})
            return OddsSourceSyncJobStartResult(backend="arq", queue_job_id=f"oddsportal-sync:{job_id}")

    service = DataSourceService(repository=FakeRepository(), odds_sync_job_starter=FakeStarter())

    result = asyncio.run(
        service.start_oddsportal_sync(
            event_urls=[],
            markets=["asian_handicap"],
            limit=3,
            force=True,
            resume_failed=True,
            start_background=True,
        )
    )

    assert result["status"] == "queued"
    assert result["payload"]["event_urls"] == ["https://www.oddsportal.com/football/h2h/resume/#abc"]
    assert calls[0]["function"] == "mark_queued"
    assert calls[1]["function"] == "start"


def test_data_source_service_can_auto_discover_oddsportal_urls():
    calls: list[dict[str, object]] = []

    class FakeRepository:
        def open_prediction_odds_targets(self, *, limit: int) -> list[dict[str, object]]:
            assert limit == 25
            return [
                {
                    "home_team": "Kashima Antlers",
                    "away_team": "Vissel Kobe",
                    "league": "J1 League",
                    "kickoff_utc": "2026-06-02T12:00:00+00:00",
                }
            ]

        async def discover_oddsportal_event_urls(
            self,
            *,
            targets: list[dict[str, object]],
            discovery_urls: list[str],
            limit: int,
        ) -> dict[str, object]:
            assert targets[0]["home_team"] == "Kashima Antlers"
            assert discovery_urls == ["https://www.oddsportal.com/football/japan/j1-league/"]
            assert limit == 2
            return {
                "status": "ok",
                "event_urls": ["https://www.oddsportal.com/football/japan/j1-league/kashima-vissel-kobe-Oj63Qw3D/"],
                "matches": [
                    {
                        "event_url": "https://www.oddsportal.com/football/japan/j1-league/kashima-vissel-kobe-Oj63Qw3D/",
                        "match_score": 0.97,
                    }
                ],
            }

        def mark_oddsportal_sync_queued(self, **kwargs) -> None:
            calls.append({"function": "mark_queued", "kwargs": kwargs})

    class FakeStarter:
        async def start_oddsportal_snapshot_sync_job(self, job_id: str, payload: dict[str, object]) -> object:
            calls.append({"function": "start", "job_id": job_id, "payload": payload})
            return OddsSourceSyncJobStartResult(backend="arq", queue_job_id=f"oddsportal-sync:{job_id}")

    service = DataSourceService(repository=FakeRepository(), odds_sync_job_starter=FakeStarter())

    result = asyncio.run(
        service.start_oddsportal_sync(
            event_urls=[],
            markets=["asian_handicap"],
            limit=2,
            force=True,
            auto_discover=True,
            discovery_urls=["https://www.oddsportal.com/football/japan/j1-league/"],
            target_limit=25,
            start_background=True,
        )
    )

    assert result["status"] == "queued"
    assert result["payload"]["event_urls"] == [
        "https://www.oddsportal.com/football/japan/j1-league/kashima-vissel-kobe-Oj63Qw3D/"
    ]
    assert result["payload"]["discovery_result"]["status"] == "ok"
    assert calls[0]["function"] == "mark_queued"
    assert calls[1]["function"] == "start"


def test_data_source_service_auto_discover_uses_suggested_urls_when_not_configured(monkeypatch):
    monkeypatch.delenv("FOOTBALL_DATA_ODDSPORTAL_DISCOVERY_URLS", raising=False)
    calls: list[dict[str, object]] = []

    class FakeRepository:
        def open_prediction_odds_targets(self, *, limit: int) -> list[dict[str, object]]:
            return [{"home_team": "Arsenal", "away_team": "Chelsea", "league": "England Premier League"}]

        async def discover_oddsportal_event_urls(
            self,
            *,
            targets: list[dict[str, object]],
            discovery_urls: list[str],
            limit: int,
        ) -> dict[str, object]:
            assert discovery_urls == ["https://www.oddsportal.com/football/england/premier-league/"]
            return {
                "status": "ok",
                "event_urls": ["https://www.oddsportal.com/football/england/premier-league/arsenal-chelsea/#abc"],
                "matches": [],
            }

        def mark_oddsportal_sync_queued(self, **kwargs) -> None:
            calls.append({"function": "mark_queued", "kwargs": kwargs})

    class FakeStarter:
        async def start_oddsportal_snapshot_sync_job(self, job_id: str, payload: dict[str, object]) -> object:
            calls.append({"function": "start", "job_id": job_id, "payload": payload})
            return OddsSourceSyncJobStartResult(backend="arq", queue_job_id=f"oddsportal-sync:{job_id}")

    service = DataSourceService(repository=FakeRepository(), odds_sync_job_starter=FakeStarter())

    result = asyncio.run(
        service.start_oddsportal_sync(
            event_urls=[],
            markets=["asian_handicap"],
            limit=2,
            force=True,
            auto_discover=True,
            discovery_urls=[],
            target_limit=25,
            start_background=True,
        )
    )

    assert result["status"] == "queued"
    assert result["payload"]["discovery_urls"] == ["https://www.oddsportal.com/football/england/premier-league/"]
    assert calls[0]["function"] == "mark_queued"


def test_data_source_service_auto_discover_uses_recent_analysis_seed_when_open_targets_empty(monkeypatch):
    monkeypatch.delenv("FOOTBALL_DATA_ODDSPORTAL_DISCOVERY_URLS", raising=False)
    calls: list[dict[str, object]] = []

    class FakeRepository:
        def open_prediction_odds_targets(self, *, limit: int) -> list[dict[str, object]]:
            return []

        def recent_analysis_odds_targets(self, *, limit: int) -> list[dict[str, object]]:
            assert limit == 25
            return [{"home_team": "Arsenal", "away_team": "Chelsea", "league": "England Premier League"}]

        async def discover_oddsportal_event_urls(
            self,
            *,
            targets: list[dict[str, object]],
            discovery_urls: list[str],
            limit: int,
        ) -> dict[str, object]:
            assert targets == [
                {"home_team": "Arsenal", "away_team": "Chelsea", "league": "England Premier League"}
            ]
            assert discovery_urls == ["https://www.oddsportal.com/football/england/premier-league/"]
            return {
                "status": "ok",
                "event_urls": ["https://www.oddsportal.com/football/england/premier-league/arsenal-chelsea/#abc"],
                "matches": [],
            }

        def mark_oddsportal_sync_queued(self, **kwargs) -> None:
            calls.append({"function": "mark_queued", "kwargs": kwargs})

    class FakeStarter:
        async def start_oddsportal_snapshot_sync_job(self, job_id: str, payload: dict[str, object]) -> object:
            calls.append({"function": "start", "job_id": job_id, "payload": payload})
            return OddsSourceSyncJobStartResult(backend="arq", queue_job_id=f"oddsportal-sync:{job_id}")

    service = DataSourceService(repository=FakeRepository(), odds_sync_job_starter=FakeStarter())

    result = asyncio.run(
        service.start_oddsportal_sync(
            event_urls=[],
            markets=["asian_handicap"],
            limit=2,
            force=True,
            auto_discover=True,
            discovery_urls=[],
            target_limit=25,
            start_background=True,
        )
    )

    assert result["status"] == "queued"
    assert result["payload"]["discovery_target_source"] == "analysis_odds"
    assert result["payload"]["discovery_target_count"] == 1
    assert result["payload"]["event_urls"] == [
        "https://www.oddsportal.com/football/england/premier-league/arsenal-chelsea/#abc"
    ]
    assert calls[0]["function"] == "mark_queued"


def test_dashboard_snapshot_exposes_odds_source_status(tmp_path):
    db_path = str(tmp_path / "learning.sqlite3")
    market_db_path = str(tmp_path / "snapshots.sqlite3")
    snapshot_store.upsert_odds_source_sync_state(
        source="oddsportal_scraper",
        scope_key="manual_event_url",
        external_id="https://www.oddsportal.com/football/h2h/example/#abc",
        status="succeeded",
        snapshot_count=8,
        cursor={"markets": ["asian_handicap"]},
        db_path=market_db_path,
    )

    snapshot = sources_module.dashboard_snapshot(db_path=db_path, market_db_path=market_db_path, limit=10)

    assert snapshot["odds_source_status"]["status"] == "ok"
    assert snapshot["odds_source_status"]["sync_state"]["by_source"]["oddsportal_scraper"]["latest_status"] == "succeeded"
    assert snapshot["odds_source_status"]["sources"]["oddsportal_scraper"]["role"]
