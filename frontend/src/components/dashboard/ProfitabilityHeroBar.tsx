import { Rocket, Hourglass, Target } from "lucide-react";
import type { DashboardProfitabilityForecast } from "../../types";

function pct(n: number | null | undefined, digits = 1): string {
  if (n == null) return "—";
  return `${(n * 100).toFixed(digits)}%`;
}

export function ProfitabilityHeroBar({ forecast }: { forecast?: DashboardProfitabilityForecast }) {
  if (!forecast?.available) {
    return (
      <div className="rounded-xl border border-ink-200 dark:border-ink-700 bg-ink-50 dark:bg-ink-800/60 px-4 py-3 flex items-center gap-3">
        <Hourglass size={18} className="text-ink-400" />
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
            <Rocket size={22} className="text-success-600 dark:text-success-500 flex-shrink-0 animate-tick" />
          ) : (
            <Target size={20} className="text-brand-600 dark:text-brand-400 flex-shrink-0" />
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
