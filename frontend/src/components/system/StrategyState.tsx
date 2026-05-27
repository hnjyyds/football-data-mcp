import type { DashboardSnapshot } from "../../types";
import { Badge, toneVariant } from "../shared/Badge";

function fmt(v: number | null | undefined, digits = 2): string {
  if (v == null) return "—";
  return typeof v === "number" ? v.toFixed(digits) : String(v);
}
function fmtPct(v: number | null | undefined): string {
  if (v == null) return "—";
  return `${(v * 100).toFixed(1)}%`;
}

export function StrategyStateCard({ snapshot }: { snapshot: DashboardSnapshot }) {
  const state = snapshot.strategy_state;
  if (!state) return null;

  const isActive = state.active;
  const statusLabel = state.status === "live_calibration_active" ? "实时校准中" : state.status === "collecting_samples" ? "样本收集中" : state.status ?? "—";
  const tone = isActive ? "good" : "neutral";

  const metrics = [
    { label: "最低概率", value: fmtPct(state.min_calibrated_probability) },
    { label: "最低赔率", value: fmt(state.min_decimal_odds) },
    { label: "最高赔率", value: fmt(state.max_decimal_odds) },
    { label: "最低边际", value: fmtPct(state.min_value_edge) },
    { label: "样本数", value: String(state.sample_count ?? "—") },
    { label: "命中率", value: fmtPct(state.hit_rate) },
    { label: "ROI", value: state.roi != null ? `${(state.roi * 100).toFixed(1)}%` : "—" },
    { label: "先验强度", value: fmt(state.prior_strength, 0) },
  ];

  return (
    <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 shadow-sm p-4">
      <div className="flex items-center justify-between mb-3">
        <span className="font-semibold text-slate-900 dark:text-white text-sm">策略状态</span>
        <Badge variant={toneVariant(tone)}>{statusLabel}</Badge>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {metrics.map((m) => (
          <div key={m.label}>
            <div className="text-xs text-slate-500 dark:text-slate-400 mb-0.5">{m.label}</div>
            <div className="text-sm font-semibold tabular-nums text-slate-900 dark:text-white">{m.value}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
