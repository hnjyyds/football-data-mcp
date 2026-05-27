import { useMemo } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
  Legend,
} from "recharts";

export type MovementPoint = {
  t: string;              // 时间戳（ISO 或 friendly label）
  [bookmaker: string]: string | number | null | undefined;
};

type Props = {
  points: MovementPoint[];
  bookmakers: string[];        // 要绘制的庄家/系列名（数据键）
  title?: string;
  subtitle?: string;
  yLabel?: string;
  /** 当前模型概率隐含赔率（参考线） */
  modelImpliedOdds?: number | null;
  /** 开赛时间（参考线） */
  kickoffMarker?: string | null;
};

const SERIES_COLORS = [
  "#1aa6ab", // brand
  "#f6720c", // strike
  "#0ea5e9", // info
  "#8b5cf6", // purple
  "#ef4444", // danger
  "#10b981", // success
  "#f59e0b", // warning
  "#64748b", // ink
];

function fmtTime(value: string | number): string {
  if (typeof value === "number") return String(value);
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }).format(d);
}

export function LineMovementChart({
  points,
  bookmakers,
  title,
  subtitle,
  yLabel = "赔率",
  modelImpliedOdds,
  kickoffMarker,
}: Props) {
  const data = useMemo(() => {
    return points.map((p) => {
      const out: Record<string, any> = { t: p.t, tLabel: fmtTime(p.t) };
      for (const b of bookmakers) out[b] = p[b];
      return out;
    });
  }, [points, bookmakers]);

  if (!points.length || !bookmakers.length) {
    return (
      <div className="card p-6 text-center text-ink-500 dark:text-ink-400 text-sm">
        暂无走线数据
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
      <div className="p-3">
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={data} margin={{ top: 6, right: 12, bottom: 6, left: -10 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.2)" />
            <XAxis
              dataKey="tLabel"
              tick={{ fontSize: 10, fill: "#64748b" }}
              stroke="#cbd5e1"
              minTickGap={28}
            />
            <YAxis
              tick={{ fontSize: 10, fill: "#64748b" }}
              stroke="#cbd5e1"
              domain={["auto", "auto"]}
              label={yLabel ? { value: yLabel, angle: -90, position: "insideLeft", style: { fontSize: 10, fill: "#64748b" } } : undefined}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: "rgba(255,255,255,0.96)",
                border: "1px solid #e2e8f0",
                borderRadius: "8px",
                fontSize: "12px",
                padding: "6px 10px",
              }}
              labelStyle={{ color: "#64748b", fontSize: "10px", fontWeight: 500 }}
              formatter={(value: any) => (typeof value === "number" ? value.toFixed(2) : "—")}
            />
            <Legend wrapperStyle={{ fontSize: "10px", paddingTop: "6px" }} iconSize={8} />
            {modelImpliedOdds != null && (
              <ReferenceLine
                y={modelImpliedOdds}
                stroke="#f6720c"
                strokeDasharray="5 3"
                label={{ value: "模型隐含", position: "right", fontSize: 9, fill: "#f6720c" }}
              />
            )}
            {kickoffMarker && (
              <ReferenceLine
                x={fmtTime(kickoffMarker)}
                stroke="#ef4444"
                strokeDasharray="3 3"
                label={{ value: "开赛", position: "top", fontSize: 9, fill: "#ef4444" }}
              />
            )}
            {bookmakers.map((b, i) => (
              <Line
                key={b}
                type="monotone"
                dataKey={b}
                stroke={SERIES_COLORS[i % SERIES_COLORS.length]}
                strokeWidth={1.5}
                dot={false}
                activeDot={{ r: 3 }}
                connectNulls
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}
