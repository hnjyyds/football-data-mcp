import { ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine, ZAxis } from "recharts";
import { Icon } from "../shared/Icon";

export type ReliabilityPoint = {
  predicted: number;  // model probability (0~1)
  actual: number;     // empirical hit rate (0~1)
  samples: number;    // bucket size
  bucket?: string;
};

/**
 * Reliability diagram (calibration plot).
 *
 * - X axis: model-predicted probability bucket midpoint
 * - Y axis: empirical hit rate
 * - Dot size: sample count in that bucket
 * - 45° dashed line: perfect calibration
 * - Dots above the line = model UNDERCONFIDENT (good outcomes happen more)
 * - Dots below the line = model OVERCONFIDENT (the danger zone)
 */
export function ReliabilityDiagram({
  points,
  title = "概率校准 (Reliability Diagram)",
  subtitle,
}: {
  points: ReliabilityPoint[];
  title?: string;
  subtitle?: string;
}) {
  if (!points.length) {
    return (
      <div className="card p-6 text-center text-ink-500 dark:text-ink-400 text-sm">
        <Icon name="chart" size={24} className="mx-auto mb-2 opacity-40" />
        暂无校准数据
      </div>
    );
  }

  const data = points.map(p => ({
    x: p.predicted,
    y: p.actual,
    z: Math.max(8, Math.min(120, p.samples * 4)),
    bucket: p.bucket ?? `[${p.predicted.toFixed(2)}]`,
    samples: p.samples,
  }));

  // Compute average calibration error
  const avgError = points.reduce((sum, p) => sum + Math.abs(p.actual - p.predicted), 0) / points.length;
  const errorPct = (avgError * 100).toFixed(1);
  const errorTone = avgError < 0.05 ? "text-success-600 dark:text-success-500" : avgError < 0.10 ? "text-warning-600 dark:text-warning-500" : "text-danger-600 dark:text-danger-500";

  return (
    <section className="card overflow-hidden">
      <div className="px-3 py-2 border-b border-ink-100 dark:border-ink-800 flex items-center justify-between">
        <div>
          <div className="text-sm font-semibold text-ink-900 dark:text-white">{title}</div>
          {subtitle && <div className="text-2xs text-ink-500 dark:text-ink-400 mt-0.5">{subtitle}</div>}
        </div>
        <span className={`text-2xs font-semibold tabular-nums ${errorTone}`}>
          平均校准误差: {errorPct}%
        </span>
      </div>
      <div className="p-3">
        <ResponsiveContainer width="100%" height={260}>
          <ScatterChart margin={{ top: 8, right: 12, bottom: 8, left: -8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.18)" />
            <XAxis
              type="number"
              dataKey="x"
              domain={[0, 1]}
              ticks={[0, 0.2, 0.4, 0.5, 0.6, 0.8, 1.0]}
              tickFormatter={(v) => `${Math.round(v * 100)}%`}
              tick={{ fontSize: 10, fill: "#64748b" }}
              stroke="#cbd5e1"
              label={{ value: "模型预测概率", position: "insideBottom", offset: -2, style: { fontSize: 10, fill: "#64748b" } }}
            />
            <YAxis
              type="number"
              dataKey="y"
              domain={[0, 1]}
              ticks={[0, 0.2, 0.4, 0.5, 0.6, 0.8, 1.0]}
              tickFormatter={(v) => `${Math.round(v * 100)}%`}
              tick={{ fontSize: 10, fill: "#64748b" }}
              stroke="#cbd5e1"
              label={{ value: "实际命中率", angle: -90, position: "insideLeft", style: { fontSize: 10, fill: "#64748b" } }}
            />
            <ZAxis type="number" dataKey="z" range={[40, 400]} />
            <Tooltip
              contentStyle={{
                backgroundColor: "rgba(255,255,255,0.96)",
                border: "1px solid #e2e8f0",
                borderRadius: "8px",
                fontSize: "12px",
                padding: "6px 10px",
              }}
              formatter={(value, name) => {
                const key = String(name ?? "");
                if (key === "x") return [`${(Number(value) * 100).toFixed(1)}%`, "预测"];
                if (key === "y") return [`${(Number(value) * 100).toFixed(1)}%`, "实际"];
                if (key === "z") return [String(Math.round(Number(value) / 4)), "样本数"];
                return [String(value), key];
              }}
            />
            <ReferenceLine
              segment={[{ x: 0, y: 0 }, { x: 1, y: 1 }]}
              stroke="#1aa6ab"
              strokeDasharray="4 4"
              label={{ value: "完美校准", position: "insideTopLeft", fontSize: 9, fill: "#1aa6ab" }}
            />
            <Scatter
              data={data}
              fill="#f6720c"
              fillOpacity={0.7}
              stroke="#b53908"
              strokeWidth={1}
            />
          </ScatterChart>
        </ResponsiveContainer>
        <div className="mt-2 grid grid-cols-2 gap-2 text-2xs text-ink-500 dark:text-ink-400">
          <div className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-strike-500" />
            散点 = 概率桶（大小=样本量）
          </div>
          <div className="flex items-center gap-1">
            <span className="w-2 h-0.5 bg-brand-500" />
            45° = 完美校准对角线
          </div>
          <div className="col-span-2 text-ink-500/80 dark:text-ink-400/80 italic">
            散点在对角线上方 = 模型保守（实际更好）；下方 = 模型过度自信
          </div>
        </div>
      </div>
    </section>
  );
}
