# Deep Analysis Output

Use this reference whenever the user asks to analyze a match, several matches, a parlay, or criticizes missing reasoning. A conclusion table is not enough unless the user explicitly asks for a quick scan.

## Default Structure

For each match, output the analysis process before the final pick:

1. `赔率源核验`
   - source ledger, source tier, official/public status, canonical match id/name reconciliation, opening/current odds, unverified gaps, confidence downgrade
2. `战意和小组形势`
   - points, ranking, goal difference, remaining opponents, win/draw/loss consequences, and match-behavior impact
3. `基本面`
   - standings, points, ranking, qualification pressure, motivation, schedule, injuries, lineup/news
4. `近期战绩和上一场`
   - last one to three matches, how goals happened, whether attack/defense signals are repeatable
5. `战术画像`
   - formation, defensive block, pressing, counter channels, set pieces, attacking dependence, matchup conflicts
6. `赔率变化和市场结构`
   - HAD, HHAD, total-goals, score/half-full if used, public heat, whether odds support the football claim
7. `公开统计、概率/模型校验和比分簇`
   - xG/shots if available, no-vig market estimate/model signal, optional analyst confidence band, score clusters, chance quality, and whether the statistical signal is compatible with Jingcai
8. `反证审查`
   - strongest reasons the pick may fail: draw, win-not-cover, low total, lineup trap, source uncertainty, price overheat
9. `竞彩映射`
   - candidate board for 胜平负, 让球胜平负, 总进球, 比分, 半全场; explain which market expresses the best-supported script
10. `高波动票观察`
   - only when justified: exact market/result, upset or reverse-favorite script, evidence, conditions, price compensation, and kill score
11. `综合结论`
   - decisive stance: 首选 or 本场不选, confidence, caveat, rejected alternatives, and what new info would change the view

## Broad Match Scans

When analyzing multiple matches, do not stop at a summary table. Use:

1. a one-screen priority table
2. detailed per-match sections for each candidate that remains playable or controversial
3. a final ticket/combo section explaining why some matches are included, downgraded, protected, or excluded

For a large slate, it is acceptable to mark low-quality matches as `跳过` in the table, but any match suggested for single/parlay/useful防 must have the full feature-by-feature reasoning.

## Combination Structure Review

Use this section for 串关, 混合过关, 胆, or slate screening. Keep it analytical and do not output stake sizing.

| Leg | Market/result | Role | Source grade | Main failure mode | Correlation risk | Decision |
| --- | --- | --- | --- | --- | --- | --- |

Role labels:

- `稳胆`: high source quality, clear football lane, odds support, clean Jingcai expression, and low correlated fragility.
- `防点`: main direction exists but draw, margin, total-goals, or lineup risk must be protected.
- `高波动观察`: lower-hit-rate alternate with evidence and price compensation, not a stabilizer.
- `剔除`: source, lineup, market, or correlation risk makes it a poor combination leg.

Decision rules:

- Exclude a leg if its best argument is only low odds, public favorite strength, or "needed to raise payout".
- Downgrade when several selected legs share the same failure mode: favorite heat, draw acceptability, low tempo, rotation, or narrow-win risk.
- Downgrade when diversification is fake: multiple legs rely on the same public favorite narrative, stale lineup assumption, or market-derived model signal.
- Explain why the final structure is smaller or more selective when adding another leg weakens the whole ticket.
- If no clean combination exists, say `组合结构不成立` instead of forcing a parlay.

## Feature Point Discipline

For every important feature, write:

- `事实`: what was observed and from which source
- `解释`: why it matters for this matchup
- `竞彩影响`: which market it supports or weakens
- `反向风险`: how the same fact could mislead
- `数据质量`: when relevant, whether the source is current, complete, identity-matched, or only a model/stat sanity check

Do not compress this into one sentence like "主胜可做胆" or "赔率偏薄". Explain the path from evidence to pick.

## Market Candidate Board

For every playable or controversial match, include:

| 玩法 | 候选结果 | 对应脚本 | 支撑点 | 反证点 | 价格负担 | 赔率补偿 | 结论 |
| --- | --- | --- | --- | --- | --- | --- | --- |

Required comparisons:

- Add `比分差簇` to the board when HHAD is in play: exact one-goal, exact two-goal, three-plus, draw/favorite-fails, or underdog-cover band.
- Compare low-priced 胜平负 against HHAD, not only against `跳过`.
- For every low-priced result, state the price burden: what draw, margin, tempo, lineup, or heat risk is no longer well paid.
- Add `概率校验` or explain in prose when no-vig/model checks materially support or contradict a row.
- When claiming `赔率补偿` or `价值`, state the market-implied estimate, analyst confidence band if available, and why the gap survives source/model uncertainty.
- For HHAD, analyze `让胜`, `让平`, and `让负` as separate scripts.
- For `让平`, explain why the exact-margin band is more concentrated than raw win, cover, total-goals, or skip.
- If the final view stays with 胜平负, explain why HHAD's extra price is not worth the margin risk.
- If HHAD is stronger, explain why its margin script is more precise than the raw win direction.
- If total-goals is stronger than side/margin, explain why tempo and score cluster are clearer than result.

## High-Volatility Ticket Observation

Use this section when the user asks for high-volatility ideas or when an underdog/reverse-favorite script has real football evidence but should not become the main `首选`.

Do not produce a high-volatility line merely because the odds are large. It must pass a separate evidence test:

- The underdog's previous loss showed ability, not only a better-looking final score: competitive game state, late concessions, counters, set pieces, physical defending, goalkeeper form, or tactical discipline.
- The favorite's main line has a clear weakness: low price burden, uncertain margin, sterile open-play creation, lineup/rotation concern, or a public story that may be ahead of the football.
- The Jingcai market maps cleanly to the script, such as underdog `+1 让胜` for unbeaten, `+1 让平` for narrow loss, favorite `-1 让负` for fail-to-cover, or HAD `平/负` for outright upset/draw.
- The ticket has a named death path. If the most natural match script kills it, say so and keep it as observation or reject it.

Output format:

- `高波动观察`: exact market/result, or `无`.
- `成立条件`: one to three match conditions.
- `基本面证据`: concise evidence chain.
- `赔率补偿`: whether price compensates the lower hit-rate and why.
- `最怕比分`: the cleanest losing score.
- `与主线关系`: serious alternate, small observation, or rejected after audit.

## Final Synthesis

The final conclusion must integrate the feature points, not merely repeat them:

- strongest supporting chain
- strongest opposing chain
- why the chosen Jingcai market is narrower or safer than alternatives
- when quantitative checks are used: market-implied estimate, confidence band, evidence gap, and whether it survives the error buffer
- `首选`: one exact Jingcai market and result, or `本场不选`
- `次选/防点`: one optional alternate or protection when justified
- `高波动观察`: one optional lower-hit-rate exact market/result when justified, clearly separated from the main stance
- `放弃`: tempting markets rejected and why
- `改变条件`: new info that would move the stance
- For parlays: `组合结构`: included legs, protected legs, excluded legs, and the shared failure mode to watch

Do not end with equal options. If two options are close, make the stronger one `首选` and the other `次选/防点`.

The `首选` must be gradeable after the match: exact Jingcai market plus exact result. If the analysis can only say "the favorite is better" or "the game leans low-scoring" without a clean market expression, the correct final stance is `本场不选` or a lower-confidence `次选/防点`, not a forced pick.

If the `首选` is the lowest-priced obvious side, explicitly say why it survived the low-odds audit. If the reasoning is only probability, reputation, or "更稳", downgrade it before finalizing.

The high-volatility observation must never be worded as a safer replacement for `首选`. It is a researched alternate script: plausible, lower hit-rate, price-sensitive, and easy to kill if the match follows the favorite's clean path.
