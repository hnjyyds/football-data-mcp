import { useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowLeft, BarChart3, BrainCircuit, CheckCircle2, ChevronDown, ChevronRight, ChevronUp,
  Clock, Database, Eye, Gauge, ListChecks, RefreshCw, ShieldCheck, Target, TrendingUp,
  Activity, AlertTriangle, XCircle, Rocket, MapPin, CloudSun, UserRound, UsersRound,
  CircleHelp
} from "lucide-react";
import {
  CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis
} from "recharts";
import {
  buildDashboardView, buildMatchDetailView, customerCopy, formatOdds, formatPercent,
  formatSignedPercent, marketLabel, reasonLabel, statusFlagLabel, strategyStatusLabel
} from "./dashboardModel";
import { dashboardPath, matchDetailPath, parseDashboardRoute, type DashboardRoute } from "./appRouting";
import type {
  DashboardMatchDetail, DashboardRecord, DashboardSectionKey, DashboardSnapshot,
  KpiCard, LearningEvent, PredictionLedgerRow, ProbabilityRow
} from "./types";

// --- Layout components ---
import { TopBar } from "./components/layout/TopBar";
import { Sidebar, BottomNav } from "./components/layout/Sidebar";
// --- Dashboard components ---
import { KpiCards } from "./components/dashboard/KpiCards";
import { PickGrid } from "./components/dashboard/PickCard";
import { LedgerTable } from "./components/dashboard/LedgerTable";
import { SettlementFeed } from "./components/dashboard/SettlementFeed";
// --- System components ---
import { StrategyStateCard } from "./components/system/StrategyState";
import { HealthPanel } from "./components/system/HealthPanel";
import { ProductionGates } from "./components/system/ProductionGates";
// --- Shared components ---
import { Badge, toneVariant } from "./components/shared/Badge";
import { LoadingSpinner, SkeletonCard } from "./components/shared/LoadingSpinner";
import { ToastContainer, useToasts } from "./components/shared/Toast";
import { OddsChart } from "./components/detail/OddsChart";
import { TeamMatchup, TeamLogo } from "./components/shared/TeamLogo";

const API_URL = "/api/dashboard";
type DashboardViewModel = ReturnType<typeof buildDashboardView>;
type MatchDetailViewModel = ReturnType<typeof buildMatchDetailView>;

// ─── Utility helpers ─────────────────────────────────────────────────────────

function currentDashboardRoute(): DashboardRoute {
  return parseDashboardRoute(`${window.location.pathname}${window.location.search}`);
}

function localTime(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return new Intl.DateTimeFormat("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false }).format(d);
}

function fullLocalTime(value: string | null | undefined): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return new Intl.DateTimeFormat("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false }).format(d);
}

function numericValue(v: unknown): number | null {
  if (typeof v === "number" && Number.isFinite(v)) return v;
  if (typeof v === "string" && v.trim()) { const p = Number(v); return Number.isFinite(p) ? p : null; }
  return null;
}

function boolValue(v: unknown): boolean {
  if (typeof v === "boolean") return v;
  if (typeof v === "string") return ["1","true","yes","on"].includes(v.trim().toLowerCase());
  return false;
}

function objectRecord(v: unknown): Record<string, unknown> {
  return v && typeof v === "object" && !Array.isArray(v) ? v as Record<string, unknown> : {};
}

function isAfterTime(a: unknown, b: unknown): boolean {
  const da = new Date(typeof a === "string" ? a : ""), db = new Date(typeof b === "string" ? b : "");
  if (Number.isNaN(da.getTime())) return false;
  if (Number.isNaN(db.getTime())) return true;
  return da.getTime() > db.getTime();
}

function latestTime(rows: PredictionLedgerRow[], key: "created_at_utc" | "settled_at_utc"): string | null {
  let latest: string | null = null, latestMs = Number.NEGATIVE_INFINITY;
  for (const row of rows) {
    const v = row[key]; if (!v) continue;
    const ms = new Date(v).getTime();
    if (!Number.isNaN(ms) && ms > latestMs) { latest = v; latestMs = ms; }
  }
  return latest;
}

function displayMatchup(v: string | null | undefined): string {
  return (v || "—").replace(/\s+vs\s+/gi, " 对 ");
}

function readableEventDetail(detail: string): string {
  return customerCopy(detail
    .replaceAll("asian_handicap", "亚盘").replaceAll("over_under", "大小球")
    .replaceAll("moneyline_1x2", "胜平负").replaceAll("collecting_samples", "样本收集中")
    .replaceAll("live_calibration_active", "实时校准已启用")
    .replaceAll("no_positive_edge", "无正向边际").replaceAll("core_market_missing", "核心盘口缺失")
    .replaceAll("calibrated_probability_below_threshold", "概率不足")
    .replaceAll("value_edge_below_threshold", "价值边际不足")
  );
}

// ─── Panel wrapper ───────────────────────────────────────────────────────────

function Panel({ title, icon: Icon, children, className = "", badge }: {
  title?: string; icon?: typeof Target; children: React.ReactNode; className?: string; badge?: string;
}) {
  return (
    <section className={`rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 shadow-sm overflow-hidden ${className}`}>
      {title && (
        <div className="flex items-center gap-2 px-4 py-3 border-b border-slate-100 dark:border-slate-700/50">
          {Icon && <Icon size={16} className="text-slate-500 dark:text-slate-400" />}
          <span className="font-semibold text-slate-900 dark:text-white text-sm flex-1">{title}</span>
          {badge && <Badge variant="neutral">{badge}</Badge>}
        </div>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs text-slate-500 dark:text-slate-400 mb-0.5">{label}</div>
      <div className="text-sm font-semibold text-slate-900 dark:text-white tabular-nums">{value}</div>
    </div>
  );
}

// ─── Overview section ────────────────────────────────────────────────────────

function OverviewSection({ snapshot, view, onSelectRecommendation }: {
  snapshot: DashboardSnapshot;
  view: DashboardViewModel;
  onSelectRecommendation: (r: DashboardRecord) => void;
}) {
  const accountability = view.predictionAccountability;
  const primaryPick = view.primaryPick;

  // Hero stats
  const heroTone = accountability.tone ?? "neutral";
  const heroBg: Record<string, string> = {
    good: "bg-gradient-to-r from-emerald-50 to-white dark:from-emerald-900/20 dark:to-slate-800 border-emerald-200 dark:border-emerald-800",
    bad: "bg-gradient-to-r from-red-50 to-white dark:from-red-900/20 dark:to-slate-800 border-red-200 dark:border-red-800",
    caution: "bg-gradient-to-r from-amber-50 to-white dark:from-amber-900/20 dark:to-slate-800 border-amber-200 dark:border-amber-800",
    neutral: "bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700",
  };

  return (
    <div className="flex flex-col gap-4">
      {/* Hero */}
      <div className={`rounded-xl border p-4 sm:p-6 shadow-sm ${heroBg[heroTone] ?? heroBg.neutral}`}>
        <div className="flex flex-col sm:flex-row sm:items-start gap-4">
          <div className="flex-1 min-w-0">
            <span className="text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">策略总览</span>
            <h2 className="text-xl font-bold text-slate-900 dark:text-white mt-1">{accountability.headline}</h2>
            <p className="text-sm text-slate-600 dark:text-slate-300 mt-1">{accountability.detail}</p>
            <div className="flex flex-wrap gap-2 mt-3">
              <Badge variant={toneVariant(accountability.tone)}>{accountability.policyText}</Badge>
              <Badge variant={toneVariant(view.productionReadiness.tone)}>{view.productionReadiness.actionText}</Badge>
              <Badge variant="neutral">{view.strategyLabel}</Badge>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3 sm:w-48 flex-shrink-0">
            <div className="rounded-lg bg-white/70 dark:bg-slate-900/40 p-3 text-center">
              <div className="text-2xl font-bold text-slate-900 dark:text-white tabular-nums">{snapshot.kpis.asian_pick_count}</div>
              <div className="text-xs text-slate-500 dark:text-slate-400">当前推荐</div>
            </div>
            <div className="rounded-lg bg-white/70 dark:bg-slate-900/40 p-3 text-center">
              <div className="text-2xl font-bold text-slate-900 dark:text-white tabular-nums">{snapshot.prediction_kpis.open_count}</div>
              <div className="text-xs text-slate-500 dark:text-slate-400">未结算</div>
            </div>
            <div className="rounded-lg bg-white/70 dark:bg-slate-900/40 p-3 text-center">
              <div className="text-2xl font-bold text-slate-900 dark:text-white tabular-nums">
                {snapshot.prediction_kpis.hit_rate != null ? `${Math.round(snapshot.prediction_kpis.hit_rate * 100)}%` : "—"}
              </div>
              <div className="text-xs text-slate-500 dark:text-slate-400">命中率</div>
            </div>
            <div className="rounded-lg bg-white/70 dark:bg-slate-900/40 p-3 text-center">
              <div className={`text-2xl font-bold tabular-nums ${(snapshot.prediction_kpis.roi ?? 0) > 0 ? "text-emerald-600 dark:text-emerald-400" : "text-slate-900 dark:text-white"}`}>
                {snapshot.prediction_kpis.roi != null ? `${(snapshot.prediction_kpis.roi * 100).toFixed(1)}%` : "—"}
              </div>
              <div className="text-xs text-slate-500 dark:text-slate-400">ROI</div>
            </div>
          </div>
        </div>
      </div>

      {/* KPI strip */}
      <KpiCards cards={view.kpiCards} />

      {/* Picks */}
      <Panel title="当前推荐" icon={TrendingUp} badge="亚盘">
        <PickGrid
          records={snapshot.asian_picks}
          onSelect={onSelectRecommendation}
          emptyMessage="暂无可发布推荐信号"
        />
      </Panel>

      {/* Settlement feed */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <SettlementFeed records={snapshot.recent_settlements ?? []} />
        <StrategyStateCard snapshot={snapshot} />
      </div>
    </div>
  );
}

// ─── Signals section ─────────────────────────────────────────────────────────

function SignalsSection({ snapshot, view, onSelectLedger, onSelectRecommendation }: {
  snapshot: DashboardSnapshot;
  view: DashboardViewModel;
  onSelectLedger: (id: string) => void;
  onSelectRecommendation: (r: DashboardRecord) => void;
}) {
  return (
    <div className="flex flex-col gap-4">
      {/* Candidate funnel */}
      <Panel title="候选分析漏斗" icon={Eye}>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          {view.filterGroups.map((f) => (
            <div key={f.reason} className="text-center p-3 rounded-lg bg-slate-50 dark:bg-slate-700/40">
              <div className="text-lg font-bold text-slate-900 dark:text-white tabular-nums">{f.count}</div>
              <div className="text-xs text-slate-500 dark:text-slate-400 mt-0.5 truncate">{f.label || reasonLabel(f.reason)}</div>
            </div>
          ))}
        </div>
      </Panel>

      {/* Prediction ledger */}
      <LedgerTable
        rows={snapshot.prediction_ledger ?? []}
        selectedId={null}
        onSelect={onSelectLedger}
      />
    </div>
  );
}

// ─── Production section ───────────────────────────────────────────────────────

function ProductionSection({ view }: { view: DashboardViewModel }) {
  const gates = view.productionReadiness.gateRows ?? [];
  const formattedGates = gates.map((g) => ({
    name: statusFlagLabel(g.key ?? ""),
    status: g.title,
    tone: g.tone,
    detail: g.detail,
    required: false,
  }));
  return (
    <div className="flex flex-col gap-4">
      <ProductionGates
        gates={formattedGates}
        overallTone={view.productionReadiness.tone ?? "neutral"}
        overallLabel={view.productionReadiness.actionText ?? "—"}
      />
      {view.recommendationOpportunity && (
        <Panel title="推荐发布机会" icon={Rocket}>
          <div className="text-sm text-slate-700 dark:text-slate-300 mb-3">
            {view.recommendationOpportunity.releaseGate?.detail ?? view.recommendationOpportunity.detail ?? "暂无分析"}
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {(view.recommendationOpportunity.metrics ?? []).map((item) => (
              <Metric key={item.label} label={item.label} value={String(item.value ?? "—")} />
            ))}
          </div>
        </Panel>
      )}
    </div>
  );
}

// ─── Model section ────────────────────────────────────────────────────────────

function ModelSection({ view, snapshot }: { view: DashboardViewModel; snapshot: DashboardSnapshot }) {
  const backtestCurve = view.backtestCurve;

  return (
    <div className="flex flex-col gap-4">
      {/* Backtest curve */}
      {backtestCurve?.points?.length > 0 && (
        <Panel title="累计 ROI 曲线" icon={BarChart3}>
          <OddsChart
            points={backtestCurve.points.map((p) => ({ label: String((p as any).x ?? p.index), roi: p.y }))}
            lines={["roi"]}
            referenceValue={0}
          />
        </Panel>
      )}

      {/* Calibration bands from snapshot */}
      {(snapshot.buckets ?? []).length > 0 && (
        <Panel title="概率校准分组" icon={Gauge}>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 dark:border-slate-700/50 text-xs text-slate-500 dark:text-slate-400">
                  <th className="text-left py-2 px-3 font-medium">概率区间</th>
                  <th className="text-right py-2 px-3 font-medium">样本数</th>
                  <th className="text-right py-2 px-3 font-medium">命中率</th>
                  <th className="text-right py-2 px-3 font-medium">ROI</th>
                </tr>
              </thead>
              <tbody>
                {(snapshot.buckets ?? []).slice(0, 20).map((b, i) => (
                  <tr key={i} className="border-b border-slate-50 dark:border-slate-700/30">
                    <td className="py-2 px-3 text-xs text-slate-700 dark:text-slate-300">{(b as any).calibration_band ?? (b as any).probability_bucket}</td>
                    <td className="py-2 px-3 text-xs text-right tabular-nums text-slate-600 dark:text-slate-400">{(b as any).sample_count}</td>
                    <td className="py-2 px-3 text-xs text-right tabular-nums">{(b as any).hit_rate != null ? formatPercent((b as any).hit_rate) : "—"}</td>
                    <td className={`py-2 px-3 text-xs text-right tabular-nums font-medium ${((b as any).roi ?? 0) > 0 ? "text-emerald-600 dark:text-emerald-400" : "text-red-500 dark:text-red-400"}`}>
                      {(b as any).roi != null ? formatSignedPercent((b as any).roi) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}

      {/* CLV Tracking */}
      {view.clvTracking?.metrics && view.clvTracking.metrics.length > 0 && (
        <Panel title="收盘线价值 (CLV)" icon={TrendingUp}>
          <div className="text-sm text-slate-700 dark:text-slate-300 mb-3">{view.clvTracking.detail}</div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {view.clvTracking.metrics.map((m, i) => (
              <Metric key={i} label={m.label} value={m.value} />
            ))}
          </div>
        </Panel>
      )}
    </div>
  );
}

// ─── Data section ─────────────────────────────────────────────────────────────

function DataSection({ snapshot, view }: { snapshot: DashboardSnapshot; view: DashboardViewModel }) {
  const auto = objectRecord(snapshot.auto_learning_state);
  const resultSummary = objectRecord(auto.last_result_summary);
  const enabled = boolValue(auto.enabled);
  const running = isAfterTime(auto.last_started_at_utc, auto.last_finished_at_utc);
  const runCount = numericValue(auto.run_count) ?? 0;
  const formalRecords = numericValue(resultSummary.asian_record_count) ?? 0;
  const observationRecords = numericValue(resultSummary.asian_learning_observation_record_count) ?? 0;
  const shadowRecords = numericValue(resultSummary.asian_shadow_prediction_record_count) ?? numericValue(resultSummary.saved_shadow_prediction_count) ?? 0;
  const analyzedCount = numericValue(resultSummary.asian_analyzed_count) ?? 0;
  const settledRecords = (numericValue(resultSummary.settled_count) ?? 0) + (numericValue(resultSummary.shadow_settled_count) ?? 0);
  const statusTone: KpiCard["tone"] = (auto.last_error as any) ? "bad" : running ? "caution" : enabled ? "good" : "bad";
  const statusText = !enabled ? "自动学习关闭" : (auto.last_error as any) ? "异常" : running ? "扫描中" : runCount > 0 ? "上轮已完成" : "等待首轮";

  return (
    <div className="flex flex-col gap-4">
      {/* Auto-learning status */}
      <Panel title="自动学习运行状态" icon={Activity} badge={statusText}>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 mb-4">
          <Metric label="候选/分析" value={`${numericValue(resultSummary.asian_total_candidates) ?? 0}/${analyzedCount}`} />
          <Metric label="发布/观察/影子" value={`${formalRecords}/${observationRecords}/${shadowRecords}`} />
          <Metric label="上轮结算" value={`${settledRecords} 条`} />
          <Metric label="最新结算" value={localTime(latestTime(snapshot.prediction_ledger ?? [], "settled_at_utc"))} />
          <Metric label="上次完成" value={fullLocalTime(typeof auto.last_finished_at_utc === "string" ? auto.last_finished_at_utc : null)} />
        </div>
        {(auto.last_error as any) && (
          <div className="text-xs text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 rounded-lg p-2">
            上次错误：{String(auto.last_error)}
          </div>
        )}
      </Panel>

      <HealthPanel snapshot={snapshot} />

      {/* Events log */}
      {(snapshot.learning_events ?? []).length > 0 && (
        <Panel title="系统事件" icon={Clock}>
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {(snapshot.learning_events ?? []).slice(0, 30).map((event, i) => (
              <div key={i} className="flex items-start gap-2 text-xs">
                <span className="text-slate-400 dark:text-slate-500 flex-shrink-0 tabular-nums">{localTime(event.at_utc)}</span>
                <span className={`flex-shrink-0 px-1.5 py-0.5 rounded text-xs ${
                  event.severity === "error" || event.severity === "blocked" ? "bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300" :
                  event.severity === "warning" ? "bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300" :
                  "bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300"
                }`}>{event.severity ?? "info"}</span>
                <span className="text-slate-600 dark:text-slate-300"><strong>{event.title}</strong> {readableEventDetail(event.detail ?? "")}</span>
              </div>
            ))}
          </div>
        </Panel>
      )}
    </div>
  );
}

// ─── Match detail page ────────────────────────────────────────────────────────

function MatchDetailPage({
  ledgerId, detail, loading, error, onBack
}: {
  ledgerId: string;
  detail: DashboardMatchDetail | null;
  loading: boolean;
  error: string | null;
  onBack: () => void;
}) {
  const view = useMemo(() => detail ? buildMatchDetailView(detail) : null, [detail]);

  return (
    <div className="max-w-screen-lg mx-auto px-4 py-4 pb-20 lg:pb-4">
      <button
        type="button"
        onClick={onBack}
        className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white mb-4 transition-colors"
      >
        <ArrowLeft size={16} />
        返回总览
      </button>

      {loading && <LoadingSpinner label="读取比赛详情..." />}
      {error && (
        <div className="rounded-xl border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20 p-4 text-sm text-red-700 dark:text-red-300">
          {error}
        </div>
      )}

      {detail && view && (
        <div className="flex flex-col gap-4">
          {/* Match header */}
          <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 shadow-sm p-4">
            <div className="flex items-center gap-4">
              <TeamMatchup
                home={detail.record.home_team ?? ""}
                away={detail.record.away_team ?? ""}
                homeLogo={detail.record.home_team_logo_url}
                awayLogo={detail.record.away_team_logo_url}
                meta={detail.record.league}
                size="md"
              />
              <div className="ml-auto text-right">
                <div className="text-sm font-medium text-slate-700 dark:text-slate-300">{localTime(detail.record.kickoff_utc_plus_8)}</div>
                {detail.record.settlement_status === "settled" && (
                  <div className="mt-1">
                    <Badge variant={detail.record.hit === 1 ? "success" : "error"}>
                      {detail.record.hit === 1 ? "命中" : "未命中"}
                    </Badge>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Probabilities */}
          <Panel title="概率分析" icon={Gauge}>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <Metric label="模型概率" value={detail.record.model_probability != null ? formatPercent(detail.record.model_probability) : "—"} />
              <Metric label="校准概率" value={detail.record.learned_probability != null ? formatPercent(detail.record.learned_probability) : "—"} />
              <Metric label="市场概率" value={detail.record.market_probability != null ? formatPercent(detail.record.market_probability) : "—"} />
              <Metric label="价值边际" value={detail.record.edge != null ? formatSignedPercent(detail.record.edge) : "—"} />
            </div>
          </Panel>

          {/* Odds trend chart */}
          {view.oddsTrend && view.oddsTrend.points.length > 0 && (
            <OddsChart
              title={view.oddsTrend.title || "赔率走势"}
              points={view.oddsTrend.points.map((p) => ({ ...p, label: (p as any).label ?? String((p as any).x ?? "") }))}
              lines={(view.oddsTrend.series ?? []).map((s: any) => s.key ?? s.id ?? "").filter(Boolean)}
            />
          )}

          {/* Odds snapshots */}
          {view.oddsGroups?.length > 0 && (
            <Panel title="多公司赔率快照" icon={Database}>
              <div className="space-y-3">
                {view.oddsGroups.map((group: any, gi: number) => (
                  <div key={gi} className="border border-slate-100 dark:border-slate-700/50 rounded-lg overflow-hidden">
                    <div className="bg-slate-50 dark:bg-slate-700/40 px-3 py-2 text-xs font-medium text-slate-700 dark:text-slate-300">
                      {group.bookmaker ?? group.providerText ?? "—"}
                    </div>
                    <div className="p-3 grid grid-cols-3 sm:grid-cols-6 gap-2 text-xs">
                      {(group.rows ?? group.odds ?? []).map((odd: any, i: number) => (
                        <div key={i} className="text-center">
                          <div className="text-slate-500 dark:text-slate-400">{odd.label ?? odd.selectionText ?? "—"}</div>
                          <div className="font-semibold tabular-nums text-slate-900 dark:text-white">{(odd.value ?? odd.price) != null ? formatOdds(odd.value ?? odd.price) : (odd.priceText ?? "—")}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </Panel>
          )}

          {/* Risk flags */}
          {((detail.record as any).risk_flags?.length ?? 0) > 0 && (
            <Panel title="风险标记" icon={AlertTriangle}>
              <div className="flex flex-wrap gap-2">
                {((detail.record as any).risk_flags as string[]).map((flag: string, i: number) => (
                  <Badge key={i} variant="error">{statusFlagLabel(flag)}</Badge>
                ))}
              </div>
            </Panel>
          )}
        </div>
      )}
    </div>
  );
}

// ─── App root ─────────────────────────────────────────────────────────────────

export function App() {
  const [route, setRoute] = useState<DashboardRoute>(() => currentDashboardRoute());
  const [snapshot, setSnapshot] = useState<DashboardSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [selectedLedgerId, setSelectedLedgerId] = useState<string | null>(null);
  const [detail, setDetail] = useState<DashboardMatchDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [activeSection, setActiveSection] = useState<DashboardSectionKey>("overview");
  const [darkMode, setDarkMode] = useState(() => window.matchMedia("(prefers-color-scheme: dark)").matches);
  const { toasts, dismiss, push } = useToasts();
  const prevPickCount = useRef<number | null>(null);

  // Dark mode effect
  useEffect(() => {
    document.documentElement.classList.toggle("dark", darkMode);
  }, [darkMode]);

  // Route sync
  useEffect(() => {
    const syncRoute = () => setRoute(currentDashboardRoute());
    window.addEventListener("popstate", syncRoute);
    return () => window.removeEventListener("popstate", syncRoute);
  }, []);

  function navigateToDashboard() {
    window.history.pushState(null, "", dashboardPath());
    setRoute({ page: "dashboard" });
  }

  function navigateToMatch(ledgerId: string) {
    window.history.pushState(null, "", matchDetailPath(ledgerId));
    setSelectedLedgerId(ledgerId);
    setRoute({ page: "match", ledgerId });
  }

  const detailLedgerId = route.page === "match" ? route.ledgerId : null;

  // Main data polling
  useEffect(() => {
    let cancelled = false;
    async function load(isInitial = false) {
      if (!isInitial) setRefreshing(true);
      try {
        const response = await fetch(API_URL, { cache: "no-store" });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json() as DashboardSnapshot;
        if (!cancelled) {
          setSnapshot((prev) => {
            // Toast on new picks
            const newCount = data.asian_picks?.length ?? 0;
            if (prevPickCount.current !== null && newCount > (prevPickCount.current ?? 0)) {
              push(`新增 ${newCount - prevPickCount.current!} 个推荐信号`, "success");
            }
            prevPickCount.current = newCount;
            return data;
          });
          setError(null);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      } finally {
        if (!cancelled) { setLoading(false); setRefreshing(false); }
      }
    }
    void load(true);
    const timer = window.setInterval(() => load(false), 30000);
    return () => { cancelled = true; window.clearInterval(timer); };
  }, []);

  // Detail loader
  useEffect(() => {
    let cancelled = false;
    async function loadDetail(ledgerId: string) {
      setDetailLoading(true); setDetailError(null);
      setDetail((cur) => cur?.record.ledger_id === ledgerId ? cur : null);
      try {
        const resp = await fetch(`${API_URL}/match/${encodeURIComponent(ledgerId)}`, { cache: "no-store" });
        const data = await resp.json() as DashboardMatchDetail;
        if (!resp.ok) throw new Error(resp.status === 404 ? "当前台账中不存在这场预测" : `HTTP ${resp.status}`);
        if (data.status !== "ok") throw new Error(data.status);
        if (!cancelled) { setDetail(data); setDetailError(null); }
      } catch (err) {
        if (!cancelled) { setDetail(null); setDetailError(err instanceof Error ? err.message : String(err)); }
      } finally {
        if (!cancelled) setDetailLoading(false);
      }
    }
    if (!detailLedgerId) { setDetail(null); setDetailError(null); setDetailLoading(false); return () => { cancelled = true; }; }
    void loadDetail(detailLedgerId);
    return () => { cancelled = true; };
  }, [detailLedgerId]);

  const view = useMemo(() => snapshot ? buildDashboardView(snapshot) : null, [snapshot]);
  const isMatchPage = route.page === "match";

  return (
    <div className={`min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-white`}>
      <TopBar
        snapshot={snapshot}
        darkMode={darkMode}
        onToggleDark={() => setDarkMode((d) => !d)}
        refreshing={refreshing}
        lastRefreshError={error}
      />

      <ToastContainer toasts={toasts} onDismiss={dismiss} />

      {isMatchPage ? (
        <MatchDetailPage
          ledgerId={route.ledgerId}
          detail={detail}
          loading={detailLoading}
          error={detailError}
          onBack={navigateToDashboard}
        />
      ) : (
        <div className="flex max-w-screen-2xl mx-auto">
          {/* Sidebar (desktop) */}
          <Sidebar active={activeSection} onChange={setActiveSection} />

          {/* Main content */}
          <main className="flex-1 min-w-0 px-4 py-4 pb-20 lg:pb-4">
            {error && (
              <div className="mb-3 rounded-xl border border-amber-200 dark:border-amber-700 bg-amber-50 dark:bg-amber-900/20 px-4 py-2 text-sm text-amber-800 dark:text-amber-200 flex items-center gap-2">
                <AlertTriangle size={14} />
                数据刷新失败：{error}。显示最近快照。
              </div>
            )}

            {loading && !snapshot && (
              <div className="flex flex-col gap-4">
                {[1, 2, 3].map((i) => <SkeletonCard key={i} lines={4} />)}
              </div>
            )}

            {snapshot && view && (
              <>
                {activeSection === "overview" && (
                  <OverviewSection
                    snapshot={snapshot}
                    view={view}
                    onSelectRecommendation={(r) => navigateToMatch(`recommendation:${r.id}`)}
                  />
                )}
                {activeSection === "production" && <ProductionSection view={view} />}
                {activeSection === "model" && <ModelSection view={view} snapshot={snapshot} />}
                {activeSection === "signals" && (
                  <SignalsSection
                    snapshot={snapshot}
                    view={view}
                    onSelectLedger={navigateToMatch}
                    onSelectRecommendation={(r) => navigateToMatch(`recommendation:${r.id}`)}
                  />
                )}
                {activeSection === "data" && <DataSection snapshot={snapshot} view={view} />}

                <footer className="mt-8 text-xs text-slate-400 dark:text-slate-600 text-center py-4 border-t border-slate-200 dark:border-slate-800">
                  只读监控台 · 不执行交易动作 · 数据来自自动学习库与结算校准状态
                </footer>
              </>
            )}
          </main>
        </div>
      )}

      {/* Bottom nav (mobile) */}
      {!isMatchPage && <BottomNav active={activeSection} onChange={setActiveSection} />}
    </div>
  );
}
