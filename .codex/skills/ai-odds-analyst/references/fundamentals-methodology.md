# Fundamentals Methodology

Use this reference for any single-match Jingcai analysis, parlay leg, strong favorite, draw-protection decision, postmortem, or user challenge about team strength, tactics, form, or motivation.

## Web-First Fundamentals

Before final judgement, browse current sources for football context. Do not rely only on rankings or odds.

Collect:

1. Last one to three matches for each team: results, score path, xG/shots if available, chance quality, set pieces, substitutions, and whether goals came from open play, penalties, own goals, or keeper errors.
2. Tactical shape: starting formation, defensive block height, wingback/fullback roles, counterattack channels, pressing intensity, target striker use, set-piece routines, and whether the shape changes when leading or drawing.
3. Attack/defense diagnosis: chance creation vs finishing, repeated low-quality shots, dependence on one creator, striker drought, vulnerability to direct balls, crosses, counters, or second balls.
4. Key players and competitive form: recent minutes, fitness rhythm, starting continuity, scoring/assisting reliability, chance creation, defensive influence, set-piece role, matchup fit, and whether the star is sharp, rusty, isolated, overloaded, or returning from injury.
5. Team state: injuries/illness/suspensions, travel/fatigue, rotation, manager comments, schedule, and weather/venue when relevant.
6. Table context summary: points, ranking/standing, goal difference, qualification pressure, remaining opponents, and whether one point is acceptable. For full war-intent analysis, also read [motivation-methodology.md](motivation-methodology.md).
7. Data coverage: whether the competition has reliable public xG, event stats, lineup feeds, injury feeds, player minutes, and team schedule data. Mark unsupported or stale feeds instead of treating missing data as neutral.

Prefer official match centres, Opta/StatsPerform, FotMob/Sofascore-style stat pages, ESPN/BBC/Guardian-style reports, and reputable regional coverage. Use at least two sources when the tactical read is important. If you cannot verify a tactical point, label it as unverified and do not build a bet on it.

## Data Tool Cross-Checks

Use public sports-data tools, football APIs, xG databases, and modelling packages as structured evidence when available.

- Use schedule/standings/team-search tools to reduce name ambiguity, not to bypass source verification.
- Use event statistics, xG, shot maps, and player stats to test whether recent goals were repeatable, but check sample size, opponent quality, game state, and red cards before upgrading confidence.
- Use lineup, formation, missing-player, and player-minute data to verify key-player claims. If sources disagree, cap the fundamentals confidence.
- Use Transfermarkt-style squad value, Elo-style ratings, or power rankings only as broad strength priors. They do not prove current form, tactical fit, motivation, or margin.
- Use Poisson/xG projections as score-cluster sanity checks, especially for total-goals and exact-margin markets. If the model output ignores lineups or tournament incentives, state that limitation.
- When a data skill or API returns no coverage for a competition, say `数据覆盖不足` and lean harder on current web reporting and source confidence.

## Tactical Translation

Translate fundamentals into Jingcai risk:

- Strong favorite but recent open-play scoring is weak: downgrade `让胜`, high 总进球, 比分, and 胆 confidence.
- Favorite produces many shots but few clear chances or no open-play goals: treat low-score draw or narrow win as live.
- Favorite depends on one winger/creator or target striker: check availability and matchup; absence or poor form should reduce margin expectations.
- Key attacker is available but rusty, minutes-capped, isolated, or coming off illness/injury: do not treat name value as current output; cap win-margin and high-goal confidence.
- Key creator/striker is in sharp form with stable minutes and repeatable chance involvement: upgrade attack reliability only if team structure and matchup also support supply.
- Key defender, goalkeeper, or holding midfielder is missing or in poor form: raise concession, counterattack, set-piece, and late-game failure risk.
- Underdog uses a low block plus counters/set pieces: increase 防平, 让球防平/负, and small-score probability.
- Underdog can accept one point: do not assume it will open the game after 0-0 unless group situation forces it.
- Underdog conceded chances to a weaker side last match: separate defensive weakness from tactical choice. If it can tighten shape against a favorite, do not mechanically project the opener into another open game.
- Travel/fatigue or off-field disruption can reduce tempo, but do not assume collapse unless the match evidence confirms it.

## Loss-But-Competitive Read

Do not automatically downgrade a team because it lost the previous match. Look for whether the loss contained transferable strength.

Upgrade or protect the underdog when several of these are verified:

- It stayed in the match until late before conceding separation goals.
- It created repeatable routes: counters, wide outlets, set pieces, second balls, or target-forward layoffs.
- Its defensive block forced the favorite into low-quality shots or long sterile possession.
- The final score was inflated by stoppage-time goals, keeper errors, red cards, or game-state chasing.
- Its key attacking outlets still looked fit and involved.
- The next opponent has a different weakness that makes those routes more usable.

Translate this carefully:

- If the underdog can plausibly avoid defeat, test HAD draw/upset or `+1 让胜`.
- If the favorite is still likely to win but the underdog showed resistance, test `+1 让平` or favorite fail-to-cover instead.
- If the loss exposed repeated high-quality chances conceded, do not promote the underdog just because the score stayed close for a while.

## Belgium-Iran Tactical Lesson

The miss should have triggered a tactical downgrade before kickoff:

- Belgium's previous 1-1 with Egypt was not a clean attacking confirmation. Their equalizer came from an own goal forced after Lukaku entered; Belgium had not shown reliable open-play finishing.
- Belgium carried a World Cup scoring drought into the Iran game: many attempts, little conversion, and dependence on Doku/Lukaku/De Bruyne moments rather than a stable chance machine.
- Doku had been a bright spark against Egypt, but he missed the Iran game through illness. That reduced one of Belgium's best ways to unbalance a compact block.
- Lukaku's presence helped force the Egypt own goal, but his World Cup scoring drought and lack of recent starts made `主胜+大球/让胜` fragile.
- Iran's 2-2 with New Zealand showed two sides: defensive vulnerability to direct play, but also useful attacking routes through Taremi, Rezaeian, crosses, and second-phase pressure.
- Against Belgium, Iran used a veteran back-five/wingback structure, protected the box, relied on Beiranvand, and still carried counter/set-piece danger through Taremi, Hajsafi/Ezatolahi/Rezaeian actions.
- Therefore, the better pre-match translation was not "Belgium ranking high, so主胜胆/大球"; it was "Belgium likely stronger, but open-play reliability and Iran's low-block/counter plan require 防平 or 让球防平/负, with small-score protection."

## Required Output

Every serious analysis should include:

- `战意和小组形势`: not just "needs points"; spell out win/draw/loss consequences and game-state incentives.
- `近期战绩和上一场`: not just W-D-L, but how the result happened.
- `关键球员状态`: who materially upgrades or weakens the script, including current form rather than name value.
- `战术画像`: how each team attacks and defends.
- `进攻可靠性`: whether goals are repeatable or came from low-repeat events.
- `数据覆盖`: which structured stats or lineup feeds were available, stale, conflicting, or missing.
- `对位风险`: which tactical feature can break the favored script.
- `竞彩影响`: 胜平负, 让球, 总进球, 比分, and whether to 防平/反买.
