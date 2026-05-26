import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path

from football_data_mcp.sources import (
    block_reason,
    build_odds_quality_contract,
    merge_odds,
    normalize_text,
    leisu_market_snapshots_from_odds,
    odds_from_leisu_odds_payload,
    odds_from_dongqiudi_odds_index,
    odds_from_dongqiudi_match,
    odds_from_row,
    parse_dongqiudi_kickoff,
    parse_leisu_odds_html,
    parse_leisu_schedule_html,
    parse_match_query,
    row_match_score,
    season_code_for,
    source_block_reason,
    summarize_lineup,
)
from football_data_mcp import server
from football_data_mcp import sources as sources_module


def test_parse_chinese_match_query():
    query, home, away = parse_match_query("利物浦 vs 阿森纳")
    assert "Liverpool" in query
    assert home == "Liverpool"
    assert away == "Arsenal"


def test_odds_from_row_extracts_numeric_moneyline():
    row = {
        "B365H": "1.8",
        "B365D": "3.5",
        "B365A": "4.2",
        "AvgH": "1.77",
        "AvgD": "3.61",
        "AvgA": "4.01",
    }
    odds = odds_from_row(row)
    assert odds["has_valid_numeric_odds"] is True
    assert odds["moneyline_1x2"][0]["home"] == 1.8


def test_season_code_for_may_2026():
    assert season_code_for(datetime(2026, 5, 21, tzinfo=timezone.utc)) == "2526"


def test_normalize_alias():
    assert normalize_text("曼城") == "man city"


def test_normalize_long_chinese_alias_first():
    query, home, away = parse_match_query("町田泽维亚VS浦和红钻")
    assert normalize_text(query) == "machida zelvia vs urawa red diamonds"
    assert home == "Machida Zelvia"
    assert away == "Urawa Red Diamonds"


def test_unknown_chinese_u19_teams_do_not_normalize_to_same_token():
    assert normalize_text("科帕沃于尔U19") != normalize_text("伯拉治U19")
    assert (
        row_match_score(
            {"HomeTeam": "伯拉治U19", "AwayTeam": "兹维耶达U19", "Div": "波黑U19"},
            "科帕沃于尔U19 vs 伏尔松古U19",
            "科帕沃于尔U19",
            "伏尔松古U19",
            "冰岛U19",
        )
        < 0.68
    )


def test_parse_dongqiudi_kickoff_as_utc():
    kickoff = parse_dongqiudi_kickoff("2026-05-22 10:30:00")
    assert kickoff.isoformat() == "2026-05-22T10:30:00+00:00"


def test_dongqiudi_context_candidate_can_enrich_primary_fixture():
    best = {
        "league": "英乙",
        "home_team": "诺茨郡",
        "away_team": "索尔福德城",
        "kickoff_utc_plus_8": "2026-05-25T22:00:00+08:00",
        "match_score": 1.0,
    }
    dongqiudi_candidate = {
        "source_name": "dongqiudi",
        "match_id": "54440001",
        "league": "英乙",
        "home_team": "诺茨郡",
        "away_team": "索尔福德城",
        "kickoff_utc_plus_8": "2026-05-25T22:00:00+08:00",
        "match_score": 0.98,
    }

    candidate = sources_module._dongqiudi_context_candidate_for_match(
        best,
        {"candidates": [best, dongqiudi_candidate]},
    )
    merged = sources_module._attach_context_match_identity(best, candidate)

    assert candidate == dongqiudi_candidate
    assert merged["match_id"] == "54440001"
    assert merged["context_source_name"] == "dongqiudi"
    assert merged["context_match"]["home_team"] == "诺茨郡"


def test_odds_from_dongqiudi_match_extracts_moneyline():
    odds = odds_from_dongqiudi_match(
        {
            "score_odds": {
                "origin": ["0.95,0.25,0.85", "2.15,3.2,3.2", "0.95,2.25,0.85"],
                "spot": ["0.95,0.25,0.85", "2.25,3.2,3.2", "0.9,2.25,0.9"],
            },
            "sporttery_str": "001 18钻",
        }
    )
    assert odds["has_valid_numeric_odds"] is True
    assert odds["moneyline_1x2"][1]["home"] == 2.25
    assert odds["asian_handicap"]["Dongqiudi current AH line"] == 0.25


def test_dongqiudi_odds_index_prefers_official_sporttery_moneyline():
    odds = odds_from_dongqiudi_odds_index(
        {
            "has_odds": True,
            "euro": [
                {
                    "name": "平均值",
                    "area": "欧洲",
                    "now": {"homeWin": "2.32", "draw": "2.96", "awayWin": "2.90", "ts": "2026-05-22 11:10"},
                    "begin": {"homeWin": "2.18", "draw": "3.05", "awayWin": "2.95", "ts": "2026-05-21 18:00"},
                },
                {
                    "name": "竞彩官方",
                    "area": "中国",
                    "now": {"homeWin": "2.30", "draw": "2.90", "awayWin": "2.87", "ts": "2026-05-22 11:20"},
                    "begin": {"homeWin": "2.20", "draw": "3.00", "awayWin": "2.93", "ts": "2026-05-21 18:00"},
                },
            ],
            "asia": [
                {
                    "name": "竞彩官方",
                    "area": "中国",
                    "now": {"homeWin": "0.92", "draw": "-0.25", "awayWin": "0.88", "ts": "2026-05-22 11:20"},
                    "begin": {"homeWin": "0.96", "draw": "0", "awayWin": "0.84", "ts": "2026-05-21 18:00"},
                }
            ],
        }
    )

    assert odds["preferred_moneyline_1x2"]["provider"] == "竞彩官方"
    assert odds["preferred_moneyline_1x2"]["current"] == {
        "home": 2.30,
        "draw": 2.90,
        "away": 2.87,
        "timestamp": "2026-05-22 11:20",
    }
    assert odds["preferred_asian_handicap"]["provider"] == "竞彩官方"
    assert odds["preferred_asian_handicap"]["current"]["line"] == -0.25
    assert odds["quality_contract"]["preferred_asian_handicap"]["current_metrics"]["normalized_probability"]["home_cover"] == 0.494737
    assert odds["market_policy"]["moneyline_1x2"].startswith("Use preferred_moneyline_1x2")


def test_odds_quality_contract_allows_asian_handicap_without_moneyline():
    contract = build_odds_quality_contract(
        {
            "preferred_asian_handicap": {
                "provider": "竞彩官方",
                "current": {"home_water": 0.92, "line": -0.25, "away_water": 0.88, "timestamp": "05-22 14:31"},
                "opening": {"home_water": 0.96, "line": 0, "away_water": 0.84, "timestamp": "05-21 18:00"},
            }
        }
    )

    assert contract["can_use_for_calculation"] is True
    assert contract["hard_flags"] == []
    assert contract["preferred_moneyline_1x2"]["available"] is False
    assert contract["preferred_asian_handicap"]["available"] is True
    metrics = contract["preferred_asian_handicap"]["current_metrics"]
    assert metrics["decimal_odds"]["home_cover"] == 1.92
    assert metrics["normalized_probability"]["away_cover"] == 0.505263


def test_dongqiudi_odds_index_parses_chinese_asian_handicap_line():
    odds = odds_from_dongqiudi_odds_index(
        {
            "has_odds": True,
            "asia": [
                {
                    "name": "Manbe**",
                    "area": "亚洲",
                    "now": {"homeWin": "0.87", "draw": "平/半", "awayWin": "0.78", "ts": "05-22 19:11"},
                    "begin": {"homeWin": "0.77", "draw": "受平/半", "awayWin": "0.75", "ts": "05-21 14:12"},
                }
            ],
        }
    )

    assert odds["preferred_asian_handicap"]["current"]["line"] == -0.25
    assert odds["preferred_asian_handicap"]["current"]["line_label"] == "平/半"
    assert odds["preferred_asian_handicap"]["opening"]["line"] == 0.25
    assert odds["quality_contract"]["supported_markets"]["asian_handicap"] is True


def test_dongqiudi_odds_index_prefers_freshest_complete_asian_handicap():
    odds = odds_from_dongqiudi_odds_index(
        {
            "has_odds": True,
            "asia": [
                {
                    "name": "澳*",
                    "area": "澳门",
                    "now": {"homeWin": "1.00", "draw": "一/球半", "awayWin": "0.70", "ts": "05-22 12:52"},
                    "begin": {"homeWin": "0.75", "draw": "一/球半", "awayWin": "0.95", "ts": "05-22 00:42"},
                },
                {
                    "name": "乐天*",
                    "area": "亚洲",
                    "now": {"homeWin": "0.83", "draw": "一球", "awayWin": "0.99", "ts": "05-22 20:14"},
                    "begin": {"homeWin": "0.87", "draw": "一/球半", "awayWin": "0.95", "ts": "05-21 22:08"},
                },
                {
                    "name": "Bet3**",
                    "area": "英国",
                    "now": {"homeWin": "0.77", "draw": "一球", "awayWin": "1.02", "ts": "05-22 20:13"},
                    "begin": {"homeWin": "0.80", "draw": "一/球半", "awayWin": "1.00", "ts": "05-21 20:22"},
                },
            ],
        }
    )

    assert odds["preferred_asian_handicap"]["provider"] == "乐天*"
    assert odds["preferred_asian_handicap"]["current"]["line"] == -1.0
    assert odds["preferred_asian_handicap"]["current"]["timestamp"] == "05-22 20:14"
    assert odds["market_policy"]["asian_handicap"].startswith("Use the freshest complete")


def test_dongqiudi_odds_index_returns_full_asian_handicap_markets_and_consensus():
    asia = [
        {
            "name": "澳*",
            "area": "澳门",
            "now": {"homeWin": "1.00", "draw": "一/球半", "awayWin": "0.70", "ts": "2026-05-22 12:52"},
            "begin": {"homeWin": "0.75", "draw": "一/球半", "awayWin": "0.95", "ts": "2026-05-22 00:42"},
        },
        {
            "name": "Manbe**",
            "area": "亚洲",
            "now": {"homeWin": "0.70", "draw": "一球", "awayWin": "0.95", "ts": "2026-05-22 20:00"},
            "begin": {"homeWin": "0.73", "draw": "一/球半", "awayWin": "0.83", "ts": "2026-05-21 19:47"},
        },
        {
            "name": "乐天*",
            "area": "亚洲",
            "now": {"homeWin": "0.83", "draw": "一球", "awayWin": "0.99", "ts": "2026-05-22 20:14"},
            "begin": {"homeWin": "0.87", "draw": "一/球半", "awayWin": "0.95", "ts": "2026-05-21 22:08"},
        },
        {
            "name": "韦*",
            "area": "直布",
            "now": {"homeWin": "0.78", "draw": "一球", "awayWin": "1.04", "ts": "2026-05-22 20:11"},
            "begin": {"homeWin": "0.87", "draw": "一/球半", "awayWin": "0.92", "ts": "2026-05-22 09:37"},
        },
        {
            "name": "Bet3**",
            "area": "英国",
            "now": {"homeWin": "0.77", "draw": "一球", "awayWin": "1.02", "ts": "2026-05-22 20:13"},
            "begin": {"homeWin": "0.80", "draw": "一/球半", "awayWin": "1.00", "ts": "2026-05-21 20:22"},
        },
        {
            "name": "必*",
            "area": "哥斯",
            "now": {"homeWin": "1.05", "draw": "一/球半", "awayWin": "0.75", "ts": "2026-05-22 20:13"},
            "begin": {"homeWin": "0.91", "draw": "一/球半", "awayWin": "0.89", "ts": "2026-05-22 12:14"},
        },
        {
            "name": "易胜*",
            "area": "英国",
            "now": {"homeWin": "0.76", "draw": "一球", "awayWin": "1.01", "ts": "2026-05-22 20:10"},
            "begin": {"homeWin": "0.82", "draw": "一/球半", "awayWin": "0.93", "ts": "2026-05-22 06:03"},
        },
        {
            "name": "利*",
            "area": "英国",
            "now": {"homeWin": "1.02", "draw": "一/球半", "awayWin": "0.78", "ts": "2026-05-22 14:28"},
            "begin": {"homeWin": "0.83", "draw": "一/球半", "awayWin": "0.95", "ts": "2026-05-22 07:29"},
        },
        {
            "name": "明*",
            "area": "亚洲",
            "now": {"homeWin": "1.02", "draw": "一/球半", "awayWin": "0.78", "ts": "2026-05-22 20:13"},
            "begin": {"homeWin": "0.91", "draw": "一/球半", "awayWin": "0.89", "ts": "2026-05-22 12:15"},
        },
        {
            "name": "Sportsb**",
            "area": "荷兰",
            "now": {"homeWin": "0.80", "draw": "一球", "awayWin": "1.07", "ts": "2026-05-22 19:57"},
            "begin": {"homeWin": "0.84", "draw": "一/球半", "awayWin": "0.93", "ts": "2026-05-21 20:12"},
        },
        {
            "name": "第十一家",
            "area": "亚洲",
            "now": {"homeWin": "0.81", "draw": "一球", "awayWin": "1.05", "ts": "2026-05-22 19:59"},
            "begin": {"homeWin": "0.85", "draw": "一/球半", "awayWin": "0.94", "ts": "2026-05-21 20:20"},
        },
    ]

    odds = odds_from_dongqiudi_odds_index({"has_odds": True, "asia": asia})
    consensus = odds["asian_handicap_consensus"]

    assert len(odds["asian_handicap_markets"]) == 11
    assert consensus["available"] is True
    assert consensus["market_count"] == 11
    assert consensus["complete_market_count"] == 11
    assert consensus["main_line"]["line"] == -1.0
    assert consensus["main_line"]["market_count"] == 7
    assert consensus["latest_market"]["provider"] == "乐天*"
    assert consensus["latest_market"]["timestamp"] == "2026-05-22 20:14"
    assert consensus["preferred"]["provider"] == "乐天*"
    assert consensus["preferred"]["matches_latest"] is True
    assert consensus["preferred"]["matches_main_line"] is True
    assert consensus["line_distribution"][0]["line"] == -1.0
    assert consensus["line_distribution"][0]["avg_home_water"] == 0.778571
    assert consensus["line_distribution"][0]["providers"] == [
        "Manbe**",
        "乐天*",
        "韦*",
        "Bet3**",
        "易胜*",
        "Sportsb**",
        "第十一家",
    ]
    assert "market_line_split" in consensus["warnings"]
    assert odds["market_policy"]["asian_handicap_consensus"].startswith("Read asian_handicap_consensus")


def test_dongqiudi_odds_index_does_not_select_price_outlier_as_preferred_asian_handicap():
    odds = odds_from_dongqiudi_odds_index(
        {
            "has_odds": True,
            "asia": [
                {
                    "name": "竞彩官方",
                    "area": "中国",
                    "now": {"homeWin": "0.84", "draw": "半球", "awayWin": "0.98", "ts": "2026-05-23 18:00"},
                    "begin": {"homeWin": "0.88", "draw": "半球", "awayWin": "0.94", "ts": "2026-05-23 12:00"},
                },
                {
                    "name": "平均值",
                    "area": "亚洲",
                    "now": {"homeWin": "0.85", "draw": "半球", "awayWin": "0.97", "ts": "2026-05-23 18:01"},
                    "begin": {"homeWin": "0.90", "draw": "半球", "awayWin": "0.92", "ts": "2026-05-23 12:00"},
                },
                {
                    "name": "易胜*",
                    "area": "英国",
                    "now": {"homeWin": "0.86", "draw": "半球", "awayWin": "0.99", "ts": "2026-05-23 17:59"},
                    "begin": {"homeWin": "0.89", "draw": "半球", "awayWin": "0.93", "ts": "2026-05-23 12:00"},
                },
                {
                    "name": "Bet3**",
                    "area": "英国",
                    "now": {"homeWin": "0.83", "draw": "半球", "awayWin": "0.96", "ts": "2026-05-23 17:58"},
                    "begin": {"homeWin": "0.88", "draw": "半球", "awayWin": "0.94", "ts": "2026-05-23 12:00"},
                },
                {
                    "name": "北单**",
                    "area": "中国",
                    "now": {"homeWin": "2.46", "draw": "半球", "awayWin": "1.68", "ts": "2026-05-23 18:02"},
                    "begin": {"homeWin": "2.20", "draw": "半球", "awayWin": "1.70", "ts": "2026-05-23 12:00"},
                },
            ],
        }
    )

    consensus = odds["asian_handicap_consensus"]
    assert odds["preferred_asian_handicap"]["provider"] == "平均值"
    assert consensus["price_consensus"]["main_line"] == -0.5
    assert consensus["price_consensus"]["median_decimal_odds"] == {
        "home_cover": 1.85,
        "away_cover": 1.97,
    }
    assert consensus["outlier_markets"][0]["provider"] == "北单**"
    assert consensus["outlier_markets"][0]["reason"] == "decimal_price_deviation_from_consensus"
    assert "price_outlier_detected" in consensus["warnings"]
    assert odds["market_intelligence"]["asian_handicap"]["side_bias"]["label"] == "主队方向"


def test_odds_quality_contract_calculates_overround_and_payout_rate():
    contract = build_odds_quality_contract(
        {
            "preferred_moneyline_1x2": {
                "provider": "竞彩官方",
                "current": {"home": 2.35, "draw": 2.85, "away": 2.85, "timestamp": "05-22 14:31"},
            }
        }
    )

    metrics = contract["preferred_moneyline_1x2"]["current_metrics"]

    assert metrics["raw_implied_probability"]["home"] == 0.425532
    assert metrics["raw_probability_sum"] == 1.127286
    assert metrics["overround"] == 0.127286
    assert metrics["payout_rate"] == 0.887086
    assert metrics["normalized_probability"]["home"] == 0.377483
    assert contract["hard_flags"] == []


def test_odds_quality_contract_keeps_price_calculation_when_source_timestamp_is_future():
    contract = build_odds_quality_contract(
        {
            "preferred_moneyline_1x2": {
                "provider": "竞彩官方",
                "current": {"home": 2.35, "draw": 2.85, "away": 2.85, "timestamp": "05-22 21:31"},
            }
        },
        source={"fetched_at_utc": "2026-05-22T06:56:27+00:00"},
    )

    assert contract["hard_flags"] == []
    assert "preferred_moneyline_current_timestamp_after_fetch" in contract["soft_flags"]
    assert "preferred_moneyline_current_future_source_timestamp" in contract["soft_flags"]
    assert contract["can_use_for_calculation"] is True
    assert contract["can_use_timestamp_for_freshness"] is False
    timestamp_quality = contract["preferred_moneyline_1x2"]["current_timestamp_quality"]
    assert timestamp_quality["quality"] == "future_inconsistent"
    assert timestamp_quality["relation_to_fetch"] == "after_fetch"
    assert timestamp_quality["seconds_from_fetch"] == 23673
    assert "use fetched_at as the observation time" in timestamp_quality["human_explanation"]
    assert contract["preferred_moneyline_1x2"]["price_observed_at_utc"] == "2026-05-22T06:56:27+00:00"


def test_odds_quality_contract_marks_totals_timestamp_missing_as_not_fresh():
    contract = build_odds_quality_contract(
        {
            "preferred_over_under": {
                "provider": "平均值",
                "current": {"over_water": 0.9, "line": 2.5, "under_water": 0.94},
            }
        }
    )

    assert contract["can_use_for_calculation"] is True
    assert "preferred_over_under_current_timestamp_missing" in contract["soft_flags"]
    assert contract["can_use_timestamp_for_freshness"] is False


def test_dongqiudi_odds_index_exposes_over_under_consensus_and_market_intelligence():
    odds = odds_from_dongqiudi_odds_index(
        {
            "has_odds": True,
            "size": [
                {
                    "name": "竞彩官方",
                    "area": "中国",
                    "now": {"homeWin": "0.92", "draw": "2.5/3", "awayWin": "0.80", "ts": "2026-05-22 20:44"},
                    "begin": {"homeWin": "0.87", "draw": "2.5", "awayWin": "0.85", "ts": "2026-05-19 17:56"},
                },
                {
                    "name": "平均值",
                    "area": "亚洲",
                    "now": {"homeWin": "0.96", "draw": "2.5/3", "awayWin": "0.82", "ts": "2026-05-22 21:32"},
                    "begin": {"homeWin": "0.90", "draw": "2.5", "awayWin": "0.83", "ts": "2026-05-18 20:41"},
                },
            ],
        }
    )

    assert odds["preferred_over_under"]["provider"] == "平均值"
    assert odds["preferred_over_under"]["current"]["line"] == 2.75
    assert odds["over_under_consensus"]["available"] is True
    assert odds["over_under_consensus"]["main_line"]["line"] == 2.75
    assert odds["over_under_consensus"]["main_line"]["market_count"] == 2
    metrics = odds["quality_contract"]["preferred_over_under"]["current_metrics"]
    assert metrics["available"] is True
    assert metrics["normalized_probability"]["over"] == 0.481481
    assert odds["market_intelligence"]["over_under"]["main_line"] == 2.75


def test_merge_odds_keeps_schedule_snapshot_but_promotes_official_market():
    schedule_snapshot = odds_from_dongqiudi_match(
        {
            "score_odds": {
                "origin": ["0.95,0.25,0.85", "2.15,3.2,3.2", "0.95,2.25,0.85"],
                "spot": ["0.95,0.25,0.85", "2.30,3.2,3.2", "0.9,2.25,0.9"],
            }
        }
    )
    official = odds_from_dongqiudi_odds_index(
        {
            "has_odds": True,
            "euro": [
                {
                    "name": "竞彩官方",
                    "area": "中国",
                    "now": {"homeWin": "2.30", "draw": "2.90", "awayWin": "2.87", "ts": "2026-05-22 11:20"},
                    "begin": {"homeWin": "2.20", "draw": "3.00", "awayWin": "2.93", "ts": "2026-05-21 18:00"},
                }
            ],
        }
    )

    merged = merge_odds(schedule_snapshot, official)

    assert merged["preferred_moneyline_1x2"]["provider"] == "竞彩官方"
    assert merged["schedule_snapshot"]["moneyline_1x2"][1]["draw"] == 3.2
    assert merged["market_policy"]["schedule_snapshot"] == "Backup only; do not mix with preferred market calculations."


def test_get_match_odds_fetches_dongqiudi_odds_index_for_best_match(monkeypatch):
    async def fake_get_best_match(*args, **kwargs):
        return (
            {
                "source_name": "dongqiudi",
                "match_id": "54346550",
                "time_window": {"in_window": True},
                "odds_summary": odds_from_dongqiudi_match(
                    {
                        "score_odds": {
                            "origin": ["", "2.15,3.2,3.2", ""],
                            "spot": ["", "2.30,3.2,3.2", ""],
                        }
                    }
                ),
            },
            {"candidate_count": 1, "time_window_policy": {"as_of_source": "server_current_time"}},
        )

    async def fake_match_context(match_id):
        assert match_id == "54346550"
        return {
            "odds_index": {
                "odds": odds_from_dongqiudi_odds_index(
                    {
                        "has_odds": True,
                        "euro": [
                            {
                                "name": "竞彩官方",
                                "area": "中国",
                                "now": {"homeWin": "2.30", "draw": "2.90", "awayWin": "2.87", "ts": "2026-05-22 11:20"},
                                "begin": {"homeWin": "2.20", "draw": "3.00", "awayWin": "2.93", "ts": "2026-05-21 18:00"},
                            }
                        ],
                    }
                )
            }
        }

    monkeypatch.setattr(server.sources, "get_best_match", fake_get_best_match)
    monkeypatch.setattr(server.sources, "dongqiudi_match_context", fake_match_context)

    result = asyncio.run(server.get_match_odds("町田泽维亚VS浦和红钻"))

    assert result["status"] == "ok"
    assert result["time_window_policy"]["as_of_source"] == "server_current_time"
    assert result["odds"]["preferred_moneyline_1x2"]["provider"] == "竞彩官方"
    assert result["odds"]["preferred_moneyline_1x2"]["current"]["draw"] == 2.90


def test_analyze_single_match_exposes_odds_quality_warnings_without_blocking_prices(monkeypatch):
    async def fake_get_best_match(*args, **kwargs):
        return (
            {
                "source_name": "dongqiudi",
                "match_id": "54346550",
                "match_score": 1.0,
                "time_window": {"in_window": True, "reason": "in_default_window"},
                "odds_summary": {"has_valid_numeric_odds": True},
            },
            {"candidate_count": 1, "time_window_policy": {"as_of_source": "server_current_time"}, "candidates": []},
        )

    async def fake_match_context(match_id):
        assert match_id == "54346550"
        return {
            "pre_analysis": {"available": True},
            "readiness": {"pre_analysis_available": True},
            "odds_index": {
                "odds": {
                    "has_valid_numeric_odds": True,
                    "quality_contract": {
                        "can_use_for_calculation": True,
                        "hard_flags": [],
                        "soft_flags": ["preferred_moneyline_current_timestamp_after_fetch"],
                    },
                }
            },
        }

    async def fake_probe_sources(*args, **kwargs):
        return {"usable_source_count": 1, "sources": [], "selection_policy": {}}

    monkeypatch.setattr(sources_module, "get_best_match", fake_get_best_match)
    monkeypatch.setattr(sources_module, "dongqiudi_match_context", fake_match_context)
    monkeypatch.setattr(sources_module, "probe_sources", fake_probe_sources)

    result = asyncio.run(sources_module.analyze_single_match("町田泽维亚VS浦和红钻"))

    assert result["quality"]["is_bettable_input"] is True
    assert result["quality"]["flags"] == []
    assert "preferred_moneyline_current_timestamp_after_fetch" in result["quality"]["warnings"]


def test_analyze_single_match_merges_leisu_context_when_dongqiudi_fields_are_empty(monkeypatch):
    async def fake_get_best_match(*args, **kwargs):
        return (
            {
                "source_name": "dongqiudi",
                "match_id": "54435613",
                "match_score": 1.0,
                "home_team": "纳萨夫",
                "away_team": "古佐尔警察",
                "league": "乌兹杯",
                "time_window": {"in_window": True, "reason": "in_default_window"},
                "odds_summary": {"has_valid_numeric_odds": True},
            },
            {"candidate_count": 1, "time_window_policy": {"as_of_source": "server_current_time"}, "candidates": []},
        )

    async def fake_dongqiudi_match_context(match_id):
        assert match_id == "54435613"
        return {
            "source_name": "dongqiudi",
            "provider": "dongqiudi",
            "match_id": match_id,
            "pre_analysis": {"available": True},
            "readiness": {"pre_analysis_available": True},
            "lineup": {
                "base": {"field": "暂无信息", "weather": "暂无信息", "referee": "暂无信息"},
                "lineup_status": {"lineup_basis": "unavailable"},
                "lineup_analysis": {"available": False, "warnings": ["lineup_unavailable"]},
            },
            "odds_index": {"odds": {"has_valid_numeric_odds": True}},
        }

    async def fake_leisu_candidate(**kwargs):
        assert kwargs["home_team"] == "纳萨夫"
        assert kwargs["away_team"] == "古佐尔警察"
        return {
            "status": "candidate_found",
            "available": True,
            "match": {"match_id": "4528570"},
        }

    async def fake_leisu_match_context(match_id):
        assert match_id == "4528570"
        return sources_module.normalize_leisu_match_context(
            match_id,
            lineup_payload={
                "venue": {"name": "纳萨夫体育场", "city": "卡尔希"},
                "referee": {},
                "home": [],
                "away": [],
            },
            detail_payload={"tlive": [{"data": "本场比赛天气情况：晴"}]},
        )

    async def fake_probe_sources(*args, **kwargs):
        return {"usable_source_count": 0, "sources": [], "selection_policy": {}}

    async def fake_get_match_data_bundle(*args, **kwargs):
        return {"status": "ok", "coverage": {"notes": ["test fixture"]}}

    monkeypatch.setenv("FOOTBALL_DATA_LEISU_CONTEXT_ENABLED", "true")
    monkeypatch.setattr(sources_module, "get_best_match", fake_get_best_match)
    monkeypatch.setattr(sources_module, "dongqiudi_match_context", fake_dongqiudi_match_context)
    monkeypatch.setattr(sources_module, "leisu_odds_candidate_for_match", fake_leisu_candidate)
    monkeypatch.setattr(sources_module, "leisu_match_context", fake_leisu_match_context)
    monkeypatch.setattr(sources_module, "probe_sources", fake_probe_sources)
    monkeypatch.setattr(sources_module, "get_match_data_bundle", fake_get_match_data_bundle)

    result = asyncio.run(
        sources_module.analyze_single_match(
            "纳萨夫 vs 古佐尔警察",
            as_of="2026-05-26T03:45:00+08:00",
            timezone_name="Asia/Shanghai",
        )
    )

    context = result["match_context"]
    assert context["source_name"] == "multi_source"
    assert context["venue"]["name"] == "纳萨夫体育场"
    assert context["weather"] == "晴"
    assert context["source_attempts"][0]["field_statuses"]["venue"] == "source_empty"
    assert context["source_attempts"][1]["provider"] == "leisu"
    assert context["source_attempts"][1]["field_statuses"]["venue"] == "available"
    assert context["source_attempts"][1]["field_statuses"]["weather"] == "available"


def test_analyze_single_match_builds_quality_contract_for_candidate_odds(monkeypatch):
    async def fake_get_best_match(*args, **kwargs):
        return (
            {
                "source_name": "sporttery",
                "source": {"source": "sporttery.cn", "fetched_at_utc": "2026-05-23T13:32:00+00:00"},
                "match_score": 1.0,
                "home_team": "拜仁",
                "away_team": "斯图加特",
                "league": "德国杯",
                "division": "sporttery:HAD",
                "kickoff_utc": "2026-05-23T18:00:00+00:00",
                "time_window": {
                    "in_window": True,
                    "reason": "in_default_window",
                    "as_of": "2026-05-23T21:32:00+08:00",
                    "kickoff": "2026-05-24T02:00:00+08:00",
                },
                "odds_summary": {
                    "has_valid_numeric_odds": True,
                    "moneyline_1x2": [
                        {
                            "provider": "Sporttery official HAD",
                            "home": 1.25,
                            "draw": 5.5,
                            "away": 6.8,
                        }
                    ],
                    "preferred_moneyline_1x2": {
                        "provider": "Sporttery official HAD",
                        "current": {"home": 1.25, "draw": 5.5, "away": 6.8, "timestamp": ""},
                        "opening": {},
                        "market_scope": "jingcai_supported",
                    },
                },
            },
            {"candidate_count": 1, "time_window_policy": {"as_of_source": "server_current_time"}, "candidates": []},
        )

    async def fake_team_form(*args, **kwargs):
        return {"available": False, "reason": "fixture_source_without_deep_form"}

    async def fake_get_match_data_bundle(*args, **kwargs):
        return {"status": "ok", "coverage": {"notes": ["test fixture"]}}

    monkeypatch.setattr(sources_module, "get_best_match", fake_get_best_match)
    monkeypatch.setattr(sources_module, "team_form", fake_team_form)
    monkeypatch.setattr(sources_module, "get_match_data_bundle", fake_get_match_data_bundle)

    result = asyncio.run(
        sources_module.analyze_single_match(
            "拜仁 vs 斯图加特",
            as_of="2026-05-23T21:32:00+08:00",
            timezone_name="Asia/Shanghai",
            include_source_probe=False,
        )
    )

    assert result["odds"]["quality_contract"]["supported_markets"]["moneyline_1x2"] is True
    assert "supported_market_missing" not in result["betting_decision_support"]["blocking_flags"]
    assert result["analysis_pack"]["data_coverage"]["blocks"]["moneyline_1x2"] is True


def test_analyze_single_match_exposes_analysis_pack_for_agents(monkeypatch):
    async def fake_get_best_match(*args, **kwargs):
        return (
            {
                "source_name": "dongqiudi",
                "match_id": "54346550",
                "match_score": 0.96,
                "home_team": "主队",
                "away_team": "客队",
                "time_window": {
                    "in_window": True,
                    "reason": "in_default_window",
                    "as_of": "2026-05-22T18:00:00+08:00",
                    "kickoff": "2026-05-22T20:00:00+08:00",
                },
                "odds_summary": {"has_valid_numeric_odds": True},
            },
            {"candidate_count": 1, "time_window_policy": {"as_of_source": "server_current_time"}, "candidates": []},
        )

    async def fake_match_context(match_id):
        return {
            "pre_analysis": sources_module.summarize_pre_analysis(
                {
                    "recent_record": {
                        "team_A": [{"score": "2-0", "color": "win", "main_team": "team_A", "tags": {"win_handicap": 1, "same_competition": 1}}],
                        "team_B": [{"score": "0-1", "color": "lose", "main_team": "team_A", "tags": {"win_handicap": 0, "same_competition": 1}}],
                    },
                    "league_table": {
                        "team_A": {"total": {"rank": "3", "points": "18", "matches_total": "8", "goals_pro": "14", "goals_against": "7"}},
                        "team_B": {"total": {"rank": "8", "points": "10", "matches_total": "8", "goals_pro": "9", "goals_against": "12"}},
                    },
                    "battle_history": {"list": [{"score": "1-0", "color": "win", "main_team": "team_A", "tags": {"win_handicap": 1}}]},
                }
            ),
            "lineup": {"available": False, "reason": "lineup_unavailable"},
            "readiness": {"pre_analysis_available": True, "lineup_available": False},
            "odds_index": {
                "odds": odds_from_dongqiudi_odds_index(
                    {
                        "has_odds": True,
                        "euro": [
                            {
                                "name": "竞彩官方",
                                "area": "中国",
                                "now": {"homeWin": "1.80", "draw": "3.50", "awayWin": "4.60", "ts": "2026-05-22 17:58"},
                                "begin": {"homeWin": "1.95", "draw": "3.40", "awayWin": "4.10", "ts": "2026-05-22 10:00"},
                            }
                        ],
                        "asia": [
                            {
                                "name": "竞彩官方",
                                "area": "中国",
                                "now": {"homeWin": "0.82", "draw": "半球", "awayWin": "1.02", "ts": "2026-05-22 17:58"},
                                "begin": {"homeWin": "0.94", "draw": "平/半", "awayWin": "0.88", "ts": "2026-05-22 10:00"},
                            }
                        ],
                        "size": [
                            {
                                "name": "竞彩官方",
                                "area": "中国",
                                "now": {"homeWin": "0.92", "draw": "2.5/3", "awayWin": "0.80", "ts": "2026-05-22 17:58"},
                                "begin": {"homeWin": "0.88", "draw": "2.5", "awayWin": "0.84", "ts": "2026-05-22 10:00"},
                            }
                        ],
                    }
                )
            },
        }

    async def fake_probe_sources(*args, **kwargs):
        return {"usable_source_count": 1, "sources": [], "selection_policy": {}}

    monkeypatch.setattr(sources_module, "get_best_match", fake_get_best_match)
    monkeypatch.setattr(sources_module, "dongqiudi_match_context", fake_match_context)
    monkeypatch.setattr(sources_module, "probe_sources", fake_probe_sources)

    result = asyncio.run(sources_module.analyze_single_match("主队 vs 客队"))

    assert list(result.keys())[:5] == ["status", "agent_brief", "final_decision", "market_candidates", "best_candidate"]
    assert result["final_decision"] == result["betting_decision_support"]["final_decision"]
    pack = result["analysis_pack"]
    assert "over_under" in pack["data_coverage"]["available_blocks"]
    assert pack["model_inputs"]["recent_form_summary"]["home"]["record"]["wins"] == 1
    assert pack["model_inputs"]["recent_form_summary"]["home"]["same_competition_sample_size"] == 1
    assert pack["model_inputs"]["league_table_summary"]["rank_delta_home_minus_away"] == -5
    assert pack["agent_brief"]["decision_contract"].startswith("Use betting_decision_support.final_execution_advice")
    assert pack["agent_brief"]["final_decision"]["headline"]
    assert pack["agent_brief"]["final_execution_advice"]["action"] in {"bet_now", "observe", "skip"}
    assert pack["agent_brief"]["market_candidates"]
    assert result["final_execution_advice"] == result["betting_decision_support"]["final_execution_advice"]
    assert result["model_card"]["probability_boundary"] == "mcp_market_anchored_scoreline_model"
    assert result["model_card"]["model_engine"]["method"] == "dixon_coles_adjusted_market_anchored_poisson_v1"
    assert result["model_card"]["model_engine"]["dixon_coles"]["low_score_adjustment"] is True
    assert result["analysis_pack"]["agent_brief"]["model_engine"]["fitted_market_targets"]
    assert result["analysis_pack"]["model_inputs"]["model_engine"]["available"] is True
    assert result["analysis_pack"]["agent_brief"]["model_engine"]["version"].startswith("football-data-mcp-model-engine")
    assert result["professional_scorecard"]["all_scores_at_least_7"] is True
    assert min(result["professional_scorecard"]["scores"].values()) >= 7
    assert result["decision_audit"]["audit_id"].startswith("football-mcp-")
    assert result["decision_audit"]["final_execution_advice"] == result["final_execution_advice"]


def test_analyze_single_match_returns_actionable_decision_support_when_data_is_calculable(monkeypatch):
    async def fake_get_best_match(*args, **kwargs):
        return (
            {
                "source_name": "dongqiudi",
                "match_id": "54346550",
                "match_score": 0.96,
                "home_team": "主队",
                "away_team": "客队",
                "time_window": {
                    "in_window": True,
                    "reason": "in_default_window",
                    "as_of": "2026-05-22T18:00:00+08:00",
                    "kickoff": "2026-05-22T20:00:00+08:00",
                },
                "odds_summary": {"has_valid_numeric_odds": True},
            },
            {"candidate_count": 1, "time_window_policy": {"as_of_source": "server_current_time"}, "candidates": []},
        )

    async def fake_match_context(match_id):
        return {
            "pre_analysis": {
                "available": True,
                "recent_record": {
                    "home": [
                        {"team_A_score": 2, "team_B_score": 0},
                        {"team_A_score": 1, "team_B_score": 0},
                        {"team_A_score": 3, "team_B_score": 1},
                    ],
                    "away": [
                        {"team_A_score": 0, "team_B_score": 2},
                        {"team_A_score": 1, "team_B_score": 2},
                        {"team_A_score": 0, "team_B_score": 1},
                    ],
                },
            },
            "lineup": {"available": False, "reason": "lineup_unavailable"},
            "readiness": {"pre_analysis_available": True, "lineup_available": False},
            "odds_index": {
                "odds": odds_from_dongqiudi_odds_index(
                    {
                        "has_odds": True,
                        "euro": [
                            {
                                "name": "竞彩官方",
                                "area": "中国",
                                "now": {"homeWin": "1.80", "draw": "3.50", "awayWin": "4.60", "ts": "2026-05-22 17:58"},
                                "begin": {"homeWin": "1.95", "draw": "3.40", "awayWin": "4.10", "ts": "2026-05-22 10:00"},
                            }
                        ],
                        "asia": [
                            {
                                "name": "竞彩官方",
                                "area": "中国",
                                "now": {"homeWin": "0.82", "draw": "半球", "awayWin": "1.02", "ts": "2026-05-22 17:58"},
                                "begin": {"homeWin": "0.94", "draw": "平/半", "awayWin": "0.88", "ts": "2026-05-22 10:00"},
                            },
                            {
                                "name": "平均值",
                                "area": "亚洲",
                                "now": {"homeWin": "0.84", "draw": "半球", "awayWin": "0.98", "ts": "2026-05-22 17:57"},
                                "begin": {"homeWin": "0.96", "draw": "平/半", "awayWin": "0.86", "ts": "2026-05-22 10:01"},
                            },
                        ],
                    }
                )
            },
        }

    async def fake_probe_sources(*args, **kwargs):
        return {"usable_source_count": 1, "sources": [], "selection_policy": {}}

    monkeypatch.setattr(sources_module, "get_best_match", fake_get_best_match)
    monkeypatch.setattr(sources_module, "dongqiudi_match_context", fake_match_context)
    monkeypatch.setattr(sources_module, "probe_sources", fake_probe_sources)

    result = asyncio.run(sources_module.analyze_single_match("主队 vs 客队"))

    support = result["betting_decision_support"]
    assert support["blocking_flags"] == []
    assert "lineup_unavailable" in support["caution_flags"]
    assert support["best_candidate"]["recommendation"] in {"immediate_bet", "condition_observe", "no_bet"}
    assert support["final_decision"]["headline"].startswith(("立即投注", "现在不下单", "不投注"))
    assert support["final_decision"]["agent_instruction"].startswith("Final agents must use this object")
    assert support["final_execution_advice"]["action"] in {"bet_now", "observe", "skip"}
    assert support["final_execution_advice"]["agent_can_override"] is False
    assert support["risk_overlay"]["severity"] in {"low", "medium"}
    assert support["decision_rule"] == "Only blocking_flags can force skip/no-bet; caution_flags are handled by MCP risk_overlay and final_execution_advice."


def test_analyze_single_match_blocks_only_real_hard_failures(monkeypatch):
    async def fake_get_best_match(*args, **kwargs):
        return (
            {
                "source_name": "dongqiudi",
                "match_id": "54346550",
                "match_score": 1.0,
                "time_window": {"in_window": True, "reason": "in_default_window"},
                "odds_summary": {"has_valid_numeric_odds": False},
            },
            {"candidate_count": 1, "time_window_policy": {"as_of_source": "server_current_time"}, "candidates": []},
        )

    async def fake_match_context(match_id):
        return {
            "pre_analysis": {"available": True},
            "lineup": {"available": False, "reason": "lineup_unavailable"},
            "readiness": {"pre_analysis_available": True},
            "odds_index": {"odds": {"has_valid_numeric_odds": False, "quality_contract": {"can_use_for_calculation": False, "hard_flags": ["supported_market_missing"], "soft_flags": []}}},
        }

    async def fake_probe_sources(*args, **kwargs):
        return {"usable_source_count": 1, "sources": [], "selection_policy": {}}

    monkeypatch.setattr(sources_module, "get_best_match", fake_get_best_match)
    monkeypatch.setattr(sources_module, "dongqiudi_match_context", fake_match_context)
    monkeypatch.setattr(sources_module, "probe_sources", fake_probe_sources)

    result = asyncio.run(sources_module.analyze_single_match("主队 vs 客队"))

    support = result["betting_decision_support"]
    assert "odds_missing" in support["blocking_flags"]
    assert support["best_candidate"]["recommendation"] == "no_bet"
    assert support["final_decision"]["headline"].startswith("不投注")


def test_decision_support_rejects_marginal_probability_edge_when_ev_is_negative():
    odds = odds_from_dongqiudi_odds_index(
        {
            "has_odds": True,
            "euro": [
                {
                    "name": "竞彩官方",
                    "area": "中国",
                    "now": {"homeWin": "2.00", "draw": "3.20", "awayWin": "3.80", "ts": "2026-05-22 17:58"},
                    "begin": {"homeWin": "2.05", "draw": "3.20", "awayWin": "3.50", "ts": "2026-05-22 10:00"},
                }
            ],
        }
    )

    support = sources_module.build_betting_decision_support(
        match={"time_window": {"as_of": "2026-05-22T18:00:00+08:00", "kickoff": "2026-05-22T20:00:00+08:00"}},
        odds=odds,
        form={"available": False},
        match_context=None,
        quality_flags=[],
        quality_warnings=[],
    )

    assert support["blocking_flags"] == []
    candidate = support["market_candidates"][0]
    assert candidate["probability_edge"] > 0
    assert candidate["expected_multiplier"] < 1
    assert candidate["edge"] < 0
    assert candidate["edge_basis"] == "expected_multiplier_minus_1"
    assert support["best_candidate"]["recommendation"] == "no_bet"


def test_decision_support_uses_expected_value_not_no_vig_probability_edge(monkeypatch):
    odds = sources_module.odds_from_sporttery_fixture(
        {
            "source": {"fetched_at_utc": "2026-05-24T05:13:18+00:00"},
            "official_odds": {"HAD": {"home": 1.80, "draw": 3.40, "away": 4.20}},
        }
    )
    odds = sources_module.with_odds_quality_contract(odds, {"fetched_at_utc": "2026-05-24T05:13:18+00:00"})

    def fake_projection(**kwargs):
        return {
            "available": True,
            "version": "test",
            "method": "test",
            "derived_probabilities": {"1x2": {"home": 0.52, "draw": 0.27, "away": 0.21}},
            "market_edges": {"1x2": {"home": 0.00927, "draw": -0.0005, "away": -0.00877}},
            "expected_goals": {"home": 1.2, "away": 1.0, "total": 2.2},
            "model_quality": {"feature_coverage": {"moneyline_1x2": True}},
            "probability_source": "test projection",
        }

    monkeypatch.setattr(sources_module.model_engine, "build_model_projection", fake_projection)

    support = sources_module.build_betting_decision_support(
        match={
            "home_team": "主队",
            "away_team": "客队",
            "time_window": {"as_of": "2026-05-24T13:00:00+08:00", "kickoff": "2026-05-24T16:00:00+08:00"},
        },
        odds=odds,
        form={"available": True},
        match_context=None,
        quality_flags=[],
        quality_warnings=[],
    )

    candidate = support["market_candidates"][0]
    assert candidate["selection"] == "主队 主胜"
    assert candidate["probability_edge"] == 0.00927
    assert candidate["expected_multiplier"] == 0.936
    assert candidate["edge"] == -0.064
    assert candidate["edge_basis"] == "expected_multiplier_minus_1"
    assert candidate["recommendation"] == "no_value"
    assert support["best_candidate"]["recommendation"] == "no_bet"


def test_sporttery_hhad_is_structured_as_official_let_goal_not_asian_handicap():
    odds = sources_module.odds_from_sporttery_fixture(
        {
            "match_num_str": "周日002",
            "source": {"fetched_at_utc": "2026-05-24T05:13:18+00:00"},
            "selling_pools": ["HAD", "HHAD"],
            "official_odds": {
                "HAD": {"home": 2.78, "draw": 2.95, "away": 2.32},
                "HHAD": {"home": 1.47, "draw": 3.80, "away": 5.37, "goal_line": 1.0},
            },
        }
    )

    assert odds["asian_handicap"] == {}
    assert odds["official_jingcai_hhad"]["market_type"] == "official_let_goal_3way"
    assert odds["official_jingcai_hhad"]["home_goal_line"] == 1.0
    assert odds["official_jingcai_hhad"]["settlement_rule"].startswith("竞彩让球胜平负")
    assert "not an Asian handicap" in odds["market_policy"]["official_jingcai_hhad"]


def test_shortlist_value_matches_filters_and_ranks_mcp_decisions(monkeypatch, tmp_path):
    async def fake_list_matches(*args, **kwargs):
        assert kwargs["window_hours"] == 1
        return {
            "status": "ok",
            "time_window_policy": {"as_of": "2026-05-23T20:00:00+08:00", "window_hours": 1},
            "matches": [
                {"home_team": "强队A", "away_team": "弱队A", "league": "测试联赛", "kickoff_utc_plus_8": "2026-05-23T20:20:00+08:00"},
                {"home_team": "强队B", "away_team": "弱队B", "league": "测试联赛", "kickoff_utc_plus_8": "2026-05-23T20:40:00+08:00"},
                {"home_team": "强队C", "away_team": "弱队C", "league": "测试联赛", "kickoff_utc_plus_8": "2026-05-23T20:50:00+08:00"},
            ],
            "total_count": 3,
        }

    analyses = {
        "强队A vs 弱队A": {
            "status": "ok",
            "agent_brief": {"match": {"home_team": "强队A", "away_team": "弱队A", "league": "测试联赛", "kickoff_utc_plus_8": "2026-05-23T20:20:00+08:00"}},
            "final_decision": {"headline": "立即投注：大小球 小球 2.5 @ 2.0，small", "recommendation": "immediate_bet"},
            "best_candidate": {"market": "over_under", "selection": "小球 2.5", "recommendation": "immediate_bet", "edge": 0.08, "stake_level": "small", "decimal_odds": 2.0},
            "market_candidates": [],
            "betting_decision_support": {"blocking_flags": [], "caution_flags": ["lineup_unavailable"], "confidence": 0.62},
            "analysis_pack": {"data_coverage": {"blocks": {"moneyline_1x2": True, "asian_handicap": True, "over_under": True, "recent_form": True, "league_table": True, "battle_history": True, "lineup": False}}},
            "quality": {"is_bettable_input": True},
        },
        "强队B vs 弱队B": {
            "status": "ok",
            "agent_brief": {"match": {"home_team": "强队B", "away_team": "弱队B", "league": "测试联赛", "kickoff_utc_plus_8": "2026-05-23T20:40:00+08:00"}},
            "final_decision": {"headline": "立即投注：亚盘 强队B -0.5 @ 1.9，small", "recommendation": "immediate_bet"},
            "best_candidate": {"market": "asian_handicap", "selection": "强队B -0.5", "recommendation": "immediate_bet", "edge": 0.12, "stake_level": "small", "decimal_odds": 1.9},
            "market_candidates": [],
            "betting_decision_support": {"blocking_flags": [], "caution_flags": [], "confidence": 0.68},
            "analysis_pack": {"data_coverage": {"blocks": {"moneyline_1x2": True, "asian_handicap": True, "over_under": True, "recent_form": True, "league_table": True, "battle_history": True, "lineup": True}}},
            "quality": {"is_bettable_input": True},
        },
        "强队C vs 弱队C": {
            "status": "ok",
            "agent_brief": {"match": {"home_team": "强队C", "away_team": "弱队C", "league": "测试联赛", "kickoff_utc_plus_8": "2026-05-23T20:50:00+08:00"}},
            "final_decision": {"headline": "不投注：supported_market_missing", "recommendation": "no_bet"},
            "best_candidate": {"market": "none", "selection": "", "recommendation": "no_bet", "edge": 0, "stake_level": "none"},
            "market_candidates": [],
            "betting_decision_support": {"blocking_flags": ["supported_market_missing"], "caution_flags": [], "confidence": 0.2},
            "analysis_pack": {"data_coverage": {"blocks": {"moneyline_1x2": False, "asian_handicap": False, "over_under": False}}},
            "quality": {"is_bettable_input": False},
        },
    }

    async def fake_analyze_single_match(query, **kwargs):
        return analyses[query]

    log_path = tmp_path / "recommendations.jsonl"
    monkeypatch.setattr(sources_module, "list_matches", fake_list_matches)
    monkeypatch.setattr(sources_module, "analyze_single_match", fake_analyze_single_match)

    result = asyncio.run(
        sources_module.shortlist_value_matches(
            as_of="2026-05-23T20:00:00+08:00",
            timezone_name="Asia/Shanghai",
            window_minutes=60,
            top_n=2,
            recommendation_log_path=str(log_path),
        )
    )

    assert result["status"] == "ok"
    assert result["window_minutes"] == 60
    assert [pick["match"]["home_team"] for pick in result["picks"]] == ["强队B", "强队A"]
    assert result["picks"][0]["value_score"] > result["picks"][1]["value_score"]
    assert result["rejected_count"] == 1
    assert result["rejected"][0]["reason"] == "blocking_flags_present"
    assert log_path.read_text(encoding="utf-8").count('"tool": "shortlist_value_matches"') == 1


def test_shortlist_confidence_mode_prefers_calibrated_probability_over_edge(monkeypatch):
    async def fake_list_matches(*args, **kwargs):
        return {
            "status": "ok",
            "time_window_policy": {"as_of": "2026-05-23T20:00:00+08:00", "window_hours": 1},
            "matches": [
                {"home_team": "高边际队", "away_team": "客队A", "league": "测试联赛", "kickoff_utc_plus_8": "2026-05-23T20:20:00+08:00"},
                {"home_team": "高置信队", "away_team": "客队B", "league": "测试联赛", "kickoff_utc_plus_8": "2026-05-23T20:40:00+08:00"},
            ],
            "total_count": 2,
        }

    analyses = {
        "高边际队 vs 客队A": {
            "status": "ok",
            "agent_brief": {"match": {"home_team": "高边际队", "away_team": "客队A", "league": "测试联赛"}},
            "final_decision": {"headline": "立即投注：高边际", "recommendation": "immediate_bet"},
            "final_execution_advice": {"headline": "最终执行：高边际", "action": "bet_now"},
            "best_candidate": {
                "market": "1x2",
                "selection": "高边际队 主胜",
                "recommendation": "immediate_bet",
                "edge": 0.12,
                "model_probability": 0.58,
                "calibrated_probability": 0.56,
                "stake_level": "small",
                "decimal_odds": 2.0,
            },
            "market_candidates": [],
            "betting_decision_support": {"blocking_flags": [], "caution_flags": [], "confidence": 0.7},
            "analysis_pack": {"data_coverage": {"blocks": {"moneyline_1x2": True, "asian_handicap": True, "over_under": True, "recent_form": True}}},
            "quality": {"is_bettable_input": True},
        },
        "高置信队 vs 客队B": {
            "status": "ok",
            "agent_brief": {"match": {"home_team": "高置信队", "away_team": "客队B", "league": "测试联赛"}},
            "final_decision": {"headline": "立即投注：高置信", "recommendation": "immediate_bet"},
            "final_execution_advice": {"headline": "最终执行：高置信", "action": "bet_now"},
            "best_candidate": {
                "market": "1x2",
                "selection": "高置信队 主胜",
                "recommendation": "immediate_bet",
                "edge": 0.02,
                "model_probability": 0.74,
                "calibrated_probability": 0.71,
                "stake_level": "small",
                "decimal_odds": 1.45,
            },
            "market_candidates": [],
            "betting_decision_support": {"blocking_flags": [], "caution_flags": ["near_kickoff_under_60m"], "confidence": 0.69},
            "analysis_pack": {"data_coverage": {"blocks": {"moneyline_1x2": True, "asian_handicap": True, "over_under": True, "recent_form": True}}},
            "quality": {"is_bettable_input": True},
        },
    }

    async def fake_analyze_single_match(query, **kwargs):
        return analyses[query]

    monkeypatch.setattr(sources_module, "list_matches", fake_list_matches)
    monkeypatch.setattr(sources_module, "analyze_single_match", fake_analyze_single_match)

    result = asyncio.run(
        sources_module.shortlist_value_matches(
            as_of="2026-05-23T20:00:00+08:00",
            timezone_name="Asia/Shanghai",
            window_minutes=60,
            top_n=2,
            mode="confidence",
        )
    )

    assert result["mode"] == "confidence"
    assert [pick["match"]["home_team"] for pick in result["picks"]] == ["高置信队", "高边际队"]
    assert result["picks"][0]["selection_confidence"]["calibrated_probability"] == 0.71
    assert "near_kickoff_under_60m" not in result["picks"][0]["selection_confidence"]["effective_caution_flags"]
    assert "calibrated_probability" in result["ranking_policy"]


def test_shortlist_defaults_to_confidence_mode(monkeypatch):
    async def fake_list_matches(*args, **kwargs):
        return {
            "status": "ok",
            "time_window_policy": {"as_of": "2026-05-23T20:00:00+08:00", "window_hours": 1},
            "matches": [
                {"home_team": "高边际队", "away_team": "客队A", "league": "测试联赛"},
                {"home_team": "高概率队", "away_team": "客队B", "league": "测试联赛"},
            ],
            "total_count": 2,
        }

    analyses = {
        "高边际队 vs 客队A": {
            "status": "ok",
            "agent_brief": {"match": {"home_team": "高边际队", "away_team": "客队A", "league": "测试联赛"}},
            "final_decision": {"headline": "立即投注：高边际", "recommendation": "immediate_bet"},
            "final_execution_advice": {"headline": "最终执行：高边际", "action": "bet_now"},
            "best_candidate": {
                "market": "1x2",
                "selection": "高边际队 主胜",
                "recommendation": "immediate_bet",
                "edge": 0.12,
                "model_probability": 0.55,
                "stake_level": "small",
                "decimal_odds": 2.0,
            },
            "market_candidates": [],
            "betting_decision_support": {"blocking_flags": [], "caution_flags": [], "confidence": 0.62},
            "analysis_pack": {"data_coverage": {"blocks": {"moneyline_1x2": True, "asian_handicap": True, "over_under": True, "recent_form": True}}},
            "quality": {"is_bettable_input": True},
        },
        "高概率队 vs 客队B": {
            "status": "ok",
            "agent_brief": {"match": {"home_team": "高概率队", "away_team": "客队B", "league": "测试联赛"}},
            "final_decision": {"headline": "立即投注：高概率", "recommendation": "immediate_bet"},
            "final_execution_advice": {"headline": "最终执行：高概率", "action": "bet_now"},
            "best_candidate": {
                "market": "1x2",
                "selection": "高概率队 主胜",
                "recommendation": "immediate_bet",
                "edge": 0.01,
                "model_probability": 0.72,
                "stake_level": "small",
                "decimal_odds": 1.45,
            },
            "market_candidates": [],
            "betting_decision_support": {"blocking_flags": [], "caution_flags": [], "confidence": 0.7},
            "analysis_pack": {"data_coverage": {"blocks": {"moneyline_1x2": True, "asian_handicap": True, "over_under": True, "recent_form": True}}},
            "quality": {"is_bettable_input": True},
        },
    }

    async def fake_analyze_single_match(query, **kwargs):
        return analyses[query]

    monkeypatch.setattr(sources_module, "list_matches", fake_list_matches)
    monkeypatch.setattr(sources_module, "analyze_single_match", fake_analyze_single_match)

    result = asyncio.run(
        sources_module.shortlist_value_matches(
            as_of="2026-05-23T20:00:00+08:00",
            timezone_name="Asia/Shanghai",
            window_minutes=60,
            top_n=2,
        )
    )

    assert result["mode"] == "confidence"
    assert [pick["match"]["home_team"] for pick in result["picks"]] == ["高概率队", "高边际队"]


def test_shortlist_confidence_mode_can_target_asian_handicap_candidates(monkeypatch):
    async def fake_list_matches(*args, **kwargs):
        assert kwargs["window_hours"] == 1
        return {
            "status": "ok",
            "time_window_policy": {"as_of": "2026-05-23T20:00:00+08:00", "window_hours": 1},
            "matches": [
                {"home_team": "主队A", "away_team": "客队A", "league": "测试联赛", "kickoff_utc_plus_8": "2026-05-23T20:20:00+08:00"},
                {"home_team": "主队B", "away_team": "客队B", "league": "测试联赛", "kickoff_utc_plus_8": "2026-05-23T20:40:00+08:00"},
            ],
            "total_count": 2,
        }

    analyses = {
        "主队A vs 客队A": {
            "status": "ok",
            "agent_brief": {"match": {"home_team": "主队A", "away_team": "客队A", "league": "测试联赛"}},
            "final_decision": {"headline": "立即投注：大小球", "recommendation": "immediate_bet"},
            "final_execution_advice": {"headline": "最终执行：大小球", "action": "bet_now"},
            "best_candidate": {
                "market": "over_under",
                "selection": "大球 2.5",
                "recommendation": "immediate_bet",
                "edge": 0.09,
                "model_probability": 0.62,
                "stake_level": "small",
                "decimal_odds": 1.8,
            },
            "market_candidates": [
                {
                    "market": "over_under",
                    "selection": "大球 2.5",
                    "recommendation": "immediate_bet",
                    "edge": 0.09,
                    "model_probability": 0.62,
                    "stake_level": "small",
                    "decimal_odds": 1.8,
                },
                {
                    "market": "asian_handicap",
                    "selection": "主队A -0.25",
                    "recommendation": "immediate_bet",
                    "edge": 0.03,
                    "model_probability": 0.57,
                    "calibrated_probability": 0.61,
                    "stake_level": "small",
                    "decimal_odds": 1.92,
                },
            ],
            "betting_decision_support": {"blocking_flags": [], "caution_flags": ["near_kickoff_under_60m"], "confidence": 0.66},
            "analysis_pack": {"data_coverage": {"blocks": {"moneyline_1x2": True, "asian_handicap": True, "over_under": True, "recent_form": True}}},
            "quality": {"is_bettable_input": True},
        },
        "主队B vs 客队B": {
            "status": "ok",
            "agent_brief": {"match": {"home_team": "主队B", "away_team": "客队B", "league": "测试联赛"}},
            "final_decision": {"headline": "立即投注：大小球", "recommendation": "immediate_bet"},
            "final_execution_advice": {"headline": "最终执行：大小球", "action": "bet_now"},
            "best_candidate": {
                "market": "over_under",
                "selection": "小球 2.25",
                "recommendation": "immediate_bet",
                "edge": 0.08,
                "model_probability": 0.6,
                "stake_level": "small",
                "decimal_odds": 1.85,
            },
            "market_candidates": [
                {
                    "market": "asian_handicap",
                    "selection": "客队B +0.5",
                    "recommendation": "condition_observe",
                    "edge": 0.02,
                    "model_probability": 0.54,
                    "calibrated_probability": 0.56,
                    "stake_level": "watch_only_until_condition",
                    "decimal_odds": 1.9,
                }
            ],
            "betting_decision_support": {"blocking_flags": [], "caution_flags": [], "confidence": 0.66},
            "analysis_pack": {"data_coverage": {"blocks": {"moneyline_1x2": True, "asian_handicap": True, "over_under": True, "recent_form": True}}},
            "quality": {"is_bettable_input": True},
        },
    }

    async def fake_analyze_single_match(query, **kwargs):
        return analyses[query]

    monkeypatch.setattr(sources_module, "list_matches", fake_list_matches)
    monkeypatch.setattr(sources_module, "analyze_single_match", fake_analyze_single_match)

    result = asyncio.run(
        sources_module.shortlist_value_matches(
            as_of="2026-05-23T20:00:00+08:00",
            timezone_name="Asia/Shanghai",
            window_minutes=60,
            top_n=2,
            mode="confidence",
            target_market="asian_handicap",
        )
    )

    assert result["target_market"] == "asian_handicap"
    assert [pick["best_candidate"]["market"] for pick in result["picks"]] == ["asian_handicap", "asian_handicap"]
    assert result["picks"][0]["best_candidate"]["selection"] == "主队A -0.25"
    assert result["picks"][0]["final_execution_advice"]["market"] == "asian_handicap"
    assert result["picks"][0]["selection_confidence"]["calibrated_probability"] == 0.61


def test_shortlist_balanced_mode_requires_confidence_and_fair_odds(monkeypatch):
    async def fake_list_matches(*args, **kwargs):
        return {
            "status": "ok",
            "time_window_policy": {"as_of": "2026-05-23T20:00:00+08:00", "window_hours": 1},
            "matches": [
                {"home_team": "低赔热门", "away_team": "客队A", "league": "测试联赛"},
                {"home_team": "概率不足", "away_team": "客队B", "league": "测试联赛"},
                {"home_team": "均衡选择", "away_team": "客队C", "league": "测试联赛"},
            ],
            "total_count": 3,
        }

    def analysis_for(home, selection, probability, odds, edge):
        return {
            "status": "ok",
            "agent_brief": {"match": {"home_team": home, "away_team": "客队", "league": "测试联赛"}},
            "final_decision": {"headline": f"立即投注：{selection}", "recommendation": "immediate_bet"},
            "final_execution_advice": {"headline": f"最终执行：{selection}", "action": "bet_now"},
            "best_candidate": {
                "market": "asian_handicap",
                "selection": selection,
                "recommendation": "immediate_bet",
                "edge": edge,
                "model_probability": probability,
                "calibrated_probability": probability,
                "stake_level": "small",
                "decimal_odds": odds,
            },
            "market_candidates": [],
            "betting_decision_support": {"blocking_flags": [], "caution_flags": ["near_kickoff_under_60m"], "confidence": 0.7},
            "analysis_pack": {"data_coverage": {"blocks": {"moneyline_1x2": True, "asian_handicap": True, "over_under": True, "recent_form": True}}},
            "quality": {"is_bettable_input": True},
        }

    analyses = {
        "低赔热门 vs 客队A": analysis_for("低赔热门", "低赔热门 -1", 0.73, 1.32, 0.02),
        "概率不足 vs 客队B": analysis_for("概率不足", "概率不足 +0.25", 0.55, 1.9, 0.03),
        "均衡选择 vs 客队C": analysis_for("均衡选择", "均衡选择 -0.25", 0.62, 1.78, 0.06),
    }

    async def fake_analyze_single_match(query, **kwargs):
        return analyses[query]

    monkeypatch.setattr(sources_module, "list_matches", fake_list_matches)
    monkeypatch.setattr(sources_module, "analyze_single_match", fake_analyze_single_match)

    result = asyncio.run(
        sources_module.shortlist_value_matches(
            as_of="2026-05-23T20:00:00+08:00",
            timezone_name="Asia/Shanghai",
            window_minutes=60,
            top_n=3,
            mode="balance",
            target_market="asian_handicap",
            min_calibrated_probability=0.58,
            min_decimal_odds=1.65,
            max_decimal_odds=2.05,
            min_value_edge=0.02,
        )
    )

    assert result["mode"] == "balanced"
    assert result["target_market"] == "asian_handicap"
    assert [pick["match"]["home_team"] for pick in result["picks"]] == ["均衡选择"]
    confidence = result["picks"][0]["selection_confidence"]
    assert confidence["fair_break_even_probability"] == 0.561798
    assert confidence["value_edge"] == 0.058202
    assert confidence["expected_return"] == 0.1036
    assert sorted(item["reason"] for item in result["rejected"]) == [
        "calibrated_probability_below_threshold",
        "decimal_odds_below_threshold",
    ]


def test_shortlist_balanced_mode_rejects_immature_high_risk_formal_picks(monkeypatch):
    async def fake_list_matches(*args, **kwargs):
        return {
            "status": "ok",
            "time_window_policy": {"as_of": "2026-05-23T20:00:00+08:00", "window_hours": 1},
            "matches": [
                {"home_team": "大盘弱队", "away_team": "客队A", "league": "测试联赛"},
                {"home_team": "缺少多公司", "away_team": "客队B", "league": "测试联赛"},
                {"home_team": "缺少阵容", "away_team": "客队C", "league": "测试联赛"},
                {"home_team": "稳妥选择", "away_team": "客队D", "league": "测试联赛"},
            ],
            "total_count": 4,
        }

    def analysis_for(
        home: str,
        selection: str,
        line: float,
        *,
        multi_bookmaker_snapshot: bool = True,
        caution_flags: list[str] | None = None,
    ) -> dict:
        return {
            "status": "ok",
            "agent_brief": {"match": {"home_team": home, "away_team": "客队", "league": "测试联赛"}},
            "final_decision": {"headline": f"立即投注：{selection}", "recommendation": "immediate_bet"},
            "final_execution_advice": {"headline": f"最终执行：{selection}", "action": "bet_now"},
            "best_candidate": {
                "market": "asian_handicap",
                "selection": selection,
                "line": line,
                "recommendation": "immediate_bet",
                "edge": 0.08,
                "model_probability": 0.62,
                "calibrated_probability": 0.62,
                "stake_level": "small",
                "decimal_odds": 1.88,
            },
            "market_candidates": [],
            "betting_decision_support": {
                "blocking_flags": [],
                "caution_flags": caution_flags or ["near_kickoff_under_60m"],
                "confidence": 0.7,
            },
            "analysis_pack": {
                "data_coverage": {
                    "blocks": {
                        "moneyline_1x2": True,
                        "asian_handicap": True,
                        "over_under": True,
                        "multi_bookmaker_snapshot": multi_bookmaker_snapshot,
                        "lineup": True,
                    }
                }
            },
            "quality": {"is_bettable_input": True},
        }

    analyses = {
        "大盘弱队 vs 客队A": analysis_for("大盘弱队", "大盘弱队 +2.5", 2.5),
        "缺少多公司 vs 客队B": analysis_for(
            "缺少多公司",
            "缺少多公司 +0.5",
            0.5,
            multi_bookmaker_snapshot=False,
        ),
        "缺少阵容 vs 客队C": analysis_for(
            "缺少阵容",
            "缺少阵容 +0.5",
            0.5,
            caution_flags=["lineup_unavailable"],
        ),
        "稳妥选择 vs 客队D": analysis_for("稳妥选择", "稳妥选择 -0.25", -0.25),
    }

    async def fake_analyze_single_match(query, **kwargs):
        return analyses[query]

    monkeypatch.setattr(sources_module, "list_matches", fake_list_matches)
    monkeypatch.setattr(sources_module, "analyze_single_match", fake_analyze_single_match)

    result = asyncio.run(
        sources_module.shortlist_value_matches(
            as_of="2026-05-23T20:00:00+08:00",
            timezone_name="Asia/Shanghai",
            window_minutes=60,
            top_n=4,
            mode="balanced",
            target_market="asian_handicap",
            min_calibrated_probability=0.58,
            min_decimal_odds=1.65,
            max_decimal_odds=2.05,
            min_value_edge=0.02,
        )
    )

    assert [pick["match"]["home_team"] for pick in result["picks"]] == ["稳妥选择"]
    assert sorted(item["reason"] for item in result["rejected"]) == [
        "large_handicap_requires_backtest",
        "lineup_context_missing",
        "multi_bookmaker_snapshot_missing",
    ]


def test_list_matches_includes_late_night_fixtures_from_previous_dongqiudi_day(monkeypatch):
    late_night_row = {
        "match_id": "late-night-1",
        "start_play": "2026-05-23 18:00:00",
        "status": "Fixture",
        "competition": {"id": "test", "name": "测试联赛", "area_name": "测试"},
        "team_A": {"name": "凌晨主队", "league_rank": ""},
        "team_B": {"name": "凌晨客队", "league_rank": ""},
        "score_odds": {
            "origin": ["0.95,0.25,0.85", "2.15,3.2,3.2", "0.95,2.25,0.85"],
            "spot": ["0.95,0.25,0.85", "2.25,3.2,3.2", "0.9,2.25,0.9"],
        },
    }
    requested_dates = []

    async def fake_load_dongqiudi_matches_for_date(local_date):
        date_key = local_date.astimezone(sources_module.DEFAULT_USER_TIMEZONE).strftime("%Y-%m-%d")
        requested_dates.append(date_key)
        source = {
            "url": f"https://example.test/{date_key}",
            "fetched_at_utc": "2026-05-23T17:42:00+00:00",
            "source": "dongqiudi.com",
        }
        return ([late_night_row] if date_key == "2026-05-23" else []), source

    async def fake_leisu_schedule_status(*args, **kwargs):
        return {"available": False, "reason": "test_disabled"}

    monkeypatch.setattr(sources_module, "load_dongqiudi_matches_for_date", fake_load_dongqiudi_matches_for_date)
    monkeypatch.setattr(sources_module, "leisu_schedule_status", fake_leisu_schedule_status)

    result = asyncio.run(
        sources_module.list_matches(
            as_of="2026-05-24T01:42:00+08:00",
            timezone_name="Asia/Shanghai",
            window_hours=1,
            analysis_ready_only=True,
        )
    )

    assert "2026-05-23" in requested_dates
    assert result["total_count"] == 1
    assert result["matches"][0]["home_team"] == "凌晨主队"
    assert result["matches"][0]["kickoff_utc_plus_8"] == "2026-05-24T02:00:00+08:00"
    assert result["matches"][0]["source"]["url"] == "https://example.test/2026-05-23"


def test_auto_learning_config_from_env_supports_background_sampling_windows(monkeypatch):
    monkeypatch.setenv("FOOTBALL_DATA_AUTO_LEARNING_INTERVAL_SECONDS", "900")
    monkeypatch.setenv("FOOTBALL_DATA_AUTO_LEARNING_TOP_N", "12")
    monkeypatch.setenv("FOOTBALL_DATA_AUTO_LEARNING_LIMIT", "80")
    monkeypatch.setenv("FOOTBALL_DATA_AUTO_LEARNING_TIMEZONE", "Asia/Shanghai")
    monkeypatch.setenv("FOOTBALL_DATA_AUTO_LEARNING_ASIAN_WINDOW_MINUTES", "1440")
    monkeypatch.setenv("FOOTBALL_DATA_AUTO_LEARNING_PARLAY_WINDOW_MINUTES", "2880")
    monkeypatch.setenv("FOOTBALL_DATA_AUTO_LEARNING_OBSERVATION_LIMIT", "40")
    monkeypatch.setenv("FOOTBALL_DATA_AUTO_LEARNING_ANALYSIS_CANDIDATE_LIMIT", "90")
    monkeypatch.setenv("FOOTBALL_DATA_AUTO_LEARNING_ANALYSIS_CONCURRENCY", "12")
    monkeypatch.setenv("FOOTBALL_DATA_AUTO_LEARNING_SHADOW_PREDICTION_LIMIT", "120")

    config = server._auto_learning_config_from_env()

    assert config["interval_seconds"] == 900
    assert config["top_n"] == 12
    assert config["limit"] == 80
    assert config["timezone_name"] == "Asia/Shanghai"
    assert config["asian_window_minutes"] == 1440
    assert config["parlay_window_minutes"] == 2880
    assert config["learning_observation_limit"] == 40
    assert config["analysis_candidate_limit"] == 90
    assert config["analysis_concurrency"] == 12
    assert config["shadow_prediction_limit"] == 120


def test_auto_learning_config_separates_prediction_window_from_snapshot_collection(monkeypatch):
    for key in [
        "FOOTBALL_DATA_AUTO_LEARNING_INTERVAL_SECONDS",
        "FOOTBALL_DATA_AUTO_LEARNING_TOP_N",
        "FOOTBALL_DATA_AUTO_LEARNING_LIMIT",
        "FOOTBALL_DATA_AUTO_LEARNING_TIMEZONE",
        "FOOTBALL_DATA_AUTO_LEARNING_ASIAN_WINDOW_MINUTES",
        "FOOTBALL_DATA_AUTO_LEARNING_PARLAY_WINDOW_MINUTES",
        "FOOTBALL_DATA_AUTO_LEARNING_SNAPSHOT_WINDOW_MINUTES",
        "FOOTBALL_DATA_AUTO_LEARNING_SNAPSHOT_LIMIT",
        "FOOTBALL_DATA_AUTO_LEARNING_OBSERVATION_LIMIT",
        "FOOTBALL_DATA_AUTO_LEARNING_ANALYSIS_CANDIDATE_LIMIT",
        "FOOTBALL_DATA_AUTO_LEARNING_ANALYSIS_CONCURRENCY",
        "FOOTBALL_DATA_AUTO_LEARNING_SHADOW_PREDICTION_LIMIT",
    ]:
        monkeypatch.delenv(key, raising=False)

    config = server._auto_learning_config_from_env()

    assert config["interval_seconds"] == 120
    assert config["top_n"] == 12
    assert config["limit"] == 80
    assert config["asian_window_minutes"] == 10
    assert config["parlay_window_minutes"] == 10
    assert config["market_snapshot_window_minutes"] == 24 * 60
    assert config["market_snapshot_limit"] == 80
    assert config["learning_observation_limit"] == 30
    assert config["analysis_candidate_limit"] == 80
    assert config["analysis_concurrency"] == 10
    assert config["shadow_prediction_limit"] == 100


def test_docker_compose_auto_learning_defaults_keep_snapshot_history_wide():
    compose_text = Path("docker-compose.yml").read_text(encoding="utf-8")

    assert "FOOTBALL_DATA_AUTO_LEARNING_INTERVAL_SECONDS:-120" in compose_text
    assert "FOOTBALL_DATA_AUTO_LEARNING_ASIAN_WINDOW_MINUTES:-10" in compose_text
    assert "FOOTBALL_DATA_AUTO_LEARNING_PARLAY_WINDOW_MINUTES:-10" in compose_text
    assert "FOOTBALL_DATA_AUTO_LEARNING_SNAPSHOT_WINDOW_MINUTES:-1440" in compose_text
    assert "FOOTBALL_DATA_AUTO_LEARNING_SNAPSHOT_LIMIT:-80" in compose_text


def test_run_auto_learning_cycle_tool_keeps_snapshot_collection_wide_by_default(monkeypatch):
    calls = []

    async def fake_run_auto_learning_cycle(**kwargs):
        calls.append(kwargs)
        return {"status": "ok", "run_id": "tool-default-window-test"}

    monkeypatch.setattr(server.sources, "run_auto_learning_cycle", fake_run_auto_learning_cycle)

    result = asyncio.run(server.run_auto_learning_cycle())

    assert result["status"] == "ok"
    assert calls[0]["asian_window_minutes"] == 10
    assert calls[0]["parlay_window_minutes"] == 10
    assert calls[0]["market_snapshot_window_minutes"] == 24 * 60


def test_shortlist_value_matches_uses_concurrent_fast_analysis_without_repeated_source_probe(monkeypatch):
    async def fake_list_matches(*args, **kwargs):
        return {
            "status": "ok",
            "time_window_policy": {"as_of": "2026-05-23T20:00:00+08:00", "window_hours": 1},
            "matches": [
                {"home_team": f"主队{i}", "away_team": f"客队{i}", "league": "测试联赛", "kickoff_utc_plus_8": "2026-05-23T20:20:00+08:00"}
                for i in range(6)
            ],
            "total_count": 6,
        }

    active = 0
    max_active = 0
    kwargs_seen = []

    async def fake_analyze_single_match(query, **kwargs):
        nonlocal active, max_active
        kwargs_seen.append(kwargs)
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0.01)
        active -= 1
        return {
            "status": "ok",
            "agent_brief": {"match": {"home_team": query.split(" vs ")[0], "away_team": query.split(" vs ")[1], "league": "测试联赛"}},
            "final_decision": {"headline": f"立即投注：{query}", "recommendation": "immediate_bet"},
            "final_execution_advice": {"headline": f"最终执行：立即投注 {query}", "action": "bet_now"},
            "best_candidate": {"market": "asian_handicap", "selection": query, "recommendation": "immediate_bet", "edge": 0.05, "stake_level": "small", "decimal_odds": 1.9},
            "market_candidates": [],
            "betting_decision_support": {"blocking_flags": [], "caution_flags": [], "confidence": 0.6},
            "analysis_pack": {"data_coverage": {"blocks": {"moneyline_1x2": True, "asian_handicap": True, "over_under": True, "recent_form": True}}},
            "quality": {"is_bettable_input": True},
        }

    monkeypatch.setattr(sources_module, "list_matches", fake_list_matches)
    monkeypatch.setattr(sources_module, "analyze_single_match", fake_analyze_single_match)

    started = time.perf_counter()
    result = asyncio.run(
        sources_module.shortlist_value_matches(
            as_of="2026-05-23T20:00:00+08:00",
            timezone_name="Asia/Shanghai",
            window_minutes=60,
            top_n=3,
            limit=6,
            recommendation_log_path="/tmp/football-data-mcp-test-fast-shortlist.jsonl",
        )
    )
    elapsed = time.perf_counter() - started

    assert result["status"] == "ok"
    assert result["analyzed_count"] == 6
    assert result["picks"][0]["final_execution_advice"]["action"] == "bet_now"
    assert max_active > 1
    assert elapsed < 0.05
    assert kwargs_seen
    assert all(kwargs.get("include_source_probe") is False for kwargs in kwargs_seen)


def test_shortlist_value_matches_default_analyzes_all_thirty_listed_candidates(monkeypatch):
    async def fake_list_matches(*args, **kwargs):
        return {
            "status": "ok",
            "time_window_policy": {"as_of": "2026-05-24T01:42:00+08:00", "window_hours": 1},
            "matches": [
                {"home_team": f"主队{i:02d}", "away_team": f"客队{i:02d}", "league": "测试联赛"}
                for i in range(30)
            ],
            "total_count": 30,
        }

    analyzed_queries = []

    async def fake_analyze_single_match(query, **kwargs):
        analyzed_queries.append(query)
        return {
            "status": "ok",
            "agent_brief": {"match": {"home_team": query.split(" vs ")[0], "away_team": query.split(" vs ")[1], "league": "测试联赛"}},
            "final_decision": {"headline": f"立即投注：{query}", "recommendation": "immediate_bet"},
            "final_execution_advice": {"headline": f"最终执行：立即投注 {query}", "action": "bet_now"},
            "best_candidate": {
                "market": "asian_handicap",
                "selection": query,
                "recommendation": "immediate_bet",
                "edge": 0.05,
                "model_probability": 0.62,
                "calibrated_probability": 0.62,
                "stake_level": "small",
                "decimal_odds": 1.9,
            },
            "market_candidates": [],
            "betting_decision_support": {"blocking_flags": [], "caution_flags": [], "confidence": 0.62},
            "analysis_pack": {"data_coverage": {"blocks": {"moneyline_1x2": True, "asian_handicap": True, "over_under": True, "recent_form": True}}},
            "quality": {"is_bettable_input": True},
        }

    monkeypatch.setattr(sources_module, "list_matches", fake_list_matches)
    monkeypatch.setattr(sources_module, "analyze_single_match", fake_analyze_single_match)

    result = asyncio.run(
        sources_module.shortlist_value_matches(
            as_of="2026-05-24T01:42:00+08:00",
            timezone_name="Asia/Shanghai",
            window_minutes=60,
            limit=30,
            mode="balance",
            target_market="asian_handicap",
        )
    )

    assert result["total_candidates"] == 30
    assert result["analysis_candidate_limit"] == 30
    assert result["analyzed_count"] == 30
    assert result["not_analyzed_count"] == 0
    assert len(analyzed_queries) == 30


def test_shortlist_value_matches_can_analyze_sixty_candidates_and_reports_funnel(monkeypatch):
    async def fake_list_matches(*args, **kwargs):
        return {
            "status": "ok",
            "time_window_policy": {"as_of": "2026-05-24T10:00:00+08:00", "window_hours": 24},
            "matches": [
                {
                    "match_id": f"wide-{i:02d}",
                    "home_team": f"扩样主队{i:02d}",
                    "away_team": f"扩样客队{i:02d}",
                    "league": "扩样联赛",
                    "kickoff_utc_plus_8": "2026-05-24T20:00:00+08:00",
                }
                for i in range(70)
            ],
            "total_count": 70,
        }

    active = 0
    max_active = 0
    analyzed_queries = []

    async def fake_analyze_single_match(query, **kwargs):
        nonlocal active, max_active
        analyzed_queries.append(query)
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0.01)
        active -= 1
        index = int(query.split("扩样主队")[1].split(" ")[0])
        recommendation = "no_value" if index % 3 == 0 else "immediate_bet"
        edge = -0.01 if recommendation == "no_value" else 0.05
        probability = 0.50 if recommendation == "no_value" else 0.62
        return {
            "status": "ok",
            "agent_brief": {
                "match": {
                    "match_id": f"wide-{index:02d}",
                    "home_team": f"扩样主队{index:02d}",
                    "away_team": f"扩样客队{index:02d}",
                    "league": "扩样联赛",
                }
            },
            "final_decision": {"headline": f"分析：{query}", "recommendation": recommendation},
            "final_execution_advice": {"headline": f"最终执行：{query}", "action": "paper_track"},
            "best_candidate": {
                "market": "asian_handicap",
                "selection": query,
                "selection_key": "home_cover",
                "line": -0.5,
                "recommendation": recommendation,
                "edge": edge,
                "model_probability": probability,
                "calibrated_probability": probability,
                "stake_level": "small",
                "decimal_odds": 1.86,
            },
            "market_candidates": [],
            "betting_decision_support": {"blocking_flags": [], "caution_flags": [], "confidence": probability},
            "analysis_pack": {
                "data_coverage": {
                    "blocks": {
                        "moneyline_1x2": True,
                        "asian_handicap": True,
                        "over_under": True,
                        "recent_form": True,
                    }
                }
            },
            "quality": {"is_bettable_input": True},
        }

    monkeypatch.setattr(sources_module, "list_matches", fake_list_matches)
    monkeypatch.setattr(sources_module, "analyze_single_match", fake_analyze_single_match)

    result = asyncio.run(
        sources_module.shortlist_value_matches(
            as_of="2026-05-24T10:00:00+08:00",
            timezone_name="Asia/Shanghai",
            window_minutes=24 * 60,
            top_n=5,
            limit=70,
            mode="balance",
            target_market="asian_handicap",
            analysis_candidate_limit=60,
            analysis_concurrency=12,
        )
    )

    assert result["analysis_candidate_limit"] == 60
    assert result["analysis_concurrency"] == 12
    assert result["analyzed_count"] == 60
    assert result["not_analyzed_count"] == 10
    assert len(analyzed_queries) == 60
    assert max_active > 8
    assert result["funnel_report"]["candidate_counts"]["eligible"] == 40
    assert result["funnel_report"]["rejection_reasons"]["no_positive_edge"] == 20


def test_shortlist_value_matches_preserves_source_match_and_context_for_dashboard(monkeypatch):
    async def fake_list_matches(*args, **kwargs):
        return {
            "status": "ok",
            "time_window_policy": {"as_of": "2026-05-25T20:50:00+08:00", "window_hours": 1},
            "matches": [
                {
                    "match_id": "dqd-ctx-1",
                    "source_name": "dongqiudi",
                    "home_team": "上下文主队",
                    "away_team": "上下文客队",
                    "league": "上下文联赛",
                    "kickoff_utc_plus_8": "2026-05-25T21:00:00+08:00",
                }
            ],
            "total_count": 1,
        }

    async def fake_analyze_single_match(query, **kwargs):
        return {
            "status": "ok",
            "agent_brief": {
                "match": {
                    "home_team": "上下文主队",
                    "away_team": "上下文客队",
                    "league": "上下文联赛",
                    "kickoff_utc_plus_8": "2026-05-25T21:00:00+08:00",
                }
            },
            "match": {
                "match_id": "dqd-ctx-1",
                "source_name": "dongqiudi",
                "home_team": "上下文主队",
                "away_team": "上下文客队",
                "league": "上下文联赛",
                "kickoff_utc_plus_8": "2026-05-25T21:00:00+08:00",
            },
            "match_context": {
                "lineup": {
                    "base": {"weather": "小雨 20C", "referee": "测试裁判"},
                    "lineup_status": {"lineup_basis": "forecast_lineups"},
                    "lineup_analysis": {"available": True, "can_use_for_analysis": True, "warnings": []},
                    "forecast_lineups": {
                        "home": {"lineup_count": 11, "lineups": [{"name": "主队前锋", "position": "F"}]},
                        "away": {"lineup_count": 11, "lineups": [{"name": "客队门将", "position": "G"}]},
                    },
                }
            },
            "best_candidate": {
                "market": "asian_handicap",
                "selection": "上下文主队 -0.5",
                "selection_key": "home_cover",
                "line": -0.5,
                "recommendation": "no_value",
                "edge": -0.01,
                "model_probability": 0.52,
                "calibrated_probability": 0.52,
                "stake_level": "none",
                "decimal_odds": 1.86,
            },
            "market_candidates": [],
            "betting_decision_support": {"blocking_flags": [], "caution_flags": [], "confidence": 0.52},
            "analysis_pack": {
                "data_coverage": {
                    "blocks": {
                        "moneyline_1x2": True,
                        "asian_handicap": True,
                        "over_under": True,
                        "recent_form": True,
                        "weather": True,
                        "referee": True,
                        "lineup": True,
                    }
                }
            },
            "quality": {"is_bettable_input": True},
        }

    monkeypatch.setattr(sources_module, "list_matches", fake_list_matches)
    monkeypatch.setattr(sources_module, "analyze_single_match", fake_analyze_single_match)

    result = asyncio.run(
        sources_module.shortlist_value_matches(
            as_of="2026-05-25T20:50:00+08:00",
            timezone_name="Asia/Shanghai",
            window_minutes=10,
            top_n=5,
            limit=1,
            mode="balanced",
            target_market="asian_handicap",
            analysis_candidate_limit=1,
        )
    )

    rejected = result["rejected"][0]
    assert rejected["match"]["match_id"] == "dqd-ctx-1"
    assert rejected["match"]["source_name"] == "dongqiudi"
    assert rejected["match_context"]["lineup"]["base"]["weather"] == "小雨 20C"
    assert rejected["match_context"]["lineup"]["base"]["referee"] == "测试裁判"


def test_recommend_jingcai_parlay_builds_2x1_ticket_from_mcp_shortlist(monkeypatch):
    async def fake_shortlist_value_matches(**kwargs):
        return {
            "status": "ok",
            "tool": "shortlist_value_matches",
            "window_minutes": kwargs["window_minutes"],
            "picks": [
                {
                    "match": {"home_team": "主队A", "away_team": "客队A", "league": "测试联赛"},
                    "final_execution_advice": {
                        "action": "bet_now",
                        "market": "1x2",
                        "market_label": "胜平负",
                        "selection": "主队A 主胜",
                        "decimal_odds": 1.80,
                        "stake_level": "small",
                    },
                    "best_candidate": {
                        "market": "1x2",
                        "selection": "主队A 主胜",
                        "decimal_odds": 1.80,
                        "model_probability": 0.62,
                        "market_probability": 0.56,
                        "edge": 0.06,
                    },
                    "confidence": 0.66,
                    "caution_flags": [],
                    "value_score": 34.2,
                },
                {
                    "match": {"home_team": "主队B", "away_team": "客队B", "league": "测试联赛"},
                    "final_execution_advice": {
                        "action": "bet_now",
                        "market": "1x2",
                        "market_label": "胜平负",
                        "selection": "客队B 客胜",
                        "decimal_odds": 1.90,
                        "stake_level": "small",
                    },
                    "best_candidate": {
                        "market": "1x2",
                        "selection": "客队B 客胜",
                        "decimal_odds": 1.90,
                        "model_probability": 0.56,
                        "market_probability": 0.51,
                        "edge": 0.05,
                    },
                    "confidence": 0.63,
                    "caution_flags": [],
                    "value_score": 31.5,
                },
            ],
        }

    monkeypatch.setattr(sources_module, "shortlist_value_matches", fake_shortlist_value_matches)

    result = asyncio.run(
        sources_module.recommend_jingcai_parlay(
            window_minutes=60,
            top_n=1,
            max_legs=2,
            include_non_official_markets=True,
        )
    )

    ticket = result["parlay_tickets"][0]
    assert result["status"] == "ok"
    assert result["eligible_leg_count"] == 2
    assert ticket["parlay_type"] == "2串1"
    assert ticket["combined_decimal_odds"] == 3.42
    assert ticket["estimated_hit_probability"] == 0.3472
    assert ticket["edge_proxy"] == 0.1874
    assert ticket["recommendation"] == "parlay_recommended"
    assert ticket["stake_level"] == "small"
    assert ticket["market_scope"] == "jingcai_supported"
    assert [leg["selection"] for leg in ticket["legs"]] == ["主队A 主胜", "客队B 客胜"]


def test_parse_sporttery_match_list_extracts_selling_had_and_hhad():
    source = {"url": "https://webapi.sporttery.cn/gateway/uniform/football/getMatchListV1.qry", "source": "sporttery.cn"}
    data = {
        "success": True,
        "value": {
            "matchInfoList": [
                {
                    "businessDate": "2026-05-23",
                    "subMatchList": [
                        {
                            "matchId": 2039907,
                            "matchNumStr": "周六013",
                            "matchStatus": "Selling",
                            "matchDate": "2026-05-24",
                            "matchTime": "00:00",
                            "leagueAbbName": "意甲",
                            "homeTeamAbbName": "博洛尼亚",
                            "awayTeamAbbName": "国际米兰",
                            "oddsList": [
                                {"poolCode": "HAD", "h": "2.95", "d": "3.50", "a": "1.98"},
                                {"poolCode": "HHAD", "h": "1.62", "d": "3.85", "a": "4.00", "goalLine": "+1.00"},
                            ],
                            "poolList": [
                                {"poolCode": "HAD", "poolStatus": "Selling"},
                                {"poolCode": "HHAD", "poolStatus": "Selling"},
                            ],
                        },
                        {
                            "matchId": 2039908,
                            "matchStatus": "Ended",
                            "matchDate": "2026-05-24",
                            "matchTime": "02:00",
                            "homeTeamAbbName": "结束主队",
                            "awayTeamAbbName": "结束客队",
                        },
                    ],
                }
            ]
        },
    }

    matches = sources_module.parse_sporttery_match_list(data, source)

    assert len(matches) == 1
    match = matches[0]
    assert match["source_name"] == "sporttery"
    assert match["match_num_str"] == "周六013"
    assert match["kickoff_utc_plus_8"] == "2026-05-24T00:00:00+08:00"
    assert match["selling_pools"] == ["HAD", "HHAD"]
    assert match["official_odds"]["HAD"]["home"] == 2.95
    assert match["official_odds"]["HHAD"]["goal_line"] == 1.0
    assert match["analysis_readiness"]["can_run_single_match_analysis"] is True


def test_recommend_jingcai_parlay_uses_official_sporttery_had_source(monkeypatch):
    official_matches = [
        {
            "source_name": "sporttery",
            "match_id": "official-1",
            "match_num_str": "周六001",
            "league": "测试联赛",
            "home_team": "主队A",
            "away_team": "客队A",
            "kickoff_utc_plus_8": "2026-05-24T20:00:00+08:00",
            "official_odds": {"HAD": {"home": 1.80, "draw": 3.40, "away": 4.20}},
            "selling_pools": ["HAD"],
        },
        {
            "source_name": "sporttery",
            "match_id": "official-2",
            "match_num_str": "周六002",
            "league": "测试联赛",
            "home_team": "主队B",
            "away_team": "客队B",
            "kickoff_utc_plus_8": "2026-05-24T21:00:00+08:00",
            "official_odds": {"HAD": {"home": 1.90, "draw": 3.30, "away": 3.80}},
            "selling_pools": ["HAD"],
        },
    ]

    async def fake_load_sporttery_official_matches(*args, **kwargs):
        return official_matches, {"url": "https://sporttery.test", "source": "sporttery.cn"}

    async def fake_analyze_single_match(query, **kwargs):
        home = query.split(" vs ")[0]
        away = query.split(" vs ")[1]
        return {
            "status": "ok",
            "agent_brief": {"match": {"home_team": home, "away_team": away, "league": "测试联赛"}},
            "betting_decision_support": {"blocking_flags": [], "caution_flags": [], "confidence": 0.66},
            "market_candidates": [
                {
                    "market": "1x2",
                    "selection": f"{home} 主胜",
                    "selection_key": "home",
                    "recommendation": "immediate_bet",
                    "edge": 0.08,
                    "decimal_odds": 1.70,
                    "market_probability": 0.52,
                    "model_probability": 0.60,
                }
            ],
            "analysis_pack": {"data_coverage": {"blocks": {"moneyline_1x2": True}}},
            "quality": {"is_bettable_input": True},
        }

    async def unexpected_shortlist_value_matches(**kwargs):
        raise AssertionError("official Jingcai parlay should not start from non-official shortlist")

    monkeypatch.setattr(sources_module, "load_sporttery_official_matches", fake_load_sporttery_official_matches)
    monkeypatch.setattr(sources_module, "analyze_single_match", fake_analyze_single_match)
    monkeypatch.setattr(sources_module, "shortlist_value_matches", unexpected_shortlist_value_matches)

    result = asyncio.run(
        sources_module.recommend_jingcai_parlay(
            as_of="2026-05-24T19:30:00+08:00",
            timezone_name="Asia/Shanghai",
            window_minutes=180,
            top_n=1,
            max_legs=2,
            include_non_official_markets=False,
        )
    )

    ticket = result["recommended_tickets"][0]
    assert result["official_jingcai_source"]["selling_count"] == 2
    assert result["official_jingcai_source"]["analyzed_count"] == 2
    assert result["eligible_leg_count"] == 2
    assert ticket["market_scope"] == "jingcai_supported"
    assert ticket["legs"][0]["market"] == "1x2"
    assert ticket["legs"][0]["official_pool"] == "HAD"
    assert ticket["legs"][0]["decimal_odds"] == 1.8
    assert ticket["recommendation"] == "parlay_recommended"


def test_recommend_jingcai_parlay_confidence_mode_allows_high_probability_low_odds_negative_ev(monkeypatch):
    official_matches = [
        {
            "source_name": "sporttery",
            "match_id": "official-low-odds-1",
            "match_num_str": "周日011",
            "league": "英超",
            "home_team": "曼城",
            "away_team": "维拉",
            "kickoff_utc_plus_8": "2026-05-24T23:00:00+08:00",
            "official_odds": {"HAD": {"home": 1.25, "draw": 5.80, "away": 8.50}},
            "selling_pools": ["HAD"],
        },
        {
            "source_name": "sporttery",
            "match_id": "official-low-odds-2",
            "match_num_str": "周日018",
            "league": "意甲",
            "home_team": "那不勒斯",
            "away_team": "乌迪内斯",
            "kickoff_utc_plus_8": "2026-05-25T00:00:00+08:00",
            "official_odds": {"HAD": {"home": 1.35, "draw": 4.40, "away": 6.60}},
            "selling_pools": ["HAD"],
        },
    ]

    async def fake_load_sporttery_official_matches(*args, **kwargs):
        return official_matches, {"url": "https://sporttery.test", "source": "sporttery.cn"}

    async def fake_analyze_single_match(query, **kwargs):
        if query.startswith("曼城"):
            probabilities = {"home": 0.74, "draw": 0.16, "away": 0.10}
        else:
            probabilities = {"home": 0.68, "draw": 0.20, "away": 0.12}
        return {
            "status": "ok",
            "agent_brief": {"match": {"home_team": query.split(" vs ")[0], "away_team": query.split(" vs ")[1], "league": "测试联赛"}},
            "betting_decision_support": {"blocking_flags": [], "caution_flags": [], "confidence": 0.68},
            "model_engine": {
                "available": True,
                "derived_probabilities": {"1x2": probabilities},
            },
            "analysis_pack": {"data_coverage": {"blocks": {"moneyline_1x2": True}}},
            "quality": {"is_bettable_input": True},
        }

    monkeypatch.setattr(sources_module, "load_sporttery_official_matches", fake_load_sporttery_official_matches)
    monkeypatch.setattr(sources_module, "analyze_single_match", fake_analyze_single_match)

    result = asyncio.run(
        sources_module.recommend_jingcai_parlay(
            as_of="2026-05-24T19:30:00+08:00",
            timezone_name="Asia/Shanghai",
            window_minutes=360,
            top_n=1,
            max_legs=2,
            parlay_mode="confidence",
            include_non_official_markets=False,
        )
    )

    ticket = result["recommended_tickets"][0]
    assert result["parlay_mode"] == "confidence"
    assert result["eligible_leg_count"] == 2
    assert ticket["recommendation"] == "parlay_recommended"
    assert ticket["parlay_mode"] == "confidence"
    assert "负EV" in result["recommendation_summary"]["headline"]
    assert ticket["confidence_mode_note"].startswith("置信模式")
    assert ticket["combined_decimal_odds"] == 1.6875
    assert ticket["edge_proxy"] < 0
    assert "confidence_mode_negative_ev_allowed" in ticket["risk_flags"]
    assert [leg["selection"] for leg in ticket["legs"]] == ["曼城 主胜", "那不勒斯 主胜"]
    assert all(leg["model_probability"] >= 0.6 for leg in ticket["legs"])
    assert all(leg["edge"] < 0 for leg in ticket["legs"])


def test_find_candidates_can_resolve_sporttery_official_fixture(monkeypatch):
    official_matches = [
        {
            "source_name": "sporttery",
            "match_id": "official-1",
            "match_num_str": "周六014",
            "league": "德国杯",
            "home_team": "拜仁",
            "away_team": "斯图加特",
            "kickoff_utc": "2026-05-23T18:00:00+00:00",
            "kickoff_utc_plus_8": "2026-05-24T02:00:00+08:00",
            "official_odds": {"HAD": {"home": 1.25, "draw": 5.50, "away": 6.80}},
            "selling_pools": ["HAD"],
            "analysis_readiness": {"can_run_single_match_analysis": True},
        }
    ]

    async def fake_load_fixtures():
        return [], {"source": "football-data.co.uk"}

    async def fake_load_dongqiudi_window(*args, **kwargs):
        return [], {"source": "dongqiudi.com"}

    async def fake_load_sporttery_official_matches(*args, **kwargs):
        return official_matches, {"source": "sporttery.cn", "url": "https://sporttery.test"}

    monkeypatch.setattr(sources_module, "load_fixtures", fake_load_fixtures)
    monkeypatch.setattr(sources_module, "load_dongqiudi_window", fake_load_dongqiudi_window)
    monkeypatch.setattr(sources_module, "load_sporttery_official_matches", fake_load_sporttery_official_matches)

    result = asyncio.run(
        sources_module.find_candidates(
            "拜仁 vs 斯图加特",
            as_of="2026-05-23T21:32:00+08:00",
            timezone_name="Asia/Shanghai",
            window_hours=24,
        )
    )

    assert result["candidate_count"] == 1
    candidate = result["candidates"][0]
    assert candidate["source_name"] == "sporttery"
    assert candidate["home_team"] == "拜仁"
    assert candidate["odds_summary"]["moneyline_1x2"][0]["provider"] == "Sporttery official HAD"


def test_recommend_jingcai_parlay_defaults_to_jingcai_day_window(monkeypatch):
    kwargs_seen = {}

    async def fake_load_sporttery_official_matches(as_of_dt, window_minutes):
        kwargs_seen["window_minutes"] = window_minutes
        return [], {"url": "https://sporttery.test", "source": "sporttery.cn"}

    monkeypatch.setattr(sources_module, "load_sporttery_official_matches", fake_load_sporttery_official_matches)

    result = asyncio.run(sources_module.recommend_jingcai_parlay())

    assert result["status"] == "ok"
    assert result["window_minutes"] == 24 * 60
    assert result["parlay_mode"] == "confidence"
    assert kwargs_seen["window_minutes"] == 24 * 60
    assert result["official_jingcai_source"]["enabled"] is True
    assert result["parlay_policy"]["default_window_rule"].startswith("Parlay uses a Jingcai day-style")
    assert "excluded by default" in result["parlay_policy"]["non_official_market_rule"]


def test_sporttery_fixture_odds_use_fetch_time_as_snapshot_timestamp():
    odds = sources_module.odds_from_sporttery_fixture(
        {
            "match_num_str": "周六014",
            "source": {"source": "sporttery.cn", "fetched_at_utc": "2026-05-23T13:32:00+00:00"},
            "official_odds": {"HAD": {"home": 1.25, "draw": 5.5, "away": 6.8}},
        }
    )

    assert odds["preferred_moneyline_1x2"]["current"]["timestamp"] == "2026-05-23T13:32:00+00:00"


def test_fetch_sporttery_match_list_uses_configured_proxy(monkeypatch):
    async def fake_fetch_text(url, headers=None):
        assert url == "http://host.docker.internal:8919/sporttery/match-list"
        return sources_module.CachedText(
            fetched_at=1_779_570_000.0,
            text='{"success": true, "value": {"matchInfoList": []}}',
            url=url,
        )

    sources_module._TEXT_CACHE.clear()
    monkeypatch.setenv("SPORTTERY_PROXY_URL", "http://host.docker.internal:8919/sporttery/match-list")
    monkeypatch.setattr(sources_module, "fetch_text", fake_fetch_text)

    data, source = asyncio.run(sources_module.fetch_sporttery_match_list())

    assert data["success"] is True
    assert source["url"] == "http://host.docker.internal:8919/sporttery/match-list"
    assert source["source"] == "sporttery.cn"


def test_sporttery_pick_rejects_negative_ev_even_when_normalized_edge_is_positive():
    fixture = {
        "source_name": "sporttery",
        "home_team": "赫塔费",
        "away_team": "奥萨苏纳",
        "official_odds": {"HAD": {"home": 2.43, "draw": 2.5, "away": 3.15}},
    }
    analysis = {
        "status": "ok",
        "confidence": 0.7,
        "betting_decision_support": {
            "blocking_flags": [],
            "caution_flags": [],
            "confidence": 0.7,
            "best_candidate": {
                "market": "1x2",
                "selection_key": "home",
                "selection": "赫塔费 主胜",
                "model_probability": 0.381817,
            },
        },
    }

    pick, reason = sources_module._sporttery_pick_from_analysis(
        fixture,
        analysis,
        min_edge=0.01,
        parlay_mode="value",
    )

    assert pick is None
    assert reason == "official_had_ev_below_threshold"


def test_recommend_jingcai_parlay_excludes_non_official_markets_by_default(monkeypatch):
    async def fake_load_sporttery_official_matches(as_of_dt, window_minutes):
        return [], {"url": "https://sporttery.test", "source": "sporttery.cn"}

    async def unexpected_shortlist_value_matches(**kwargs):
        raise AssertionError("official Jingcai mode must not use non-official shortlist")

    monkeypatch.setattr(sources_module, "load_sporttery_official_matches", fake_load_sporttery_official_matches)
    monkeypatch.setattr(sources_module, "shortlist_value_matches", unexpected_shortlist_value_matches)

    result = asyncio.run(
        sources_module.recommend_jingcai_parlay(
            window_minutes=60,
            top_n=1,
            max_legs=2,
        )
    )

    assert result["eligible_leg_count"] == 0
    assert result["parlay_tickets"] == []
    assert result["official_jingcai_source"]["enabled"] is True
    assert result["official_jingcai_source"]["selling_count"] == 0


def test_recommend_jingcai_parlay_marks_non_official_handicap_legs(monkeypatch):
    async def fake_shortlist_value_matches(**kwargs):
        return {
            "status": "ok",
            "picks": [
                {
                    "match": {"home_team": "主队A", "away_team": "客队A", "league": "测试联赛"},
                    "final_execution_advice": {
                        "action": "bet_now",
                        "market": "asian_handicap",
                        "market_label": "亚盘",
                        "selection": "主队A -0.5",
                        "decimal_odds": 1.92,
                        "stake_level": "small",
                    },
                    "best_candidate": {
                        "market": "asian_handicap",
                        "selection": "主队A -0.5",
                        "decimal_odds": 1.92,
                        "model_probability": 0.58,
                        "edge": 0.06,
                    },
                    "confidence": 0.62,
                    "caution_flags": [],
                },
                {
                    "match": {"home_team": "主队B", "away_team": "客队B", "league": "测试联赛"},
                    "final_execution_advice": {
                        "action": "bet_now",
                        "market": "over_under",
                        "market_label": "大小球",
                        "selection": "大球 2.5",
                        "decimal_odds": 1.88,
                        "stake_level": "small",
                    },
                    "best_candidate": {
                        "market": "over_under",
                        "selection": "大球 2.5",
                        "decimal_odds": 1.88,
                        "model_probability": 0.57,
                        "edge": 0.05,
                    },
                    "confidence": 0.61,
                    "caution_flags": ["near_kickoff_under_60m"],
                },
            ],
        }

    monkeypatch.setattr(sources_module, "shortlist_value_matches", fake_shortlist_value_matches)

    result = asyncio.run(
        sources_module.recommend_jingcai_parlay(
            window_minutes=60,
            top_n=1,
            max_legs=2,
            include_non_official_markets=True,
        )
    )

    ticket = result["parlay_tickets"][0]
    assert ticket["market_scope"] == "mixed_non_official"
    assert ticket["stake_level"] == "tiny"
    assert "contains_non_official_handicap_or_totals" in ticket["risk_flags"]
    assert result["parlay_policy"]["non_official_market_rule"].startswith("Asian handicap")


def test_recommend_jingcai_parlay_downgrades_deep_handicap_combo_probability(monkeypatch):
    async def fake_shortlist_value_matches(**kwargs):
        return {
            "status": "ok",
            "picks": [
                {
                    "match": {"home_team": "红崖", "away_team": "耶龙加", "league": "澳布甲"},
                    "final_execution_advice": {
                        "action": "bet_now",
                        "market": "asian_handicap",
                        "market_label": "亚盘",
                        "selection": "耶龙加 -2.75",
                        "decimal_odds": 1.75,
                        "stake_level": "small",
                        "line": -2.75,
                    },
                    "best_candidate": {
                        "market": "asian_handicap",
                        "selection": "耶龙加 -2.75",
                        "decimal_odds": 1.75,
                        "model_probability": 0.814306,
                        "market_probability": 0.520548,
                        "edge": 0.293758,
                        "line": -2.75,
                    },
                    "confidence": 0.69,
                    "caution_flags": ["lineup_unavailable", "near_kickoff_under_60m"],
                },
                {
                    "match": {"home_team": "马尼拉挖掘者", "away_team": "内湖公马", "league": "菲律宾联"},
                    "final_execution_advice": {
                        "action": "bet_now",
                        "market": "asian_handicap",
                        "market_label": "亚盘",
                        "selection": "马尼拉挖掘者 -2.5",
                        "decimal_odds": 1.85,
                        "stake_level": "small",
                        "line": -2.5,
                    },
                    "best_candidate": {
                        "market": "asian_handicap",
                        "selection": "马尼拉挖掘者 -2.5",
                        "decimal_odds": 1.85,
                        "model_probability": 0.69485,
                        "market_probability": 0.513158,
                        "edge": 0.181692,
                        "line": -2.5,
                    },
                    "confidence": 0.645,
                    "caution_flags": ["lineup_unavailable", "near_kickoff_under_60m"],
                },
            ],
        }

    monkeypatch.setattr(sources_module, "shortlist_value_matches", fake_shortlist_value_matches)

    result = asyncio.run(
        sources_module.recommend_jingcai_parlay(
            window_minutes=60,
            top_n=1,
            max_legs=2,
            include_non_official_markets=True,
        )
    )

    ticket = result["parlay_tickets"][0]
    assert ticket["recommendation"] == "single_bet_preferred"
    assert ticket["risk_level"] == "high"
    assert ticket["estimated_hit_probability"] < 0.24
    assert ticket["edge_proxy"] < 0
    assert "deep_handicap_line" in ticket["risk_flags"]
    assert "leg_probability_capped" in ticket["risk_flags"]
    assert "parlay_dependence_penalty_applied" in ticket["risk_flags"]
    assert ticket["legs"][0]["raw_model_probability"] == 0.814306
    assert ticket["legs"][0]["model_probability"] <= 0.48
    assert ticket["legs"][0]["probability_calibration"]["applied"] is True


def test_recommend_jingcai_parlay_returns_single_fallbacks_when_no_ticket_recommended(monkeypatch):
    async def fake_shortlist_value_matches(**kwargs):
        return {
            "status": "ok",
            "picks": [
                {
                    "match": {"home_team": "主队A", "away_team": "客队A", "league": "测试联赛"},
                    "final_execution_advice": {
                        "action": "bet_now",
                        "market": "asian_handicap",
                        "market_label": "亚盘",
                        "selection": "主队A -1.25",
                        "decimal_odds": 1.82,
                        "stake_level": "small",
                        "line": -1.25,
                    },
                    "best_candidate": {
                        "market": "asian_handicap",
                        "selection": "主队A -1.25",
                        "decimal_odds": 1.82,
                        "model_probability": 0.60,
                        "edge": 0.08,
                        "line": -1.25,
                    },
                    "confidence": 0.64,
                    "caution_flags": ["lineup_unavailable", "near_kickoff_under_60m"],
                },
                {
                    "match": {"home_team": "主队B", "away_team": "客队B", "league": "测试联赛"},
                    "final_execution_advice": {
                        "action": "bet_now",
                        "market": "asian_handicap",
                        "market_label": "亚盘",
                        "selection": "主队B -1.25",
                        "decimal_odds": 1.85,
                        "stake_level": "small",
                        "line": -1.25,
                    },
                    "best_candidate": {
                        "market": "asian_handicap",
                        "selection": "主队B -1.25",
                        "decimal_odds": 1.85,
                        "model_probability": 0.60,
                        "edge": 0.08,
                        "line": -1.25,
                    },
                    "confidence": 0.64,
                    "caution_flags": ["lineup_unavailable", "near_kickoff_under_60m"],
                },
            ],
        }

    monkeypatch.setattr(sources_module, "shortlist_value_matches", fake_shortlist_value_matches)

    result = asyncio.run(
        sources_module.recommend_jingcai_parlay(
            window_minutes=60,
            top_n=2,
            max_legs=2,
            include_non_official_markets=True,
        )
    )

    assert result["recommendation_summary"]["action"] == "single_bet_fallback"
    assert result["recommended_ticket_count"] == 0
    assert result["risk_candidate_ticket_count"] >= 1
    assert result["single_bet_fallbacks"]
    assert result["single_bet_fallbacks"][0]["single_expected_multiplier"] > 0
    assert result["agent_guidance"].startswith("No recommended parlay ticket")


def test_recommend_jingcai_parlay_does_not_stake_negative_single_fallback(monkeypatch):
    async def fake_shortlist_value_matches(**kwargs):
        return {
            "status": "ok",
            "picks": [
                {
                    "match": {"home_team": "主队A", "away_team": "客队A", "league": "测试联赛"},
                    "final_execution_advice": {
                        "action": "bet_now",
                        "market": "asian_handicap",
                        "market_label": "亚盘",
                        "selection": "主队A -1.25",
                        "decimal_odds": 1.82,
                        "line": -1.25,
                    },
                    "best_candidate": {
                        "market": "asian_handicap",
                        "selection": "主队A -1.25",
                        "decimal_odds": 1.82,
                        "model_probability": 0.60,
                        "line": -1.25,
                    },
                    "confidence": 0.60,
                    "caution_flags": [
                        "asian_handicap_consensus_market_line_split",
                        "over_under_consensus_total_line_split",
                        "lineup_unavailable",
                        "near_kickoff_under_60m",
                    ],
                },
                {
                    "match": {"home_team": "主队B", "away_team": "客队B", "league": "测试联赛"},
                    "final_execution_advice": {
                        "action": "bet_now",
                        "market": "asian_handicap",
                        "market_label": "亚盘",
                        "selection": "主队B -1.25",
                        "decimal_odds": 1.80,
                        "line": -1.25,
                    },
                    "best_candidate": {
                        "market": "asian_handicap",
                        "selection": "主队B -1.25",
                        "decimal_odds": 1.80,
                        "model_probability": 0.60,
                        "line": -1.25,
                    },
                    "confidence": 0.60,
                    "caution_flags": [
                        "asian_handicap_consensus_market_line_split",
                        "over_under_consensus_total_line_split",
                        "lineup_unavailable",
                        "near_kickoff_under_60m",
                    ],
                },
            ],
        }

    monkeypatch.setattr(sources_module, "shortlist_value_matches", fake_shortlist_value_matches)

    result = asyncio.run(
        sources_module.recommend_jingcai_parlay(
            window_minutes=60,
            top_n=1,
            max_legs=2,
            include_non_official_markets=True,
        )
    )

    assert result["recommendation_summary"]["action"] == "no_bettable_candidate"
    assert result["single_bet_fallbacks"][0]["stake_level"] == "none"
    assert result["single_bet_fallbacks"][0]["single_recommendation"] == "watch_only"


def test_summarize_lineup_exposes_official_starters():
    summary = summarize_lineup(
        {
            "base": {"weather": "阴", "temperature": "14°C", "field": "National Olympic Stadium"},
            "persons": {
                "team_A": {
                    "team_name": "町田泽维亚",
                    "team_coach": "黑田刚",
                    "formation_pic": "118",
                    "lineups": [
                        {
                            "person": "谷晃生",
                            "shirtnumber": "1",
                            "position": "门将",
                            "nationality_name": "日本",
                            "captain": 0,
                        }
                    ],
                    "sub": [{"person": "相马勇纪", "shirtnumber": "7", "position": "中场"}],
                },
                "team_B": {
                    "team_name": "浦和红钻",
                    "team_coach": "斯科尔扎",
                    "formation": "4-2-3-1",
                    "lineups": [
                        {
                            "person": "西川周作",
                            "shirtnumber": "1",
                            "position": "门将",
                            "nationality_name": "日本",
                            "captain": 1,
                        }
                    ],
                    "sub": [],
                },
            },
            "forecasts": {},
            "sideline": {"team_A": [], "team_B": []},
        },
        {"url": "https://example.test/lineup"},
    )

    assert summary["lineup_status"]["official_lineups_published"] is True
    assert summary["lineup_status"]["lineup_basis"] == "official_lineups"
    assert summary["official_lineups"]["home"]["team_name"] == "町田泽维亚"
    assert summary["official_lineups"]["home"]["formation"] == ""
    assert summary["official_lineups"]["home"]["formation_raw"] == "118"
    assert summary["official_lineups"]["home"]["formation_valid"] is False
    assert "raw formation code" in summary["official_lineups"]["home"]["formation_warning"]
    assert summary["official_lineups"]["home"]["lineup_count"] == 1
    assert summary["official_lineups"]["home"]["lineups"][0] == {
        "name": "谷晃生",
        "shirt_number": "1",
        "position": "门将",
        "nationality": "日本",
        "captain": False,
    }
    assert summary["official_lineups"]["away"]["formation"] == "4-2-3-1"
    assert summary["official_lineups"]["away"]["formation_raw"] == "4-2-3-1"
    assert summary["official_lineups"]["away"]["formation_valid"] is True
    assert summary["official_lineups"]["away"]["lineups"][0]["captain"] is True
    assert summary["lineup_analysis"]["available"] is True
    assert summary["lineup_analysis"]["basis"] == "official_lineups"
    assert summary["lineup_analysis"]["can_use_for_analysis"] is False
    assert summary["lineup_analysis"]["home"]["position_counts"]["门将"] == 1
    assert "home formation is an opaque source code; do not infer tactics from it" in summary["lineup_analysis"]["warnings"]
    assert "home starter count is 1, expected 11" in summary["lineup_analysis"]["warnings"]


def test_summarize_lineup_allows_complete_normalized_lineups_for_analysis():
    def players(prefix: str):
        positions = ["门将", "后卫", "后卫", "后卫", "后卫", "中场", "中场", "中场", "中场", "前锋", "前锋"]
        return [
            {
                "person": f"{prefix}{index}",
                "shirtnumber": str(index),
                "position": position,
                "nationality_name": "日本",
                "captain": 1 if index == 1 else 0,
            }
            for index, position in enumerate(positions, start=1)
        ]

    summary = summarize_lineup(
        {
            "persons": {
                "team_A": {
                    "team_name": "主队",
                    "formation": "4-4-2",
                    "lineups": players("主"),
                    "sub": [],
                },
                "team_B": {
                    "team_name": "客队",
                    "formation": "4-2-3-1",
                    "lineups": players("客"),
                    "sub": [],
                },
            },
            "forecasts": {},
        },
        {"url": "https://example.test/lineup"},
    )

    assert summary["lineup_analysis"]["basis"] == "official_lineups"
    assert summary["lineup_analysis"]["can_use_for_analysis"] is True
    assert summary["lineup_analysis"]["warnings"] == []
    assert summary["lineup_analysis"]["home"]["formation"] == "4-4-2"
    assert summary["lineup_analysis"]["home"]["position_counts"] == {
        "门将": 1,
        "后卫": 4,
        "中场": 4,
        "前锋": 2,
    }


def test_dongqiudi_match_context_exposes_source_identity(monkeypatch):
    async def fake_detail(match_id):
        return {"tabs": {}, "matchSample": {}}, {"url": "https://www.dongqiudi.com/detail"}

    async def fake_pre_analysis(match_id):
        return None, {"url": "https://www.dongqiudi.com/pre-analysis"}

    async def fake_odds_index(match_id):
        return None, {"url": "https://www.dongqiudi.com/odds"}

    async def fake_lineup(match_id):
        return {
            "base": {"field": "测试球场", "weather": "阴", "referee": "测试裁判"},
            "persons": {},
            "forecasts": {},
        }, {"url": "https://www.dongqiudi.com/lineup"}

    monkeypatch.setattr(sources_module, "load_dongqiudi_detail", fake_detail)
    monkeypatch.setattr(sources_module, "load_dongqiudi_pre_analysis", fake_pre_analysis)
    monkeypatch.setattr(sources_module, "load_dongqiudi_odds_index", fake_odds_index)
    monkeypatch.setattr(sources_module, "load_dongqiudi_lineup", fake_lineup)

    context = asyncio.run(sources_module.dongqiudi_match_context("543210"))

    assert context["source_name"] == "dongqiudi"
    assert context["provider"] == "dongqiudi"
    assert context["match_id"] == "543210"
    assert context["lineup"]["source_name"] == "dongqiudi"
    assert context["lineup"]["base"]["field"] == "测试球场"


def test_block_reason_detects_cloudflare_style_challenge():
    assert block_reason("<title>Just a moment...</title>") == "just a moment"


def test_parse_leisu_schedule_html_extracts_fixture_links():
    html = """
    <div class="box_h dd-item data">
      <div class="lier-event-name">
        <a class="event-name lang" href="https://www.leisu.com/data/zuqiu/comp-544">中乙</a>
      </div>
      <div class="lier-team-home">
        <a class="name color-666 lang" href="https://www.leisu.com/data/zuqiu/team-34684"> 大连英博B队 </a>
      </div>
      <div class="lier-score color-red">
        <a class="name color-666 lang" href="https://live.leisu.com/detail-4512919">-</a>
      </div>
      <div class="lier-team-away">
        <a class="name color-666 lang" href="https://www.leisu.com/data/zuqiu/team-45461">泰安天贶</a>
      </div>
      <div class="lier-data">
        <a class="link" href="https://live.leisu.com/shujufenxi-4512919">数据</a>
      </div>
    </div>
    """

    matches = parse_leisu_schedule_html(html)

    assert matches == [
        {
            "source_name": "leisu",
            "match_id": "4512919",
            "league": "中乙",
            "home_team": "大连英博B队",
            "away_team": "泰安天贶",
            "detail_url": "https://live.leisu.com/detail-4512919",
            "analysis_url": "https://live.leisu.com/shujufenxi-4512919",
            "odds_url": "https://odds.leisu.com/3in1-4512919",
            "kickoff_utc": None,
            "kickoff_utc_plus_8": None,
            "analysis_readiness": {
                "can_run_single_match_analysis": False,
                "grade": "corroboration_only",
                "guaranteed_inputs": {
                    "schedule": False,
                    "match_id": True,
                    "odds_snapshot": False,
                },
                "missing": ["kickoff_time_missing", "odds_missing"],
                "rule": "Leisu HTML schedule is a corroborating source unless kickoff and odds are resolved by stronger structured sources.",
            },
        }
    ]


def test_leisu_parsed_matches_override_captcha_script_false_positive():
    html = '<script src="AliyunCaptcha.js"></script><div class="dd-item data"></div>'

    assert source_block_reason("leisu_schedule", html, parsed_match_count=1) is None


def _leisu_odds_payload():
    return {
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
                "name": "澳门",
                "area": "澳门",
                "now": {"homeWin": "0.92", "draw": "平/半", "awayWin": "0.88", "ts": "2026-05-25 12:01"},
                "begin": {"homeWin": "0.96", "draw": "平手", "awayWin": "0.84", "ts": "2026-05-24 18:01"},
            },
            {
                "name": "Bet365",
                "area": "英国",
                "now": {"homeWin": "0.90", "draw": "平/半", "awayWin": "0.90", "ts": "2026-05-25 12:03"},
                "begin": {"homeWin": "0.94", "draw": "平手", "awayWin": "0.86", "ts": "2026-05-24 18:03"},
            },
        ],
        "size": [
            {
                "name": "澳门",
                "area": "澳门",
                "now": {"homeWin": "0.86", "draw": "2.5", "awayWin": "0.94", "ts": "2026-05-25 12:02"},
                "begin": {"homeWin": "0.90", "draw": "2.25", "awayWin": "0.90", "ts": "2026-05-24 18:02"},
            }
        ],
    }


def test_parse_leisu_odds_html_detects_waf_challenge():
    html = """
    <textarea id="renderData">{"l1":"var arg1='abc';","l2":"GET"}</textarea>
    <meta name="aliyun_waf_aa" content="1">
    <script>document.cookie='acw_sc__v2=test'</script>
    """

    result = parse_leisu_odds_html(html, match_id="4512919")

    assert result["available"] is False
    assert result["access"]["status"] == "waf_challenge"
    assert result["access"]["requires_cookie_or_proxy"] is True
    assert result["quality_gate"]["can_promote_to_model_input"] is False


def test_odds_from_leisu_odds_payload_builds_quality_contract_and_consensus():
    odds = odds_from_leisu_odds_payload(_leisu_odds_payload(), match_id="4512919")

    assert odds["has_valid_numeric_odds"] is True
    assert odds["source_detail"]["source"] == "leisu_odds"
    assert odds["preferred_moneyline_1x2"]["provider"] == "竞彩官方"
    assert odds["preferred_asian_handicap"]["current"]["line"] == -0.25
    assert odds["asian_handicap_consensus"]["complete_market_count"] == 2
    assert odds["preferred_over_under"]["current"]["line"] == 2.5
    assert odds["quality_contract"]["supported_markets"]["moneyline_1x2"] is True
    assert odds["quality_contract"]["supported_markets"]["asian_handicap"] is True


def test_leisu_market_snapshots_from_odds_normalizes_multi_company_time_series():
    odds = odds_from_leisu_odds_payload(_leisu_odds_payload(), match_id="4512919")

    snapshots = leisu_market_snapshots_from_odds(
        odds,
        match={
            "match_id": "4512919",
            "league": "中乙",
            "home_team": "大连英博B队",
            "away_team": "泰安天贶",
            "kickoff_utc": "2026-05-25T11:00:00+00:00",
        },
        fetched_at_utc="2026-05-25T04:05:00+00:00",
    )

    assert len(snapshots) == 9
    assert {item.provider for item in snapshots} == {"leisu"}
    assert {item.market_type for item in snapshots} == {"h2h", "asian_handicap", "over_under"}
    bet365_home = next(
        item
        for item in snapshots
        if item.bookmaker == "Bet365" and item.market_type == "asian_handicap" and item.selection == "大连英博B队"
    )
    assert bet365_home.line == -0.25
    assert bet365_home.decimal_odds == 1.9
    assert bet365_home.source_time_utc == "2026-05-25T04:03:00+00:00"
    away_cover = next(
        item
        for item in snapshots
        if item.bookmaker == "Bet365" and item.market_type == "asian_handicap" and item.selection == "泰安天贶"
    )
    assert away_cover.line == 0.25
    assert away_cover.raw["side"] == "away_cover"


def test_parse_market_timestamp_accepts_leisu_unix_seconds():
    parsed = sources_module.parse_market_timestamp_for_selection(1779707225)

    assert parsed == datetime(2026, 5, 25, 11, 7, 5, tzinfo=timezone.utc)


def test_leisu_access_status_detects_rate_limit_html():
    html = "<html><body><h1>403 Forbidden</h1><p>denied by rate limit</p></body></html>"

    status = sources_module.leisu_odds_access_status(html)

    assert status["blocked"] is True
    assert status["status"] == "blocked"
    assert status["requires_cookie_or_proxy"] is True


def test_decode_leisu_mobile_api_response_inflates_shifted_payload():
    payload = {"cids": [2], "coop": {"2": {"name": "36*", "type": 0}}, "asia": []}
    encoded = sources_module._encode_leisu_mobile_api_payload_for_test(payload, shift=14)

    decoded = sources_module.decode_leisu_mobile_api_response({"code": 114, "data": encoded})

    assert decoded == payload


def test_odds_from_leisu_mobile_payload_preserves_multi_company_history():
    mobile_payload = {
        "cids": [2],
        "coop": {"2": {"name": "36*", "type": 0}},
        "asia": [
            {
                "cid": 2,
                "f": ["0.90", "-0.5", "0.90", "0"],
                "n": [["0.95", "-0.25", "0.85", "0"], [-1, 0, 1]],
                "r": [["0.97", "-0.25", "0.82", "0"], [1, 0, -1]],
            }
        ],
        "eu": [
            {
                "cid": 2,
                "f": ["3.10", "3.30", "2.05", "0"],
                "n": [["3.20", "3.50", "2.10", "0"], [1, 1, 1]],
                "r": [["3.25", "3.50", "2.05", "0"], [1, 0, -1]],
            }
        ],
        "bs": [
            {
                "cid": 2,
                "f": ["0.88", "2.5", "0.92", "0"],
                "n": [["0.90", "2.25", "0.90", "0"], [1, -1, 1]],
                "r": [["0.92", "2.25", "0.88", "0"], [1, 0, -1]],
            }
        ],
    }
    detail_payloads = {
        "asia": {2: [[1779707225, "8", "1.00", "-0.25", "0.80", 2, "0", "0-0"]]},
        "eu": {2: [[1779707225, "8", "3.25", "3.50", "2.05", 2, "0", "0-0"]]},
        "bs": {2: [[1779707225, "8", "0.90", "2.25", "0.90", 2, "0", "0-0"]]},
    }

    odds = sources_module.odds_from_leisu_mobile_payload(
        mobile_payload,
        match_id="4523319",
        detail_payloads=detail_payloads,
    )

    assert odds["source_detail"]["source"] == "leisu_mobile_api"
    assert odds["source_detail"]["raw_market_counts"] == {"euro": 1, "asia": 1, "size": 1}
    assert odds["asian_handicap_markets"][0]["provider"] == "36*"
    assert odds["asian_handicap_markets"][0]["current"]["timestamp"] == 1779707225
    assert odds["asian_handicap_markets"][0]["history"][0]["score"] == "0-0"
    assert odds["moneyline_1x2"][0]["history"][0]["draw"] == 3.5
    assert odds["over_under_markets"][0]["history"][0]["line"] == 2.25


def test_leisu_market_snapshots_from_odds_expands_mobile_history():
    odds = sources_module.odds_from_leisu_mobile_payload(
        {
            "cids": [2],
            "coop": {"2": {"name": "36*", "type": 0}},
            "asia": [
                {
                    "cid": 2,
                    "f": ["0.90", "-0.5", "0.90", "0"],
                    "r": [["0.97", "-0.25", "0.82", "0"], [1, 0, -1]],
                }
            ],
            "eu": [],
            "bs": [],
        },
        match_id="4523319",
        detail_payloads={
            "asia": {
                2: [
                    [1779707225, "8", "1.00", "-0.25", "0.80", 2, "0", "0-0"],
                    [1779707206, "8", "0.97", "-0.25", "0.82", 2, "0", "0-0"],
                ]
            }
        },
    )

    snapshots = leisu_market_snapshots_from_odds(
        odds,
        match={
            "match_id": "4523319",
            "league": "韩K2联",
            "home_team": "城州开拓者",
            "away_team": "金浦",
            "kickoff_utc": "2026-05-25T09:30:00+00:00",
        },
        fetched_at_utc="2026-05-25T11:08:00+00:00",
    )

    assert len(snapshots) == 4
    assert {snapshot.source_time_utc for snapshot in snapshots} == {
        "2026-05-25T11:06:46+00:00",
        "2026-05-25T11:07:05+00:00",
    }
    assert {snapshot.raw["score"] for snapshot in snapshots} == {"0-0"}


def test_leisu_numeric_handicap_line_uses_moneyline_favorite_for_sign():
    odds = sources_module.odds_from_leisu_mobile_payload(
        {
            "cids": [18],
            "coop": {"18": {"name": "18**", "type": 0}},
            "eu": [
                {
                    "cid": 18,
                    "f": ["1.25", "5.00", "8.25", "0"],
                    "n": [["1.24", "5.00", "8.75", "0"], [0, 0, 0]],
                }
            ],
            "asia": [
                {
                    "cid": 18,
                    "f": ["0.73", "1.5", "0.83", "0"],
                    "n": [["0.85", "1.75", "0.71", "0"], [1, 1, -1]],
                }
            ],
            "bs": [],
        },
        match_id="4528570",
        detail_payloads={
            "asia": {
                18: [
                    [1779713762, "8", "0.73", "1.5", "0.83", 1, "0", "0-0"],
                    [1779720553, "8", "0.85", "1.75", "0.71", 1, "0", "0-0"],
                ]
            }
        },
    )

    snapshots = leisu_market_snapshots_from_odds(
        odds,
        match={
            "match_id": "4528570",
            "league": "乌兹杯",
            "home_team": "纳萨夫",
            "away_team": "休尔坦古佐",
            "kickoff_utc": "2026-05-25T19:51:00+00:00",
        },
        fetched_at_utc="2026-05-25T19:57:00+00:00",
    )

    home_lines = [
        item.line for item in snapshots
        if item.market_type == "asian_handicap" and item.selection == "纳萨夫"
    ]
    away_lines = [
        item.line for item in snapshots
        if item.market_type == "asian_handicap" and item.selection == "休尔坦古佐"
    ]
    assert home_lines == [-1.5, -1.75]
    assert away_lines == [1.5, 1.75]
    assert (odds["asian_handicap_markets"][0]["current"] or {})["line"] == -1.75
    metrics = sources_module.asian_handicap_probability_metrics(odds["preferred_asian_handicap"]["current"])
    assert metrics["home_handicap"] == -1.75


def test_normalize_leisu_match_context_extracts_venue_weather_referee_and_lineups():
    def players(prefix: str):
        return [
            {"name": f"{prefix}{index}", "shirt_number": index, "position_name": "中场"}
            for index in range(1, 12)
        ]

    context = sources_module.normalize_leisu_match_context(
        "4526729",
        lineup_payload={
            "venue": {"name": "何塞马穆德阿巴斯球场", "city": "瓦拉达里斯", "country": "Brazil"},
            "referee": {"name": "测试裁判"},
            "home": players("主"),
            "away": players("客"),
            "home_formation": "4-4-2",
            "away_formation": "4-2-3-1",
        },
        detail_payload={
            "tlive": [
                {"data": "本场比赛场地情况：良好"},
                {"data": "本场比赛天气情况：局部有云"},
            ]
        },
    )

    assert context["source_name"] == "leisu"
    assert context["venue"]["name"] == "何塞马穆德阿巴斯球场"
    assert context["weather"] == "局部有云"
    assert context["referee"]["name"] == "测试裁判"
    assert context["lineup"]["lineup_status"]["lineup_basis"] == "official_lineups"
    assert context["lineup"]["official_lineups"]["home"]["lineup_count"] == 11
    assert context["available_blocks"] == ["venue", "weather", "referee", "lineup"]


def test_merge_match_contexts_fills_source_empty_dongqiudi_fields_with_leisu():
    dongqiudi_context = {
        "source_name": "dongqiudi",
        "provider": "dongqiudi",
        "match_id": "54435613",
        "venue": "暂无信息",
        "weather": "暂无信息",
        "referee": "暂无信息",
        "lineup": {
            **summarize_lineup(
                {
                    "base": {
                        "field": "暂无信息",
                        "weather": "暂无信息",
                        "referee": "暂无信息",
                    }
                }
            ),
            "source_name": "dongqiudi",
        },
    }
    leisu_context = sources_module.normalize_leisu_match_context(
        "4528570",
        lineup_payload={
            "venue": {"name": "纳萨夫体育场"},
            "referee": {},
            "home": [],
            "away": [],
        },
        detail_payload={"tlive": [{"data": "本场比赛天气情况：晴"}]},
    )

    merged = sources_module.merge_match_contexts(dongqiudi_context, leisu_context)

    assert merged["source_name"] == "multi_source"
    assert merged["venue"]["name"] == "纳萨夫体育场"
    assert merged["weather"] == "晴"
    assert merged["referee"] == "暂无信息"
    assert merged["source_attempts"][0]["provider"] == "dongqiudi"
    assert merged["source_attempts"][0]["field_statuses"]["venue"] == "source_empty"
    assert merged["source_attempts"][1]["provider"] == "leisu"
    assert merged["source_attempts"][1]["field_statuses"]["venue"] == "available"
    assert merged["source_attempts"][1]["field_statuses"]["weather"] == "available"


def test_parse_leisu_odds_html_extracts_embedded_json_payload():
    html = f"""
    <html><body>
      <script id="leisu-odds-data" type="application/json">
        {json.dumps(_leisu_odds_payload(), ensure_ascii=False)}
      </script>
    </body></html>
    """

    result = parse_leisu_odds_html(html, match_id="4512919")

    assert result["available"] is True
    assert result["access"]["status"] == "ok"
    assert result["odds"]["preferred_moneyline_1x2"]["provider"] == "竞彩官方"
    assert result["quality_gate"]["can_promote_to_model_input"] is True


def test_fetch_leisu_odds_uses_proxy_when_configured(monkeypatch):
    calls = []

    async def fake_fetch_text(url, *, use_cache=True, headers=None):
        calls.append({"url": url, "use_cache": use_cache, "headers": headers})
        return sources_module.CachedText(
            fetched_at=time.time(),
            text=json.dumps(_leisu_odds_payload(), ensure_ascii=False),
            url=url,
        )

    monkeypatch.setenv("LEISU_ODDS_PROXY_URL", "http://127.0.0.1:8920/leisu/odds/{match_id}")
    monkeypatch.setattr(sources_module, "fetch_text", fake_fetch_text)

    result = asyncio.run(sources_module.probe_leisu_odds(match_id="4512919"))

    assert result["status"] == "ok"
    assert result["fetch"]["method"] == "proxy"
    assert calls[0]["url"] == "http://127.0.0.1:8920/leisu/odds/4512919"
    assert result["odds"]["source_detail"]["match_id"] == "4512919"


def test_probe_leisu_odds_prefers_mobile_api_when_available(monkeypatch):
    async def fake_fetch_leisu_mobile_odds_payload(**kwargs):
        return {
            "status": "ok",
            "method": "mobile_api",
            "payload": {
                "source": "leisu_mobile_api",
                "matchId": kwargs["match_id"],
                "euro": [
                    {
                        "name": "36*",
                        "area": "雷速移动端",
                        "now": {"homeWin": "3.25", "draw": "3.50", "awayWin": "2.05", "ts": 1779707225},
                        "begin": {"homeWin": "3.10", "draw": "3.30", "awayWin": "2.05", "ts": ""},
                    }
                ],
                "asia": [],
                "size": [],
            },
            "access": {"status": "ok", "blocked": False, "requires_cookie_or_proxy": False, "reason": ""},
            "source": {
                "url": "https://api-gateway.leisu.com/v1/web/match/common/odds_list",
                "source": "leisu.com",
                "fetched_at_utc": "2026-05-25T11:10:00+00:00",
            },
            "mobile_api": {"list_market_counts": {"eu": 1, "asia": 0, "bs": 0}},
        }

    monkeypatch.delenv("LEISU_ODDS_PROXY_URL", raising=False)
    monkeypatch.setattr(sources_module, "fetch_leisu_mobile_odds_payload", fake_fetch_leisu_mobile_odds_payload)

    result = asyncio.run(sources_module.probe_leisu_odds(match_id="4523319"))

    assert result["status"] == "ok"
    assert result["fetch"]["method"] == "mobile_api"
    assert result["fetch"]["mobile_api"]["list_market_counts"]["eu"] == 1
    assert result["odds"]["source_detail"]["source"] == "leisu_mobile_api"


def test_probe_leisu_odds_tool_delegates(monkeypatch):
    async def fake_probe_leisu_odds(**kwargs):
        return {"status": "ok", "match_id": kwargs["match_id"], "odds_url": kwargs["odds_url"]}

    monkeypatch.setattr(server.sources, "probe_leisu_odds", fake_probe_leisu_odds)

    result = asyncio.run(server.probe_leisu_odds(match_id="4512919", odds_url=""))

    assert result == {"status": "ok", "match_id": "4512919", "odds_url": ""}
