from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from statistics import median
from typing import Any


ODDS_FEATURE_ENGINE_METHOD = "odds_feature_engine_v1"
DEFAULT_DEVIG_METHOD = "power"


def parse_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number


def round_metric(value: Any, digits: int = 6) -> float | None:
    number = parse_float(value)
    if number is None:
        return None
    return round(number, digits)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _median(values: list[float]) -> float | None:
    return float(median(values)) if values else None


def decimal_to_implied_probability(decimal_odds: Any) -> float | None:
    odds = parse_float(decimal_odds)
    if odds is None or odds <= 1.0:
        return None
    return 1.0 / odds


def devig_probabilities(
    odds_by_selection: dict[str, Any],
    *,
    method: str = DEFAULT_DEVIG_METHOD,
) -> dict[str, Any]:
    """Convert decimal odds into no-vig probabilities.

    The output is deliberately method-tagged so backtests can compare different
    open-source-style odds transformations instead of hiding the bookmaker margin.
    """

    raw = {
        str(selection): decimal_to_implied_probability(odds)
        for selection, odds in odds_by_selection.items()
    }
    raw = {selection: probability for selection, probability in raw.items() if probability is not None}
    if len(raw) < 2:
        return {
            "status": "unavailable",
            "method": method,
            "reason": "at_least_two_valid_prices_required",
            "probabilities": {},
        }

    overround = sum(raw.values())
    if overround <= 0:
        return {
            "status": "unavailable",
            "method": method,
            "reason": "invalid_overround",
            "probabilities": {},
        }

    normalized_method = str(method or DEFAULT_DEVIG_METHOD).strip().lower()
    if normalized_method == "multiplicative":
        probabilities = {selection: probability / overround for selection, probability in raw.items()}
        metadata: dict[str, Any] = {}
    elif normalized_method == "additive":
        deduction = (overround - 1.0) / len(raw)
        adjusted = {selection: max(0.0001, probability - deduction) for selection, probability in raw.items()}
        adjusted_total = sum(adjusted.values())
        probabilities = {selection: probability / adjusted_total for selection, probability in adjusted.items()}
        metadata = {"additive_deduction": round_metric(deduction)}
    elif normalized_method == "power":
        exponent = _solve_power_devig_exponent(list(raw.values()))
        powered = {selection: probability**exponent for selection, probability in raw.items()}
        powered_total = sum(powered.values())
        probabilities = {selection: probability / powered_total for selection, probability in powered.items()}
        metadata = {"power_exponent": round_metric(exponent, 8)}
    else:
        return {
            "status": "unavailable",
            "method": normalized_method,
            "reason": "unsupported_devig_method",
            "probabilities": {},
        }

    return {
        "status": "available",
        "method": normalized_method,
        "probabilities": {selection: round_metric(probability) for selection, probability in probabilities.items()},
        "raw_implied_probabilities": {selection: round_metric(probability) for selection, probability in raw.items()},
        "overround": round_metric(overround),
        "bookmaker_margin": round_metric(overround - 1.0),
        **metadata,
    }


def _solve_power_devig_exponent(raw_probabilities: list[float]) -> float:
    low = 0.01
    high = 20.0
    for _ in range(80):
        mid = (low + high) / 2.0
        total = sum(probability**mid for probability in raw_probabilities)
        if total > 1.0:
            low = mid
        else:
            high = mid
    return (low + high) / 2.0


def build_odds_feature_summary(
    rows: list[dict[str, Any]],
    *,
    home_team: str = "",
    away_team: str = "",
    devig_method: str = DEFAULT_DEVIG_METHOD,
) -> dict[str, Any]:
    normalized_rows = [
        normalized
        for row in rows
        if (normalized := _normalize_snapshot_row(row, home_team=home_team, away_team=away_team))
    ]
    if not normalized_rows:
        return {
            "status": "unavailable",
            "method": ODDS_FEATURE_ENGINE_METHOD,
            "reason": "matching_market_snapshots_missing",
            "devig_method": devig_method,
            "markets": {},
            "key_signals": [],
        }

    latest_rows = _extreme_rows_by_bookmaker_selection(normalized_rows, latest=True)
    opening_rows = _extreme_rows_by_bookmaker_selection(normalized_rows, latest=False)
    no_vig_samples, margin_samples = _bookmaker_no_vig_samples(latest_rows, devig_method=devig_method)

    markets: dict[str, Any] = {}
    for market in sorted({row["market"] for row in normalized_rows}):
        selection_keys = sorted({row["selection_key"] for row in latest_rows if row["market"] == market})
        selections = {
            selection_key: _selection_feature_summary(
                market=market,
                selection_key=selection_key,
                latest_rows=[
                    row for row in latest_rows if row["market"] == market and row["selection_key"] == selection_key
                ],
                opening_rows=[
                    row for row in opening_rows if row["market"] == market and row["selection_key"] == selection_key
                ],
                no_vig_samples=[
                    value
                    for (sample_market, _line_group, sample_selection), values in no_vig_samples.items()
                    if sample_market == market and sample_selection == selection_key
                    for value in values
                ],
                devig_method=devig_method,
                line_group="all",
            )
            for selection_key in selection_keys
        }
        line_summaries = _market_line_summaries(
            market=market,
            latest_rows=latest_rows,
            opening_rows=opening_rows,
            no_vig_samples=no_vig_samples,
            devig_method=devig_method,
        )
        market_margins = margin_samples.get(market, [])
        markets[market] = {
            "status": "available" if selections else "unavailable",
            "selection_count": len(selections),
            "bookmaker_count": len(
                {row["bookmaker"] for row in latest_rows if row["market"] == market and row.get("bookmaker")}
            ),
            "snapshot_count": len([row for row in normalized_rows if row["market"] == market]),
            "devig_method": devig_method,
            "margin": _margin_summary(market_margins),
            "selections": selections,
            "lines": line_summaries,
        }

    key_signals = _key_odds_signals(markets)
    return {
        "status": "available" if markets else "unavailable",
        "method": ODDS_FEATURE_ENGINE_METHOD,
        "devig_method": devig_method,
        "snapshot_count": len(normalized_rows),
        "bookmaker_count": len({row["bookmaker"] for row in normalized_rows if row.get("bookmaker")}),
        "market_count": len(markets),
        "markets": markets,
        "key_signals": key_signals[:8],
        "usage_policy": (
            "Use no-vig market probability, bookmaker dispersion, and price movement as market evidence; "
            "current decimal odds still decide expected value."
        ),
    }


def candidate_odds_profile(candidate: dict[str, Any], odds_features: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(odds_features, dict) or odds_features.get("status") != "available":
        return {
            "status": "unavailable",
            "method": "candidate_odds_profile_v1",
            "reason": "odds_features_unavailable",
        }
    market = _candidate_market_key(candidate.get("market"))
    selection_key = _candidate_selection_key(candidate)
    line_group = _candidate_line_group(market, candidate.get("line"))
    market_summary = ((odds_features.get("markets") or {}).get(market) or {})
    line_summary = ((market_summary.get("lines") or {}).get(line_group) or {}) if line_group else {}
    selection_summary = ((line_summary.get("selections") or {}).get(selection_key)) if line_summary else None
    if not isinstance(selection_summary, dict):
        selection_summary = (market_summary.get("selections") or {}).get(selection_key)
    if not isinstance(selection_summary, dict):
        return {
            "status": "unavailable",
            "method": "candidate_odds_profile_v1",
            "reason": "candidate_market_selection_missing",
            "market": market,
            "selection_key": selection_key,
            "line_group": line_group,
        }

    model_probability = parse_float(candidate.get("model_probability"))
    decimal_odds = parse_float(candidate.get("decimal_odds")) or parse_float(selection_summary.get("current_decimal_odds"))
    no_vig_probability = parse_float(selection_summary.get("no_vig_probability"))
    current_consensus_odds = parse_float(selection_summary.get("current_decimal_odds"))
    raw_implied_probability = decimal_to_implied_probability(decimal_odds)

    expected_multiplier = None
    ev_edge = None
    kelly_fraction = None
    fair_decimal_odds = None
    probability_edge_vs_no_vig = None
    if model_probability is not None:
        fair_decimal_odds = 1.0 / _clamp(model_probability, 0.001, 0.999)
        if no_vig_probability is not None:
            probability_edge_vs_no_vig = model_probability - no_vig_probability
        if decimal_odds is not None and decimal_odds > 1.0:
            expected_multiplier = model_probability * decimal_odds
            ev_edge = expected_multiplier - 1.0
            if decimal_odds > 1.0:
                kelly_fraction = ev_edge / (decimal_odds - 1.0)

    price_gap_vs_consensus = None
    if decimal_odds is not None and current_consensus_odds is not None and current_consensus_odds > 1.0:
        price_gap_vs_consensus = decimal_odds / current_consensus_odds - 1.0

    return {
        "status": "available",
        "method": "candidate_odds_profile_v1",
        "market": market,
        "selection_key": selection_key,
        "line_group": line_group or selection_summary.get("line_group"),
        "devig_method": selection_summary.get("no_vig_method") or odds_features.get("devig_method"),
        "decimal_odds": round_metric(decimal_odds, 4),
        "current_consensus_odds": round_metric(current_consensus_odds, 4),
        "best_available_odds": selection_summary.get("best_decimal_odds"),
        "worst_available_odds": selection_summary.get("worst_decimal_odds"),
        "price_spread": selection_summary.get("price_spread"),
        "price_spread_pct": selection_summary.get("price_spread_pct"),
        "raw_implied_probability": round_metric(raw_implied_probability),
        "no_vig_probability": round_metric(no_vig_probability),
        "model_probability": round_metric(model_probability),
        "probability_edge_vs_no_vig": round_metric(probability_edge_vs_no_vig),
        "fair_decimal_odds_from_model": round_metric(fair_decimal_odds, 4),
        "expected_multiplier": round_metric(expected_multiplier, 6),
        "ev_edge": round_metric(ev_edge, 4),
        "kelly_fraction_full": round_metric(_clamp(kelly_fraction or 0.0, 0.0, 0.25), 4)
        if kelly_fraction is not None
        else None,
        "price_gap_vs_consensus": round_metric(price_gap_vs_consensus, 4),
        "bookmaker_count": selection_summary.get("bookmaker_count"),
        "devig_sample_count": selection_summary.get("devig_sample_count"),
        "research_verdict": _candidate_research_verdict(
            model_probability=model_probability,
            no_vig_probability=no_vig_probability,
            ev_edge=ev_edge,
            price_spread_pct=parse_float(selection_summary.get("price_spread_pct")),
            movement_delta=parse_float(selection_summary.get("implied_probability_delta")),
        ),
        "selection_features": {
            "opening_decimal_odds": selection_summary.get("opening_decimal_odds"),
            "current_decimal_odds": selection_summary.get("current_decimal_odds"),
            "odds_delta": selection_summary.get("odds_delta"),
            "implied_probability_delta": selection_summary.get("implied_probability_delta"),
            "line_delta": selection_summary.get("line_delta"),
        },
    }


def _normalize_snapshot_row(row: dict[str, Any], *, home_team: str, away_team: str) -> dict[str, Any] | None:
    decimal_odds = parse_float(row.get("decimal_odds"))
    if decimal_odds is None or decimal_odds <= 1.0:
        return None
    market = _canonical_market_type(row.get("market_type"))
    if market not in {"h2h", "asian_handicap", "over_under"}:
        return None
    selection_key = _snapshot_selection_key(row, market=market, home_team=home_team, away_team=away_team)
    if not selection_key:
        return None
    row_time = _snapshot_time(row)
    if row_time is None:
        return None
    return {
        "market": market,
        "selection_key": selection_key,
        "selection": row.get("selection") or selection_key,
        "bookmaker": str(row.get("bookmaker") or "unknown"),
        "decimal_odds": decimal_odds,
        "line": parse_float(row.get("line")),
        "line_group": _line_group(market, parse_float(row.get("line"))),
        "observed_at": row_time,
        "source_time_utc": row.get("source_time_utc"),
        "fetched_at_utc": row.get("fetched_at_utc"),
    }


def _extreme_rows_by_bookmaker_selection(rows: list[dict[str, Any]], *, latest: bool) -> list[dict[str, Any]]:
    selected: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for row in sorted(rows, key=lambda item: item["observed_at"], reverse=latest):
        key = (row["market"], row["selection_key"], row["bookmaker"], str(row.get("line_group") or ""))
        if key not in selected:
            selected[key] = row
    return list(selected.values())


def _bookmaker_no_vig_samples(
    latest_rows: list[dict[str, Any]],
    *,
    devig_method: str,
) -> tuple[dict[tuple[str, str, str], list[float]], dict[str, list[float]]]:
    by_book_market_line: dict[tuple[str, str, str], dict[str, float]] = defaultdict(dict)
    for row in latest_rows:
        group_key = (row["bookmaker"], row["market"], str(row.get("line_group") or ""))
        by_book_market_line[group_key][row["selection_key"]] = row["decimal_odds"]

    samples: dict[tuple[str, str], list[float]] = defaultdict(list)
    margin_samples: dict[str, list[float]] = defaultdict(list)
    for (_bookmaker, market, _line_group), odds_by_selection in by_book_market_line.items():
        if not _has_complete_market(market, odds_by_selection):
            continue
        devig = devig_probabilities(odds_by_selection, method=devig_method)
        if devig.get("status") != "available":
            continue
        margin = parse_float(devig.get("bookmaker_margin"))
        if margin is not None:
            margin_samples[market].append(margin)
        for selection_key, probability in (devig.get("probabilities") or {}).items():
            parsed = parse_float(probability)
            if parsed is not None:
                samples[(market, _line_group, selection_key)].append(parsed)
    return samples, margin_samples


def _market_line_summaries(
    *,
    market: str,
    latest_rows: list[dict[str, Any]],
    opening_rows: list[dict[str, Any]],
    no_vig_samples: dict[tuple[str, str, str], list[float]],
    devig_method: str,
) -> dict[str, Any]:
    market_latest_rows = [row for row in latest_rows if row["market"] == market]
    line_groups = sorted({str(row.get("line_group") or "none") for row in market_latest_rows})
    summaries: dict[str, Any] = {}
    for line_group in line_groups:
        latest_for_line = [row for row in market_latest_rows if str(row.get("line_group") or "none") == line_group]
        opening_for_line = [
            row
            for row in opening_rows
            if row["market"] == market and str(row.get("line_group") or "none") == line_group
        ]
        selection_keys = sorted({row["selection_key"] for row in latest_for_line})
        line_values = [row["line"] for row in latest_for_line if row.get("line") is not None]
        summaries[line_group] = {
            "line_group": line_group,
            "line": round_metric(_median(line_values), 4),
            "selection_count": len(selection_keys),
            "bookmaker_count": len({row["bookmaker"] for row in latest_for_line if row.get("bookmaker")}),
            "selections": {
                selection_key: _selection_feature_summary(
                    market=market,
                    selection_key=selection_key,
                    latest_rows=[
                        row for row in latest_for_line if row["selection_key"] == selection_key
                    ],
                    opening_rows=[
                        row for row in opening_for_line if row["selection_key"] == selection_key
                    ],
                    no_vig_samples=no_vig_samples.get((market, line_group, selection_key), []),
                    devig_method=devig_method,
                    line_group=line_group,
                )
                for selection_key in selection_keys
            },
        }
    return summaries


def _selection_feature_summary(
    *,
    market: str,
    selection_key: str,
    latest_rows: list[dict[str, Any]],
    opening_rows: list[dict[str, Any]],
    no_vig_samples: list[float],
    devig_method: str,
    line_group: str,
) -> dict[str, Any]:
    latest_prices = [row["decimal_odds"] for row in latest_rows if row.get("decimal_odds")]
    opening_prices = [row["decimal_odds"] for row in opening_rows if row.get("decimal_odds")]
    latest_lines = [row["line"] for row in latest_rows if row.get("line") is not None]
    opening_lines = [row["line"] for row in opening_rows if row.get("line") is not None]
    current_decimal_odds = _median(latest_prices)
    opening_decimal_odds = _median(opening_prices)
    current_implied = _median([1.0 / price for price in latest_prices if price > 1.0])
    opening_implied = _median([1.0 / price for price in opening_prices if price > 1.0])
    no_vig_probability = _median(no_vig_samples)
    price_spread = max(latest_prices) - min(latest_prices) if latest_prices else None
    price_spread_pct = price_spread / current_decimal_odds if price_spread is not None and current_decimal_odds else None
    latest_line = _median(latest_lines)
    opening_line = _median(opening_lines)
    line_delta = latest_line - opening_line if latest_line is not None and opening_line is not None else None
    odds_delta = (
        current_decimal_odds - opening_decimal_odds
        if current_decimal_odds is not None and opening_decimal_odds is not None
        else None
    )
    implied_probability_delta = (
        current_implied - opening_implied
        if current_implied is not None and opening_implied is not None
        else None
    )
    return {
        "status": "available" if latest_prices else "unavailable",
        "market": market,
        "selection_key": selection_key,
        "line_group": line_group,
        "selection": str((latest_rows[0] if latest_rows else {}).get("selection") or selection_key),
        "bookmaker_count": len({row["bookmaker"] for row in latest_rows if row.get("bookmaker")}),
        "snapshot_count": len(latest_rows) + len(opening_rows),
        "opening_decimal_odds": round_metric(opening_decimal_odds, 4),
        "current_decimal_odds": round_metric(current_decimal_odds, 4),
        "best_decimal_odds": round_metric(max(latest_prices), 4) if latest_prices else None,
        "worst_decimal_odds": round_metric(min(latest_prices), 4) if latest_prices else None,
        "price_spread": round_metric(price_spread, 4),
        "price_spread_pct": round_metric(price_spread_pct, 4),
        "opening_raw_implied_probability": round_metric(opening_implied),
        "current_raw_implied_probability": round_metric(current_implied),
        "no_vig_probability": round_metric(no_vig_probability),
        "no_vig_method": devig_method,
        "devig_sample_count": len(no_vig_samples),
        "odds_delta": round_metric(odds_delta, 4),
        "implied_probability_delta": round_metric(implied_probability_delta),
        "opening_line": round_metric(opening_line, 4),
        "latest_line": round_metric(latest_line, 4),
        "line_delta": round_metric(line_delta, 4),
        "quality": _selection_quality(len(no_vig_samples), len(latest_prices), price_spread_pct),
    }


def _margin_summary(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"status": "unavailable", "sample_count": 0}
    return {
        "status": "available",
        "sample_count": len(values),
        "median": round_metric(_median(values)),
        "min": round_metric(min(values)),
        "max": round_metric(max(values)),
    }


def _key_odds_signals(markets: dict[str, Any]) -> list[dict[str, Any]]:
    signals: list[dict[str, Any]] = []
    for market, summary in markets.items():
        for selection_key, selection in ((summary.get("selections") or {}).items()):
            price_spread_pct = parse_float(selection.get("price_spread_pct")) or 0.0
            probability_delta = parse_float(selection.get("implied_probability_delta")) or 0.0
            if abs(probability_delta) >= 0.02:
                signals.append(
                    {
                        "type": "steam_move" if probability_delta > 0 else "drift_move",
                        "market": market,
                        "selection_key": selection_key,
                        "selection": selection.get("selection"),
                        "strength": round_metric(abs(probability_delta)),
                        "implied_probability_delta": round_metric(probability_delta),
                        "note": "opening-to-current implied probability moved by at least two points",
                    }
                )
            if price_spread_pct >= 0.06:
                signals.append(
                    {
                        "type": "bookmaker_disagreement",
                        "market": market,
                        "selection_key": selection_key,
                        "selection": selection.get("selection"),
                        "strength": round_metric(price_spread_pct),
                        "price_spread_pct": round_metric(price_spread_pct),
                        "note": "bookmakers disagree enough that best-price shopping matters",
                    }
                )
    signals.sort(key=lambda item: abs(parse_float(item.get("strength")) or 0.0), reverse=True)
    return signals


def _selection_quality(devig_sample_count: int, price_count: int, price_spread_pct: float | None) -> str:
    if devig_sample_count >= 3 and (price_spread_pct is None or price_spread_pct <= 0.06):
        return "high"
    if devig_sample_count >= 1 and price_count >= 1:
        return "medium"
    return "raw_price_only"


def _candidate_research_verdict(
    *,
    model_probability: float | None,
    no_vig_probability: float | None,
    ev_edge: float | None,
    price_spread_pct: float | None,
    movement_delta: float | None,
) -> str:
    if model_probability is None or ev_edge is None:
        return "insufficient_model_or_price"
    if price_spread_pct is not None and price_spread_pct >= 0.08:
        return "value_depends_on_bookmaker_price"
    if no_vig_probability is not None and model_probability <= no_vig_probability and ev_edge > 0:
        return "price_value_not_probability_edge"
    if movement_delta is not None and movement_delta > 0.02 and ev_edge <= 0:
        return "market_support_but_price_tight"
    if ev_edge > 0.035:
        return "positive_ev_with_market_context"
    if ev_edge > 0:
        return "thin_positive_ev"
    return "no_current_price_value"


def _canonical_market_type(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"1x2", "h2h", "moneyline", "moneyline_1x2"}:
        return "h2h"
    if normalized in {"asian_handicap", "spreads", "spread"}:
        return "asian_handicap"
    if normalized in {"over_under", "totals", "total"}:
        return "over_under"
    return normalized


def _candidate_market_key(value: Any) -> str:
    return _canonical_market_type(value)


def _candidate_selection_key(candidate: dict[str, Any]) -> str:
    selection_key = str(candidate.get("selection_key") or "").strip().lower()
    market = _candidate_market_key(candidate.get("market"))
    if market == "h2h":
        if selection_key in {"home", "h"}:
            return "home"
        if selection_key in {"draw", "d", "x"}:
            return "draw"
        if selection_key in {"away", "a"}:
            return "away"
    if market == "asian_handicap":
        if selection_key in {"home", "home_cover", "h"}:
            return "home_cover"
        if selection_key in {"away", "away_cover", "a"}:
            return "away_cover"
    if market == "over_under":
        if selection_key in {"over", "o"}:
            return "over"
        if selection_key in {"under", "u"}:
            return "under"
    return selection_key


def _snapshot_selection_key(row: dict[str, Any], *, market: str, home_team: str, away_team: str) -> str:
    raw = row.get("raw") if isinstance(row.get("raw"), dict) else {}
    raw_side = str(raw.get("side") or "").strip().lower()
    if raw_side in {"home", "draw", "away", "home_cover", "away_cover", "over", "under"}:
        return raw_side
    selection = str(row.get("selection") or "").strip()
    selection_lower = selection.lower()
    if market == "h2h":
        if selection_lower in {"draw", "d", "x", "平", "平局"}:
            return "draw"
        if _team_matches(selection, home_team):
            return "home"
        if _team_matches(selection, away_team):
            return "away"
    if market == "asian_handicap":
        if _team_matches(selection, home_team):
            return "home_cover"
        if _team_matches(selection, away_team):
            return "away_cover"
    if market == "over_under":
        if selection_lower in {"over", "o", "大", "大球"}:
            return "over"
        if selection_lower in {"under", "u", "小", "小球"}:
            return "under"
    return selection_lower


def _team_matches(left: str, right: str) -> bool:
    left_norm = _normalize_name(left)
    right_norm = _normalize_name(right)
    if not left_norm or not right_norm:
        return False
    return left_norm == right_norm or left_norm in right_norm or right_norm in left_norm


def _normalize_name(value: str) -> str:
    return " ".join(str(value or "").strip().lower().replace("_", " ").split())


def _snapshot_time(row: dict[str, Any]) -> datetime | None:
    return _parse_time(row.get("source_time_utc")) or _parse_time(row.get("fetched_at_utc"))


def _parse_time(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _line_group(market: str, line: float | None) -> str:
    if line is None:
        return "none"
    if market == "asian_handicap":
        return f"{abs(line):.3f}"
    return f"{line:.3f}"


def _candidate_line_group(market: str, line: Any) -> str:
    parsed = parse_float(line)
    if parsed is None:
        return "none"
    return _line_group(market, parsed)


def _has_complete_market(market: str, odds_by_selection: dict[str, Any]) -> bool:
    keys = set(odds_by_selection)
    if market == "h2h":
        return {"home", "draw", "away"}.issubset(keys)
    if market == "asian_handicap":
        return {"home_cover", "away_cover"}.issubset(keys)
    if market == "over_under":
        return {"over", "under"}.issubset(keys)
    return len(keys) >= 2
