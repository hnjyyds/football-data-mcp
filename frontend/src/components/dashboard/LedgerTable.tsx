import { useState, type KeyboardEvent } from "react";
import { Icon } from "../shared/Icon";
import type { PredictionLedgerRow } from "../../types";
import { TeamLogo } from "../shared/TeamLogo";
import { Badge } from "../shared/Badge";
import { formatOdds, formatPercent, reasonLabel } from "../../dashboardModel";
import { formatBeijingShort } from "../../formatTime";

type Filter = "all" | "recommendation" | "observation" | "reanalysis" | "settled" | "open" | "hit" | "miss";

const FILTERS: Array<{ key: Filter; label: string }> = [
  { key: "all", label: "全部" },
  { key: "recommendation", label: "推荐" },
  { key: "observation", label: "观察" },
  { key: "reanalysis", label: "待复算" },
  { key: "settled", label: "已结算" },
  { key: "open", label: "未结算" },
  { key: "hit", label: "命中" },
  { key: "miss", label: "未命中" },
];

const localTime = formatBeijingShort;

function applyFilter(rows: PredictionLedgerRow[], filter: Filter): PredictionLedgerRow[] {
  switch (filter) {
    case "recommendation": return rows.filter((r) => r.prediction_type === "recommendation" || r.prediction_type?.includes("recommendation"));
    case "observation": return rows.filter((r) => r.prediction_type === "observation" || r.prediction_type?.includes("observation"));
    case "reanalysis": return rows.filter((r) => {
      const primaryReason = r.prediction_diagnostic?.primary_reason;
      return r.rejection_reason === "awaiting_reanalysis_after_snapshot" || primaryReason === "awaiting_reanalysis_after_snapshot";
    });
    case "settled": return rows.filter((r) => r.settlement_status === "settled");
    case "open": return rows.filter((r) => r.settlement_status === "open");
    case "hit": return rows.filter((r) => r.hit === 1);
    case "miss": return rows.filter((r) => r.settlement_status === "settled" && r.hit === 0);
    default: return rows;
  }
}

function rowReason(row: PredictionLedgerRow): string {
  return row.prediction_diagnostic?.primary_reason || row.rejection_reason || row.recommendation || "";
}

function applyReasonFilter(rows: PredictionLedgerRow[], reasonFilter: LedgerReasonFilter | null | undefined): PredictionLedgerRow[] {
  if (!reasonFilter?.reason && !reasonFilter?.label) return rows;
  return rows.filter((row) => {
    const reason = rowReason(row);
    return (!!reasonFilter.reason && reason === reasonFilter.reason) || reasonLabel(reason) === reasonFilter.label;
  });
}

function filterCounts(rows: PredictionLedgerRow[]): Record<Filter, number> {
  return FILTERS.reduce((acc, item) => {
    acc[item.key] = applyFilter(rows, item.key).length;
    return acc;
  }, {} as Record<Filter, number>);
}

export type LedgerReasonFilter = {
  reason?: string;
  label: string;
};

function statusLabel(row: PredictionLedgerRow): string {
  if (row.settlement_status === "settled") return row.hit === 1 ? "命中" : "未中";
  if (row.settlement_status === "open") return "待结算";
  if (row.settlement_status === "cancelled_postponed") return "延期";
  if (row.settlement_status === "unsettleable") return "无源";
  return "跟踪";
}

function StatusIcon({ row }: { row: PredictionLedgerRow }) {
  const label = statusLabel(row);
  if (row.settlement_status === "settled") {
    return (
      <span aria-label={label} role="img">
        <Icon name={row.hit === 1 ? "success" : "error"} size={14} className={row.hit === 1 ? "text-success-500" : "text-danger-500"} />
      </span>
    );
  }
  if (row.settlement_status === "open") return <span aria-label={label} role="img"><Icon name="pending" size={14} className="text-warning-500" /></span>;
  if (row.settlement_status === "unsettleable") return <span aria-label={label} role="img"><Icon name="warn" size={14} className="text-ink-400" /></span>;
  return <span aria-label={label} role="img"><Icon name="eye" size={14} className="text-ink-400" /></span>;
}

export function LedgerTable({
  rows,
  selectedId,
  onSelect,
  reasonFilter = null,
  onReasonFilterClear,
}: {
  rows: PredictionLedgerRow[];
  selectedId?: string | null;
  onSelect?: (id: string) => void;
  reasonFilter?: LedgerReasonFilter | null;
  onReasonFilterClear?: () => void;
}) {
  const [filter, setFilter] = useState<Filter>("all");
  const [collapsed, setCollapsed] = useState(false);
  const [page, setPage] = useState(0);
  const PAGE_SIZE = 20;

  const reasonFilteredRows = applyReasonFilter(rows, reasonFilter);
  const counts = filterCounts(reasonFilteredRows);
  const filtered = applyFilter(reasonFilteredRows, filter);
  const total = filtered.length;
  const pageRows = filtered.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);
  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <section className="surface-panel overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 pt-4 pb-2">
        <Icon name="database" size={14} className="text-[hsl(var(--muted-foreground))]" />
        <span className="font-semibold text-[hsl(var(--foreground))] text-sm flex-1">预测台账</span>
        <span className="text-xs text-[hsl(var(--muted-foreground))]">{total} 条</span>
        <button
          type="button"
          onClick={() => setCollapsed((c) => !c)}
          className="shadcn-button-ghost h-8 w-8 p-0"
          aria-label={collapsed ? "展开台账" : "折叠台账"}
        >
          <Icon name={collapsed ? "chevronDown" : "chevronUp"} size={16} />
        </button>
      </div>

      {!collapsed && (
        <>
          {/* Filter bar */}
          <div className="border-b border-[hsl(var(--border))]">
            {reasonFilter?.reason && (
              <div className="flex flex-wrap items-center gap-2 px-4 pt-2 text-xs">
                <span className="text-[hsl(var(--muted-foreground))]">阻断原因筛选</span>
                <Badge variant="warning">{reasonFilter.label}</Badge>
                <button
                  type="button"
                  onClick={() => { onReasonFilterClear?.(); setPage(0); }}
                  className="shadcn-button-ghost min-h-7 rounded-md px-2 py-0.5 text-xs"
                >
                  清除阻断筛选
                </button>
              </div>
            )}
            <div className="flex gap-1.5 px-4 py-2 overflow-x-auto">
              {FILTERS.map((f) => (
                <button
                  key={f.key}
                  type="button"
                  onClick={() => { setFilter(f.key); setPage(0); }}
                  className={`focusable-control flex-shrink-0 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                    filter === f.key
                      ? "bg-[hsl(var(--primary))] text-[hsl(var(--primary-foreground))]"
                      : "text-[hsl(var(--muted-foreground))] hover:bg-[hsl(var(--muted))] hover:text-[hsl(var(--foreground))]"
                  }`}
                >
                  {f.label} <span className="tabular-nums">{counts[f.key]}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Table */}
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[hsl(var(--border))] text-xs text-[hsl(var(--muted-foreground))]">
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
                    <td colSpan={9} className="py-10">
                      <div className="mx-auto max-w-sm text-center">
                        <div className="mx-auto mb-3 grid h-10 w-10 place-items-center rounded-lg bg-[hsl(var(--muted))] text-[hsl(var(--muted-foreground))]">
                          <Icon name="search" size={18} />
                        </div>
                        <div className="text-sm font-semibold text-[hsl(var(--foreground))]">当前筛选没有记录</div>
                        <div className="mt-1 text-xs leading-relaxed text-[hsl(var(--muted-foreground))]">
                          切换筛选条件，或等待自动学习写入新的预测样本。
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
                {pageRows.map((row) => {
                  const isSelected = selectedId === row.ledger_id;
                  const onKey = (e: KeyboardEvent<HTMLTableRowElement>) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      onSelect?.(row.ledger_id);
                    }
                  };
                  const a11yLabel = `${row.home_team ?? ""} 对 ${row.away_team ?? ""} ${row.selection ?? ""} ${statusLabel(row)}`;
                  return (
                    <tr
                      key={row.ledger_id}
                      role="button"
                      tabIndex={0}
                      aria-label={a11yLabel}
                      aria-pressed={isSelected}
                      onKeyDown={onKey}
                      className={`border-b border-[hsl(var(--border))] cursor-pointer transition-colors outline-none focus-visible:ring-2 focus-visible:ring-[hsl(var(--ring))] ${
                        isSelected
                          ? "bg-[hsl(var(--muted))]"
                          : "hover:bg-[hsl(var(--muted))]/60"
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
                            <div className="text-xs font-medium text-[hsl(var(--foreground))] truncate max-w-[120px]">
                              {row.home_team}
                            </div>
                            <div className="text-xs text-[hsl(var(--muted-foreground))] truncate max-w-[120px]">
                              {row.away_team}
                            </div>
                          </div>
                        </div>
                      </td>
                      <td className="px-3 py-2.5 hidden sm:table-cell">
                        <span className="text-xs text-[hsl(var(--muted-foreground))] truncate max-w-[80px] block">{row.league}</span>
                      </td>
                      <td className="px-3 py-2.5 hidden md:table-cell">
                        <span className="text-xs text-[hsl(var(--foreground))] truncate max-w-[120px] block">{row.selection}</span>
                      </td>
                      <td className="px-3 py-2.5 text-right hidden lg:table-cell">
                        <span className="text-xs tabular-nums text-[hsl(var(--foreground))]">
                          {row.learned_probability != null ? formatPercent(row.learned_probability) : row.model_probability != null ? formatPercent(row.model_probability) : "—"}
                        </span>
                      </td>
                      <td className="px-3 py-2.5 text-right">
                        <span className="text-xs tabular-nums font-medium text-[hsl(var(--foreground))]">
                          {row.decimal_odds != null ? formatOdds(row.decimal_odds) : "—"}
                        </span>
                      </td>
                      <td className="px-3 py-2.5 text-right hidden md:table-cell">
                        <span className={`text-xs tabular-nums ${(row.edge ?? 0) > 0 ? "text-emerald-600 dark:text-emerald-400" : "text-[hsl(var(--muted-foreground))]"}`}>
                          {row.edge != null ? formatPercent(row.edge) : "—"}
                        </span>
                      </td>
                      <td className="px-3 py-2.5 text-right hidden lg:table-cell">
                        <span className="text-xs text-[hsl(var(--muted-foreground))]">{localTime(row.kickoff_utc_plus_8)}</span>
                      </td>
                      <td className="px-3 py-2.5">
                        <div className="flex justify-center">
                          {row.settlement_status === "settled" ? (
                            <Badge variant={row.hit === 1 ? "success" : "error"}>
                              {row.hit === 1 ? "命中" : "未中"}
                            </Badge>
                          ) : row.settlement_status === "open" ? (
                            <Badge variant="warning">待结算</Badge>
                          ) : row.settlement_status === "cancelled_postponed" ? (
                            <Badge variant="neutral">延期</Badge>
                          ) : row.settlement_status === "unsettleable" ? (
                            <Badge variant="neutral">无源</Badge>
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
            <div className="flex items-center justify-between px-4 py-2 border-t border-[hsl(var(--border))] text-xs text-[hsl(var(--muted-foreground))]">
              <button
                type="button"
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
                className="shadcn-button-ghost min-h-8 px-3 py-1.5 text-xs disabled:opacity-40"
              >
                上一页
              </button>
              <span>{page + 1} / {totalPages}</span>
              <button
                type="button"
                onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                disabled={page >= totalPages - 1}
                className="shadcn-button-ghost min-h-8 px-3 py-1.5 text-xs disabled:opacity-40"
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
