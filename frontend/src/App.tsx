import {
  Activity,
  AlertTriangle,
  ArrowLeft,
  BarChart3,
  BrainCircuit,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  CloudSun,
  Clock,
  Database,
  Eye,
  Gauge,
  ListChecks,
  MapPin,
  RefreshCw,
  Rocket,
  ShieldCheck,
  TrendingUp,
  Target,
  UserRound,
  UsersRound
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { CSSProperties } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import {
  buildDashboardView,
  buildMatchDetailView,
  customerCopy,
  formatOdds,
  formatPercent,
  formatSignedPercent,
  marketLabel,
  reasonLabel,
  statusFlagLabel,
  strategyStatusLabel
} from "./dashboardModel";
import { dashboardPath, matchDetailPath, parseDashboardRoute, type DashboardRoute } from "./appRouting";
import type { DashboardMatchDetail, DashboardRecord, DashboardSectionKey, DashboardSnapshot, KpiCard, LearningEvent, PredictionLedgerRow, ProbabilityRow } from "./types";

const API_URL = "/api/dashboard";
type LedgerFilter = "all" | "recommendation" | "observation" | "settled" | "open" | "hit" | "miss";
type DashboardViewModel = ReturnType<typeof buildDashboardView>;
type BacktestChartPoint = DashboardViewModel["backtestCurve"]["points"][number];

function currentDashboardRoute(): DashboardRoute {
  return parseDashboardRoute(`${window.location.pathname}${window.location.search}`);
}

const LEDGER_FILTERS: Array<{ key: LedgerFilter; label: string }> = [
  { key: "all", label: "全部预测" },
  { key: "recommendation", label: "推荐发布" },
  { key: "observation", label: "观察样本" },
  { key: "settled", label: "已结算" },
  { key: "open", label: "未结算" },
  { key: "hit", label: "命中" },
  { key: "miss", label: "未命中" }
];

const SECTION_ICONS: Record<DashboardSectionKey, typeof Target> = {
  overview: Target,
  production: Rocket,
  model: Gauge,
  signals: TrendingUp,
  data: Database
};

const AUTO_STEP_LABELS: Record<string, string> = {
  asian_shortlist: "临场亚盘分析",
  jingcai_parlay: "竞彩组合扫描",
  market_snapshot_sync: "赔率快照补强",
  snapshot_reanalysis: "快照复算",
  settlement: "赛果结算",
  idle: "等待下一轮"
};

function toneClass(tone: KpiCard["tone"]): string {
  return `tone-${tone}`;
}

function localTime(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false
  }).format(date);
}

function fullLocalTime(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false
  }).format(date);
}

function objectRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function numericValue(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function boolValue(value: unknown): boolean {
  if (typeof value === "boolean") return value;
  if (typeof value === "string") return ["1", "true", "yes", "on"].includes(value.trim().toLowerCase());
  return false;
}

function isAfterTime(left: unknown, right: unknown): boolean {
  const leftDate = new Date(typeof left === "string" ? left : "");
  const rightDate = new Date(typeof right === "string" ? right : "");
  if (Number.isNaN(leftDate.getTime())) return false;
  if (Number.isNaN(rightDate.getTime())) return true;
  return leftDate.getTime() > rightDate.getTime();
}

function latestTime(rows: PredictionLedgerRow[], key: "created_at_utc" | "settled_at_utc"): string | null {
  let latest: string | null = null;
  let latestMs = Number.NEGATIVE_INFINITY;
  for (const row of rows) {
    const value = row[key];
    if (!value) continue;
    const ms = new Date(value).getTime();
    if (!Number.isNaN(ms) && ms > latestMs) {
      latest = value;
      latestMs = ms;
    }
  }
  return latest;
}

function displayMatchup(value: string | null | undefined): string {
  return (value || "—").replace(/\s+vs\s+/gi, " 对 ");
}

type TeamVisualRecord = {
  matchup?: string | null;
  home_team?: string | null;
  away_team?: string | null;
  home_team_logo_url?: string | null;
  away_team_logo_url?: string | null;
};

function splitMatchup(value: string | null | undefined): { home: string; away: string } {
  const [home, away] = (value || "").split(/\s+(?:vs|对)\s+/i).map((part) => part.trim());
  return { home: home || "主队", away: away || "客队" };
}

function teamInitials(teamName: string | null | undefined): string {
  const clean = (teamName || "").replace(/\s+/g, " ").trim();
  if (!clean) return "FC";
  const compact = clean.replace(/[^\p{L}\p{N}\u4e00-\u9fff]/gu, "");
  const chinese = compact.match(/[\u4e00-\u9fff]/gu);
  if (chinese?.length) return chinese.slice(0, 2).join("");
  const parts = clean.split(/[\s·._-]+/).filter(Boolean);
  const initials = parts.length > 1 ? `${parts[0][0] || ""}${parts[1][0] || ""}` : compact.slice(0, 2);
  return (initials || "FC").toUpperCase();
}

function teamAccent(teamName: string | null | undefined): string {
  const palette = ["#0f766e", "#2563eb", "#c2410c", "#7c3aed", "#be123c", "#047857", "#b45309", "#155e75"];
  const value = teamName || "";
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) % palette.length;
  }
  return palette[Math.abs(hash) % palette.length];
}

function TeamBadge({
  teamName,
  logoUrl,
  size = "small"
}: {
  teamName: string;
  logoUrl?: string | null;
  size?: "small" | "medium" | "large";
}) {
  const initials = teamInitials(teamName);
  return (
    <span
      className={`team-badge ${size}`}
      style={{ "--team-accent": teamAccent(teamName) } as CSSProperties}
      aria-label={`${teamName || "球队"} 队徽`}
      title={teamName || "球队"}
    >
      {logoUrl ? <img src={logoUrl} alt="" loading="lazy" referrerPolicy="no-referrer" /> : <span>{initials}</span>}
    </span>
  );
}

function TeamMatchup({
  record,
  meta,
  size = "small",
  compact = false
}: {
  record: TeamVisualRecord;
  meta?: string;
  size?: "small" | "medium" | "large";
  compact?: boolean;
}) {
  const parsed = splitMatchup(record.matchup);
  const homeTeam = record.home_team || parsed.home;
  const awayTeam = record.away_team || parsed.away;
  return (
    <div className={`team-matchup ${compact ? "compact-matchup" : ""}`}>
      <div className="team-line">
        <TeamBadge teamName={homeTeam} logoUrl={record.home_team_logo_url} size={size} />
        <strong>{homeTeam}</strong>
      </div>
      <div className="team-line">
        <TeamBadge teamName={awayTeam} logoUrl={record.away_team_logo_url} size={size} />
        <strong>{awayTeam}</strong>
      </div>
      {meta && <span>{meta}</span>}
    </div>
  );
}

function countdown(value: string): string {
  const date = new Date(value);
  const diff = date.getTime() - Date.now();
  if (Number.isNaN(diff)) return "—";
  if (diff <= 0) return "已开赛";
  const minutes = Math.round(diff / 60000);
  if (minutes < 60) return `${minutes} 分钟`;
  return `${Math.floor(minutes / 60)} 小时 ${minutes % 60} 分钟`;
}

function recordStatusText(status: string, hit?: number | null): string {
  if (status === "settled") return hit ? "命中" : "未命中";
  if (status === "open") return "赛果待确认";
  if (status === "tracked_only") return "仅跟踪";
  if (status === "unsupported_market") return "不支持结算";
  return status || "未知";
}

function oddsResolutionText(detail: DashboardMatchDetail | null): string {
  const resolution = detail?.odds_snapshot.resolution;
  if (!resolution || resolution.status !== "matched") return "暂无雷速快照";
  if (resolution.source_home_team || resolution.source_away_team) return "已匹配雷速别名";
  return "已匹配雷速";
}

function oddsResolutionSource(detail: DashboardMatchDetail | null): string {
  const resolution = detail?.odds_snapshot.resolution;
  if (!detail) return "正在读取本场持久化样本";
  if (!resolution || resolution.status !== "matched") return "暂无本场雷速赔率快照；已采集的赛事情报会继续展示";
  const sourceMatch = [resolution.source_home_team, resolution.source_away_team].filter(Boolean).join(" 对 ");
  const sourceLeague = resolution.source_league || resolution.league;
  const score = resolution.match_score == null ? "" : ` · 匹配分 ${formatOdds(resolution.match_score)}`;
  return [sourceLeague, sourceMatch || "雷速原始队名未记录"].filter(Boolean).join(" · ") + score;
}

function readableEventDetail(detail: string): string {
  const text = detail
    .replaceAll("asian_handicap_consensus_market_line_split", "亚盘公司盘口分歧")
    .replaceAll("over_under_consensus_total_line_split", "大小球公司盘口分歧")
    .replaceAll("near_kickoff_under_60m", "临近开赛 60 分钟内")
    .replaceAll("observed_not_recommended", "观察样本")
    .replaceAll("shortlist_value_matches", "推荐筛选")
    .replaceAll("balanced_observation", "均衡观察")
    .replaceAll("collecting_samples", "样本收集中")
    .replaceAll("live_calibration_active", "实时校准已启用")
    .replaceAll("asian_handicap", "亚盘")
    .replaceAll("over_under", "大小球")
    .replaceAll("moneyline_1x2", "胜平负")
    .replaceAll("h2h", "胜平负")
    .replaceAll("immediate_bet", "建议跟踪")
    .replaceAll("condition_observe", "条件观察")
    .replaceAll("paper_track", "观察跟踪")
    .replaceAll("no_value", "无正价值")
    .replaceAll("no_bet", "不建议")
    .replaceAll("balanced", "均衡模式")
    .replaceAll("observed", "已观察")
    .replaceAll("unknown", "未知")
    .replaceAll("samples=", "样本数 ")
    .replaceAll("minP=", "最低概率 ")
    .replaceAll("profit=", "收益 ")
    .replaceAll("no_positive_edge", "无正向边际")
    .replaceAll("multi_bookmaker_snapshot_missing", "缺少多公司赔率快照")
    .replaceAll("awaiting_reanalysis_after_snapshot", "赔率快照已补齐，等待下一轮复算")
    .replaceAll("core_market_missing", "核心盘口缺失")
    .replaceAll("calibrated_probability_below_threshold", "概率不足")
    .replaceAll("value_edge_below_threshold", "价值边际不足")
    .replaceAll("large_handicap_requires_backtest", "大盘口需回测")
    .replaceAll("edge_below_threshold", "边际不足")
    .replaceAll("value_edge_below_threshold", "价值边际不足");
  return customerCopy(text)
    .replace(/\s+vs\s+/gi, " 对 ")
    .replace(/样本=(\d+)/g, "样本数 $1")
    .replace(/最低概率=([0-9.]+)/g, "最低概率 $1")
    .replace(/收益=([+-]?[0-9.]+)/g, "收益 $1");
}

function DashboardSectionTabs({
  sections,
  active,
  onChange
}: {
  sections: DashboardViewModel["dashboardSections"];
  active: DashboardSectionKey;
  onChange: (section: DashboardSectionKey) => void;
}) {
  return (
    <nav className="section-tabs" aria-label="监控分区">
      {sections.map((section) => {
        const Icon = SECTION_ICONS[section.key];
        return (
          <button
            type="button"
            className={`section-tab ${active === section.key ? "active" : ""} tone-${section.tone}`}
            aria-pressed={active === section.key}
            key={section.key}
            onClick={() => onChange(section.key)}
          >
            <Icon size={17} />
            <span>{section.label}</span>
            <em>{section.description}</em>
            <b>{section.badge}</b>
          </button>
        );
      })}
    </nav>
  );
}

function DashboardHero({
  snapshot,
  view
}: {
  snapshot: DashboardSnapshot;
  view: DashboardViewModel;
}) {
  const accountability = view.predictionAccountability;
  const readiness = view.productionReadiness;
  const primaryPick = view.primaryPick;
  return (
    <section className={`dashboard-hero tone-${accountability.tone}`}>
      <div className="hero-copy">
        <span className="eyebrow">策略总览</span>
        <h2>{accountability.headline}</h2>
        <p>{accountability.detail}</p>
        <div className="hero-status-row">
          <span className={`status-pill ${accountability.tone === "good" ? "good" : accountability.tone === "bad" ? "bad" : accountability.tone === "caution" ? "caution" : "neutral"}`}>
            {accountability.policyText}
          </span>
          <span className={`status-pill ${readiness.tone === "good" ? "good" : readiness.tone === "bad" ? "bad" : readiness.tone === "caution" ? "caution" : "neutral"}`}>
            {readiness.actionText}
          </span>
          <span className="status-pill neutral">{view.strategyLabel}</span>
        </div>
      </div>
      <div className="hero-signal-board" aria-label="当前信号摘要">
        <div className="hero-signal-main">
          <span>当前推荐发布</span>
          <strong>{snapshot.kpis.asian_pick_count}</strong>
          <em>{primaryPick ? displayMatchup(primaryPick.matchup) : "暂无可发布推荐信号"}</em>
        </div>
        <div className="hero-signal-grid">
          <Metric label="观察样本" value={`${snapshot.kpis.observation_count}`} />
          <Metric label="未结算" value={`${snapshot.prediction_kpis.open_count}`} />
          <Metric label="赔率快照" value={`${snapshot.market_snapshot_summary.total_snapshot_count}`} />
          <Metric label="已回测" value={`${snapshot.prediction_kpis.settled_count}`} />
        </div>
      </div>
    </section>
  );
}

function KpiStrip({ cards }: { cards: KpiCard[] }) {
  return (
    <section className="kpi-strip" aria-label="系统指标">
      {cards.map((card) => (
        <div className={`kpi-card ${toneClass(card.tone)}`} key={card.label}>
          <span>{card.label}</span>
          <strong>{card.value}</strong>
        </div>
      ))}
    </section>
  );
}

function MatchPhaseStrip({ view }: { view: ReturnType<typeof buildDashboardView> }) {
  const iconMap = [Activity, Clock, CheckCircle2, AlertTriangle, ListChecks];
  return (
    <section className="phase-strip" aria-label="比赛阶段分布">
      {view.matchPhaseCards.map((card, index) => {
        const Icon = iconMap[index] ?? ListChecks;
        return (
          <div className={`phase-card tone-${card.tone}`} key={card.key}>
            <div>
              <Icon size={16} />
              <span>{card.label}</span>
            </div>
            <strong>{card.value}</strong>
            <em>{card.caption}</em>
            <i style={{ width: card.width }} />
          </div>
        );
      })}
    </section>
  );
}

function OperationStatusPanel({
  snapshot,
  view
}: {
  snapshot: DashboardSnapshot;
  view: DashboardViewModel;
}) {
  const auto = objectRecord(snapshot.auto_learning_state);
  const resultSummary = objectRecord(auto.last_result_summary);
  const enabled = boolValue(auto.enabled);
  const running = isAfterTime(auto.last_started_at_utc, auto.last_finished_at_utc);
  const runCount = numericValue(auto.run_count) ?? 0;
  const intervalSeconds = numericValue(auto.interval_seconds) ?? 120;
  const asianWindow = numericValue(auto.asian_window_minutes) ?? 10;
  const formalRecords = numericValue(resultSummary.asian_record_count) ?? 0;
  const observationRecords = numericValue(resultSummary.asian_learning_observation_record_count) ?? 0;
  const shadowRecords = numericValue(resultSummary.asian_shadow_prediction_record_count) ?? numericValue(resultSummary.saved_shadow_prediction_count) ?? 0;
  const savedRecords = formalRecords + observationRecords + shadowRecords;
  const candidateCount = numericValue(resultSummary.asian_total_candidates) ?? 0;
  const analyzedCount = numericValue(resultSummary.asian_analyzed_count) ?? 0;
  const rejectedCount = numericValue(resultSummary.asian_rejected_count) ?? 0;
  const rejectionReasons = objectRecord(resultSummary.asian_rejection_reasons);
  const topRejection = Object.entries(rejectionReasons)
    .map(([reason, count]) => ({ reason, count: numericValue(count) ?? 0 }))
    .sort((a, b) => b.count - a.count)[0];
  const snapshotSync = objectRecord(resultSummary.market_snapshot_sync);
  const snapshotStatus = typeof snapshotSync.status === "string" ? snapshotSync.status : "";
  const snapshotAccessible = numericValue(snapshotSync.accessible_match_count) ?? 0;
  const snapshotSaved = numericValue(snapshotSync.saved_snapshot_count) ?? 0;
  const snapshotProbed = numericValue(snapshotSync.probed_match_count) ?? 0;
  const settledRecords = (numericValue(resultSummary.settled_count) ?? 0) + (numericValue(resultSummary.shadow_settled_count) ?? 0);
  const latestSettledAt = latestTime(snapshot.prediction_ledger || [], "settled_at_utc");
  const openRows = (snapshot.prediction_ledger || []).filter((row) => row.settlement_status !== "settled").slice(0, 3);
  const phaseParts = [
    snapshot.prediction_kpis.scheduled_count ? `未开赛 ${snapshot.prediction_kpis.scheduled_count}` : "",
    snapshot.prediction_kpis.maybe_live_count ? `可能进行中 ${snapshot.prediction_kpis.maybe_live_count}` : "",
    snapshot.prediction_kpis.result_pending_count ? `赛果待确认 ${snapshot.prediction_kpis.result_pending_count}` : "",
    snapshot.prediction_kpis.final_pending_count ? `完场待结算 ${snapshot.prediction_kpis.final_pending_count}` : "",
    snapshot.prediction_kpis.postponed_count ? `延期/取消 ${snapshot.prediction_kpis.postponed_count}` : ""
  ].filter(Boolean);
  const hasError = Boolean(auto.last_error);
  const currentStep = typeof auto.current_step === "string" ? auto.current_step : "";
  const stepLabel = AUTO_STEP_LABELS[currentStep] || (currentStep ? currentStep : "等待下一轮");
  const statusText = !enabled ? "自动学习关闭" : hasError ? "自动学习异常" : running ? "正在扫描" : runCount > 0 ? "上一轮已完成" : "等待首轮";
  const statusTone: KpiCard["tone"] = hasError ? "bad" : running ? "caution" : enabled ? "good" : "bad";
  const headline = snapshot.prediction_kpis.recommended_count > 0
    ? "有推荐信号可发布"
    : enabled
      ? "系统正在观察，推荐发布仍关闭"
      : "自动学习未开启";
  const detail = enabled
    ? `后台按约 ${Math.max(1, Math.round(intervalSeconds / 60))} 分钟轮询。临场分析先写入观察/影子台账，雷速多公司快照作为后续补强，不再挡住基础分析。`
    : "自动学习关闭时不会扫描新比赛，也不会写入新的观察预测。";

  return (
    <section className={`ops-command-center tone-${statusTone}`} aria-label="当前运行状态">
      <div className="ops-hero">
        <div>
          <span className="eyebrow">现在系统在做什么</span>
          <h2>{headline}</h2>
          <p>{detail}</p>
        </div>
        <span className={`status-pill ${statusTone === "good" ? "good" : statusTone === "bad" ? "bad" : "caution"}`}>
          {statusText}
        </span>
      </div>

      <div className="ops-answer-grid">
        <div className="ops-answer">
          <span>有没有在预测？</span>
          <strong>{enabled ? `有，${running ? stepLabel : "按轮扫描候选"}` : "没有，自动学习关闭"}</strong>
          <p>{running ? "当前轮次还在执行，但临场分析已排在慢速快照同步之前。" : `上一轮结束：${fullLocalTime(typeof auto.last_finished_at_utc === "string" ? auto.last_finished_at_utc : null)}`}</p>
        </div>
        <div className="ops-answer">
          <span>为什么没推荐？</span>
          <strong>{snapshot.prediction_kpis.recommended_count > 0 ? "已有可发布信号" : "发布闸门未打开"}</strong>
          <p>{view.recommendationOpportunity.releaseGate?.detail || view.predictionAccountability.policyText}</p>
        </div>
        <div className="ops-answer">
          <span>上一轮分析了吗？</span>
          <strong>{analyzedCount} 场分析 · 新增 {savedRecords} 条</strong>
          <p>{analyzedCount > 0 ? `发布 ${formalRecords} 条，观察 ${observationRecords} 条，影子 ${shadowRecords} 条；${topRejection ? `主要阻断：${reasonLabel(topRejection.reason)} ${topRejection.count} 场。` : "没有候选阻断。"}` : "没有候选进入当前赛前窗口，或赛程源暂未给出可扫描比赛。"}</p>
        </div>
        <div className="ops-answer">
          <span>数据源阻塞？</span>
          <strong>{snapshotStatus === "partial" || snapshotStatus === "error" ? "快照补强受阻" : snapshotSaved > 0 ? "快照可用" : "暂无新增快照"}</strong>
          <p>{snapshotProbed > 0 ? `雷速快照探测 ${snapshotProbed} 场，可访问 ${snapshotAccessible} 场，保存 ${snapshotSaved} 条；基础赔率不足时不会生成方向。` : "多公司快照没有开始或本轮未探测，基础分析仍可使用已有盘口。"}</p>
        </div>
      </div>

      <div className="ops-metric-grid">
        <Metric label="候选/分析" value={`${candidateCount}/${analyzedCount} 场`} />
        <Metric label="发布/观察/影子" value={`${formalRecords}/${observationRecords}/${shadowRecords}`} />
        <Metric label="上一轮结算" value={`${settledRecords} 条`} />
        <Metric label="最新结算" value={localTime(latestSettledAt)} />
        <Metric label="未结算拆分" value={phaseParts.join(" / ") || "0"} />
      </div>

      <div className="ops-open-list" aria-label="未结算样本">
        <div className="ops-open-head">
          <ListChecks size={16} />
          <strong>当前未结算</strong>
          <span>{snapshot.prediction_kpis.open_count} 场</span>
        </div>
        {openRows.length ? openRows.map((row) => (
          <div className="ops-open-row" key={row.ledger_id}>
            <TeamMatchup record={row} meta={row.league} compact />
            <span>{localTime(row.kickoff_utc_plus_8)}</span>
            <b>{row.status_label || "未结算"}</b>
          </div>
        )) : (
          <div className="empty-state compact">当前没有未结算样本。</div>
        )}
      </div>
    </section>
  );
}

const PRODUCT_TERMS = [
  {
    term: "预测样本",
    plain: "模型已经算过方向并写入台账，哪怕不发布，也会等赛果回测。"
  },
  {
    term: "推荐发布",
    plain: "通过概率、价值边际、赔率范围和风控闸门后，才展示给使用者的信号。"
  },
  {
    term: "价值边际",
    plain: "模型判断的概率优势扣掉市场隐含概率后的空间，负数通常不值得发布。"
  },
  {
    term: "Brier",
    plain: "概率预测误差，越低越好，用来判断学习后概率是否更准。"
  },
  {
    term: "rho",
    plain: "历史强弱或盘口方向的相关证据；为 0 多半表示模型引擎证据还没入库。"
  },
  {
    term: "CLV",
    plain: "预测赔率和收盘赔率的差，用来判断是否早于市场发现价值。"
  }
];

function MetricGlossaryPanel() {
  return (
    <section className="panel metric-glossary" aria-label="名词速查">
      <div className="panel-title">
        <CircleHelp size={18} />
        <h2>名词速查</h2>
      </div>
      <div className="term-list">
        {PRODUCT_TERMS.map((item) => (
          <div className="term-row" key={item.term}>
            <strong>{item.term}</strong>
            <span>{item.plain}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

function PredictionAccountabilityPanel({ view }: { view: ReturnType<typeof buildDashboardView> }) {
  const accountability = view.predictionAccountability;
  const metricIcons = [Target, ShieldCheck, Eye, Clock];
  return (
    <section className={`panel prediction-accountability ${toneClass(accountability.tone)}`} aria-label="预测闭环说明">
      <div className="prediction-accountability-head">
        <div className="panel-title">
          <Target size={18} />
          <h2>{accountability.headline}</h2>
          <span className={`status-pill ${accountability.tone === "good" ? "good" : accountability.tone === "bad" ? "bad" : accountability.tone === "caution" ? "caution" : "neutral"}`}>
            {accountability.policyText}
          </span>
        </div>
        <strong>{accountability.title}</strong>
        <p>{accountability.detail}</p>
      </div>
      <div className="accountability-metrics">
        {accountability.metrics.map((metric, index) => {
          const Icon = metricIcons[index] ?? ListChecks;
          return (
            <div className={`accountability-metric ${toneClass(metric.tone)}`} key={metric.label}>
              <Icon size={16} />
              <span>{metric.label}</span>
              <strong>{metric.value}</strong>
              <em>{metric.caption}</em>
            </div>
          );
        })}
      </div>
      <div className="accountability-checks">
        {accountability.checkRows.map((check) => (
          <div className={`accountability-check ${toneClass(check.tone)}`} key={check.key}>
            <div>
              <span>{check.label}</span>
              <strong>{check.title}</strong>
              <em>{check.detail}</em>
            </div>
            <b>{check.statusText}</b>
            <i>
              <span style={{ width: check.width }} />
            </i>
            <small>{check.progressText}</small>
          </div>
        ))}
      </div>
    </section>
  );
}

function AuditPanel({ view }: { view: ReturnType<typeof buildDashboardView> }) {
  const iconMap = [Target, TrendingUp, BrainCircuit, CheckCircle2, Database];
  return (
    <section className="audit-panel" aria-label="预测评估总览">
      <div className="audit-main">
        <div className="panel-title">
          <BarChart3 size={18} />
          <h2>预测评估</h2>
          <span className="status-pill neutral">推荐和预测分层</span>
        </div>
        <div className="audit-health-grid">
          {view.healthCards.map((card, index) => {
            const Icon = iconMap[index] ?? ListChecks;
            return (
              <div className={`audit-card tone-${card.tone}`} key={card.key}>
                <div className="audit-card-head">
                  <Icon size={16} />
                  <span>{card.label}</span>
                  <strong>{card.metricText}</strong>
                </div>
                <b>{card.title}</b>
                <p>{card.detail}</p>
                {card.progressValue !== null && (
                  <div className="audit-progress" aria-label={`${card.label}进度 ${card.progressText}`}>
                    <i style={{ width: `${Math.max(4, card.progressValue * 100)}%` }} />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
      <div className="audit-side">
        <div className="panel-title compact-title">
          <AlertTriangle size={18} />
          <h2>无推荐原因</h2>
        </div>
        <div className="funnel-list">
          {view.recommendationFunnel.length ? view.recommendationFunnel.map((item) => (
            <div className="funnel-row" key={item.reason}>
              <div>
                <span>{item.label}</span>
                <strong>{item.countText}</strong>
              </div>
              <div className="funnel-track">
                <i style={{ width: item.width }} />
              </div>
            </div>
          )) : <div className="empty-state compact">暂无过滤原因。</div>}
        </div>
      </div>
    </section>
  );
}

function LearningDiagnosticsPanel({ view }: { view: ReturnType<typeof buildDashboardView> }) {
  const diagnostics = view.learningDiagnostics;
  const iconMap = [Target, CheckCircle2, Clock, Database, RefreshCw];
  return (
    <section className={`panel learning-diagnostics tone-${diagnostics.tone}`} aria-label="学习闭环诊断">
      <div className="learning-diagnostics-head">
        <div className="panel-title">
          <BrainCircuit size={18} />
          <h2>学习闭环诊断</h2>
          <span className={`status-pill ${diagnostics.tone === "good" ? "good" : diagnostics.tone === "caution" ? "caution" : "neutral"}`}>
            {diagnostics.title}
          </span>
        </div>
        <p>{diagnostics.detail}</p>
      </div>
      <div className="diagnostic-metrics">
        {diagnostics.metrics.map((metric, index) => {
          const Icon = iconMap[index] ?? ListChecks;
          return (
            <div className={`diagnostic-metric tone-${metric.tone}`} key={metric.label}>
              <Icon size={16} />
              <span>{metric.label}</span>
              <strong>{metric.value}</strong>
              <em>{metric.caption}</em>
            </div>
          );
        })}
      </div>
      <div className="diagnostic-body">
        <div className="readiness-list">
          {diagnostics.readinessItems.map((item) => (
            <div className={`readiness-row tone-${item.tone}`} key={item.key}>
              <div>
                <strong>{item.label}</strong>
                <span>{item.title}</span>
                <p>{item.detail}</p>
              </div>
              <b>{item.progressText}</b>
              {item.progressValue !== null && (
                <div className="audit-progress" aria-label={`${item.label}进度 ${item.progressText}`}>
                  <i style={{ width: `${Math.max(4, item.progressValue * 100)}%` }} />
                </div>
              )}
            </div>
          ))}
        </div>
        <div className="diagnostic-blockers">
          <div className="panel-title compact-title">
            <AlertTriangle size={18} />
            <h2>主要阻断</h2>
          </div>
          <div className="funnel-list">
            {diagnostics.blockerRows.length ? diagnostics.blockerRows.map((item) => (
              <div className="funnel-row" key={item.reason}>
                <div>
                  <span>{item.label}</span>
                  <strong>{item.countText}</strong>
                </div>
                <div className="funnel-track">
                  <i style={{ width: item.width }} />
                </div>
              </div>
            )) : <div className="empty-state compact">暂无阻断原因。</div>}
          </div>
        </div>
      </div>
    </section>
  );
}

function DashboardContractPanel({ view }: { view: ReturnType<typeof buildDashboardView> }) {
  const contract = view.dashboardContract;
  const iconMap = [Target, Eye, AlertTriangle, ShieldCheck];
  return (
    <section className={`panel dashboard-contract tone-${contract.tone}`} aria-label="前后端数据契约">
      <div className="learning-diagnostics-head">
        <div className="panel-title">
          <ShieldCheck size={18} />
          <h2>数据契约</h2>
          <span className={`status-pill ${contract.tone === "good" ? "good" : contract.tone === "caution" ? "caution" : contract.tone === "bad" ? "bad" : "neutral"}`}>
            {contract.title}
          </span>
        </div>
        <p>{contract.detail}</p>
        <div className="contract-policy-line">
          <BrainCircuit size={15} />
          <span>{contract.policyText}</span>
        </div>
      </div>
      <div className="diagnostic-metrics contract-metrics">
        {contract.metricRows.map((metric, index) => {
          const Icon = iconMap[index] ?? ListChecks;
          return (
            <div className={`diagnostic-metric tone-${metric.tone}`} key={metric.label}>
              <Icon size={16} />
              <span>{metric.label}</span>
              <strong>{metric.value}</strong>
              <em>{metric.caption}</em>
            </div>
          );
        })}
      </div>
      <div className="contract-section-list">
        {contract.sectionRows.length ? contract.sectionRows.map((section) => (
          <div className={`contract-section-row tone-${section.tone}`} key={`${section.label}-${section.title}`}>
            <div>
              <span>{section.label}</span>
              <strong>{section.title}</strong>
              <em>{section.detail}</em>
            </div>
            <b>{section.statusText}</b>
            <i>
              <span style={{ width: section.width }} />
            </i>
            <small>{section.progressText}</small>
          </div>
        )) : <div className="empty-state compact">暂无数据契约状态。</div>}
      </div>
    </section>
  );
}

function ProductionReadinessPanel({ view }: { view: ReturnType<typeof buildDashboardView> }) {
  const readiness = view.productionReadiness;
  const iconMap = [ShieldCheck, Rocket, ListChecks, TrendingUp];
  return (
    <section className={`panel production-readiness tone-${readiness.tone}`} aria-label="上线状态审计">
      <div className="learning-diagnostics-head">
        <div className="panel-title">
          <Rocket size={18} />
          <h2>上线状态</h2>
          <span className={`status-pill ${readiness.tone === "good" ? "good" : readiness.tone === "caution" ? "caution" : readiness.tone === "bad" ? "bad" : "neutral"}`}>
            {readiness.actionText}
          </span>
        </div>
        <p>{readiness.detail}</p>
      </div>
      <div className="diagnostic-metrics production-metrics">
        {readiness.metrics.map((metric, index) => {
          const Icon = iconMap[index] ?? ShieldCheck;
          return (
            <div className={`diagnostic-metric tone-${metric.tone}`} key={metric.label}>
              <Icon size={16} />
              <span>{metric.label}</span>
              <strong>{metric.value}</strong>
              <em>{metric.caption}</em>
            </div>
          );
        })}
      </div>
      <div className="readiness-gate-list">
        {readiness.gateRows.map((gate) => (
          <div className={`readiness-gate-row tone-${gate.tone}`} key={gate.key}>
            <div>
              <span>{gate.label}</span>
              <strong>{gate.title}</strong>
              <em>{gate.detail}</em>
            </div>
            <b>{gate.statusText}</b>
            <i>
              <span style={{ width: gate.width }} />
            </i>
            <small>{gate.progressText}</small>
          </div>
        ))}
      </div>
    </section>
  );
}

function ProductionCommandCenterPanel({ view }: { view: DashboardViewModel }) {
  const ops = view.productionOps;
  const cardIcons = [Activity, Clock, RefreshCw, ShieldCheck];
  return (
    <section className={`panel production-command tone-${ops.tone}`} aria-label="生产就绪中心">
      <div className="production-command-head">
        <div>
          <span className="eyebrow">生产就绪中心</span>
          <h2>{ops.headline}</h2>
          <p>{ops.detail}</p>
        </div>
        <span className={`status-pill ${ops.tone === "good" ? "good" : ops.tone === "bad" ? "bad" : ops.tone === "caution" ? "caution" : "neutral"}`}>
          {ops.releaseText}
        </span>
      </div>
      <div className="production-status-grid">
        {ops.statusCards.map((card, index) => {
          const Icon = cardIcons[index] ?? Activity;
          return (
            <div className={`diagnostic-metric tone-${card.tone}`} key={card.label}>
              <Icon size={16} />
              <span>{card.label}</span>
              <strong>{card.value}</strong>
              <em>{card.caption}</em>
            </div>
          );
        })}
      </div>
      <div className="production-blocker-list">
        {ops.blockerRows.length ? ops.blockerRows.map((row) => (
          <div className={`readiness-gate-row tone-${row.tone}`} key={row.key}>
            <div>
              <span>{row.label}</span>
              <strong>{row.title}</strong>
              <em>{row.detail}</em>
            </div>
            <b>{row.statusText}</b>
            <i>
              <span style={{ width: row.width }} />
            </i>
            <small>{row.progressText}</small>
          </div>
        )) : <div className="empty-state compact">暂无阻断项，推荐发布可进入候选确认。</div>}
      </div>
    </section>
  );
}

function AutoLearningWorkflowPanel({ view }: { view: DashboardViewModel }) {
  return (
    <section className="panel auto-workflow-panel" aria-label="自动学习流水">
      <div className="panel-title">
        <ListChecks size={18} />
        <h2>自动学习流水</h2>
        <span className="status-pill neutral">赛前 10 分钟</span>
      </div>
      <div className="workflow-grid">
        {view.productionOps.workflowRows.map((row) => (
          <div className={`workflow-row tone-${row.tone}`} key={row.key}>
            <span className="workflow-dot" />
            <div>
              <strong>{row.label}</strong>
              <p>{row.detail}</p>
            </div>
            <b>{row.statusText}</b>
            <em>{row.metaText}</em>
          </div>
        ))}
      </div>
    </section>
  );
}

function LearningEffectivenessPanel({ view }: { view: ReturnType<typeof buildDashboardView> }) {
  const effectiveness = view.learningEffectiveness;
  const iconMap = [BarChart3, Gauge, Database, TrendingUp];
  return (
    <section className={`panel learning-effectiveness tone-${effectiveness.tone}`} aria-label="模型质量">
      <div className="learning-diagnostics-head">
        <div className="panel-title">
          <Gauge size={18} />
          <h2>模型质量</h2>
          <span className={`status-pill ${effectiveness.tone === "good" ? "good" : effectiveness.tone === "caution" ? "caution" : effectiveness.tone === "bad" ? "bad" : "neutral"}`}>
            {effectiveness.title}
          </span>
        </div>
        <p>{effectiveness.detail}</p>
      </div>
      <div className="diagnostic-metrics">
        {effectiveness.metrics.map((metric, index) => {
          const Icon = iconMap[index] ?? ListChecks;
          return (
            <div className={`diagnostic-metric tone-${metric.tone}`} key={metric.label}>
              <Icon size={16} />
              <span>{metric.label}</span>
              <strong>{metric.value}</strong>
              <em>{metric.caption}</em>
            </div>
          );
        })}
      </div>
      <div className="quality-summary">
        {effectiveness.summaryRows.map((row) => (
          <div className="quality-summary-row" key={row.label}>
            <span>{row.label}</span>
            <strong>{row.value}</strong>
          </div>
        ))}
        <p>{effectiveness.metricRule}</p>
      </div>
      <div className={`model-verdict ${toneClass(effectiveness.deploymentVerdict.tone)}`}>
        <div className="model-verdict-head">
          <ShieldCheck size={16} />
          <span>上线结论</span>
          <strong>{effectiveness.deploymentVerdict.title}</strong>
          <em>{effectiveness.deploymentVerdict.statusText}</em>
        </div>
        <p>{effectiveness.deploymentVerdict.detail}</p>
        <div className="model-verdict-metrics">
          <span>{effectiveness.deploymentVerdict.actionText}</span>
          <span>样本 {effectiveness.deploymentVerdict.sampleText}</span>
          <span>收益 {effectiveness.deploymentVerdict.roiText}</span>
          <span>{effectiveness.deploymentVerdict.reasonsText}</span>
        </div>
      </div>
      {effectiveness.probabilityGovernance && (
        <div className={`probability-governance tone-${effectiveness.probabilityGovernance.tone}`}>
          <div className="probability-governance-head">
            <Gauge size={16} />
            <span>概率治理</span>
            <strong>{effectiveness.probabilityGovernance.title}</strong>
            <em>{effectiveness.probabilityGovernance.policyText}</em>
          </div>
          <p>{effectiveness.probabilityGovernance.detail}</p>
          <div className="probability-governance-meta">
            <span>{effectiveness.probabilityGovernance.activeText}</span>
            <span>{effectiveness.probabilityGovernance.thresholdText}</span>
            <span>{effectiveness.probabilityGovernance.guardrailsText}</span>
          </div>
          {effectiveness.probabilityGovernance.candidateRows.length > 0 && (
            <div className="probability-governance-candidates">
              {effectiveness.probabilityGovernance.candidateRows.map((row) => {
                const [label, brier, calibration, status] = row.split(":");
                return (
                  <div key={row}>
                    <span>{label}</span>
                    <b>{brier}</b>
                    <em>{calibration}</em>
                    <strong>{status}</strong>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
      {effectiveness.calibrationHealth && (
        <div className={`calibration-health tone-${effectiveness.calibrationHealth.tone}`}>
          <div className="calibration-health-head">
            <Activity size={16} />
            <span>校准健康</span>
            <strong>{effectiveness.calibrationHealth.title}</strong>
            <em>{effectiveness.calibrationHealth.actionText}</em>
          </div>
          <p>{effectiveness.calibrationHealth.detail}</p>
          <div className="calibration-health-meta">
            <span>{effectiveness.calibrationHealth.modelText}</span>
            <span>{effectiveness.calibrationHealth.candidateBandsText}</span>
          </div>
        </div>
      )}
      {effectiveness.shadowRecalibration && (
        <div className={`shadow-recalibration tone-${effectiveness.shadowRecalibration.tone}`}>
          <div className="shadow-recalibration-head">
            <BrainCircuit size={16} />
            <span>影子模型</span>
            <strong>{effectiveness.shadowRecalibration.title}</strong>
            <em>{effectiveness.shadowRecalibration.methodText}</em>
          </div>
          <p>{effectiveness.shadowRecalibration.detail}</p>
          <div className="shadow-recalibration-grid">
            <span>重校准 Brier <b>{effectiveness.shadowRecalibration.brierText}</b></span>
            <span>误差变化 <b>{effectiveness.shadowRecalibration.brierDeltaText}</b></span>
            <span>{effectiveness.shadowRecalibration.walkForwardText}</span>
            <span>{effectiveness.shadowRecalibration.validationText}</span>
            <span>{effectiveness.shadowRecalibration.selectedBandsText}</span>
          </div>
        </div>
      )}
      {effectiveness.bandRows.length > 0 && (
        <div className="probability-band-list" aria-label="学习概率分桶回测">
          <div className="probability-band-head">
            <BarChart3 size={16} />
            <strong>概率分桶回测</strong>
            <span>对比学习概率、实际命中率和收益率</span>
          </div>
          {effectiveness.bandRows.map((band) => (
            <div className={`probability-band-row tone-${band.tone}`} key={band.key}>
              <div className="probability-band-label">
                <strong>{band.label}</strong>
                <span>{band.sampleText} · {band.qualityText}</span>
              </div>
              <div className="probability-band-bars" aria-label={`${band.label} 命中率 ${band.hitRateText} 学习概率 ${band.avgProbabilityText}`}>
                <span>
                  <i className="hit-bar" style={{ width: band.hitWidth }} />
                </span>
                <span>
                  <i className="probability-bar" style={{ width: band.probabilityWidth }} />
                </span>
              </div>
              <div className="probability-band-values">
                <span>命中 {band.hitRateText}</span>
                <span>概率 {band.avgProbabilityText}</span>
                <strong>{band.roiText}</strong>
                <em>校准差 {band.calibrationText}</em>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function ModelGovernancePanel({ view }: { view: ReturnType<typeof buildDashboardView> }) {
  const governance = view.modelGovernance;
  const iconMap = [BrainCircuit, Gauge, ListChecks, TrendingUp];
  return (
    <section className={`panel model-governance tone-${governance.tone}`} aria-label="专业模型审计">
      <div className="learning-diagnostics-head">
        <div className="panel-title">
          <BrainCircuit size={18} />
          <h2>专业模型审计</h2>
          <span className={`status-pill ${governance.tone === "good" ? "good" : governance.tone === "caution" ? "caution" : governance.tone === "bad" ? "bad" : "neutral"}`}>
            {governance.title}
          </span>
        </div>
        <p>{governance.detail}</p>
      </div>
      <div className="model-method-line">
        <span>{governance.methodText}</span>
        <em>{governance.ruleText}</em>
      </div>
      <div className="diagnostic-metrics model-governance-metrics">
        {governance.metrics.map((metric, index) => {
          const Icon = iconMap[index] ?? ListChecks;
          return (
            <div className={`diagnostic-metric tone-${metric.tone}`} key={metric.label}>
              <Icon size={16} />
              <span>{metric.label}</span>
              <strong>{metric.value}</strong>
              <em>{metric.caption}</em>
            </div>
          );
        })}
      </div>
      <div className="readiness-gate-list model-governance-list">
        {governance.checkRows.map((check) => (
          <div className={`readiness-gate-row tone-${check.tone}`} key={check.key}>
            <div>
              <span>{check.label}</span>
              <strong>{check.title}</strong>
              <em>{check.detail}</em>
            </div>
            <b>{check.statusText}</b>
            <i>
              <span style={{ width: check.width }} />
            </i>
            <small>{check.progressText}</small>
          </div>
        ))}
      </div>
    </section>
  );
}

function AdaptiveLearningPlanPanel({ view }: { view: ReturnType<typeof buildDashboardView> }) {
  const plan = view.adaptiveLearningPlan;
  const metricIcons = [ListChecks, AlertTriangle, Database, BrainCircuit];
  return (
    <section className={`panel adaptive-learning-plan tone-${plan.tone}`} aria-label="自学习修正计划">
      <div className="learning-diagnostics-head">
        <div className="panel-title">
          <BrainCircuit size={18} />
          <h2>自学习修正</h2>
          <span className={`status-pill ${plan.tone === "good" ? "good" : plan.tone === "caution" ? "caution" : plan.tone === "bad" ? "bad" : "neutral"}`}>
            {plan.title}
          </span>
        </div>
        <p>{plan.detail}</p>
      </div>
      <div className="diagnostic-metrics adaptive-metrics">
        {plan.metrics.map((metric, index) => {
          const Icon = metricIcons[index] ?? ListChecks;
          return (
            <div className={`diagnostic-metric tone-${metric.tone}`} key={metric.label}>
              <Icon size={16} />
              <span>{metric.label}</span>
              <strong>{metric.value}</strong>
              <em>{metric.caption}</em>
            </div>
          );
        })}
      </div>
      <div className="adaptive-action-list">
        {plan.actionRows.length ? plan.actionRows.map((action) => (
          <div className={`adaptive-action-row tone-${action.tone}`} key={action.key}>
            <div>
              <span>{action.label}</span>
              <strong>{action.title}</strong>
              <em>{action.detail}</em>
            </div>
            <b>{action.statusText}</b>
            <p>{action.evidence}</p>
            <small>{action.policyEffect}</small>
            <i>
              <span style={{ width: action.width }} />
            </i>
            <time>{action.progressText}</time>
          </div>
        )) : (
          <div className="empty-state compact">暂无自动修正动作，继续收集预测和结算样本。</div>
        )}
      </div>
    </section>
  );
}

function ClvTrackingPanel({ view }: { view: ReturnType<typeof buildDashboardView> }) {
  const clv = view.clvTracking;
  const iconMap = [Target, CheckCircle2, TrendingUp, AlertTriangle];
  return (
    <section className={`panel clv-tracking tone-${clv.tone}`} aria-label="CLV 收盘价追踪">
      <div className="learning-diagnostics-head">
        <div className="panel-title">
          <TrendingUp size={18} />
          <h2>CLV 追踪</h2>
          <span className={`status-pill ${clv.tone === "good" ? "good" : clv.tone === "caution" ? "caution" : clv.tone === "bad" ? "bad" : "neutral"}`}>
            {clv.title}
          </span>
        </div>
        <p>{clv.detail}</p>
      </div>
      <div className="diagnostic-metrics clv-metrics">
        {clv.metrics.map((metric, index) => {
          const Icon = iconMap[index] ?? ListChecks;
          return (
            <div className={`diagnostic-metric tone-${metric.tone}`} key={metric.label}>
              <Icon size={16} />
              <span>{metric.label}</span>
              <strong>{metric.value}</strong>
              <em>{metric.caption}</em>
            </div>
          );
        })}
      </div>
      <div className="clv-record-list">
        {clv.recordRows.length ? clv.recordRows.map((row) => (
          <div className={`clv-record-row tone-${row.tone}`} key={row.id}>
            <div>
              <strong>{row.matchup}</strong>
              <span>{row.marketText} · {row.selectionText}</span>
            </div>
            <b>{row.priceText}</b>
            <em>{row.clvText}</em>
            <time>{row.timeText.includes("T") ? localTime(row.timeText) : row.timeText}</time>
          </div>
        )) : (
          <div className="empty-state compact">{clv.ruleText}</div>
        )}
      </div>
    </section>
  );
}

function formatUnitAxis(value: number): string {
  if (!Number.isFinite(value)) return "0";
  return value > 0 ? `+${value.toFixed(1)}` : value.toFixed(1);
}

function BacktestTooltip({
  active,
  payload
}: {
  active?: boolean;
  payload?: Array<{ payload: BacktestChartPoint }>;
}) {
  const point = payload?.[0]?.payload;
  if (!active || !point) return null;
  return (
    <div className="chart-tooltip">
      <strong>{point.matchup}</strong>
      <span>{point.typeText} · {point.resultText}</span>
      <b>累计 {point.cumulativeText}</b>
      <em>本场 {point.profitText} · 滚动命中 {point.rollingHitText}</em>
    </div>
  );
}

function BacktestCurvePanel({ view }: { view: ReturnType<typeof buildDashboardView> }) {
  const curve = view.backtestCurve;
  const iconMap = [TrendingUp, AlertTriangle, Target, Activity];
  return (
    <section className={`panel backtest-curve tone-${curve.tone}`} aria-label="回测走势">
      <div className="learning-diagnostics-head">
        <div className="panel-title">
          <Activity size={18} />
          <h2>回测走势</h2>
          <span className={`status-pill ${curve.tone === "good" ? "good" : curve.tone === "caution" ? "caution" : "neutral"}`}>
            {curve.title}
          </span>
        </div>
        <p>{curve.detail}</p>
      </div>
      <div className="diagnostic-metrics backtest-metrics">
        {curve.metrics.map((metric, index) => {
          const Icon = iconMap[index] ?? ListChecks;
          return (
            <div className={`diagnostic-metric tone-${metric.tone}`} key={metric.label}>
              <Icon size={16} />
              <span>{metric.label}</span>
              <strong>{metric.value}</strong>
              <em>{metric.caption}</em>
            </div>
          );
        })}
      </div>
      {curve.points.length ? (
        <div className="backtest-chart-wrap">
          <div className="backtest-chart" role="img" aria-label="累计收益曲线">
            <ResponsiveContainer width="100%" height={260} minWidth={0}>
              <LineChart data={curve.points} margin={{ top: 12, right: 18, bottom: 8, left: 2 }}>
                <CartesianGrid stroke="#e4ebf2" strokeDasharray="4 4" vertical={false} />
                <XAxis
                  dataKey="index"
                  tickLine={false}
                  axisLine={false}
                  tickMargin={8}
                  tick={{ fill: "#667085", fontSize: 12, fontWeight: 700 }}
                />
                <YAxis
                  width={48}
                  tickLine={false}
                  axisLine={false}
                  tickFormatter={formatUnitAxis}
                  tick={{ fill: "#667085", fontSize: 12, fontWeight: 700 }}
                />
                <ReferenceLine y={0} stroke="#9aa8b6" strokeDasharray="5 5" />
                <Tooltip content={<BacktestTooltip />} cursor={{ stroke: "#91a7bd", strokeDasharray: "4 4" }} />
                <Line
                  type="monotone"
                  dataKey="cumulativeValue"
                  name="累计收益"
                  stroke="#0f766e"
                  strokeWidth={3}
                  dot={{ r: 3.5, strokeWidth: 2, fill: "#ffffff", stroke: "#0f766e" }}
                  activeDot={{ r: 5, strokeWidth: 2, fill: "#0f766e", stroke: "#ffffff" }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div className="backtest-point-list">
            {curve.points.slice(-5).map((point) => (
              <div className={`backtest-point-row tone-${point.tone}`} key={`${point.index}-${point.matchup}`}>
                <span>{point.index}</span>
                <strong>{point.matchup}</strong>
                <em>{point.resultText} · {point.profitText}</em>
                <b>{point.cumulativeText}</b>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="empty-state compact">暂无已结算样本，等待赛果后生成走势。</div>
      )}
    </section>
  );
}

function PredictionQualityPanel({ view }: { view: ReturnType<typeof buildDashboardView> }) {
  const quality = view.predictionQuality;
  const iconMap = [Target, CheckCircle2, ListChecks, AlertTriangle];
  return (
    <section className={`panel prediction-quality tone-${quality.tone}`} aria-label="观察样本质量">
      <div className="learning-diagnostics-head">
        <div className="panel-title">
          <BarChart3 size={18} />
          <h2>观察样本质量</h2>
          <span className={`status-pill ${quality.tone === "good" ? "good" : quality.tone === "caution" ? "caution" : quality.tone === "bad" ? "bad" : "neutral"}`}>
            {quality.title}
          </span>
        </div>
        <p>{quality.detail}</p>
      </div>
      <div className="diagnostic-metrics prediction-quality-metrics">
        {quality.metricRows.map((metric, index) => {
          const Icon = iconMap[index] ?? ListChecks;
          return (
            <div className={`diagnostic-metric tone-${metric.tone}`} key={metric.label}>
              <Icon size={16} />
              <span>{metric.label}</span>
              <strong>{metric.value}</strong>
              <em>{metric.caption}</em>
            </div>
          );
        })}
      </div>
      <div className="prediction-quality-list">
        {quality.segmentRows.length ? quality.segmentRows.map((segment) => (
          <div className={`prediction-quality-row tone-${segment.tone}`} key={segment.label}>
            <div className="prediction-quality-main">
              <strong>{segment.label}</strong>
              <span>{segment.totalText} · {segment.settledText} · {segment.qualityText}</span>
              <i><b style={{ width: segment.width }} /></i>
            </div>
            <div className="prediction-quality-values">
              <span>命中 {segment.hitRateText}</span>
              <span>收益 {segment.roiText}</span>
              <span>概率 {segment.avgProbabilityText}</span>
              <span>边际 {segment.avgEdgeText}</span>
              <span>{segment.adjustmentLabel}</span>
              <span>{segment.weightText}</span>
              <em>赔率覆盖 {segment.oddsCoverageText}</em>
            </div>
            <p>{segment.adjustmentDetail}</p>
          </div>
        )) : <div className="empty-state compact">暂无可展示的分组回测。</div>}
      </div>
    </section>
  );
}

function RecommendationOpportunityPanel({
  view,
  onSelect
}: {
  view: ReturnType<typeof buildDashboardView>;
  onSelect: (ledgerId: string) => void;
}) {
  const opportunity = view.recommendationOpportunity;
  const iconMap = [ShieldCheck, Eye, CheckCircle2, RefreshCw];
  return (
    <section className={`panel recommendation-opportunity tone-${opportunity.tone}`} aria-label="推荐机会审计">
      <div className="learning-diagnostics-head">
        <div className="panel-title">
          <Target size={18} />
          <h2>推荐机会审计</h2>
          <span className={`status-pill ${opportunity.tone === "good" ? "good" : opportunity.tone === "caution" ? "caution" : opportunity.tone === "bad" ? "bad" : "neutral"}`}>
            {opportunity.title}
          </span>
        </div>
        <p>{opportunity.detail}</p>
      </div>
      <div className="opportunity-threshold">
        <Gauge size={16} />
        <span>{opportunity.thresholdText}</span>
      </div>
      {opportunity.releaseGate && (
        <div className={`release-gate tone-${opportunity.releaseGate.tone}`}>
          <div className="release-gate-summary">
            <ShieldCheck size={16} />
            <strong>{opportunity.releaseGate.title}</strong>
            <span>{opportunity.releaseGate.detail}</span>
          </div>
          {opportunity.releaseGate.gateRows.length > 0 && (
            <div className="release-gate-list" aria-label="推荐发布闸门">
              {opportunity.releaseGate.gateRows.map((gate) => (
                <div className={`release-gate-row tone-${gate.tone}`} key={gate.key}>
                  <div>
                    <span>{gate.label}</span>
                    <strong>{gate.title}</strong>
                    <em>{gate.detail}</em>
                  </div>
                  <b>{gate.progressText}</b>
                  <i>
                    <span style={{ width: gate.width }} />
                  </i>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
      <div className="diagnostic-metrics opportunity-metrics">
        {opportunity.metrics.map((metric, index) => {
          const Icon = iconMap[index] ?? ListChecks;
          return (
            <div className={`diagnostic-metric tone-${metric.tone}`} key={metric.label}>
              <Icon size={16} />
              <span>{metric.label}</span>
              <strong>{metric.value}</strong>
              <em>{metric.caption}</em>
            </div>
          );
        })}
      </div>
      {opportunity.counterSignal && (
        <div className={`counter-signal-panel tone-${opportunity.counterSignal.tone}`}>
          <div className="counter-signal-head">
            <Activity size={16} />
            <div>
              <strong>{opportunity.counterSignal.title}</strong>
              <span>{opportunity.counterSignal.detail}</span>
            </div>
            <em>{opportunity.counterSignal.modelText}</em>
            <b>{opportunity.counterSignal.candidateBandsText}</b>
          </div>
          <div className="counter-signal-list">
            {opportunity.counterSignal.candidates.length ? opportunity.counterSignal.candidates.map((candidate) => (
              <div className="counter-signal-row" key={candidate.ledgerId}>
                <div>
                  <TeamMatchup
                    record={{
                      matchup: candidate.matchup,
                      home_team: candidate.homeTeam,
                      away_team: candidate.awayTeam,
                      home_team_logo_url: candidate.homeTeamLogoUrl,
                      away_team_logo_url: candidate.awayTeamLogoUrl
                    }}
                    compact
                  />
                  <span>{[candidate.league, candidate.selection, candidate.signalLabel, candidate.bandText].filter(Boolean).join(" · ")}</span>
                  <em>{candidate.signalReason}</em>
                </div>
                <div className="candidate-metrics">
                  <span>学习 {candidate.probabilityText}</span>
                  <span>重校准 {candidate.metaProbabilityText}</span>
                  <span>边际 {candidate.metaEdgeText}</span>
                  <span>{candidate.oddsText}</span>
                  <em>{candidate.snapshotText}</em>
                  <em>{candidate.confidenceText}</em>
                </div>
                <b>{candidate.actionLabel}</b>
                <button type="button" className="icon-text-button" onClick={() => onSelect(candidate.ledgerId)}>
                  <Eye size={15} />
                  <span>查看</span>
                </button>
              </div>
            )) : <div className="empty-state compact">暂无反向观察候选。</div>}
          </div>
        </div>
      )}
      <div className="opportunity-body">
        <div className="opportunity-candidates">
          <div className="panel-title compact-title">
            <Eye size={18} />
            <h2>观察信号样本</h2>
          </div>
          <div className="opportunity-candidate-list">
            {opportunity.candidates.length ? opportunity.candidates.map((candidate) => (
              <div className="opportunity-candidate-row" key={candidate.ledgerId}>
                <div>
                  <TeamMatchup
                    record={{
                      matchup: candidate.matchup,
                      home_team: candidate.homeTeam,
                      away_team: candidate.awayTeam,
                      home_team_logo_url: candidate.homeTeamLogoUrl,
                      away_team_logo_url: candidate.awayTeamLogoUrl
                    }}
                    compact
                  />
                  <span>{[candidate.league, candidate.selection, candidate.actionLabel].filter(Boolean).join(" · ")}</span>
                </div>
                <div className="candidate-metrics">
                  <span>{candidate.probabilityText}</span>
                  <span>{candidate.edgeText}</span>
                  <span>{candidate.oddsText}</span>
                  <em>{candidate.snapshotText}</em>
                </div>
                <b className={candidate.thresholdReady ? "good-text" : "muted-text"}>{candidate.blockerLabel}</b>
                <button type="button" className="icon-text-button" onClick={() => onSelect(candidate.ledgerId)}>
                  <Eye size={15} />
                  <span>查看</span>
                </button>
              </div>
            )) : <div className="empty-state compact">暂无观察信号样本。</div>}
          </div>
        </div>
        <div className="opportunity-blockers">
          <div className="panel-title compact-title">
            <AlertTriangle size={18} />
            <h2>主要原因</h2>
          </div>
          <div className="funnel-list">
            {opportunity.blockers.length ? opportunity.blockers.map((item) => (
              <div className="funnel-row" key={item.key}>
                <div>
                  <span>{item.label}</span>
                  <strong>{item.countText}</strong>
                </div>
                <div className="funnel-track">
                  <i style={{ width: item.width }} />
                </div>
              </div>
            )) : <div className="empty-state compact">暂无阻断原因。</div>}
          </div>
        </div>
      </div>
    </section>
  );
}

function PickTable({
  rows,
  selectedLedgerId,
  onSelect
}: {
  rows: DashboardRecord[];
  selectedLedgerId: string | null;
  onSelect: (record: DashboardRecord) => void;
}) {
  if (!rows.length) {
    return (
      <div className="empty-state">
        当前没有达到发布标准的亚盘信号。系统仍在记录观察样本并等待回测闭环。
      </div>
    );
  }

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>联赛</th>
            <th>比赛</th>
            <th>开赛</th>
            <th>方向</th>
            <th>赔率</th>
            <th>模型</th>
            <th>学习后</th>
            <th>价值边际</th>
            <th>风险</th>
            <th>详情</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const ledgerId = `recommendation:${row.id}`;
            return (
            <tr className={ledgerId === selectedLedgerId ? "selected-row" : ""} key={row.id}>
              <td>{row.league || "—"}</td>
              <td>
                <TeamMatchup record={row} meta={countdown(row.kickoff_utc_plus_8)} />
              </td>
              <td>{localTime(row.kickoff_utc_plus_8)}</td>
              <td>{row.selection || "—"}</td>
              <td>{formatOdds(row.decimal_odds)}</td>
              <td>{formatPercent(row.model_probability)}</td>
              <td>{formatPercent(row.learned_probability)}</td>
              <td>{formatSignedPercent(row.edge)}</td>
              <td>
                <div className="chips">
                  {(row.risk_flags.length ? row.risk_flags : ["no_hard_blockers"]).slice(0, 2).map((flag) => (
                    <span className="chip" key={flag}>{statusFlagLabel(flag)}</span>
                  ))}
                </div>
              </td>
              <td>
                <button
                  type="button"
                  className="row-action"
                  onClick={() => onSelect(row)}
                  aria-label={`查看 ${displayMatchup(row.matchup)} 详情`}
                >
                  <span>查看</span>
                  <ChevronRight size={15} />
                </button>
              </td>
            </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function probabilityWidth(row: ProbabilityRow): string {
  const value = row.value ?? 0;
  return `${Math.max(0, Math.min(100, value * 100))}%`;
}

function playerText(player: { name: string; position: string; shirt_number: string; captain: boolean }): string {
  const meta = [player.shirt_number ? `${player.shirt_number}号` : "", player.position, player.captain ? "队长" : ""]
    .filter(Boolean)
    .join(" · ");
  return meta ? `${player.name || "未知球员"} · ${meta}` : player.name || "未知球员";
}

function MatchDetailPanel({
  detail,
  loading,
  error
}: {
  detail: DashboardMatchDetail | null;
  loading: boolean;
  error: string | null;
}) {
  const [expandedBookmakers, setExpandedBookmakers] = useState<Record<string, boolean>>({});
  const detailKey = detail?.record.ledger_id || "";

  useEffect(() => {
    setExpandedBookmakers({});
  }, [detailKey]);

  if (loading && !detail) {
    return (
      <section className="panel detail-panel">
        <div className="panel-title">
          <Gauge size={18} />
          <h2>比赛详情</h2>
        </div>
        <div className="empty-state compact">正在读取该场持久化分析证据...</div>
      </section>
    );
  }

  if (error && !detail) {
    return (
      <section className="panel detail-panel">
        <div className="panel-title">
          <Gauge size={18} />
          <h2>比赛详情</h2>
        </div>
        <div className="banner compact">详情读取失败：{error}</div>
      </section>
    );
  }

  if (!detail) {
    return (
      <section className="panel detail-panel">
        <div className="panel-title">
          <Gauge size={18} />
          <h2>比赛详情</h2>
        </div>
        <div className="empty-state compact">选择一场预测样本后查看完整证据。</div>
      </section>
    );
  }

  const view = buildMatchDetailView(detail);
  const contextIcons = [MapPin, CloudSun, UserRound];
  const toggleBookmaker = (groupId: string) => {
    setExpandedBookmakers((current) => ({
      ...current,
      [groupId]: !(current[groupId] ?? false)
    }));
  };

  return (
    <section className="panel detail-panel" aria-label="比赛详情">
      <div className="panel-title">
        <Gauge size={18} />
        <h2>比赛详情</h2>
        <span className="status-pill neutral">
          {detail.record.status_label || recordStatusText(detail.record.settlement_status, detail.record.hit)}
        </span>
      </div>
      <div className="detail-heading">
        <TeamMatchup record={detail.record} meta={view.subtitle || "—"} size="large" />
        <b>{view.marketSummary}</b>
      </div>
      <div className="detail-grid">
        <Metric label="推荐动作" value={view.actionText} />
        <Metric label="盘口方向" value={detail.record.selection || "—"} />
        <Metric label="开赛时间" value={localTime(detail.record.kickoff_utc_plus_8)} />
        <Metric label="比分状态" value={view.scoreStatusText} />
        <Metric label="期望倍数" value={formatOdds(detail.evidence.core_metrics.expected_multiplier)} />
      </div>
      <div className={`clv-detail-card ${toneClass(view.clvTracking.tone)}`}>
        <div>
          <TrendingUp size={16} />
          <span>CLV 收盘价</span>
          <strong>{view.clvTracking.title}</strong>
        </div>
        <p>{view.clvTracking.detail}</p>
        <div className="clv-detail-metrics">
          <b>{view.clvTracking.priceText}</b>
          <strong>{view.clvTracking.clvText}</strong>
          <time>{view.clvTracking.timeText.includes("T") ? localTime(view.clvTracking.timeText) : view.clvTracking.timeText}</time>
        </div>
      </div>
      <div className="probability-stack">
        {view.probabilityRows.map((row) => (
          <div className="probability-row" key={row.label}>
            <span>{row.label}</span>
            <div className="bar-track">
              <i style={{ width: probabilityWidth(row) }} />
            </div>
            <strong>{row.text}</strong>
          </div>
        ))}
      </div>
      <div className={`prediction-diagnostic ${toneClass(view.predictionDiagnostic.tone)}`}>
        <div className="prediction-diagnostic-head">
          <BrainCircuit size={16} />
          <strong>预测诊断</strong>
          <span>{view.predictionDiagnostic.title} · {view.predictionDiagnostic.statusText}</span>
          <em>{view.predictionDiagnostic.passText}</em>
      </div>
      <p>{view.predictionDiagnostic.summary}</p>
      {view.predictionDiagnostic.learningDetail && <p>{view.predictionDiagnostic.learningDetail}</p>}
      <div className="prediction-diagnostic-grid">
          {view.predictionDiagnostic.gapRows.map((row) => (
            <div key={row.label}>
              <span>{row.label}</span>
              <strong>{row.value}</strong>
            </div>
          ))}
        </div>
        {view.predictionDiagnostic.explanationRows.length > 0 && (
          <div className="model-explanation-grid" aria-label="模型解释">
            {view.predictionDiagnostic.explanationRows.map((row) => (
              <div className={`model-explanation-card ${toneClass(row.tone)}`} key={`${row.label}-${row.value}`}>
                <span>{row.label}</span>
                <strong>{row.value}</strong>
                <p>{row.detail}</p>
              </div>
            ))}
          </div>
        )}
      </div>
      <div className="detail-block">
        <div className="detail-block-title">
          <MapPin size={16} />
          <span>赛事情报</span>
          <em className="inline-note">{view.contextSourceText}</em>
        </div>
        <div className="context-grid">
          {view.contextRows.map((row, index) => {
            const Icon = contextIcons[index] ?? ListChecks;
            return (
              <div className={`context-row ${row.available ? "" : "muted"}`} key={row.label}>
                <Icon size={15} />
                <span>{row.label}</span>
                <strong>{row.value}</strong>
                <em>{row.statusText}</em>
              </div>
            );
          })}
        </div>
        <div className="context-diagnostics">
          {view.contextDiagnostics.map((item) => (
            <div className={`context-diagnostic ${toneClass(item.tone)}`} key={`${item.label}-${item.detail}`}>
              <ShieldCheck size={15} />
              <strong>{item.label}</strong>
              <span>{item.detail}</span>
            </div>
          ))}
        </div>
        {view.sourceAttemptRows.length > 0 && (
          <div className="source-attempt-list" aria-label="来源核验">
            {view.sourceAttemptRows.map((attempt) => (
              <div className={`source-attempt-row ${toneClass(attempt.tone)}`} key={`${attempt.providerText}-${attempt.matchIdText}`}>
                <div>
                  <strong>{attempt.providerText}</strong>
                  <span>{attempt.matchIdText}</span>
                  <b>{attempt.statusText}</b>
                </div>
                <p>{attempt.fieldSummary}</p>
                {attempt.detail && <em>{attempt.detail}</em>}
              </div>
            ))}
          </div>
        )}
      </div>
      <div className="detail-block">
        <div className="detail-block-title">
          <UsersRound size={16} />
          <span>阵容球员</span>
          <em className="inline-note">{view.lineup.statusText}</em>
        </div>
        {view.lineup.available ? (
          <div className="lineup-grid">
            {[
              { label: detail.record.home_team || "主队", logoUrl: detail.record.home_team_logo_url, team: view.lineup.home },
              { label: detail.record.away_team || "客队", logoUrl: detail.record.away_team_logo_url, team: view.lineup.away }
            ].map((item) => (
              <div className="lineup-team" key={item.label}>
                <div className="lineup-team-head">
                  <div className="lineup-team-title">
                    <TeamBadge teamName={item.label} logoUrl={item.logoUrl} />
                    <strong>{item.label}</strong>
                  </div>
                  <span>{item.team.formation} · {item.team.starterCountText}</span>
                </div>
                <div className="player-list">
                  {item.team.players.length ? item.team.players.slice(0, 8).map((player, index) => (
                    <span className="player-row" key={`${item.label}-${player.name}-${index}`}>
                      {playerText(player)}
                    </span>
                  )) : <span className="player-row muted">暂未采集球员名单</span>}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="empty-state compact">{view.lineup.statusText}。</div>
        )}
        {view.lineup.warnings.length > 0 && (
          <div className="chips">
            {view.lineup.warnings.slice(0, 4).map((warning) => (
              <span className="chip" key={warning}>{warning}</span>
            ))}
          </div>
        )}
      </div>
      <div className="detail-block">
        <div className="detail-block-title">
          <Database size={16} />
          <span>赔率快照</span>
          <em className="inline-note">{view.oddsSummary}</em>
        </div>
        {view.oddsGroups.length ? (
          <div className="bookmaker-groups">
            {view.oddsGroups.map((group, groupIndex) => {
              const isExpanded = expandedBookmakers[group.id] ?? groupIndex === 0;
              return (
                <div className="bookmaker-group" key={group.id}>
                  <button
                    type="button"
                    className="bookmaker-group-toggle"
                    aria-expanded={isExpanded}
                    onClick={() => toggleBookmaker(group.id)}
                  >
                    {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                    <strong>{group.bookmaker}</strong>
                    <span>{group.rowCountText}</span>
                    <em>{group.marketTypesText}</em>
                    <time>{localTime(group.latestFetchedAtUtc)}</time>
                  </button>
                  {isExpanded && (
                    <div className="table-wrap">
                      <table className="odds-detail-table">
                        <thead>
                          <tr>
                            <th>盘口类型</th>
                            <th>方向</th>
                            <th>盘口</th>
                            <th>赔率</th>
                            <th>来源时间</th>
                            <th>采集时间</th>
                          </tr>
                        </thead>
                        <tbody>
                          {group.rows.map((row, index) => (
                            <tr key={`${row.bookmaker}-${row.market_type}-${row.selection}-${row.source_time_utc}-${index}`}>
                              <td>{row.marketTypeLabel}</td>
                              <td>{row.selectionText || "—"}</td>
                              <td>{row.lineText}</td>
                              <td><strong className="profit">{row.oddsText}</strong></td>
                              <td>{localTime(row.source_time_utc)}</td>
                              <td>{localTime(row.fetched_at_utc)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ) : view.candidateRows.length ? (
          <div className="candidate-odds-fallback">
            <strong>暂无多公司时间序列快照</strong>
            <span>但本场已有预测使用的盘口赔率，下面先展示当前可用盘口。</span>
            <div className="candidate-mini-table">
              {view.candidateRows.map((candidate) => (
                <div className="candidate-mini-row candidate-odds-row" key={`${candidate.selection}-${candidate.oddsText}`}>
                  <span>{candidate.selectionText}</span>
                  <small>{candidate.providerText || "来源未知"}</small>
                  <strong>{candidate.oddsText}</strong>
                  <b>{candidate.probabilityText}</b>
                  <em>{candidate.edgeText}</em>
                </div>
              ))}
            </div>
          </div>
        ) : (
          <div className="empty-state compact">本地暂无多公司时间序列快照。这表示尚未成功采集或匹配，不代表雷速没有赔率。</div>
        )}
      </div>
      <div className="detail-block">
        <div className="detail-block-title">
          <ListChecks size={16} />
          <span>数据与风险</span>
        </div>
        <div className="chips">
          {[...view.dataFlags, ...(view.riskFlags.length ? view.riskFlags : ["无硬性阻断"])].slice(0, 10).map((flag) => (
            <span className="chip" key={flag}>{flag}</span>
          ))}
        </div>
      </div>
      {view.candidateRows.length > 0 && (
        <div className="detail-block">
          <div className="detail-block-title">
            <TrendingUp size={16} />
            <span>候选盘口对比</span>
          </div>
          <div className="candidate-mini-table">
            {view.candidateRows.map((candidate) => (
              <div className="candidate-mini-row" key={`${candidate.selection}-${candidate.oddsText}`}>
                <span>{candidate.selectionText}</span>
                <small>{candidate.providerText || "来源未知"}</small>
                <strong>{candidate.oddsText}</strong>
                <b>{candidate.probabilityText}</b>
                <em>{candidate.edgeText}</em>
              </div>
            ))}
          </div>
        </div>
      )}
      <div className="detail-block">
        <div className="detail-block-title">
          <Activity size={16} />
          <span>闭环轨迹</span>
        </div>
        <div className="detail-timeline">
          {view.timeline.map((item, index) => (
            <div className="timeline-row" key={`${item.title}-${index}`}>
              <strong>{customerCopy(item.title)}</strong>
              <span>{readableEventDetail(item.detail)}</span>
              <time>{localTime(item.at_utc)}</time>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function MatchDetailPage({
  ledgerId,
  detail,
  loading,
  error,
  onBack
}: {
  ledgerId: string;
  detail: DashboardMatchDetail | null;
  loading: boolean;
  error: string | null;
  onBack: () => void;
}) {
  const snapshotCount = detail?.odds_snapshot.snapshot_count ?? 0;
  const bookmakerCount = detail?.odds_snapshot.bookmaker_count ?? 0;
  const title = detail ? displayMatchup(detail.record.matchup) : "比赛详情";
  const subtitle = detail
    ? [detail.record.league, detail.record.prediction_type_label, marketLabel(detail.record.market)].filter(Boolean).join(" · ")
    : ledgerId;

  return (
    <div className="match-page">
      <button type="button" className="back-button" onClick={onBack}>
        <ArrowLeft size={16} />
        <span>返回监控台</span>
      </button>
      <section className="panel match-page-hero">
        <div>
          <span className="eyebrow">比赛详情</span>
          <h2>{title}</h2>
          <p>{subtitle || "正在读取持久化样本"}</p>
          <p className="match-resolution-line">{oddsResolutionSource(detail)}</p>
        </div>
        <div className="match-page-metrics">
          <Metric label="雷速匹配" value={oddsResolutionText(detail)} />
          <Metric label="赔率快照" value={`${snapshotCount} 条`} />
          <Metric label="公司数量" value={`${bookmakerCount} 家`} />
        </div>
      </section>
      <MatchDetailPanel detail={detail} loading={loading} error={error} />
    </div>
  );
}

function StrategyPanel({ snapshot }: { snapshot: DashboardSnapshot }) {
  const strategy = snapshot.strategy_state;
  return (
    <section className="panel">
      <div className="panel-title">
        <ShieldCheck size={18} />
        <h2>策略状态</h2>
        <span className={`status-pill ${strategy.active ? "good" : "caution"}`}>{strategyStatusLabel(strategy)}</span>
      </div>
      <div className="strategy-grid">
        <Metric label="命中率" value={formatPercent(strategy.hit_rate)} />
        <Metric label="收益率" value={formatSignedPercent(strategy.roi)} />
        <Metric label="最低概率" value={formatPercent(strategy.min_calibrated_probability)} />
        <Metric label="赔率区间" value={`${formatOdds(strategy.min_decimal_odds)} - ${formatOdds(strategy.max_decimal_odds)}`} />
        <Metric label="最低价值边际" value={formatSignedPercent(strategy.min_value_edge)} />
        <Metric label="先验权重" value={String(strategy.prior_strength ?? "—")} />
      </div>
      <p className="panel-note">
        该状态由结算结果自动刷新。样本达到阈值后，均衡亚盘推荐会读取这些阈值并应用实时校准。
      </p>
    </section>
  );
}

function ContextCoveragePanel({ view }: { view: ReturnType<typeof buildDashboardView> }) {
  const iconMap: Record<string, typeof MapPin> = {
    venue: MapPin,
    weather: CloudSun,
    referee: UserRound,
    lineup: UsersRound
  };
  return (
    <section className="panel context-coverage-panel">
      <div className="panel-title">
        <MapPin size={18} />
        <h2>赛事情报覆盖</h2>
        <span className="status-pill neutral">{view.contextCoverage.totalText}</span>
      </div>
      <p className="panel-note">{view.contextCoverage.summary}</p>
      <div className="context-source-line">{view.contextCoverage.sourceText}</div>
      <div className="context-coverage-list">
        {view.contextCoverage.fields.length ? view.contextCoverage.fields.map((field) => {
          const Icon = iconMap[field.key] ?? ListChecks;
          return (
            <div className={`context-coverage-row tone-${field.tone}`} key={field.key}>
              <Icon size={15} />
              <div>
                <span>{field.label}</span>
                <strong>{field.value}</strong>
                <em>{field.caption}</em>
                <div className="audit-progress" aria-label={`${field.label}覆盖 ${field.value}`}>
                  <i style={{ width: field.width }} />
                </div>
              </div>
            </div>
          );
        }) : <div className="empty-state compact">暂无赛事情报统计。</div>}
      </div>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function DataSourcePanel({ snapshot }: { snapshot: DashboardSnapshot }) {
  const clv = snapshot.clv_tracking;
  const marketSummary = snapshot.market_snapshot_summary;
  const calibrationSampleCount = snapshot.strategy_state.sample_count ?? snapshot.prediction_kpis.settled_count ?? 0;
  const clvText = clv ? `${clv.available_count}/${clv.tracked_count}` : "0/0";
  return (
    <section className="panel data-source-panel" aria-label="当前数据源">
      <div className="panel-title">
        <Database size={18} />
        <h2>当前数据源</h2>
        <span className="status-pill neutral">后端实际读取</span>
      </div>
      <div className="data-source-grid">
        <Metric label="学习库" value={snapshot.db_path || "未返回"} />
        <Metric label="赔率库" value={marketSummary?.db_path || "未返回"} />
        <Metric label="校准样本" value={`${calibrationSampleCount} 场`} />
        <Metric label="CLV 样本" value={clvText} />
      </div>
      <p className="panel-note">
        这里展示本次接口实际读取的数据路径，用于区分本机临时库、容器运行库和赔率快照库。
      </p>
    </section>
  );
}

function DataSourceHealthPanel({ view }: { view: DashboardViewModel }) {
  const health = view.dataSourceHealth;
  const cardIcons = [RefreshCw, Database, ListChecks, Clock];
  const pillTone = health.tone === "good" ? "good" : health.tone === "bad" ? "bad" : health.tone === "caution" ? "caution" : "neutral";
  return (
    <section className={`panel data-health-panel tone-${health.tone}`} aria-label="数据采集健康中心">
      <div className="data-health-head">
        <div>
          <span className="eyebrow">数据采集健康中心</span>
          <h2>{health.title}</h2>
          <p>{health.detail}</p>
        </div>
        <span className={`status-pill ${pillTone}`}>{health.issueText}</span>
      </div>
      <div className="data-health-status-grid">
        {health.statusCards.map((card, index) => {
          const Icon = cardIcons[index] ?? Database;
          return (
            <div className={`diagnostic-metric tone-${card.tone}`} key={card.label}>
              <Icon size={16} />
              <span>{card.label}</span>
              <strong>{card.value}</strong>
              <em>{card.caption}</em>
            </div>
          );
        })}
      </div>
      <div className="data-health-check-grid">
        {health.checkRows.map((row) => (
          <div className={`data-health-check tone-${row.tone}`} key={row.key}>
            <div>
              <span>{row.label}</span>
              <strong>{row.title}</strong>
              <em>{row.detail}</em>
            </div>
            <b>{row.statusText}</b>
            <i>
              <span style={{ width: row.width }} />
            </i>
            <small>{row.metaText}</small>
          </div>
        ))}
      </div>
    </section>
  );
}

function FilterPanel({ snapshot }: { snapshot: DashboardSnapshot }) {
  const view = buildDashboardView(snapshot);
  return (
    <section className="panel">
      <div className="panel-title">
        <AlertTriangle size={18} />
        <h2>候选池过滤</h2>
      </div>
      <div className="filter-list">
        {view.filterGroups.length ? (
          view.filterGroups.map((group) => (
            <div className="filter-row" key={group.reason}>
              <span>{group.label}</span>
              <strong>{group.count}</strong>
            </div>
          ))
        ) : (
          <div className="empty-state compact">暂无观察样本。</div>
        )}
      </div>
    </section>
  );
}

function EventPanel({ events }: { events: LearningEvent[] }) {
  return (
    <section className="panel wide">
      <div className="panel-title">
        <Activity size={18} />
        <h2>自动学习流水</h2>
      </div>
      <div className="event-list">
        {events.length ? events.map((event, index) => (
          <div className="event-row" key={`${event.kind}-${event.at_utc}-${index}`}>
            <span className={`event-dot ${event.severity}`} />
            <div>
              <strong>{customerCopy(event.title)}</strong>
              <p>{readableEventDetail(event.detail)}</p>
            </div>
            <time>{localTime(event.at_utc)}</time>
          </div>
        )) : <div className="empty-state compact">暂无学习流水。</div>}
      </div>
    </section>
  );
}

function settlementGroupKey(row: DashboardRecord): string {
  return [row.league, row.matchup, row.score || ""].join("|");
}

function settlementGroups(rows: DashboardRecord[]): Array<{ key: string; rows: DashboardRecord[] }> {
  const groups: Array<{ key: string; rows: DashboardRecord[] }> = [];
  const index = new Map<string, { key: string; rows: DashboardRecord[] }>();
  for (const row of rows) {
    const key = settlementGroupKey(row);
    let group = index.get(key);
    if (!group) {
      group = { key, rows: [] };
      index.set(key, group);
      groups.push(group);
    }
    group.rows.push(row);
  }
  return groups;
}

function SettlementPanel({ rows }: { rows: DashboardRecord[] }) {
  const groups = settlementGroups(rows).slice(0, 6);

  return (
    <section className="panel wide">
      <div className="panel-title">
        <CheckCircle2 size={18} />
        <h2>最近结算</h2>
      </div>
      <div className="settlement-grid">
        {groups.length ? groups.map((group) => {
          const primary = group.rows[0];
          return (
            <div className="settlement-card" key={group.key}>
              <div className="settlement-card-head">
                <span>{primary.league}</span>
                {group.rows.length > 1 && <em>同场多盘口 {group.rows.length}</em>}
              </div>
              <TeamMatchup record={primary} meta={`真实比分 ${primary.score || "—"}`} compact />
              <div className="settlement-lines">
                {group.rows.map((row) => (
                  <div className="settlement-line" key={row.id}>
                    <span>{row.selection || "—"}</span>
                    <b className={row.hit ? "profit" : "loss"}>{row.hit ? "命中" : "未命中"} · {row.profit_units ?? "—"}</b>
                  </div>
                ))}
              </div>
            </div>
          );
        }) : <div className="empty-state compact">暂无已结算推荐。</div>}
      </div>
    </section>
  );
}

function SnapshotCoveragePanel({ view }: { view: ReturnType<typeof buildDashboardView> }) {
  return (
    <section className="panel">
      <div className="panel-title">
        <Database size={18} />
        <h2>赔率时间序列</h2>
        <span className="status-pill neutral">{view.snapshotSummary}</span>
      </div>
      <div className="snapshot-provider-list">
        {view.snapshotProviders.length ? (
          view.snapshotProviders.map((provider) => (
            <div className="snapshot-provider-row" key={provider.provider}>
              <div>
                <strong>{provider.providerLabel}</strong>
                <span>{provider.marketTypesText}</span>
              </div>
              <div className="snapshot-provider-metrics">
                <b>{provider.snapshot_count}</b>
                <span>{provider.event_count} 场 · {provider.bookmaker_count} 家</span>
                <time>{localTime(provider.latest_fetched_at_utc)}</time>
              </div>
            </div>
          ))
        ) : (
          <div className="empty-state compact">{view.snapshotEmptyText}</div>
        )}
      </div>
    </section>
  );
}

function ledgerMatches(filter: LedgerFilter, row: ReturnType<typeof buildDashboardView>["predictionRows"][number]): boolean {
  if (filter === "all") return true;
  if (filter === "recommendation") return row.prediction_type === "recommendation";
  if (filter === "observation") return row.prediction_type === "observation";
  if (filter === "settled") return row.settlement_status === "settled";
  if (filter === "open") return row.settlement_status === "open";
  if (filter === "hit") return row.settlement_status === "settled" && row.hit === 1;
  if (filter === "miss") return row.settlement_status === "settled" && row.hit === 0;
  return true;
}

function PredictionLedgerPanel({
  rows,
  summary,
  filter,
  onFilterChange,
  selectedLedgerId,
  onSelect,
  collapsed,
  onCollapsedChange
}: {
  rows: ReturnType<typeof buildDashboardView>["predictionRows"];
  summary: string;
  filter: LedgerFilter;
  onFilterChange: (filter: LedgerFilter) => void;
  selectedLedgerId: string | null;
  onSelect: (ledgerId: string) => void;
  collapsed: boolean;
  onCollapsedChange: (collapsed: boolean) => void;
}) {
  const visibleRows = rows.filter((row) => ledgerMatches(filter, row));
  const toggleLabel = collapsed ? "展开台账" : "收起台账";

  return (
    <section className={`panel ledger-panel ${collapsed ? "collapsed" : ""}`}>
      <div className="panel-title">
        <ListChecks size={18} />
        <h2>预测台账</h2>
        <span className="status-pill neutral">{summary}</span>
        <button
          type="button"
          className="panel-toggle"
          aria-expanded={!collapsed}
          aria-controls="prediction-ledger-body"
          onClick={() => onCollapsedChange(!collapsed)}
        >
          <span>{toggleLabel}</span>
          <ChevronDown className={collapsed ? "" : "expanded"} size={16} aria-hidden="true" />
        </button>
      </div>
      {collapsed ? (
        <div id="prediction-ledger-body" className="ledger-collapsed-note">
          明细已收起，展开后可筛选样本，并点击某场查看预测、赛果、赔率快照和赛事情报。
        </div>
      ) : (
        <div id="prediction-ledger-body" className="ledger-body">
          <div className="segmented-control" aria-label="预测台账筛选">
            {LEDGER_FILTERS.map((item) => (
              <button
                type="button"
                key={item.key}
                className={filter === item.key ? "active" : ""}
                onClick={() => onFilterChange(item.key)}
              >
                {item.label}
              </button>
            ))}
          </div>
          <div className="table-wrap">
            <table className="ledger-table">
              <thead>
                <tr>
                  <th>类型</th>
                  <th>状态</th>
                  <th>联赛</th>
                  <th>比赛</th>
                  <th>开赛</th>
                  <th>预测方向</th>
                  <th>赔率</th>
                  <th>概率</th>
                  <th>价值边际</th>
                  <th>真实比分</th>
                  <th>收益</th>
                  <th>结算时间</th>
                  <th>详情</th>
                </tr>
              </thead>
              <tbody>
              {visibleRows.length ? visibleRows.map((row) => (
                  <tr className={row.ledger_id === selectedLedgerId ? "selected-row" : ""} key={row.ledger_id}>
                    <td>
                      <div className="match-cell">
                        <strong>{row.diagnosticLabel}</strong>
                        <span>{row.diagnosticReasonText}</span>
                      </div>
                    </td>
                    <td><span className={`result-pill ${row.statusText === "命中" ? "hit" : row.statusText === "未命中" ? "miss" : ""}`}>{row.statusText}</span></td>
                    <td>{row.league || "—"}</td>
                    <td><TeamMatchup record={row} meta={row.oddsCoverageText} compact /></td>
                    <td>{localTime(row.kickoff_utc_plus_8)}</td>
                    <td>
                      <div className="match-cell">
                        <strong>{row.selection || "—"}</strong>
                        <span>{row.diagnosticGapText}</span>
                      </div>
                    </td>
                    <td>{row.oddsText}</td>
                    <td>{row.probabilityText}</td>
                    <td>{row.edgeText}</td>
                    <td>{row.scoreText}</td>
                    <td>{row.profitText}</td>
                    <td>{localTime(row.settled_at_utc)}</td>
                    <td>
                      <button
                        type="button"
                        className="icon-action"
                        aria-label={`查看 ${row.matchup} 样本详情`}
                        aria-pressed={row.ledger_id === selectedLedgerId}
                        onClick={() => onSelect(row.ledger_id)}
                      >
                        <Eye size={15} />
                      </button>
                    </td>
                  </tr>
                )) : (
                  <tr>
                    <td colSpan={13}>
                      <div className="empty-state compact">当前筛选下没有预测记录。</div>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  );
}

function OverviewSection({
  snapshot,
  view,
  selectedLedgerId,
  onSelectRecommendation
}: {
  snapshot: DashboardSnapshot;
  view: DashboardViewModel;
  selectedLedgerId: string | null;
  onSelectRecommendation: (record: DashboardRecord) => void;
}) {
  return (
    <div className="dashboard-section">
      <OperationStatusPanel snapshot={snapshot} view={view} />
      <KpiStrip cards={view.kpiCards} />
      <MatchPhaseStrip view={view} />
      <section className="overview-layout" aria-label="概览工作区">
        <div className="overview-main">
          <section className="panel main-panel">
            <div className="panel-title">
              <TrendingUp size={18} />
              <h2>未来窗口亚盘候选</h2>
              <span className="status-pill neutral">均衡模式 · 亚盘</span>
            </div>
            <PickTable
              rows={view.pickRows}
              selectedLedgerId={selectedLedgerId}
              onSelect={onSelectRecommendation}
            />
          </section>
          <BacktestCurvePanel view={view} />
        </div>
        <div className="overview-side">
          <MetricGlossaryPanel />
          <ProductionReadinessPanel view={view} />
        </div>
      </section>
    </div>
  );
}

function ProductionSection({ view }: { view: DashboardViewModel }) {
  return (
    <div className="dashboard-section">
      <ProductionCommandCenterPanel view={view} />
      <AutoLearningWorkflowPanel view={view} />
      <section className="production-lower-grid">
        <ProductionReadinessPanel view={view} />
        <PredictionAccountabilityPanel view={view} />
      </section>
    </div>
  );
}

function ModelSection({ view }: { view: DashboardViewModel }) {
  return (
    <div className="dashboard-section">
      <MetricGlossaryPanel />
      <ModelGovernancePanel view={view} />
      <LearningEffectivenessPanel view={view} />
      <BacktestCurvePanel view={view} />
      <PredictionQualityPanel view={view} />
      <AdaptiveLearningPlanPanel view={view} />
    </div>
  );
}

function SignalsSection({
  snapshot,
  view,
  ledgerFilter,
  selectedLedgerId,
  ledgerCollapsed,
  onLedgerFilterChange,
  onLedgerCollapsedChange,
  onSelectLedger,
  onSelectRecommendation
}: {
  snapshot: DashboardSnapshot;
  view: DashboardViewModel;
  ledgerFilter: LedgerFilter;
  selectedLedgerId: string | null;
  ledgerCollapsed: boolean;
  onLedgerFilterChange: (filter: LedgerFilter) => void;
  onLedgerCollapsedChange: (collapsed: boolean) => void;
  onSelectLedger: (ledgerId: string) => void;
  onSelectRecommendation: (record: DashboardRecord) => void;
}) {
  return (
    <div className="dashboard-section">
      <RecommendationOpportunityPanel view={view} onSelect={onSelectLedger} />
      <section className="panel main-panel">
        <div className="panel-title">
          <TrendingUp size={18} />
          <h2>未来窗口亚盘候选</h2>
          <span className="status-pill neutral">均衡模式 · 亚盘</span>
        </div>
        <PickTable
          rows={view.pickRows}
          selectedLedgerId={selectedLedgerId}
          onSelect={onSelectRecommendation}
        />
      </section>
      <PredictionLedgerPanel
        rows={view.predictionRows}
        summary={view.predictionSummary}
        filter={ledgerFilter}
        onFilterChange={onLedgerFilterChange}
        selectedLedgerId={selectedLedgerId}
        onSelect={onSelectLedger}
        collapsed={ledgerCollapsed}
        onCollapsedChange={onLedgerCollapsedChange}
      />
      <section className="signals-lower-grid">
        <FilterPanel snapshot={snapshot} />
        <SettlementPanel rows={snapshot.recent_settlements} />
      </section>
    </div>
  );
}

function DataSection({
  snapshot,
  view
}: {
  snapshot: DashboardSnapshot;
  view: DashboardViewModel;
}) {
  return (
    <div className="dashboard-section">
      <DataSourceHealthPanel view={view} />
      <DataSourcePanel snapshot={snapshot} />
      <section className="data-grid">
        <SnapshotCoveragePanel view={view} />
        <ClvTrackingPanel view={view} />
        <ContextCoveragePanel view={view} />
        <StrategyPanel snapshot={snapshot} />
      </section>
      <LearningDiagnosticsPanel view={view} />
      <DashboardContractPanel view={view} />
      <AuditPanel view={view} />
      <EventPanel events={snapshot.learning_events} />
    </div>
  );
}

export function App() {
  const [route, setRoute] = useState<DashboardRoute>(() => currentDashboardRoute());
  const [snapshot, setSnapshot] = useState<DashboardSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedLedgerId, setSelectedLedgerId] = useState<string | null>(null);
  const [detail, setDetail] = useState<DashboardMatchDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [ledgerFilter, setLedgerFilter] = useState<LedgerFilter>("all");
  const [ledgerCollapsed, setLedgerCollapsed] = useState(true);
  const [activeSection, setActiveSection] = useState<DashboardSectionKey>("overview");

  useEffect(() => {
    function syncRoute() {
      setRoute(currentDashboardRoute());
    }
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

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const response = await fetch(API_URL, { cache: "no-store" });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json() as DashboardSnapshot;
        if (!cancelled) {
          setSnapshot(data);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    const timer = window.setInterval(load, 30000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    if (!snapshot) return;
    if (route.page === "match") {
      if (selectedLedgerId !== route.ledgerId) setSelectedLedgerId(route.ledgerId);
      return;
    }
    const ledgerIds = (snapshot.prediction_ledger || []).map((row) => row.ledger_id);
    const fallbackPick = snapshot.asian_picks[0] ? `recommendation:${snapshot.asian_picks[0].id}` : null;
    const preferred =
      (snapshot.prediction_ledger || []).find((row) => row.prediction_type === "recommendation" && row.has_odds_snapshot)?.ledger_id
      || (snapshot.prediction_ledger || []).find((row) => row.has_odds_snapshot)?.ledger_id
      || (snapshot.prediction_ledger || []).find((row) => row.prediction_type === "recommendation")?.ledger_id
      || ledgerIds[0]
      || fallbackPick;
    if (!preferred) {
      setSelectedLedgerId(null);
      return;
    }
    if (!selectedLedgerId || !ledgerIds.includes(selectedLedgerId)) {
      setSelectedLedgerId(preferred);
    }
  }, [snapshot, selectedLedgerId, route]);

  useEffect(() => {
    let cancelled = false;

    async function loadDetail(ledgerId: string) {
      setDetailLoading(true);
      setDetailError(null);
      setDetail((current) => current?.record.ledger_id === ledgerId ? current : null);
      try {
        const response = await fetch(`${API_URL}/match/${encodeURIComponent(ledgerId)}`, { cache: "no-store" });
        const data = await response.json() as DashboardMatchDetail;
        if (!response.ok) {
          throw new Error(response.status === 404 ? "当前台账中不存在这场预测，可能是旧数据已清空" : `HTTP ${response.status}`);
        }
        if (data.status !== "ok") throw new Error(data.status);
        if (!cancelled) {
          setDetail(data);
          setDetailError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setDetail(null);
          setDetailError(err instanceof Error ? err.message : String(err));
        }
      } finally {
        if (!cancelled) setDetailLoading(false);
      }
    }

    if (!detailLedgerId) {
      setDetail(null);
      setDetailError(null);
      setDetailLoading(false);
      return () => {
        cancelled = true;
      };
    }

    void loadDetail(detailLedgerId);
    return () => {
      cancelled = true;
    };
  }, [detailLedgerId]);

  const view = useMemo(() => snapshot ? buildDashboardView(snapshot) : null, [snapshot]);
  const isMatchPage = route.page === "match";

  return (
    <main className={`app-shell ${isMatchPage ? "detail-shell" : ""}`}>
      <header className="topbar">
        <div>
          <span className="eyebrow">策略控制台</span>
          <h1>{isMatchPage ? "比赛详情" : "足球策略控制台"}</h1>
        </div>
        <div className="topbar-status">
          <span><Database size={15} /> {snapshot?.kpis.live_calibration_active ? "实时校准已启用" : "样本收集中"}</span>
          <span><Clock size={15} /> {snapshot ? localTime(snapshot.generated_at_utc) : "加载中"}</span>
          <span><RefreshCw size={15} /> 30 秒自动刷新</span>
        </div>
      </header>

      {error && <div className="banner">数据刷新失败：{error}。页面保留最近一次有效快照。</div>}
      {loading && !snapshot && <div className="loading">正在读取策略快照...</div>}

      {isMatchPage ? (
        <MatchDetailPage
          ledgerId={route.ledgerId}
          detail={detail}
          loading={detailLoading}
          error={detailError}
          onBack={navigateToDashboard}
        />
      ) : snapshot && view && (
        <>
          <DashboardSectionTabs sections={view.dashboardSections} active={activeSection} onChange={setActiveSection} />
          {activeSection === "overview" && (
            <OverviewSection
              snapshot={snapshot}
              view={view}
              selectedLedgerId={selectedLedgerId}
              onSelectRecommendation={(record) => navigateToMatch(`recommendation:${record.id}`)}
            />
          )}
          {activeSection === "production" && <ProductionSection view={view} />}
          {activeSection === "model" && <ModelSection view={view} />}
          {activeSection === "signals" && (
            <SignalsSection
              snapshot={snapshot}
              view={view}
              ledgerFilter={ledgerFilter}
              selectedLedgerId={selectedLedgerId}
              ledgerCollapsed={ledgerCollapsed}
              onLedgerFilterChange={setLedgerFilter}
              onLedgerCollapsedChange={setLedgerCollapsed}
              onSelectLedger={navigateToMatch}
              onSelectRecommendation={(record) => navigateToMatch(`recommendation:${record.id}`)}
            />
          )}
          {activeSection === "data" && <DataSection snapshot={snapshot} view={view} />}
          <footer className="footer-note">
            只读监控台，不提供搜索输入，不执行交易动作。数据来自自动学习库与结算校准状态。
          </footer>
        </>
      )}
    </main>
  );
}
