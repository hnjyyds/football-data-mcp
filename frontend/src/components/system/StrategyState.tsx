import { Icon } from "../shared/Icon";
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
  const statusLabel = state.status === "live_calibration_active"
    ? "实时校准中"
    : state.status === "collecting_samples"
    ? "样本收集中"
    : state.status ?? "—";
  const tone = isActive ? "good" : "neutral";

  const rows: Array<[string, string, string?]> = [
    ["命中率", fmtPct(state.hit_rate)],
    ["ROI", state.roi != null ? `${(state.roi * 100).toFixed(1)}%` : "—", (state.roi ?? 0) > 0 ? "good" : (state.roi ?? 0) < 0 ? "bad" : "neutral"],
    ["样本数", String(state.sample_count ?? "—")],
    ["最低概率", fmtPct(state.min_calibrated_probability)],
    ["赔率区间", `${fmt(state.min_decimal_odds)} ~ ${fmt(state.max_decimal_odds)}`],
    ["最低边际", fmtPct(state.min_value_edge)],
    ["先验强度", fmt(state.prior_strength, 0)],
  ];

  return (
    <section className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 shadow-sm overflow-hidden">
      <div className="flex items-center gap-2 px-3 py-2 border-b border-slate-100 dark:border-slate-700/50">
        <Icon name="settingsAlt" size={14} className="text-ink-500 dark:text-ink-400" />
        <span className="font-semibold text-slate-900 dark:text-white text-sm flex-1">策略状态</span>
        <Badge variant={toneVariant(tone)}>{statusLabel}</Badge>
      </div>
      <div className="divide-y divide-slate-50 dark:divide-slate-700/30">
        {rows.map(([label, value, valueTone]) => {
          const toneClass =
            valueTone === "good"
              ? "text-emerald-600 dark:text-emerald-400"
              : valueTone === "bad"
              ? "text-red-600 dark:text-red-400"
              : "text-slate-900 dark:text-white";
          return (
            <div key={label} className="flex items-center justify-between px-3 py-1.5">
              <span className="text-xs text-slate-600 dark:text-slate-400">{label}</span>
              <span className={`text-xs font-semibold tabular-nums ${toneClass}`}>{value}</span>
            </div>
          );
        })}
      </div>
    </section>
  );
}
