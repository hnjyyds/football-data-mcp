import { CheckCircle2, XCircle, History } from "lucide-react";
import type { DashboardRecord } from "../../types";
import { TeamLogo } from "../shared/TeamLogo";

function localTime(v: string | null | undefined): string {
  if (!v) return "—";
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return "—";
  return new Intl.DateTimeFormat("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false }).format(d);
}

export function SettlementFeed({ records }: { records: DashboardRecord[] }) {
  return (
    <section className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 shadow-sm overflow-hidden">
      <div className="flex items-center gap-2 px-3 py-2 border-b border-slate-100 dark:border-slate-700/50">
        <History size={14} className="text-slate-500 dark:text-slate-400" />
        <span className="font-semibold text-slate-900 dark:text-white text-sm flex-1">近期结算</span>
        <span className="text-xs text-slate-400 dark:text-slate-500">{records.length} 条</span>
      </div>
      {!records.length ? (
        <div className="text-center py-6 text-slate-400 dark:text-slate-500 text-sm">
          暂无已结算记录
        </div>
      ) : (
        <div className="divide-y divide-slate-50 dark:divide-slate-700/30">
          {records.slice(0, 8).map((r) => {
            const hit = r.hit === 1;
            return (
              <div key={r.id} className="flex items-center gap-2 px-3 py-2 hover:bg-slate-50 dark:hover:bg-slate-700/30 transition-colors">
                {hit
                  ? <CheckCircle2 size={14} className="flex-shrink-0 text-emerald-500" />
                  : <XCircle size={14} className="flex-shrink-0 text-red-400" />
                }
                <div className="flex items-center gap-1 flex-shrink-0">
                  <TeamLogo name={r.home_team ?? ""} logoUrl={r.home_team_logo_url} size="xs" />
                  <TeamLogo name={r.away_team ?? ""} logoUrl={r.away_team_logo_url} size="xs" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-medium text-slate-900 dark:text-white truncate">
                    {r.home_team} <span className="text-slate-400">对</span> {r.away_team}
                  </div>
                  <div className="text-[10px] text-slate-500 dark:text-slate-400 truncate">{r.selection}</div>
                </div>
                <div className="flex-shrink-0 text-right">
                  <div className={`text-xs font-bold tabular-nums ${hit ? "text-emerald-600 dark:text-emerald-400" : "text-red-500 dark:text-red-400"}`}>
                    {r.profit_units != null ? (r.profit_units > 0 ? "+" : "") + r.profit_units.toFixed(2) : "—"}
                  </div>
                  <div className="text-[10px] text-slate-400 dark:text-slate-500">{localTime(r.settled_at_utc)}</div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
