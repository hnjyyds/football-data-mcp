export type ScorelineCell = {
  home_goals: number;
  away_goals: number;
  probability: number;
};

type Props = {
  scorelines: ScorelineCell[];
  homeTeam?: string;
  awayTeam?: string;
  maxGoals?: number;
  title?: string;
};

export function ScoreMatrix({
  scorelines,
  homeTeam = "主队",
  awayTeam = "客队",
  maxGoals = 5,
  title = "比分概率热点",
}: Props) {
  if (!scorelines?.length) {
    return (
      <div className="card p-6 text-center text-ink-500 dark:text-ink-400 text-sm">
        暂无比分分布数据
      </div>
    );
  }

  // Find max probability for normalization
  const maxProb = Math.max(...scorelines.map((s) => s.probability));

  // Build lookup
  const lookup = new Map<string, number>();
  for (const s of scorelines) {
    lookup.set(`${s.home_goals}-${s.away_goals}`, s.probability);
  }

  return (
    <section className="card overflow-hidden">
      <div className="px-3 py-2 border-b border-ink-100 dark:border-ink-800 flex items-center justify-between">
        <div className="text-sm font-semibold text-ink-900 dark:text-white">{title}</div>
        <div className="text-2xs text-ink-500 dark:text-ink-400">{homeTeam} 主队进球 × {awayTeam} 客队进球</div>
      </div>
      <div className="p-3 flex justify-center overflow-x-auto">
        <table className="border-separate border-spacing-0.5">
          <thead>
            <tr>
              <th className="w-8 h-7 text-2xs text-ink-400">→</th>
              {Array.from({ length: maxGoals + 1 }, (_, ag) => (
                <th key={ag} className="w-9 h-7 text-2xs font-medium text-ink-600 dark:text-ink-400">
                  {ag}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Array.from({ length: maxGoals + 1 }, (_, hg) => (
              <tr key={hg}>
                <td className="w-8 h-9 text-2xs font-medium text-ink-600 dark:text-ink-400 text-center">{hg}</td>
                {Array.from({ length: maxGoals + 1 }, (_, ag) => {
                  const prob = lookup.get(`${hg}-${ag}`) ?? 0;
                  const intensity = maxProb > 0 ? prob / maxProb : 0;
                  const isDiagonal = hg === ag;
                  const isHomeWin = hg > ag;
                  // 主队胜：青色；平局：灰色；客队胜：橙色
                  const hue = isDiagonal ? [148, 163, 184] : isHomeWin ? [26, 166, 171] : [246, 114, 12];
                  const bg = `rgba(${hue.join(",")}, ${0.08 + intensity * 0.78})`;
                  const isPeak = prob === maxProb && prob > 0;
                  return (
                    <td
                      key={ag}
                      className={`w-9 h-9 rounded text-center text-2xs tabular-nums cursor-default ${
                        isPeak ? "ring-2 ring-strike-400 font-bold" : ""
                      }`}
                      style={{ backgroundColor: bg, color: intensity > 0.5 ? "white" : "rgb(15,23,42)" }}
                      title={`${hg}-${ag}: ${(prob * 100).toFixed(2)}%`}
                    >
                      {prob > 0.01 ? (prob * 100).toFixed(1) : ""}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="px-3 py-2 border-t border-ink-100 dark:border-ink-800 flex items-center gap-3 text-2xs text-ink-500 dark:text-ink-400">
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-brand-500/60" />主胜</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-ink-400/40" />平局</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm bg-strike-500/60" />客胜</span>
        <span className="ml-auto">⬛ 最高概率</span>
      </div>
    </section>
  );
}
