import { Icon } from "../shared/Icon";
import type { DashboardProfitabilityForecast } from "../../types";

function pct(n: number | null | undefined, digits = 1): string {
  if (n == null) return "—";
  return `${(n * 100).toFixed(digits)}%`;
}

function num(n: number | null | undefined): string {
  if (n == null) return "—";
  return String(n);
}

export function ProfitabilityPanel({ forecast }: { forecast?: DashboardProfitabilityForecast }) {
  if (!forecast?.available) {
    return (
      <section className="card overflow-hidden">
        <div className="px-3 py-2 border-b border-ink-100 dark:border-ink-800 flex items-center gap-2">
          <Icon name="trendUp" size={14} className="text-ink-500" />
          <span className="font-semibold text-ink-900 dark:text-white text-sm">盈利时间预估</span>
        </div>
        <div className="p-4 text-center">
          <Icon name="alert" size={28} className="mx-auto text-ink-400 dark:text-ink-500 mb-2" />
          <div className="text-sm text-ink-600 dark:text-ink-400">
            {forecast?.interpretation ?? "需要更多结算样本"}
          </div>
          <div className="text-2xs text-ink-400 dark:text-ink-500 mt-1">
            最低 {forecast?.min_required ?? 5} 个 · 当前 {forecast?.settled_count ?? 0} 个
          </div>
        </div>
      </section>
    );
  }

  const state = forecast.model_state ?? "insufficient_data";
  if (state === "losing") {
    return (
      <section className="card overflow-hidden border-danger-500/30">
        <div className="px-3 py-2 border-b border-danger-500/20 flex items-center gap-2">
          <Icon name="error" size={14} className="text-danger-500" />
          <span className="font-semibold text-ink-900 dark:text-white text-sm">盈利诊断</span>
          <span className="ml-auto text-2xs font-semibold text-danger-600 dark:text-danger-500">
            无法证明盈利路径
          </span>
        </div>
        <div className="p-3 space-y-3">
          <div className="rounded-lg bg-danger-500/10 px-3 py-2 text-xs leading-relaxed text-danger-700 dark:text-danger-500">
            {forecast.interpretation ?? "当前命中率低于盈亏平衡线，不能通过增加样本来证明盈利，需要先改进模型或数据源。"}
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2 border-t border-ink-100 dark:border-ink-800/60">
            <div>
              <div className="text-2xs text-ink-500 dark:text-ink-400">命中率</div>
              <div className="text-sm font-semibold text-danger-600 dark:text-danger-500 tabular-nums">{pct(forecast.observed_hit_rate)}</div>
            </div>
            <div>
              <div className="text-2xs text-ink-500 dark:text-ink-400">盈亏平衡线</div>
              <div className="text-sm font-semibold text-ink-900 dark:text-white tabular-nums">{pct(forecast.break_even_hit_rate_needed)}</div>
            </div>
            <div>
              <div className="text-2xs text-ink-500 dark:text-ink-400">单笔 ROI</div>
              <div className="text-sm font-semibold text-danger-600 dark:text-danger-500 tabular-nums">{pct(forecast.implied_roi_per_bet)}</div>
            </div>
            <div>
              <div className="text-2xs text-ink-500 dark:text-ink-400">命中率缺口</div>
              <div className="text-sm font-semibold text-warning-600 dark:text-warning-500 tabular-nums">{pct(forecast.hit_rate_gap)}</div>
            </div>
          </div>
        </div>
      </section>
    );
  }

  if (state === "marginal_edge") {
    return (
      <section className="card overflow-hidden border-warning-500/30">
        <div className="px-3 py-2 border-b border-warning-500/20 flex items-center gap-2">
          <Icon name="warn" size={14} className="text-warning-500" />
          <span className="font-semibold text-ink-900 dark:text-white text-sm">盈利诊断</span>
          <span className="ml-auto text-2xs font-semibold text-warning-600 dark:text-warning-500">
            边际过小
          </span>
        </div>
        <div className="p-3 text-xs leading-relaxed text-ink-600 dark:text-ink-300">
          {forecast.interpretation ?? "当前优势太小，短期内很难统计证明盈利，需要优化候选过滤或模型特征。"}
        </div>
      </section>
    );
  }

  const remaining = forecast.remaining_bets ?? 0;
  const total = forecast.required_bets_total ?? Math.max(1, forecast.settled_bets_so_far ?? 0);
  const sofar = forecast.settled_bets_so_far ?? 0;
  const progress = Math.max(0, Math.min(100, (sofar / total) * 100));
  const isReady = remaining === 0 && total > 0 && sofar >= total && (forecast.implied_roi_per_bet ?? 0) > 0;

  return (
    <section className="card overflow-hidden">
      <div className="px-3 py-2 border-b border-ink-100 dark:border-ink-800 flex items-center gap-2">
        <Icon name="trendUp" size={14} className="text-brand-500" />
        <span className="font-semibold text-ink-900 dark:text-white text-sm">盈利时间预估（贝叶斯）</span>
        <span className="ml-auto text-2xs text-ink-500 dark:text-ink-400">
          {pct(forecast.confidence_level, 0)} 置信度
        </span>
      </div>
      <div className="p-3 space-y-3">
        {/* Big metric: days remaining */}
        <div className="flex items-center gap-3">
          <div className="w-14 h-14 rounded-xl bg-gradient-to-br from-brand-500/15 to-strike-500/15 flex flex-col items-center justify-center flex-shrink-0">
            {isReady ? (
              <Icon name="target" size={22} className="text-success-600 dark:text-success-500" />
            ) : (
              <Icon name="calendar" size={22} className="text-brand-600 dark:text-brand-400" />
            )}
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-display-xs text-ink-900 dark:text-white">
              {isReady ? "已达成" : `${forecast.remaining_days ?? "?"} 天`}
            </div>
            <div className="text-2xs text-ink-500 dark:text-ink-400">
              {isReady
                ? "可启动正式策略验证"
                : `约 ${remaining} 笔后可统计证明 ROI > 0`}
            </div>
          </div>
        </div>

        {/* Progress bar */}
        <div>
          <div className="flex justify-between text-2xs text-ink-500 dark:text-ink-400 mb-1 tabular-nums">
            <span>已结算 {sofar}</span>
            <span>目标 {total}</span>
          </div>
          <div className="h-2 rounded-full bg-ink-200 dark:bg-ink-800 overflow-hidden">
            <div
              className={`h-full transition-all duration-700 ${
                isReady
                  ? "bg-gradient-to-r from-success-400 to-success-600"
                  : "bg-gradient-to-r from-brand-400 via-brand-500 to-strike-500"
              }`}
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>

        {/* Metrics grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2 border-t border-ink-100 dark:border-ink-800/60">
          <div>
            <div className="text-2xs text-ink-500 dark:text-ink-400">命中率</div>
            <div className="text-sm font-semibold text-ink-900 dark:text-white tabular-nums">{pct(forecast.observed_hit_rate)}</div>
          </div>
          <div>
            <div className="text-2xs text-ink-500 dark:text-ink-400">单笔 ROI</div>
            <div className={`text-sm font-semibold tabular-nums ${(forecast.implied_roi_per_bet ?? 0) > 0 ? "text-success-600 dark:text-success-500" : "text-danger-500"}`}>
              {pct(forecast.implied_roi_per_bet)}
            </div>
          </div>
          <div>
            <div className="text-2xs text-ink-500 dark:text-ink-400">平均赔率</div>
            <div className="text-sm font-semibold text-ink-900 dark:text-white tabular-nums">
              {forecast.assumed_avg_odds != null ? forecast.assumed_avg_odds.toFixed(2) : "—"}
            </div>
          </div>
          <div>
            <div className="text-2xs text-ink-500 dark:text-ink-400">每日结算</div>
            <div className="text-sm font-semibold text-ink-900 dark:text-white tabular-nums">
              {num(forecast.settled_per_day_estimate)} 笔
            </div>
          </div>
        </div>

        {forecast.notes && (
          <div className="text-2xs text-ink-500 dark:text-ink-400 pt-2 border-t border-ink-100 dark:border-ink-800/60 leading-relaxed">
            {forecast.notes}
          </div>
        )}
      </div>
    </section>
  );
}
