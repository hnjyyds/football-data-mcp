import { Clock, AlertTriangle, ChevronRight, TrendingUp } from "lucide-react";
import type { DashboardRecord } from "../../types";
import { TeamLogo } from "../shared/TeamLogo";
import { Badge } from "../shared/Badge";
import { ProgressRing } from "../shared/ProgressRing";
import { formatOdds, formatPercent } from "../../dashboardModel";

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

function recommendationBadge(rec: string): { label: string; variant: "success" | "warning" | "neutral" } {
  if (rec === "strong_buy" || rec === "immediate_bet") return { label: "强买", variant: "success" };
  if (rec === "buy") return { label: "买入", variant: "success" };
  if (rec === "condition_observe") return { label: "观察", variant: "warning" };
  if (rec === "balanced") return { label: "均衡", variant: "neutral" };
  return { label: rec || "—", variant: "neutral" };
}

function probabilityColor(p: number | null | undefined): string {
  if (p == null) return "#94a3b8";
  if (p >= 0.68) return "#10b981";
  if (p >= 0.62) return "#3b82f6";
  if (p >= 0.57) return "#f59e0b";
  return "#ef4444";
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
  const isImminent = countdownText !== "已开赛" && countdownText !== "—" && countdownText.includes("min");

  return (
    <button
      type="button"
      onClick={() => onSelect?.(record)}
      className={`group w-full text-left rounded-lg border p-3 transition-all hover:shadow-md ${
        selected
          ? "border-blue-400 dark:border-blue-500 bg-blue-50/60 dark:bg-blue-900/20 ring-1 ring-blue-400/30 shadow-md"
          : "border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 hover:border-blue-300 dark:hover:border-blue-600"
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
            {hasRisk && <AlertTriangle size={11} className="text-amber-500" />}
            <span className="text-[10px] text-slate-400 dark:text-slate-500 truncate ml-auto">{record.league}</span>
          </div>

          {/* Team matchup - inline horizontal */}
          <div className="flex items-center gap-1.5 min-w-0">
            <TeamLogo name={record.home_team ?? ""} logoUrl={record.home_team_logo_url} size="xs" />
            <span className="text-xs font-medium text-slate-900 dark:text-white truncate flex-1">{record.home_team}</span>
          </div>
          <div className="flex items-center gap-1.5 min-w-0 mt-0.5">
            <TeamLogo name={record.away_team ?? ""} logoUrl={record.away_team_logo_url} size="xs" />
            <span className="text-xs font-medium text-slate-900 dark:text-white truncate flex-1">{record.away_team}</span>
          </div>
        </div>

        <ChevronRight size={14} className="flex-shrink-0 text-slate-400 dark:text-slate-500 mt-0.5 opacity-0 group-hover:opacity-100 transition-opacity" />
      </div>

      {/* Footer metrics */}
      <div className="mt-2.5 pt-2.5 border-t border-slate-100 dark:border-slate-700/50">
        <div className="flex items-center justify-between gap-2 mb-1.5">
          <span className="text-[11px] text-slate-600 dark:text-slate-300 truncate flex items-center gap-1">
            <TrendingUp size={10} />
            {record.selection}
          </span>
          <span className={`text-[10px] tabular-nums flex items-center gap-0.5 ${isImminent ? "text-amber-600 dark:text-amber-400 font-medium" : "text-slate-400 dark:text-slate-500"}`}>
            <Clock size={9} />
            {countdownText}
          </span>
        </div>
        <div className="grid grid-cols-3 gap-1.5 text-xs">
          <div className="text-center px-1.5 py-1 rounded bg-slate-50 dark:bg-slate-700/50">
            <div className="text-[9px] text-slate-500 dark:text-slate-400 leading-none">赔率</div>
            <div className="font-bold tabular-nums text-slate-900 dark:text-white mt-0.5">
              {record.decimal_odds != null ? formatOdds(record.decimal_odds) : "—"}
            </div>
          </div>
          <div className="text-center px-1.5 py-1 rounded bg-slate-50 dark:bg-slate-700/50">
            <div className="text-[9px] text-slate-500 dark:text-slate-400 leading-none">价值</div>
            <div className={`font-bold tabular-nums mt-0.5 ${edge != null && edge > 0 ? "text-emerald-600 dark:text-emerald-400" : "text-slate-900 dark:text-white"}`}>
              {edge != null ? (edge > 0 ? "+" : "") + (edge * 100).toFixed(1) + "%" : "—"}
            </div>
          </div>
          <div className="text-center px-1.5 py-1 rounded bg-slate-50 dark:bg-slate-700/50">
            <div className="text-[9px] text-slate-500 dark:text-slate-400 leading-none">时间</div>
            <div className="font-medium text-slate-700 dark:text-slate-300 mt-0.5 text-[11px]">
              {localTime(record.kickoff_utc_plus_8)}
            </div>
          </div>
        </div>
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
  if (!records.length) {
    return (
      <div className="text-center py-8 text-slate-400 dark:text-slate-500 text-sm">
        <TrendingUp size={28} className="mx-auto mb-2 opacity-40" />
        {emptyMessage}
      </div>
    );
  }
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
      {records.map((r) => (
        <PickCard
          key={r.id}
          record={r}
          selected={selectedId === r.id}
          onSelect={onSelect}
        />
      ))}
    </div>
  );
}
