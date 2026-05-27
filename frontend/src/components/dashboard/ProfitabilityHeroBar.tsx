import { Icon } from "../shared/Icon";
import type { DashboardProfitabilityForecast } from "../../types";

function pct(n: number | null | undefined, digits = 1): string {
  if (n == null) return "—";
  return `${(n * 100).toFixed(digits)}%`;
}

export function ProfitabilityHeroBar({ forecast }: { forecast?: DashboardProfitabilityForecast }) {
  // Empty / loading state
  if (!forecast?.available) {
    return (
      <div className="rounded-xl border border-ink-200 dark:border-ink-700 bg-ink-50 dark:bg-ink-800/60 px-4 py-3 flex items-center gap-3">
        <Icon name="hourglass" size={18} className="text-ink-400" />
        <div className="flex-1 min-w-0">
          <div className="text-sm font-semibold text-ink-900 dark:text-white">
            盈利预估暂未启用
          </div>
          <div className="text-2xs text-ink-500 dark:text-ink-400 mt-0.5">
            {forecast?.interpretation ?? `需要至少 ${forecast?.min_required ?? 5} 个已结算样本（当前 ${forecast?.settled_count ?? 0}）`}
          </div>
        </div>
      </div>
    );
  }

  const state = forecast.model_state ?? "insufficient_data";

  // Losing state — model is currently unprofitable
  if (state === "losing") {
    const breakEven = forecast.break_even_hit_rate_needed ?? 0;
    const gap = forecast.hit_rate_gap ?? 0;
    return (
      <div className="rounded-xl border border-danger-500/40 bg-gradient-to-r from-danger-500/10 to-danger-500/5 dark:from-danger-900/30 dark:to-danger-900/10 px-4 py-3 shadow-sm animate-slide-up">
        <div className="flex flex-col sm:flex-row sm:items-center gap-3">
          <Icon name="error" size={22} className="text-danger-600 dark:text-danger-500 flex-shrink-0" />
          <div className="min-w-0 flex-1">
            <div className="text-sm font-bold text-ink-900 dark:text-white">
              ⚠️ 模型当前在亏损 — 无法证明盈利路径
            </div>
            <div className="text-2xs text-ink-700 dark:text-ink-300 mt-1">
              命中率 <strong className="tabular-nums text-danger-600 dark:text-danger-500">{pct(forecast.observed_hit_rate)}</strong> ·
              单笔 ROI <strong className="tabular-nums text-danger-600 dark:text-danger-500">{pct(forecast.implied_roi_per_bet)}</strong> ·
              需要 <strong className="tabular-nums">{pct(breakEven)}</strong> 才能盈亏平衡（差 {pct(gap)}）
            </div>
            <div className="text-2xs text-ink-500 dark:text-ink-400 mt-1">
              💡 当务之急：重跑 holdout validation 检查 log-loss vs 市场基线，确认是否需要换模型/数据源
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Marginal edge — can't reach significance in reasonable time
  if (state === "marginal_edge") {
    return (
      <div className="rounded-xl border border-warning-500/40 bg-gradient-to-r from-warning-500/10 to-warning-500/5 dark:from-warning-900/30 dark:to-warning-900/10 px-4 py-3 shadow-sm animate-slide-up">
        <div className="flex flex-col sm:flex-row sm:items-center gap-3">
          <Icon name="warn" size={22} className="text-warning-600 dark:text-warning-500 flex-shrink-0" />
          <div className="min-w-0 flex-1">
            <div className="text-sm font-bold text-ink-900 dark:text-white">
              边际过小，难以统计验证
            </div>
            <div className="text-2xs text-ink-700 dark:text-ink-300 mt-1">
              命中率 <strong className="tabular-nums">{pct(forecast.observed_hit_rate)}</strong> ·
              单笔 ROI <strong className="tabular-nums">{pct(forecast.implied_roi_per_bet)}</strong> ·
              需要 &gt;100000 笔才能证明
            </div>
            <div className="text-2xs text-ink-500 dark:text-ink-400 mt-1">
              💡 建议：收紧候选过滤（提高 min_calibrated_probability 到 0.65+）或改进特征工程
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Profitable state
  const remaining = forecast.remaining_bets ?? 0;
  const total = forecast.required_bets_total ?? 1;
  const sofar = forecast.settled_bets_so_far ?? 0;
  const progress = Math.max(0, Math.min(100, (sofar / total) * 100));
  const isReady = remaining === 0;
  const remainingDays = forecast.remaining_days;

  const accentBg = isReady
    ? "bg-gradient-to-r from-success-500/15 to-success-500/5 dark:from-success-500/25 dark:to-success-500/10 border-success-500/40"
    : "bg-gradient-to-r from-brand-500/15 via-brand-500/5 to-strike-500/10 dark:from-brand-700/30 dark:via-brand-900/20 dark:to-strike-900/20 border-brand-400/40";

  return (
    <div className={`rounded-xl border ${accentBg} px-4 py-3 shadow-sm animate-slide-up`}>
      <div className="flex flex-col sm:flex-row sm:items-center gap-3">
        <div className="flex items-center gap-2 min-w-0 flex-1">
          {isReady ? (
            <Icon name="production" size={22} className="text-success-600 dark:text-success-500 flex-shrink-0 animate-tick" />
          ) : (
            <Icon name="target" size={20} className="text-brand-600 dark:text-brand-400 flex-shrink-0" />
          )}
          <div className="min-w-0">
            <div className="text-sm font-bold text-ink-900 dark:text-white">
              {isReady
                ? `🎉 已达 ${pct(forecast.confidence_level, 0)} 统计置信度`
                : `还需 ${remaining} 笔 ≈ ${remainingDays ?? "?"} 天可证明盈利`}
            </div>
            <div className="text-2xs text-ink-600 dark:text-ink-300 mt-0.5">
              当前命中率 <strong className="tabular-nums">{pct(forecast.observed_hit_rate)}</strong> ·
              单笔 ROI <strong className="tabular-nums">{pct(forecast.implied_roi_per_bet)}</strong> ·
              每天约 <strong className="tabular-nums">{forecast.settled_per_day_estimate}</strong> 笔已结算
            </div>
          </div>
        </div>
        <div className="flex items-center gap-3 flex-shrink-0">
          <div className="flex-1 sm:w-40">
            <div className="h-2 rounded-full bg-ink-200 dark:bg-ink-700 overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-700 ${
                  isReady
                    ? "bg-gradient-to-r from-success-400 to-success-600"
                    : "bg-gradient-to-r from-brand-400 to-brand-600"
                }`}
                style={{ width: `${progress}%` }}
              />
            </div>
            <div className="flex justify-between text-2xs text-ink-500 dark:text-ink-400 mt-1 tabular-nums">
              <span>{sofar}</span>
              <span>{total}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
