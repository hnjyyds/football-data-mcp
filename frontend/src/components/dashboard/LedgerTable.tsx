import { useState } from "react";
import { ChevronDown, ChevronUp, CheckCircle2, XCircle, Clock, Eye } from "lucide-react";
import type { PredictionLedgerRow } from "../../types";
import { TeamLogo } from "../shared/TeamLogo";
import { Badge } from "../shared/Badge";
import { formatOdds, formatPercent } from "../../dashboardModel";

type Filter = "all" | "recommendation" | "observation" | "settled" | "open" | "hit" | "miss";

const FILTERS: Array<{ key: Filter; label: string }> = [
  { key: "all", label: "全部" },
  { key: "recommendation", label: "推荐" },
  { key: "observation", label: "观察" },
  { key: "settled", label: "已结算" },
  { key: "open", label: "未结算" },
  { key: "hit", label: "命中" },
  { key: "miss", label: "未命中" },
];

function localTime(v: string | null | undefined): string {
  if (!v) return "—";
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return "—";
  return new Intl.DateTimeFormat("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false }).format(d);
}

function applyFilter(rows: PredictionLedgerRow[], filter: Filter): PredictionLedgerRow[] {
  switch (filter) {
    case "recommendation": return rows.filter((r) => r.prediction_type === "recommendation" || r.prediction_type?.includes("recommendation"));
    case "observation": return rows.filter((r) => r.prediction_type === "observation" || r.prediction_type?.includes("observation"));
    case "settled": return rows.filter((r) => r.settlement_status === "settled");
    case "open": return rows.filter((r) => r.settlement_status === "open");
    case "hit": return rows.filter((r) => r.hit === 1);
    case "miss": return rows.filter((r) => r.settlement_status === "settled" && r.hit === 0);
    default: return rows;
  }
}

function StatusIcon({ row }: { row: PredictionLedgerRow }) {
  if (row.settlement_status === "settled") {
    return row.hit === 1
      ? <CheckCircle2 size={14} className="text-emerald-500" />
      : <XCircle size={14} className="text-red-400" />;
  }
  if (row.settlement_status === "open") return <Clock size={14} className="text-amber-500" />;
  return <Eye size={14} className="text-slate-400" />;
}

export function LedgerTable({
  rows,
  selectedId,
  onSelect,
}: {
  rows: PredictionLedgerRow[];
  selectedId?: string | null;
  onSelect?: (id: string) => void;
}) {
  const [filter, setFilter] = useState<Filter>("all");
  const [collapsed, setCollapsed] = useState(false);
  const [page, setPage] = useState(0);
  const PAGE_SIZE = 20;

  const filtered = applyFilter(rows, filter);
  const total = filtered.length;
  const pageRows = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <section className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 shadow-sm overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-slate-100 dark:border-slate-700/50">
        <span className="font-semibold text-slate-900 dark:text-white text-sm flex-1">预测台账</span>
        <span className="text-xs text-slate-500 dark:text-slate-400">{total} 条</span>
        <button
          type="button"
          onClick={() => setCollapsed((c) => !c)}
          className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-500 dark:text-slate-400 transition-colors"
          aria-label={collapsed ? "展开台账" : "折叠台账"}
        >
          {collapsed ? <ChevronDown size={16} /> : <ChevronUp size={16} />}
        </button>
      </div>

      {!collapsed && (
        <>
          {/* Filter bar */}
          <div className="flex gap-1 px-4 py-2 border-b border-slate-100 dark:border-slate-700/50 overflow-x-auto">
            {FILTERS.map((f) => (
              <button
                key={f.key}
                type="button"
                onClick={() => { setFilter(f.key); setPage(0); }}
                className={`flex-shrink-0 px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                  filter === f.key
                    ? "bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300"
                    : "text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700"
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>

          {/* Table */}
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 dark:border-slate-700/50 text-xs text-slate-500 dark:text-slate-400">
                  <th className="text-left px-4 py-2 font-medium w-8" />
                  <th className="text-left px-4 py-2 font-medium">赛事</th>
                  <th className="text-left px-3 py-2 font-medium hidden sm:table-cell">联赛</th>
                  <th className="text-left px-3 py-2 font-medium hidden md:table-cell">选项</th>
                  <th className="text-right px-3 py-2 font-medium hidden lg:table-cell">概率</th>
                  <th className="text-right px-3 py-2 font-medium">赔率</th>
                  <th className="text-right px-3 py-2 font-medium hidden md:table-cell">优势</th>
                  <th className="text-right px-3 py-2 font-medium hidden lg:table-cell">开赛</th>
                  <th className="text-center px-3 py-2 font-medium">结果</th>
                </tr>
              </thead>
              <tbody>
                {pageRows.length === 0 && (
                  <tr>
                    <td colSpan={9} className="text-center py-8 text-slate-400 dark:text-slate-500 text-sm">
                      暂无记录
                    </td>
                  </tr>
                )}
                {pageRows.map((row) => {
                  const isSelected = selectedId === row.ledger_id;
                  return (
                    <tr
                      key={row.ledger_id}
                      className={`border-b border-slate-50 dark:border-slate-700/30 cursor-pointer transition-colors ${
                        isSelected
                          ? "bg-blue-50 dark:bg-blue-900/20"
                          : "hover:bg-slate-50 dark:hover:bg-slate-700/30"
                      }`}
                      onClick={() => onSelect?.(row.ledger_id)}
                    >
                      <td className="px-4 py-2.5">
                        <StatusIcon row={row} />
                      </td>
                      <td className="px-4 py-2.5">
                        <div className="flex items-center gap-2 min-w-0">
                          <TeamLogo name={row.home_team ?? ""} logoUrl={row.home_team_logo_url} size="xs" />
                          <div className="min-w-0">
                            <div className="text-xs font-medium text-slate-900 dark:text-white truncate max-w-[120px]">
                              {row.home_team}
                            </div>
                            <div className="text-xs text-slate-500 dark:text-slate-400 truncate max-w-[120px]">
                              {row.away_team}
                            </div>
                          </div>
                        </div>
                      </td>
                      <td className="px-3 py-2.5 hidden sm:table-cell">
                        <span className="text-xs text-slate-500 dark:text-slate-400 truncate max-w-[80px] block">{row.league}</span>
                      </td>
                      <td className="px-3 py-2.5 hidden md:table-cell">
                        <span className="text-xs text-slate-700 dark:text-slate-300 truncate max-w-[120px] block">{row.selection}</span>
                      </td>
                      <td className="px-3 py-2.5 text-right hidden lg:table-cell">
                        <span className="text-xs tabular-nums text-slate-700 dark:text-slate-300">
                          {row.learned_probability != null ? formatPercent(row.learned_probability) : row.model_probability != null ? formatPercent(row.model_probability) : "—"}
                        </span>
                      </td>
                      <td className="px-3 py-2.5 text-right">
                        <span className="text-xs tabular-nums font-medium text-slate-900 dark:text-white">
                          {row.decimal_odds != null ? formatOdds(row.decimal_odds) : "—"}
                        </span>
                      </td>
                      <td className="px-3 py-2.5 text-right hidden md:table-cell">
                        <span className={`text-xs tabular-nums ${(row.edge ?? 0) > 0 ? "text-emerald-600 dark:text-emerald-400" : "text-slate-500"}`}>
                          {row.edge != null ? formatPercent(row.edge) : "—"}
                        </span>
                      </td>
                      <td className="px-3 py-2.5 text-right hidden lg:table-cell">
                        <span className="text-xs text-slate-500 dark:text-slate-400">{localTime(row.kickoff_utc_plus_8)}</span>
                      </td>
                      <td className="px-3 py-2.5">
                        <div className="flex justify-center">
                          {row.settlement_status === "settled" ? (
                            <Badge variant={row.hit === 1 ? "success" : "error"}>
                              {row.hit === 1 ? "命中" : "未中"}
                            </Badge>
                          ) : row.settlement_status === "open" ? (
                            <Badge variant="warning">待结算</Badge>
                          ) : (
                            <Badge variant="neutral">跟踪</Badge>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between px-4 py-2 border-t border-slate-100 dark:border-slate-700/50 text-xs text-slate-500 dark:text-slate-400">
              <button
                type="button"
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
                className="px-3 py-1 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 disabled:opacity-40 transition-colors"
              >
                上一页
              </button>
              <span>{page + 1} / {totalPages}</span>
              <button
                type="button"
                onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                disabled={page >= totalPages - 1}
                className="px-3 py-1 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 disabled:opacity-40 transition-colors"
              >
                下一页
              </button>
            </div>
          )}
        </>
      )}
    </section>
  );
}
