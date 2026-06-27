#!/usr/bin/env python3
"""Poisson and Monte Carlo sanity checks for football scorelines.

This script intentionally accepts explicit expected-goals inputs. It does not
fetch data or decide whether the inputs are good.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from collections import Counter
from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple


Score = Tuple[int, int]


def poisson_pmf(lam: float, max_goals: int) -> List[float]:
    if lam < 0:
        raise ValueError("Expected goals must be non-negative")
    probs = [math.exp(-lam)]
    for goals in range(1, max_goals + 1):
        probs.append(probs[-1] * lam / goals)
    total = sum(probs)
    if total <= 0:
        raise ValueError("Invalid probability mass")
    return [p / total for p in probs]


def score_grid(home_xg: float, away_xg: float, max_goals: int) -> Dict[Score, float]:
    home_probs = poisson_pmf(home_xg, max_goals)
    away_probs = poisson_pmf(away_xg, max_goals)
    return {
        (home_goals, away_goals): hp * ap
        for home_goals, hp in enumerate(home_probs)
        for away_goals, ap in enumerate(away_probs)
    }


def poisson_sample(lam: float, rng: random.Random) -> int:
    threshold = math.exp(-lam)
    product = 1.0
    count = 0
    while True:
        count += 1
        product *= rng.random()
        if product <= threshold:
            return count - 1


def monte_carlo(home_xg: float, away_xg: float, simulations: int, seed: int) -> Dict[Score, float]:
    rng = random.Random(seed)
    scores: Counter[Score] = Counter()
    for _ in range(simulations):
        scores[(poisson_sample(home_xg, rng), poisson_sample(away_xg, rng))] += 1
    return {score: count / simulations for score, count in scores.items()}


def summarize(grid: Dict[Score, float], handicap_home: int | None) -> Dict[str, object]:
    home_win = sum(p for (h, a), p in grid.items() if h > a)
    draw = sum(p for (h, a), p in grid.items() if h == a)
    away_win = sum(p for (h, a), p in grid.items() if h < a)
    btts = sum(p for (h, a), p in grid.items() if h > 0 and a > 0)

    total_bands = {
        "0": sum(p for (h, a), p in grid.items() if h + a == 0),
        "1": sum(p for (h, a), p in grid.items() if h + a == 1),
        "2": sum(p for (h, a), p in grid.items() if h + a == 2),
        "3": sum(p for (h, a), p in grid.items() if h + a == 3),
        "4": sum(p for (h, a), p in grid.items() if h + a == 4),
        "5+": sum(p for (h, a), p in grid.items() if h + a >= 5),
        "under_2_5": sum(p for (h, a), p in grid.items() if h + a <= 2),
        "over_2_5": sum(p for (h, a), p in grid.items() if h + a >= 3),
    }

    result: Dict[str, object] = {
        "1x2": {"home": home_win, "draw": draw, "away": away_win},
        "total_goals": total_bands,
        "btts_yes": btts,
        "top_scores": [
            {"score": f"{h}-{a}", "probability": p}
            for (h, a), p in sorted(grid.items(), key=lambda item: item[1], reverse=True)[:12]
        ],
    }

    if handicap_home is not None:
        hhad_home = sum(p for (h, a), p in grid.items() if h + handicap_home > a)
        hhad_draw = sum(p for (h, a), p in grid.items() if h + handicap_home == a)
        hhad_away = sum(p for (h, a), p in grid.items() if h + handicap_home < a)
        result["home_handicap"] = handicap_home
        result["hhad"] = {"home": hhad_home, "draw": hhad_draw, "away": hhad_away}

    return result


def pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def print_human(args: argparse.Namespace, exact: Dict[str, object], mc: Dict[str, object] | None) -> None:
    print(f"{args.home} vs {args.away}")
    print(f"Input xG: {args.home} {args.home_xg:.2f}, {args.away} {args.away_xg:.2f}")
    print(f"Poisson grid max goals: {args.max_goals}")
    if args.handicap_home is not None:
        print(f"Home handicap: {args.handicap_home:+d}")
    print()

    one_x_two = exact["1x2"]
    print("1X2")
    print(f"  Home: {pct(one_x_two['home'])}")
    print(f"  Draw: {pct(one_x_two['draw'])}")
    print(f"  Away: {pct(one_x_two['away'])}")
    print()

    if "hhad" in exact:
        hhad = exact["hhad"]
        print("HHAD")
        print(f"  Home handicap win: {pct(hhad['home'])}")
        print(f"  Handicap draw: {pct(hhad['draw'])}")
        print(f"  Home handicap loss: {pct(hhad['away'])}")
        print()

    totals = exact["total_goals"]
    print("Total goals")
    print(
        "  "
        + ", ".join(
            [
                f"0={pct(totals['0'])}",
                f"1={pct(totals['1'])}",
                f"2={pct(totals['2'])}",
                f"3={pct(totals['3'])}",
                f"4={pct(totals['4'])}",
                f"5+={pct(totals['5+'])}",
            ]
        )
    )
    print(f"  Under 2.5: {pct(totals['under_2_5'])}; Over 2.5: {pct(totals['over_2_5'])}")
    print(f"  BTTS yes: {pct(exact['btts_yes'])}")
    print()

    print("Top scores")
    for score in exact["top_scores"]:
        print(f"  {score['score']}: {pct(score['probability'])}")

    if mc:
        print()
        print(f"Monte Carlo check ({args.simulations} simulations, seed {args.seed})")
        mc_1x2 = mc["1x2"]
        print(f"  1X2: H {pct(mc_1x2['home'])}, D {pct(mc_1x2['draw'])}, A {pct(mc_1x2['away'])}")
        if "hhad" in mc:
            mc_hhad = mc["hhad"]
            print(
                "  HHAD: "
                f"H {pct(mc_hhad['home'])}, D {pct(mc_hhad['draw'])}, A {pct(mc_hhad['away'])}"
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Poisson football match simulation checks.")
    parser.add_argument("--home", required=True, help="Home or listed first team name")
    parser.add_argument("--away", required=True, help="Away or listed second team name")
    parser.add_argument("--home-xg", required=True, type=float, help="Expected goals for home/listed team")
    parser.add_argument("--away-xg", required=True, type=float, help="Expected goals for away/listed team")
    parser.add_argument("--handicap-home", type=int, help="Home-team handicap, e.g. +1 or -1")
    parser.add_argument("--max-goals", type=int, default=8, help="Poisson grid cutoff per team")
    parser.add_argument("--simulations", type=int, default=0, help="Optional Monte Carlo simulations")
    parser.add_argument("--seed", type=int, default=26, help="Monte Carlo random seed")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of human-readable output")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.max_goals < 3:
        raise SystemExit("--max-goals must be at least 3")
    if args.simulations < 0:
        raise SystemExit("--simulations cannot be negative")

    exact_grid = score_grid(args.home_xg, args.away_xg, args.max_goals)
    exact = summarize(exact_grid, args.handicap_home)

    mc = None
    if args.simulations:
        mc_grid = monte_carlo(args.home_xg, args.away_xg, args.simulations, args.seed)
        mc = summarize(mc_grid, args.handicap_home)

    payload = {
        "home": args.home,
        "away": args.away,
        "home_xg": args.home_xg,
        "away_xg": args.away_xg,
        "max_goals": args.max_goals,
        "poisson": exact,
        "monte_carlo": mc,
    }

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print_human(args, exact, mc)


if __name__ == "__main__":
    main()
