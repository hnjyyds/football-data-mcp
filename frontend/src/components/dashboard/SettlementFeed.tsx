import { Icon } from "../shared/Icon";
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
    <section className="surface-panel overflow-hidden">
      <div className="flex items-center gap-2 px-4 pt-4 pb-2">
        <Icon name="history" size={14} className="text-[hsl(var(--muted-foreground))]" />
        <span className="font-semibold text-[hsl(var(--foreground))] text-sm flex-1">近期结算</span>
        <span className="text-xs text-[hsl(var(--muted-foreground))]">{records.length} 条</span>
      </div>
      {!records.length ? (
        <div className="px-4 py-8 text-center">
          <div className="mx-auto mb-3 grid h-10 w-10 place-items-center rounded-lg bg-[hsl(var(--muted))] text-[hsl(var(--muted-foreground))]">
            <Icon name="history" size={18} />
          </div>
          <div className="text-sm font-semibold text-[hsl(var(--foreground))]">暂无已结算记录</div>
          <div className="mt-1 text-xs text-[hsl(var(--muted-foreground))]">新样本结算后会在这里显示盈亏和命中情况。</div>
        </div>
      ) : (
        <div className="divide-y divide-[hsl(var(--border))]">
          {records.slice(0, 8).map((r) => {
            const hit = r.hit === 1;
            return (
              <div key={r.id} className="flex items-center gap-2 px-3 py-2.5 hover:bg-[hsl(var(--muted))]/60 transition-colors">
                {hit
                  ? <Icon name="success" size={14} className="flex-shrink-0 text-success-500" />
                  : <Icon name="error" size={14} className="flex-shrink-0 text-danger-500" />
                }
                <div className="flex items-center gap-1 flex-shrink-0">
                  <TeamLogo name={r.home_team ?? ""} logoUrl={r.home_team_logo_url} size="xs" />
                  <TeamLogo name={r.away_team ?? ""} logoUrl={r.away_team_logo_url} size="xs" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-medium text-[hsl(var(--foreground))] truncate">
                    {r.home_team} <span className="text-[hsl(var(--muted-foreground))]">对</span> {r.away_team}
                  </div>
                  <div className="text-[10px] text-[hsl(var(--muted-foreground))] truncate">{r.selection}</div>
                </div>
                <div className="flex-shrink-0 text-right">
                  <div className={`text-xs font-bold tabular-nums ${hit ? "text-emerald-600 dark:text-emerald-400" : "text-red-500 dark:text-red-400"}`}>
                    {r.profit_units != null ? (r.profit_units > 0 ? "+" : "") + r.profit_units.toFixed(2) : "—"}
                  </div>
                  <div className="text-[10px] text-[hsl(var(--muted-foreground))]">{localTime(r.settled_at_utc)}</div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
