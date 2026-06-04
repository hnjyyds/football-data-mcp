from football_data_mcp import odds_feature_engine


def _snapshot(
    *,
    bookmaker: str,
    market_type: str,
    selection: str,
    decimal_odds: float,
    observed_at: str,
    raw_side: str,
    line: float | None = None,
) -> dict:
    return {
        "bookmaker": bookmaker,
        "market_type": market_type,
        "selection": selection,
        "decimal_odds": decimal_odds,
        "line": line,
        "source_time_utc": observed_at,
        "fetched_at_utc": observed_at,
        "raw": {"side": raw_side},
    }


def test_power_devig_removes_bookmaker_margin():
    result = odds_feature_engine.devig_probabilities(
        {"home": 1.90, "draw": 3.40, "away": 4.50},
        method="power",
    )

    assert result["status"] == "available"
    assert result["method"] == "power"
    assert result["bookmaker_margin"] > 0
    assert abs(sum(result["probabilities"].values()) - 1.0) < 0.00001
    assert result["probabilities"]["home"] < result["raw_implied_probabilities"]["home"]


def test_odds_feature_summary_extracts_no_vig_probability_and_steam_move():
    rows = [
        _snapshot(bookmaker="Bet365", market_type="h2h", selection="Arsenal", decimal_odds=2.10, observed_at="2026-05-23T08:00:00+00:00", raw_side="home"),
        _snapshot(bookmaker="Bet365", market_type="h2h", selection="Draw", decimal_odds=3.40, observed_at="2026-05-23T08:00:00+00:00", raw_side="draw"),
        _snapshot(bookmaker="Bet365", market_type="h2h", selection="Chelsea", decimal_odds=3.80, observed_at="2026-05-23T08:00:00+00:00", raw_side="away"),
        _snapshot(bookmaker="Bet365", market_type="h2h", selection="Arsenal", decimal_odds=1.88, observed_at="2026-05-23T10:00:00+00:00", raw_side="home"),
        _snapshot(bookmaker="Bet365", market_type="h2h", selection="Draw", decimal_odds=3.55, observed_at="2026-05-23T10:00:00+00:00", raw_side="draw"),
        _snapshot(bookmaker="Bet365", market_type="h2h", selection="Chelsea", decimal_odds=4.30, observed_at="2026-05-23T10:00:00+00:00", raw_side="away"),
        _snapshot(bookmaker="Pinnacle", market_type="h2h", selection="Arsenal", decimal_odds=2.08, observed_at="2026-05-23T08:05:00+00:00", raw_side="home"),
        _snapshot(bookmaker="Pinnacle", market_type="h2h", selection="Draw", decimal_odds=3.45, observed_at="2026-05-23T08:05:00+00:00", raw_side="draw"),
        _snapshot(bookmaker="Pinnacle", market_type="h2h", selection="Chelsea", decimal_odds=3.85, observed_at="2026-05-23T08:05:00+00:00", raw_side="away"),
        _snapshot(bookmaker="Pinnacle", market_type="h2h", selection="Arsenal", decimal_odds=1.94, observed_at="2026-05-23T10:05:00+00:00", raw_side="home"),
        _snapshot(bookmaker="Pinnacle", market_type="h2h", selection="Draw", decimal_odds=3.50, observed_at="2026-05-23T10:05:00+00:00", raw_side="draw"),
        _snapshot(bookmaker="Pinnacle", market_type="h2h", selection="Chelsea", decimal_odds=4.10, observed_at="2026-05-23T10:05:00+00:00", raw_side="away"),
    ]

    summary = odds_feature_engine.build_odds_feature_summary(rows, home_team="Arsenal", away_team="Chelsea")
    home = summary["markets"]["h2h"]["selections"]["home"]

    assert summary["status"] == "available"
    assert summary["markets"]["h2h"]["margin"]["status"] == "available"
    assert home["bookmaker_count"] == 2
    assert home["opening_decimal_odds"] == 2.09
    assert home["current_decimal_odds"] == 1.91
    assert home["no_vig_probability"] is not None
    assert home["devig_sample_count"] == 2
    assert home["implied_probability_delta"] > 0.04
    assert summary["key_signals"][0]["type"] == "steam_move"


def test_candidate_profile_compares_model_to_no_vig_market_and_current_price():
    odds_features = {
        "status": "available",
        "devig_method": "power",
        "markets": {
            "asian_handicap": {
                "lines": {
                    "0.250": {
                        "selections": {
                            "home_cover": {
                                "status": "available",
                                "current_decimal_odds": 1.92,
                                "best_decimal_odds": 1.98,
                                "worst_decimal_odds": 1.88,
                                "price_spread": 0.10,
                                "price_spread_pct": 0.0521,
                                "no_vig_probability": 0.505,
                                "no_vig_method": "power",
                                "bookmaker_count": 2,
                                "devig_sample_count": 2,
                                "implied_probability_delta": 0.018,
                                "line_group": "0.250",
                            }
                        }
                    }
                },
                "selections": {
                    "home_cover": {
                        "status": "available",
                        "current_decimal_odds": 1.90,
                        "best_decimal_odds": 1.96,
                        "worst_decimal_odds": 1.86,
                        "price_spread": 0.10,
                        "price_spread_pct": 0.0526,
                        "no_vig_probability": 0.515,
                        "no_vig_method": "power",
                        "bookmaker_count": 3,
                        "devig_sample_count": 3,
                        "implied_probability_delta": 0.018,
                    }
                }
            }
        },
    }

    profile = odds_feature_engine.candidate_odds_profile(
        {
            "market": "asian_handicap",
            "selection_key": "home_cover",
            "model_probability": 0.56,
            "decimal_odds": 1.94,
            "line": -0.25,
        },
        odds_features,
    )

    assert profile["status"] == "available"
    assert profile["line_group"] == "0.250"
    assert profile["no_vig_probability"] == 0.505
    assert profile["probability_edge_vs_no_vig"] == 0.055
    assert profile["expected_multiplier"] == 1.0864
    assert profile["kelly_fraction_full"] > 0
    assert profile["research_verdict"] == "positive_ev_with_market_context"
