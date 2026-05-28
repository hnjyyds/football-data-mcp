import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import { Icon, type IconName } from "./components/shared/Icon";
import {
  CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis
} from "recharts";
import {
  buildDashboardView, buildMatchDetailView, customerCopy, formatOdds, formatPercent,
  formatSignedPercent, marketLabel, reasonLabel, statusFlagLabel, strategyStatusLabel
} from "./dashboardModel";
import { dashboardPath, matchDetailPath, parseDashboardRoute, type DashboardRoute } from "./appRouting";
import { fetchDashboardSnapshot, fetchMatchDetail, HttpError } from "./api/dashboardClient";
import { createPoller, withRetry } from "./api/poller";
import { reportError } from "./errorReporter";
import { useDarkMode } from "./useDarkMode";
import { formatBeijingShort, formatBeijingFull } from "./formatTime";
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
import { Panel, Metric } from "./components/shared/Panel";
import { ProfitabilityHeroBar } from "./components/dashboard/ProfitabilityHeroBar";
import { ProfitabilityPanel } from "./components/dashboard/ProfitabilityPanel";
import { HeatMap } from "./components/charts/HeatMap";
import { ReliabilityDiagram } from "./components/charts/ReliabilityDiagram";

type DashboardViewModel = ReturnType<typeof buildDashboardView>;
type MatchDetailViewModel = ReturnType<typeof buildMatchDetailView>;

type LineupPlayer = { number?: number | string | null; name?: string; position?: string };
type LineupSide = { formation?: string; starterCountText?: string; players?: LineupPlayer[] };

// ─── Utility helpers ─────────────────────────────────────────────────────────

function currentDashboardRoute(): DashboardRoute {
  return parseDashboardRoute(`${window.location.pathname}${window.location.search}`);
}

const localTime = formatBeijingShort;
const fullLocalTime = formatBeijingFull;

const MatchDetailPage = lazy(() => import("./pages/MatchDetailPage"));

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

// ─── Overview section ────────────────────────────────────────────────────────

function OverviewSection({ snapshot, view, onSelectRecommendation }: {
  snapshot: DashboardSnapshot;
  view: DashboardViewModel;
  onSelectRecommendation: (r: DashboardRecord) => void;
}) {
  const accountability = view.predictionAccountability;
  const hitRate = snapshot.prediction_kpis.hit_rate;
  const roi = snapshot.prediction_kpis.roi;
  const accentTone = toneVariant(accountability.tone);

  // Top stat row data
  const topStats = [
    {
      label: "当前推荐",
      value: snapshot.kpis.asian_pick_count,
      caption: "可发布",
      tone: snapshot.kpis.asian_pick_count > 0 ? "good" : "neutral",
    },
    {
      label: "未结算",
      value: snapshot.prediction_kpis.open_count,
      caption: "等待结算",
      tone: "info",
    },
    {
      label: "命中率",
      value: hitRate != null ? `${Math.round(hitRate * 100)}%` : "—",
      caption: `${snapshot.prediction_kpis.settled_count ?? 0} 场已结算`,
      tone: hitRate != null && hitRate >= 0.55 ? "good" : "neutral",
    },
    {
      label: "ROI",
      value: roi != null ? `${roi >= 0 ? "+" : ""}${(roi * 100).toFixed(1)}%` : "—",
      caption: "纸面收益",
      tone: roi != null && roi > 0 ? "good" : roi != null && roi < 0 ? "bad" : "neutral",
    },
  ];

  return (
    <div className="flex flex-col gap-3">
      {/* Profitability hero bar - 最显眼位置 */}
      <ProfitabilityHeroBar forecast={snapshot.profitability_forecast} />

      {/* Status bar - 单行，紧凑 */}
      <div className="flex flex-col md:flex-row md:items-center gap-2 md:gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-0.5">
            <Badge variant={accentTone}>{accountability.policyText}</Badge>
            <Badge variant={toneVariant(view.productionReadiness.tone)}>{view.productionReadiness.actionText}</Badge>
            <Badge variant="neutral">{view.strategyLabel}</Badge>
          </div>
          <p className="text-xs text-slate-600 dark:text-slate-400 truncate">{accountability.detail}</p>
        </div>
      </div>

      {/* Top stat row - 4 columns always */}
      <div className="grid grid-cols-4 gap-2 md:gap-3">
        {topStats.map((s) => {
          const toneTextMap: Record<string, string> = {
            good: "text-emerald-600 dark:text-emerald-400",
            bad: "text-red-600 dark:text-red-400",
            info: "text-sky-600 dark:text-sky-400",
            neutral: "text-slate-900 dark:text-white",
          };
          return (
            <div key={s.label} className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-3 shadow-sm">
              <div className="text-[11px] text-slate-500 dark:text-slate-400 mb-0.5">{s.label}</div>
              <div className={`text-xl md:text-2xl font-bold tabular-nums ${toneTextMap[s.tone] ?? toneTextMap.neutral}`}>
                {s.value}
              </div>
              <div className="text-[10px] text-slate-400 dark:text-slate-500 mt-0.5">{s.caption}</div>
            </div>
          );
        })}
      </div>

      {/* Main grid: picks (2/3) + side column (1/3) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        {/* Picks column */}
        <div className="lg:col-span-2 flex flex-col gap-3">
          <Panel title="当前推荐" icon="trendUp" badge={`${snapshot.asian_picks?.length ?? 0} 条·亚盘`} dense>
            <PickGrid
              records={snapshot.asian_picks}
              onSelect={onSelectRecommendation}
              emptyMessage="暂无可发布推荐信号"
            />
          </Panel>
          <SettlementFeed records={snapshot.recent_settlements ?? []} />
        </div>

        {/* Side column */}
        <div className="flex flex-col gap-3">
          <StrategyStateCard snapshot={snapshot} />
          <KpiCards cards={view.kpiCards} compact />
        </div>
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
  const mb = snapshot.market_breakdown;
  // Build heatmap cells from market_breakdown (league × market)
  const heatmapCells = (mb?.heatmap_cells ?? [])
    .filter((c) => c.hit_rate != null && c.sample_count >= 1)
    .map((c) => ({
      x: c.league,
      y: c.market,
      value: c.hit_rate ?? 0,
      sampleSize: c.sample_count,
      tooltip: `${c.league} × ${c.market}: 命中 ${((c.hit_rate ?? 0) * 100).toFixed(1)}% · ROI ${(((c.roi ?? 0) * 100)).toFixed(1)}% · n=${c.sample_count}`,
    }));
  const roiCells = (mb?.heatmap_cells ?? [])
    .filter((c) => c.roi != null && c.sample_count >= 1)
    .map((c) => ({
      x: c.league,
      y: c.market,
      value: c.roi ?? 0,
      sampleSize: c.sample_count,
      tooltip: `${c.league} × ${c.market}: ROI ${((c.roi ?? 0) * 100).toFixed(1)}% (n=${c.sample_count})`,
    }));

  return (
    <div className="flex flex-col gap-4">
      {/* Heatmaps - 联赛 × 市场命中率 / ROI */}
      {(mb?.heatmap_cells?.length ?? 0) > 0 && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          <HeatMap
            cells={heatmapCells}
            xLabels={mb?.leagues ?? []}
            yLabels={mb?.markets ?? []}
            title="命中率热力图（联赛 × 市场）"
            subtitle={`总结算样本 ${mb?.total_settled ?? 0}，颜色越深命中率越高，透明度反映样本量`}
            domain={[0, 1]}
            scale="sequential"
            formatValue={(v) => `${(v * 100).toFixed(0)}%`}
          />
          <HeatMap
            cells={roiCells}
            xLabels={mb?.leagues ?? []}
            yLabels={mb?.markets ?? []}
            title="ROI 热力图（联赛 × 市场）"
            subtitle="红=亏损 / 灰=平 / 绿=盈利，可识别强势赛事"
            domain={[-0.30, 0.30]}
            scale="diverging"
            formatValue={(v) => `${v > 0 ? "+" : ""}${(v * 100).toFixed(0)}%`}
          />
        </div>
      )}

      {/* Candidate funnel */}
      <Panel title="候选分析漏斗" icon="eye">
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
        <Panel title="推荐发布机会" icon="production">
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
  const buckets = snapshot.buckets ?? [];

  // Build reliability points from market-global buckets.
  // The dashboard contract normalizes to {band, sample_count, hit_rate, avg_model_probability}.
  const reliabilityPoints = buckets
    .filter((b) => b.sample_count >= 3 && b.avg_model_probability != null && b.hit_rate != null)
    .map((b) => ({
      predicted: Number(b.avg_model_probability),
      actual: Number(b.hit_rate),
      samples: Number(b.sample_count),
      bucket: String(b.band || "").replace("prob:", ""),
    }));

  const latestValidation = snapshot.latest_validation ?? null;

  return (
    <div className="flex flex-col gap-4">
      {/* Profitability forecast - top of model section */}
      <ProfitabilityPanel forecast={snapshot.profitability_forecast} />

      {/* Latest holdout validation snapshot */}
      {latestValidation && (
        <Panel title="最近一次 Holdout 验证" icon="gauge" badge={latestValidation.beats_market ? "✓ 跑赢市场" : "✗ 未跑赢"}>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-3">
            <Metric label="Log Loss 差" value={latestValidation.log_loss_diff != null ? (latestValidation.log_loss_diff < 0 ? "" : "+") + latestValidation.log_loss_diff.toFixed(4) : "—"} />
            <Metric label="Brier 差" value={latestValidation.brier_diff != null ? (latestValidation.brier_diff < 0 ? "" : "+") + latestValidation.brier_diff.toFixed(4) : "—"} />
            <Metric label="ROI" value={latestValidation.roi != null ? `${(latestValidation.roi * 100).toFixed(1)}%` : "—"} />
            <Metric label="样本数" value={`${latestValidation.bet_count}/${latestValidation.evaluated_count}`} />
          </div>
          <div className="text-xs text-ink-600 dark:text-ink-400 leading-relaxed">
            自动化就绪度: <strong className={latestValidation.automation_readiness === "paper_trade_only" ? "text-success-600" : latestValidation.automation_readiness === "watchlist" ? "text-warning-600" : "text-danger-600"}>{latestValidation.automation_readiness}</strong>
            <span className="mx-2">·</span>
            训练赛季: {latestValidation.training_seasons?.join(", ")}
            <span className="mx-2">·</span>
            验证赛季: {latestValidation.validation_seasons?.join(", ")}
            <span className="mx-2">·</span>
            {latestValidation.created_at_utc ? fullLocalTime(latestValidation.created_at_utc) : "—"}
          </div>
        </Panel>
      )}

      {/* Reliability diagram - probability calibration */}
      {reliabilityPoints.length > 0 && (
        <ReliabilityDiagram
          points={reliabilityPoints}
          subtitle={`基于 ${reliabilityPoints.length} 个概率桶 · 散点越靠近对角线，模型概率越准`}
        />
      )}

      {/* Per-market breakdown table */}
      {(snapshot.market_breakdown?.by_market?.length ?? 0) > 0 && (
        <Panel title="按市场表现分组" icon="trendUp">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 dark:border-slate-700/50 text-xs text-slate-500 dark:text-slate-400">
                  <th className="text-left py-2 px-3 font-medium">市场</th>
                  <th className="text-right py-2 px-3 font-medium">已结算</th>
                  <th className="text-right py-2 px-3 font-medium">命中</th>
                  <th className="text-right py-2 px-3 font-medium">命中率</th>
                  <th className="text-right py-2 px-3 font-medium">ROI</th>
                </tr>
              </thead>
              <tbody>
                {(snapshot.market_breakdown?.by_market ?? []).map((row) => (
                  <tr key={row.market} className="border-b border-slate-50 dark:border-slate-700/30">
                    <td className="py-2 px-3 text-xs font-medium text-slate-800 dark:text-slate-200">{row.market}</td>
                    <td className="py-2 px-3 text-xs text-right tabular-nums text-slate-600 dark:text-slate-400">{row.sample_count}</td>
                    <td className="py-2 px-3 text-xs text-right tabular-nums text-slate-600 dark:text-slate-400">{row.hit_count}</td>
                    <td className="py-2 px-3 text-xs text-right tabular-nums font-medium">
                      {row.hit_rate != null ? formatPercent(row.hit_rate) : "—"}
                    </td>
                    <td className={`py-2 px-3 text-xs text-right tabular-nums font-medium ${(row.roi ?? 0) > 0 ? "text-emerald-600 dark:text-emerald-400" : "text-red-500 dark:text-red-400"}`}>
                      {row.roi != null ? formatSignedPercent(row.roi) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}

      {/* Backtest curve */}
      {backtestCurve?.points?.length > 0 && (
        <Panel title="累计 ROI 曲线" icon="chart">
          <OddsChart
            points={backtestCurve.points.map((p) => ({
              label: String(p.index),
              roi: p.cumulativeValue,
            }))}
            lines={["roi"]}
            referenceValue={0}
          />
        </Panel>
      )}

      {/* Calibration bands from snapshot */}
      {(snapshot.buckets ?? []).length > 0 && (
        <Panel title="概率校准分组" icon="gauge">
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
                    <td className="py-2 px-3 text-xs text-slate-700 dark:text-slate-300">{b.band}</td>
                    <td className="py-2 px-3 text-xs text-right tabular-nums text-slate-600 dark:text-slate-400">{b.sample_count}</td>
                    <td className="py-2 px-3 text-xs text-right tabular-nums">{b.hit_rate != null ? formatPercent(b.hit_rate) : "—"}</td>
                    <td className={`py-2 px-3 text-xs text-right tabular-nums font-medium ${(b.roi ?? 0) > 0 ? "text-emerald-600 dark:text-emerald-400" : "text-red-500 dark:text-red-400"}`}>
                      {b.roi != null ? formatSignedPercent(b.roi) : "—"}
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
        <Panel title="收盘线价值 (CLV)" icon="trendUp">
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
  const auto = snapshot.auto_learning_state;
  const resultSummary = auto.last_result_summary ?? {};
  const enabled = auto.enabled;
  const running = isAfterTime(auto.last_started_at_utc, auto.last_finished_at_utc);
  const runCount = auto.run_count;
  const formalRecords = resultSummary.asian_record_count ?? 0;
  const observationRecords = numericValue((resultSummary as Record<string, unknown>).asian_learning_observation_record_count) ?? 0;
  const shadowRecords = resultSummary.asian_shadow_prediction_record_count ?? resultSummary.saved_shadow_prediction_count ?? 0;
  const analyzedCount = resultSummary.asian_analyzed_count ?? 0;
  const settledRecords = (resultSummary.settled_count ?? 0) + (resultSummary.shadow_settled_count ?? 0);
  const hasError = !!auto.last_error;
  const statusTone: KpiCard["tone"] = hasError ? "bad" : running ? "caution" : enabled ? "good" : "bad";
  const statusText = !enabled ? "自动学习关闭" : hasError ? "异常" : running ? "扫描中" : runCount > 0 ? "上轮已完成" : "等待首轮";

  return (
    <div className="flex flex-col gap-4">
      {/* Auto-learning status */}
      <Panel title="自动学习运行状态" icon="activity" badge={statusText}>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 mb-4">
          <Metric label="候选/分析" value={`${resultSummary.asian_total_candidates ?? 0}/${analyzedCount}`} />
          <Metric label="发布/观察/影子" value={`${formalRecords}/${observationRecords}/${shadowRecords}`} />
          <Metric label="上轮结算" value={`${settledRecords} 条`} />
          <Metric label="最新结算" value={localTime(latestTime(snapshot.prediction_ledger ?? [], "settled_at_utc"))} />
          <Metric label="上次完成" value={fullLocalTime(auto.last_finished_at_utc ?? null)} />
        </div>
        {hasError && (
          <div className="text-xs text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20 rounded-lg p-2">
            上次错误：{auto.last_error}
          </div>
        )}
      </Panel>

      <HealthPanel snapshot={snapshot} />

      {/* Events log */}
      {(snapshot.learning_events ?? []).length > 0 && (
        <Panel title="系统事件" icon="clock">
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
  const [darkMode, setDarkMode] = useDarkMode();
  const { toasts, dismiss, push } = useToasts();
  const prevPickCount = useRef<number | null>(null);

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

  // Main data polling — retry/backoff, AbortController mutex, visibility-aware
  useEffect(() => {
    const poller = createPoller<DashboardSnapshot>(
      async ({ signal }) => {
        setRefreshing(true);
        try {
          return await withRetry(() => fetchDashboardSnapshot({ signal }), {
            retries: 2,
            baseDelayMs: 1000,
            maxDelayMs: 8000,
            signal,
          });
        } finally {
          setRefreshing(false);
        }
      },
      {
        intervalMs: 30000,
        onResult: (data) => {
          setSnapshot(() => {
            const newCount = data.asian_picks?.length ?? 0;
            if (prevPickCount.current !== null && newCount > (prevPickCount.current ?? 0)) {
              push(`新增 ${newCount - prevPickCount.current!} 个推荐信号`, "success");
            }
            prevPickCount.current = newCount;
            return data;
          });
          setError(null);
          setLoading(false);
        },
        onError: (err) => {
          const message = err instanceof Error ? err.message : String(err);
          setError(message);
          setLoading(false);
          reportError(err, { kind: "dashboard-fetch" });
        },
      }
    );
    poller.start();
    return () => poller.stop();
  }, [push]);

  // Detail loader — AbortController on dependency change
  useEffect(() => {
    if (!detailLedgerId) {
      setDetail(null);
      setDetailError(null);
      setDetailLoading(false);
      return;
    }
    const controller = new AbortController();
    let cancelled = false;
    setDetailLoading(true);
    setDetailError(null);
    setDetail((cur) => (cur?.record.ledger_id === detailLedgerId ? cur : null));
    fetchMatchDetail(detailLedgerId, { signal: controller.signal })
      .then((data) => {
        if (cancelled) return;
        if (data.status !== "ok") {
          setDetail(null);
          setDetailError(data.status);
          return;
        }
        setDetail(data);
        setDetailError(null);
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof DOMException && err.name === "AbortError") return;
        setDetail(null);
        if (err instanceof HttpError) setDetailError(err.message);
        else setDetailError(err instanceof Error ? err.message : String(err));
        reportError(err, { kind: "match-detail-fetch", ledgerId: detailLedgerId });
      })
      .finally(() => {
        if (!cancelled) setDetailLoading(false);
      });
    return () => {
      cancelled = true;
      controller.abort();
    };
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
        <Suspense fallback={<LoadingSpinner label="加载比赛页面..." />}>
          <MatchDetailPage
            ledgerId={route.ledgerId}
            detail={detail}
            loading={detailLoading}
            error={detailError}
            onBack={navigateToDashboard}
          />
        </Suspense>
      ) : (
        <div className="flex max-w-screen-2xl mx-auto">
          {/* Sidebar (desktop) */}
          <Sidebar active={activeSection} onChange={setActiveSection} />

          {/* Main content */}
          <main className="flex-1 min-w-0 px-3 sm:px-4 py-3 pb-20 lg:pb-4">
            {error && (
              <div className="mb-3 rounded-lg border border-amber-200 dark:border-amber-700 bg-amber-50 dark:bg-amber-900/20 px-3 py-2 text-xs text-amber-800 dark:text-amber-200 flex items-center gap-2">
                <Icon name="warn" size={12} />
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

                <footer className="mt-6 text-[10px] text-slate-400 dark:text-slate-600 text-center py-3 border-t border-slate-100 dark:border-slate-800">
                  只读监控台 · 不执行交易动作
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
