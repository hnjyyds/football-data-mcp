from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime
from typing import Any

from football_data_mcp import model_engine, rating, sources


DEFAULT_PRICE_PREFERENCE = [
    "Average closing",
    "Average",
    "Pinnacle closing",
    "Pinnacle",
    "Bet365 closing",
    "Bet365",
    "Max closing",
    "Max",
]

DEFAULT_TOTALS_PREFERENCE = [
    "Average over/under 2.5",
    "Pinnacle over/under 2.5",
    "Bet365 over/under 2.5",
    "Max over/under 2.5",
]

DEFAULT_SWEEP_DIVISIONS = ["E0", "SP1", "I1", "D1", "F1"]
DEFAULT_SWEEP_EDGE_THRESHOLDS = [0.01, 0.02, 0.03, 0.04, 0.05]
DEFAULT_SWEEP_TRAINING_SAMPLES = [20, 40, 80, 120]


def _parse_float(value: Any) -> float | None:
    return sources.parse_float(value)


def _round(value: float | None, ndigits: int = 6) -> float | None:
    return sources.round_metric(value, ndigits)


def _completed_result(row: dict[str, str]) -> dict[str, Any] | None:
    result = str(row.get("FTR") or "").strip().upper()
    home_goals = _parse_float(row.get("FTHG"))
    away_goals = _parse_float(row.get("FTAG"))
    if result not in {"H", "D", "A"} or home_goals is None or away_goals is None:
        return None
    result_key = {"H": "home", "D": "draw", "A": "away"}[result]
    total_goals = int(home_goals + away_goals)
    return {
        "home_goals": int(home_goals),
        "away_goals": int(away_goals),
        "total_goals": total_goals,
        "result_1x2": result_key,
        "over_under_2_5": "over" if total_goals > 2.5 else "under",
    }


def _select_moneyline(row: dict[str, str]) -> dict[str, Any] | None:
    for provider in DEFAULT_PRICE_PREFERENCE:
        fields = sources.BOOKMAKER_FIELDS.get(provider)
        if not fields:
            continue
        home_key, draw_key, away_key = fields
        home = _parse_float(row.get(home_key))
        draw = _parse_float(row.get(draw_key))
        away = _parse_float(row.get(away_key))
        if all(value is not None and value > 1 for value in [home, draw, away]):
            return {
                "provider": provider,
                "current": {
                    "home": home,
                    "draw": draw,
                    "away": away,
                },
            }
    return None


def _select_over_under(row: dict[str, str]) -> dict[str, Any] | None:
    for provider in DEFAULT_TOTALS_PREFERENCE:
        fields = sources.OVER_UNDER_FIELDS.get(provider)
        if not fields:
            continue
        over_key, under_key = fields
        over = _parse_float(row.get(over_key))
        under = _parse_float(row.get(under_key))
        if all(value is not None and value > 1 for value in [over, under]):
            return {
                "provider": provider,
                "current": {
                    "line": 2.5,
                    "over_water": over,
                    "under_water": under,
                },
            }
    return None


def _select_asian_handicap(row: dict[str, str]) -> dict[str, Any] | None:
    line = _parse_float(row.get("AHh"))
    home = _parse_float(row.get("AvgAHH") or row.get("MaxAHH") or row.get("B365AHH") or row.get("PAHH"))
    away = _parse_float(row.get("AvgAHA") or row.get("MaxAHA") or row.get("B365AHA") or row.get("PAHA"))
    if line is None or not all(value is not None and value > 1 for value in [home, away]):
        return None
    return {
        "provider": "Average AH",
        "current": {
            "line": line,
            "home_water": home,
            "away_water": away,
        },
    }


def _odds_for_backtest(row: dict[str, str]) -> dict[str, Any]:
    odds: dict[str, Any] = {}
    moneyline = _select_moneyline(row)
    over_under = _select_over_under(row)
    asian = _select_asian_handicap(row)
    if moneyline:
        odds["preferred_moneyline_1x2"] = moneyline
    if over_under:
        odds["preferred_over_under"] = over_under
    if asian:
        odds["preferred_asian_handicap"] = asian
    odds["quality_contract"] = sources.build_odds_quality_contract(odds)
    return odds


def build_historical_samples(
    rows: list[dict[str, str]],
    *,
    division: str = "",
    season: str = "",
) -> list[dict[str, Any]]:
    samples = []
    for row in rows:
        kickoff = sources.parse_kickoff(row)
        actual = _completed_result(row)
        if not kickoff or not actual:
            continue
        odds = _odds_for_backtest(row)
        supported = (odds.get("quality_contract") or {}).get("supported_markets") or {}
        if not supported.get("moneyline_1x2"):
            continue
        division_code = str(row.get("Div") or division or "")
        home_team = str(row.get("HomeTeam") or "").strip()
        away_team = str(row.get("AwayTeam") or "").strip()
        if not home_team or not away_team:
            continue
        samples.append(
            {
                "id": f"{division_code}:{kickoff.date().isoformat()}:{home_team}:{away_team}",
                "division": division_code,
                "season": season,
                "match": {
                    "division": division_code,
                    "league": sources.LEAGUE_NAMES.get(division_code, division_code),
                    "home_team": home_team,
                    "away_team": away_team,
                    "kickoff_utc": kickoff.astimezone(sources.timezone.utc).isoformat(),
                    "kickoff_local": kickoff.isoformat(),
                },
                "kickoff": kickoff,
                "actual": actual,
                "odds": odds,
                "source_row": row,
            }
        )
    samples.sort(key=lambda item: item["kickoff"])
    return samples


def _team_recent_summary(samples: list[dict[str, Any]], team: str, *, limit: int = 5) -> dict[str, Any]:
    relevant = [
        sample
        for sample in samples
        if sample["match"]["home_team"] == team or sample["match"]["away_team"] == team
    ]
    relevant = relevant[-limit:]
    wins = draws = losses = goals_for = goals_against = points = 0
    matches = []
    for sample in relevant:
        is_home = sample["match"]["home_team"] == team
        actual = sample["actual"]
        gf = actual["home_goals"] if is_home else actual["away_goals"]
        ga = actual["away_goals"] if is_home else actual["home_goals"]
        goals_for += gf
        goals_against += ga
        if gf > ga:
            wins += 1
            points += 3
            result = "W"
        elif gf == ga:
            draws += 1
            points += 1
            result = "D"
        else:
            losses += 1
            result = "L"
        matches.append(
            {
                "date": sample["kickoff"].date().isoformat(),
                "home_team": sample["match"]["home_team"],
                "away_team": sample["match"]["away_team"],
                "score": f"{actual['home_goals']}-{actual['away_goals']}",
                "result_for_team": result,
            }
        )

    sample_size = len(relevant)
    return {
        "team": team,
        "sample_size": sample_size,
        "record": {"wins": wins, "draws": draws, "losses": losses},
        "points_per_match": _round(points / sample_size if sample_size else None),
        "goals_for_per_match": _round(goals_for / sample_size if sample_size else None),
        "goals_against_per_match": _round(goals_against / sample_size if sample_size else None),
        "matches": matches,
    }


def _walk_forward_form(prior_samples: list[dict[str, Any]], sample: dict[str, Any]) -> dict[str, Any]:
    home = sample["match"]["home_team"]
    away = sample["match"]["away_team"]
    return {
        "available": True,
        "recent_record_summary": {
            "home": _team_recent_summary(prior_samples, home),
            "away": _team_recent_summary(prior_samples, away),
        },
        "team_strength": {
            "rolling_elo": rating.build_pre_match_elo_context(
                prior_samples,
                home_team=home,
                away_team=away,
            )
        },
        "leakage_policy": "only matches with kickoff before this sample are used for form features",
    }


def _market_probabilities(sample: dict[str, Any]) -> dict[str, float]:
    metrics = (((sample.get("odds") or {}).get("quality_contract") or {}).get("preferred_moneyline_1x2") or {}).get("current_metrics") or {}
    return {
        key: float(value)
        for key in ("home", "draw", "away")
        if (value := _parse_float((metrics.get("normalized_probability") or {}).get(key))) is not None
    }


def _market_decimal_odds(sample: dict[str, Any]) -> dict[str, float]:
    metrics = (((sample.get("odds") or {}).get("quality_contract") or {}).get("preferred_moneyline_1x2") or {}).get("current_metrics") or {}
    return {
        key: float(value)
        for key in ("home", "draw", "away")
        if (value := _parse_float((metrics.get("odds") or {}).get(key))) is not None
    }


def _log_loss(probabilities: dict[str, float], actual: str) -> float:
    probability = max(min(probabilities.get(actual) or 0.0, 0.999999), 0.000001)
    return -math.log(probability)


def _brier_score(probabilities: dict[str, float], actual: str) -> float:
    return sum((probabilities.get(key, 0.0) - (1.0 if key == actual else 0.0)) ** 2 for key in ("home", "draw", "away"))


def _average(values: list[float]) -> float | None:
    if not values:
        return None
    return _round(sum(values) / len(values))


def _calibration(records: list[dict[str, Any]], probability_key: str) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, float]] = {}
    for record in records:
        actual = record["actual"]["result_1x2"]
        for side, probability in (record.get(probability_key) or {}).items():
            value = _parse_float(probability)
            if value is None:
                continue
            lower = min(int(value * 10) / 10, 0.9)
            label = f"{lower:.1f}-{lower + 0.1:.1f}"
            bucket = buckets.setdefault(label, {"count": 0, "predicted_sum": 0.0, "hit_sum": 0.0})
            bucket["count"] += 1
            bucket["predicted_sum"] += value
            bucket["hit_sum"] += 1.0 if side == actual else 0.0
    return [
        {
            "bucket": label,
            "count": int(bucket["count"]),
            "avg_predicted_probability": _round(bucket["predicted_sum"] / bucket["count"]),
            "observed_frequency": _round(bucket["hit_sum"] / bucket["count"]),
        }
        for label, bucket in sorted(buckets.items())
    ]


def _build_walk_forward_base(
    samples: list[dict[str, Any]],
    *,
    min_training_samples: int = 20,
    max_samples: int | None = None,
) -> dict[str, Any]:
    ordered = sorted(samples, key=lambda item: item["kickoff"])
    if max_samples:
        ordered = ordered[: max(1, int(max_samples))]

    records = []
    skipped_for_training = 0
    skipped_unavailable = 0

    for index, sample in enumerate(ordered):
        prior_samples = ordered[:index]
        if len(prior_samples) < min_training_samples:
            skipped_for_training += 1
            continue

        form = _walk_forward_form(prior_samples, sample)
        projection = model_engine.build_model_projection(
            match=sample["match"],
            odds=sample["odds"],
            form=form,
        )
        model_probs = ((projection.get("derived_probabilities") or {}).get("1x2") or {})
        market_probs = _market_probabilities(sample)
        if not projection.get("available") or not model_probs or not market_probs:
            skipped_unavailable += 1
            continue

        actual = sample["actual"]["result_1x2"]
        model_log_loss = _log_loss(model_probs, actual)
        market_log_loss = _log_loss(market_probs, actual)
        model_brier = _brier_score(model_probs, actual)
        market_brier = _brier_score(market_probs, actual)

        edges = {
            key: _round((model_probs.get(key) or 0.0) - (market_probs.get(key) or 0.0))
            for key in ("home", "draw", "away")
        }

        records.append(
            {
                "match": sample["match"],
                "training_sample_count": len(prior_samples),
                "leakage_policy": form["leakage_policy"],
                "form_summary": form["recent_record_summary"],
                "team_strength": form.get("team_strength") or {},
                "model_engine": {
                    "version": projection.get("version"),
                    "method": projection.get("method"),
                    "expected_goals": projection.get("expected_goals"),
                    "model_quality": projection.get("model_quality"),
                },
                "model_probabilities_1x2": {key: _round(_parse_float(value)) for key, value in model_probs.items()},
                "market_probabilities_1x2": {key: _round(_parse_float(value)) for key, value in market_probs.items()},
                "market_decimal_odds_1x2": _market_decimal_odds(sample),
                "edges_1x2": edges,
                "actual": sample["actual"],
                "scores": {
                    "model_log_loss_1x2": _round(model_log_loss),
                    "market_log_loss_1x2": _round(market_log_loss),
                    "model_brier_score_1x2": _round(model_brier),
                    "market_brier_score_1x2": _round(market_brier),
                },
            }
        )

    return {
        "records": records,
        "summary": {
            "sample_count": len(ordered),
            "evaluated_count": len(records),
            "skipped_for_training_count": skipped_for_training,
            "skipped_unavailable_count": skipped_unavailable,
            "min_training_samples": min_training_samples,
        },
    }


def _walk_forward_result_from_base(
    base: dict[str, Any],
    *,
    edge_threshold: float,
    stake: float,
) -> dict[str, Any]:
    model_log_losses: list[float] = []
    market_log_losses: list[float] = []
    model_briers: list[float] = []
    market_briers: list[float] = []
    bet_count = 0
    profit = 0.0
    records = []

    for base_record in base.get("records") or []:
        scores = base_record.get("scores") or {}
        model_log_losses.append(float(scores.get("model_log_loss_1x2") or 0.0))
        market_log_losses.append(float(scores.get("market_log_loss_1x2") or 0.0))
        model_briers.append(float(scores.get("model_brier_score_1x2") or 0.0))
        market_briers.append(float(scores.get("market_brier_score_1x2") or 0.0))

        edges = base_record.get("edges_1x2") or {}
        selected = max(edges, key=lambda key: edges[key] if edges[key] is not None else -999)
        selected_edge = edges.get(selected) or 0.0
        decimal_odds = (base_record.get("market_decimal_odds_1x2") or {}).get(selected)
        actual = (base_record.get("actual") or {}).get("result_1x2")
        recommended = selected_edge >= edge_threshold and decimal_odds is not None
        bet_profit = 0.0
        if recommended:
            bet_count += 1
            bet_profit = (decimal_odds - 1.0) * stake if selected == actual else -stake
            profit += bet_profit

        public_record = {
            key: value
            for key, value in base_record.items()
            if key != "market_decimal_odds_1x2"
        }
        public_record["recommendation"] = {
            "recommended": recommended,
            "selection": selected if recommended else "",
            "edge": selected_edge if recommended else 0.0,
            "decimal_odds": decimal_odds if recommended else None,
            "stake": stake if recommended else 0.0,
            "profit": _round(bet_profit),
        }
        records.append(public_record)

    summary = {
        **(base.get("summary") or {}),
        "edge_threshold": edge_threshold,
    }
    evaluated_count = len(records)
    return {
        "status": "ok",
        "summary": summary,
        "metrics": {
            "model": {
                "log_loss_1x2": _average(model_log_losses),
                "brier_score_1x2": _average(model_briers),
            },
            "market": {
                "log_loss_1x2": _average(market_log_losses),
                "brier_score_1x2": _average(market_briers),
            },
            "delta": {
                "log_loss_model_minus_market": _round((_average(model_log_losses) or 0) - (_average(market_log_losses) or 0)) if evaluated_count else None,
                "brier_model_minus_market": _round((_average(model_briers) or 0) - (_average(market_briers) or 0)) if evaluated_count else None,
            },
        },
        "betting": {
            "stake": stake,
            "bet_count": bet_count,
            "profit": _round(profit),
            "roi": _round(profit / (bet_count * stake) if bet_count and stake else None),
            "policy": "Flat stake on the largest positive 1X2 model edge above edge_threshold.",
        },
        "calibration": {
            "model_1x2": _calibration(records, "model_probabilities_1x2"),
            "market_1x2": _calibration(records, "market_probabilities_1x2"),
        },
        "records": records,
        "agent_contract": {
            "no_future_leakage_rule": "Each record uses only samples with kickoff earlier than the evaluated match for form features.",
            "profit_rule": "Profit is paper-trading flat-stake only; it is not authorization for real-money betting.",
            "interpretation_rule": "Model is useful only if walk-forward metrics and ROI beat market baseline over enough samples.",
        },
    }


def run_walk_forward_backtest(
    samples: list[dict[str, Any]],
    *,
    min_training_samples: int = 20,
    edge_threshold: float = 0.02,
    stake: float = 1.0,
    max_samples: int | None = None,
) -> dict[str, Any]:
    base = _build_walk_forward_base(
        samples,
        min_training_samples=min_training_samples,
        max_samples=max_samples,
    )
    return _walk_forward_result_from_base(
        base,
        edge_threshold=edge_threshold,
        stake=stake,
    )


async def fetch_football_data_season_rows(division: str, season: str) -> tuple[list[dict[str, str]], dict[str, Any]]:
    url = sources.SEASON_URL_TEMPLATE.format(season=season, division=division.lower())
    fetched = await sources.fetch_text(url)
    return sources.parse_csv(fetched.text), sources.evidence(fetched.url, fetched.fetched_at)


async def run_football_data_backtest(
    *,
    division: str = "E0",
    season: str = "",
    min_training_samples: int = 20,
    edge_threshold: float = 0.02,
    stake: float = 1.0,
    max_samples: int | None = None,
) -> dict[str, Any]:
    season = season or sources.season_code_for(sources.now_utc())
    rows, source = await fetch_football_data_season_rows(division, season)
    samples = build_historical_samples(rows, division=division, season=season)
    result = run_walk_forward_backtest(
        samples,
        min_training_samples=min_training_samples,
        edge_threshold=edge_threshold,
        stake=stake,
        max_samples=max_samples,
    )
    return {
        **result,
        "division": division,
        "season": season,
        "source": source,
        "league": sources.LEAGUE_NAMES.get(division, division),
        "row_count": len(rows),
    }


def _probability_bucket(probability: float, *, bucket_size: float = 0.05) -> str:
    bounded = max(0.0, min(float(probability), 0.999999))
    lower = math.floor(bounded / bucket_size) * bucket_size
    upper = min(lower + bucket_size, 1.0)
    return f"{lower:.2f}-{upper:.2f}"


def _top_probability_selection(record: dict[str, Any]) -> dict[str, Any] | None:
    probabilities = record.get("model_probabilities_1x2") or {}
    odds = record.get("market_decimal_odds_1x2") or {}
    market_probabilities = record.get("market_probabilities_1x2") or {}
    if not probabilities or not odds:
        return None
    selection = max(probabilities, key=lambda key: probabilities[key] if probabilities[key] is not None else -999)
    raw_probability = _parse_float(probabilities.get(selection))
    decimal_odds = _parse_float(odds.get(selection))
    if raw_probability is None or decimal_odds is None:
        return None
    actual = (record.get("actual") or {}).get("result_1x2")
    match = record.get("match") or {}
    kickoff = str(match.get("kickoff_local") or match.get("kickoff_utc") or "")
    return {
        "match": match,
        "date": kickoff[:10],
        "selection": selection,
        "raw_model_probability": raw_probability,
        "market_probability": _parse_float(market_probabilities.get(selection)),
        "edge": _parse_float((record.get("edges_1x2") or {}).get(selection)),
        "decimal_odds": decimal_odds,
        "actual": actual,
        "hit": selection == actual,
    }


def _build_top_selection_calibrator(
    training_records: list[dict[str, Any]],
    *,
    bucket_size: float = 0.05,
    prior_strength: int = 20,
) -> dict[str, Any]:
    selections = [
        selection
        for record in training_records
        if (selection := _top_probability_selection(record)) is not None
    ]
    hit_count = sum(1 for selection in selections if selection["hit"])
    global_hit_rate = hit_count / len(selections) if selections else 0.0
    buckets: dict[str, dict[str, Any]] = {}
    for selection in selections:
        label = _probability_bucket(selection["raw_model_probability"], bucket_size=bucket_size)
        bucket = buckets.setdefault(
            label,
            {
                "bucket": label,
                "count": 0,
                "hit_count": 0,
                "predicted_probability_sum": 0.0,
            },
        )
        bucket["count"] += 1
        bucket["hit_count"] += 1 if selection["hit"] else 0
        bucket["predicted_probability_sum"] += selection["raw_model_probability"]

    public_buckets = []
    for label, bucket in sorted(buckets.items()):
        count = int(bucket["count"])
        hit_count = int(bucket["hit_count"])
        observed = hit_count / count if count else 0.0
        calibrated = (hit_count + global_hit_rate * prior_strength) / (count + prior_strength) if count else global_hit_rate
        bucket.update(
            {
                "observed_hit_rate": _round(observed),
                "avg_predicted_probability": _round(bucket["predicted_probability_sum"] / count if count else None),
                "calibrated_probability": _round(calibrated),
            }
        )
        public_buckets.append(bucket)

    return {
        "method": "empirical_top_selection_probability_bins_v1",
        "bucket_size": bucket_size,
        "prior_strength": prior_strength,
        "training_record_count": len(selections),
        "global_hit_rate": _round(global_hit_rate),
        "buckets": public_buckets,
        "bucket_map": {bucket["bucket"]: bucket for bucket in public_buckets},
    }


def _apply_top_selection_calibrator(
    selection: dict[str, Any],
    calibrator: dict[str, Any],
) -> dict[str, Any]:
    label = _probability_bucket(
        selection["raw_model_probability"],
        bucket_size=float(calibrator.get("bucket_size") or 0.05),
    )
    bucket = (calibrator.get("bucket_map") or {}).get(label) or {}
    calibrated = _parse_float(bucket.get("calibrated_probability"))
    if calibrated is None:
        calibrated = _parse_float(calibrator.get("global_hit_rate"))
    if calibrated is None:
        calibrated = selection["raw_model_probability"]
    return {
        **selection,
        "calibrated_probability": _round(calibrated),
        "calibration_bucket": {
            "bucket": label,
            "count": int(bucket.get("count") or 0),
            "observed_hit_rate": bucket.get("observed_hit_rate"),
            "avg_predicted_probability": bucket.get("avg_predicted_probability"),
        },
    }


def _top_k_confidence_metrics(
    selections: list[dict[str, Any]],
    *,
    top_k: int,
    min_calibrated_probability: float,
    stake: float,
) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for selection in selections:
        calibrated = _parse_float(selection.get("calibrated_probability"))
        if calibrated is None or calibrated < min_calibrated_probability:
            continue
        grouped[str(selection.get("date") or "")].append(selection)

    selected: list[dict[str, Any]] = []
    for rows in grouped.values():
        selected.extend(
            sorted(
                rows,
                key=lambda item: (
                    _parse_float(item.get("calibrated_probability")) or 0.0,
                    _parse_float(item.get("raw_model_probability")) or 0.0,
                    _parse_float(item.get("edge")) or -999.0,
                ),
                reverse=True,
            )[: max(1, int(top_k))]
        )

    bet_count = len(selected)
    hits = sum(1 for item in selected if item.get("hit"))
    profit = sum(
        ((float(item["decimal_odds"]) - 1.0) * stake if item.get("hit") else -stake)
        for item in selected
    )
    avg_calibrated = _average([float(item.get("calibrated_probability") or 0.0) for item in selected])
    hit_rate = _round(hits / bet_count if bet_count else None)
    return {
        "selection_mode": "calibrated_confidence",
        "top_k": int(top_k),
        "min_calibrated_probability": float(min_calibrated_probability),
        "bet_count": bet_count,
        "hit_count": hits,
        "hit_rate": hit_rate,
        "avg_decimal_odds": _average([float(item.get("decimal_odds") or 0.0) for item in selected]),
        "avg_raw_model_probability": _average([float(item.get("raw_model_probability") or 0.0) for item in selected]),
        "avg_calibrated_probability": avg_calibrated,
        "avg_market_probability": _average([
            float(item["market_probability"])
            for item in selected
            if item.get("market_probability") is not None
        ]),
        "avg_edge": _average([
            float(item["edge"])
            for item in selected
            if item.get("edge") is not None
        ]),
        "profit": _round(profit),
        "roi": _round(profit / (bet_count * stake) if bet_count and stake else None),
        "calibration_error": _round(abs((hit_rate or 0.0) - (avg_calibrated or 0.0)) if bet_count else None),
        "selection_policy": "For each validation date, rank all available matches by calibrated_probability and keep Top K.",
    }


async def run_top_k_confidence_backtest(
    *,
    divisions: list[str] | None = None,
    training_seasons: list[str] | None = None,
    validation_seasons: list[str] | None = None,
    min_training_samples: int = 120,
    top_k_options: list[int] | None = None,
    probability_floors: list[float] | None = None,
    stake: float = 1.0,
    max_samples: int | None = None,
    bucket_size: float = 0.05,
    prior_strength: int = 20,
    include_records: bool = False,
) -> dict[str, Any]:
    divisions = [str(item).strip() for item in (divisions or DEFAULT_SWEEP_DIVISIONS) if str(item).strip()]
    if training_seasons is None or validation_seasons is None:
        recent = _default_recent_seasons(5)
        training_seasons = recent[:-1]
        validation_seasons = recent[-1:]
    training_seasons = [str(item).strip() for item in training_seasons if str(item).strip()]
    validation_seasons = [str(item).strip() for item in validation_seasons if str(item).strip()]
    top_k_options = [max(1, int(item)) for item in (top_k_options or [1, 2, 3])]
    probability_floors = [float(item) for item in (probability_floors or [0.0, 0.55, 0.6, 0.65])]

    source_results = []
    errors = []
    training_records: list[dict[str, Any]] = []
    validation_records: list[dict[str, Any]] = []

    for division in divisions:
        for season, target in [
            *((season, "training") for season in training_seasons),
            *((season, "validation") for season in validation_seasons),
        ]:
            try:
                rows, source = await fetch_football_data_season_rows(division, season)
                samples = build_historical_samples(rows, division=division, season=season)
                base = _build_walk_forward_base(
                    samples,
                    min_training_samples=min_training_samples,
                    max_samples=max_samples,
                )
                for record in base.get("records") or []:
                    record = {
                        **record,
                        "division": division,
                        "season": season,
                    }
                    if target == "training":
                        training_records.append(record)
                    else:
                        validation_records.append(record)
                source_results.append(
                    {
                        "division": division,
                        "season": season,
                        "target": target,
                        "row_count": len(rows),
                        "sample_count": len(samples),
                        "evaluated_count": (base.get("summary") or {}).get("evaluated_count"),
                        "source": source,
                    }
                )
            except Exception as exc:
                errors.append(
                    {
                        "division": division,
                        "season": season,
                        "target": target,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )

    calibrator = _build_top_selection_calibrator(
        training_records,
        bucket_size=bucket_size,
        prior_strength=prior_strength,
    )
    validation_selections = [
        _apply_top_selection_calibrator(selection, calibrator)
        for record in validation_records
        if (selection := _top_probability_selection(record)) is not None
    ]
    top_k_results = [
        _top_k_confidence_metrics(
            validation_selections,
            top_k=top_k,
            min_calibrated_probability=floor,
            stake=stake,
        )
        for floor in probability_floors
        for top_k in top_k_options
    ]
    best_result = max(
        top_k_results,
        key=lambda item: (
            item.get("hit_rate") or 0.0,
            item.get("roi") if item.get("roi") is not None else -999.0,
            item.get("bet_count") or 0,
        ),
        default=None,
    )
    public_calibrator = {key: value for key, value in calibrator.items() if key != "bucket_map"}
    return {
        "status": "ok" if validation_selections else "empty",
        "tool": "run_top_k_confidence_backtest",
        "divisions": divisions,
        "training_seasons": training_seasons,
        "validation_seasons": validation_seasons,
        "summary": {
            "source_count": len(source_results),
            "error_count": len(errors),
            "training_record_count": len(training_records),
            "validation_record_count": len(validation_selections),
            "min_training_samples": min_training_samples,
            "stake": stake,
            "max_samples": max_samples,
        },
        "calibration": public_calibrator,
        "top_k_results": top_k_results,
        "best_result": best_result,
        "source_results": source_results,
        "errors": errors,
        "records": validation_selections if include_records else [],
        "agent_contract": {
            "confidence_rule": "calibrated_probability is learned from training-season top-selection hit rates, then scored on validation seasons only.",
            "top_k_rule": "Top-K results answer whether selecting only the highest calibrated confidence matches improves hit rate.",
            "profit_rule": "ROI is flat-stake paper trading and is not authorization for real-money betting.",
            "real_money_allowed": False,
        },
    }


def _metric_value(result: dict[str, Any], path: tuple[str, ...]) -> float | None:
    current: Any = result
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return _parse_float(current)


def _sweep_rank_score(result: dict[str, Any]) -> float:
    roi = _metric_value(result, ("betting", "roi")) or 0.0
    bet_count = _metric_value(result, ("betting", "bet_count")) or 0.0
    evaluated_count = _metric_value(result, ("summary", "evaluated_count")) or 0.0
    log_loss_delta = _metric_value(result, ("metrics", "delta", "log_loss_model_minus_market"))
    brier_delta = _metric_value(result, ("metrics", "delta", "brier_model_minus_market"))
    score = roi * 100
    score += min(bet_count, 200) * 0.03
    score += min(evaluated_count, 1000) * 0.002
    if log_loss_delta is not None:
        score -= log_loss_delta * 25
    if brier_delta is not None:
        score -= brier_delta * 12
    return round(score, 6)


def _compact_sweep_result(
    *,
    division: str,
    season: str,
    edge_threshold: float,
    min_training_samples: int,
    result: dict[str, Any],
) -> dict[str, Any]:
    summary = result.get("summary") or {}
    metrics = result.get("metrics") or {}
    betting = result.get("betting") or {}
    compact = {
        "division": division,
        "league": sources.LEAGUE_NAMES.get(division, division),
        "season": season,
        "edge_threshold": edge_threshold,
        "min_training_samples": min_training_samples,
        "sample_count": summary.get("sample_count"),
        "evaluated_count": summary.get("evaluated_count"),
        "bet_count": betting.get("bet_count"),
        "profit": betting.get("profit"),
        "roi": betting.get("roi"),
        "model_log_loss_1x2": (metrics.get("model") or {}).get("log_loss_1x2"),
        "market_log_loss_1x2": (metrics.get("market") or {}).get("log_loss_1x2"),
        "log_loss_model_minus_market": (metrics.get("delta") or {}).get("log_loss_model_minus_market"),
        "brier_model_minus_market": (metrics.get("delta") or {}).get("brier_model_minus_market"),
    }
    compact["rank_score"] = _sweep_rank_score({"summary": summary, "metrics": metrics, "betting": betting})
    compact["beats_market_log_loss"] = (
        compact["log_loss_model_minus_market"] is not None
        and compact["log_loss_model_minus_market"] < 0
    )
    compact["profitable"] = compact["roi"] is not None and compact["roi"] > 0
    return compact


def _summarize_segment(results: list[dict[str, Any]], key: str) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for result in results:
        grouped.setdefault(str(result.get(key) or ""), []).append(result)
    summary = {}
    for label, items in grouped.items():
        best = max(items, key=lambda item: item.get("rank_score") or -999)
        positive_roi = [item for item in items if (item.get("roi") or 0) > 0]
        beats_market = [item for item in items if item.get("beats_market_log_loss")]
        total_evaluated = sum(int(item.get("evaluated_count") or 0) for item in items)
        total_bets = sum(int(item.get("bet_count") or 0) for item in items)
        summary[label] = {
            "config_count": len(items),
            "total_evaluated_count": total_evaluated,
            "total_bet_count": total_bets,
            "positive_roi_config_count": len(positive_roi),
            "beats_market_log_loss_config_count": len(beats_market),
            "best_config": best,
        }
    return summary


def _sample_size_warnings(results: list[dict[str, Any]], *, min_evaluated: int = 50, min_bets: int = 20) -> list[dict[str, Any]]:
    warnings = []
    for result in results:
        evaluated = int(result.get("evaluated_count") or 0)
        bets = int(result.get("bet_count") or 0)
        reasons = []
        if evaluated < min_evaluated:
            reasons.append("evaluated_sample_below_recommended_minimum")
        if bets and bets < min_bets:
            reasons.append("bet_count_below_recommended_minimum")
        if reasons:
            warnings.append(
                {
                    "division": result.get("division"),
                    "season": result.get("season"),
                    "edge_threshold": result.get("edge_threshold"),
                    "min_training_samples": result.get("min_training_samples"),
                    "evaluated_count": evaluated,
                    "bet_count": bets,
                    "reasons": reasons,
                }
            )
    return warnings


def _automation_readiness(results: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> dict[str, Any]:
    if not results:
        return {
            "status": "not_ready",
            "reason": "no_valid_backtest_configs",
            "real_money_allowed": False,
        }
    eligible = [
        result
        for result in results
        if (_parse_float(result.get("roi")) or 0.0) > 0
        and (log_loss_delta := _parse_float(result.get("log_loss_model_minus_market"))) is not None
        and log_loss_delta < 0
    ]
    stable_eligible = [
        result
        for result in eligible
        if int(result.get("evaluated_count") or 0) >= 300
        and int(result.get("bet_count") or 0) >= 80
        and (_parse_float(result.get("roi")) or 0.0) > 0.03
    ]
    best = max(stable_eligible or eligible or results, key=lambda item: item.get("rank_score") or -999)
    evaluated = int(best.get("evaluated_count") or 0)
    bet_count = int(best.get("bet_count") or 0)
    roi = _parse_float(best.get("roi")) or 0.0
    log_loss_delta = _parse_float(best.get("log_loss_model_minus_market"))
    if evaluated >= 300 and bet_count >= 80 and roi > 0.03 and log_loss_delta is not None and log_loss_delta < 0:
        status = "paper_trade_only"
        reason = "best_config_has_positive_roi_and_beats_market_but_still_requires_live_paper_validation"
    elif roi > 0 and log_loss_delta is not None and log_loss_delta < 0:
        status = "watchlist"
        reason = "positive_signal_detected_but_sample_size_or_bet_count_is_not_enough"
    else:
        status = "not_ready"
        reason = "no_config_both_profitable_and_better_than_market_log_loss"
    return {
        "status": status,
        "reason": reason,
        "best_config": best,
        "sample_size_warning_count": len(warnings),
        "real_money_allowed": False,
        "next_gate": "Run live paper trading and closing-line-value checks before any execution automation.",
    }


def _weighted_average(items: list[tuple[float | None, int]]) -> float | None:
    weighted_sum = 0.0
    weight_sum = 0
    for value, weight in items:
        if value is None or weight <= 0:
            continue
        weighted_sum += float(value) * weight
        weight_sum += weight
    if not weight_sum:
        return None
    return _round(weighted_sum / weight_sum)


def _aggregate_config_results(
    *,
    division: str,
    seasons: list[str],
    edge_threshold: float,
    min_training_samples: int,
    results: list[dict[str, Any]],
    selection_source: str,
) -> dict[str, Any]:
    sample_count = sum(int((result.get("summary") or {}).get("sample_count") or 0) for result in results)
    evaluated_count = sum(int((result.get("summary") or {}).get("evaluated_count") or 0) for result in results)
    skipped_for_training = sum(int((result.get("summary") or {}).get("skipped_for_training_count") or 0) for result in results)
    skipped_unavailable = sum(int((result.get("summary") or {}).get("skipped_unavailable_count") or 0) for result in results)
    bet_count = sum(int((result.get("betting") or {}).get("bet_count") or 0) for result in results)
    profit = sum(float((result.get("betting") or {}).get("profit") or 0.0) for result in results)
    stake = _parse_float(((results[0].get("betting") or {}) if results else {}).get("stake")) or 1.0
    model_log_loss = _weighted_average(
        [
            (
                _parse_float(((result.get("metrics") or {}).get("model") or {}).get("log_loss_1x2")),
                int((result.get("summary") or {}).get("evaluated_count") or 0),
            )
            for result in results
        ]
    )
    market_log_loss = _weighted_average(
        [
            (
                _parse_float(((result.get("metrics") or {}).get("market") or {}).get("log_loss_1x2")),
                int((result.get("summary") or {}).get("evaluated_count") or 0),
            )
            for result in results
        ]
    )
    model_brier = _weighted_average(
        [
            (
                _parse_float(((result.get("metrics") or {}).get("model") or {}).get("brier_score_1x2")),
                int((result.get("summary") or {}).get("evaluated_count") or 0),
            )
            for result in results
        ]
    )
    market_brier = _weighted_average(
        [
            (
                _parse_float(((result.get("metrics") or {}).get("market") or {}).get("brier_score_1x2")),
                int((result.get("summary") or {}).get("evaluated_count") or 0),
            )
            for result in results
        ]
    )
    roi = _round(profit / (bet_count * stake) if bet_count and stake else None)
    aggregate = {
        "division": division,
        "league": sources.LEAGUE_NAMES.get(division, division),
        "seasons": seasons,
        "selection_source": selection_source,
        "edge_threshold": edge_threshold,
        "min_training_samples": min_training_samples,
        "sample_count": sample_count,
        "evaluated_count": evaluated_count,
        "skipped_for_training_count": skipped_for_training,
        "skipped_unavailable_count": skipped_unavailable,
        "bet_count": bet_count,
        "profit": _round(profit),
        "roi": roi,
        "model_log_loss_1x2": model_log_loss,
        "market_log_loss_1x2": market_log_loss,
        "log_loss_model_minus_market": _round((model_log_loss or 0) - (market_log_loss or 0)) if model_log_loss is not None and market_log_loss is not None else None,
        "model_brier_score_1x2": model_brier,
        "market_brier_score_1x2": market_brier,
        "brier_model_minus_market": _round((model_brier or 0) - (market_brier or 0)) if model_brier is not None and market_brier is not None else None,
    }
    aggregate["beats_market_log_loss"] = (
        aggregate["log_loss_model_minus_market"] is not None
        and aggregate["log_loss_model_minus_market"] < 0
    )
    aggregate["profitable"] = aggregate["roi"] is not None and aggregate["roi"] > 0
    aggregate["rank_score"] = _sweep_rank_score(
        {
            "summary": {"evaluated_count": evaluated_count},
            "metrics": {
                "delta": {
                    "log_loss_model_minus_market": aggregate["log_loss_model_minus_market"],
                    "brier_model_minus_market": aggregate["brier_model_minus_market"],
                }
            },
            "betting": {"roi": roi, "bet_count": bet_count},
        }
    )
    return aggregate


def _select_training_config(
    training_configs: list[dict[str, Any]],
    *,
    min_selection_bets: int,
    min_selection_evaluated: int,
) -> dict[str, Any] | None:
    eligible = [
        config
        for config in training_configs
        if config.get("profitable")
        and config.get("beats_market_log_loss")
        and int(config.get("bet_count") or 0) >= min_selection_bets
        and int(config.get("evaluated_count") or 0) >= min_selection_evaluated
    ]
    return max(eligible or training_configs, key=lambda item: item.get("rank_score") or -999, default=None)


def _holdout_readiness(
    division_results: list[dict[str, Any]],
    *,
    min_validation_bets: int,
    min_validation_evaluated: int,
) -> dict[str, Any]:
    validation_results = [
        result.get("validation_result") or {}
        for result in division_results
        if result.get("validation_result")
    ]
    if not validation_results:
        return {
            "status": "not_ready",
            "reason": "no_validation_results",
            "real_money_allowed": False,
        }
    passing = [
        result
        for result in validation_results
        if result.get("profitable")
        and result.get("beats_market_log_loss")
        and int(result.get("bet_count") or 0) >= min_validation_bets
        and int(result.get("evaluated_count") or 0) >= min_validation_evaluated
    ]
    weak_positive = [
        result
        for result in validation_results
        if result.get("profitable")
        and result.get("beats_market_log_loss")
    ]
    best = max(passing or weak_positive or validation_results, key=lambda item: item.get("rank_score") or -999)
    if passing:
        status = "validated_paper_trade_only"
        reason = "selected_training_config_survived_holdout_validation"
    elif weak_positive:
        status = "watchlist"
        reason = "holdout_positive_but_validation_sample_or_bet_count_is_too_small"
    else:
        status = "not_ready"
        reason = "selected_training_config_failed_holdout_validation"
    return {
        "status": status,
        "reason": reason,
        "best_validation_result": best,
        "real_money_allowed": False,
        "next_gate": "Run live paper trading with closing-line-value tracking before any real-money automation.",
    }


def _default_recent_seasons(count: int = 5) -> list[str]:
    current = sources.season_code_for(sources.now_utc())
    start = int(current[:2])
    return [f"{year:02d}{year + 1:02d}" for year in range(start - count + 1, start + 1)]


async def run_backtest_sweep(
    *,
    divisions: list[str] | None = None,
    seasons: list[str] | None = None,
    edge_thresholds: list[float] | None = None,
    min_training_samples_options: list[int] | None = None,
    stake: float = 1.0,
    max_samples: int | None = None,
    include_records: bool = False,
) -> dict[str, Any]:
    divisions = [str(item).strip() for item in (divisions or DEFAULT_SWEEP_DIVISIONS) if str(item).strip()]
    seasons = [str(item).strip() for item in (seasons or _default_recent_seasons()) if str(item).strip()]
    edge_thresholds = [
        float(item)
        for item in (edge_thresholds or DEFAULT_SWEEP_EDGE_THRESHOLDS)
    ]
    min_training_samples_options = [
        int(item)
        for item in (min_training_samples_options or DEFAULT_SWEEP_TRAINING_SAMPLES)
    ]

    source_results = []
    config_results = []
    errors = []
    for division in divisions:
        for season in seasons:
            try:
                rows, source = await fetch_football_data_season_rows(division, season)
                samples = build_historical_samples(rows, division=division, season=season)
                source_results.append(
                    {
                        "division": division,
                        "season": season,
                        "league": sources.LEAGUE_NAMES.get(division, division),
                        "row_count": len(rows),
                        "sample_count": len(samples),
                        "source": source,
                    }
                )
            except Exception as exc:
                errors.append(
                    {
                        "division": division,
                        "season": season,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
                continue

            for min_training_samples in min_training_samples_options:
                base = _build_walk_forward_base(
                    samples,
                    min_training_samples=min_training_samples,
                    max_samples=max_samples,
                )
                for edge_threshold in edge_thresholds:
                    result = _walk_forward_result_from_base(
                        base,
                        edge_threshold=edge_threshold,
                        stake=stake,
                    )
                    compact = _compact_sweep_result(
                        division=division,
                        season=season,
                        edge_threshold=edge_threshold,
                        min_training_samples=min_training_samples,
                        result=result,
                    )
                    if include_records:
                        compact["records"] = result.get("records") or []
                    config_results.append(compact)

    ranked = sorted(config_results, key=lambda item: item.get("rank_score") or -999, reverse=True)
    warnings = _sample_size_warnings(config_results)
    return {
        "status": "ok" if config_results else "empty",
        "divisions": divisions,
        "seasons": seasons,
        "edge_thresholds": edge_thresholds,
        "min_training_samples_options": min_training_samples_options,
        "summary": {
            "source_count": len(source_results),
            "config_count": len(config_results),
            "error_count": len(errors),
            "max_samples": max_samples,
            "stake": stake,
        },
        "best_configs": ranked[:10],
        "worst_configs": list(reversed(ranked[-10:])),
        "all_configs": config_results,
        "league_summary": _summarize_segment(config_results, "division"),
        "season_summary": _summarize_segment(config_results, "season"),
        "source_results": source_results,
        "errors": errors,
        "sample_size_warnings": warnings,
        "automation_readiness": _automation_readiness(config_results, warnings),
        "ranking_policy": (
            "Configs are ranked by paper ROI, bet/evaluation sample support, and penalties when model log loss or Brier underperform the market baseline."
        ),
        "agent_contract": {
            "no_automation_without_positive_sweep": "Do not enable automated betting unless a config beats market log loss, has positive paper ROI, and later passes live paper trading.",
            "sample_warning_rule": "Treat sample_size_warnings as a block on strong claims even when ROI is positive.",
            "market_baseline_rule": "A config that is profitable but worse than the market probability baseline is not model evidence.",
        },
    }


async def run_holdout_validation(
    *,
    divisions: list[str] | None = None,
    training_seasons: list[str] | None = None,
    validation_seasons: list[str] | None = None,
    edge_thresholds: list[float] | None = None,
    min_training_samples_options: list[int] | None = None,
    stake: float = 1.0,
    max_samples: int | None = None,
    min_selection_bets: int = 30,
    min_selection_evaluated: int = 100,
    min_validation_bets: int = 50,
    min_validation_evaluated: int = 100,
) -> dict[str, Any]:
    divisions = [str(item).strip() for item in (divisions or DEFAULT_SWEEP_DIVISIONS) if str(item).strip()]
    if training_seasons is None or validation_seasons is None:
        recent = _default_recent_seasons(5)
        training_seasons = recent[:-1]
        validation_seasons = recent[-1:]
    training_seasons = [str(item).strip() for item in training_seasons if str(item).strip()]
    validation_seasons = [str(item).strip() for item in validation_seasons if str(item).strip()]
    edge_thresholds = [float(item) for item in (edge_thresholds or DEFAULT_SWEEP_EDGE_THRESHOLDS)]
    min_training_samples_options = [int(item) for item in (min_training_samples_options or DEFAULT_SWEEP_TRAINING_SAMPLES)]

    source_results = []
    division_results = []
    errors = []
    training_config_count = 0
    fetched_samples: dict[tuple[str, str], list[dict[str, Any]]] = {}

    for division in divisions:
        for season in [*training_seasons, *validation_seasons]:
            key = (division, season)
            if key in fetched_samples:
                continue
            try:
                rows, source = await fetch_football_data_season_rows(division, season)
                samples = build_historical_samples(rows, division=division, season=season)
                fetched_samples[key] = samples
                source_results.append(
                    {
                        "division": division,
                        "season": season,
                        "league": sources.LEAGUE_NAMES.get(division, division),
                        "row_count": len(rows),
                        "sample_count": len(samples),
                        "source": source,
                    }
                )
            except Exception as exc:
                fetched_samples[key] = []
                errors.append(
                    {
                        "division": division,
                        "season": season,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )

        training_configs = []
        for min_training_samples in min_training_samples_options:
            training_bases = {
                season: _build_walk_forward_base(
                    fetched_samples.get((division, season), []),
                    min_training_samples=min_training_samples,
                    max_samples=max_samples,
                )
                for season in training_seasons
            }
            for edge_threshold in edge_thresholds:
                season_results = [
                    _walk_forward_result_from_base(
                        base,
                        edge_threshold=edge_threshold,
                        stake=stake,
                    )
                    for base in training_bases.values()
                ]
                training_configs.append(
                    _aggregate_config_results(
                        division=division,
                        seasons=training_seasons,
                        edge_threshold=edge_threshold,
                        min_training_samples=min_training_samples,
                        results=season_results,
                        selection_source="training_only",
                    )
                )
        training_config_count += len(training_configs)
        selected_config = _select_training_config(
            training_configs,
            min_selection_bets=min_selection_bets,
            min_selection_evaluated=min_selection_evaluated,
        )
        if not selected_config:
            division_results.append(
                {
                    "division": division,
                    "league": sources.LEAGUE_NAMES.get(division, division),
                    "status": "no_training_config",
                    "training_configs": [],
                    "selected_config": None,
                    "validation_result": None,
                }
            )
            continue

        validation_results = [
            run_walk_forward_backtest(
                fetched_samples.get((division, season), []),
                min_training_samples=int(selected_config["min_training_samples"]),
                edge_threshold=float(selected_config["edge_threshold"]),
                stake=stake,
                max_samples=max_samples,
            )
            for season in validation_seasons
        ]
        validation_result = _aggregate_config_results(
            division=division,
            seasons=validation_seasons,
            edge_threshold=float(selected_config["edge_threshold"]),
            min_training_samples=int(selected_config["min_training_samples"]),
            results=validation_results,
            selection_source="holdout_validation",
        )
        division_results.append(
            {
                "division": division,
                "league": sources.LEAGUE_NAMES.get(division, division),
                "status": "ok",
                "training_configs": sorted(training_configs, key=lambda item: item.get("rank_score") or -999, reverse=True)[:10],
                "selected_config": selected_config,
                "validation_result": validation_result,
            }
        )

    return {
        "status": "ok" if division_results else "empty",
        "divisions": divisions,
        "training_seasons": training_seasons,
        "validation_seasons": validation_seasons,
        "edge_thresholds": edge_thresholds,
        "min_training_samples_options": min_training_samples_options,
        "summary": {
            "division_count": len(divisions),
            "source_count": len(source_results),
            "training_config_count": training_config_count,
            "error_count": len(errors),
            "max_samples": max_samples,
            "stake": stake,
            "min_selection_bets": min_selection_bets,
            "min_validation_bets": min_validation_bets,
        },
        "division_results": division_results,
        "holdout_readiness": _holdout_readiness(
            division_results,
            min_validation_bets=min_validation_bets,
            min_validation_evaluated=min_validation_evaluated,
        ),
        "source_results": source_results,
        "errors": errors,
        "agent_contract": {
            "holdout_rule": "Training seasons select the config; validation seasons only score the preselected config.",
            "no_real_money_rule": "Holdout pass can allow paper trading only; real-money automation still requires live CLV and execution-risk validation.",
            "failure_rule": "If holdout_readiness.status is not validated_paper_trade_only, shortlist/parlay recommendations remain research-only.",
        },
    }
