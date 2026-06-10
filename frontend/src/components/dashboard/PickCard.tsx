import { useMemo, useState } from "react";

import { Icon } from "../shared/Icon";
import type { DashboardRecord } from "../../types";
import { TeamLogo } from "../shared/TeamLogo";
import { Badge } from "../shared/Badge";
import { ProgressRing } from "../shared/ProgressRing";
import { formatOdds } from "../../dashboardModel";

function localTime(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return new Intl.DateTimeFormat("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false }).format(d);
}

function countdown(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value);
  const diff = d.getTime() - Date.now();
  if (Number.isNaN(diff)) return "—";
  if (diff <= 0) return "已开赛";
  const minutes = Math.round(diff / 60000);
  if (minutes < 60) return `${minutes}min`;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return m > 0 ? `${h}h${m}m` : `${h}h`;
}

function timestamp(value: string | null | undefined): number {
  if (!value) return 0;
  const time = new Date(value).getTime();
  return Number.isNaN(time) ? 0 : time;
}

function resultScore(record: DashboardRecord): string | null {
  return record.true_result?.score || record.match_state?.score || record.score || null;
}

function matchStatusText(record: DashboardRecord, fallback: string): string {
  if (record.settlement_status === "settled") return record.hit === 1 ? "命中" : "未中";
  if (record.match_state?.label) return record.match_state.label;
  if (record.status_label) return record.status_label;
  return fallback;
}

function profitText(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}u`;
}

function recommendationBadge(rec: string): { label: string; variant: "success" | "warning" | "neutral" } {
  if (rec === "strong_buy") return { label: "强买", variant: "success" };
  if (rec === "immediate_bet") return { label: "观察", variant: "warning" };
  if (rec === "buy") return { label: "买入", variant: "success" };
  if (rec === "condition_observe") return { label: "观察", variant: "warning" };
  if (rec === "balanced") return { label: "均衡", variant: "neutral" };
  if (rec === "no_value" || rec === "watch_only" || rec === "observed_not_recommended") {
    return { label: "观察", variant: "warning" };
  }
  if (rec === "recommendation") return { label: "推荐", variant: "success" };
  if (rec === "observation" || rec === "prediction") return { label: "预测", variant: "neutral" };
  return { label: rec || "—", variant: "neutral" };
}

function probabilityColor(p: number | null | undefined): string {
  if (p == null) return "hsl(var(--muted-foreground))";
  if (p >= 0.65) return "hsl(var(--foreground))";
  if (p >= 0.55) return "hsl(var(--muted-foreground))";
  return "hsl(var(--border))";
}

type ProbabilityTier = {
  key: "high" | "medium" | "low";
  label: string;
  min: number;
  maxExclusive: number;
};

const PROBABILITY_TIERS: ProbabilityTier[] = [
  { key: "high", label: "高概率", min: 0.65, maxExclusive: Number.POSITIVE_INFINITY },
  { key: "medium", label: "中概率", min: 0.55, maxExclusive: 0.65 },
  { key: "low", label: "低概率", min: Number.NEGATIVE_INFINITY, maxExclusive: 0.55 },
];
const PAGE_SIZE = 6;

function displayProbability(record: DashboardRecord): number {
  return record.learned_probability ?? record.model_probability ?? -1;
}

function compareByFreshnessThenProbability(left: DashboardRecord, right: DashboardRecord): number {
  const timeDiff = timestamp(right.created_at_utc) - timestamp(left.created_at_utc);
  if (timeDiff !== 0) return timeDiff;
  return displayProbability(right) - displayProbability(left);
}

function tierRecords(records: DashboardRecord[]) {
  const sorted = [...records].sort(compareByFreshnessThenProbability);
  return PROBABILITY_TIERS.map((tier) => {
    const items = sorted.filter((record) => {
      const probability = displayProbability(record);
      return probability >= tier.min && probability < tier.maxExclusive;
    });
    return { ...tier, items };
  }).filter((tier) => tier.items.length > 0);
}

export function PickCard({
  record,
  onSelect,
  selected,
}: {
  record: DashboardRecord;
  onSelect?: (record: DashboardRecord) => void;
  selected?: boolean;
}) {
  const prob = record.learned_probability ?? record.model_probability;
  const edge = record.edge;
  const { label: recLabel, variant: recVariant } = recommendationBadge(record.recommendation ?? "");
  const hasRisk = (record.risk_flags?.length ?? 0) > 0;
  const countdownText = countdown(record.kickoff_utc_plus_8);
  const scoreText = resultScore(record);
  const statusText = matchStatusText(record, countdownText);
  const isSettled = record.settlement_status === "settled";
  const isHit = isSettled && record.hit === 1;
  const isImminent = !isSettled && countdownText !== "已开赛" && countdownText !== "—" && countdownText.includes("min");
  const isHot = (prob ?? 0) >= 0.68;

  return (
    <button
      type="button"
      onClick={() => onSelect?.(record)}
      className={`focusable-control group w-full text-left rounded-lg border p-3 transition-colors hover:bg-[hsl(var(--muted))]/45 ${
        selected
          ? "border-[hsl(var(--primary))] bg-[hsl(var(--muted))] ring-1 ring-[hsl(var(--primary))]/25"
          : "border-[hsl(var(--border))] bg-[hsl(var(--card))]"
      }`}
      aria-pressed={selected}
    >
      <div className="flex items-start gap-3">
        {/* Probability ring */}
        <ProgressRing
          value={prob ?? 0}
          max={1}
          size={48}
          strokeWidth={4}
          color={probabilityColor(prob)}
          label={prob != null ? `${Math.round(prob * 100)}` : "—"}
        />

        <div className="flex-1 min-w-0">
          {/* Header row: tags */}
          <div className="flex items-center gap-1.5 mb-1.5 flex-wrap">
            <Badge variant={recVariant} className="text-[10px] py-0">{recLabel}</Badge>
            {isHot && (
            <span className="text-[hsl(var(--foreground))]" title="高置信度">
                <Icon name="hot" size={11} />
              </span>
            )}
            {hasRisk && (
            <span className="text-[hsl(var(--muted-foreground))]" title="存在风险标记">
                <Icon name="warn" size={11} />
              </span>
            )}
            {isSettled && (
              <Badge variant={isHit ? "success" : "neutral"} className="text-[10px] py-0">
                {isHit ? "命中" : "未中"}
              </Badge>
            )}
            <span className="text-[10px] text-ink-400 dark:text-ink-500 truncate ml-auto">{record.league}</span>
          </div>

          {/* Team matchup - inline horizontal */}
          <div className="flex items-center gap-1.5 min-w-0">
            <TeamLogo name={record.home_team ?? ""} logoUrl={record.home_team_logo_url} size="xs" />
            <span className="text-xs font-medium text-[hsl(var(--foreground))] truncate flex-1">{record.home_team}</span>
          </div>
          <div className="flex items-center gap-1.5 min-w-0 mt-0.5">
            <TeamLogo name={record.away_team ?? ""} logoUrl={record.away_team_logo_url} size="xs" />
            <span className="text-xs font-medium text-[hsl(var(--foreground))] truncate flex-1">{record.away_team}</span>
          </div>
        </div>

        <Icon name="chevronRight" size={14} className="flex-shrink-0 text-ink-400 dark:text-ink-500 mt-0.5 opacity-0 group-hover:opacity-100 transition-opacity" />
      </div>

      {/* Footer metrics */}
      <div className="mt-2.5 pt-2.5 border-t border-[hsl(var(--border))]">
        <div className="flex items-center justify-between gap-2 mb-1.5">
          <span className="text-[11px] text-[hsl(var(--foreground))] truncate flex items-center gap-1">
            <Icon name="trendUp" size={10} />
            {record.selection}
          </span>
          <span className={`text-[10px] tabular-nums flex items-center gap-0.5 ${isImminent ? "text-[hsl(var(--foreground))] font-medium" : "text-[hsl(var(--muted-foreground))]"}`}>
            <Icon name={isSettled ? "circleCheck" : "clock"} size={9} />
            {statusText}
          </span>
        </div>
        <div className="grid grid-cols-3 gap-1.5 text-xs">
          <div className="text-center px-1.5 py-1 rounded-md bg-[hsl(var(--muted))]/60">
            <div className="text-[9px] text-[hsl(var(--muted-foreground))] leading-none">赔率</div>
            <div className="font-semibold tabular-nums text-[hsl(var(--foreground))] mt-0.5">
              {record.decimal_odds != null ? formatOdds(record.decimal_odds) : "—"}
            </div>
          </div>
          <div className="text-center px-1.5 py-1 rounded-md bg-[hsl(var(--muted))]/60">
            <div className="text-[9px] text-[hsl(var(--muted-foreground))] leading-none">价值</div>
            <div className={`font-semibold tabular-nums mt-0.5 ${edge != null && edge > 0 ? "text-success-600 dark:text-success-500" : "text-[hsl(var(--foreground))]"}`}>
              {edge != null ? (edge > 0 ? "+" : "") + (edge * 100).toFixed(1) + "%" : "—"}
            </div>
          </div>
          <div className="text-center px-1.5 py-1 rounded-md bg-[hsl(var(--muted))]/60">
            <div className="text-[9px] text-[hsl(var(--muted-foreground))] leading-none">{isSettled ? "赛果" : "时间"}</div>
            <div className="font-medium text-[hsl(var(--foreground))] mt-0.5 text-[11px]">
              {isSettled ? scoreText ?? "已完场" : localTime(record.kickoff_utc_plus_8)}
            </div>
          </div>
        </div>
        {isSettled && (
          <div className="mt-1.5 flex items-center justify-between rounded-md bg-[hsl(var(--muted))]/40 px-2 py-1 text-[10px]">
            <span className="text-[hsl(var(--muted-foreground))]">
              结算 {localTime(record.settled_at_utc)}
            </span>
            <span className={record.profit_units != null && record.profit_units > 0 ? "font-medium text-success-600 dark:text-success-500" : "font-medium text-[hsl(var(--foreground))]"}>
              {profitText(record.profit_units)}
            </span>
          </div>
        )}
      </div>
    </button>
  );
}

export function PickGrid({
  records,
  selectedId,
  onSelect,
  emptyMessage = "暂无推荐信号",
}: {
  records: DashboardRecord[];
  selectedId?: string | null;
  onSelect?: (record: DashboardRecord) => void;
  emptyMessage?: string;
}) {
  const grouped = useMemo(() => tierRecords(records), [records]);
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({ low: true });
  const [pages, setPages] = useState<Record<string, number>>({});

  if (!records.length) {
    return (
      <div className="text-center py-8 text-[hsl(var(--muted-foreground))] text-sm">
        <span className="inline-block mb-2 opacity-40">
          <Icon name="football" size={32} />
        </span>
        <div>{emptyMessage}</div>
      </div>
    );
  }

  function toggleGroup(key: string) {
    setCollapsed((current) => ({ ...current, [key]: !current[key] }));
  }

  function changePage(key: string, nextPage: number, pageCount: number) {
    const bounded = Math.max(0, Math.min(nextPage, Math.max(0, pageCount - 1)));
    setPages((current) => ({ ...current, [key]: bounded }));
  }

  return (
    <div className="space-y-4">
      {grouped.map((group) => (
        <section key={group.key} className="surface-muted overflow-hidden">
          <button
            type="button"
            onClick={() => toggleGroup(group.key)}
            className="focusable-control flex w-full items-center justify-between gap-3 px-3 py-3 text-left hover:bg-[hsl(var(--muted))]"
            aria-expanded={!collapsed[group.key]}
          >
            <div className="min-w-0">
              <div className="text-sm font-semibold text-[hsl(var(--foreground))]">{group.label}</div>
              <div className="text-[11px] text-[hsl(var(--muted-foreground))]">
                {group.key === "high" ? ">= 65%" : group.key === "medium" ? "55% - 64.9%" : "< 55%"} · {group.items.length} 场
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant="neutral" className="text-[10px]">
                {collapsed[group.key] ? "已折叠" : "已展开"}
              </Badge>
              <Icon name={collapsed[group.key] ? "chevronDown" : "chevronUp"} size={16} className="text-[hsl(var(--muted-foreground))]" />
            </div>
          </button>
          {!collapsed[group.key] && (() => {
            const pageCount = Math.max(1, Math.ceil(group.items.length / PAGE_SIZE));
            const pageIndex = Math.min(pages[group.key] ?? 0, pageCount - 1);
            const pagedItems = group.items.slice(pageIndex * PAGE_SIZE, (pageIndex + 1) * PAGE_SIZE);
            return (
              <div className="border-t border-[hsl(var(--border))] px-3 pb-3">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 pt-3">
                  {pagedItems.map((r) => (
                    <PickCard
                      key={r.id}
                      record={r}
                      selected={selectedId === r.id}
                      onSelect={onSelect}
                    />
                  ))}
                </div>
                {pageCount > 1 && (
                  <div className="mt-3 flex items-center justify-between gap-3">
                    <div className="text-[11px] text-[hsl(var(--muted-foreground))]">
                      第 {pageIndex + 1} / {pageCount} 页
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => changePage(group.key, pageIndex - 1, pageCount)}
                        disabled={pageIndex <= 0}
                        className="shadcn-button-secondary min-h-8 px-2.5 py-1.5 text-xs disabled:opacity-40"
                      >
                        上一页
                      </button>
                      <button
                        type="button"
                        onClick={() => changePage(group.key, pageIndex + 1, pageCount)}
                        disabled={pageIndex >= pageCount - 1}
                        className="shadcn-button-secondary min-h-8 px-2.5 py-1.5 text-xs disabled:opacity-40"
                      >
                        下一页
                      </button>
                    </div>
                  </div>
                )}
              </div>
            );
          })()}
        </section>
      ))}
    </div>
  );
}
