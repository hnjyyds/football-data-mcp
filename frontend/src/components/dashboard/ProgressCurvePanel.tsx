import { useMemo } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { BacktestCurveView } from "../../types";
import { Badge, toneVariant } from "../shared/Badge";
import { Metric, Panel } from "../shared/Panel";

function shortDateLabel(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    timeZone: "Asia/Shanghai",
  }).format(date);
}

export function ProgressCurvePanel({ backtestCurve }: { backtestCurve: BacktestCurveView }) {
  const points = backtestCurve?.points ?? [];
  const daily = useMemo(() => {
    const buckets = new Map<string, { dateText: string; cumulative: number; cumulativeHitRate: number | null }>();
    for (const point of points) {
      const key = shortDateLabel(point.atUtc);
      if (!key || key === "—") continue;
      buckets.set(key, {
        dateText: key,
        cumulative: point.cumulativeValue,
        cumulativeHitRate: point.cumulativeHitRateValue,
      });
    }
    return Array.from(buckets.values());
  }, [points]);
  const today = daily[daily.length - 1] ?? null;
  const yesterday = daily[daily.length - 2] ?? null;
  const cumulativeDelta = today && yesterday ? today.cumulative - yesterday.cumulative : null;
  const hitDelta = today && yesterday && today.cumulativeHitRate != null && yesterday.cumulativeHitRate != null
    ? today.cumulativeHitRate - yesterday.cumulativeHitRate
    : null;
  const summaryText = !today
    ? "还没有足够的结算历史来判断今天是否比昨天更好。"
    : !yesterday
      ? `当前仅有 ${today.dateText} 的走势数据，继续积累后再比较昨日变化。`
      : `相较 ${yesterday.dateText}，${today.dateText} 的累计收益${cumulativeDelta != null ? ` ${cumulativeDelta >= 0 ? "增加" : "减少"} ${Math.abs(cumulativeDelta).toFixed(2)}` : "暂不可比"}，总体命中率${hitDelta != null ? ` ${hitDelta >= 0 ? "变化" : "回落"} ${Math.abs(hitDelta * 100).toFixed(1)}%` : "暂不可比"}。`;

  return (
    <Panel title="模型长期表现曲线" icon="chart" badge={backtestCurve.title}>
      <div className="mb-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-3 dark:border-slate-700 dark:bg-slate-900/40">
        <div className="flex flex-wrap items-center gap-2 mb-1">
          <Badge variant={toneVariant(backtestCurve.tone)}>
            {today && yesterday
              ? cumulativeDelta != null && cumulativeDelta >= 0
                ? "较昨日改善"
                : "较昨日承压"
              : "等待对比"}
          </Badge>
          <span className="text-sm font-semibold text-slate-900 dark:text-white">今天 vs 昨天</span>
        </div>
        <div className="text-xs leading-relaxed text-slate-600 dark:text-slate-300">{summaryText}</div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
        {backtestCurve.metrics.map((metric) => (
          <Metric key={metric.label} label={metric.label} value={metric.value} />
        ))}
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <div className="rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-700 dark:bg-slate-950">
          <div className="mb-2 text-xs font-semibold text-slate-900 dark:text-white">累计收益曲线</div>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={points} margin={{ top: 6, right: 12, bottom: 6, left: -12 }}>
              <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.15} />
              <XAxis dataKey="index" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip
                formatter={(value) => [typeof value === "number" ? value.toFixed(2) : String(value ?? "—"), "累计收益"]}
                labelFormatter={(label) => `第 ${label} 场`}
              />
              <ReferenceLine y={0} stroke="#94a3b8" strokeDasharray="4 4" />
              <Line type="monotone" dataKey="cumulativeValue" stroke="#14b8a6" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-700 dark:bg-slate-950">
          <div className="mb-2 text-xs font-semibold text-slate-900 dark:text-white">总体命中率累计曲线</div>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={points} margin={{ top: 6, right: 12, bottom: 6, left: -12 }}>
              <CartesianGrid strokeDasharray="3 3" strokeOpacity={0.15} />
              <XAxis dataKey="index" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} domain={[0, 1]} tickFormatter={(value) => `${Math.round(value * 100)}%`} />
              <Tooltip
                formatter={(value) => [typeof value === "number" ? `${(value * 100).toFixed(1)}%` : String(value ?? "—"), "总体命中率"]}
                labelFormatter={(label) => `第 ${label} 场`}
              />
              <ReferenceLine y={0.5} stroke="#94a3b8" strokeDasharray="4 4" />
              <Line type="monotone" dataKey="cumulativeHitRateValue" stroke="#f59e0b" strokeWidth={2} dot={false} connectNulls />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </Panel>
  );
}
