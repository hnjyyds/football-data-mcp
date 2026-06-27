# GitHub Football Model Selection

Use this reference when the user asks for GitHub football prediction projects, simulation engines, or "which repo is accurate".

## Preferred Stack

For a practical Codex skill, prefer a composable stack:

1. `soccerdata`: data acquisition from sources such as Club Elo, ESPN, FBref, Football-Data.co.uk, Sofascore, Understat, and WhoScored.
2. `penaltyblog`: football modelling utilities, including Poisson/Dixon-Coles style match models and probability tools.
3. `ai-odds-analyst`: web-verified fundamentals, team news, motivation, Jingcai odds audit, and final market mapping.
4. This skill: scenario simulation and model sanity checks.

Reason: end-to-end "prediction apps" often look complete but hide data leakage, weak evaluation, or stale data. A composable stack keeps sources, assumptions, and judgement auditable.

## Candidate Repo Tiers

### Tier A: Libraries and Data Infrastructure

- `probberechts/soccerdata`
  - Role: data scraper/loader.
  - Strength: broad football data-source coverage and strong community signal.
  - Limitation: not a prediction engine by itself.
- `martineastwood/penaltyblog`
  - Role: model and probability toolkit.
  - Strength: practical football analytics API; suitable for Poisson/Dixon-Coles modelling.
  - Limitation: inputs and calibration remain the analyst's responsibility.
- `ML-KULeuven/socceraction`
  - Role: event-data action valuation with VAEP/xT.
  - Strength: serious soccer analytics foundation.
  - Limitation: requires event data and is not a quick match predictor.

### Tier B: End-To-End Predictors To Inspect

- `kochlisGit/ProphitBet-Soccer-Bets-Predictor`
  - Role: machine-learning soccer prediction app.
  - Strength: higher community signal than many small predictor repos and includes multiple ML methods.
  - Audit focus: check data leakage, feature dates, backtest split, and whether tournament/international matches are supported.
- `DOsinga/football_predictions`
  - Role: transparent historical-result based predictions.
  - Strength: simple and inspectable.
  - Audit focus: limited tactical/team-news coverage.

### Tier C: New World Cup 2026-Specific Repos

- Repos such as `letmefind/Fifa2026-Prediction-Skill` may match the current task vocabulary: Elo, xG, Poisson, Monte Carlo, tournament simulation.
- Treat them as experimental unless they have reproducible tests, backtests, and active real pre-match tracking.
- Do not equate recent update activity with accuracy.

## Accuracy Audit Checklist

Ask these before trusting any repo:

- Does it publish predictions before kickoff, or only examples after results are known?
- Does it report Brier score, log loss, calibration, or expected calibration error?
- Does it compare against a baseline such as bookmaker no-vig probabilities, Elo-only, or home-favorite heuristics?
- Does it separate train/validation/test by time, not random shuffling across future matches?
- Does it avoid features that would be unavailable before kickoff?
- Does it support international tournaments, neutral venues, extra rest, and group-stage incentives?
- Does it expose raw probabilities and score distributions, not only "winner" labels?
- Can the model be run locally with documented data dependencies?
- Are data sources current, legal, and robust?

## Red Flags

- README says "90%+ accuracy" without a dated test set.
- The model predicts only win/draw/loss labels without calibrated probabilities.
- The repo has no clear data timestamping.
- It trains and tests on randomly split match rows.
- It optimizes for hit rate while ignoring odds, calibration, and draw probability.
- It cannot explain scoreline or handicap distributions.
- It requires opaque paid data or an unavailable API for basic use.

## Recommended Integration Pattern

Use GitHub projects as replaceable engines behind a stable analyst workflow:

```text
web current facts -> assumptions ledger -> simulator/model -> score clusters
                 -> odds-source audit -> Jingcai mapping -> final adjudication
```

If model and fundamentals agree, confidence can rise only when odds-source quality and market mapping also agree. If they conflict, state which input is likely missing: lineup, tactical matchup, stale data, motivation, small sample, or price overreaction.
