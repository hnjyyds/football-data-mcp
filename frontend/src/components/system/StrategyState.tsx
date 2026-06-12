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
    <section className="surface-panel overflow-hidden">
      <div className="flex items-center gap-2 px-4 pt-4 pb-2">
        <Icon name="settingsAlt" size={14} className="text-ink-400 dark:text-ink-500" />
        <span className="text-sm font-semibold text-ink-950 dark:text-white flex-1">策略状态</span>
        <Badge variant={toneVariant(tone)}>{statusLabel}</Badge>
      </div>
      <div className="grid grid-cols-2 gap-2 px-4 pb-4 sm:grid-cols-3 lg:grid-cols-2 xl:grid-cols-3">
        {rows.map(([label, value, valueTone]) => {
          const toneClass =
            valueTone === "good"
              ? "text-emerald-700 dark:text-emerald-300"
              : valueTone === "bad"
              ? "text-red-700 dark:text-red-300"
              : "text-ink-950 dark:text-white";
          return (
            <div key={label} className="clean-card px-3 py-2">
              <div className="metric-label">{label}</div>
              <div className={`mt-1 text-sm font-semibold tabular-nums ${toneClass}`}>{value}</div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
