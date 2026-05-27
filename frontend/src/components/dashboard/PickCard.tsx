import { TrendingUp, Clock, AlertTriangle, ChevronRight } from "lucide-react";
import type { DashboardRecord } from "../../types";
import { TeamMatchup } from "../shared/TeamLogo";
import { Badge } from "../shared/Badge";
import { ProgressRing } from "../shared/ProgressRing";
import { formatOdds, formatPercent } from "../../dashboardModel";

function localTime(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return new Intl.DateTimeFormat("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false }).format(d);
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

  return (
    <button
      type="button"
      onClick={() => onSelect?.(record)}
      className={`w-full text-left rounded-xl border p-4 transition-all shadow-sm hover:shadow-md ${
        selected
          ? "border-blue-400 dark:border-blue-500 bg-blue-50 dark:bg-blue-900/20 ring-1 ring-blue-400/30"
          : "border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 hover:border-slate-300 dark:hover:border-slate-600"
      }`}
      aria-pressed={selected}
    >
      <div className="flex items-start gap-3">
        {/* Probability ring */}
        <ProgressRing
          value={prob ?? 0}
          max={1}
          size={52}
          strokeWidth={4}
          color={probabilityColor(prob)}
          label={prob != null ? `${Math.round(prob * 100)}%` : "—"}
          sublabel="概率"
        />

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-2 flex-wrap">
            <Badge variant={recVariant}>{recLabel}</Badge>
            <span className="text-xs text-slate-500 dark:text-slate-400">{record.league}</span>
            {hasRisk && <AlertTriangle size={13} className="text-red-500" />}
          </div>
          <TeamMatchup
            home={record.home_team ?? ""}
            away={record.away_team ?? ""}
            homeLogo={record.home_team_logo_url}
            awayLogo={record.away_team_logo_url}
            size="xs"
          />
        </div>

        <ChevronRight size={16} className="flex-shrink-0 text-slate-400 dark:text-slate-500 mt-1" />
      </div>

      <div className="mt-3 pt-3 border-t border-slate-100 dark:border-slate-700/50 grid grid-cols-3 gap-2 text-xs">
        <div>
          <div className="text-slate-500 dark:text-slate-400 mb-0.5">赔率</div>
          <div className="font-semibold tabular-nums text-slate-900 dark:text-white">
            {record.decimal_odds != null ? formatOdds(record.decimal_odds) : "—"}
          </div>
        </div>
        <div>
          <div className="text-slate-500 dark:text-slate-400 mb-0.5">优势</div>
          <div className={`font-semibold tabular-nums ${edge != null && edge > 0 ? "text-emerald-600 dark:text-emerald-400" : "text-slate-900 dark:text-white"}`}>
            {edge != null ? formatPercent(edge) : "—"}
          </div>
        </div>
        <div>
          <div className="text-slate-500 dark:text-slate-400 mb-0.5 flex items-center gap-1">
            <Clock size={10} />开赛
          </div>
          <div className="font-medium text-slate-700 dark:text-slate-300">
            {localTime(record.kickoff_utc_plus_8)}
          </div>
        </div>
      </div>

      <div className="mt-2 text-xs text-slate-600 dark:text-slate-300 flex items-center gap-1">
        <TrendingUp size={12} />
        <span className="truncate">{record.selection}</span>
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
      <div className="text-center py-10 text-slate-500 dark:text-slate-400 text-sm">
        {emptyMessage}
      </div>
    );
  }
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-3">
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
