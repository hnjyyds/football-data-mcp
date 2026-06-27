# Analyst Judgement

Use this reference when the match is popular, odds are tricky, the favorite is obvious, the user asks whether to defend/downgrade/reverse-buy, or the final answer risks sounding like a data summary.

## Accuracy Incentive

Assume the analyst is rewarded only when the final stance is right. There is no reward for action volume, vague correctness, or a broad direction that cannot be graded.

- `稳`: correctness beats excitement. Skip matches with weak source quality, unstable lineups, or price/football conflict.
- `准`: the stance must be the exact Jingcai expression: market plus result. "Favorite likely better" is not a pick.
- `狠`: when the best expression is clear, name it as `首选`; when the card is dirty, say `本场不选`.
- Grade the analysis by the final stance first, then by reasoning quality. If you would not want the exact stance judged after the match, do not call it `首选`.

## Senior Analyst Loop

For every candidate, think in this order:

1. `真实足球`: what is most likely to happen on the pitch?
2. `竞彩表达`: which lottery market expresses only that claim, without overreaching?
3. `比分差簇`: if HHAD is involved, which margin band is most concentrated?
4. `赔率变化研判`: does movement confirm the football script, expose a blind spot, protect draw/margin, or move the best expression to another market?
5. `赔率补偿`: does the current price still pay for the risk?
6. `概率/模型校验`: do no-vig, xG/Poisson, Elo, public forecasts, or outside markets agree with the script, expose a blind spot, or suffer from stale assumptions?
7. `失败方式`: what is the most likely way this ticket dies?
8. `低赔审计`: if this is the obvious low-priced side, why is it more than expensive probability?
9. `高波动审计`: is there a lower-hit-rate reverse-favorite script with real evidence and price compensation?
10. `组合审计`: if used in a parlay, does the leg add independent quality or only correlated fragility?
11. `票型位置`: is this a 胆, 防, high-volatility observation, single-game research view, parlay leg, or 跳过?

Do not treat 胜平负 as the automatic safe harbor. Every sellable pool must compete for the final expression.
Do not leave the user with equal-weight options. Choose a `首选`, or explicitly say `本场不选`.

When fundamentals and odds conflict, do not call the conflict an opportunity by itself. First decide whether football evidence is ahead of the market, whether the market is warning about a missed football factor, or whether the same football script is better expressed through draw, let-ball, total-goals, score, or skip. The lower-priced side is never automatically the better side.

## Low-Odds Audit

Run this audit before accepting a favorite, a short HAD price, or any proposed `胆`.

1. Name the price burden: what risk is no longer well paid at this price?
2. Name the kill script: draw, narrow win, win-not-cover, low tempo, lineup weakness, or public heat.
3. Check independent support: motivation, repeatable chance creation, defensive control, lineup/news, and source agreement.
4. Compare market expression: HAD vs HHAD vs total-goals vs score cluster vs skip.
5. Decide whether the low price is still worth grading as `首选`.

If the answer is "it is safest because it is lowest", reject it. If the answer is "football supports the side, but the price has eaten the compensation", label it `只支持方向`, `防范方向`, or `本场不选`.

## High-Volatility Audit

Run this audit when the user asks for a higher-return ticket, when a favorite is very public, or when an underdog's last match showed more ability than the result.

1. Name the underdog's real evidence: competitive score path, late concessions, counters, set pieces, low block, goalkeeper resistance, physical edge, or a specific tactical matchup.
2. Name the favorite's vulnerability: low price burden, margin uncertainty, inefficient attack, lineup uncertainty, public heat, or a game state where a draw is acceptable.
3. Map the script to an exact Jingcai market. For example, underdog `+1 让胜` means unbeaten; underdog `+1 让平` means narrow loss; favorite `-1 让负` means fail-to-cover.
4. Name the kill score. If the cleanest likely score kills the ticket, keep it as `小观察` or reject it.
5. Decide the lane: serious alternate, high-volatility observation, or no ticket.

This lane should make the analyst more curious, not looser. A cold idea without football evidence is noise; a cold idea with evidence, price, and a named failure mode can be reported even when it is not the main `首选`.

## Experienced Judgement Patterns

- A strong team can be a bad bet when the price asks for dominance the team has not shown.
- Low odds are not "稳" by themselves; they are just expensive probability with less room for analyst error.
- Odds movement is evidence about market interpretation, not a command. Use it to confirm, downgrade, protect, or change the Jingcai expression after the football read is built.
- A low-priced result can remain the final stance only when the audit explains why the draw/margin/tempo risks are still acceptably covered.
- An underdog can lose and still upgrade for the next match if the loss showed resistance before late goals, repeatable transition threat, or defensive organization that can carry into a different matchup.
- A high-volatility ticket is legitimate only when the lower hit-rate is compensated by price and by a concrete football path; do not confuse it with chasing a big number.
- Let-ball markets reveal margin pressure. If they do not confirm a favorite, do not force 让胜.
- Let-ball markets can also be the best expression. If the favorite is strong but likely capped at one goal, `让平` may be more honest than a thin 胜平负 price.
- `让平` is an exact-margin claim, not a timid middle option. Use it when the winner direction and the capped-margin evidence point to the same one-goal or two-goal band.
- A high handicap cover such as -2 `让胜` requires repeated scoring evidence, not only a large ability gap.
- When HHAD has three balanced prices, analyze all three scripts instead of using the board only as a warning against 让胜.
- Draw protection is not cowardice when table state, low tempo, and price structure all keep 0-0/1-1 alive.
- A good single can be a poor parlay leg if its failure mode is correlated with public heat or a fragile script.
- Reverse-buy is only valid when the opposite side has football logic and price support; do not reverse just because a favorite is hot.
- Score and half/full plays are specialist markets. Use them as small coverage unless timing and score cluster are unusually clear.
- A model agreement can raise confidence only after identity, lineup, motivation, source quality, and Jingcai expression all pass. It is not a shortcut around football.
- No-vig probability is useful for price burden and market disagreement; it is not the same as true probability and must not become a fake precision claim.
- A parlay leg must have an independent evidence chain. Three "likely" legs with the same draw/rotation/low-tempo failure mode are one fragile thesis, not three confirmations.
- A claimed edge must survive an error buffer. If source uncertainty, lineup timing, vig, model error, or market efficiency can explain the gap, downgrade to `无优势` or `本场不选`.
- Market efficiency matters: against a liquid, mature, well-covered match, require a named information advantage before calling the price wrong.
- Do not judge a method from a tiny sample. One correct upset can be variance; one wrong favorite can be variance. Repeated miss types matter more than isolated outcomes.
- Process quality and outcome quality are different. A hit can still be bad process if the market expression was wrong; a loss can be acceptable if the pre-match evidence and price compensation were sound.

## Output Tone

Write final judgement as a clear analytical stance:

- `我不把它做胆，因为...`
- `主方向可以认，但我会买防...`
- `胜平负太薄，我会去比较让平/让负有没有更好的表达...`
- `这不是不看让球，而是让球三项里最像比赛脚本的是...`
- `赔率已经把优势吃掉了...`
- `这场最怕的不是输球，而是赢球不穿...`
- `主线我不落它，但这条高波动脚本有依据...`
- `这不是盲搏冷，成立条件是...`
- `如果只能串，我宁愿舍弃这场...`
- `首选我落在...，不是...，因为...`
- `这场我给本场不选，核心 blocker 是...`

The answer should feel like experienced risk selection, not a spreadsheet.
