import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";

type ChartPoint = {
  label: string;
  [key: string]: number | string | null | undefined;
};

const COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6"];

export function OddsChart({
  points,
  lines,
  title,
  yLabel,
  referenceValue,
}: {
  points: ChartPoint[];
  lines: string[];
  title?: string;
  yLabel?: string;
  referenceValue?: number;
}) {
  if (!points.length) {
    return (
      <div className="flex items-center justify-center h-36 text-slate-400 dark:text-slate-500 text-sm rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800">
        暂无图表数据
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 shadow-sm p-4">
      {title && <div className="font-semibold text-slate-900 dark:text-white text-sm mb-3">{title}</div>}
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={points} margin={{ top: 4, right: 4, bottom: 4, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" className="dark:[&>line]:stroke-slate-700" />
          <XAxis dataKey="label" tick={{ fontSize: 11 }} stroke="#94a3b8" />
          <YAxis tick={{ fontSize: 11 }} stroke="#94a3b8" label={yLabel ? { value: yLabel, angle: -90, position: "insideLeft", style: { fontSize: 10, fill: "#94a3b8" } } : undefined} />
          <Tooltip
            contentStyle={{
              backgroundColor: "var(--tw-bg-opacity,1)",
              border: "1px solid #e2e8f0",
              borderRadius: "8px",
              fontSize: "12px",
            }}
          />
          {referenceValue != null && (
            <ReferenceLine y={referenceValue} stroke="#94a3b8" strokeDasharray="4 4" />
          )}
          {lines.map((key, i) => (
            <Line
              key={key}
              type="monotone"
              dataKey={key}
              stroke={COLORS[i % COLORS.length]}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4 }}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
