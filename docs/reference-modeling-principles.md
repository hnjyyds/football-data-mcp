# Reference Modeling Principles

This repository should follow a small set of explicit modeling principles drawn
from the external work we trust most. The goal is to keep the stack honest:
use bookmaker information as a strong market prior, avoid overfitting to noisy
odds paths, and measure whether the model is actually adding value.

## 1. `penaltyblog`: market price can be a direct modeling input

Primary references:

- https://penaltyblog.readthedocs.io/en/latest/models/goal_expectancy.html
- https://penaltyblog.readthedocs.io/en/latest/api/implied.html

What to learn:

- A clean 1X2 market can already be enough to recover implied team scoring
  rates (`mu_home`, `mu_away`).
- Removing margin / overround is a first-class step, not an afterthought.
- Poisson / Dixon-Coles style goal models should often start from market
  probabilities instead of trying to beat them with historical features alone.

Repository rule:

- Prefer `current clean market probability -> implied goal expectancy ->
  scoreline model` over `long odds history -> bespoke pattern mining`.
- When a trusted current market exists, it is acceptable to work without full
  odds history.

## 2. `BeatTheBookie`: evaluation does not require dense odds history

Primary reference:

- https://arxiv.org/abs/1710.02824

What to learn:

- `closing odds` are already a high-value benchmark.
- A small `odds series` dataset can be useful, but it is not the minimum
  requirement for proving model value.
- The core question is whether the model beats the market on quality and price,
  not whether we stored every intraday tick.

Repository rule:

- The minimum useful audit set is:
  - prediction-time odds
  - closing odds or last pre-kickoff odds
  - final outcome
- Treat dense odds series as optional enrichment, not as a hard dependency.

## 3. Historical data + bookmaker odds should be fused, not separated

Primary reference:

- https://arxiv.org/abs/1802.08848

What to learn:

- Historical team strength and bookmaker odds should be combined.
- The right pattern is usually:
  - historical information supplies structured prior / team strength
  - current bookmaker odds supply the strongest market anchor
- This is a fusion problem, not a replacement problem.

Repository rule:

- Historical form, Elo, and team-strength features should remain context /
  priors unless validation proves they improve the market-anchored baseline.
- Market odds should stay the main observed anchor for match-specific
  probability.

## Practical architecture decisions for this repo

1. Sparse odds snapshots are enough.

- Keep only the anchor prices that matter most:
  - `opening`
  - `decision`
  - `latest`
  - `closing`
- Do not design the system around a requirement for full dense odds curves.

2. CLV is the default market-value audit.

- Positive CLV is the simplest early sign that the model is not obviously
  paying worse-than-market prices.
- If CLV is persistently negative, reduce trust even when hit rate looks good.

3. Current market quality matters more than historical volume.

- One clean current 1X2 market is often more useful than many low-quality noisy
  historical points.
- Quality gates should block malformed, stale, or access-broken odds instead of
  filling gaps with invented movement.

4. Dense history is optional, not forbidden.

- If dense series becomes available, use it for secondary research only:
  - movement diagnostics
  - timing analysis
  - market microstructure experiments
- Do not make the main recommendation path depend on it.

## Anti-patterns

Avoid these:

- Assuming missing full odds history means the model cannot be evaluated.
- Treating all intraday odds points as equally informative.
- Letting historical strength features override a clean current market without
  holdout evidence.
- Using movement-only narratives to justify picks when current price and CLV do
  not support them.
