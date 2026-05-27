import { useMemo } from "react";

export type HeatMapCell = {
  x: string;
  y: string;
  value: number;        // 数值（例如命中率 0~1，或 ROI -0.2~+0.2）
  sampleSize?: number;  // 样本数（决定透明度）
  tooltip?: string;
};

type Props = {
  cells: HeatMapCell[];
  xLabels: string[];       // 列标签（例如联赛）
  yLabels: string[];       // 行标签（例如盘口类型）
  title?: string;
  subtitle?: string;
  /** 值范围。color: diverging 时以 0 为中心（命中率用 [0,1]，ROI 用 [-0.2, 0.2]） */
  domain?: [number, number];
  /** sequential: 单色渐变（默认）；diverging: 双向（红-灰-绿）适合 ROI */
  scale?: "sequential" | "diverging";
  formatValue?: (v: number) => string;
};

function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

function colorForValue(
  value: number,
  scale: "sequential" | "diverging",
  domain: [number, number]
): string {
  const [lo, hi] = domain;
  const clamped = Math.max(lo, Math.min(hi, value));
  if (scale === "diverging") {
    // 红 → 浅灰 → 绿
    const mid = (lo + hi) / 2;
    if (clamped < mid) {
      const t = (mid - clamped) / (mid - lo);
      const r = Math.round(lerp(248, 220, t));
      const g = Math.round(lerp(250, 38, t));
      const b = Math.round(lerp(252, 38, t));
      return `rgb(${r}, ${g}, ${b})`;
    } else {
      const t = (clamped - mid) / (hi - mid);
      const r = Math.round(lerp(248, 16, t));
      const g = Math.round(lerp(250, 185, t));
      const b = Math.round(lerp(252, 129, t));
      return `rgb(${r}, ${g}, ${b})`;
    }
  } else {
    // sequential 单色品牌色渐变
    const t = (clamped - lo) / Math.max(hi - lo, 1e-9);
    const r = Math.round(lerp(238, 13, t));
    const g = Math.round(lerp(252, 132, t));
    const b = Math.round(lerp(251, 136, t));
    return `rgb(${r}, ${g}, ${b})`;
  }
}

export function HeatMap({
  cells,
  xLabels,
  yLabels,
  title,
  subtitle,
  domain = [0, 1],
  scale = "sequential",
  formatValue = (v) => `${(v * 100).toFixed(1)}%`,
}: Props) {
  const cellMap = useMemo(() => {
    const map = new Map<string, HeatMapCell>();
    for (const c of cells) map.set(`${c.x}::${c.y}`, c);
    return map;
  }, [cells]);

  // 计算最大样本量用于透明度
  const maxSample = Math.max(1, ...cells.map((c) => c.sampleSize ?? 1));

  if (!xLabels.length || !yLabels.length) {
    return (
      <div className="card p-6 text-center text-ink-500 dark:text-ink-400 text-sm">
        暂无热力图数据
      </div>
    );
  }

  return (
    <section className="card overflow-hidden">
      {(title || subtitle) && (
        <div className="px-3 py-2 border-b border-ink-100 dark:border-ink-800">
          {title && <div className="text-sm font-semibold text-ink-900 dark:text-white">{title}</div>}
          {subtitle && <div className="text-2xs text-ink-500 dark:text-ink-400 mt-0.5">{subtitle}</div>}
        </div>
      )}
      <div className="p-3 overflow-x-auto">
        <table className="border-separate border-spacing-0.5">
          <thead>
            <tr>
              <th className="w-24" />
              {xLabels.map((x) => (
                <th key={x} className="text-2xs font-medium text-ink-500 dark:text-ink-400 px-1 pb-1 text-left rotate-[-30deg] origin-bottom-left h-8 whitespace-nowrap">
                  {x}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {yLabels.map((y) => (
              <tr key={y}>
                <td className="text-2xs font-medium text-ink-700 dark:text-ink-300 pr-2 text-right whitespace-nowrap">
                  {y}
                </td>
                {xLabels.map((x) => {
                  const cell = cellMap.get(`${x}::${y}`);
                  if (!cell) {
                    return (
                      <td
                        key={x}
                        className="w-10 h-7 rounded bg-ink-100/40 dark:bg-ink-800/40"
                        title={`${y} × ${x}: 无样本`}
                      />
                    );
                  }
                  const bg = colorForValue(cell.value, scale, domain);
                  const opacity = 0.3 + (0.7 * (cell.sampleSize ?? 1)) / maxSample;
                  const text = cell.value > (domain[0] + domain[1]) / 2 + (domain[1] - domain[0]) * 0.3 ? "white" : "rgba(15,23,42,0.85)";
                  return (
                    <td
                      key={x}
                      className="w-10 h-7 rounded text-center text-2xs font-medium tabular-nums cursor-default"
                      style={{ backgroundColor: bg, opacity, color: text }}
                      title={cell.tooltip ?? `${y} × ${x}: ${formatValue(cell.value)} (n=${cell.sampleSize ?? "-"})`}
                    >
                      {formatValue(cell.value)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
        {/* Legend */}
        <div className="mt-3 flex items-center gap-2 text-2xs text-ink-500 dark:text-ink-400">
          <span>{formatValue(domain[0])}</span>
          <div
            className="flex-1 h-2 rounded-full max-w-[160px]"
            style={{
              background: scale === "diverging"
                ? "linear-gradient(to right, rgb(220,38,38), rgb(248,250,252), rgb(16,185,129))"
                : "linear-gradient(to right, rgb(238,252,251), rgb(13,132,136))",
            }}
          />
          <span>{formatValue(domain[1])}</span>
          <span className="ml-2 text-ink-400 dark:text-ink-500">透明度 = 样本量</span>
        </div>
      </div>
    </section>
  );
}
