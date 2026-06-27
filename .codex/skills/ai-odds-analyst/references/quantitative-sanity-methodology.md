# Quantitative Sanity Methodology

Use this reference when odds conversion, no-vig probability, model forecasts, xG/Poisson score clusters, prediction-market prices, or calibration review could improve the analysis.

Quantitative checks are a challenge layer, not the final analyst. They help expose hidden assumptions and price burden; they do not replace web-verified Jingcai odds, football context, or the final `首选` / `本场不选` discipline.

## Market Mechanics Translation

Borrow the data discipline of edge, scoring, variance, and market efficiency, but translate it into Jingcai research language:

- `市场隐含概率`: what the current price is charging after normalization.
- `分析置信带`: a bounded analyst probability range, not a single fake-precise number, and only when evidence is strong enough to state one.
- `证据差`: analyst confidence minus market-implied estimate. Treat this as a prompt for scrutiny, not as an automatic action.
- `误差缓冲`: the minimum gap required to overcome source uncertainty, model error, lineup timing, and market efficiency. Thin gaps are `无优势/只支持方向`.
- `决策质量`: whether the pre-match process was sound, independent of whether the result happened to win.
- `结果质量`: the match result; useful for scoring, but never enough to rewrite the pre-match process.

Use these terms to sharpen `赔率补偿` and `价值`, while keeping the final output inside Jingcai market/result analysis.

## Allowed Uses

- Convert odds into implied probability and no-vig estimates to understand market burden.
- Compare Jingcai HAD/HHAD/TTG structure against overseas 1X2, Asian handicap, exchange, or prediction-market prices when the event identity and timestamp are aligned.
- Use xG, shot maps, Elo-style ratings, Poisson models, or public forecasts as independent sanity checks for winner, goal range, and exact-margin clusters.
- Use historical predictions and results to review calibration, Brier-style error, and repeated market-expression mistakes.
- Use model disagreement to ask better football questions: lineup, motivation, tactical matchup, sample size, stale data, or market overreaction.
- Use market efficiency as a guardrail: if the market is liquid, current, and widely covered, require a specific information advantage before calling a line mispriced.

## Hard Boundaries

- Do not output Kelly criterion, bankroll fraction, unit size, stake amount, or an instruction to place a bet.
- Do not call no-vig probability `真实概率`; label it `市场隐含/去水估计`.
- Do not average model, market, and football lanes into a fake precision number when the assumptions differ.
- Do not use a model result when match identity, home/away order, venue, or lineup timing is unresolved.
- Do not let model confidence override a weak or unavailable Jingcai source ledger.
- Do not call a 1-3 percentage point probability gap meaningful when source quality, vig, lineup uncertainty, or model error can easily explain it.
- Do not evaluate a method from fewer than roughly 30 comparable settled stances except as anecdotal learning; small samples are variance-heavy.

## Probability Checks

For decimal odds:

1. `implied probability = 1 / odds`
2. `overround = sum(implied probabilities) - 1`
3. `no-vig estimate = implied probability / sum(implied probabilities)`

Use the result to answer:

- Which outcome is carrying the price burden?
- Is the draw being protected despite favorite heat?
- Does HHAD imply a stronger or weaker margin than the football lane?
- Does TTG imply a goal band that fits the tactical script?
- Are outside markets materially more aggressive or cautious than Jingcai?

If the difference is material, write it as `概率校验冲突` and explain what must be investigated before selecting.

## Edge and Evidence Margin

Use edge-style thinking only as a research audit:

1. Establish `市场隐含概率` from current verified odds when possible.
2. State `分析置信带` only if the football lane has enough evidence. Example: `偏主方向，但只能给 48-55% 区间`.
3. Compare the band to the market estimate:
   - `清晰高于市场`: possible value only if source quality, lineup, and market expression also pass.
   - `接近市场`: no analytical edge; prefer `观察`, `只支持方向`, or `本场不选`.
   - `低于市场`: market price is too expensive for the football risk; downgrade.
4. Apply `误差缓冲`: require a wider gap when sources are weak, league liquidity is low, lineups are pending, or model assumptions are stale.
5. Translate the result into Jingcai language: `赔率补偿足`, `赔率补偿不足`, `价格已吃掉优势`, or `概率校验无优势`.

Never output "bet" or "pass" from this calculation. The final stance remains exact Jingcai market/result or `本场不选`.

## Market Efficiency and Information Advantage

Before calling a price wrong, answer:

- What information do we have that the market may not have fully priced: lineup, tactical matchup, motivation, schedule, weather, venue, or source mismatch?
- Is the market liquid and mature, or thin and narrative-driven?
- Is public heat likely to distort the obvious side?
- Is the apparent edge just model overconfidence, stale data, or a home/away/neutral-site mismatch?

If there is no specific information advantage, downgrade claims from `价值` to `市场价格合理`, `只支持方向`, or `本场不选`.

## Model Sanity Checks

When a public model or local calculation is available, record:

- source or method name
- data recency and competition coverage
- inputs visible to the method, such as xG, shots, Elo, injuries, or lineups
- blind spots, such as missing current lineups, neutral venue, tournament incentives, weather, or tactical matchup
- output direction: winner, draw risk, goal range, and score cluster

Translation rules:

- Model says favorite strongly wins, but football lane shows sterile attack or draw-acceptable table state: downgrade favorite margin and test 防平/让球 protection.
- Model says low goals, but both teams must chase: inspect whether the model is using season averages that miss match-state incentives.
- Model says upset/draw, but Jingcai and football lane support favorite: treat it as `反证`, not automatic cold selection; find the football reason.
- Model and football lane agree, but Jingcai price is thin: the conclusion may still be `只支持方向` or `本场不选` if compensation is gone.

## Forecast Extremizing Guardrail

When several independent forecasts or models agree, modestly sharpen the qualitative confidence only if:

- the sources are genuinely independent, not copies of the same odds feed or model family
- each source is using current match identity, lineup timing, and venue correctly
- the agreement is about the same Jingcai expression, not merely the broad winner direction

Do not extremize when forecasts share the same stale injury feed, bookmaker-derived prior, public ranking narrative, or missing motivation context. In that case, treat agreement as duplicated evidence and keep confidence capped.

## Calibration Review

When reviewing past analyses, keep a simple scorecard:

| Date | Match | Stated stance | Optional probability | Result | Exact stance hit? | Calibration note | Lesson |
| --- | --- | --- | --- | --- | --- | --- | --- |

Judge in this order:

1. Did the exact `首选` hit?
2. Was `本场不选` correct if no clean market existed?
3. If a probability was stated, was it overconfident or underconfident?
4. Did the miss come from football read, source quality, market expression, price burden, or model misuse?
5. Was the sample large enough to infer a pattern, or is this only one variance-heavy result?

Use Brier-style thinking only for learning. The user-facing postmortem should still end with reusable Jingcai rules, not a statistics lecture.

## Scoring and Calibration

When enough settled records exist, group optional probability bands and check calibration:

| Band | Count | Hit rate | Note |
| --- | --- | --- | --- |
| 40-49% |  |  |  |
| 50-59% |  |  |  |
| 60-69% |  |  |  |
| 70%+ |  |  |  |

Use Brier-style error only when a numeric probability was recorded before kickoff:

`Brier = (probability - outcome)^2`

Interpretation:

- High confidence misses are more serious than low confidence misses.
- A winning pick can still be bad process if the stated probability was inflated or the market expression was wrong.
- A losing pick can be acceptable process if evidence, source quality, and market expression were sound.
- Do not claim calibration improvement from tiny samples; require repeated settled stances in comparable markets.

## Variance and Sample-Size Discipline

Do not over-learn from short runs:

- Fewer than 10 settled stances: anecdotal only.
- 10-29 settled stances: look for obvious process errors, not hit-rate conclusions.
- 30-99 settled stances: begin checking calibration bands and repeated miss types.
- 100+ settled stances: stronger evidence about process quality, source reliability, and market-expression bias.

For high-volatility observations, exact scores, half/full, and `让平`, expect wider variance. Judge whether the pre-match evidence named the right score cluster and failure mode before changing the method.

## Output Requirement

When quantitative checks are used, include a compact `概率/模型校验` section:

- `市场隐含`: no-vig or normalized market estimate and source.
- `分析置信带`: optional range when evidence supports it; omit instead of faking precision.
- `证据差/误差缓冲`: whether the gap is large enough after source and model uncertainty.
- `模型/统计信号`: xG, Elo, Poisson, public forecast, or unavailable.
- `一致点`: where it agrees with football and Jingcai source reads.
- `冲突点`: where it contradicts them and why that matters.
- `裁断`: whether it upgrades confidence, downgrades confidence, changes the Jingcai expression, or only remains background.
