from __future__ import annotations

import asyncio

from football_data_mcp.services.mobile_service import MobileAnalysisService


class FakeSources:
    def __init__(self):
        self.list_calls = 0
        self.analysis_calls = 0

    async def list_matches(self, **kwargs):
        self.list_calls += 1
        return {
            "status": "ok",
            "source": {"name": "fake"},
            "time_window_policy": {"window_hours": kwargs.get("window_hours")},
            "total_count": 1,
            "matches": [
                {
                    "match_id": "m-1",
                    "home_team": "北城 FC",
                    "away_team": "海港城",
                    "league": "英超",
                    "kickoff_utc": "2026-06-03T12:00:00+00:00",
                    "kickoff_utc_plus_8": "2026-06-03T20:00:00+08:00",
                    "analysis_readiness": {"can_run_single_match_analysis": True},
                }
            ],
        }

    async def analyze_single_match(self, query, **kwargs):
        self.analysis_calls += 1
        return {
            "status": "ok",
            "match": {
                "match_id": "m-1",
                "home_team": "北城 FC",
                "away_team": "海港城",
                "league": "英超",
                "kickoff_utc_plus_8": "2026-06-03T20:00:00+08:00",
            },
            "odds": {
                "quality_contract": {
                    "preferred_moneyline_1x2": {
                        "current": {"home": 2.1, "draw": 3.4, "away": 3.6},
                        "current_metrics": {
                            "normalized_probability": {"home": 0.45, "draw": 0.28, "away": 0.27}
                        },
                    }
                }
            },
            "analysis_pack": {
                "data_coverage": {
                    "blocks": {
                        "schedule": True,
                        "moneyline_1x2": True,
                        "asian_handicap": True,
                        "model_engine": True,
                        "lineup": False,
                    }
                }
            },
            "data_bundle": {
                "market_movement": {
                    "status": "available",
                    "primary_movement": {
                        "direction_label": "升温",
                        "first_observed_at_utc": "2026-06-03T08:00:00+00:00",
                        "latest_observed_at_utc": "2026-06-03T10:00:00+00:00",
                    },
                    "key_movements": [],
                }
            },
            "betting_decision_support": {
                "confidence": 0.62,
                "blocking_flags": [],
                "caution_flags": ["lineup_unavailable"],
                "best_candidate": {
                    "market": "asian_handicap",
                    "selection": "北城 FC -0.25",
                    "selection_key": "home_cover",
                    "model_probability": 0.482,
                    "raw_model_probability": 0.46,
                    "edge": 0.036,
                    "decimal_odds": 2.08,
                    "market_movement_signal": "supports_selection",
                    "market_movement_note": "盘口走势：北城 FC -0.25 升温。",
                    "market_movement": {
                        "status": "available",
                        "direction": "shortening",
                        "direction_label": "升温",
                        "opening_decimal_odds": 1.98,
                        "latest_decimal_odds": 1.88,
                        "opening_line": -0.25,
                        "latest_line": -0.5,
                        "line_delta": -0.25,
                        "odds_delta": -0.1,
                        "implied_probability_delta": 0.026,
                        "first_observed_at_utc": "2026-06-03T08:00:00+00:00",
                        "latest_observed_at_utc": "2026-06-03T10:00:00+00:00",
                    },
                    "odds_movement_calibration": {"adjustment": 0.022},
                },
                "market_candidates": [
                    {
                        "market": "asian_handicap",
                        "selection": "北城 FC -0.25",
                        "selection_key": "home_cover",
                        "line": -0.25,
                        "decimal_odds": 2.08,
                        "model_probability": 0.482,
                    }
                ],
                "model_engine": {
                    "expected_goals": {"home": 1.52, "away": 1.08},
                    "derived_probabilities": {
                        "1x2": {"home": 0.456, "draw": 0.271, "away": 0.273},
                        "asian_handicap": {"line": -0.25, "home_cover": 0.482, "away_cover": 0.518},
                        "over_under": {"line": 2.5, "over": 0.51, "under": 0.49},
                    },
                    "scoreline_distribution": [
                        {"home_goals": 1, "away_goals": 0, "probability": 0.16},
                        {"home_goals": 1, "away_goals": 1, "probability": 0.12},
                        {"home_goals": 0, "away_goals": 1, "probability": 0.10},
                    ],
                },
            },
        }


class FakeValidationStore:
    @staticmethod
    def get_latest_validation():
        return {
            "method": "holdout_v2",
            "automation_readiness": "not_ready",
            "beats_market": False,
            "log_loss_diff": 0.02,
            "roi": -0.05,
            "bet_count": 0,
            "evaluated_count": 84,
            "created_at_utc": "2026-06-03T12:00:00+00:00",
        }


class FakeDataSourceService:
    @staticmethod
    def odds_source_status():
        return {
            "sources": {
                "leisu": {
                    "next_action": "雷速无可用赔率快照；配置 LEISU_ODDS_PROXY_URL/COOKIE，或继续由 oddsportal_scraper 补位。",
                },
                "oddsportal_scraper": {
                    "next_action": "OddsPortal 兜底快照正常运行，等待雷速恢复后切回主源。",
                },
            },
            "closure": {
                "active_source": "oddsportal_scraper",
                "production_ready": True,
                "reason": "雷速不可用或过期，当前使用独立爬虫赔率源兜底。",
                "checked_at_utc": "2026-06-03T12:05:00+00:00",
            },
        }


def test_mobile_service_shapes_match_list_for_ios():
    service = MobileAnalysisService(
        source_module=FakeSources(),
        validation_store_module=FakeValidationStore(),
        data_source_service=FakeDataSourceService(),
    )

    result = asyncio.run(service.matches(limit=5))

    assert result["status"] == "ok"
    assert result["matches"][0]["query"] == "北城 FC vs 海港城"
    assert result["matches"][0]["analysisReady"] is True
    assert result["modelReadiness"]["status"] == "not_ready"
    assert result["oddsSourceHealth"]["status"] == "fallback"


def test_mobile_service_shapes_analysis_for_ios_decoding_contract():
    service = MobileAnalysisService(
        source_module=FakeSources(),
        validation_store_module=FakeValidationStore(),
        data_source_service=FakeDataSourceService(),
    )

    result = asyncio.run(service.analysis(query="北城 FC vs 海港城"))
    analysis = result["analysis"]

    assert analysis["homeTeam"]["name"] == "北城 FC"
    assert analysis["finalProbabilities"]["home"] == 0.456
    assert analysis["oddsMovement"]["points"][0]["direction"] == "supportsHome"
    assert analysis["asian"]["line"] == -0.25
    assert len(analysis["scoreMatrix"]) == 25
    assert analysis["adjustments"][1]["title"] == "赔率走势校准"
    assert analysis["modelReadiness"]["label"] == "未通过验证"
    assert analysis["oddsSourceHealth"]["activeSource"] == "oddsportal_scraper"
    assert analysis["dataSources"][2]["name"] == "独立赔率源"
    assert analysis["risks"][0]["title"] == "未通过验证"


def test_mobile_service_caches_match_lists_for_short_window():
    fake_sources = FakeSources()
    service = MobileAnalysisService(source_module=fake_sources)

    first = asyncio.run(service.matches(limit=5))
    second = asyncio.run(service.matches(limit=5))

    assert first["cache"]["hit"] is False
    assert second["cache"]["hit"] is True
    assert fake_sources.list_calls == 1


def test_mobile_service_caches_analysis_for_same_match():
    fake_sources = FakeSources()
    service = MobileAnalysisService(source_module=fake_sources)

    first = asyncio.run(service.analysis(query="北城 FC vs 海港城"))
    second = asyncio.run(service.analysis(query="北城 FC vs 海港城"))

    assert first["cache"]["hit"] is False
    assert second["cache"]["hit"] is True
    assert fake_sources.analysis_calls == 1
