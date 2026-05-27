import type {
  AuditBlockView,
  AuditHealthCard,
  CandidateFilter,
  CandidateRow,
  ContextCoverageView,
  DashboardContextCoverage,
  DashboardContextCoverageSource,
  DashboardDecisionAudit,
  DashboardLearningDiagnostics,
  DashboardRecordDetail,
  DashboardMatchDetail,
  DashboardRecord,
  DashboardSnapshot,
  DashboardView,
  KpiCard,
  MatchDetailView,
  MarketSnapshotProviderView,
  OddsSnapshotBookmakerGroup,
  OddsSnapshotRowView,
  PickView,
  ProbabilityRow,
  RecommendationFunnelView,
  PredictionLedgerRow,
  PredictionLedgerViewRow,
  RecordDetailView,
  StrategyState
} from "./types";

const REASON_LABELS: Record<string, string> = {
  calibrated_probability_below_threshold: "概率不足",
  decimal_odds_below_threshold: "赔率过低",
  decimal_odds_above_threshold: "赔率过高",
  value_edge_below_threshold: "价值边际不足",
  edge_below_threshold: "边际不足",
  core_market_missing: "核心盘口缺失",
  quality_not_bettable: "数据质量不足",
  blocking_flags_present: "存在硬阻断",
  no_positive_edge: "无正向边际",
  large_handicap_requires_backtest: "大盘口需回测",
  multi_bookmaker_snapshot_missing: "缺少多公司赔率",
  awaiting_reanalysis_after_snapshot: "赔率已补齐待复算",
  prediction_decimal_odds_required: "缺少记录赔率",
  matching_market_snapshots_missing: "缺少匹配收盘价",
  snapshot_times_missing: "快照时间缺失",
  pre_kickoff_closing_snapshots_missing: "缺少开赛前快照",
  shadow_prediction_reference_only: "影子预测仅用于对照回测",
  lineup_context_missing: "阵容信息不足",
  no_value: "无正价值",
  no_bet: "不建议",
  immediate_bet: "建议跟踪",
  condition_observe: "条件观察",
  observed_not_recommended: "观察样本",
  supported_market_missing: "缺少可用盘口",
  near_kickoff_under_60m: "临近开赛 60 分钟内"
};

const ACTION_LABELS: Record<string, string> = {
  bet_now: "建议跟踪",
  immediate_bet: "建议跟踪",
  paper_track: "观察跟踪",
  observe: "继续观察",
  condition_observe: "条件观察",
  skip: "跳过",
  no_value: "无正价值",
  no_bet: "不建议",
  paper_counter_signal: "反向观察",
  no_bettable_candidate: "暂无可推荐",
  wait_for_lineup: "等待阵容"
};

const PROVIDER_LABELS: Record<string, string> = {
  dongqiudi: "懂球帝",
  leisu: "雷速体育",
  multi_source: "多源融合",
  the_odds_api: "赔率接口"
};

const MARKET_TYPE_LABELS: Record<string, string> = {
  h2h: "胜平负",
  asian_handicap: "亚盘",
  over_under: "大小球",
  spreads: "让球",
  totals: "大小球"
};

const STAKE_LEVEL_LABELS: Record<string, string> = {
  none: "不下注",
  small: "小注",
  medium: "中注",
  large: "大注",
  watch_only: "仅观察",
  watch_only_until_condition: "条件观察"
};

const DATA_BLOCK_LABELS: Record<string, string> = {
  schedule: "赛程",
  odds: "赔率",
  moneyline_1x2: "胜平负",
  h2h: "胜平负",
  asian_handicap: "亚盘",
  over_under: "大小球",
  multi_bookmaker_snapshot: "多公司赔率快照",
  market_movement_history: "盘口变化",
  lineup: "阵容",
  venue: "场地",
  weather: "天气",
  referee: "裁判",
  recent_form: "近况",
  league_table: "积分榜",
  battle_history: "交锋",
  core_markets: "核心盘口"
};

const CONTEXT_FIELD_LABELS: Record<string, string> = {
  venue: "比赛场地",
  weather: "天气",
  referee: "裁判",
  lineup: "阵容"
};

const BOOLEAN_DATA_LABELS: Record<string, { ok: string; missing: string }> = {
  odds: { ok: "赔率已采集", missing: "赔率暂未采集" },
  schedule: { ok: "赛程已采集", missing: "赛程暂未采集" },
  lineup: { ok: "阵容已采集", missing: "阵容暂未采集" },
  venue: { ok: "场地已采集", missing: "场地暂未采集" },
  weather: { ok: "天气已采集", missing: "天气暂未采集" },
  referee: { ok: "裁判已采集", missing: "裁判暂未采集" },
  multi_bookmaker_snapshot: { ok: "多公司赔率快照已采集", missing: "缺少多公司赔率快照" },
  core_markets_ready: { ok: "核心盘口已就绪", missing: "核心盘口不足" }
};

const FLAG_LABELS: Record<string, string> = {
  no_hard_blockers: "无硬性阻断",
  lineup_unavailable: "阵容暂未采集",
  lineup_context_limited: "阵容信息有限",
  lineup_context_missing: "阵容信息不足",
  form_context_limited: "近况信息有限",
  low_settled_sample: "结算样本偏少",
  near_kickoff_under_60m: "临近开赛 60 分钟内",
  multi_bookmaker_snapshot_missing: "缺少多公司赔率快照",
  large_handicap_requires_backtest: "大盘口需回测",
  supported_market_missing: "缺少可用盘口",
  core_market_missing: "核心盘口缺失",
  quality_not_bettable: "数据质量不足",
  no_positive_edge: "无正向边际",
  blocking_flags_present: "存在硬阻断",
  asian_handicap_consensus_market_line_split: "亚盘公司盘口分歧",
  asian_handicap_consensus_price_outlier_detected: "亚盘赔率离群",
  asian_handicap_consensus_preferred_not_latest: "亚盘首选盘口不是最新",
  asian_handicap_consensus_preferred_line_differs_from_main: "亚盘首选盘口偏离主线",
  asian_handicap_consensus_latest_line_differs_from_main: "亚盘最新盘口偏离主线",
  asian_handicap_consensus_asian_handicap_complete_market_missing: "亚盘公司数据不完整",
  over_under_consensus_total_line_split: "大小球公司盘口分歧",
  over_under_consensus_price_outlier_detected: "大小球赔率离群",
  over_under_consensus_preferred_not_latest: "大小球首选盘口不是最新",
  over_under_consensus_preferred_line_differs_from_main: "大小球首选盘口偏离主线",
  over_under_consensus_latest_line_differs_from_main: "大小球最新盘口偏离主线",
  over_under_consensus_over_under_complete_market_missing: "大小球公司数据不完整",
  leisu_requires_cookie_or_proxy: "雷速需要登录凭据或代理",
  leisu_access_waf_challenge: "雷速访问受限",
  contains_observe_condition_leg: "包含条件观察项",
  observe_leg_not_allowed: "不允许条件观察项"
};

const ADVICE_REASON_LABELS: Record<string, string> = {
  "balanced threshold passed": "满足均衡阈值",
  balanced_threshold_passed: "满足均衡阈值",
  balanced_observation: "均衡观察",
  balanced: "均衡模式",
  confidence: "高置信模式",
  value: "价值模式"
};

const MARKET_TYPE_ORDER: Record<string, number> = {
  asian_handicap: 1,
  spreads: 1,
  h2h: 2,
  over_under: 3,
  totals: 3
};

const ODDS_TREND_COLORS = [
  "#0f766e",
  "#2563eb",
  "#b45309",
  "#7c3aed",
  "#be123c",
  "#15803d",
  "#475569",
  "#0891b2"
];

export function formatPercent(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "—";
  }
  return `${(value * 100).toFixed(digits)}%`;
}

export function formatOdds(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "—";
  }
  return value.toFixed(2);
}

export function formatSignedPercent(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "—";
  }
  const sign = value > 0 ? "+" : "";
  return `${sign}${formatPercent(value)}`;
}

function formatDecimal(value: number | null | undefined, digits = 4): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "—";
  }
  return value.toFixed(digits);
}

function formatSignedDecimal(value: number | null | undefined, digits = 4): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "—";
  }
  const sign = value > 0 ? "+" : "";
  return `${sign}${formatDecimal(value, digits)}`;
}

export function strategyStatusLabel(strategy: StrategyState): string {
  if (strategy.active) {
    return `实时校准中 ${strategy.sample_count}`;
  }
  return `收集中 ${strategy.sample_count}/${strategy.min_live_sample_count}`;
}

export function reasonLabel(reason: string): string {
  return REASON_LABELS[reason] ?? statusFlagLabel(reason, "未识别原因");
}

function actionLabel(action: unknown): string {
  if (typeof action !== "string" || !action.trim()) return "";
  return ACTION_LABELS[action] ?? "未识别动作";
}

function adviceReasonLabel(reason: unknown): string {
  if (typeof reason !== "string" || !reason.trim()) return "";
  return ADVICE_REASON_LABELS[reason] ?? reasonLabel(reason);
}

function timelineDetailText(detail: unknown): string {
  if (typeof detail !== "string" || !detail.trim()) return "";
  return detail
    .replaceAll("snapshot_reanalysis", "赔率补齐复算")
    .replaceAll("shortlist_value_matches", "推荐筛选")
    .replaceAll("balanced_observation", "均衡观察")
    .replaceAll("collecting_samples", "样本收集中")
    .replaceAll("live_calibration_active", "实时校准已启用")
    .replaceAll("asian_handicap", "亚盘")
    .replaceAll("over_under", "大小球")
    .replaceAll("moneyline_1x2", "胜平负")
    .replaceAll("h2h", "胜平负")
    .replaceAll("no_positive_edge", "无正向边际")
    .replaceAll("multi_bookmaker_snapshot_missing", "缺少多公司赔率快照")
    .replaceAll("awaiting_reanalysis_after_snapshot", "赔率已补齐待复算")
    .replaceAll("samples=", "样本数 ")
    .replaceAll("minP=", "最低概率 ")
    .replaceAll("profit=", "收益 ")
    .replace(/\s+vs\s+/gi, " 对 ")
    .replace(/,\s*/g, "、");
}

function timelineRows<T extends { title: string; detail: string; at_utc: string }>(rows: T[] | undefined): T[] {
  return (rows || []).map((item) => ({
    ...item,
    detail: timelineDetailText(item.detail)
  }));
}

export function marketLabel(market: unknown): string {
  if (typeof market !== "string" || !market.trim()) return "";
  return MARKET_TYPE_LABELS[market] ?? "未知盘口";
}

function stakeLevelLabel(stakeLevel: unknown): string {
  if (typeof stakeLevel !== "string" || !stakeLevel.trim()) return "";
  return STAKE_LEVEL_LABELS[stakeLevel] ?? "未知注码";
}

function dataBlockLabel(block: unknown): string {
  if (typeof block !== "string" || !block.trim()) return "其他数据";
  return DATA_BLOCK_LABELS[block] ?? "其他数据";
}

function stringList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value
    .map((item) => typeof item === "string" ? item.trim() : "")
    .filter(Boolean);
}

function truthyDataValue(value: unknown): boolean {
  if (typeof value === "boolean") return value;
  if (typeof value === "number") return value > 0;
  if (typeof value === "string") {
    return !["false", "missing", "no", "0"].includes(value.trim().toLowerCase());
  }
  return Boolean(value);
}

export function statusFlagLabel(flag: unknown, fallback = "未识别状态"): string {
  if (typeof flag !== "string" || !flag.trim()) return fallback;
  const normalizedFlag = flag.trim().toLowerCase().replace(/[\s-]+/g, "_");
  if (FLAG_LABELS[flag]) return FLAG_LABELS[flag];
  if (FLAG_LABELS[normalizedFlag]) return FLAG_LABELS[normalizedFlag];
  if (normalizedFlag.startsWith("asian_handicap_consensus_")) return `亚盘${statusFlagLabel(normalizedFlag.replace("asian_handicap_consensus_", ""), "市场结构异常")}`;
  if (normalizedFlag.startsWith("over_under_consensus_")) return `大小球${statusFlagLabel(normalizedFlag.replace("over_under_consensus_", ""), "市场结构异常")}`;
  if (normalizedFlag.startsWith("lineup_")) return "阵容信息异常";
  return fallback;
}

function dataFlagLabel(key: string, value: unknown): string {
  if (key === "available_blocks") {
    const labels = stringList(value).map(dataBlockLabel);
    return labels.length ? `已采集：${labels.join("、")}` : "暂无已采集数据块";
  }
  if (key === "missing_blocks") {
    const labels = stringList(value).map(dataBlockLabel);
    return labels.length ? `缺少：${labels.join("、")}` : "关键数据块完整";
  }
  if (key === "ratio") {
    const ratio = numeric(value);
    return `数据完整度 ${formatPercent(ratio)}`;
  }
  if (key === "core_markets_ready") {
    return truthyDataValue(value) ? "核心盘口已就绪" : "核心盘口不足";
  }
  if (BOOLEAN_DATA_LABELS[key]) {
    return truthyDataValue(value) ? BOOLEAN_DATA_LABELS[key].ok : BOOLEAN_DATA_LABELS[key].missing;
  }
  return "数据状态已记录";
}

function pickView(record: DashboardRecord): PickView {
  return {
    ...record,
    matchup: matchupLabel(record.matchup),
    selection: selectionLabel(record.selection, record.market),
    oddsText: formatOdds(record.decimal_odds),
    modelProbabilityText: formatPercent(record.model_probability),
    learnedProbabilityText: formatPercent(record.learned_probability),
    edgeText: formatSignedPercent(record.edge)
  };
}

function kpiCards(snapshot: DashboardSnapshot): KpiCard[] {
  const kpis = snapshot.kpis;
  const predictionKpis = snapshot.prediction_kpis;
  return [
    { label: "预测样本", value: String(predictionKpis?.total_count ?? 0), tone: (predictionKpis?.total_count ?? 0) > 0 ? "good" : "caution" },
    { label: "推荐发布", value: String(predictionKpis?.recommended_count ?? kpis.asian_pick_count), tone: (predictionKpis?.recommended_count ?? kpis.asian_pick_count) > 0 ? "good" : "neutral" },
    { label: "观察样本", value: String(predictionKpis?.observation_count ?? kpis.observation_count), tone: "neutral" },
    { label: "未结算", value: String(predictionKpis?.open_count ?? kpis.open_records), tone: (predictionKpis?.open_count ?? kpis.open_records) > 0 ? "caution" : "neutral" },
    { label: "已回测", value: String(predictionKpis?.settled_count ?? kpis.settled_records), tone: (predictionKpis?.settled_count ?? kpis.settled_records) >= 20 ? "good" : "caution" },
    {
      label: "学习状态",
      value: kpis.live_calibration_active ? "已生效" : `收集 ${kpis.strategy_sample_count}/${snapshot.strategy_state.min_live_sample_count}`,
      tone: kpis.live_calibration_active ? "good" : "caution"
    }
  ];
}

function matchPhaseCards(snapshot: DashboardSnapshot): DashboardView["matchPhaseCards"] {
  const kpis = snapshot.prediction_kpis;
  const total = Math.max(0, Number(kpis?.total_count ?? 0));
  const resultPending = Number(kpis?.result_pending_count ?? 0) + Number(kpis?.maybe_live_count ?? 0);
  const postponed = Number(kpis?.postponed_count ?? 0);
  const phaseRows = [
    {
      key: "live",
      label: "比赛进行中",
      value: Number(kpis?.live_count ?? 0),
      caption: "实时比分已跟踪",
      tone: "good" as const
    },
    {
      key: "scheduled",
      label: "未开赛",
      value: Number(kpis?.scheduled_count ?? 0),
      caption: "等待开赛后刷新",
      tone: "neutral" as const
    },
    {
      key: "final_pending",
      label: "完场待结算",
      value: Number(kpis?.final_pending_count ?? 0),
      caption: "下一轮写入回测",
      tone: Number(kpis?.final_pending_count ?? 0) > 0 ? "caution" as const : "neutral" as const
    },
    ...(postponed > 0 ? [{
      key: "postponed",
      label: "延期/取消",
      value: postponed,
      caption: "不再按正常开赛等待",
      tone: "caution" as const
    }] : []),
    {
      key: "result_pending",
      label: "赛果待确认",
      value: resultPending,
      caption: "源站状态待确认",
      tone: resultPending > 0 ? "caution" as const : "neutral" as const
    },
    {
      key: "settled",
      label: "已回测",
      value: Number(kpis?.settled_count ?? 0),
      caption: "已计入命中/收益",
      tone: Number(kpis?.settled_count ?? 0) > 0 ? "good" as const : "neutral" as const
    }
  ];

  return phaseRows.map((row) => {
    const ratio = total > 0 ? Math.max(0, Math.min(1, row.value / total)) : null;
    return {
      ...row,
      value: String(row.value),
      ratio,
      width: `${Math.max(row.value > 0 ? 8 : 0, (ratio ?? 0) * 100)}%`
    };
  });
}

function filterGroups(groups: CandidateFilter[]): Array<CandidateFilter & { label: string }> {
  return groups.map((group) => ({
    ...group,
    label: reasonLabel(group.reason)
  }));
}

function numeric(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function stringValue(value: unknown, fallback = "—"): string {
  return typeof value === "string" && value.trim() ? value : fallback;
}

function objectValue(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function boolValue(value: unknown): boolean | null {
  if (typeof value === "boolean") return value;
  if (typeof value === "string") {
    const normalized = value.trim().toLowerCase();
    if (["1", "true", "yes", "on"].includes(normalized)) return true;
    if (["0", "false", "no", "off"].includes(normalized)) return false;
  }
  return null;
}

function matchupLabel(value: unknown): string {
  return stringValue(value).replace(/\s+vs\s+/gi, " 对 ");
}

function selectionLabel(selection: unknown, marketType: unknown): string {
  const text = stringValue(selection);
  if (text === "—") return text;
  const market = typeof marketType === "string" ? marketType : "";
  const normalized = text.trim().toLowerCase();
  if (market === "h2h" || market === "moneyline_1x2") {
    if (["draw", "tie", "x"].includes(normalized)) return "平局";
    if (normalized === "home") return "主胜";
    if (normalized === "away") return "客胜";
  }
  if (market === "over_under" || market === "totals") {
    if (["over", "大", "大球"].includes(normalized)) return "大球";
    if (["under", "小", "小球"].includes(normalized)) return "小球";
  }
  return text
    .replace(/\bDraw\b/g, "平局")
    .replace(/\bOver\b/g, "大球")
    .replace(/\bUnder\b/g, "小球")
    .replace(/\s+vs\s+/gi, " 对 ");
}

function dataFlags(data: Record<string, unknown>): string[] {
  const entries = Object.entries(data);
  if (!entries.length) return ["数据状态未知"];
  return entries.map(([key, value]) => dataFlagLabel(key, value));
}

function flagLabels(flags: string[]): string[] {
  return flags.map((flag) => statusFlagLabel(flag)).filter(Boolean);
}

function evidenceDataCompletenessForDetail(detail: DashboardMatchDetail): Record<string, unknown> {
  const raw = detail.evidence.data_completeness || {};
  const normalized = { ...raw };
  if ((detail.odds_snapshot.snapshot_count ?? 0) <= 0) return normalized;

  const availableBlocks = stringList(normalized.available_blocks);
  if (availableBlocks.length) {
    normalized.available_blocks = Array.from(new Set([...availableBlocks, "multi_bookmaker_snapshot"]));
  } else {
    normalized.multi_bookmaker_snapshot = true;
  }

  const missingBlocks = stringList(normalized.missing_blocks);
  if (missingBlocks.length) {
    normalized.missing_blocks = missingBlocks.filter((block) => block !== "multi_bookmaker_snapshot");
  }
  return normalized;
}

function riskFlagsForDetail(detail: DashboardMatchDetail): string[] {
  const flags = [...detail.evidence.risk_flags, ...detail.evidence.caution_flags];
  if ((detail.odds_snapshot.snapshot_count ?? 0) <= 0) return flags;
  return flags.filter((flag) => flag !== "multi_bookmaker_snapshot_missing");
}

function candidateRows(candidates: Array<Record<string, unknown>>): CandidateRow[] {
  return candidates.slice(0, 5).map((candidate) => {
    const probability = numeric(candidate.calibrated_probability ?? candidate.learned_probability ?? candidate.model_probability);
    const selection = stringValue(candidate.selection);
    const movementSignal = stringValue(candidate.market_movement_signal, "");
    const movementText = stringValue(candidate.market_movement_note, "");
    const movementTone: KpiCard["tone"] =
      movementSignal === "against_selection" ? "bad" :
        movementSignal === "supports_selection" ? "good" :
          movementSignal === "stable" ? "neutral" : "caution";
    return {
      selection,
      selectionText: selectionLabel(selection, candidate.market),
      providerText: stringValue(candidate.provider),
      oddsText: formatOdds(numeric(candidate.decimal_odds)),
      probabilityText: formatPercent(probability),
      edgeText: formatSignedPercent(numeric(candidate.edge)),
      movementText,
      movementTone
    };
  });
}

function profitText(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}`;
}

function oddsCoverageText(row: PredictionLedgerRow): string {
  const snapshotCount = row.odds_snapshot_count ?? 0;
  if (!snapshotCount) return "暂无快照";
  const bookmakerCount = row.odds_bookmaker_count ?? 0;
  return bookmakerCount ? `快照 ${snapshotCount} 条 · ${bookmakerCount} 家` : `快照 ${snapshotCount} 条`;
}

function fallbackBacktestEligible(row: PredictionLedgerRow): boolean {
  return ["open", "settled"].includes(row.settlement_status) && row.market !== "parlay";
}

function predictionDiagnosticView(
  row: PredictionLedgerRow,
  evidenceDiagnostic?: DashboardMatchDetail["evidence"]["prediction_diagnostic"]
): MatchDetailView["predictionDiagnostic"] {
  const diagnostic = row.prediction_diagnostic ?? evidenceDiagnostic;
  const title = customerCopy(diagnostic?.actionability_label || row.prediction_type_label || "观察样本");
  const backtestEligible = diagnostic?.backtest_eligible ?? fallbackBacktestEligible(row);
  const learningActive = diagnostic?.learning_active ?? false;
  const learningStatusText = diagnostic?.learning_application_label || (learningActive ? "学习校准已启用" : "样本收集中");
  const reasonText =
    diagnostic?.primary_reason_label ||
    reasonLabel(diagnostic?.primary_reason || row.rejection_reason || row.recommendation);
  const probabilityGap = diagnostic?.threshold_gaps?.probability ?? null;
  const valueEdgeGap = diagnostic?.threshold_gaps?.value_edge ?? null;
  const learnedAdjustment = diagnostic?.learned_adjustment ?? null;
  const minOdds = diagnostic?.thresholds?.min_decimal_odds ?? null;
  const maxOdds = diagnostic?.thresholds?.max_decimal_odds ?? null;
  const summary = diagnostic?.diagnostic_summary
    ? `${title} · ${reasonText}`
    : [title, reasonText].filter(Boolean).join(" · ");
  const tone =
    diagnostic?.recommended || diagnostic?.threshold_passed
      ? "good"
      : backtestEligible
      ? "caution"
      : "neutral";
  return {
    title,
    statusText: `${backtestEligible ? "参与回测" : "暂不回测"} · ${learningStatusText}`,
    reasonText,
    summary,
    learningDetail: diagnostic?.learning_application_detail || "",
    tone,
    passText: diagnostic?.threshold_passed ? "通过阈值" : "未过阈值",
    gapRows: [
      { label: "概率阈值差", value: formatSignedPercent(probabilityGap) },
      { label: "价值边际差", value: formatSignedPercent(valueEdgeGap) },
      { label: "模型校准差", value: formatSignedPercent(learnedAdjustment) },
      { label: "赔率区间", value: `${formatOdds(minOdds)} 至 ${formatOdds(maxOdds)}` }
    ],
    explanationRows: (diagnostic?.feature_explanations || []).map((item) => ({
      label: item.label || "解释项",
      value: item.value || "—",
      detail: item.detail || "",
      tone: toneFromSeverity(item.tone)
    }))
  };
}

function lineText(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value}`;
}

export function predictionStatusLabel(row: PredictionLedgerRow): string {
  if (row.status_label) return row.status_label;
  if (row.settlement_status === "settled") return row.hit ? "命中" : "未命中";
  if (row.settlement_status === "open") return "赛果待确认";
  if (row.settlement_status === "tracked_only") return "仅跟踪";
  if (row.settlement_status === "unsupported_market") return "不支持结算";
  return row.settlement_status || "未知";
}

function predictionRowView(row: PredictionLedgerRow): PredictionLedgerViewRow {
  const diagnostic = predictionDiagnosticView(row);
  const displayProbability = row.governed_probability ?? row.learned_probability ?? row.model_probability;
  const probabilitySource = row.probability_source_label ? ` · ${row.probability_source_label}` : "";
  const scoreText =
    row.score_type === "live" && row.score
      ? `实时 ${row.score}`
      : row.score_type === "final_pending" && row.score
      ? `待结算 ${row.score}`
      : row.score || predictionStatusLabel(row);
  return {
    ...row,
    matchup: matchupLabel(row.matchup),
    selection: selectionLabel(row.selection, row.market),
    statusText: predictionStatusLabel(row),
    oddsText: formatOdds(row.decimal_odds),
    probabilityText: `${formatPercent(displayProbability)}${probabilitySource}`,
    edgeText: formatSignedPercent(row.edge),
    scoreText,
    profitText: profitText(row.profit_units),
    oddsCoverageText: oddsCoverageText(row),
    diagnosticLabel: `${diagnostic.title} · ${diagnostic.statusText.split(" · ")[0]}`,
    diagnosticReasonText: diagnostic.reasonText,
    diagnosticGapText: `概率差 ${diagnostic.gapRows[0].value} · 价值差 ${diagnostic.gapRows[1].value}`
  };
}

function predictionScoreText(row: PredictionLedgerRow): string {
  if (row.score_type === "live" && row.score) return `实时 ${row.score}`;
  if (row.score_type === "final_pending" && row.score) return `待结算 ${row.score}`;
  if (row.true_result?.score) return row.true_result.score;
  if (row.score) return row.score;
  return row.status_label || "赛果待确认";
}

function predictionSummary(snapshot: DashboardSnapshot): string {
  const kpis = snapshot.prediction_kpis;
  if (!kpis) return "暂无预测台账";
  const hasSegmentedSettlements =
    kpis.recommended_settled_count !== undefined &&
    kpis.recommended_hit_count !== undefined &&
    kpis.observation_settled_count !== undefined &&
    kpis.observation_hit_count !== undefined;
  if (hasSegmentedSettlements) {
    const formalSettled = kpis.recommended_settled_count ?? 0;
    const formalHit = kpis.recommended_hit_count ?? 0;
    const observationSettled = kpis.observation_settled_count ?? 0;
    const observationHit = kpis.observation_hit_count ?? 0;
    const parts = [
      `共 ${kpis.total_count} 场`,
      `发布 ${kpis.recommended_count} 场`,
      `观察 ${kpis.observation_count} 场`,
      `已结算 ${kpis.settled_count} 场`
    ];
    if (kpis.open_count > 0) {
      const breakdown = [
        kpis.scheduled_count ? `未开赛 ${kpis.scheduled_count}` : "",
        kpis.maybe_live_count ? `可能进行中 ${kpis.maybe_live_count}` : "",
        kpis.result_pending_count ? `赛果待确认 ${kpis.result_pending_count}` : "",
        kpis.final_pending_count ? `完场待结算 ${kpis.final_pending_count}` : "",
        kpis.postponed_count ? `延期/取消 ${kpis.postponed_count}` : ""
      ].filter(Boolean).join(" / ");
      parts.push(`未结算 ${kpis.open_count} 场${breakdown ? `（${breakdown}）` : ""}`);
    }
    if (formalSettled > 0) parts.push(`发布命中 ${formalHit}/${formalSettled}`);
    if (observationSettled > 0) parts.push(`观察命中 ${observationHit}/${observationSettled}`);
    if (formalSettled === 0 && observationSettled === 0) parts.push("暂无可计算命中率");
    parts.push(`收益率 ${formatSignedPercent(kpis.roi)}`);
    return parts.join(" · ");
  }
  return [
    `共 ${kpis.total_count} 场`,
    `已结算 ${kpis.settled_count} 场`,
    `命中率 ${formatPercent(kpis.hit_rate)}`,
    `收益率 ${formatSignedPercent(kpis.roi)}`
  ].join(" · ");
}

function marketSnapshotProviderRows(snapshot: DashboardSnapshot): MarketSnapshotProviderView[] {
  const summary = snapshot.market_snapshot_summary;
  return (summary?.providers || []).map((provider) => ({
    ...provider,
    providerLabel: PROVIDER_LABELS[provider.provider] ?? provider.provider,
    marketTypesText: (provider.market_types || [])
      .map((item) => marketLabel(item))
      .join("、") || "—"
  }));
}

function marketSnapshotSummary(snapshot: DashboardSnapshot): string {
  const summary = snapshot.market_snapshot_summary;
  if (!summary || !summary.total_snapshot_count) {
    const lastSync = summary?.last_sync;
    if (lastSync?.status === "partial" || lastSync?.status === "error") {
      return "暂无赔率快照 · 雷速抓取受限";
    }
    return "暂无赔率快照";
  }
  return [
    `共 ${summary.total_snapshot_count} 条`,
    `${summary.event_count} 场`,
    `${summary.bookmaker_count} 家公司`
  ].join(" · ");
}

function marketSnapshotEmptyText(snapshot: DashboardSnapshot): string {
  const lastSync = snapshot.market_snapshot_summary?.last_sync;
  if (!lastSync) return "暂无赔率快照。同步雷速或其他赔率源后会显示覆盖情况。";
  if (lastSync.status === "error") {
    return `雷速快照抓取失败：${stringValue(lastSync.error, "未知错误")}`;
  }
  if (lastSync.soft_flags?.includes("leisu_requires_cookie_or_proxy")) {
    return `已探测 ${lastSync.probed_match_count ?? 0} 场，${lastSync.accessible_match_count ?? 0} 场可访问；需要雷速登录凭据或代理。`;
  }
  if ((lastSync.saved_snapshot_count ?? 0) === 0) {
    return `已探测 ${lastSync.probed_match_count ?? 0} 场，暂未生成可入库赔率快照。`;
  }
  return "暂无赔率快照。同步雷速或其他赔率源后会显示覆盖情况。";
}

function toneFromSeverity(status: unknown): AuditHealthCard["tone"] {
  if (status === "good" || status === "caution" || status === "bad" || status === "neutral") return status;
  if (status === "ok") return "good";
  if (status === "warning") return "caution";
  if (status === "blocked") return "bad";
  if (status === "error") return "bad";
  return "neutral";
}

function statusText(status: unknown): string {
  if (status === "ok") return "通过";
  if (status === "info") return "观察";
  if (status === "warning") return "注意";
  if (status === "blocked") return "阻断";
  if (status === "error" || status === "missing") return "异常";
  return "待确认";
}

function clampedRatio(value: unknown): number | null {
  const parsed = numeric(value);
  if (parsed === null) return null;
  return Math.max(0, Math.min(1, parsed));
}

function metricProgressText(current: unknown, target: unknown): string {
  const currentValue = numeric(current);
  const targetValue = numeric(target);
  if (currentValue === null) return "—";
  if (targetValue === null || targetValue <= 0) return String(currentValue);
  return `${currentValue}/${targetValue}`;
}

function fallbackDecisionAudit(snapshot: DashboardSnapshot): DashboardDecisionAudit {
  const kpis = snapshot.prediction_kpis;
  const strategy = snapshot.strategy_state;
  const coveredCount = (snapshot.prediction_ledger || []).filter((row) => row.has_odds_snapshot || (row.odds_snapshot_count ?? 0) > 0).length;
  const ledgerCount = snapshot.prediction_ledger?.length || 0;
  const topReasons = (snapshot.candidate_filters || []).map((group) => ({
    reason: group.reason,
    count: group.count
  }));
  const hasRecommendation = (kpis?.recommended_count ?? 0) > 0;
  const learningActive = Boolean(strategy?.active);
  const minSamples = Number(strategy?.min_live_sample_count ?? 20);
  const sampleCount = Number(strategy?.sample_count ?? 0);
  const settledCount = Number(kpis?.settled_count ?? 0);
  const recommendationTitle = hasRecommendation ? "已有推荐发布" : (kpis?.observation_count ?? 0) > 0 ? "当前无可发布推荐" : "暂无预测样本";
  const learningTitle = learningActive ? "学习校准已生效" : settledCount === 0 ? "学习尚未生效" : "学习样本收集中";
  const oddsRatio = ledgerCount ? coveredCount / ledgerCount : null;

  return {
    generated_at_utc: snapshot.generated_at_utc,
    prediction: {
      status: kpis?.total_count ? "ok" : "warning",
      title: kpis?.total_count ? "预测样本已入库" : "暂无预测样本",
      detail: kpis?.total_count
        ? `已形成 ${kpis.total_count} 条预测样本，其中推荐发布 ${kpis.recommended_count} 条、观察样本 ${kpis.observation_count} 条；所有可结算样本都会进入回测。`
        : "自动学习循环还没有形成可回测预测，无法验证准确率。",
      total_count: kpis?.total_count ?? 0,
      evaluation_count: kpis?.total_count ?? 0,
      recommended_count: kpis?.recommended_count ?? 0,
      observation_count: kpis?.observation_count ?? 0,
      open_count: kpis?.open_count ?? 0,
      settled_count: settledCount
    },
    recommendation: {
      status: hasRecommendation ? "ok" : (kpis?.observation_count ?? 0) > 0 ? "warning" : "info",
      title: recommendationTitle,
      detail: hasRecommendation
        ? `推荐发布 ${kpis.recommended_count} 场，观察样本 ${kpis.observation_count} 场。`
        : `${kpis?.observation_count ?? 0} 场进入观察样本，主要原因：${topReasons[0] ? reasonLabel(topReasons[0].reason) : "样本不足"}。`,
      recommended_count: kpis?.recommended_count ?? 0,
      observation_count: kpis?.observation_count ?? 0,
      open_count: kpis?.open_count ?? 0,
      top_rejection_reasons: topReasons
    },
    learning: {
      status: learningActive ? "ok" : settledCount === 0 ? "warning" : "info",
      title: learningTitle,
      detail: learningActive
        ? `已结算 ${settledCount} 场，实时校准正在参与概率调整。`
        : settledCount === 0
          ? "还没有已结算样本，模型不会根据命中结果调整概率。"
          : `已结算 ${settledCount} 场，达到 ${minSamples} 场后才启用实时校准。`,
      active: learningActive,
      sample_count: sampleCount,
      min_sample_count: minSamples,
      settled_count: settledCount,
      hit_rate: kpis?.hit_rate ?? null,
      roi: kpis?.roi ?? null
    },
    settlement: {
      status: settledCount > 0 ? "info" : (kpis?.open_count ?? 0) > 0 ? "warning" : "info",
      title: settledCount > 0 ? "部分样本已结算" : "等待首批赛果",
      detail: settledCount > 0
        ? `已结算 ${settledCount} 场，未结算 ${kpis?.open_count ?? 0} 场。`
        : `${kpis?.open_count ?? 0} 场仍未结算。`,
      open_count: kpis?.open_count ?? 0,
      settled_count: settledCount,
      hit_count: kpis?.hit_count ?? 0,
      miss_count: kpis?.miss_count ?? 0
    },
    odds: {
      status: coveredCount > 0 ? "info" : "warning",
      title: coveredCount > 0 ? "部分赔率已覆盖" : "赔率覆盖不足",
      detail: `台账 ${coveredCount}/${ledgerCount} 场有赔率快照，共 ${snapshot.market_snapshot_summary?.total_snapshot_count ?? 0} 条。`,
      covered_count: coveredCount,
      ledger_count: ledgerCount,
      coverage_ratio: oddsRatio === null ? null : Number(oddsRatio.toFixed(6)),
      snapshot_count: snapshot.market_snapshot_summary?.total_snapshot_count ?? 0,
      bookmaker_count: snapshot.market_snapshot_summary?.bookmaker_count ?? 0
    },
    health_items: []
  };
}

function decisionAudit(snapshot: DashboardSnapshot): DashboardDecisionAudit {
  const audit = snapshot.decision_audit || fallbackDecisionAudit(snapshot);
  if (audit.health_items?.length) return audit;
  return {
    ...audit,
    health_items: [
      {
        key: "prediction",
        label: "预测",
        status: audit.prediction.status,
        title: audit.prediction.title,
        detail: audit.prediction.detail,
        current: audit.prediction.total_count,
        target: null,
        ratio: audit.prediction.total_count > 0 ? 1 : 0
      },
      {
        key: "recommendation",
        label: "推荐",
        status: audit.recommendation.status,
        title: audit.recommendation.title,
        detail: audit.recommendation.detail,
        current: audit.recommendation.recommended_count,
        target: 1,
        ratio: audit.recommendation.recommended_count > 0 ? 1 : 0
      },
      {
        key: "learning",
        label: "学习",
        status: audit.learning.status,
        title: audit.learning.title,
        detail: audit.learning.detail,
        current: audit.learning.sample_count,
        target: audit.learning.min_sample_count,
        ratio: audit.learning.min_sample_count ? audit.learning.sample_count / audit.learning.min_sample_count : null
      },
      {
        key: "settlement",
        label: "结算",
        status: audit.settlement.status,
        title: audit.settlement.title,
        detail: audit.settlement.detail,
        current: audit.settlement.settled_count,
        target: audit.settlement.open_count + audit.settlement.settled_count,
        ratio: (audit.settlement.open_count + audit.settlement.settled_count) > 0
          ? audit.settlement.settled_count / (audit.settlement.open_count + audit.settlement.settled_count)
          : null
      },
      {
        key: "odds",
        label: "赔率",
        status: audit.odds.status,
        title: audit.odds.title,
        detail: audit.odds.detail,
        current: audit.odds.covered_count,
        target: audit.odds.ledger_count,
        ratio: audit.odds.coverage_ratio
      }
    ]
  };
}

function auditHealthCard(item: DashboardDecisionAudit["health_items"][number]): AuditHealthCard {
  const progressValue = clampedRatio(item.ratio);
  return {
    key: item.key,
    label: customerCopy(item.label),
    status: item.status,
    tone: toneFromSeverity(item.status),
    title: customerCopy(item.title),
    detail: customerCopy(item.detail),
    metricText: metricProgressText(item.current, item.target),
    progressText: metricProgressText(item.current, item.target),
    progressValue
  };
}

function auditHealthCards(snapshot: DashboardSnapshot): AuditHealthCard[] {
  return decisionAudit(snapshot).health_items.map(auditHealthCard);
}

function auditBlock(
  status: { status: DashboardDecisionAudit["learning"]["status"]; title: string; detail: string },
  progressCurrent: unknown,
  progressTarget: unknown
): AuditBlockView {
  const target = numeric(progressTarget);
  const current = numeric(progressCurrent);
  return {
    status: status.status,
    tone: toneFromSeverity(status.status),
    title: customerCopy(status.title),
    detail: customerCopy(status.detail),
    progressText: metricProgressText(current, target),
    progressValue: target && current !== null ? clampedRatio(current / target) : null
  };
}

function recommendationFunnel(snapshot: DashboardSnapshot): RecommendationFunnelView[] {
  const audit = decisionAudit(snapshot);
  const reasons = audit.recommendation.top_rejection_reasons.length
    ? audit.recommendation.top_rejection_reasons
    : (snapshot.candidate_filters || []).map((group) => ({ reason: group.reason, count: group.count }));
  const maxCount = Math.max(1, ...reasons.map((item) => item.count || 0));
  return reasons.slice(0, 6).map((item) => {
    const ratio = Math.max(0, Math.min(1, (item.count || 0) / maxCount));
    return {
      reason: item.reason,
      label: reasonLabel(item.reason),
      count: item.count || 0,
      countText: `${item.count || 0} 场`,
      ratio,
      width: `${Math.max(6, ratio * 100)}%`
    };
  });
}

function fallbackLearningDiagnostics(snapshot: DashboardSnapshot): DashboardLearningDiagnostics {
  const audit = decisionAudit(snapshot);
  const learning = audit.learning;
  const odds = audit.odds;
  const prediction = audit.prediction;
  const recommendation = audit.recommendation;
  const remaining = Math.max((learning.min_sample_count || 0) - (learning.sample_count || 0), 0);
  return {
    status: learning.active ? "live_calibrating" : prediction.settled_count > 0 ? "collecting_backtest_samples" : "waiting_results",
    severity: learning.status,
    title: learning.title,
    detail: learning.detail,
    prediction_total: prediction.total_count,
    formal_count: recommendation.recommended_count,
    observation_count: recommendation.observation_count,
    open_count: prediction.open_count,
    settled_count: prediction.settled_count,
    hit_count: audit.settlement.hit_count,
    miss_count: audit.settlement.miss_count,
    backtested_count: prediction.settled_count,
    waiting_result_count: prediction.open_count,
    ready_for_backtest_count: prediction.total_count,
    sample_count: learning.sample_count,
    settled_sample_target: learning.min_sample_count,
    remaining_to_live_calibration: remaining,
    live_calibration_active: learning.active,
    odds_covered_count: odds.covered_count,
    odds_ledger_count: odds.ledger_count,
    odds_coverage_ratio: odds.coverage_ratio,
    snapshot_count: odds.snapshot_count,
    bookmaker_count: odds.bookmaker_count,
    reanalysis_backlog_count: recommendation.top_rejection_reasons
      .filter((item) => item.reason === "awaiting_reanalysis_after_snapshot")
      .reduce((total, item) => total + (item.count || 0), 0),
    hit_rate: learning.hit_rate,
    roi: learning.roi,
    readiness_items: audit.health_items,
    top_blockers: recommendation.top_rejection_reasons
  };
}

function diagnosticBlockers(items: DashboardLearningDiagnostics["top_blockers"]): RecommendationFunnelView[] {
  const maxCount = Math.max(1, ...items.map((item) => item.count || 0));
  return items.slice(0, 5).map((item) => {
    const ratio = Math.max(0, Math.min(1, (item.count || 0) / maxCount));
    return {
      reason: item.reason,
      label: reasonLabel(item.reason),
      count: item.count || 0,
      countText: `${item.count || 0} 场`,
      ratio,
      width: `${Math.max(6, ratio * 100)}%`
    };
  });
}

function learningDiagnosticsView(snapshot: DashboardSnapshot): DashboardView["learningDiagnostics"] {
  const diagnostics = snapshot.learning_diagnostics || fallbackLearningDiagnostics(snapshot);
  return {
    severity: diagnostics.severity,
    tone: toneFromSeverity(diagnostics.severity),
    title: customerCopy(diagnostics.title),
    detail: customerCopy(diagnostics.detail),
    metrics: [
      {
        label: "可回测样本",
        value: String(diagnostics.ready_for_backtest_count),
        caption: `发布 ${diagnostics.formal_count} · 观察 ${diagnostics.observation_count}`,
        tone: diagnostics.ready_for_backtest_count > 0 ? "good" : "caution"
      },
      {
        label: "已回测",
        value: `${diagnostics.backtested_count}/${diagnostics.settled_sample_target}`,
        caption: diagnostics.live_calibration_active ? "实时校准已启用" : `还差 ${diagnostics.remaining_to_live_calibration} 场启用校准`,
        tone: diagnostics.live_calibration_active ? "good" : diagnostics.backtested_count > 0 ? "neutral" : "caution"
      },
      {
        label: "未结算",
        value: String(diagnostics.waiting_result_count),
        caption: "赛果写入后自动结算命中和收益",
        tone: diagnostics.waiting_result_count > 0 ? "neutral" : "good"
      },
      {
        label: "赔率覆盖",
        value: `${diagnostics.odds_covered_count}/${diagnostics.odds_ledger_count}`,
        caption: `${diagnostics.snapshot_count} 条 · ${diagnostics.bookmaker_count} 家公司`,
        tone: toneFromSeverity(diagnostics.odds_ledger_count && diagnostics.odds_covered_count === diagnostics.odds_ledger_count ? "ok" : diagnostics.odds_covered_count > 0 ? "info" : "warning")
      },
      {
        label: "待复算",
        value: String(diagnostics.reanalysis_backlog_count),
        caption: diagnostics.reanalysis_backlog_count ? "赔率补齐后等待下一轮分析" : "当前无需复算",
        tone: diagnostics.reanalysis_backlog_count ? "caution" : "good"
      }
    ],
    readinessItems: (diagnostics.readiness_items || []).map(auditHealthCard),
    blockerRows: diagnosticBlockers(diagnostics.top_blockers || [])
  };
}

function yesNo(value: boolean): string {
  return value ? "是" : "否";
}

function learningEffectivenessView(snapshot: DashboardSnapshot): DashboardView["learningEffectiveness"] {
  const effectiveness = snapshot.learning_effectiveness;
  if (!effectiveness) {
    return {
      severity: "warning",
      tone: "caution",
      title: "等待模型质量样本",
      detail: "暂无已结算概率样本，暂时无法比较学习后概率、原始模型和市场隐含概率。",
      metricRule: "Brier 分数越低越好；校准误差越低越好。",
      metrics: [
        { label: "学习后 Brier", value: "—", caption: "等待结算样本", tone: "caution" },
        { label: "原始模型 Brier", value: "—", caption: "等待结算样本", tone: "neutral" },
        { label: "市场 Brier", value: "—", caption: "等待赔率样本", tone: "neutral" },
        { label: "相对模型", value: "—", caption: "负数代表学习后更好", tone: "neutral" }
      ],
      summaryRows: [
        { label: "样本数", value: "0" },
        { label: "是否优于原始模型", value: "否" },
        { label: "是否优于市场", value: "否" },
        { label: "校准误差变化", value: "—" }
      ],
      deploymentVerdict: deploymentVerdictView(undefined),
      bandRows: []
    };
  }

  const deltaModel = effectiveness.deltas?.learned_brier_minus_model ?? null;
  const deltaMarket = effectiveness.deltas?.learned_brier_minus_market ?? null;
  const calibrationDelta = effectiveness.deltas?.learned_calibration_error_minus_model ?? null;
  const bandRows = (effectiveness.probability_bands || []).map((band) => {
    const sampleCount = band.sample_count ?? 0;
    const hitRate = band.hit_rate ?? null;
    const avgProbability = band.avg_probability ?? null;
    const roi = band.roi ?? null;
    const calibrationError = band.calibration_error ?? null;
    const tone: KpiCard["tone"] =
      sampleCount === 0
        ? "neutral"
        : roi !== null && roi > 0 && calibrationError !== null && calibrationError <= 0.1
          ? "good"
          : roi !== null && roi < 0
            ? "caution"
            : "neutral";
    return {
      key: band.key,
      label: customerCopy(band.label || "概率段"),
      sampleText: `${sampleCount} 场`,
      hitRateText: formatPercent(hitRate),
      avgProbabilityText: formatPercent(avgProbability),
      roiText: formatSignedPercent(roi),
      calibrationText: calibrationError === null ? "—" : formatPercent(calibrationError),
      qualityText: band.sample_quality === "enough_sample" ? "样本较充分" : "样本偏少",
      hitWidth: `${Math.max(0, Math.min(100, (hitRate ?? 0) * 100)).toFixed(1)}%`,
      probabilityWidth: `${Math.max(0, Math.min(100, (avgProbability ?? 0) * 100)).toFixed(1)}%`,
      tone
    };
  });
  return {
    severity: effectiveness.severity,
    tone: toneFromSeverity(effectiveness.severity),
    title: customerCopy(effectiveness.title),
    detail: customerCopy(effectiveness.detail),
    metricRule: customerCopy(effectiveness.metric_rule || "Brier 分数越低越好；校准误差越低越好。"),
    calibrationHealth: calibrationHealthView(effectiveness.calibration_health),
    shadowRecalibration: shadowRecalibrationView(effectiveness.shadow_recalibration),
    probabilityGovernance: probabilityGovernanceView(effectiveness.probability_governance),
    metrics: [
      {
        label: "学习后 Brier",
        value: formatDecimal(effectiveness.learned?.brier_score),
        caption: "学习校准后的概率误差",
        tone: effectiveness.learning_improved ? "good" : "caution"
      },
      {
        label: "原始模型 Brier",
        value: formatDecimal(effectiveness.model?.brier_score),
        caption: "未学习前的模型误差",
        tone: "neutral"
      },
      {
        label: "市场 Brier",
        value: formatDecimal(effectiveness.market?.brier_score),
        caption: "赔率隐含概率误差",
        tone: effectiveness.beats_market ? "good" : "neutral"
      },
      {
        label: "相对模型",
        value: formatSignedDecimal(deltaModel),
        caption: "负数代表学习后更好",
        tone: deltaModel !== null && deltaModel < 0 ? "good" : deltaModel !== null && deltaModel > 0 ? "caution" : "neutral"
      }
    ],
    summaryRows: [
      { label: "样本数", value: String(effectiveness.sample_count ?? 0) },
      { label: "是否优于原始模型", value: yesNo(Boolean(effectiveness.learning_improved)) },
      { label: "是否优于市场", value: yesNo(Boolean(effectiveness.beats_market)) },
      { label: "相对市场", value: formatSignedDecimal(deltaMarket) },
      { label: "校准误差变化", value: formatSignedDecimal(calibrationDelta) }
    ],
    deploymentVerdict: deploymentVerdictView(effectiveness),
    bandRows
  };
}

function modelGovernanceView(snapshot: DashboardSnapshot): DashboardView["modelGovernance"] {
  const governance = snapshot.model_governance;
  if (!governance) {
    return {
      severity: "warning",
      tone: "caution",
      title: "等待专业模型审计",
      detail: "后端尚未返回模型治理摘要，暂时只能查看基础模型质量和回测走势。",
      methodText: "方法待确认",
      ruleText: "模型审计只读取已入库样本、结算指标和赔率快照。",
      metrics: [
        { label: "模型证据", value: "0", caption: "等待 model_engine 入库", tone: "caution" },
        { label: "历史 rho", value: "0/0", caption: "等待历史联赛样本", tone: "neutral" },
        { label: "校准样本", value: "0", caption: "等待结算样本", tone: "neutral" },
        { label: "平均 CLV", value: "—", caption: "等待收盘价", tone: "neutral" }
      ],
      checkRows: []
    };
  }
  const summary = governance.summary;
  const methodText = Object.entries(governance.method_counts || {})
    .sort((left, right) => right[1] - left[1])
    .slice(0, 2)
    .map(([method, count]) => `${method}:${count}`)
    .join(" · ") || "方法待确认";
  return {
    severity: governance.severity,
    tone: toneFromSeverity(governance.severity),
    title: customerCopy(governance.title),
    detail: customerCopy(governance.detail),
    methodText,
    ruleText: customerCopy(governance.rule || "模型审计只读取已入库样本、结算指标和赔率快照。"),
    metrics: [
      {
        label: "模型证据",
        value: `${summary.model_engine_count}/${summary.record_count}`,
        caption: `${summary.model_available_count} 条可审计`,
        tone: summary.model_engine_count > 0 ? "good" : "caution"
      },
      {
        label: "历史 rho",
        value: `${summary.historical_rho_count}/${summary.model_engine_count}`,
        caption: `平均 ${formatSignedDecimal(governance.rho?.historical_avg_rho)}`,
        tone: summary.historical_rho_count > 0 ? "good" : "caution"
      },
      {
        label: "校准样本",
        value: String(summary.calibration_sample_count ?? 0),
        caption: `${governance.calibration?.learning_improved ? "优于原模型" : "待证明"} · ${governance.calibration?.beats_market ? "跑赢市场" : "未跑赢市场"}`,
        tone: governance.calibration?.learning_improved && governance.calibration?.beats_market ? "good" : summary.calibration_sample_count > 0 ? "caution" : "neutral"
      },
      {
        label: "平均 CLV",
        value: formatSignedPercent(summary.avg_clv_return),
        caption: `正 CLV ${formatPercent(summary.positive_clv_rate)}`,
        tone: summary.avg_clv_return !== null && summary.avg_clv_return > 0 ? "good" : summary.avg_clv_return !== null && summary.avg_clv_return < 0 ? "bad" : "neutral"
      }
    ],
    checkRows: (governance.checks || []).map((check) => {
      const ratio = clampedRatio(check.ratio);
      return {
        key: check.key,
        label: customerCopy(check.label),
        title: customerCopy(check.title),
        detail: customerCopy(check.detail),
        statusText: statusText(check.status),
        progressText: check.key === "clv_tracking" ? `${check.current ?? 0}/${check.target ?? 0}` : metricProgressText(check.current, check.target),
        width: `${Math.max(4, Math.min(100, (ratio ?? 0) * 100))}%`,
        tone: toneFromSeverity(check.status)
      };
    })
  };
}

function clvTrackingView(snapshot: DashboardSnapshot): DashboardView["clvTracking"] {
  const tracking = snapshot.clv_tracking;
  if (!tracking) {
    return {
      severity: "warning",
      tone: "caution",
      title: "等待 CLV 追踪",
      detail: "后端尚未返回收盘价价值追踪，暂时无法比较推荐价和收盘价。",
      ruleText: "CLV 只读取持久化赔率快照。",
      metrics: [
        { label: "可计算", value: "0/0", caption: "等待收盘价", tone: "neutral" },
        { label: "正 CLV", value: "—", caption: "暂无样本", tone: "neutral" },
        { label: "平均 CLV", value: "—", caption: "暂无样本", tone: "neutral" },
        { label: "跳过", value: "0", caption: "缺少赔率或队名", tone: "neutral" }
      ],
      recordRows: []
    };
  }
  const severity: DashboardView["clvTracking"]["severity"] =
    tracking.available_count > 0 ? "ok" : tracking.tracked_count > 0 ? "warning" : "missing";
  const positiveRate = tracking.positive_clv_rate;
  const avgClv = tracking.avg_clv_return;
  return {
    severity,
    tone: toneFromSeverity(severity),
    title: tracking.available_count > 0 ? "CLV 收盘价追踪" : "等待收盘价对齐",
    detail: `${tracking.available_count}/${tracking.tracked_count} 条样本可计算收盘价价值；正 CLV ${formatPercent(positiveRate)}，平均 CLV ${formatSignedPercent(avgClv)}。`,
    ruleText: tracking.rule || "CLV 只读取持久化赔率快照。",
    metrics: [
      {
        label: "可计算",
        value: `${tracking.available_count}/${tracking.tracked_count}`,
        caption: `${tracking.record_count} 条进入检查`,
        tone: tracking.available_count > 0 ? "good" : "caution"
      },
      {
        label: "正 CLV",
        value: formatPercent(positiveRate),
        caption: `${tracking.positive_clv_count} 条优于收盘价`,
        tone: positiveRate !== null && positiveRate >= 0.5 ? "good" : positiveRate !== null ? "caution" : "neutral"
      },
      {
        label: "平均 CLV",
        value: formatSignedPercent(avgClv),
        caption: "推荐价相对收盘价",
        tone: avgClv !== null && avgClv > 0 ? "good" : avgClv !== null && avgClv < 0 ? "bad" : "neutral"
      },
      {
        label: "跳过",
        value: String(tracking.skipped_count ?? 0),
        caption: "缺少队名或记录赔率",
        tone: tracking.skipped_count > 0 ? "caution" : "good"
      }
    ],
    recordRows: (tracking.records || []).slice(0, 8).map((record) => {
      const clv = record.clv || { status: "unavailable" };
      const clvReturn = clv.clv_return ?? null;
      const tone: KpiCard["tone"] = clv.status !== "available"
        ? "neutral"
        : clvReturn !== null && clvReturn > 0
          ? "good"
          : clvReturn !== null && clvReturn < 0
            ? "bad"
            : "neutral";
      return {
        id: String(record.record_id ?? record.record_key ?? `${record.home_team}-${record.away_team}-${record.selection}`),
        matchup: `${record.home_team || "主队"} 对 ${record.away_team || "客队"}`,
        marketText: marketLabel(record.market),
        selectionText: record.selection || record.selection_key || "—",
        priceText: clv.status === "available"
          ? `${formatOdds(clv.prediction_decimal_odds)} → ${formatOdds(clv.closing_decimal_odds)}`
          : reasonLabel(clv.reason || clv.status || "unavailable"),
        clvText: clv.status === "available" ? formatSignedPercent(clvReturn) : "—",
        timeText: clv.latest_closing_snapshot_utc || "等待快照",
        tone
      };
    })
  };
}

function streakText(type: unknown, count: unknown): string {
  const countText = formatDecimal(numeric(count), 0);
  if (type === "hit") return `命中 ${countText}`;
  if (type === "miss") return `未命中 ${countText}`;
  return "暂无";
}

function backtestCurveView(snapshot: DashboardSnapshot): DashboardView["backtestCurve"] {
  const curve = snapshot.backtest_curve;
  if (!curve) {
    return {
      severity: "warning",
      tone: "caution",
      title: "等待回测走势",
      detail: "后端尚未返回累计收益走势，暂时只能查看总体 ROI。",
      metrics: [
        { label: "累计收益", value: "—", caption: "等待结算", tone: "neutral" },
        { label: "最大回撤", value: "—", caption: "等待结算", tone: "neutral" },
        { label: "滚动命中", value: "—", caption: "等待结算", tone: "neutral" },
        { label: "当前连段", value: "暂无", caption: "等待结算", tone: "neutral" }
      ],
      points: [],
      polyline: "",
      zeroLineY: 50
    };
  }
  const summary = curve.summary;
  const points = curve.points || [];
  const cumulativeValues = points
    .map((point) => numeric(point.cumulative_profit))
    .filter((value): value is number => value !== null);
  const minValue = Math.min(0, ...cumulativeValues);
  const maxValue = Math.max(0, ...cumulativeValues);
  const range = Math.max(0.01, maxValue - minValue);
  const xStep = points.length > 1 ? 100 / (points.length - 1) : 0;
  const chartPoints = points.map((point, index) => {
    const cumulative = numeric(point.cumulative_profit) ?? 0;
    const x = points.length > 1 ? index * xStep : 50;
    const y = 100 - ((cumulative - minValue) / range) * 100;
    return {
      index: point.index,
      matchup: point.matchup || "比赛",
      typeText: point.prediction_type_label || "预测",
      resultText: point.hit ? "命中" : "未命中",
      cumulativeValue: Number(cumulative.toFixed(4)),
      cumulativeText: formatSignedDecimal(point.cumulative_profit, 2),
      drawdownText: formatSignedDecimal(point.drawdown_units, 2),
      rollingHitText: formatPercent(point.rolling_hit_rate),
      profitValue: numeric(point.profit_units) ?? 0,
      profitText: formatSignedDecimal(point.profit_units, 2),
      x: Number(x.toFixed(2)),
      y: Number(y.toFixed(2)),
      tone: point.hit ? "good" : "caution" as KpiCard["tone"]
    };
  });
  const latestPoint = points[points.length - 1];
  const latestRollingHit = latestPoint ? latestPoint.rolling_hit_rate : null;
  const zeroLineY = 100 - ((0 - minValue) / range) * 100;
  return {
    severity: curve.severity,
    tone: toneFromSeverity(curve.severity),
    title: curve.title || "回测走势",
    detail: curve.detail || "",
    metrics: [
      {
        label: "累计收益",
        value: formatSignedDecimal(summary.profit_units, 2),
        caption: `${summary.settled_count ?? 0} 场已结算`,
        tone: (summary.profit_units ?? 0) > 0 ? "good" : (summary.profit_units ?? 0) < 0 ? "caution" : "neutral"
      },
      {
        label: "最大回撤",
        value: formatSignedDecimal(summary.max_drawdown_units, 2),
        caption: "从历史峰值回落",
        tone: (summary.max_drawdown_units ?? 0) < 0 ? "caution" : "good"
      },
      {
        label: "滚动命中",
        value: formatPercent(latestRollingHit),
        caption: `最近 ${summary.rolling_window ?? 10} 场`,
        tone: latestRollingHit !== null && latestRollingHit >= 0.5 ? "good" : "caution"
      },
      {
        label: "当前连段",
        value: streakText(summary.current_streak_type, summary.current_streak_count),
        caption: `最长连黑 ${summary.longest_loss_streak ?? 0}`,
        tone: summary.current_streak_type === "hit" ? "good" : summary.current_streak_type === "miss" ? "caution" : "neutral"
      }
    ],
    points: chartPoints,
    polyline: chartPoints.map((point) => `${point.x},${point.y}`).join(" "),
    zeroLineY: Number(zeroLineY.toFixed(2))
  };
}

function qualitySegmentTone(tone: unknown, roi: number | null): KpiCard["tone"] {
  if (tone === "positive" || (roi !== null && roi > 0)) return "good";
  if (tone === "negative" || (roi !== null && roi < 0)) return "caution";
  return "neutral";
}

function sampleQualityText(value: unknown): string {
  if (value === "enough_sample") return "样本较充分";
  if (value === "thin_sample") return "样本偏少";
  return "样本状态待确认";
}

function probabilityBandLabel(key: unknown): string {
  const labels: Record<string, string> = {
    under_45: "低于 45%",
    between_45_55: "45% - 55%",
    between_55_65: "55% - 65%",
    over_65: "65% 以上"
  };
  if (typeof key !== "string" || !key.trim()) return "未分桶";
  return labels[key] ?? "概率分桶";
}

function calibrationActionText(action: unknown): string {
  const labels: Record<string, string> = {
    collect_more_samples: "继续采样",
    continue_band_backtest: "继续分桶回测",
    freeze_formal_recommendations_and_run_band_recalibration: "暂停推荐发布并优化分桶"
  };
  if (typeof action !== "string" || !action.trim()) return "继续观察校准";
  return labels[action] ?? "继续观察校准";
}

function metaModelText(metaModel: unknown): string {
  const meta = typeof metaModel === "object" && metaModel ? metaModel as Record<string, unknown> : {};
  const name = meta.name === "probability_band_reliability" ? "概率分桶可靠性" : "轻量分桶模型";
  const minSamples = numeric(meta.min_band_sample_count);
  return minSamples === null ? name : `${name} · 最小分桶 ${formatDecimal(minSamples, 0)} 场`;
}

function candidateBandsText(keys: unknown): string {
  const labels = stringList(keys).map((key) => probabilityBandLabel(key));
  return labels.length ? `反向观察分桶：${labels.join("、")}` : "暂无反向观察分桶";
}

function calibrationHealthView(
  health: NonNullable<DashboardSnapshot["learning_effectiveness"]>["calibration_health"] | undefined
): DashboardView["learningEffectiveness"]["calibrationHealth"] {
  if (!health) return undefined;
  return {
    title: customerCopy(health.title || "校准健康"),
    detail: customerCopy(health.detail || "等待后端返回校准健康说明。"),
    actionText: calibrationActionText(health.recommended_action),
    modelText: metaModelText(health.meta_model),
    candidateBandsText: candidateBandsText(health.candidate_band_keys),
    tone: toneFromSeverity(health.severity)
  };
}

function recalibrationMethodText(method: unknown): string {
  if (method === "beta_binomial_probability_band_recalibrator_v1") return "贝塔-二项分桶后验";
  return "轻量重校准模型";
}

function shadowRecalibrationView(
  shadow: NonNullable<DashboardSnapshot["learning_effectiveness"]>["shadow_recalibration"] | undefined
): DashboardView["learningEffectiveness"]["shadowRecalibration"] {
  if (!shadow) return undefined;
  const quality = shadow.quality || {
    sample_count: 0,
    learned_brier_score: null,
    recalibrated_brier_score: null,
    brier_delta: null
  };
  const validation = shadow.validation || {
    sample_count: 0,
    hit_rate: null,
    roi: null
  };
  return {
    title: customerCopy(shadow.title || "影子重校准模型"),
    detail: customerCopy(shadow.detail || "该模型只进入持续验证，不会直接开放推荐发布。"),
    methodText: recalibrationMethodText(shadow.method),
    brierText: `${formatDecimal(quality.learned_brier_score)} -> ${formatDecimal(quality.recalibrated_brier_score)}`,
    brierDeltaText: formatSignedDecimal(quality.brier_delta),
    walkForwardText: `走步验证 ${quality.walk_forward_sample_count ?? 0} 场 · Brier ${formatDecimal(quality.walk_forward_recalibrated_brier_score)} · 变化 ${formatSignedDecimal(quality.walk_forward_brier_delta)}`,
    validationText: `${validation.sample_count ?? 0} 场 · 命中 ${formatPercent(validation.hit_rate)} · 收益 ${formatSignedPercent(validation.roi)}`,
    selectedBandsText: candidateBandsText(shadow.selected_band_keys).replace("反向观察分桶", "验证分桶"),
    tone: toneFromSeverity(shadow.severity)
  };
}

function governancePolicyText(value: unknown): string {
  const labels: Record<string, string> = {
    market_guardrail: "市场保护",
    shadow_walk_forward_guardrail: "走步保护",
    learned_gate: "学习门槛",
    conservative_watch: "保守观察",
    collecting_samples: "样本收集"
  };
  return labels[String(value || "")] || "保守观察";
}

function governanceThresholdText(value: unknown): string {
  if (value === "governed_probability") return "门槛概率：治理后概率";
  return "门槛概率：学习后概率";
}

function probabilityGovernanceView(
  governance: NonNullable<DashboardSnapshot["learning_effectiveness"]>["probability_governance"] | undefined
): DashboardView["learningEffectiveness"]["probabilityGovernance"] {
  if (!governance) return undefined;
  return {
    title: customerCopy(governance.title || "概率治理"),
    detail: customerCopy(governance.detail || "后端正在比较学习概率、原始模型和市场基准。"),
    activeText: `当前使用：${governance.active_source_label || "治理后概率"}`,
    policyText: governancePolicyText(governance.policy_mode),
    thresholdText: governanceThresholdText(governance.threshold_probability_field),
    guardrailsText: (governance.guardrails || []).length ? governance.guardrails.join("、") : "暂无额外保护",
    tone: toneFromSeverity(governance.severity),
    candidateRows: (governance.candidates || []).map((candidate) => [
      candidate.label || "概率候选",
      formatDecimal(candidate.brier_score),
      formatDecimal(candidate.calibration_error),
      candidate.selected ? "已选用" : "观察"
    ].join(":"))
  };
}

function adjustmentLabel(value: unknown): string {
  if (typeof value !== "string" || !value.trim()) return "保持观察";
  const labels: Record<string, string> = {
    collect_more_samples: "继续采样",
    suppress_reason: "降权过滤",
    tighten_thresholds: "收紧阈值",
    promote_watchlist: "保留观察",
    hold_neutral: "中性观察"
  };
  return labels[value] ?? "保持观察";
}

function deploymentActionText(value: unknown): string {
  if (typeof value !== "string" || !value.trim()) return "等待上线判断";
  const labels: Record<string, string> = {
    allow_gate_evaluation: "允许进入发布评估",
    calibrate_down_only: "仅用于保守校准",
    keep_paper_backtest: "继续样本回测",
    collect_more_samples: "继续采样",
    collect_or_retrain: "继续采样或优化",
    run_band_recalibration: "重新校准概率分桶"
  };
  return labels[value] ?? "保持观察";
}

function deploymentStatusText(verdict: NonNullable<DashboardSnapshot["learning_effectiveness"]>["deployment_verdict"] | undefined): string {
  if (!verdict) return "等待上线结论";
  if (verdict.production_ready) return "可进入发布闸门";
  const labels: Record<string, string> = {
    waiting_settled_samples: "等待回测样本",
    calibration_only_not_beating_market: "仅限保守校准",
    paper_only_negative_roi: "收益未转正",
    learning_not_deployable: "暂不可部署",
    calibration_inversion_guardrail: "校准保护中"
  };
  return labels[verdict.status] ?? "继续观察";
}

function deploymentReasonsText(reasons: string[] | undefined): string {
  const labels: Record<string, string> = {
    no_settled_samples: "暂无已结算样本",
    not_better_than_model: "未优于原始模型",
    not_better_than_market: "未跑赢市场",
    settled_roi_negative: "收益未转正",
    probability_bands_inverted: "概率分桶反向"
  };
  const mapped = (reasons || []).map((reason) => labels[reason] || reason).filter(Boolean);
  return mapped.length ? mapped.join("、") : "无额外阻断";
}

function deploymentVerdictView(
  effectiveness: DashboardSnapshot["learning_effectiveness"] | undefined
): DashboardView["learningEffectiveness"]["deploymentVerdict"] {
  const verdict = effectiveness?.deployment_verdict;
  if (!verdict) {
    return {
      title: "等待上线结论",
      detail: "后端尚未返回学习结果的上线可用性判断。",
      actionText: "等待上线判断",
      statusText: "等待上线结论",
      tone: "neutral",
      sampleText: "0 场",
      roiText: "—",
      reasonsText: "无额外阻断"
    };
  }
  return {
    title: customerCopy(verdict.title || "上线结论待确认"),
    detail: customerCopy(verdict.detail || ""),
    actionText: deploymentActionText(verdict.action),
    statusText: deploymentStatusText(verdict),
    tone: toneFromSeverity(verdict.severity),
    sampleText: `${verdict.sample_count ?? 0} 场`,
    roiText: formatSignedPercent(verdict.roi),
    reasonsText: deploymentReasonsText(verdict.reasons)
  };
}

function predictionQualityView(snapshot: DashboardSnapshot): DashboardView["predictionQuality"] {
  const quality = snapshot.prediction_quality;
  if (!quality) {
    return {
      severity: "warning",
      tone: "caution",
      title: "等待预测质量分段",
      detail: "后端尚未返回按原因分组的回测质量，暂时只能查看总命中率和总收益率。",
      metricRows: [
        { label: "预测样本", value: "0", caption: "等待台账", tone: "neutral" },
        { label: "已回测", value: "0", caption: "等待结算", tone: "neutral" },
        { label: "分组数量", value: "0", caption: "等待原因归类", tone: "neutral" },
        { label: "负收益分组", value: "0", caption: "等待回测", tone: "neutral" }
      ],
      segmentRows: []
    };
  }

  const summary = quality.summary || {
    total_count: 0,
    settled_count: 0,
    open_count: 0,
    segment_count: 0,
    negative_segment_count: 0,
    best_reason: "",
    worst_reason: ""
  };
  const maxCount = Math.max(1, ...(quality.segments || []).map((segment) => segment.total_count || 0));
  const segmentRows = (quality.segments || []).map((segment) => {
    const total = segment.total_count || 0;
    const coverageText = total > 0
      ? `${segment.odds_covered_count || 0}/${total}`
      : "0/0";
    const ratio = total / maxCount;
    const adjustment = segment.adjustment || null;
    const weight = numeric(adjustment?.weight_multiplier);
    return {
      label: customerCopy(segment.label || reasonLabel(segment.reason)),
      totalText: `${total} 场`,
      settledText: `已回测 ${segment.settled_count || 0} 场`,
      hitRateText: formatPercent(segment.hit_rate),
      roiText: formatSignedPercent(segment.roi),
      avgProbabilityText: formatPercent(segment.avg_probability),
      avgEdgeText: formatSignedPercent(segment.avg_edge),
      oddsCoverageText: coverageText,
      qualityText: sampleQualityText(segment.sample_quality),
      adjustmentLabel: customerCopy(adjustment?.label || adjustmentLabel(adjustment?.action)),
      adjustmentDetail: customerCopy(adjustment?.detail || "保持当前采样权重。"),
      weightText: `权重 ${formatDecimal(weight ?? 1, 2)}`,
      width: `${Math.max(6, Math.min(100, ratio * 100))}%`,
      tone: qualitySegmentTone(segment.tone, segment.roi)
    };
  });

  return {
    severity: quality.severity,
    tone: toneFromSeverity(quality.severity),
    title: customerCopy(quality.title),
    detail: customerCopy(quality.detail),
    metricRows: [
      {
        label: "预测样本",
        value: String(summary.total_count ?? 0),
        caption: "进入观察或发布台账",
        tone: (summary.total_count ?? 0) > 0 ? "neutral" : "caution"
      },
      {
        label: "已回测",
        value: String(summary.settled_count ?? 0),
        caption: `${summary.open_count ?? 0} 场未结算`,
        tone: (summary.settled_count ?? 0) >= 20 ? "good" : (summary.settled_count ?? 0) > 0 ? "neutral" : "caution"
      },
      {
        label: "分组数量",
        value: String(summary.segment_count ?? segmentRows.length),
        caption: "按主要原因拆分",
        tone: segmentRows.length ? "neutral" : "caution"
      },
      {
        label: "负收益分组",
        value: String(summary.negative_segment_count ?? 0),
        caption: "用于降权或过滤",
        tone: (summary.negative_segment_count ?? 0) > 0 ? "caution" : "good"
      }
    ],
    segmentRows
  };
}

function adaptiveActionProgressText(current: unknown, target: unknown, label: string): string {
  const currentValue = numeric(current);
  const targetValue = numeric(target);
  if (currentValue === null) return "—";
  if (targetValue === null) return String(currentValue);
  if (targetValue === 0) {
    if (label.includes("Brier") || Math.abs(currentValue) < 0.02) return formatSignedDecimal(currentValue);
    return formatSignedPercent(currentValue);
  }
  return metricProgressText(current, target);
}

function adaptiveLearningPlanView(snapshot: DashboardSnapshot): DashboardView["adaptiveLearningPlan"] {
  const plan = snapshot.adaptive_learning_plan;
  if (!plan) {
    return {
      tone: "caution",
      title: "等待自学习修正计划",
      detail: "后端尚未返回模型发现不准后的自动调整动作。",
      metrics: [
        { label: "动作总数", value: "0", caption: "等待计划", tone: "neutral" },
        { label: "阻断动作", value: "0", caption: "等待计划", tone: "neutral" },
        { label: "采样动作", value: "0", caption: "等待计划", tone: "neutral" },
        { label: "冻结模型", value: "0", caption: "等待计划", tone: "neutral" }
      ],
      actionRows: []
    };
  }
  const summary = plan.summary || {
    action_count: 0,
    blocked_action_count: 0,
    warning_action_count: 0,
    collection_action_count: 0,
    frozen_model_count: 0
  };
  const actionRows = (plan.actions || []).map((action, index) => {
    const current = numeric(action.current);
    const target = numeric(action.target);
    const ratio = target && target > 0 && current !== null ? current / target : action.status === "ok" ? 1 : action.status === "warning" ? 0.5 : 0.12;
    return {
      key: `${index}-${action.label || "修正动作"}`,
      label: customerCopy(action.label || "修正动作"),
      title: customerCopy(action.title || "待确认"),
      detail: customerCopy(action.detail || ""),
      evidence: customerCopy(action.evidence || "等待证据"),
      policyEffect: customerCopy(action.policy_effect || "继续验证"),
      statusText: statusText(action.status),
      progressText: adaptiveActionProgressText(action.current, action.target, action.evidence || action.label || ""),
      width: `${Math.max(4, Math.min(100, (clampedRatio(ratio) ?? 0) * 100))}%`,
      tone: toneFromSeverity(action.status)
    };
  });
  return {
    tone: toneFromSeverity(plan.severity),
    title: customerCopy(plan.title || "自学习修正计划"),
    detail: customerCopy(plan.detail || "后端未返回修正计划说明。"),
    metrics: [
      {
        label: "动作总数",
        value: String(summary.action_count ?? actionRows.length),
        caption: "本轮自动策略动作",
        tone: (summary.action_count ?? 0) > 0 ? "neutral" : "caution"
      },
      {
        label: "阻断动作",
        value: String(summary.blocked_action_count ?? 0),
        caption: "会关闭推荐发布",
        tone: (summary.blocked_action_count ?? 0) > 0 ? "bad" : "good"
      },
      {
        label: "采样动作",
        value: String(summary.collection_action_count ?? 0),
        caption: "继续补样本或复算",
        tone: (summary.collection_action_count ?? 0) > 0 ? "caution" : "good"
      },
      {
        label: "冻结模型",
        value: String(summary.frozen_model_count ?? 0),
        caption: "不得升级发布",
        tone: (summary.frozen_model_count ?? 0) > 0 ? "bad" : "good"
      }
    ],
    actionRows
  };
}

function dashboardContractView(snapshot: DashboardSnapshot): DashboardView["dashboardContract"] {
  const contract = snapshot.dashboard_contract;
  if (!contract) {
    return {
      tone: "caution",
      title: "等待数据契约",
      detail: "后端尚未返回数据契约健康状态，无法证明监控模块是否全部对齐。",
      policyText: "预测策略待确认",
      metricRows: [
        { label: "前端模块", value: "0", caption: "等待契约", tone: "neutral" },
        { label: "可见模块", value: "0", caption: "等待契约", tone: "neutral" },
        { label: "缺失模块", value: "0", caption: "等待契约", tone: "neutral" },
        { label: "阻断模块", value: "0", caption: "等待契约", tone: "neutral" }
      ],
      sectionRows: []
    };
  }
  const summary = contract.summary || {
    required_count: 0,
    ok_count: 0,
    warning_count: 0,
    blocked_count: 0,
    missing_required_count: 0,
    frontend_visible_count: 0
  };
  const formalEnabled = Boolean(contract.policy?.formal_recommendation_enabled);
  const sectionRows = (contract.sections || []).map((section) => {
    const ratio = clampedRatio(section.ratio);
    return {
      label: customerCopy(section.label || "契约模块"),
      title: customerCopy(section.title || "待确认"),
      detail: customerCopy(section.detail || ""),
      statusText: statusText(section.status),
      progressText: metricProgressText(section.current, section.target),
      width: `${Math.max(4, Math.min(100, (ratio ?? 0) * 100))}%`,
      tone: toneFromSeverity(section.status)
    };
  });
  return {
    tone: toneFromSeverity(contract.severity || contract.status),
    title: customerCopy(contract.title || "数据契约"),
    detail: customerCopy(contract.detail || "后端未返回契约说明。"),
    policyText: formalEnabled ? "推荐发布开放，观察样本继续回测" : "推荐发布暂停，观察样本继续回测",
    metricRows: [
      {
        label: "前端模块",
        value: String(summary.required_count ?? 0),
        caption: "必须对齐的监控模块",
        tone: (summary.required_count ?? 0) > 0 ? "neutral" : "caution"
      },
      {
        label: "可见模块",
        value: String(summary.frontend_visible_count ?? 0),
        caption: "已由前端展示",
        tone: (summary.frontend_visible_count ?? 0) >= (summary.required_count ?? 0) ? "good" : "caution"
      },
      {
        label: "缺失模块",
        value: String(summary.missing_required_count ?? 0),
        caption: "缺失会破坏契约",
        tone: (summary.missing_required_count ?? 0) > 0 ? "bad" : "good"
      },
      {
        label: "阻断模块",
        value: String(summary.blocked_count ?? 0),
        caption: "阻断推荐发布或质量闸门",
        tone: (summary.blocked_count ?? 0) > 0 ? "caution" : "good"
      }
    ],
    sectionRows
  };
}

export function customerCopy(value: string): string {
  return value
    .replaceAll("不推荐不等于不预测", "推荐发布受风控保护")
    .replaceAll("不是空壳玩具，但未达生产推荐", "推荐服务验证中")
    .replaceAll("仍是空壳玩具", "等待数据接入")
    .replaceAll("不是空壳玩具", "已形成验证闭环")
    .replaceAll("空壳玩具", "未形成验证样本")
    .replaceAll("玩具", "验证样本")
    .replaceAll("生产推荐", "推荐发布")
    .replaceAll("生产闸门", "发布闸门")
    .replaceAll("推荐闸门", "发布评估")
    .replaceAll("生产结论", "上线结论")
    .replaceAll("生产就绪", "上线状态")
    .replaceAll("正式推荐", "推荐发布")
    .replaceAll("纸面预测", "观察样本")
    .replaceAll("纸面信号", "观察信号")
    .replaceAll("纸面观察", "观察验证")
    .replaceAll("纸面验证", "持续验证")
    .replaceAll("纸面回测", "样本回测")
    .replaceAll("纸面收益", "验证收益")
    .replaceAll("纸面", "观察")
    .replaceAll("等待赛果", "未结算")
    .replaceAll("继续观察样本、回测和观察", "继续观察样本和回测")
    .replaceAll("重训", "优化")
    .replaceAll("不推荐也必须落台账", "所有分析样本均会进入台账")
    .replaceAll("不推荐也会回测", "观察样本会回测");
}

function productionActionText(action: unknown): string {
  if (action === "start_prediction_loop") return "接入预测数据";
  if (action === "allow_formal_recommendations") return "可发布推荐信号";
  if (action === "continue_paper_validation_or_retrain") return "继续验证";
  if (action === "collect_or_retrain") return "继续验证";
  return "继续监控";
}

function fallbackProductionReadiness(snapshot: DashboardSnapshot): NonNullable<DashboardSnapshot["production_readiness"]> {
  const kpis = snapshot.prediction_kpis;
  const total = kpis?.total_count ?? 0;
  const settled = kpis?.settled_count ?? 0;
  const open = kpis?.open_count ?? 0;
  const isToy = total <= 0;
  return {
    status: isToy ? "toy_empty" : "paper_validation",
    severity: isToy ? "error" : "warning",
    title: isToy ? "等待数据接入" : "推荐服务验证中",
    detail: isToy
      ? "当前尚未形成可验证样本，无法进行回测评估。"
      : `已积累 ${total} 条预测样本和 ${settled} 条回测记录；推荐发布保持关闭，直到学习效果、市场基准和收益表现全部通过。`,
    is_toy: isToy,
    production_ready: false,
    recommended_action: isToy ? "start_prediction_loop" : "continue_paper_validation_or_retrain",
    summary: {
      prediction_total: total,
      settled_count: settled,
      open_count: open,
      hit_rate: kpis?.hit_rate ?? null,
      roi: kpis?.roi ?? null,
      learning_improved: false,
      beats_market: false,
      formal_recommendation_enabled: false,
      blocked_count: isToy ? 2 : 1,
      warning_count: settled > 0 ? 1 : 0
    },
    gates: [
      {
        key: "prediction_loop",
        label: "预测闭环",
        status: isToy ? "missing" : "ok",
        title: isToy ? "没有预测样本" : "已持续预测",
        detail: `台账共有 ${total} 条预测；所有分析样本均会进入台账，用于后续回测。`,
        current: total,
        target: 1,
        ratio: total > 0 ? 1 : 0
      },
      {
        key: "backtest_sample",
        label: "回测样本",
        status: settled >= 20 ? "ok" : settled > 0 ? "warning" : "blocked",
        title: settled >= 20 ? "回测样本可用" : settled > 0 ? "样本不足" : "尚未回测",
        detail: `已结算 ${settled} 场，未结算 ${open} 场。`,
        current: settled,
        target: 20,
        ratio: settled >= 20 ? 1 : settled / 20
      }
    ]
  };
}

function readinessProgressText(current: unknown, target: unknown, label: string, key = ""): string {
  if (key === "shadow_walk_forward" || label.includes("走步验证")) return formatSignedDecimal(numeric(current));
  if (label.includes("收益")) return formatSignedPercent(numeric(current));
  const currentValue = numeric(current);
  const targetValue = numeric(target);
  if (targetValue === 1 && (currentValue === 0 || currentValue === 1)) {
    return currentValue === 1 ? "通过" : "未通过";
  }
  return metricProgressText(current, target);
}

function productionReadinessView(snapshot: DashboardSnapshot): DashboardView["productionReadiness"] {
  const readiness = snapshot.production_readiness || fallbackProductionReadiness(snapshot);
  const summary = readiness.summary;
  const title = readiness.production_ready
    ? "推荐服务可发布"
    : readiness.is_toy
      ? "等待数据接入"
      : "推荐服务验证中";
  const detail = readiness.is_toy
    ? "当前尚未形成可验证样本，无法进行回测评估。"
    : `已积累 ${summary.prediction_total ?? 0} 条预测样本和 ${summary.settled_count ?? 0} 条回测记录；仍有 ${summary.blocked_count ?? 0} 个风控项，推荐发布保持关闭。`;
  return {
    tone: toneFromSeverity(readiness.severity),
    title,
    detail: customerCopy(detail),
    actionText: productionActionText(readiness.recommended_action),
    metrics: [
      {
        label: "系统状态",
        value: readiness.is_toy ? "待接入" : "运行中",
        caption: readiness.is_toy ? "缺少预测闭环" : "已有预测闭环",
        tone: readiness.is_toy ? "bad" : "good"
      },
      {
        label: "推荐发布",
        value: readiness.production_ready ? "是" : "否",
        caption: readiness.production_ready ? "可发布推荐信号" : "继续验证",
        tone: readiness.production_ready ? "good" : "caution"
      },
      {
        label: "已回测",
        value: String(summary.settled_count ?? 0),
        caption: `${summary.open_count ?? 0} 场未结算`,
        tone: (summary.settled_count ?? 0) >= 20 ? "good" : (summary.settled_count ?? 0) > 0 ? "neutral" : "caution"
      },
      {
        label: "验证收益",
        value: formatSignedPercent(summary.roi),
        caption: `命中率 ${formatPercent(summary.hit_rate)}`,
        tone: (summary.roi ?? 0) >= 0 ? "good" : "bad"
      }
    ],
    gateRows: (readiness.gates || []).map((gate, index) => {
      const ratio = clampedRatio(gate.ratio);
      return {
        key: `${index}-${gate.label || "闸门"}`,
        label: customerCopy(gate.label || "闸门"),
        title: customerCopy(gate.title || "待确认"),
        detail: customerCopy(gate.detail || ""),
        statusText: statusText(gate.status),
        progressText: readinessProgressText(gate.current, gate.target, gate.label || "", gate.key),
        width: `${Math.max(4, Math.min(100, (ratio ?? 0) * 100))}%`,
        tone: toneFromSeverity(gate.status)
      };
    })
  };
}

function intervalText(seconds: number | null): string {
  if (seconds === null || seconds <= 0) return "未配置";
  if (seconds < 60) return `${Math.round(seconds)} 秒`;
  const minutes = Math.max(1, Math.round(seconds / 60));
  return `${minutes} 分钟`;
}

function isoAfter(left: unknown, right: unknown): boolean {
  const leftText = typeof left === "string" ? left : "";
  const rightText = typeof right === "string" ? right : "";
  const leftDate = new Date(leftText);
  const rightDate = new Date(rightText);
  if (Number.isNaN(leftDate.getTime())) return false;
  if (Number.isNaN(rightDate.getTime())) return true;
  return leftDate.getTime() > rightDate.getTime();
}

function workflowStatusText(status: "ok" | "info" | "warning" | "blocked" | "error" | "missing"): string {
  return statusText(status);
}

function productionWorkflowRow(
  key: string,
  label: string,
  status: "ok" | "info" | "warning" | "blocked" | "error" | "missing",
  detail: string,
  metaText = ""
): DashboardView["productionOps"]["workflowRows"][number] {
  return {
    key,
    label,
    title: label,
    detail: customerCopy(detail),
    statusText: workflowStatusText(status),
    metaText,
    tone: toneFromSeverity(status)
  };
}

function productionOpsView(snapshot: DashboardSnapshot): DashboardView["productionOps"] {
  const readiness = snapshot.production_readiness || fallbackProductionReadiness(snapshot);
  const summary = readiness.summary || fallbackProductionReadiness(snapshot).summary;
  const auto = objectValue(snapshot.auto_learning_state);
  const resultSummary = objectValue(auto.last_result_summary);
  const marketSync = Object.keys(objectValue(resultSummary.market_snapshot_sync)).length
    ? objectValue(resultSummary.market_snapshot_sync)
    : objectValue(auto.last_market_snapshot_sync);
  const reanalysis = Object.keys(objectValue(resultSummary.snapshot_reanalysis)).length
    ? objectValue(resultSummary.snapshot_reanalysis)
    : objectValue(auto.last_snapshot_reanalysis);
  const enabled = boolValue(auto.enabled) ?? false;
  const intervalSeconds = numeric(auto.interval_seconds) ?? 120;
  const asianWindow = numeric(auto.asian_window_minutes) ?? 10;
  const limit = numeric(auto.limit) ?? 0;
  const runCount = numeric(auto.run_count) ?? 0;
  const timezone = stringValue(auto.timezone_name, "本地时区");
  const lastRunning = isoAfter(auto.last_started_at_utc, auto.last_finished_at_utc);
  const savedRecords = numeric(resultSummary.saved_record_count) ?? numeric(resultSummary.asian_record_count) ?? 0;
  const settledCount = numeric(resultSummary.settled_count) ?? 0;
  const shadowSettledCount = numeric(resultSummary.shadow_settled_count) ?? 0;
  const marketStatus = stringValue(marketSync.status, "");
  const marketSaved = numeric(marketSync.saved_snapshot_count) ?? 0;
  const skippedCount = numeric(reanalysis.skipped_count) ?? 0;
  const clvAvailable = summary.clv_available_count ?? snapshot.clv_tracking?.available_count ?? 0;
  const clvTracked = summary.clv_tracked_count ?? snapshot.clv_tracking?.tracked_count ?? 0;
  const clvReady = summary.clv_ready ?? false;
  const blockedCount = summary.blocked_count ?? 0;
  const releaseOpen = Boolean(readiness.production_ready);
  const autoStatus = enabled ? (auto.last_error ? "异常" : "运行中") : "已关闭";
  const lastRunValue = lastRunning ? "进行中" : runCount > 0 ? "已完成" : "等待首轮";
  const nextRunValue = !enabled ? "已暂停" : lastRunning ? "等待本轮结束" : `约 ${intervalText(intervalSeconds)}内`;
  const releaseText = releaseOpen ? "开放" : "关闭";
  const blockerRows = (readiness.gates || [])
    .filter((gate) => gate.status !== "ok")
    .map((gate, index) => {
      const ratio = clampedRatio(gate.ratio);
      return {
        key: `${index}-${gate.key || gate.label || "gate"}`,
        label: customerCopy(gate.label || "闸门"),
        title: customerCopy(gate.title || "待确认"),
        detail: customerCopy(gate.detail || ""),
        statusText: statusText(gate.status),
        progressText: readinessProgressText(gate.current, gate.target, gate.label || "", gate.key),
        width: `${Math.max(4, Math.min(100, (ratio ?? 0) * 100))}%`,
        tone: toneFromSeverity(gate.status)
      };
    });

  const workflowRows = [
    productionWorkflowRow(
      "schedule",
      "抓赛程",
      enabled ? "ok" : "error",
      enabled ? `自动学习已开启，候选上限 ${limit || "—"} 场。` : "自动学习已关闭，系统不会扫描新比赛。",
      `${runCount} 轮`
    ),
    productionWorkflowRow(
      "odds",
      "抓赔率",
      marketStatus === "error" ? "error" : marketSaved > 0 ? "ok" : "warning",
      marketStatus === "error"
        ? `赔率快照抓取失败，已保存 ${marketSaved} 条。`
        : marketSaved > 0
          ? `上一轮保存 ${marketSaved} 条赔率快照。`
          : "上一轮没有生成可入库赔率快照。",
      stringValue(marketSync.provider, "赔率源")
    ),
    productionWorkflowRow(
      "near_kickoff",
      "赛前窗口",
      skippedCount > 0 ? "warning" : "ok",
      skippedCount > 0
        ? `${skippedCount} 个候选不在开赛前 ${asianWindow} 分钟窗口。`
        : `仅分析未来 ${asianWindow} 分钟内的比赛。`,
      `${asianWindow} 分钟`
    ),
    productionWorkflowRow(
      "paper_records",
      "观察样本",
      savedRecords > 0 ? "ok" : "info",
      `上一轮新增 ${savedRecords} 条观察样本。`,
      `${snapshot.prediction_kpis.observation_count ?? 0} 总样本`
    ),
    productionWorkflowRow(
      "settlement",
      "赛果结算",
      settledCount + shadowSettledCount > 0 ? "ok" : "info",
      `上一轮结算 ${settledCount} 条推荐和 ${shadowSettledCount} 条影子样本。`,
      `${snapshot.prediction_kpis.settled_count ?? 0} 已回测`
    ),
    productionWorkflowRow(
      "calibration",
      "实时校准",
      snapshot.strategy_state.active ? "ok" : "warning",
      snapshot.strategy_state.active
        ? `实时校准中 ${snapshot.strategy_state.sample_count}。`
        : `样本收集中 ${snapshot.strategy_state.sample_count}/${snapshot.strategy_state.min_live_sample_count}。`,
      "学习阈值"
    ),
    productionWorkflowRow(
      "clv",
      "CLV 追踪",
      clvReady ? "ok" : "blocked",
      `${clvAvailable}/${clvTracked} 条可计算收盘价价值。`,
      formatSignedPercent(summary.avg_clv_return ?? snapshot.clv_tracking?.avg_clv_return ?? null)
    ),
    productionWorkflowRow(
      "release",
      "发布门禁",
      releaseOpen ? "ok" : "blocked",
      releaseOpen ? "推荐发布可以开放。" : "推荐发布保持关闭。",
      `${blockedCount} 个阻断项`
    )
  ];

  return {
    tone: releaseOpen ? "good" : blockedCount > 0 ? "caution" : "neutral",
    headline: releaseOpen ? "推荐发布开放" : "推荐发布关闭",
    detail: customerCopy(readiness.detail || ""),
    releaseText,
    statusCards: [
      {
        label: "自动学习",
        value: autoStatus,
        caption: `${intervalText(intervalSeconds)}轮询 · ${asianWindow} 分钟窗口`,
        tone: enabled && !auto.last_error ? "good" : "bad"
      },
      {
        label: "最近运行",
        value: lastRunValue,
        caption: lastRunning ? "等待本轮结束" : `新增 ${savedRecords} 条样本`,
        tone: lastRunning ? "caution" : runCount > 0 ? "good" : "neutral"
      },
      {
        label: "下一轮",
        value: nextRunValue,
        caption: timezone,
        tone: enabled ? "neutral" : "bad"
      },
      {
        label: "发布门禁",
        value: releaseText,
        caption: `${blockedCount} 个阻断项`,
        tone: releaseOpen ? "good" : "bad"
      }
    ],
    blockerRows,
    workflowRows
  };
}

const DATA_SYNC_STATUS_LABELS: Record<string, string> = {
  ok: "正常",
  success: "正常",
  completed: "正常",
  complete: "正常",
  partial: "部分受限",
  warning: "需要关注",
  error: "抓取失败",
  failed: "抓取失败",
  disabled: "已关闭"
};

const DATA_HEALTH_FLAG_LABELS: Record<string, string> = {
  leisu_access_waf_challenge: "雷速访问受限",
  leisu_requires_cookie_or_proxy: "需要雷速登录凭据或代理",
  outside_near_kickoff_window: "不在赛前分析窗口",
  multi_bookmaker_snapshot_missing: "缺少多公司赔率快照",
  matching_market_snapshots_missing: "缺少匹配收盘价",
  pre_kickoff_closing_snapshots_missing: "缺少开赛前收盘价快照"
};

function statusCard(
  label: string,
  value: string,
  caption: string,
  tone: KpiCard["tone"]
): DashboardView["dataSourceHealth"]["statusCards"][number] {
  return { label, value, caption, tone };
}

function dataHealthRow(
  key: string,
  label: string,
  status: "ok" | "info" | "warning" | "blocked" | "error" | "missing",
  title: string,
  detail: string,
  metaText: string,
  ratio: number | null
): DashboardView["dataSourceHealth"]["checkRows"][number] {
  return {
    key,
    label,
    title,
    detail: customerCopy(detail),
    statusText: statusText(status),
    metaText,
    width: `${Math.max(4, Math.min(100, (ratio ?? (status === "ok" ? 1 : 0.12)) * 100))}%`,
    tone: toneFromSeverity(status)
  };
}

function firstObjectValue(...values: unknown[]): Record<string, unknown> {
  for (const value of values) {
    const candidate = objectValue(value);
    if (Object.keys(candidate).length > 0) return candidate;
  }
  return {};
}

function marketSyncState(snapshot: DashboardSnapshot): Record<string, unknown> {
  const auto = objectValue(snapshot.auto_learning_state);
  const resultSummary = objectValue(auto.last_result_summary);
  return firstObjectValue(
    objectValue(resultSummary.market_snapshot_sync),
    auto.last_market_snapshot_sync,
    snapshot.market_snapshot_summary?.last_sync
  );
}

function snapshotReanalysisState(snapshot: DashboardSnapshot): Record<string, unknown> {
  const auto = objectValue(snapshot.auto_learning_state);
  const resultSummary = objectValue(auto.last_result_summary);
  return firstObjectValue(objectValue(resultSummary.snapshot_reanalysis), auto.last_snapshot_reanalysis);
}

function providerDisplayName(provider: unknown): string {
  const key = typeof provider === "string" ? provider : "";
  return PROVIDER_LABELS[key] ?? "赔率源";
}

function syncStatusLabel(status: unknown, savedCount: number): string {
  const key = typeof status === "string" ? status : "";
  if (DATA_SYNC_STATUS_LABELS[key]) return DATA_SYNC_STATUS_LABELS[key];
  if (savedCount > 0) return "正常";
  return "等待下一轮";
}

function syncStatusSeverity(status: unknown, savedCount: number, flagCount: number): "ok" | "info" | "warning" | "error" {
  if (status === "error" || status === "failed") return "error";
  if (status === "partial" || status === "warning" || flagCount > 0) return "warning";
  if (status === "ok" || status === "success" || status === "completed" || status === "complete") return savedCount > 0 ? "ok" : "warning";
  if (savedCount > 0) return "ok";
  return "info";
}

function numberText(value: unknown, fallback = 0): number {
  return numeric(value) ?? fallback;
}

function syncCaption(sync: Record<string, unknown>): string {
  const probed = numberText(sync.probed_match_count);
  const accessible = numberText(sync.accessible_match_count);
  const saved = numberText(sync.saved_snapshot_count);
  if (probed || accessible || saved) {
    return `探测 ${probed} 场 · 可访问 ${accessible} 场 · 保存 ${saved} 条`;
  }
  return "尚未返回最近一轮抓取结果";
}

function freshnessText(value: unknown, baseValue: unknown): string {
  const raw = typeof value === "string" ? value : "";
  if (!raw) return "未返回时间";
  const date = new Date(raw);
  const base = new Date(typeof baseValue === "string" ? baseValue : "");
  if (Number.isNaN(date.getTime())) return "未返回时间";
  if (Number.isNaN(base.getTime())) return raw;
  const diffMinutes = Math.max(0, Math.round((base.getTime() - date.getTime()) / 60000));
  if (diffMinutes < 5) return "刚刚更新";
  if (diffMinutes < 60) return `${diffMinutes} 分钟前`;
  const hours = Math.round(diffMinutes / 60);
  if (hours < 24) return `${hours} 小时前`;
  return `${Math.round(hours / 24)} 天前`;
}

function friendlyFlags(sync: Record<string, unknown>): string[] {
  const hard = Array.isArray(sync.hard_flags) ? sync.hard_flags : [];
  const soft = Array.isArray(sync.soft_flags) ? sync.soft_flags : [];
  return [...hard, ...soft]
    .map((flag) => typeof flag === "string" ? DATA_HEALTH_FLAG_LABELS[flag] : "")
    .filter(Boolean)
    .filter((flag, index, list) => list.indexOf(flag) === index);
}

function dataSourceHealthView(snapshot: DashboardSnapshot): DashboardView["dataSourceHealth"] {
  const auto = objectValue(snapshot.auto_learning_state);
  const marketSummary = snapshot.market_snapshot_summary;
  const marketSync = marketSyncState(snapshot);
  const reanalysis = snapshotReanalysisState(snapshot);
  const intervalSeconds = numeric(auto.interval_seconds) ?? 120;
  const asianWindow = numeric(auto.asian_window_minutes) ?? 10;
  const runCount = numeric(auto.run_count) ?? 0;
  const syncSaved = numberText(marketSync.saved_snapshot_count);
  const flags = friendlyFlags(marketSync);
  const syncSeverity = syncStatusSeverity(marketSync.status, syncSaved, flags.length);
  const ledgerCount = snapshot.prediction_ledger?.length || 0;
  const coveredCount = (snapshot.prediction_ledger || []).filter((row) => row.has_odds_snapshot || (row.odds_snapshot_count ?? 0) > 0).length;
  const multiBookmakerCount = (snapshot.prediction_ledger || []).filter((row) => (row.odds_bookmaker_count ?? 0) >= 2).length;
  const ledgerRatio = ledgerCount ? coveredCount / ledgerCount : null;
  const ledgerStatus = ledgerCount === 0 ? "info" : coveredCount === ledgerCount ? "ok" : coveredCount > 0 ? "warning" : "blocked";
  const skippedCount = numberText(reanalysis.skipped_count);
  const windowStatus = skippedCount > 0 ? "warning" : "ok";
  const contextCoverage = snapshot.context_coverage;
  const contextRatios = (contextCoverage?.fields || []).map((field) => field.coverage_ratio ?? 0);
  const contextRatio = contextRatios.length
    ? contextRatios.reduce((total, value) => total + value, 0) / contextRatios.length
    : 0;
  const contextStatus = contextRatio >= 0.7 ? "ok" : contextRatio > 0 ? "warning" : "missing";
  const clv = snapshot.clv_tracking;
  const clvReadiness = objectValue(objectValue(clv).readiness);
  const clvAvailable = numeric(clvReadiness.current) ?? clv?.available_count ?? 0;
  const clvTarget = numeric(clvReadiness.target) ?? 30;
  const clvStatus = clvAvailable >= clvTarget ? "ok" : clvAvailable > 0 ? "blocked" : "blocked";
  const latestSnapshotText = freshnessText(marketSummary?.latest_fetched_at_utc, snapshot.generated_at_utc);
  const syncAttemptText = freshnessText(marketSync.at_utc, snapshot.generated_at_utc);
  const syncCaptionText = syncCaption(marketSync);
  const syncDetailText = syncCaptionText.startsWith("尚未")
    ? `${providerDisplayName(marketSync.provider)}${syncCaptionText}。`
    : `${providerDisplayName(marketSync.provider)}最近一轮${syncCaptionText}。`;

  const checkRows = [
    dataHealthRow(
      "odds_sync",
      "赔率抓取",
      syncSeverity === "error" ? "error" : syncSeverity === "warning" ? "warning" : syncSeverity === "ok" ? "ok" : "info",
      syncSeverity === "ok" ? "上一轮已保存赔率快照" : syncSeverity === "error" ? "赔率抓取失败" : syncSeverity === "warning" ? "赔率抓取受限" : "等待下一轮抓取",
      syncSeverity === "ok"
        ? `上一轮保存 ${syncSaved} 条赔率快照，来源 ${providerDisplayName(marketSync.provider)}。`
        : syncDetailText,
      syncAttemptText,
      syncSeverity === "ok" ? 1 : syncSeverity === "warning" ? 0.45 : 0.12
    ),
    dataHealthRow(
      "near_kickoff",
      "赛前窗口",
      windowStatus,
      skippedCount > 0 ? "候选不在分析窗口" : "仅分析赛前窗口内比赛",
      skippedCount > 0
        ? `${skippedCount} 个候选没有进入开赛前 ${asianWindow} 分钟分析窗口。`
        : `当前配置只分析未来 ${asianWindow} 分钟内的比赛。`,
      `${asianWindow} 分钟`,
      skippedCount > 0 ? 0.45 : 1
    ),
    dataHealthRow(
      "ledger_coverage",
      "台账覆盖",
      ledgerStatus,
      ledgerStatus === "ok" || (syncSeverity === "ok" && coveredCount > 0) ? "赔率覆盖可追溯" : ledgerCount === 0 ? "等待预测台账" : "部分预测缺少赔率快照",
      ledgerCount === 0
        ? "当前暂无预测台账，无法判断赔率覆盖。"
        : `台账 ${coveredCount}/${ledgerCount} 场有赔率快照，其中 ${multiBookmakerCount} 场达到多公司覆盖。`,
      `${coveredCount}/${ledgerCount}`,
      ledgerRatio
    ),
    dataHealthRow(
      "match_context",
      "赛事情报",
      contextStatus,
      contextStatus === "ok" ? "赛事情报覆盖稳定" : "赛事情报待补齐",
      contextCoverage?.summary || "暂无赛事情报覆盖统计。",
      `${Math.round(contextRatio * 100)}%`,
      contextRatio
    ),
    dataHealthRow(
      "clv_tracking",
      "收盘价追踪",
      clvStatus,
      clvStatus === "ok" ? "收盘价样本可用" : "收盘价样本不足",
      `当前 ${clvAvailable}/${clvTarget} 条可计算收盘价价值，用于判断是否跑赢收盘线。`,
      `${clvAvailable}/${clvTarget}`,
      clvTarget ? clvAvailable / clvTarget : null
    )
  ];

  const nonHealthyCount = checkRows.filter((row) => row.tone !== "good").length;
  const hasCriticalIssue =
    syncSeverity === "error" ||
    syncSeverity === "warning" ||
    windowStatus !== "ok" ||
    ledgerStatus === "blocked" ||
    clvStatus !== "ok";
  const title = hasCriticalIssue ? "数据采集需要关注" : "数据采集正常";
  const issueText = flags.length ? flags.join("；") : nonHealthyCount > 0 ? `${nonHealthyCount} 项需要关注` : "暂无数据采集阻断";

  return {
    tone: !hasCriticalIssue && nonHealthyCount === 0 ? "good" : syncSeverity === "error" || ledgerStatus === "blocked" ? "bad" : "caution",
    title,
    detail: `赔率、赛事情报、赛前 ${asianWindow} 分钟窗口和收盘价追踪集中体检；预测前应优先确认这里没有阻断项。`,
    issueText,
    statusCards: [
      statusCard("赔率源", syncStatusLabel(marketSync.status, syncSaved), syncCaptionText, toneFromSeverity(syncSeverity)),
      statusCard(
        "赔率快照",
        `${marketSummary?.total_snapshot_count ?? 0} 条`,
        `${marketSummary?.event_count ?? 0} 场 · ${marketSummary?.bookmaker_count ?? 0} 家公司 · ${latestSnapshotText}`,
        (marketSummary?.total_snapshot_count ?? 0) > 0 ? "good" : "caution"
      ),
      statusCard(
        "台账覆盖",
        `${coveredCount}/${ledgerCount}`,
        `${multiBookmakerCount} 场多公司 · ${ledgerStatus === "ok" ? "覆盖完整" : "待补齐"}`,
        toneFromSeverity(ledgerStatus)
      ),
      statusCard("采集窗口", `${asianWindow} 分钟`, `${intervalText(intervalSeconds)}轮询 · ${runCount} 轮`, windowStatus === "ok" ? "good" : "caution")
    ],
    checkRows
  };
}

function fallbackPredictionAccountability(snapshot: DashboardSnapshot): NonNullable<DashboardSnapshot["prediction_accountability"]> {
  const kpis = snapshot.prediction_kpis;
  const total = kpis?.total_count ?? 0;
  const formal = kpis?.recommended_count ?? 0;
  const paper = kpis?.observation_count ?? 0;
  const settled = kpis?.settled_count ?? 0;
  const open = kpis?.open_count ?? 0;
  return {
    status: total > 0 ? "active_validation" : "empty",
    severity: total > 0 ? "warning" : "error",
    headline: total > 0 ? "推荐发布受风控保护" : "等待预测闭环",
    title: total > 0 ? "推荐发布受风控保护" : "等待预测闭环",
    detail: total > 0
      ? `当前推荐发布 ${formal} 条、观察样本 ${paper} 条；${settled} 条已回测，${open} 条未结算。`
      : "当前尚未形成预测样本，无法回测验证。",
    summary: {
      total_predictions: total,
      formal_recommendations: formal,
      paper_predictions: paper,
      settled_predictions: settled,
      open_predictions: open,
      hit_rate: kpis?.hit_rate ?? null,
      roi: kpis?.roi ?? null,
      learning_active: Boolean(snapshot.strategy_state?.active),
      learning_improved: Boolean(snapshot.learning_effectiveness?.learning_improved),
      beats_market: Boolean(snapshot.learning_effectiveness?.beats_market),
      formal_gate_enabled: Boolean(snapshot.recommendation_opportunity?.release_gate?.formal_enabled),
      primary_blocker: snapshot.candidate_filters?.[0]?.reason || "",
      primary_blocker_label: snapshot.candidate_filters?.[0] ? reasonLabel(snapshot.candidate_filters[0].reason) : "暂无主要阻断"
    },
    checks: [
      {
        key: "prediction_loop",
        label: "预测闭环",
        status: total > 0 ? "ok" : "missing",
        title: total > 0 ? "正在持续预测" : "没有预测样本",
        detail: `已生成 ${total} 条预测；未达到发布标准的信号仍会作为观察样本保留。`,
        current: total,
        target: 1,
        ratio: total > 0 ? 1 : 0
      },
      {
        key: "formal_gate",
        label: "推荐闸门",
        status: formal > 0 ? "ok" : settled >= 20 ? "blocked" : "warning",
        title: formal > 0 ? "推荐发布开放" : "推荐发布关闭",
        detail: `当前推荐发布 ${formal} 条；主要阻断为 ${snapshot.candidate_filters?.[0] ? reasonLabel(snapshot.candidate_filters[0].reason) : "暂无主要阻断"}。`,
        current: formal,
        target: 1,
        ratio: formal > 0 ? 1 : 0
      }
    ],
    policy: {
      prediction_policy: "always_predict_and_backtest",
      formal_recommendation_policy: "gate_formal_recommendations_when_learning_or_roi_is_unproven",
      paper_prediction_policy: "persist_every_analysis_ready_signal_for_settlement_backtest",
      no_real_bet: true
    }
  };
}

function predictionAccountabilityPolicyText(accountability: NonNullable<DashboardSnapshot["prediction_accountability"]>): string {
  if (accountability.policy?.no_real_bet === false) return "策略状态异常：交易动作未明确关闭";
  return accountability.summary.formal_gate_enabled
    ? "推荐发布开放，观察样本继续进入回测"
    : "推荐发布关闭，观察样本继续进入回测";
}

function predictionAccountabilityView(snapshot: DashboardSnapshot): DashboardView["predictionAccountability"] {
  const accountability = snapshot.prediction_accountability || fallbackPredictionAccountability(snapshot);
  const summary = accountability.summary;
  const checks = accountability.checks || [];
  return {
    tone: toneFromSeverity(accountability.severity),
    headline: customerCopy(accountability.headline || "推荐发布受风控保护"),
    title: customerCopy(accountability.title || "预测闭环"),
    detail: customerCopy(accountability.detail || "等待预测闭环说明。"),
    policyText: predictionAccountabilityPolicyText(accountability),
    metrics: [
      {
        label: "预测样本",
        value: String(summary.total_predictions ?? 0),
        caption: "所有可分析信号",
        tone: (summary.total_predictions ?? 0) > 0 ? "good" : "bad"
      },
      {
        label: "推荐发布",
        value: String(summary.formal_recommendations ?? 0),
        caption: summary.formal_gate_enabled ? "闸门已开放" : "受发布闸门保护",
        tone: (summary.formal_recommendations ?? 0) > 0 ? "good" : "neutral"
      },
      {
        label: "观察样本",
        value: String(summary.paper_predictions ?? 0),
        caption: "观察样本会回测",
        tone: (summary.paper_predictions ?? 0) > 0 ? "caution" : "neutral"
      },
      {
        label: "未结算",
        value: String(summary.open_predictions ?? 0),
        caption: `${summary.settled_predictions ?? 0} 条已回测`,
        tone: (summary.open_predictions ?? 0) > 0 ? "caution" : "neutral"
      }
    ],
    checkRows: checks.map((check, index) => {
      const ratio = clampedRatio(check.ratio);
      return {
        key: `${index}-${check.key || check.label || "check"}`,
        label: customerCopy(check.label || "检查项"),
        title: customerCopy(check.title || "待确认"),
        detail: customerCopy(check.detail || ""),
        statusText: statusText(check.status),
        progressText: metricProgressText(check.current, check.target),
        width: `${Math.max(4, Math.min(100, (ratio ?? (check.status === "ok" ? 1 : 0.12)) * 100))}%`,
        tone: toneFromSeverity(check.status)
      };
    })
  };
}

function contextCoverageCaption(field: DashboardContextCoverage["fields"][number]): string {
  const parts = [];
  if (field.source_empty_count) parts.push(`${field.source_empty_count} 源站暂无`);
  if (field.not_collected_count) parts.push(`${field.not_collected_count} 本地未采集`);
  return parts.join(" · ") || "无缺口";
}

function contextCoverageTone(ratio: number): KpiCard["tone"] {
  if (ratio >= 0.7) return "good";
  if (ratio > 0) return "neutral";
  return "caution";
}

function contextCoverageSourceText(item: DashboardContextCoverageSource): string {
  const label = item.label || "来源未知";
  const count = item.count ?? 0;
  if (item.status === "odds_matched_context_not_collected") return `${label} ${count} 场（仅赔率）`;
  if (item.status === "access_blocked") return `${label} ${count} 场（访问受限）`;
  if (item.status === "not_collected") return `${label} ${count} 场`;
  return `${label} ${count} 场`;
}

function contextCoverageView(snapshot: DashboardSnapshot): ContextCoverageView {
  const coverage = snapshot.context_coverage;
  if (!coverage) {
    return {
      totalText: "0 场",
      summary: "暂无赛事情报覆盖统计。",
      sourceText: "暂无来源统计",
      fields: []
    };
  }
  return {
    totalText: `${coverage.total_count ?? 0} 场`,
    summary: coverage.summary || "暂无赛事情报覆盖统计。",
    sourceText: (coverage.source_counts || [])
      .map(contextCoverageSourceText)
      .join(" · ") || "暂无来源统计",
    fields: (coverage.fields || []).map((field) => {
      const total = field.total_count || coverage.total_count || 0;
      const ratio = field.coverage_ratio ?? (total ? field.available_count / total : 0);
      return {
        key: field.key,
        label: field.label || DATA_BLOCK_LABELS[field.key] || field.key,
        value: `${field.available_count ?? 0}/${total}`,
        caption: contextCoverageCaption(field),
        width: `${Math.max(4, Math.min(100, ratio * 100))}%`,
        tone: contextCoverageTone(ratio)
      };
    })
  };
}

function recommendationThresholdText(opportunity: DashboardSnapshot["recommendation_opportunity"]): string {
  const thresholds = opportunity?.gate_thresholds;
  if (!thresholds) return "等待推荐门槛";
  return [
    `最低概率 ${formatPercent(thresholds.min_calibrated_probability)}`,
    `最低边际 ${formatSignedPercent(thresholds.min_value_edge)}`,
    `赔率 ${formatOdds(thresholds.min_decimal_odds)}-${formatOdds(thresholds.max_decimal_odds)}`
  ].join(" · ");
}

function recommendationReleaseGateView(opportunity: DashboardSnapshot["recommendation_opportunity"]): DashboardView["recommendationOpportunity"]["releaseGate"] {
  const gate = opportunity?.release_gate;
  if (!gate) return null;
  const gateRows = (gate.gates || []).map((item, index) => {
    const ratio = clampedRatio(item.ratio);
    const current = item.current;
    const target = item.target;
    const progressText = item.key === "shadow_walk_forward"
      ? formatSignedDecimal(current)
      : ["backtest_roi", "signal_backtest", "global_backtest_roi"].includes(item.key)
        ? formatSignedPercent(current)
        : target === null || target === undefined
          ? formatDecimal(current, 0)
          : target === 0
            ? current === 0 ? "无需补齐" : formatDecimal(current, 0)
          : target === 1 && (current === 0 || current === 1)
            ? current === 1 ? "通过" : "未通过"
            : `${formatDecimal(current, 0)}/${formatDecimal(target, 0)}`;
    return {
      key: `${index}-${item.label || "闸门"}`,
      label: customerCopy(item.label || "闸门"),
      title: customerCopy(item.title || "待确认"),
      detail: customerCopy(item.detail || ""),
      tone: toneFromSeverity(item.status),
      progressText,
      width: `${Math.max(4, Math.min(100, (ratio ?? 0) * 100))}%`
    };
  });
  return {
    title: customerCopy(gate.title || "推荐发布门控"),
    detail: customerCopy(gate.detail || "后端未返回门控说明。"),
    tone: toneFromSeverity(gate.severity),
    gateRows
  };
}

function fallbackRecommendationOpportunity(): DashboardView["recommendationOpportunity"] {
  return {
    severity: "warning",
    tone: "caution",
    title: "暂无推荐机会审计",
    detail: "后端尚未返回推荐机会数据，无法解释当前没有可发布推荐的原因。",
    thresholdText: "等待推荐门槛",
    releaseGate: null,
    metrics: [
      { label: "推荐发布", value: "0", caption: "暂无可发布推荐", tone: "neutral" },
      { label: "观察信号", value: "0", caption: "暂无观察信号", tone: "neutral" },
      { label: "已过门槛", value: "0", caption: "等待候选", tone: "neutral" },
      { label: "待复算", value: "0", caption: "当前无复算队列", tone: "neutral" }
    ],
    blockers: [],
    candidates: []
  };
}

function counterSignalView(
  opportunity: NonNullable<DashboardSnapshot["recommendation_opportunity"]>
): DashboardView["recommendationOpportunity"]["counterSignal"] {
  const candidates = (opportunity.counter_signal_candidates || []).map((candidate) => ({
    ledgerId: candidate.ledger_id,
    matchup: matchupLabel(candidate.matchup),
    league: candidate.league,
    homeTeam: candidate.home_team,
    awayTeam: candidate.away_team,
    homeTeamLogoUrl: candidate.home_team_logo_url,
    awayTeamLogoUrl: candidate.away_team_logo_url,
    selection: selectionLabel(candidate.selection, "asian_handicap"),
    signalLabel: candidate.meta_signal_label || "反向校准观察",
    signalReason: candidate.meta_signal_reason || opportunity.counter_signal_rule?.detail || "该候选只用于校准观察。",
    actionLabel: actionLabel(candidate.recommendation),
    blockerLabel: reasonLabel(candidate.primary_blocker),
    probabilityText: formatPercent(candidate.learned_probability),
    metaProbabilityText: formatPercent(candidate.meta_probability),
    edgeText: formatSignedPercent(candidate.value_edge),
    metaEdgeText: formatSignedPercent(candidate.meta_edge),
    confidenceText: `${sampleQualityText(candidate.meta_confidence)} · ${candidate.meta_sample_count ?? 0} 场`,
    oddsText: formatOdds(candidate.decimal_odds),
    snapshotText: candidate.has_odds_snapshot ? `${candidate.odds_snapshot_count ?? 0} 条快照` : "暂无快照",
    bandText: probabilityBandLabel(candidate.probability_band_key)
  }));
  const count = opportunity.counter_signal_count ?? candidates.length;
  if (count <= 0 && !candidates.length) return undefined;
  const rule = opportunity.counter_signal_rule;
  return {
    title: customerCopy(rule?.title || "反向校准观察"),
    detail: customerCopy(rule?.detail || "当前候选只进入观察验证，用来验证概率分桶是否需要优化。"),
    modelText: metaModelText(rule?.meta_model),
    candidateBandsText: candidateBandsText(rule?.candidate_band_keys),
    tone: toneFromSeverity(opportunity.severity),
    candidates
  };
}

function recommendationOpportunityView(snapshot: DashboardSnapshot): DashboardView["recommendationOpportunity"] {
  const opportunity = snapshot.recommendation_opportunity;
  if (!opportunity) return fallbackRecommendationOpportunity();
  const metrics = [
    {
      label: "推荐发布",
      value: String(opportunity.formal_count ?? 0),
      caption: opportunity.formal_count ? "可作为发布信号跟踪" : "当前没有可发布推荐",
      tone: opportunity.formal_count ? "good" : "neutral" as KpiCard["tone"]
    },
    {
      label: "观察信号",
      value: String(opportunity.paper_signal_count ?? 0),
      caption: "观察信号保留预测和回测",
      tone: opportunity.paper_signal_count ? "caution" : "neutral" as KpiCard["tone"]
    },
    {
      label: "已过门槛",
      value: String(opportunity.threshold_ready_count ?? 0),
      caption: "概率、边际、赔率均达标",
      tone: opportunity.threshold_ready_count ? "good" : "neutral" as KpiCard["tone"]
    },
    {
      label: "待复算",
      value: String(opportunity.reanalysis_backlog_count ?? 0),
      caption: opportunity.reanalysis_backlog_count ? "赔率补齐后需重算" : "当前无复算队列",
      tone: opportunity.reanalysis_backlog_count ? "caution" : "good" as KpiCard["tone"]
    }
  ];
  const counterSignalCount = opportunity.counter_signal_count ?? 0;
  if (counterSignalCount > 0) {
    metrics.push({
      label: "反向观察",
      value: String(counterSignalCount),
      caption: "只验证校准，不作为推荐",
      tone: "caution"
    });
  }
  metrics.push({
    label: "历史信号",
    value: String(opportunity.historical_paper_signal_count ?? 0),
    caption: "已结算或非当前窗口，仅用于回测",
    tone: "neutral"
  });
  return {
    severity: opportunity.severity,
    tone: toneFromSeverity(opportunity.severity),
    title: customerCopy(opportunity.title),
    detail: customerCopy(opportunity.detail),
    thresholdText: recommendationThresholdText(opportunity),
    releaseGate: recommendationReleaseGateView(opportunity),
    metrics,
    blockers: diagnosticBlockers(opportunity.top_blockers || []).map((item, index) => ({
      key: `blocker-${index}`,
      label: item.label,
      count: item.count,
      countText: item.countText,
      ratio: item.ratio,
      width: item.width
    })),
    candidates: (opportunity.top_candidates || []).map((candidate) => ({
      ledgerId: candidate.ledger_id,
      matchup: matchupLabel(candidate.matchup),
      league: candidate.league,
      homeTeam: candidate.home_team,
      awayTeam: candidate.away_team,
      homeTeamLogoUrl: candidate.home_team_logo_url,
      awayTeamLogoUrl: candidate.away_team_logo_url,
      selection: selectionLabel(candidate.selection, "asian_handicap"),
      actionLabel: actionLabel(candidate.recommendation),
      blockerLabel: reasonLabel(candidate.primary_blocker),
      probabilityText: formatPercent(candidate.learned_probability),
      probabilityGapText: formatSignedPercent(candidate.probability_gap),
      edgeText: formatSignedPercent(candidate.value_edge),
      edgeGapText: formatSignedPercent(candidate.value_edge_gap),
      oddsText: formatOdds(candidate.decimal_odds),
      snapshotText: candidate.has_odds_snapshot ? `${candidate.odds_snapshot_count ?? 0} 条快照` : "暂无快照",
      thresholdReady: Boolean(candidate.threshold_ready)
    })),
    counterSignal: counterSignalView(opportunity)
  };
}

export function buildRecordDetailView(detail: DashboardRecordDetail): RecordDetailView {
  const record = detail.record;
  const metrics = detail.evidence.core_metrics;
  const action = detail.evidence.final_execution_advice;
  const probabilityRows: ProbabilityRow[] = [
    { label: "模型概率", value: metrics.model_probability, text: formatPercent(metrics.model_probability) },
    { label: "学习后概率", value: metrics.learned_probability, text: formatPercent(metrics.learned_probability) },
    { label: "市场隐含", value: metrics.market_probability, text: formatPercent(metrics.market_probability) }
  ];
  return {
    title: matchupLabel(record.matchup),
    subtitle: [record.league, marketLabel(record.market), stakeLevelLabel(record.stake_level)].filter(Boolean).join(" · "),
    marketSummary: `${selectionLabel(record.selection, record.market)} · ${formatOdds(metrics.decimal_odds)} · 价值边际 ${formatSignedPercent(metrics.edge)}`,
    actionText: [actionLabel(action.action), adviceReasonLabel(action.reason)].map((item) => stringValue(item, "")).filter(Boolean).join(" · ") || actionLabel(record.recommendation) || "—",
    probabilityRows,
    candidateRows: candidateRows(detail.evidence.market_candidates),
    dataFlags: dataFlags(detail.evidence.data_completeness),
    riskFlags: flagLabels([...detail.evidence.risk_flags, ...detail.evidence.caution_flags]),
    timeline: timelineRows(detail.timeline),
    hasQueryControls: false
  };
}

function oddsSummary(detail: DashboardMatchDetail): string {
  const snapshot = detail.odds_snapshot;
  if (!snapshot.snapshot_count) return "暂无赔率快照";
  const markets = snapshot.market_types
    .map((item) => marketLabel(item))
    .join("、") || "盘口未知";
  return `${snapshot.snapshot_count} 条 · ${snapshot.bookmaker_count} 家公司 · ${markets}`;
}

function lineupTeamView(team: DashboardMatchDetail["match_context"]["lineup"]["home"]): MatchDetailView["lineup"]["home"] {
  return {
    formation: team.formation || "阵型未知",
    starterCountText: team.starter_count ? `${team.starter_count} 人` : "人数未知",
    players: (team.starters || []).slice(0, 11)
  };
}

function contextSourceText(detail: DashboardMatchDetail): string {
  const source = detail.match_context.source;
  if (!source || source.status === "not_collected") {
    return source?.match_id ? `本地未保存情报 · ${source.match_id}` : "本地未保存情报";
  }
  const matchId = source.match_id ? ` · ${source.match_id}` : "";
  return `${source.label || "来源未知"}${matchId}`;
}

function contextFieldStatusText(field: DashboardMatchDetail["match_context"]["venue"], sourceLabel: string): string {
  if (field.available) return "已采集";
  if (field.status === "source_empty") return `${sourceLabel || "源站"}暂无`;
  if (field.status === "not_collected") return "本地未采集";
  return "待确认";
}

function sourceEmptyValue(sourceLabel: string): string {
  return `${sourceLabel || "源站"}暂无信息`;
}

function contextFieldRow(
  label: string,
  field: DashboardMatchDetail["match_context"]["venue"],
  sourceLabel: string
): MatchDetailView["contextRows"][number] {
  return {
    label,
    value: field.available
      ? field.text
      : field.status === "source_empty"
        ? sourceEmptyValue(sourceLabel)
        : field.text || "暂未采集",
    available: field.available,
    statusText: contextFieldStatusText(field, sourceLabel),
    sourceText: field.source_text
  };
}

function lineupStatusText(lineup: DashboardMatchDetail["match_context"]["lineup"], sourceLabel: string): string {
  if (lineup.available && lineup.basis === "official_lineups") return `${sourceLabel || "源站"}正式阵容`;
  if (lineup.available && lineup.basis === "forecast_lineups") return `${sourceLabel || "源站"}预测阵容`;
  if (lineup.basis === "unavailable" || lineup.basis === "not_available") return `${sourceLabel || "源站"}暂无阵容`;
  return "本地未采集阵容";
}

type ContextSourceAttempt = NonNullable<DashboardMatchDetail["match_context"]["source_attempts"]>[number];

function contextSourceAttempt(detail: DashboardMatchDetail, provider: string): ContextSourceAttempt | undefined {
  return (detail.match_context.source_attempts || []).find((attempt) => attempt.provider === provider);
}

function contextAttemptFieldLabels(attempt: ContextSourceAttempt | undefined, status: string): string[] {
  if (!attempt?.field_statuses) return [];
  return Object.entries(attempt.field_statuses)
    .filter(([, fieldStatus]) => fieldStatus === status)
    .map(([key]) => CONTEXT_FIELD_LABELS[key] || DATA_BLOCK_LABELS[key] || key)
    .filter(Boolean);
}

function contextAttemptStatusText(status: string): string {
  if (status === "matched") return "已匹配";
  if (status === "odds_matched_context_not_collected") return "仅匹配赔率";
  if (status === "access_blocked") return "访问受限";
  if (status === "not_collected") return "本地未采集";
  if (status === "source_empty") return "源站暂无";
  return statusText(status as any);
}

function contextAttemptFieldStatusText(status: string): string {
  if (status === "available") return "已采集";
  if (status === "source_empty") return "源站暂无";
  if (status === "not_collected") return "本地未采集";
  if (status === "access_blocked") return "访问受限";
  if (status === "matched") return "已匹配";
  return contextAttemptStatusText(status);
}

function contextAttemptTone(attempt: ContextSourceAttempt): KpiCard["tone"] {
  const statuses = Object.values(attempt.field_statuses || {});
  if (statuses.some((status) => status === "available")) return "good";
  if (attempt.status === "access_blocked" || statuses.some((status) => status === "access_blocked")) return "bad";
  if (attempt.status === "odds_matched_context_not_collected") return "caution";
  if (statuses.some((status) => status === "source_empty" || status === "not_collected")) return "caution";
  return toneFromSeverity(attempt.status as any);
}

function sourceAttemptDetailText(detail: string): string {
  return detail
    .replaceAll("odds_matched_context_not_collected", "仅匹配赔率")
    .replaceAll("access_blocked", "访问受限")
    .replaceAll("source_empty", "源站暂无")
    .replaceAll("not_collected", "本地未采集")
    .replaceAll("403 forbidden", "403 访问被拒绝")
    .replace(/\s+vs\s+/gi, " 对 ");
}

function contextSourceAttemptRows(detail: DashboardMatchDetail): MatchDetailView["sourceAttemptRows"] {
  return (detail.match_context.source_attempts || []).map((attempt) => {
    const fieldSummary = Object.entries(attempt.field_statuses || {})
      .map(([key, status]) => `${CONTEXT_FIELD_LABELS[key] || DATA_BLOCK_LABELS[key] || key}${contextAttemptFieldStatusText(status)}`)
      .filter(Boolean)
      .join("、");
    return {
      providerText: attempt.label || PROVIDER_LABELS[attempt.provider] || "来源未知",
      matchIdText: attempt.match_id ? `赛事 ${attempt.match_id}` : "暂无赛事编号",
      statusText: contextAttemptStatusText(attempt.status),
      fieldSummary: fieldSummary || "暂无字段状态",
      detail: sourceAttemptDetailText(attempt.detail || ""),
      tone: contextAttemptTone(attempt)
    };
  });
}

function contextDiagnostics(detail: DashboardMatchDetail): MatchDetailView["contextDiagnostics"] {
  const diagnostics: MatchDetailView["contextDiagnostics"] = [];
  const source = detail.match_context.source;
  const sourceLabel = source?.label || "源站";
  const matchId = source?.match_id ? `比赛 ${source.match_id}` : "比赛";
  const sourceEmptyLabels: string[] = [
    ["比赛场地", detail.match_context.venue] as const,
    ["天气", detail.match_context.weather] as const,
    ["裁判", detail.match_context.referee] as const
  ]
    .filter(([, field]) => !field.available && field.status === "source_empty")
    .map(([label]) => label);
  if (!detail.match_context.lineup.available && source?.status === "matched") {
    sourceEmptyLabels.push("阵容");
  }

  if (source?.status === "matched") {
    diagnostics.push({
      label: sourceLabel,
      detail: sourceEmptyLabels.length
        ? `已查询${sourceLabel}${matchId}，${sourceEmptyLabels.join("、")}为源站暂无。`
        : `已查询${sourceLabel}${matchId}，可用情报已写入本地详情。`,
      tone: sourceEmptyLabels.length ? "caution" : "good"
    });
  } else {
    diagnostics.push({
      label: "情报源",
      detail: source?.match_id
        ? `本地未保存赛事情报，已有源站编号 ${source.match_id}。`
        : "本地未保存赛事情报，尚未证明懂球帝或雷速没有这些字段。",
      tone: "bad"
    });
  }

  const hasLeisuSnapshot = (detail.odds_snapshot.latest_rows || []).some((row) => row.provider === "leisu")
    || detail.odds_snapshot.resolution?.provider === "leisu";
  if (source?.status !== "matched" && !hasLeisuSnapshot) {
    diagnostics.push({
      label: "雷速体育",
      detail: "本场本地尚未保存雷速赛事情报，也没有可展示的雷速赔率快照。",
      tone: "caution"
    });
    return diagnostics;
  }
  const leisuAttempt = contextSourceAttempt(detail, "leisu");
  if (leisuAttempt?.status === "odds_matched_context_not_collected") {
    const leisuMissingLabels = contextAttemptFieldLabels(leisuAttempt, "not_collected");
    diagnostics.push({
      label: "雷速体育",
      detail: `已匹配雷速赛事 ${leisuAttempt.match_id || "未知"} 和赔率快照 ${detail.odds_snapshot.snapshot_count || 0} 条；本条记录尚未保存雷速赛事情报，${(leisuMissingLabels.length ? leisuMissingLabels : ["赛事情报"]).join("、")}等待复算补齐。`,
      tone: "caution"
    });
    return diagnostics;
  }
  if (leisuAttempt?.status === "access_blocked") {
    diagnostics.push({
      label: "雷速体育",
      detail: `已匹配雷速赛事 ${leisuAttempt.match_id || "未知"} 和赔率快照 ${detail.odds_snapshot.snapshot_count || 0} 条；详情接口访问受限，需要雷速 Cookie 或代理，当前只能使用雷速赔率快照。`,
      tone: "bad"
    });
    return diagnostics;
  }
  diagnostics.push({
    label: "雷速体育",
    detail: hasLeisuSnapshot
      ? `雷速体育赔率快照已匹配 ${detail.odds_snapshot.snapshot_count} 条，赛事情报以当前已保存的${sourceLabel}结构化字段为准。`
      : `本条记录未匹配到可展示雷速快照，赛事情报以当前已保存的${sourceLabel}结构化字段为准。`,
    tone: hasLeisuSnapshot ? "good" : "caution"
  });

  return diagnostics;
}

function oddsRowView(row: DashboardMatchDetail["odds_snapshot"]["latest_rows"][number]): OddsSnapshotRowView {
  return {
    ...row,
    providerLabel: PROVIDER_LABELS[row.provider] ?? row.provider,
    marketTypeLabel: marketLabel(row.market_type),
    selectionText: selectionLabel(row.selection, row.market_type),
    oddsText: formatOdds(row.decimal_odds),
    lineText: lineText(row.line)
  };
}

function oddsRowSortKey(row: OddsSnapshotRowView): string {
  return `${row.fetched_at_utc || ""}|${row.source_time_utc || ""}|${row.market_type || ""}|${row.selection || ""}`;
}

function oddsBookmakerGroups(rows: OddsSnapshotRowView[]): OddsSnapshotBookmakerGroup[] {
  const grouped = new Map<string, OddsSnapshotRowView[]>();
  for (const row of rows) {
    const bookmaker = row.bookmaker || row.providerLabel || "未知公司";
    grouped.set(bookmaker, [...(grouped.get(bookmaker) || []), row]);
  }

  return Array.from(grouped.entries()).map(([bookmaker, groupRows]) => {
    const sortedRows = [...groupRows].sort((left, right) => oddsRowSortKey(right).localeCompare(oddsRowSortKey(left)));
    const marketTypes = Array.from(new Set(sortedRows.map((row) => row.market_type))).sort((left, right) => {
      const leftRank = MARKET_TYPE_ORDER[left] ?? 99;
      const rightRank = MARKET_TYPE_ORDER[right] ?? 99;
      if (leftRank !== rightRank) return leftRank - rightRank;
      return left.localeCompare(right);
    });
    const latestFetchedAtUtc = sortedRows.reduce(
      (latest, row) => row.fetched_at_utc > latest ? row.fetched_at_utc : latest,
      ""
    );
    return {
      id: bookmaker,
      bookmaker,
      rowCountText: `${sortedRows.length} 条`,
      marketTypesText: marketTypes.map((item) => marketLabel(item)).join("、") || "盘口未知",
      latestFetchedAtUtc,
      rows: sortedRows
    };
  }).sort((left, right) => {
    if (left.latestFetchedAtUtc !== right.latestFetchedAtUtc) {
      return right.latestFetchedAtUtc.localeCompare(left.latestFetchedAtUtc);
    }
    return left.bookmaker.localeCompare(right.bookmaker);
  });
}

function oddsTrendMarketKey(value: unknown): string {
  const market = stringValue(value, "").toLowerCase();
  if (["1x2", "h2h", "moneyline", "moneyline_1x2"].includes(market)) return "h2h";
  if (["asian_handicap", "spreads", "spread"].includes(market)) return "asian_handicap";
  if (["over_under", "totals", "total"].includes(market)) return "over_under";
  return market;
}

function normalizedTrendText(value: unknown): string {
  return stringValue(value, "")
    .toLowerCase()
    .replace(/\b(fc|cf|afc|sc)\b/g, " ")
    .replace(/[+\-−–—]/g, " ")
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function trendSelectionMatches(row: OddsSnapshotRowView, record: PredictionLedgerRow): boolean {
  const rowSelection = normalizedTrendText(row.selection);
  const recordSelection = normalizedTrendText(record.selection);
  if (!rowSelection || !recordSelection) return true;
  if (rowSelection === recordSelection) return true;
  return rowSelection.includes(recordSelection) || recordSelection.includes(rowSelection);
}

function trendLineMatches(row: OddsSnapshotRowView, record: PredictionLedgerRow): boolean {
  const rowLine = numeric(row.line);
  const recordLine = numeric(record.line);
  if (rowLine === null || recordLine === null) return true;
  return Math.abs(rowLine - recordLine) <= 0.001;
}

function trendObservedAt(row: OddsSnapshotRowView): string {
  return row.source_time_utc || row.fetched_at_utc || "";
}

function trendTimeLabel(value: string): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value.slice(5, 16).replace("T", " ");
  return date.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false
  });
}

function trendRowGroupKey(row: OddsSnapshotRowView): string {
  return [
    oddsTrendMarketKey(row.market_type),
    normalizedTrendText(row.selection),
    row.line === null || row.line === undefined ? "none" : String(row.line)
  ].join("|");
}

function bestTrendGroup(rows: OddsSnapshotRowView[]): OddsSnapshotRowView[] {
  const grouped = new Map<string, OddsSnapshotRowView[]>();
  for (const row of rows) {
    grouped.set(trendRowGroupKey(row), [...(grouped.get(trendRowGroupKey(row)) || []), row]);
  }
  return Array.from(grouped.values()).sort((left, right) => {
    if (right.length !== left.length) return right.length - left.length;
    const rightLatest = right.reduce((latest, row) => trendObservedAt(row) > latest ? trendObservedAt(row) : latest, "");
    const leftLatest = left.reduce((latest, row) => trendObservedAt(row) > latest ? trendObservedAt(row) : latest, "");
    return rightLatest.localeCompare(leftLatest);
  })[0] || [];
}

function oddsTrendTargetRows(
  detail: DashboardMatchDetail,
  rows: OddsSnapshotRowView[]
): { rows: OddsSnapshotRowView[]; targetText: string; basisText: string } {
  const usableRows = rows.filter((row) => {
    const odds = numeric(row.decimal_odds);
    return odds !== null && odds > 1 && Boolean(trendObservedAt(row));
  });
  if (!usableRows.length) {
    return { rows: [], targetText: "暂无可绘制盘口", basisText: "无赔率时间点" };
  }

  const recordMarket = oddsTrendMarketKey(detail.record.market);
  const sameMarketRows = usableRows.filter((row) => oddsTrendMarketKey(row.market_type) === recordMarket);
  const exactRows = sameMarketRows.filter((row) => trendSelectionMatches(row, detail.record) && trendLineMatches(row, detail.record));
  if (exactRows.length) {
    return {
      rows: exactRows,
      targetText: `${marketLabel(recordMarket)} · ${selectionLabel(detail.record.selection, recordMarket)}${detail.record.line !== null && detail.record.line !== undefined ? ` · ${lineText(detail.record.line)}` : ""}`,
      basisText: "当前预测盘口"
    };
  }

  const fallbackRows = sameMarketRows.length ? bestTrendGroup(sameMarketRows) : bestTrendGroup(usableRows);
  const sample = fallbackRows[0];
  if (!sample) {
    return { rows: [], targetText: "暂无可绘制盘口", basisText: "无赔率时间点" };
  }
  const market = oddsTrendMarketKey(sample.market_type);
  return {
    rows: fallbackRows,
    targetText: `${marketLabel(market)} · ${selectionLabel(sample.selection, market)}${sample.line !== null && sample.line !== undefined ? ` · ${lineText(sample.line)}` : ""}`,
    basisText: sameMarketRows.length ? "同盘口类型最多样本" : "最多样本盘口"
  };
}

function oddsTrendIndexText(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toFixed(1);
}

function oddsDistributionSummary(values: number[]): MatchDetailView["oddsTrend"]["distributionSummary"] {
  const sorted = [...values].filter((value) => Number.isFinite(value)).sort((left, right) => left - right);
  if (!sorted.length) {
    return {
      lowOddsText: "—",
      medianOddsText: "—",
      highOddsText: "—",
      spreadText: "—"
    };
  }
  const middle = Math.floor(sorted.length / 2);
  const medianValue = sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
  const low = sorted[0];
  const high = sorted[sorted.length - 1];
  return {
    lowOddsText: formatOdds(low),
    medianOddsText: formatOdds(medianValue),
    highOddsText: formatOdds(high),
    spreadText: (high - low).toFixed(2)
  };
}

function oddsTrendView(detail: DashboardMatchDetail, oddsRows: OddsSnapshotRowView[]): MatchDetailView["oddsTrend"] {
  const target = oddsTrendTargetRows(detail, oddsRows);
  if (!target.rows.length) {
    return {
      mode: "empty",
      title: "暂无赔率走势指数图",
      detail: "本场还没有可绘制的赔率快照。",
      statusText: "等待快照",
      tone: "neutral",
      targetText: target.targetText,
      points: [],
      series: [],
      distributionRows: [],
      distributionSummary: oddsDistributionSummary([])
    };
  }

  const grouped = new Map<string, OddsSnapshotRowView[]>();
  for (const row of target.rows) {
    const bookmaker = row.bookmaker || row.providerLabel || "未知公司";
    grouped.set(bookmaker, [...(grouped.get(bookmaker) || []), row]);
  }
  const bookmakerGroups = Array.from(grouped.entries())
    .map(([bookmaker, groupRows]) => ({
      bookmaker,
      rows: [...groupRows].sort((left, right) => trendObservedAt(left).localeCompare(trendObservedAt(right)))
    }))
    .sort((left, right) => {
      if (right.rows.length !== left.rows.length) return right.rows.length - left.rows.length;
      const rightLatest = trendObservedAt(right.rows[right.rows.length - 1]);
      const leftLatest = trendObservedAt(left.rows[left.rows.length - 1]);
      return rightLatest.localeCompare(leftLatest);
    })
    .slice(0, 8);

  const allTimes = Array.from(new Set(bookmakerGroups.flatMap((group) => group.rows.map(trendObservedAt)))).sort();
  const visibleTimes = allTimes.slice(-24);
  const points = new Map<string, MatchDetailView["oddsTrend"]["points"][number]>();
  for (const observedAt of visibleTimes) {
    points.set(observedAt, {
      observedAtUtc: observedAt,
      label: trendTimeLabel(observedAt)
    });
  }

  const series = bookmakerGroups.map((group, index) => {
    const key = `bookmaker_${index}`;
    const firstOdds = numeric(group.rows[0]?.decimal_odds) || 1;
    let latestIndex: number | null = null;
    for (const row of group.rows) {
      const observedAt = trendObservedAt(row);
      const point = points.get(observedAt);
      const odds = numeric(row.decimal_odds);
      if (!point || odds === null || odds <= 1) continue;
      const indexValue = Number(((odds / firstOdds) * 100).toFixed(2));
      point[key] = indexValue;
      latestIndex = indexValue;
    }
    const latestOdds = numeric(group.rows[group.rows.length - 1]?.decimal_odds);
    return {
      key,
      bookmaker: group.bookmaker,
      color: ODDS_TREND_COLORS[index % ODDS_TREND_COLORS.length],
      latestOddsText: formatOdds(latestOdds),
      latestIndexText: oddsTrendIndexText(latestIndex),
      pointCountText: `${group.rows.length} 点`
    };
  });

  const latestRows = bookmakerGroups.map((group, index) => ({
    group,
    index,
    row: group.rows[group.rows.length - 1],
    odds: numeric(group.rows[group.rows.length - 1]?.decimal_odds),
    latestIndex: numeric(series[index]?.latestIndexText)
  })).filter((item) => item.odds !== null && item.odds > 1);
  const oddsValues = latestRows.map((item) => item.odds as number);
  const lowOdds = oddsValues.length ? Math.min(...oddsValues) : 0;
  const highOdds = oddsValues.length ? Math.max(...oddsValues) : 0;
  const oddsRange = highOdds - lowOdds;
  const distributionRows = latestRows
    .sort((left, right) => (left.odds as number) - (right.odds as number))
    .map((item) => {
      const odds = item.odds as number;
      const position = oddsRange > 0.001 ? ((odds - lowOdds) / oddsRange) * 100 : 50;
      return {
        key: series[item.index]?.key || item.group.bookmaker,
        bookmaker: item.group.bookmaker,
        oddsText: formatOdds(odds),
        indexText: oddsTrendIndexText(item.latestIndex),
        pointCountText: `${item.group.rows.length} 点`,
        positionPercent: `${Math.max(0, Math.min(100, position)).toFixed(1)}%`,
        color: series[item.index]?.color || ODDS_TREND_COLORS[item.index % ODDS_TREND_COLORS.length]
      };
    });
  const distributionSummary = oddsDistributionSummary(oddsValues);

  const chartPoints = Array.from(points.values());
  const hasTrend = visibleTimes.length >= 2 && bookmakerGroups.some((group) => group.rows.length >= 2);
  return {
    mode: hasTrend ? "trend" : "distribution",
    title: hasTrend ? "赔率走势指数图" : "公司赔率横截面",
    detail: hasTrend
      ? `按公司分组，指数以每家公司首个赔率点为 100；当前展示 ${target.basisText}：${target.targetText}。`
      : `当前只有单时间点，先看各公司对 ${target.targetText} 的低赔/高赔分歧；低赔通常代表该公司更压低这个方向回报。`,
    statusText: hasTrend ? "可看走势" : "看公司分歧",
    tone: hasTrend ? "good" : "caution",
    targetText: target.targetText,
    points: chartPoints,
    series,
    distributionRows,
    distributionSummary
  };
}

function matchClvView(detail: DashboardMatchDetail): MatchDetailView["clvTracking"] {
  const tracking = detail.clv_tracking;
  const record = (tracking?.records || [])[0];
  const clv = record?.clv;
  if (!clv || clv.status !== "available") {
    return {
      title: "等待收盘价",
      detail: clv?.reason ? reasonLabel(clv.reason) : "本场暂未匹配到可用于 CLV 的收盘价快照。",
      priceText: "—",
      clvText: "—",
      timeText: "等待快照",
      tone: "neutral"
    };
  }
  const clvReturn = clv.clv_return ?? null;
  const tone: KpiCard["tone"] =
    clvReturn !== null && clvReturn > 0 ? "good" : clvReturn !== null && clvReturn < 0 ? "bad" : "neutral";
  return {
    title: clvReturn !== null && clvReturn > 0 ? "推荐价优于收盘价" : clvReturn !== null && clvReturn < 0 ? "推荐价弱于收盘价" : "推荐价接近收盘价",
    detail: `${clv.closing_bookmaker_count ?? 0} 家公司收盘共识，窗口 ${clv.closing_window_minutes ?? 30} 分钟。`,
    priceText: `推荐 ${formatOdds(clv.prediction_decimal_odds)} / 收盘 ${formatOdds(clv.closing_decimal_odds)}`,
    clvText: formatSignedPercent(clvReturn),
    timeText: clv.latest_closing_snapshot_utc || "—",
    tone
  };
}

function movementTone(direction: unknown): KpiCard["tone"] {
  const value = stringValue(direction, "");
  if (value === "shortening") return "good";
  if (value === "drifting") return "bad";
  if (value === "stable") return "neutral";
  return "caution";
}

function movementStatusText(status: string): string {
  if (status === "available") return "已捕捉走势";
  if (status === "insufficient_history") return "等待更多时间点";
  if (status === "unavailable") return "暂无走势";
  return status || "状态未知";
}

function marketMovementRows(movement: Record<string, unknown>): MatchDetailView["marketMovement"]["rows"] {
  const rawRows = Array.isArray(movement.key_movements)
    ? movement.key_movements.map(objectValue).filter((item) => Object.keys(item).length > 0)
    : [];
  return rawRows.slice(0, 4).map((item, index) => {
    const marketType = stringValue(item.market_type, "");
    const openingLine = numeric(item.opening_line);
    const latestLine = numeric(item.latest_line);
    const lineDelta = numeric(item.line_delta);
    const hasLine = openingLine !== null || latestLine !== null;
    return {
      key: `${marketType}-${stringValue(item.selection_key, "")}-${index}`,
      marketText: marketLabel(marketType) || "盘口",
      selectionText: selectionLabel(item.selection || item.selection_key, marketType),
      directionText: stringValue(item.direction_label, "走势未知"),
      priceText: `${formatOdds(numeric(item.opening_decimal_odds))} -> ${formatOdds(numeric(item.latest_decimal_odds))}`,
      probabilityText: formatSignedPercent(numeric(item.implied_probability_delta)),
      lineText: hasLine
        ? `${lineText(openingLine)} -> ${lineText(latestLine)}${lineDelta ? ` (${lineDelta > 0 ? "+" : ""}${lineDelta})` : ""}`
        : "无盘口线",
      metaText: `${numeric(item.bookmaker_count) ?? 0} 家 · ${numeric(item.snapshot_count) ?? 0} 条`,
      tone: movementTone(item.direction)
    };
  });
}

function marketMovementView(detail: DashboardMatchDetail): MatchDetailView["marketMovement"] {
  const movement = objectValue(detail.odds_snapshot.movement);
  const status = stringValue(movement.status, "unavailable");
  const rows = marketMovementRows(movement);
  if (status === "available") {
    return {
      title: "盘口变化已纳入分析",
      detail: `${numeric(movement.snapshot_count) ?? 0} 条快照，${numeric(movement.bookmaker_count) ?? 0} 家公司；展示开盘到最新的赔率和隐含概率变化。`,
      statusText: movementStatusText(status),
      tone: "good",
      rows
    };
  }
  if ((detail.odds_snapshot.snapshot_count ?? 0) > 0) {
    return {
      title: "已有赔率，但走势样本不足",
      detail: "本场有快照记录，但同一盘口方向还不足两个时间点；当前分析仍以最新赔率和模型概率为主。",
      statusText: movementStatusText(status),
      tone: "caution",
      rows
    };
  }
  return {
    title: "暂无盘口变化证据",
    detail: "本地还没有匹配到多公司时间序列快照；当前只能展示预测使用的盘口或等待采集补齐。",
    statusText: movementStatusText(status),
    tone: "neutral",
    rows: []
  };
}

export function buildMatchDetailView(detail: DashboardMatchDetail): MatchDetailView {
  const record = detail.record;
  const metrics = detail.evidence.core_metrics;
  const action = detail.evidence.final_execution_advice;
  const oddsRows = (detail.odds_snapshot.latest_rows || []).map(oddsRowView);
  const contextSourceLabel = detail.match_context.source?.label || "源站";
  const predictionDiagnostic = predictionDiagnosticView(record, detail.evidence.prediction_diagnostic);
  const probabilityRows: ProbabilityRow[] = [
    { label: "模型概率", value: metrics.model_probability, text: formatPercent(metrics.model_probability) },
    { label: "学习后概率", value: metrics.learned_probability, text: formatPercent(metrics.learned_probability) },
    { label: "市场隐含", value: metrics.market_probability, text: formatPercent(metrics.market_probability) }
  ];
  return {
    title: matchupLabel(record.matchup),
    subtitle: [record.league, predictionDiagnostic.title, marketLabel(record.market)].filter(Boolean).join(" · "),
    marketSummary: `${selectionLabel(record.selection, record.market)} · ${formatOdds(metrics.decimal_odds)} · 价值边际 ${formatSignedPercent(metrics.edge)}`,
    actionText: [actionLabel(action.action), adviceReasonLabel(action.reason)].map((item) => stringValue(item, "")).filter(Boolean).join(" · ") || actionLabel(record.recommendation) || "—",
    probabilityRows,
    candidateRows: candidateRows(detail.evidence.market_candidates),
    dataFlags: dataFlags(evidenceDataCompletenessForDetail(detail)),
    riskFlags: flagLabels(riskFlagsForDetail(detail)),
    timeline: timelineRows(detail.timeline),
    scoreStatusText: predictionScoreText(record),
    predictionDiagnostic,
    contextSourceText: contextSourceText(detail),
    contextDiagnostics: contextDiagnostics(detail),
    sourceAttemptRows: contextSourceAttemptRows(detail),
    contextRows: [
      contextFieldRow("比赛场地", detail.match_context.venue, contextSourceLabel),
      contextFieldRow("天气", detail.match_context.weather, contextSourceLabel),
      contextFieldRow("裁判", detail.match_context.referee, contextSourceLabel)
    ],
    lineup: {
      available: detail.match_context.lineup.available,
      basis: detail.match_context.lineup.basis,
      statusText: lineupStatusText(detail.match_context.lineup, contextSourceLabel),
      home: lineupTeamView(detail.match_context.lineup.home),
      away: lineupTeamView(detail.match_context.lineup.away),
      warnings: flagLabels(detail.match_context.lineup.warnings || [])
    },
    oddsSummary: oddsSummary(detail),
    clvTracking: matchClvView(detail),
    oddsTrend: oddsTrendView(detail, oddsRows),
    marketMovement: marketMovementView(detail),
    oddsRows,
    oddsGroups: oddsBookmakerGroups(oddsRows),
    hasQueryControls: false
  };
}

function dashboardSections(snapshot: DashboardSnapshot): DashboardView["dashboardSections"] {
  const predictionKpis = snapshot.prediction_kpis;
  const effectiveness = snapshot.learning_effectiveness;
  const snapshotSummary = snapshot.market_snapshot_summary;
  const productionTone = snapshot.production_readiness
    ? toneFromSeverity(snapshot.production_readiness.severity)
    : snapshot.prediction_accountability
      ? toneFromSeverity(snapshot.prediction_accountability.severity)
      : "neutral";
  const modelTone = effectiveness ? toneFromSeverity(effectiveness.severity) : "neutral";
  const signalTone = snapshot.recommendation_opportunity
    ? toneFromSeverity(snapshot.recommendation_opportunity.severity)
    : predictionKpis.recommended_count > 0
      ? "good"
      : "caution";
  const dataTone = (snapshotSummary?.total_snapshot_count ?? 0) > 0 ? "good" : "caution";

  return [
    {
      key: "overview",
      label: "概览",
      description: "是否在跑、为何未发布、最新结算",
      badge: `${predictionKpis.total_count ?? 0} 预测`,
      tone: productionTone
    },
    {
      key: "production",
      label: "生产",
      description: "上一轮扫描、上线门禁和阻断项",
      badge: snapshot.production_readiness?.production_ready ? "可发布" : "未发布",
      tone: productionTone
    },
    {
      key: "model",
      label: "模型",
      description: "Brier、rho、回测走势和分桶校准",
      badge: `${effectiveness?.sample_count ?? predictionKpis.settled_count ?? 0} 样本`,
      tone: modelTone
    },
    {
      key: "signals",
      label: "信号",
      description: "推荐、观察台账和候选阻断",
      badge: `${predictionKpis.recommended_count ?? 0} 发布`,
      tone: signalTone
    },
    {
      key: "data",
      label: "数据",
      description: "赔率、赛果、情报和采集健康",
      badge: `${snapshotSummary?.total_snapshot_count ?? 0} 快照`,
      tone: dataTone
    }
  ];
}

export function buildDashboardView(snapshot: DashboardSnapshot): DashboardView {
  const pickRows = snapshot.asian_picks.map(pickView);
  const audit = decisionAudit(snapshot);
  return {
    kpiCards: kpiCards(snapshot),
    dashboardSections: dashboardSections(snapshot),
    strategyLabel: strategyStatusLabel(snapshot.strategy_state),
    primaryPick: pickRows[0] ?? null,
    pickRows,
    predictionRows: (snapshot.prediction_ledger || []).map(predictionRowView),
    matchPhaseCards: matchPhaseCards(snapshot),
    predictionSummary: predictionSummary(snapshot),
    oddsCoveredCount: (snapshot.prediction_ledger || []).filter((row) => row.has_odds_snapshot || (row.odds_snapshot_count ?? 0) > 0).length,
    snapshotProviders: marketSnapshotProviderRows(snapshot),
    snapshotSummary: marketSnapshotSummary(snapshot),
    snapshotEmptyText: marketSnapshotEmptyText(snapshot),
    contextCoverage: contextCoverageView(snapshot),
    filterGroups: filterGroups(snapshot.candidate_filters),
    healthCards: auditHealthCards(snapshot),
    predictionAudit: auditBlock(audit.prediction, audit.prediction.total_count, null),
    recommendationAudit: auditBlock(
      audit.recommendation,
      audit.recommendation.recommended_count,
      Math.max(1, audit.recommendation.recommended_count + audit.recommendation.observation_count)
    ),
    learningAudit: auditBlock(audit.learning, audit.learning.sample_count, audit.learning.min_sample_count),
    settlementAudit: auditBlock(
      audit.settlement,
      audit.settlement.settled_count,
      audit.settlement.open_count + audit.settlement.settled_count
    ),
    oddsAudit: auditBlock(audit.odds, audit.odds.covered_count, audit.odds.ledger_count),
    learningDiagnostics: learningDiagnosticsView(snapshot),
    modelGovernance: modelGovernanceView(snapshot),
    clvTracking: clvTrackingView(snapshot),
    learningEffectiveness: learningEffectivenessView(snapshot),
    backtestCurve: backtestCurveView(snapshot),
    predictionQuality: predictionQualityView(snapshot),
    adaptiveLearningPlan: adaptiveLearningPlanView(snapshot),
    dashboardContract: dashboardContractView(snapshot),
    productionReadiness: productionReadinessView(snapshot),
    productionOps: productionOpsView(snapshot),
    dataSourceHealth: dataSourceHealthView(snapshot),
    predictionAccountability: predictionAccountabilityView(snapshot),
    recommendationOpportunity: recommendationOpportunityView(snapshot),
    recommendationFunnel: recommendationFunnel(snapshot),
    hasQueryControls: false
  };
}
