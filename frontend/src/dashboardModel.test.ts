import { describe, expect, it } from "vitest";
import {
  buildMatchDetailView,
  buildRecordDetailView,
  buildDashboardView,
  formatOdds,
  formatPercent,
  strategyStatusLabel
} from "./dashboardModel";
import type { DashboardMatchDetail, DashboardRecordDetail, DashboardSnapshot } from "./types";

const snapshot: DashboardSnapshot = {
  status: "ok",
  tool: "dashboard_snapshot",
  generated_at_utc: "2026-05-25T05:30:00+00:00",
  db_path: "/data/football_data_mcp_learning.sqlite3",
  kpis: {
    open_records: 39,
    settled_records: 2,
    tracked_only_records: 3,
    duplicate_ignored_records: 4,
    asian_pick_count: 1,
    observation_count: 31,
    calibration_bucket_count: 9,
    strategy_sample_count: 2,
    live_calibration_active: false
  },
  prediction_kpis: {
    total_count: 3,
    recommended_count: 1,
    observation_count: 2,
    open_count: 1,
    settled_count: 2,
    hit_count: 1,
    miss_count: 1,
    hit_rate: 0.5,
    roi: -0.05
  },
  learning_effectiveness: {
    status: "learning_improving",
    severity: "ok",
    title: "学习校准有效",
    detail: "学习后概率优于原始模型和市场隐含概率。",
    sample_count: 24,
    model: {
      sample_count: 24,
      brier_score: 0.2314,
      calibration_error: 0.112,
      avg_probability: 0.612,
      hit_rate: 0.5
    },
    learned: {
      sample_count: 24,
      brier_score: 0.2042,
      calibration_error: 0.061,
      avg_probability: 0.561,
      hit_rate: 0.5
    },
    market: {
      sample_count: 24,
      brier_score: 0.2198,
      calibration_error: 0.083,
      avg_probability: 0.583,
      hit_rate: 0.5
    },
    deltas: {
      learned_brier_minus_model: -0.0272,
      learned_brier_minus_market: -0.0156,
      learned_calibration_error_minus_model: -0.051
    },
    probability_bands: [
      {
        key: "under_45",
        label: "低于 45%",
        min_probability: 0,
        max_probability: 0.45,
        sample_count: 4,
        hit_count: 1,
        hit_rate: 0.25,
        avg_probability: 0.41,
        calibration_error: 0.16,
        brier_score: 0.24,
        roi: -0.35,
        sample_quality: "thin_sample"
      },
      {
        key: "between_45_55",
        label: "45% - 55%",
        min_probability: 0.45,
        max_probability: 0.55,
        sample_count: 8,
        hit_count: 4,
        hit_rate: 0.5,
        avg_probability: 0.51,
        calibration_error: 0.01,
        brier_score: 0.25,
        roi: -0.02,
        sample_quality: "thin_sample"
      },
      {
        key: "between_55_65",
        label: "55% - 65%",
        min_probability: 0.55,
        max_probability: 0.65,
        sample_count: 12,
        hit_count: 8,
        hit_rate: 0.667,
        avg_probability: 0.59,
        calibration_error: 0.077,
        brier_score: 0.21,
        roi: 0.18,
        sample_quality: "thin_sample"
      },
      {
        key: "over_65",
        label: "65% 以上",
        min_probability: 0.65,
        max_probability: null,
        sample_count: 0,
        hit_count: 0,
        hit_rate: null,
        avg_probability: null,
        calibration_error: null,
        brier_score: null,
        roi: null,
        sample_quality: "thin_sample"
      }
    ],
    learning_improved: true,
    beats_market: true,
    deployment_verdict: {
      status: "candidate_for_production_gate",
      severity: "ok",
      title: "学习质量可进入发布评估",
      detail: "学习概率优于原始模型和市场，且已结算收益未触发负收益暂停。",
      production_ready: true,
      action: "allow_gate_evaluation",
      sample_count: 24,
      roi: 0.08,
      reasons: []
    },
    metric_rule: "Brier 分数越低越好；校准误差越低越好。"
  },
  prediction_quality: {
    status: "segments_need_attention",
    severity: "warning",
    title: "观察样本分组偏弱",
    detail: "2 类预测原因中有 2 类回测收益为负，需要继续降权或过滤。",
    summary: {
      total_count: 4,
      settled_count: 3,
      open_count: 1,
      segment_count: 2,
      negative_segment_count: 2,
      best_reason: "no_positive_edge",
      worst_reason: "multi_bookmaker_snapshot_missing"
    },
    segments: [
      {
        key: "no_positive_edge",
        reason: "no_positive_edge",
        label: "无正向边际",
        total_count: 3,
        open_count: 1,
        settled_count: 2,
        hit_count: 1,
        miss_count: 1,
        hit_rate: 0.5,
        roi: -0.1,
        avg_probability: 0.543,
        avg_edge: -0.02,
        odds_covered_count: 1,
        odds_coverage_ratio: 0.333333,
        signal_count: 0,
        sample_quality: "thin_sample",
        tone: "negative",
        adjustment: {
          action: "collect_more_samples",
          label: "继续采样",
          detail: "无正向边际 分组样本不足，暂不自动降权。",
          weight_multiplier: 1,
          formal_gate_eligible: false
        }
      },
      {
        key: "multi_bookmaker_snapshot_missing",
        reason: "multi_bookmaker_snapshot_missing",
        label: "缺少多公司赔率快照",
        total_count: 1,
        open_count: 0,
        settled_count: 1,
        hit_count: 0,
        miss_count: 1,
        hit_rate: 0,
        roi: -1,
        avg_probability: 0.61,
        avg_edge: 0.05,
        odds_covered_count: 0,
        odds_coverage_ratio: 0,
        signal_count: 0,
        sample_quality: "thin_sample",
        tone: "negative",
        adjustment: {
          action: "suppress_reason",
          label: "降权过滤",
          detail: "缺少多公司赔率快照 分组负收益，进入推荐发布前需要降权或过滤。",
          weight_multiplier: 0.5,
          formal_gate_eligible: false
        }
      }
    ]
  },
  dashboard_contract: {
    contract_version: "dashboard_contract_v1",
    status: "warning",
    severity: "warning",
    title: "数据契约已对齐",
    detail: "前端必需 8 个模块，缺失 0 个；推荐发布未开放，预测与回测策略保持开启。",
    policy: {
      prediction_policy: "always_predict_and_backtest",
      formal_recommendation_enabled: false,
      release_gate_status: "paper_only_negative_roi",
      read_only: true
    },
    summary: {
      required_count: 8,
      ok_count: 3,
      warning_count: 4,
      blocked_count: 1,
      missing_required_count: 0,
      frontend_visible_count: 8
    },
    sections: [
      {
        key: "prediction_policy",
        label: "预测策略",
        status: "ok",
        title: "持续预测回测",
        detail: "推荐发布暂停时仍生成观察样本，并持续进入结算回测。",
        current: 3,
        target: 1,
        ratio: 1,
        required: true,
        frontend_visible: true
      },
      {
        key: "prediction_ledger",
        label: "预测台账",
        status: "ok",
        title: "台账已对齐",
        detail: "前端可读取 3 条预测，其中 1 条等待赛果、2 条已回测。",
        current: 3,
        target: 1,
        ratio: 1,
        required: true,
        frontend_visible: true
      },
      {
        key: "settlement_backtest",
        label: "回测结算",
        status: "info",
        title: "回测样本可用",
        detail: "已回测 2 场，1 场等待赛果；20 场以上才适合打开稳定推荐闸门。",
        current: 2,
        target: 20,
        ratio: 0.1,
        required: true,
        frontend_visible: true
      },
      {
        key: "recommendation_gate",
        label: "推荐发布闸门",
        status: "blocked",
        title: "推荐发布暂停",
        detail: "当前回测收益率为负，继续预测并回测，不升级为推荐发布。",
        current: 0,
        target: 1,
        ratio: 0,
        required: true,
        frontend_visible: true
      }
    ]
  },
  recommendation_opportunity: {
    status: "paper_signals_pending",
    severity: "warning",
    title: "有观察信号，尚未升为推荐发布",
    detail: "2 场观察信号已进入回测台账，其中 1 场赔率补齐后等待复算。",
    formal_count: 0,
    paper_count: 3,
    paper_signal_count: 2,
    current_open_count: 3,
    historical_paper_signal_count: 4,
    settled_signal_count: 4,
    no_value_count: 1,
    threshold_ready_count: 1,
    reanalysis_backlog_count: 1,
    missing_snapshot_count: 0,
    gate_thresholds: {
      min_calibrated_probability: 0.58,
      min_value_edge: 0.02,
      min_decimal_odds: 1.65,
      max_decimal_odds: 2.05
    },
    release_gate: {
      status: "paper_only_negative_signal_roi",
      formal_enabled: false,
      severity: "warning",
      title: "推荐发布暂停",
      detail: "正向观察信号回测收益率 -12.0%，继续预测并回测，但不升级为推荐发布。",
      sample_count: 24,
      min_sample_count: 20,
      hit_rate: 0.45,
      roi: -0.12,
      signal_settled_count: 24,
      signal_hit_rate: 0.45,
      signal_roi: -0.12,
      min_signal_sample_count: 20,
      learning_improved: true,
      beats_market: false,
      prediction_policy: "always_predict_and_backtest",
      gates: [
        {
          key: "prediction_policy",
          label: "预测策略",
          status: "ok",
          title: "持续预测回测",
          detail: "推荐发布暂停时仍生成观察样本，并持续进入结算回测。",
          current: 2,
          target: null,
          ratio: 1
        },
        {
          key: "signal_backtest",
          label: "信号回测",
          status: "blocked",
          title: "信号收益为负",
          detail: "正向观察信号收益为负，推荐发布保持暂停。",
          current: -0.12,
          target: 0,
          ratio: null
        },
        {
          key: "global_backtest_roi",
          label: "全局回测",
          status: "warning",
          title: "全局收益为负",
          detail: "包含无价值观察样本的全局收益仅作为风险提示，不单独阻断正向候选升级。",
          current: -0.12,
          target: 0,
          ratio: null
        },
        {
          key: "snapshot_coverage",
          label: "赔率快照",
          status: "ok",
          title: "快照就绪",
          detail: "0 场观察信号缺少多公司赔率快照。",
          current: 0,
          target: 0,
          ratio: 1
        }
      ]
    },
    top_blockers: [
      { reason: "awaiting_reanalysis_after_snapshot", count: 1 },
      { reason: "no_positive_edge", count: 1 }
    ],
    top_candidates: [
      {
        ledger_id: "recommendation:9",
        matchup: "博卡青年女足 vs 飓风女足",
        league: "阿女甲",
        selection: "飓风女足 +1.25",
        recommendation: "immediate_bet",
        primary_blocker: "awaiting_reanalysis_after_snapshot",
        threshold_ready: true,
        has_odds_snapshot: true,
        learned_probability: 0.62,
        probability_gap: 0.04,
        value_edge: 0.055,
        value_edge_gap: 0.035,
        decimal_odds: 1.88,
        odds_snapshot_count: 374
      }
    ]
  },
  context_coverage: {
    total_count: 3,
    source_counts: [
      { status: "matched", provider: "dongqiudi", label: "懂球帝", count: 2 },
      { status: "not_collected", provider: "", label: "暂未采集", count: 1 }
    ],
    fields: [
      {
        key: "venue",
        label: "比赛场地",
        total_count: 3,
        available_count: 1,
        source_empty_count: 1,
        not_collected_count: 1,
        coverage_ratio: 0.333333,
        summary: "1/3 已采集 · 1 源站暂无 · 1 本地未采集"
      },
      {
        key: "weather",
        label: "天气",
        total_count: 3,
        available_count: 2,
        source_empty_count: 1,
        not_collected_count: 0,
        coverage_ratio: 0.666667,
        summary: "2/3 已采集 · 1 源站暂无"
      },
      {
        key: "referee",
        label: "裁判",
        total_count: 3,
        available_count: 1,
        source_empty_count: 1,
        not_collected_count: 1,
        coverage_ratio: 0.333333,
        summary: "1/3 已采集 · 1 源站暂无 · 1 本地未采集"
      },
      {
        key: "lineup",
        label: "阵容",
        total_count: 3,
        available_count: 1,
        source_empty_count: 1,
        not_collected_count: 1,
        coverage_ratio: 0.333333,
        summary: "1/3 已采集 · 1 源站暂无 · 1 本地未采集"
      }
    ],
    summary: "懂球帝已匹配 2/3 场；天气 2/3 场有值。"
  },
  market_snapshot_summary: {
    db_path: "/data/football_data_mcp_snapshots.sqlite3",
    total_snapshot_count: 139,
    event_count: 18,
    bookmaker_count: 12,
    latest_fetched_at_utc: "2026-05-25T05:28:00+00:00",
    provider_count: 1,
    providers: [
      {
        provider: "leisu",
        snapshot_count: 139,
        event_count: 18,
        bookmaker_count: 12,
        market_type_count: 3,
        first_fetched_at_utc: "2026-05-25T04:00:00+00:00",
        latest_fetched_at_utc: "2026-05-25T05:28:00+00:00",
        market_types: ["asian_handicap", "h2h", "over_under"]
      }
    ],
    market_type_counts: [],
    latest_events: []
  },
  strategy_state: {
    key: "asian_handicap:balanced",
    market: "asian_handicap",
    mode: "balanced",
    status: "collecting_samples",
    active: false,
    sample_count: 2,
    hit_rate: 0,
    roi: -1,
    avg_model_probability: 0.605348,
    min_live_sample_count: 20,
    prior_strength: 20,
    min_calibrated_probability: 0.58,
    min_decimal_odds: 1.65,
    max_decimal_odds: 2.05,
    min_value_edge: 0.02,
    updated_at_utc: "2026-05-25T05:29:00+00:00",
    raw: {}
  },
  asian_picks: [
    {
      id: 1,
      league: "日职联",
      matchup: "清水鼓动 vs 大阪钢巴",
      home_team: "清水鼓动",
      away_team: "大阪钢巴",
      kickoff_utc_plus_8: "2026-05-25T19:00:00+08:00",
      market: "asian_handicap",
      selection: "大阪钢巴 +0.25",
      selection_key: "away_cover",
      line: 0.25,
      decimal_odds: 1.82,
      model_probability: 0.586,
      learned_probability: 0.569,
      edge: 0.02,
      recommendation: "immediate_bet",
      stake_level: "small",
      risk_flags: ["lineup_unavailable"],
      caution_flags: [],
      settlement_status: "open",
      created_at_utc: "2026-05-25T05:20:00+00:00"
    }
  ],
  candidate_filters: [
    {
      reason: "value_edge_below_threshold",
      count: 12,
      examples: []
    }
  ],
  recent_settlements: [],
  prediction_ledger: [
    {
      ledger_id: "recommendation:1",
      source: "recommendation",
      source_id: 1,
      prediction_type: "recommendation",
      prediction_type_label: "推荐发布",
      status_label: "命中",
      league: "日职联",
      matchup: "清水鼓动 vs 大阪钢巴",
      home_team: "清水鼓动",
      away_team: "大阪钢巴",
      kickoff_utc_plus_8: "2026-05-25T19:00:00+08:00",
      market: "asian_handicap",
      selection: "大阪钢巴 +0.25",
      selection_key: "away_cover",
      line: 0.25,
      decimal_odds: 1.82,
      model_probability: 0.586,
      learned_probability: 0.569,
      edge: 0.02,
      recommendation: "immediate_bet",
      rejection_reason: "",
      settlement_status: "settled",
      score: "1-2",
      true_result: {
        home_score: 1,
        away_score: 2,
        score: "1-2"
      },
      hit: 1,
      payout_multiplier: 1.82,
      profit_units: 0.82,
      settled_at_utc: "2026-05-25T13:00:00+00:00",
      created_at_utc: "2026-05-25T05:20:00+00:00",
      has_odds_snapshot: true,
      odds_snapshot_count: 219,
      odds_bookmaker_count: 12,
      odds_market_type_count: 3,
      odds_latest_fetched_at_utc: "2026-05-25T08:15:00+00:00"
    },
    {
      ledger_id: "shadow:2",
      source: "shadow_prediction",
      source_id: 2,
      prediction_type: "observation",
      prediction_type_label: "观察样本",
      status_label: "等待赛果",
      league: "韩K2",
      matchup: "坡州开拓者 vs 金浦",
      home_team: "坡州开拓者",
      away_team: "金浦",
      kickoff_utc_plus_8: "2026-05-25T20:00:00+08:00",
      market: "asian_handicap",
      selection: "金浦 -0.5",
      selection_key: "away_cover",
      line: -0.5,
      decimal_odds: 1.78,
      model_probability: 0.52,
      learned_probability: 0.52,
      edge: -0.01,
      recommendation: "no_value",
      rejection_reason: "no_positive_edge",
      settlement_status: "open",
      score: "",
      true_result: {
        home_score: null,
        away_score: null,
        score: ""
      },
      hit: null,
      payout_multiplier: null,
      profit_units: null,
      settled_at_utc: "",
      created_at_utc: "2026-05-25T05:25:00+00:00",
      has_odds_snapshot: false,
      odds_snapshot_count: 0,
      odds_bookmaker_count: 0,
      odds_market_type_count: 0,
      odds_latest_fetched_at_utc: ""
    }
  ],
  backtest_curve: {
    status: "positive_roi",
    severity: "ok",
    title: "回测走势为正",
    detail: "已按结算时间串联 2 场预测，展示累计收益、最大回撤和最近 10 场滚动命中率。",
    summary: {
      settled_count: 2,
      hit_count: 1,
      miss_count: 1,
      hit_rate: 0.5,
      profit_units: 0.02,
      roi: 0.01,
      max_drawdown_units: -0.8,
      longest_loss_streak: 1,
      current_streak_type: "miss",
      current_streak_count: 1,
      rolling_window: 10
    },
    points: [
      {
        index: 1,
        ledger_id: "recommendation:1",
        matchup: "清水鼓动 vs 大阪钢巴",
        prediction_type_label: "推荐发布",
        at_utc: "2026-05-25T13:00:00+00:00",
        hit: 1,
        profit_units: 0.82,
        cumulative_profit: 0.82,
        roi: 0.82,
        drawdown_units: 0,
        rolling_hit_rate: 1
      },
      {
        index: 2,
        ledger_id: "recommendation:3",
        matchup: "水原三星蓝翼 vs 天安城",
        prediction_type_label: "观察样本",
        at_utc: "2026-05-25T14:00:00+00:00",
        hit: 0,
        profit_units: -0.8,
        cumulative_profit: 0.02,
        roi: 0.01,
        drawdown_units: -0.8,
        rolling_hit_rate: 0.5
      }
    ]
  },
  learning_events: [
    {
      kind: "strategy",
      severity: "info",
      title: "策略状态刷新",
      detail: "collecting_samples · samples=2 · minP=0.58",
      at_utc: "2026-05-25T05:29:00+00:00"
    }
  ],
  auto_learning_state: {
    enabled: true,
    run_count: 3,
    last_error: null,
    last_result_summary: null
  },
  decision_audit: {
    generated_at_utc: "2026-05-25T05:30:00+00:00",
    prediction: {
      status: "ok",
      title: "预测样本已入库",
      detail: "已形成 3 条预测样本，其中推荐发布 1 条、观察样本 2 条；所有可结算样本都会进入回测。",
      total_count: 3,
      evaluation_count: 3,
      recommended_count: 1,
      observation_count: 2,
      open_count: 1,
      settled_count: 2
    },
    recommendation: {
      status: "ok",
      title: "已有推荐发布",
      detail: "推荐发布 1 场，观察样本 2 场。",
      recommended_count: 1,
      observation_count: 2,
      open_count: 1,
      top_rejection_reasons: [{ reason: "value_edge_below_threshold", count: 12 }]
    },
    learning: {
      status: "info",
      title: "学习样本收集中",
      detail: "已结算 2 场，达到 20 场后才启用实时校准。",
      active: false,
      sample_count: 2,
      min_sample_count: 20,
      settled_count: 2,
      hit_rate: 0.5,
      roi: -0.05
    },
    settlement: {
      status: "info",
      title: "部分样本已结算",
      detail: "已结算 2 场，等待赛果 1 场。",
      open_count: 1,
      settled_count: 2,
      hit_count: 1,
      miss_count: 1
    },
    odds: {
      status: "ok",
      title: "赔率快照已覆盖",
      detail: "台账 1/2 场有赔率快照，共 139 条。",
      covered_count: 1,
      ledger_count: 2,
      coverage_ratio: 0.5,
      snapshot_count: 139,
      bookmaker_count: 12
    },
    health_items: [
      {
        key: "prediction",
        label: "预测",
        status: "ok",
        title: "预测样本已入库",
        detail: "已形成 3 条预测样本，其中推荐发布 1 条、观察样本 2 条；所有可结算样本都会进入回测。",
        current: 3,
        target: null,
        ratio: 1
      },
      {
        key: "recommendation",
        label: "推荐",
        status: "ok",
        title: "已有推荐发布",
        detail: "推荐发布 1 场，观察样本 2 场。",
        current: 1,
        target: null,
        ratio: null
      },
      {
        key: "learning",
        label: "学习",
        status: "info",
        title: "学习样本收集中",
        detail: "已结算 2 场，达到 20 场后才启用实时校准。",
        current: 2,
        target: 20,
        ratio: 0.1
      }
    ]
  },
  learning_diagnostics: {
    status: "collecting_backtest_samples",
    severity: "info",
    title: "回测样本收集中",
    detail: "已回测 2 场，还差 18 场达到实时校准阈值。",
    prediction_total: 3,
    formal_count: 1,
    observation_count: 2,
    open_count: 1,
    settled_count: 2,
    hit_count: 1,
    miss_count: 1,
    backtested_count: 2,
    waiting_result_count: 1,
    ready_for_backtest_count: 3,
    sample_count: 2,
    settled_sample_target: 20,
    remaining_to_live_calibration: 18,
    live_calibration_active: false,
    odds_covered_count: 1,
    odds_ledger_count: 2,
    odds_coverage_ratio: 0.5,
    snapshot_count: 139,
    bookmaker_count: 12,
    reanalysis_backlog_count: 1,
    hit_rate: 0.5,
    roi: -0.05,
    readiness_items: [
      {
        key: "prediction_samples",
        label: "预测样本",
        status: "ok",
        title: "样本已入库",
        detail: "当前共有 3 场预测样本，正式 1 场、观察 2 场。",
        current: 3,
        target: null,
        ratio: 1
      },
      {
        key: "settled_backtest",
        label: "回测结算",
        status: "info",
        title: "等待更多赛果",
        detail: "已回测 2 场，等待赛果 1 场；校准阈值 20 场。",
        current: 2,
        target: 20,
        ratio: 0.1
      },
      {
        key: "reanalysis_queue",
        label: "待复算",
        status: "warning",
        title: "赔率补齐后待复算",
        detail: "1 场赔率已补齐但还需下一轮重新分析。",
        current: 1,
        target: 0,
        ratio: 0
      }
    ],
    top_blockers: [{ reason: "awaiting_reanalysis_after_snapshot", count: 1 }]
  },
  buckets: [],
  policy: {
    read_only: true,
    no_search_inputs: true,
    data_rule: "Dashboard reads persisted MCP paper-learning state"
  }
};

const detail: DashboardRecordDetail = {
  status: "ok",
  tool: "dashboard_record_detail",
  generated_at_utc: "2026-05-25T05:31:00+00:00",
  record: snapshot.asian_picks[0],
  evidence: {
    core_metrics: {
      line: 0.25,
      decimal_odds: 1.82,
      model_probability: 0.586,
      learned_probability: 0.569,
      market_probability: 0.549,
      edge: 0.02,
      expected_multiplier: 1.035
    },
    final_execution_advice: {
      action: "paper_track",
      reason: "balanced threshold passed"
    },
    data_completeness: {
      odds: true,
      schedule: true,
      lineup: false
    },
    live_calibration: {
      active: false,
      sample_count: 2
    },
    market_candidates: [
      {
        selection: "大阪钢巴 +0.25",
        decimal_odds: 1.82,
        calibrated_probability: 0.569,
        edge: 0.02
      }
    ],
    risk_flags: ["lineup_unavailable"],
    caution_flags: ["low_settled_sample"]
  },
  strategy_state: snapshot.strategy_state,
  timeline: [
    {
      title: "推荐入库",
      detail: "shortlist_value_matches · balanced",
      at_utc: "2026-05-25T05:20:00+00:00"
    }
  ],
  policy: {
    read_only: true,
    no_real_bet: true,
    data_rule: "Details read persisted evidence only"
  }
};

const matchDetail: DashboardMatchDetail = {
  status: "ok",
  tool: "dashboard_match_detail",
  generated_at_utc: "2026-05-25T05:32:00+00:00",
  record: snapshot.prediction_ledger[0],
  match_context: {
    source: {
      status: "matched",
      provider: "dongqiudi",
      label: "懂球帝",
      match_id: "543210",
      detail: "懂球帝已匹配比赛 543210"
    },
    venue: { available: true, text: "IAI 日本平球场" },
    weather: { available: true, text: "多云 18C" },
    referee: { available: true, text: "山本雄大" },
    lineup: {
      available: true,
      basis: "official_lineups",
      home: {
        formation: "4-3-3",
        starter_count: 11,
        starters: [{ name: "北川航也", position: "F", shirt_number: "23", nationality: "", captain: false }]
      },
      away: {
        formation: "4-2-3-1",
        starter_count: 11,
        starters: [{ name: "一森纯", position: "G", shirt_number: "22", nationality: "", captain: false }]
      },
      warnings: [],
      analysis: {}
    },
    players: {
      available: true,
      home: [{ name: "北川航也", position: "F", shirt_number: "23", nationality: "", captain: false }],
      away: [{ name: "一森纯", position: "G", shirt_number: "22", nationality: "", captain: false }]
    },
    available_blocks: ["venue", "weather", "referee", "lineup"]
  },
  odds_snapshot: {
    snapshot_count: 2,
    bookmaker_count: 2,
    bookmakers: ["公司A", "公司B"],
    market_types: ["asian_handicap"],
    latest_fetched_at_utc: "2026-05-25T08:15:00+00:00",
    latest_source_time_utc: "2026-05-25T08:10:00+00:00",
    latest_rows: [
      {
        provider: "leisu",
        bookmaker: "公司B",
        market_type: "asian_handicap",
        selection: "大阪钢巴 +0.25",
        decimal_odds: 1.82,
        line: 0.25,
        source_time_utc: "2026-05-25T08:10:00+00:00",
        fetched_at_utc: "2026-05-25T08:15:00+00:00"
      }
    ],
    consensus: {}
  },
  evidence: detail.evidence,
  strategy_state: snapshot.strategy_state,
  timeline: detail.timeline,
  policy: detail.policy
};

describe("dashboard model", () => {
  it("formats probabilities and odds for compact panels", () => {
    expect(formatPercent(0.586)).toBe("58.6%");
    expect(formatPercent(null)).toBe("—");
    expect(formatOdds(1.82)).toBe("1.82");
  });

  it("labels strategy status with the activation threshold", () => {
    expect(strategyStatusLabel(snapshot.strategy_state)).toBe("收集中 2/20");
  });

  it("builds dashboard view model without query controls", () => {
    const segmentedSnapshot = {
      ...snapshot,
      prediction_kpis: {
        ...snapshot.prediction_kpis,
        recommended_settled_count: 1,
        recommended_hit_count: 1,
        recommended_hit_rate: 1,
        recommended_roi: 0.82,
        observation_settled_count: 1,
        observation_hit_count: 0,
        observation_hit_rate: 0,
        observation_roi: -1
      }
    } as unknown as DashboardSnapshot;
    const view = buildDashboardView(segmentedSnapshot);

    expect(view.kpiCards.map((item) => item.label)).toEqual([
      "预测样本",
      "推荐发布",
      "观察样本",
      "等待回测",
      "已回测",
      "学习状态"
    ]);
    expect(view.dashboardSections.map((section) => section.key)).toEqual(["overview", "production", "model", "signals", "data"]);
    expect(view.dashboardSections.map((section) => `${section.label}:${section.badge}`)).toEqual([
      "概览:3 预测",
      "生产:未发布",
      "模型:24 样本",
      "信号:1 发布",
      "数据:139 快照"
    ]);
    expect(view.primaryPick?.matchup).toBe("清水鼓动 对 大阪钢巴");
    expect(view.primaryPick?.learnedProbabilityText).toBe("56.9%");
    expect(view.filterGroups[0].label).toBe("价值边际不足");
    expect(view.predictionRows[0].statusText).toBe("命中");
    expect(view.predictionRows[0].scoreText).toBe("1-2");
    expect(view.predictionRows[0].oddsCoverageText).toBe("快照 219 条 · 12 家");
    expect(view.predictionRows[1].statusText).toBe("等待赛果");
    expect(view.predictionRows[1].oddsCoverageText).toBe("暂无快照");
    expect(view.oddsCoveredCount).toBe(1);
    expect(view.predictionSummary).toBe("共 3 场 · 发布 1 场 · 观察 2 场 · 已结算 2 场 · 等待赛果 1 场 · 发布命中 1/1 · 观察命中 0/1 · 收益率 -5.0%");
    expect(view.snapshotSummary).toBe("共 139 条 · 18 场 · 12 家公司");
    expect(view.snapshotProviders[0].providerLabel).toBe("雷速体育");
    expect(view.snapshotProviders[0].marketTypesText).toBe("亚盘、胜平负、大小球");
    expect(view.healthCards[0].label).toBe("预测");
    expect(view.healthCards[0].title).toBe("预测样本已入库");
    expect(view.predictionAudit.progressText).toBe("3");
    expect(view.recommendationFunnel[0].label).toBe("价值边际不足");
    expect(view.learningAudit.progressText).toBe("2/20");
    expect(view.learningDiagnostics.title).toBe("回测样本收集中");
    expect(view.learningDiagnostics.metrics.map((item) => `${item.label}:${item.value}`)).toContain("已回测:2/20");
    expect(view.learningDiagnostics.metrics.map((item) => `${item.label}:${item.value}`)).toContain("待复算:1");
    expect(view.learningDiagnostics.readinessItems.map((item) => item.label)).toContain("回测结算");
    expect(view.learningDiagnostics.blockerRows[0].label).toBe("赔率已补齐待复算");
    expect(view.backtestCurve.title).toBe("回测走势为正");
    expect(view.backtestCurve.metrics.map((item) => `${item.label}:${item.value}`)).toEqual([
      "累计收益:+0.02",
      "最大回撤:-0.80",
      "滚动命中:50.0%",
      "当前连段:未命中 1"
    ]);
    expect(view.backtestCurve.points.map((point) => `${point.index}:${point.cumulativeText}:${point.drawdownText}:${point.rollingHitText}`)).toEqual([
      "1:+0.82:0.00:100.0%",
      "2:+0.02:-0.80:50.0%"
    ]);
    expect(JSON.stringify(view.backtestCurve)).not.toMatch(/positive_roi|negative_roi|current_streak_type/);
    expect(view.learningEffectiveness.title).toBe("学习校准有效");
    expect(view.learningEffectiveness.metrics.map((item) => `${item.label}:${item.value}`)).toEqual([
      "学习后 Brier:0.2042",
      "原始模型 Brier:0.2314",
      "市场 Brier:0.2198",
      "相对模型:-0.0272"
    ]);
    expect(view.learningEffectiveness.summaryRows.map((row) => `${row.label}:${row.value}`)).toContain("是否优于市场:是");
    expect(view.learningEffectiveness.deploymentVerdict).toEqual({
      title: "学习质量可进入发布评估",
      detail: "学习概率优于原始模型和市场，且已结算收益未触发负收益暂停。",
      actionText: "允许进入发布评估",
      statusText: "可进入发布闸门",
      tone: "good",
      sampleText: "24 场",
      roiText: "+8.0%",
      reasonsText: "无额外阻断"
    });
    expect(view.learningEffectiveness.bandRows.map((row) => `${row.label}:${row.sampleText}:${row.hitRateText}:${row.roiText}`)).toEqual([
      "低于 45%:4 场:25.0%:-35.0%",
      "45% - 55%:8 场:50.0%:-2.0%",
      "55% - 65%:12 场:66.7%:+18.0%",
      "65% 以上:0 场:—:—"
    ]);
    expect(
      [
        view.learningEffectiveness.title,
        view.learningEffectiveness.detail,
        ...view.learningEffectiveness.metrics.map((item) => item.label),
        view.learningEffectiveness.deploymentVerdict.title,
        view.learningEffectiveness.deploymentVerdict.actionText,
        ...view.learningEffectiveness.bandRows.map((item) => `${item.label} ${item.qualityText}`)
      ].join(" ")
    ).not.toMatch(/brier_score|learning_improving|beats_market|allow_gate_evaluation|thin_sample|enough_sample/);
    expect(view.predictionQuality.title).toBe("观察样本分组偏弱");
    expect(view.predictionQuality.metricRows.map((row) => `${row.label}:${row.value}`)).toContain("负收益分组:2");
    expect(view.predictionQuality.segmentRows.map((row) => `${row.label}:${row.totalText}:${row.settledText}:${row.hitRateText}:${row.roiText}`)).toEqual([
      "无正向边际:3 场:已回测 2 场:50.0%:-10.0%",
      "缺少多公司赔率快照:1 场:已回测 1 场:0.0%:-100.0%"
    ]);
    expect(view.predictionQuality.segmentRows.map((row) => `${row.label}:${row.adjustmentLabel}:${row.weightText}`)).toEqual([
      "无正向边际:继续采样:权重 1.00",
      "缺少多公司赔率快照:降权过滤:权重 0.50"
    ]);
    expect(JSON.stringify(view.predictionQuality)).not.toMatch(/no_positive_edge|multi_bookmaker_snapshot_missing|thin_sample|negative|collect_more_samples|suppress_reason/);
    expect(view.dashboardContract.title).toBe("数据契约已对齐");
    expect(view.dashboardContract.metricRows.map((row) => `${row.label}:${row.value}`)).toContain("缺失模块:0");
    expect(view.dashboardContract.sectionRows.map((row) => `${row.label}:${row.title}:${row.progressText}`)).toEqual([
      "预测策略:持续预测回测:3/1",
      "预测台账:台账已对齐:3/1",
      "回测结算:回测样本可用:2/20",
      "推荐发布闸门:推荐发布暂停:0/1"
    ]);
    expect(JSON.stringify(view.dashboardContract)).not.toMatch(/dashboard_contract_v1|always_predict_and_backtest|paper_only_negative_roi|blocked/);
    expect(view.hasQueryControls).toBe(false);
  });

  it("surfaces production readiness without raw internal labels", () => {
    const view = buildDashboardView({
      ...snapshot,
      production_readiness: {
        status: "paper_validation",
        severity: "warning",
        title: "预测闭环运行中，未达推荐发布标准",
        detail: "已有 24 条预测和 24 条回测；但仍有 3 个阻断项，推荐发布应保持关闭。",
        is_toy: false,
        production_ready: false,
        recommended_action: "continue_paper_validation_or_retrain",
        summary: {
          prediction_total: 24,
          settled_count: 24,
          open_count: 0,
          hit_rate: 0.41,
          roi: -0.12,
          learning_improved: false,
          beats_market: false,
          formal_recommendation_enabled: false,
          blocked_count: 3,
          warning_count: 1
        },
        gates: [
          {
            key: "prediction_loop",
            label: "预测闭环",
            status: "ok",
            title: "已持续预测",
            detail: "台账共有 24 条预测。",
            current: 24,
            target: 1,
            ratio: 1
          },
          {
            key: "learning_effectiveness",
            label: "学习效果",
            status: "blocked",
            title: "学习未证明有效",
            detail: "学习后概率暂未优于原始模型。",
            current: 0,
            target: 1,
            ratio: 0
          }
        ]
      }
    } as unknown as DashboardSnapshot);

    expect(view.productionReadiness.title).toBe("推荐服务验证中");
    expect(view.productionReadiness.metrics.map((item) => `${item.label}:${item.value}:${item.caption}`)).toEqual([
      "系统状态:运行中:已有预测闭环",
      "推荐发布:否:继续验证",
      "已回测:24:0 场等待赛果",
      "验证收益:-12.0%:命中率 41.0%"
    ]);
    expect(view.productionReadiness.gateRows.map((item) => `${item.label}:${item.statusText}`)).toEqual([
      "预测闭环:通过",
      "学习效果:阻断"
    ]);
    expect(JSON.stringify(view.productionReadiness)).not.toMatch(/paper_validation|continue_paper_validation_or_retrain|blocked|玩具|空壳|重训|生产推荐/);
  });

  it("builds a production command center from release gates and auto learning state", () => {
    const view = buildDashboardView({
      ...snapshot,
      generated_at_utc: "2026-05-26T11:30:00+00:00",
      kpis: {
        ...snapshot.kpis,
        strategy_sample_count: 99,
        live_calibration_active: true
      },
      prediction_kpis: {
        ...snapshot.prediction_kpis,
        total_count: 185,
        recommended_count: 0,
        observation_count: 185,
        settled_count: 101,
        open_count: 84,
        hit_rate: 0.346535,
        roi: -0.225
      },
      strategy_state: {
        ...snapshot.strategy_state,
        status: "live_calibration_active",
        active: true,
        sample_count: 99,
        min_live_sample_count: 20
      },
      clv_tracking: {
        status: "ok",
        method: "closing_line_value_batch_tracking_v1",
        record_count: 30,
        tracked_count: 30,
        skipped_count: 0,
        available_count: 8,
        positive_clv_count: 3,
        positive_clv_rate: 0.375,
        avg_clv_return: -0.002771,
        records: [],
        rule: "CLV 只读取持久化赔率快照。"
      },
      auto_learning_state: {
        enabled: true,
        run_count: 9,
        interval_seconds: 120,
        timezone_name: "Asia/Shanghai",
        limit: 80,
        asian_window_minutes: 10,
        last_started_at_utc: "2026-05-26T11:19:21+00:00",
        last_finished_at_utc: "2026-05-26T11:21:20+00:00",
        last_error: null,
        last_result_summary: {
          saved_record_count: 0,
          asian_record_count: 0,
          asian_learning_observation_record_count: 0,
          asian_shadow_prediction_record_count: 0,
          settled_count: 1,
          shadow_settled_count: 2,
          market_snapshot_sync: {
            enabled: true,
            provider: "leisu",
            status: "error",
            saved_snapshot_count: 0,
            generated_snapshot_count: 0,
            candidate_match_count: 0,
            probed_match_count: 0,
            accessible_match_count: 0,
            promotable_match_count: 0,
            db_path: "/data/football_data_mcp_snapshots.sqlite3"
          },
          snapshot_reanalysis: {
            enabled: true,
            status: "ok",
            candidate_count: 2,
            reanalyzed_count: 0,
            formal_promoted_count: 0,
            still_observation_count: 0,
            failed_count: 0,
            skipped_count: 2,
            results: [
              {
                record_id: 170,
                ledger_id: "recommendation:170",
                status: "skipped",
                reason: "outside_near_kickoff_window",
                minutes_to_kickoff: 163.9
              }
            ]
          }
        },
        last_market_snapshot_sync: {
          enabled: true,
          provider: "leisu",
          status: "error",
          saved_snapshot_count: 0,
          generated_snapshot_count: 0,
          candidate_match_count: 0,
          probed_match_count: 0,
          accessible_match_count: 0,
          promotable_match_count: 0,
          db_path: "/data/football_data_mcp_snapshots.sqlite3"
        }
      },
      production_readiness: {
        status: "paper_validation",
        severity: "warning",
        title: "预测闭环运行中，未达推荐发布标准",
        detail: "已有 185 条预测和 101 条回测；但仍有 4 个阻断项，正式推荐应保持关闭。",
        is_toy: false,
        production_ready: false,
        recommended_action: "continue_paper_validation_or_retrain",
        summary: {
          prediction_total: 185,
          settled_count: 101,
          open_count: 84,
          hit_rate: 0.346535,
          roi: -0.225,
          learning_improved: true,
          beats_market: true,
          clv_available_count: 8,
          clv_tracked_count: 30,
          avg_clv_return: -0.002771,
          positive_clv_rate: 0.375,
          clv_ready: false,
          formal_recommendation_enabled: false,
          blocked_count: 4,
          warning_count: 0
        },
        gates: [
          {
            key: "paper_roi",
            label: "纸面收益",
            status: "blocked",
            title: "纸面收益为负",
            detail: "当前纸面收益率 -22.5%；负收益时只能继续采样或优化。",
            current: -0.225,
            target: 0,
            ratio: 0
          },
          {
            key: "closing_line_value",
            label: "CLV 收盘价",
            status: "blocked",
            title: "收盘价样本不足",
            detail: "已对齐 8/30 条收盘价；平均 CLV -0.3%。",
            current: 8,
            target: 20,
            ratio: 0.4
          },
          {
            key: "recommendation_gate",
            label: "推荐闸门",
            status: "blocked",
            title: "推荐发布关闭",
            detail: "正式推荐闸门尚未开放。",
            current: 0,
            target: 1,
            ratio: 0
          }
        ]
      }
    } as unknown as DashboardSnapshot);

    expect(view.productionOps.headline).toBe("推荐发布关闭");
    expect(view.productionOps.statusCards.map((item) => `${item.label}:${item.value}:${item.caption}`)).toEqual([
      "自动学习:运行中:2 分钟轮询 · 10 分钟窗口",
      "最近运行:已完成:新增 0 条样本",
      "下一轮:约 2 分钟内:Asia/Shanghai",
      "发布门禁:关闭:4 个阻断项"
    ]);
    expect(view.productionOps.blockerRows.map((item) => `${item.label}:${item.title}:${item.statusText}`)).toEqual([
      "验证收益:验证收益为负:阻断",
      "CLV 收盘价:收盘价样本不足:阻断",
      "发布评估:推荐发布关闭:阻断"
    ]);
    expect(view.productionOps.workflowRows.map((item) => `${item.label}:${item.statusText}:${item.detail}`)).toEqual([
      "抓赛程:通过:自动学习已开启，候选上限 80 场。",
      "抓赔率:异常:赔率快照抓取失败，已保存 0 条。",
      "赛前窗口:注意:2 个候选不在开赛前 10 分钟窗口。",
      "观察样本:观察:上一轮新增 0 条观察样本。",
      "赛果结算:通过:上一轮结算 1 条推荐和 2 条影子样本。",
      "实时校准:通过:实时校准中 99。",
      "CLV 追踪:阻断:8/30 条可计算收盘价价值。",
      "发布门禁:阻断:推荐发布保持关闭。"
    ]);
    expect(JSON.stringify(view.productionOps)).not.toMatch(/paper_validation|outside_near_kickoff_window|formal|blocked|重训|toy/);
  });

  it("surfaces professional model governance and CLV tracking", () => {
    const view = buildDashboardView({
      ...snapshot,
      model_governance: {
        status: "professional_audit_watch",
        severity: "warning",
        title: "专业模型审计观察中",
        detail: "模型引擎证据已入库，仍需更多历史样本和 CLV 样本。",
        summary: {
          record_count: 3,
          model_engine_count: 2,
          model_available_count: 2,
          historical_rho_count: 1,
          market_anchor_count: 2,
          fallback_count: 0,
          calibration_sample_count: 24,
          clv_tracked_count: 2,
          clv_available_count: 1,
          avg_clv_return: 0.04,
          positive_clv_rate: 1
        },
        rho: {
          source_counts: { historical_league_mle: 1, market_snapshot_grid_fit: 1 },
          avg_rho: -0.03,
          historical_avg_rho: -0.08,
          historical_avg_sample_count: 120
        },
        calibration: {
          status: "learning_improving",
          title: "学习校准有效",
          detail: "学习后概率优于原始模型和市场隐含概率。",
          sample_count: 24,
          learning_improved: true,
          beats_market: true,
          active_probability_source: "学习校准",
          shadow_method: "beta_binomial_probability_band_recalibrator_v1",
          shadow_status: "shadow_model_watch_only",
          walk_forward_sample_count: 18,
          walk_forward_brier_delta: 0.004
        },
        clv: {
          status: "ok",
          available_count: 1,
          positive_clv_rate: 1,
          avg_clv_return: 0.04
        },
        method_counts: { dixon_coles_market_anchored_grid: 2 },
        version_counts: { "scoreline-model-v1": 2 },
        checks: [
          {
            key: "dixon_coles_rho",
            label: "Dixon-Coles rho",
            status: "warning",
            title: "等待历史 rho 样本",
            detail: "1/2 条模型记录使用历史联赛 MLE rho；其余记录继续使用盘口网格拟合。",
            current: 1,
            target: 2,
            ratio: 0.5
          },
          {
            key: "clv_tracking",
            label: "CLV 追踪",
            status: "ok",
            title: "已追踪收盘价",
            detail: "1/2 条可计算收盘价价值；平均 CLV +4.0%，正 CLV 100.0%。",
            current: 1,
            target: 2,
            ratio: 0.5
          }
        ],
        rule: "模型审计只读取已入库的 model_engine、结算校准指标和赔率快照，不会创建新的推荐信号。"
      },
      clv_tracking: {
        status: "ok",
        method: "closing_line_value_batch_tracking_v1",
        record_count: 2,
        tracked_count: 2,
        skipped_count: 0,
        available_count: 1,
        positive_clv_count: 1,
        positive_clv_rate: 1,
        avg_clv_return: 0.04,
        records: [
          {
            record_id: 7,
            record_key: "rec-7",
            home_team: "主队A",
            away_team: "客队A",
            market: "asian_handicap",
            selection: "主队A -0.5",
            selection_key: "home_cover",
            status: "available",
            clv: {
              status: "available",
              method: "closing_line_value_from_market_snapshots_v1",
              prediction_decimal_odds: 2.0,
              closing_decimal_odds: 1.92,
              clv_return: 0.041667,
              closing_bookmaker_count: 2,
              closing_window_minutes: 30,
              latest_closing_snapshot_utc: "2026-05-25T11:55:00+00:00"
            }
          }
        ],
        rule: "CLV 只读取已持久化的赔率快照；缺少匹配盘口或只有开赛后价格时保持不可用。"
      }
    } as DashboardSnapshot);

    expect(view.modelGovernance.metrics.map((item) => `${item.label}:${item.value}:${item.caption}`)).toEqual([
      "模型证据:2/3:2 条可审计",
      "历史 rho:1/2:平均 -0.0800",
      "校准样本:24:优于原模型 · 跑赢市场",
      "平均 CLV:+4.0%:正 CLV 100.0%"
    ]);
    expect(view.modelGovernance.checkRows.map((row) => `${row.label}:${row.statusText}:${row.progressText}`)).toEqual([
      "Dixon-Coles rho:注意:1/2",
      "CLV 追踪:通过:1/2"
    ]);
    expect(view.clvTracking.metrics.map((item) => `${item.label}:${item.value}`)).toEqual([
      "可计算:1/2",
      "正 CLV:100.0%",
      "平均 CLV:+4.0%",
      "跳过:0"
    ]);
    expect(view.clvTracking.recordRows[0]).toEqual(expect.objectContaining({
      matchup: "主队A 对 客队A",
      marketText: "亚盘",
      priceText: "2.00 → 1.92",
      clvText: "+4.2%"
    }));
  });

  it("surfaces probability governance when market guardrail is active", () => {
    const view = buildDashboardView({
      ...snapshot,
      prediction_ledger: [
        {
          ...snapshot.prediction_ledger[0],
          governed_probability: 0.52,
          probability_source_label: "市场基准"
        }
      ],
      learning_effectiveness: {
        ...snapshot.learning_effectiveness!,
        probability_governance: {
          status: "market_guardrail_active",
          severity: "warning",
          title: "市场基准优先",
          detail: "学习概率尚未跑赢市场，推荐发布和候选门槛暂时使用市场基准概率保护。",
          active_probability_source: "market_probability",
          active_source_label: "市场基准",
          policy_mode: "market_guardrail",
          production_ready: false,
          threshold_probability_field: "governed_probability",
          guardrails: ["学习未跑赢市场", "影子模型走步验证未过"],
          candidates: [
            {
              source: "market_probability",
              label: "市场基准",
              sample_count: 24,
              brier_score: 0.2198,
              calibration_error: 0.083,
              rank: 1,
              selected: true
            },
            {
              source: "learned_probability",
              label: "学习校准",
              sample_count: 24,
              brier_score: 0.2242,
              calibration_error: 0.061,
              rank: 2,
              selected: false
            }
          ]
        }
      } as any
    });

    expect(view.learningEffectiveness.probabilityGovernance).toEqual({
      title: "市场基准优先",
      detail: "学习概率尚未跑赢市场，推荐发布和候选门槛暂时使用市场基准概率保护。",
      activeText: "当前使用：市场基准",
      policyText: "市场保护",
      thresholdText: "门槛概率：治理后概率",
      guardrailsText: "学习未跑赢市场、影子模型走步验证未过",
      tone: "caution",
      candidateRows: [
        "市场基准:0.2198:0.0830:已选用",
        "学习校准:0.2242:0.0610:观察"
      ]
    });
    expect(view.predictionRows[0].probabilityText).toBe("52.0% · 市场基准");
    expect(JSON.stringify(view.learningEffectiveness.probabilityGovernance)).not.toMatch(/market_guardrail_active|market_probability|learned_probability|governed_probability/);
  });

  it("labels shadow walk-forward probability governance without saying learning lost to market", () => {
    const view = buildDashboardView({
      ...snapshot,
      learning_effectiveness: {
        ...snapshot.learning_effectiveness!,
        probability_governance: {
          status: "shadow_walk_forward_guardrail_active",
          severity: "warning",
          title: "走步验证保护",
          detail: "学习概率已优于市场，但影子重校准走步验证未过；正式候选门槛暂时使用市场基准保护。",
          active_probability_source: "market_probability",
          active_source_label: "市场基准",
          policy_mode: "shadow_walk_forward_guardrail",
          production_ready: false,
          threshold_probability_field: "governed_probability",
          guardrails: ["影子模型走步验证未过"],
          candidates: []
        }
      } as any
    });

    expect(view.learningEffectiveness.probabilityGovernance).toEqual(expect.objectContaining({
      title: "走步验证保护",
      detail: "学习概率已优于市场，但影子重校准走步验证未过；正式候选门槛暂时使用市场基准保护。",
      policyText: "走步保护",
      guardrailsText: "影子模型走步验证未过"
    }));
    expect(JSON.stringify(view.learningEffectiveness.probabilityGovernance)).not.toMatch(/shadow_walk_forward_guardrail|market_probability|尚未跑赢市场/);
  });

  it("renders shadow walk-forward gates as Chinese production blockers", () => {
    const view = buildDashboardView({
      ...snapshot,
      recommendation_opportunity: {
        ...snapshot.recommendation_opportunity!,
        release_gate: {
          ...snapshot.recommendation_opportunity!.release_gate!,
          status: "paper_only_shadow_walk_forward",
          formal_enabled: false,
          severity: "warning",
          title: "走步验证未过",
          detail: "影子模型走步验证未过，继续观察样本。",
          gates: [
            {
              key: "shadow_walk_forward",
              label: "走步验证",
              status: "blocked",
              title: "走步验证未过",
              detail: "影子重校准模型走步验证 40 场，Brier 变化 +0.0060。样本内改善但走步验证变差，推荐发布保持关闭。",
              current: 0.006,
              target: 0,
              ratio: 0
            }
          ]
        }
      },
      production_readiness: {
        status: "paper_validation",
        severity: "warning",
        title: "预测闭环运行中，未达推荐发布标准",
        detail: "走步验证仍有阻断项。",
        is_toy: false,
        production_ready: false,
        recommended_action: "continue_paper_validation_or_retrain",
        summary: {
          prediction_total: 41,
          settled_count: 40,
          open_count: 1,
          hit_rate: 0.62,
          roi: 0.08,
          learning_improved: true,
          beats_market: true,
          formal_recommendation_enabled: false,
          blocked_count: 1,
          warning_count: 0
        },
        gates: [
          {
            key: "shadow_walk_forward",
            label: "走步验证",
            status: "blocked",
            title: "走步验证未过",
            detail: "影子重校准模型走步验证 40 场，Brier 变化 +0.0060。样本内改善但走步验证变差，推荐发布保持关闭。",
            current: 0.006,
            target: 0,
            ratio: 0
          }
        ]
      }
    } as DashboardSnapshot);

    expect(view.recommendationOpportunity.releaseGate?.title).toBe("走步验证未过");
    expect(view.recommendationOpportunity.releaseGate?.gateRows[0]).toEqual(expect.objectContaining({
      label: "走步验证",
      title: "走步验证未过",
      tone: "bad",
      progressText: "+0.0060"
    }));
    expect(view.productionReadiness.gateRows[0]).toEqual(expect.objectContaining({
      label: "走步验证",
      statusText: "阻断",
      progressText: "+0.0060"
    }));
    expect(JSON.stringify({
      releaseGate: view.recommendationOpportunity.releaseGate,
      productionReadiness: view.productionReadiness
    })).not.toMatch(/paper_only_shadow_walk_forward|shadow_walk_forward|blocked/);
  });

  it("labels snapshot-backfilled observations as awaiting reanalysis", () => {
    const baseAudit = snapshot.decision_audit!;
    const view = buildDashboardView({
      ...snapshot,
      candidate_filters: [
        {
          reason: "awaiting_reanalysis_after_snapshot",
          count: 2,
          examples: []
        }
      ],
      decision_audit: {
        ...baseAudit,
        recommendation: {
          ...baseAudit.recommendation,
          top_rejection_reasons: [{ reason: "awaiting_reanalysis_after_snapshot", count: 2 }]
        }
      }
    });

    expect(view.filterGroups[0].label).toBe("赔率已补齐待复算");
    expect(view.recommendationFunnel[0].label).toBe("赔率已补齐待复算");
  });

  it("maps paper prediction diagnostics to Chinese dashboard and detail text", () => {
    const diagnosticRow = {
      ...snapshot.prediction_ledger[1],
      prediction_diagnostic: {
        actionability: "paper_prediction",
        actionability_label: "观察样本",
        recommended: false,
        paper_tracked: true,
        backtest_eligible: true,
        learning_active: true,
        learning_application_status: "down_weight_only",
        learning_application_label: "学习校准仅降权",
        learning_application_detail: "学习校准把概率降低 2.0%，只作为风险降权和持续验证。",
        strategy_status: "live_calibration_active",
        primary_reason: "no_positive_edge",
        primary_reason_label: "无正向边际",
        model_probability: 0.61,
        learned_probability: 0.59,
        market_probability: 0.581,
        learned_adjustment: -0.02,
        thresholds: {
          min_calibrated_probability: 0.66,
          min_value_edge: 0.04,
          min_decimal_odds: 1.7,
          max_decimal_odds: 2.05
        },
        threshold_gaps: {
          probability: -0.07,
          value_edge: -0.05,
          min_decimal_odds: 0.02,
          max_decimal_odds: 0.33
        },
        odds_in_range: true,
        threshold_passed: false,
        diagnostic_summary: "观察样本 · 无正向边际",
        feature_explanations: [
          {
            key: "probability_source",
            label: "概率来源",
            value: "学习校准 59.0%",
            detail: "当前用于门槛判断的是学习后概率。",
            tone: "caution"
          },
          {
            key: "learning_adjustment",
            label: "学习校准",
            value: "-2.0%",
            detail: "模型 61.0% 调整为 59.0%。",
            tone: "caution"
          },
          {
            key: "value_edge",
            label: "价值边际",
            value: "-1.0%",
            detail: "距离推荐发布门槛还差 5.0%。",
            tone: "bad"
          }
        ]
      }
    };
    const view = buildDashboardView({
      ...snapshot,
      prediction_ledger: [diagnosticRow]
    });
    const detailView = buildMatchDetailView({
      ...matchDetail,
      record: diagnosticRow,
      evidence: {
        ...matchDetail.evidence,
        prediction_diagnostic: diagnosticRow.prediction_diagnostic
      }
    });

    expect(view.predictionRows[0].diagnosticLabel).toBe("观察样本 · 参与回测");
    expect(view.predictionRows[0].diagnosticReasonText).toBe("无正向边际");
    expect(view.predictionRows[0].diagnosticGapText).toBe("概率差 -7.0% · 价值差 -5.0%");
    expect(detailView.predictionDiagnostic.title).toBe("观察样本");
    expect(detailView.subtitle).toBe("韩K2 · 观察样本 · 亚盘");
    expect(detailView.predictionDiagnostic.statusText).toBe("参与回测 · 学习校准仅降权");
    expect(detailView.predictionDiagnostic.learningDetail).toBe("学习校准把概率降低 2.0%，只作为风险降权和持续验证。");
    expect(detailView.predictionDiagnostic.gapRows.map((row) => `${row.label}:${row.value}`)).toEqual([
      "概率阈值差:-7.0%",
      "价值边际差:-5.0%",
      "模型校准差:-2.0%",
      "赔率区间:1.70 至 2.05"
    ]);
    expect(detailView.predictionDiagnostic.explanationRows.map((row) => `${row.label}:${row.value}:${row.detail}`)).toEqual([
      "概率来源:学习校准 59.0%:当前用于门槛判断的是学习后概率。",
      "学习校准:-2.0%:模型 61.0% 调整为 59.0%。",
      "价值边际:-1.0%:距离推荐发布门槛还差 5.0%。"
    ]);
    expect(detailView.predictionDiagnostic.explanationRows.map((row) => row.tone)).toEqual(["caution", "caution", "bad"]);
    expect(
      [
        view.predictionRows[0].diagnosticLabel,
        view.predictionRows[0].diagnosticReasonText,
        view.predictionRows[0].diagnosticGapText,
        detailView.predictionDiagnostic.summary,
        JSON.stringify(detailView.predictionDiagnostic.explanationRows)
      ].join(" ")
    ).not.toMatch(/paper_prediction|observation|观察预测|no_positive_edge|live_calibration_active|probability_source|learning_adjustment|value_edge/);
  });

  it("builds production audit view for no-recommendation learning state", () => {
    const noRecommendationSnapshot = {
      ...snapshot,
      kpis: {
        ...snapshot.kpis,
        asian_pick_count: 0,
        observation_count: 12,
        strategy_sample_count: 0,
        live_calibration_active: false
      },
      prediction_kpis: {
        ...snapshot.prediction_kpis,
        total_count: 12,
        recommended_count: 0,
        observation_count: 12,
        open_count: 12,
        settled_count: 0,
        hit_count: 0,
        miss_count: 0,
        hit_rate: null,
        roi: null,
        recommended_settled_count: 0,
        recommended_hit_count: 0,
        observation_settled_count: 0,
        observation_hit_count: 0
      },
      asian_picks: [],
      candidate_filters: [
        { reason: "no_positive_edge", count: 21, examples: [] },
        { reason: "large_handicap_requires_backtest", count: 1, examples: [] }
      ],
      decision_audit: {
        generated_at_utc: "2026-05-25T05:30:00+00:00",
        prediction: {
          status: "ok",
          title: "预测样本已入库",
          detail: "已形成 12 条预测样本，其中推荐发布 0 条、观察样本 12 条；所有可结算样本都会进入回测。",
          total_count: 12,
          evaluation_count: 12,
          recommended_count: 0,
          observation_count: 12,
          open_count: 12,
          settled_count: 0
        },
        recommendation: {
          status: "warning",
          title: "当前无推荐发布",
          detail: "12 场进入观察样本，主要原因：无正向边际。",
          recommended_count: 0,
          observation_count: 12,
          open_count: 12,
          top_rejection_reasons: [
            { reason: "no_positive_edge", count: 21 },
            { reason: "large_handicap_requires_backtest", count: 1 }
          ]
        },
        learning: {
          status: "warning",
          title: "学习尚未生效",
          detail: "还没有已结算样本，模型不会根据命中结果调整概率。",
          active: false,
          sample_count: 0,
          min_sample_count: 20,
          settled_count: 0,
          hit_rate: null,
          roi: null
        },
        settlement: {
          status: "warning",
          title: "等待首批赛果",
          detail: "12 场仍在等待赛果。",
          open_count: 12,
          settled_count: 0,
          hit_count: 0,
          miss_count: 0
        },
        odds: {
          status: "info",
          title: "赔率覆盖不足",
          detail: "台账 4/12 场有赔率快照。",
          covered_count: 4,
          ledger_count: 12,
          coverage_ratio: 0.333333,
          snapshot_count: 900,
          bookmaker_count: 16
        },
        health_items: [
          {
            key: "prediction",
            label: "预测",
            status: "ok",
            title: "预测样本已入库",
            detail: "已形成 12 条预测样本，其中推荐发布 0 条、观察样本 12 条；所有可结算样本都会进入回测。",
            current: 12,
            target: null,
            ratio: 1
          },
          {
            key: "recommendation",
            label: "推荐",
            status: "warning",
            title: "当前无推荐发布",
            detail: "12 场进入观察样本，主要原因：无正向边际。",
            current: 0,
            target: 1,
            ratio: 0
          },
          {
            key: "learning",
            label: "学习",
            status: "warning",
            title: "学习尚未生效",
            detail: "还没有已结算样本，模型不会根据命中结果调整概率。",
            current: 0,
            target: 20,
            ratio: 0
          }
        ]
      }
    } as unknown as DashboardSnapshot;

    const view = buildDashboardView(noRecommendationSnapshot);

    expect(view.healthCards.map((item) => `${item.label}:${item.title}`)).toContain("推荐:当前无推荐发布");
    expect(view.healthCards.map((item) => `${item.label}:${item.title}`)).toContain("预测:预测样本已入库");
    expect(view.predictionAudit.detail).toBe("已形成 12 条预测样本，其中推荐发布 0 条、观察样本 12 条；所有可结算样本都会进入回测。");
    expect(view.recommendationAudit.detail).toBe("12 场进入观察样本，主要原因：无正向边际。");
    expect(view.learningAudit.title).toBe("学习尚未生效");
    expect(view.learningAudit.progressText).toBe("0/20");
    expect(view.recommendationFunnel.map((item) => `${item.label}:${item.countText}`)).toEqual([
      "无正向边际:21 场",
      "大盘口需回测:1 场"
    ]);
  });

  it("keeps open observation totals visible when no predictions have settled", () => {
    const openObservationSnapshot = {
      ...snapshot,
      prediction_kpis: {
        ...snapshot.prediction_kpis,
        total_count: 12,
        recommended_count: 0,
        observation_count: 12,
        open_count: 12,
        settled_count: 0,
        hit_count: 0,
        miss_count: 0,
        hit_rate: null,
        roi: null,
        recommended_settled_count: 0,
        recommended_hit_count: 0,
        recommended_hit_rate: null,
        recommended_roi: null,
        observation_settled_count: 0,
        observation_hit_count: 0,
        observation_hit_rate: null,
        observation_roi: null
      }
    } as unknown as DashboardSnapshot;

    const view = buildDashboardView(openObservationSnapshot);

    expect(view.predictionSummary).toBe("共 12 场 · 发布 0 场 · 观察 12 场 · 已结算 0 场 · 等待赛果 12 场 · 暂无可计算命中率 · 收益率 —");
  });

  it("summarizes prediction accountability above the recommendation gate", () => {
    const accountabilitySnapshot = {
      ...snapshot,
      prediction_accountability: {
        status: "active_paper_validation",
        severity: "warning",
        headline: "推荐发布受风控保护",
        title: "推荐发布受风控保护",
        detail: "当前无推荐发布，但已有 12 条观察样本；0 条已回测，12 条等待赛果。",
        summary: {
          total_predictions: 12,
          formal_recommendations: 0,
          paper_predictions: 12,
          settled_predictions: 0,
          open_predictions: 12,
          hit_rate: null,
          roi: null,
          learning_active: false,
          learning_improved: false,
          beats_market: false,
          formal_gate_enabled: false,
          primary_blocker: "no_positive_edge",
          primary_blocker_label: "无正向边际"
        },
        checks: [
          {
            key: "prediction_loop",
            label: "预测闭环",
            status: "ok",
            title: "正在持续预测",
            detail: "已生成 12 条预测；推荐发布为 0 时仍保留观察样本。",
            current: 12,
            target: 1,
            ratio: 1
          },
          {
            key: "formal_gate",
            label: "推荐闸门",
            status: "warning",
            title: "推荐发布关闭",
            detail: "当前推荐发布 0 条；主要阻断为 无正向边际。",
            current: 0,
            target: 1,
            ratio: 0
          }
        ],
        policy: {
          prediction_policy: "always_predict_and_backtest",
          formal_recommendation_policy: "gate_formal_recommendations_when_learning_or_roi_is_unproven",
          paper_prediction_policy: "persist_every_analysis_ready_signal_for_settlement_backtest",
          no_real_bet: true
        }
      }
    } as unknown as DashboardSnapshot;

    const view = buildDashboardView(accountabilitySnapshot);

    expect(view.predictionAccountability.headline).toBe("推荐发布受风控保护");
    expect(view.predictionAccountability.metrics.map((item) => `${item.label}:${item.value}`)).toEqual([
      "预测样本:12",
      "推荐发布:0",
      "观察样本:12",
      "等待赛果:12"
    ]);
    expect(view.predictionAccountability.checkRows.map((item) => `${item.label}:${item.statusText}`)).toEqual([
      "预测闭环:通过",
      "发布评估:注意"
    ]);
    expect(JSON.stringify(view.predictionAccountability)).not.toMatch(/active_paper_validation|always_predict_and_backtest|no_positive_edge/);
  });

  it("labels live scores without treating them as settled results", () => {
    const liveSnapshot = {
      ...snapshot,
      prediction_kpis: {
        ...snapshot.prediction_kpis,
        live_count: 2,
        scheduled_count: 3,
        final_pending_count: 1,
        result_pending_count: 4,
        match_phase_counts: {
          live: 2,
          scheduled: 3,
          final: 1,
          unknown: 4
        }
      },
      prediction_ledger: [
        {
          ...snapshot.prediction_ledger[1],
          status_label: "比赛进行中",
          score: "1-0",
          score_type: "live",
          true_result: {
            home_score: null,
            away_score: null,
            score: ""
          },
          match_state: {
            phase: "live",
            label: "比赛进行中",
            minute: "42",
            period: "上半场",
            score: "1-0"
          }
        }
      ]
    } as unknown as DashboardSnapshot;

    const view = buildDashboardView(liveSnapshot);

    expect(view.predictionRows[0].statusText).toBe("比赛进行中");
    expect(view.predictionRows[0].scoreText).toBe("实时 1-0");
    expect(view.matchPhaseCards.map((item) => `${item.label}:${item.value}`)).toEqual([
      "比赛进行中:2",
      "未开赛:3",
      "完场待结算:1",
      "赛果待确认:4",
      "已回测:2"
    ]);
  });

  it("explains why odds snapshots are empty after a blocked sync", () => {
    const blockedSnapshot = {
      ...snapshot,
      market_snapshot_summary: {
        ...snapshot.market_snapshot_summary,
        total_snapshot_count: 0,
        event_count: 0,
        bookmaker_count: 0,
        provider_count: 0,
        providers: [],
        latest_fetched_at_utc: null,
        last_sync: {
          status: "partial",
          saved_snapshot_count: 0,
          probed_match_count: 2,
          accessible_match_count: 0,
          promotable_match_count: 0,
          hard_flags: ["leisu_access_waf_challenge"],
          soft_flags: ["leisu_requires_cookie_or_proxy"]
        }
      }
    } as unknown as DashboardSnapshot;

    const view = buildDashboardView(blockedSnapshot);

    expect(view.snapshotSummary).toBe("暂无赔率快照 · 雷速抓取受限");
    expect(view.snapshotEmptyText).toBe("已探测 2 场，0 场可访问；需要雷速登录凭据或代理。");
  });

  it("summarizes data collection health without exposing backend status codes", () => {
    const blockedSnapshot = {
      ...snapshot,
      market_snapshot_summary: {
        ...snapshot.market_snapshot_summary,
        total_snapshot_count: 0,
        event_count: 0,
        bookmaker_count: 0,
        provider_count: 0,
        providers: [],
        latest_fetched_at_utc: null,
        last_sync: {
          provider: "leisu",
          status: "partial",
          saved_snapshot_count: 0,
          probed_match_count: 2,
          accessible_match_count: 0,
          promotable_match_count: 0,
          hard_flags: ["leisu_access_waf_challenge"],
          soft_flags: ["leisu_requires_cookie_or_proxy"],
          at_utc: "2026-05-25T05:29:00+00:00"
        }
      },
      auto_learning_state: {
        enabled: true,
        interval_seconds: 120,
        asian_window_minutes: 10,
        run_count: 5,
        last_market_snapshot_sync: {
          provider: "leisu",
          status: "partial",
          saved_snapshot_count: 0,
          probed_match_count: 2,
          accessible_match_count: 0,
          hard_flags: ["leisu_access_waf_challenge"],
          soft_flags: ["leisu_requires_cookie_or_proxy"],
          at_utc: "2026-05-25T05:29:00+00:00"
        },
        last_snapshot_reanalysis: {
          skipped_count: 3
        }
      }
    } as unknown as DashboardSnapshot;

    const view = buildDashboardView(blockedSnapshot);

    expect(view.dataSourceHealth.title).toBe("数据采集需要关注");
    expect(view.dataSourceHealth.statusCards.map((card) => `${card.label}:${card.value}:${card.caption}`)).toContain(
      "赔率源:部分受限:探测 2 场 · 可访问 0 场 · 保存 0 条"
    );
    expect(view.dataSourceHealth.statusCards.map((card) => `${card.label}:${card.value}:${card.caption}`)).toContain(
      "采集窗口:10 分钟:2 分钟轮询 · 5 轮"
    );
    expect(view.dataSourceHealth.checkRows.map((row) => `${row.label}:${row.title}:${row.statusText}`)).toEqual([
      "赔率抓取:赔率抓取受限:注意",
      "赛前窗口:候选不在分析窗口:注意",
      "台账覆盖:部分预测缺少赔率快照:注意",
      "赛事情报:赛事情报待补齐:注意",
      "收盘价追踪:收盘价样本不足:阻断"
    ]);
    expect(view.dataSourceHealth.issueText).toBe("雷速访问受限；需要雷速登录凭据或代理");
    expect(JSON.stringify(view.dataSourceHealth)).not.toMatch(
      /partial|leisu_access_waf_challenge|leisu_requires_cookie_or_proxy|outside_near_kickoff_window|odds_matched_context_not_collected/
    );
  });

  it("shows healthy data collection cadence when snapshots and coverage are available", () => {
    const healthySnapshot = {
      ...snapshot,
      market_snapshot_summary: {
        ...snapshot.market_snapshot_summary,
        last_sync: {
          provider: "leisu",
          status: "ok",
          saved_snapshot_count: 42,
          probed_match_count: 4,
          accessible_match_count: 4,
          at_utc: "2026-05-25T05:29:00+00:00"
        }
      },
      auto_learning_state: {
        enabled: true,
        interval_seconds: 120,
        asian_window_minutes: 10,
        run_count: 5,
        last_market_snapshot_sync: {
          provider: "leisu",
          status: "ok",
          saved_snapshot_count: 42,
          probed_match_count: 4,
          accessible_match_count: 4,
          at_utc: "2026-05-25T05:29:00+00:00"
        },
        last_snapshot_reanalysis: {
          skipped_count: 0
        }
      },
      clv_tracking: {
        ...snapshot.clv_tracking,
        tracked_count: 32,
        available_count: 31,
        readiness: {
          status: "ok",
          severity: "ok",
          title: "收盘价样本充足",
          detail: "CLV 样本已达到最低门槛。",
          current: 31,
          target: 30,
          ratio: 1
        }
      }
    } as unknown as DashboardSnapshot;

    const view = buildDashboardView(healthySnapshot);

    expect(view.dataSourceHealth.title).toBe("数据采集正常");
    expect(view.dataSourceHealth.statusCards.map((card) => `${card.label}:${card.value}`)).toEqual([
      "赔率源:正常",
      "赔率快照:139 条",
      "台账覆盖:1/2",
      "采集窗口:10 分钟"
    ]);
    expect(view.dataSourceHealth.checkRows.map((row) => `${row.label}:${row.title}:${row.statusText}`)).toEqual([
      "赔率抓取:上一轮已保存赔率快照:通过",
      "赛前窗口:仅分析赛前窗口内比赛:通过",
      "台账覆盖:赔率覆盖可追溯:注意",
      "赛事情报:赛事情报待补齐:注意",
      "收盘价追踪:收盘价样本可用:通过"
    ]);
    expect(view.dataSourceHealth.issueText).toBe("2 项需要关注");
  });

  it("summarizes match context coverage without raw status codes", () => {
    const view = buildDashboardView(snapshot);

    expect(view.contextCoverage.summary).toBe("懂球帝已匹配 2/3 场；天气 2/3 场有值。");
    expect(view.contextCoverage.sourceText).toBe("懂球帝 2 场 · 暂未采集 1 场");
    expect(view.contextCoverage.fields.map((field) => `${field.label}:${field.value}:${field.caption}`)).toContain(
      "比赛场地:1/3:1 源站暂无 · 1 本地未采集"
    );
    expect(JSON.stringify(view.contextCoverage)).not.toMatch(/source_empty|not_collected|dongqiudi/);
  });

  it("labels Leisu odds-only context coverage without implying full context was collected", () => {
    const view = buildDashboardView({
      ...snapshot,
      context_coverage: {
        ...snapshot.context_coverage,
        summary: "懂球帝已匹配 1/1 场；雷速体育赔率已匹配 1/1 场；天气 1/1 场有值。",
        source_counts: [
          { status: "matched", provider: "dongqiudi", label: "懂球帝", count: 1 },
          { status: "odds_matched_context_not_collected", provider: "leisu", label: "雷速体育", count: 1 }
        ]
      }
    } as DashboardSnapshot);

    expect(view.contextCoverage.summary).toBe("懂球帝已匹配 1/1 场；雷速体育赔率已匹配 1/1 场；天气 1/1 场有值。");
    expect(view.contextCoverage.sourceText).toBe("懂球帝 1 场 · 雷速体育 1 场（仅赔率）");
    expect(JSON.stringify(view.contextCoverage)).not.toMatch(/odds_matched_context_not_collected|dongqiudi|leisu/);
  });

  it("summarizes recommendation opportunities without hiding paper predictions", () => {
    const view = buildDashboardView(snapshot);

    expect(view.recommendationOpportunity.title).toBe("有观察信号，尚未升为推荐发布");
    expect(view.recommendationOpportunity.metrics.map((metric) => `${metric.label}:${metric.value}`)).toEqual([
      "推荐发布:0",
      "观察信号:2",
      "已过门槛:1",
      "待复算:1",
      "历史信号:4"
    ]);
    expect(view.recommendationOpportunity.thresholdText).toBe("最低概率 58.0% · 最低边际 +2.0% · 赔率 1.65-2.05");
    expect(view.recommendationOpportunity.releaseGate).toEqual({
      title: "推荐发布暂停",
      detail: "正向观察信号回测收益率 -12.0%，继续预测并回测，但不升级为推荐发布。",
      tone: "caution",
      gateRows: [
        expect.objectContaining({
          label: "预测策略",
          title: "持续预测回测",
          tone: "good",
          progressText: "2"
        }),
        expect.objectContaining({
          label: "信号回测",
          title: "信号收益为负",
          tone: "bad",
          progressText: "-12.0%"
        }),
        expect.objectContaining({
          label: "全局回测",
          title: "全局收益为负",
          tone: "caution",
          progressText: "-12.0%"
        }),
        expect.objectContaining({
          label: "赔率快照",
          title: "快照就绪",
          tone: "good",
          progressText: "无需补齐"
        })
      ]
    });
    expect(view.recommendationOpportunity.candidates[0].blockerLabel).toBe("赔率已补齐待复算");
    expect(view.recommendationOpportunity.candidates[0].probabilityText).toBe("62.0%");
    expect(JSON.stringify(view.recommendationOpportunity)).not.toMatch(/awaiting_reanalysis_after_snapshot|immediate_bet/);
  });

  it("summarizes adaptive learning actions without raw backend codes", () => {
    const adaptiveSnapshot = {
      ...snapshot,
      adaptive_learning_plan: {
        status: "retrain_required",
        severity: "warning",
        title: "需要优化或冻结部分策略",
        detail: "发现 2 个阻断动作、2 个采样动作；正式推荐继续关闭，纸面预测和回测继续运行。",
        summary: {
          action_count: 5,
          blocked_action_count: 2,
          warning_action_count: 2,
          collection_action_count: 2,
          frozen_model_count: 1
        },
        actions: [
          {
            key: "freeze_shadow_recalibration",
            label: "冻结影子重校准",
            status: "blocked",
            title: "走步验证未过",
            detail: "影子重校准只允许继续观察观察，不能替换推荐发布概率。",
            reason: "shadow_walk_forward_failed",
            applies_to: "shadow_recalibration",
            evidence: "走步 Brier 变化 +0.0072",
            current: 0.0072,
            target: 0,
            policy_effect: "冻结升级，只继续样本回测"
          },
          {
            key: "suppress_no_positive_edge",
            label: "降权无正向边际",
            status: "blocked",
            title: "降权过滤",
            detail: "无正向边际 分组已有充分样本且负收益，进入推荐发布前需要降权或过滤。",
            reason: "no_positive_edge",
            applies_to: "prediction_quality_segment",
            evidence: "无正向边际 已回测 63 场，收益率 -15.8%",
            current: -0.1583,
            target: 0,
            policy_effect: "推荐发布前权重 0.50"
          }
        ]
      }
    } as unknown as DashboardSnapshot;

    const view = buildDashboardView(adaptiveSnapshot);

    expect(view.adaptiveLearningPlan.title).toBe("需要优化或冻结部分策略");
    expect(view.adaptiveLearningPlan.detail).toBe("发现 2 个阻断动作、2 个采样动作；推荐发布继续关闭，观察样本和回测继续运行。");
    expect(view.adaptiveLearningPlan.metrics.map((metric) => `${metric.label}:${metric.value}`)).toEqual([
      "动作总数:5",
      "阻断动作:2",
      "采样动作:2",
      "冻结模型:1"
    ]);
    expect(view.adaptiveLearningPlan.actionRows.map((row) => `${row.label}:${row.title}:${row.evidence}:${row.policyEffect}`)).toEqual([
      "冻结影子重校准:走步验证未过:走步 Brier 变化 +0.0072:冻结升级，只继续样本回测",
      "降权无正向边际:降权过滤:无正向边际 已回测 63 场，收益率 -15.8%:推荐发布前权重 0.50"
    ]);
    expect(JSON.stringify(view.adaptiveLearningPlan)).not.toMatch(/freeze_shadow_recalibration|shadow_walk_forward_failed|shadow_recalibration|prediction_quality_segment|blocked|正式推荐|纸面预测|重训/);
  });

  it("shows calibration inversion as a paper-only counter signal without raw model codes", () => {
    const invertedSnapshot = JSON.parse(JSON.stringify(snapshot)) as DashboardSnapshot;
    invertedSnapshot.learning_effectiveness = {
      ...invertedSnapshot.learning_effectiveness!,
      severity: "warning",
      title: "学习效果待提升",
      detail: "学习后概率暂未优于原始模型，需要继续积累样本或调整校准策略。",
      calibration_health: {
        status: "inverted_probability_bands",
        severity: "warning",
        title: "校准方向异常",
        detail: "低概率分桶 低于 45% 当前表现最好：命中率 56.3%、收益率 +16.9%；较高概率分桶反而走弱，推荐发布必须保持关闭。",
        recommended_action: "freeze_formal_recommendations_and_run_band_recalibration",
        best_band_key: "under_45",
        candidate_band_keys: ["under_45"],
        monotonicity_violations: 1,
        meta_model: {
          name: "probability_band_reliability",
          type: "wilson_roi_band_selector",
          min_band_sample_count: 8,
          confidence_z: 1.28
        },
        bands: []
      },
      shadow_recalibration: {
        status: "shadow_model_ready",
        severity: "warning",
        title: "影子重校准模型",
        detail: "影子模型按概率分桶做贝塔-二项后验重校准，当前选中 1 个只用于持续验证的分桶。",
        method: "beta_binomial_probability_band_recalibrator_v1",
        selected_band_keys: ["under_45"],
        quality: {
          sample_count: 36,
          learned_brier_score: 0.2588,
          recalibrated_brier_score: 0.2124,
          brier_delta: -0.0464,
          validation_mode: "walk_forward_prequential",
          walk_forward_sample_count: 36,
          walk_forward_recalibrated_brier_score: 0.238,
          walk_forward_brier_delta: -0.0208
        },
        validation: {
          mode: "walk_forward_prequential",
          sample_count: 12,
          hit_count: 8,
          hit_rate: 0.666667,
          roi: 0.2667,
          walk_forward_brier_score: 0.244
        },
        bands: [
          {
            key: "under_45",
            label: "低于 45%",
            sample_count: 12,
            hit_count: 8,
            hit_rate: 0.666667,
            posterior_probability: 0.642857,
            avg_learned_probability: 0.42,
            avg_market_probability: 0.52,
            posterior_edge: 0.122857,
            expected_multiplier: 1.2363,
            roi: 0.2667,
            selected: true,
            confidence: "thin_sample",
            walk_forward_brier_score: 0.244
          }
        ]
      },
      deployment_verdict: {
        status: "calibration_inversion_guardrail",
        severity: "warning",
        title: "校准方向异常，保持持续验证",
        detail: "低概率分桶 低于 45% 当前表现最好：命中率 56.3%、收益率 +16.9%；较高概率分桶反而走弱，推荐发布必须保持关闭。",
        production_ready: false,
        action: "run_band_recalibration",
        sample_count: 74,
        roi: -0.1,
        reasons: ["not_better_than_market", "probability_bands_inverted"]
      }
    };
    invertedSnapshot.recommendation_opportunity = {
      ...invertedSnapshot.recommendation_opportunity!,
      status: "counter_calibration_watchlist",
      severity: "warning",
      title: "发现反向校准观察样本",
      detail: "当前 1 场落在历史表现较好的低概率分桶；这只作为反向校准观察观察，不作为推荐发布。",
      paper_signal_count: 0,
      counter_signal_count: 1,
      release_gate: {
        ...invertedSnapshot.recommendation_opportunity!.release_gate!,
        status: "paper_only_calibration_guardrail",
        severity: "warning",
        title: "校准异常保护",
        detail: "低概率分桶 低于 45% 当前表现最好：命中率 56.3%、收益率 +16.9%；较高概率分桶反而走弱，推荐发布必须保持关闭。 当前 1 场只进入反向校准观察，不升级为推荐发布。",
        gates: [
          {
            key: "calibration_health",
            label: "校准健康",
            status: "blocked",
            title: "校准方向异常",
            detail: "低概率分桶 低于 45% 当前表现最好：命中率 56.3%、收益率 +16.9%；较高概率分桶反而走弱，推荐发布必须保持关闭。",
            current: 0,
            target: 1,
            ratio: 0
          }
        ]
      },
      counter_signal_rule: {
        status: "inverted_probability_bands",
        title: "校准方向异常",
        detail: "低概率分桶 低于 45% 当前表现最好：命中率 56.3%、收益率 +16.9%；较高概率分桶反而走弱，推荐发布必须保持关闭。",
        candidate_band_keys: ["under_45"],
        meta_model: {
          name: "probability_band_reliability",
          type: "wilson_roi_band_selector",
          min_band_sample_count: 8,
          confidence_z: 1.28
        },
        shadow_recalibration: {
          status: "shadow_model_ready",
          method: "beta_binomial_probability_band_recalibrator_v1",
          quality: {
            sample_count: 36,
            learned_brier_score: 0.2588,
            recalibrated_brier_score: 0.2124,
            brier_delta: -0.0464,
            validation_mode: "walk_forward_prequential",
            walk_forward_sample_count: 36,
            walk_forward_recalibrated_brier_score: 0.238,
            walk_forward_brier_delta: -0.0208
          },
          validation: {
            mode: "walk_forward_prequential",
            sample_count: 12,
            hit_count: 8,
            hit_rate: 0.666667,
            roi: 0.2667,
            walk_forward_brier_score: 0.244
          }
        }
      },
      counter_signal_candidates: [
        {
          ledger_id: "recommendation:31",
          matchup: "CAPS联队 vs 铂金",
          league: "津巴超",
          selection: "铂金 +0.25",
          recommendation: "paper_counter_signal",
          primary_blocker: "no_positive_edge",
          threshold_ready: false,
          has_odds_snapshot: true,
          learned_probability: 0.42,
          probability_gap: -0.16,
          value_edge: -0.03,
          value_edge_gap: -0.05,
          decimal_odds: 1.86,
          odds_snapshot_count: 18,
          meta_signal_label: "反向校准观察",
          meta_signal_reason: "低概率分桶 低于 45% 当前表现最好：命中率 56.3%、收益率 +16.9%；较高概率分桶反而走弱，推荐发布必须保持关闭。",
          probability_band_key: "under_45",
          meta_probability: 0.642857,
          meta_edge: 0.122857,
          meta_expected_multiplier: 1.1957,
          meta_sample_count: 12,
          meta_confidence: "thin_sample"
        }
      ]
    } as DashboardSnapshot["recommendation_opportunity"];

    const view = buildDashboardView(invertedSnapshot);

    expect(view.learningEffectiveness.calibrationHealth).toEqual({
      title: "校准方向异常",
      detail: "低概率分桶 低于 45% 当前表现最好：命中率 56.3%、收益率 +16.9%；较高概率分桶反而走弱，推荐发布必须保持关闭。",
      actionText: "暂停推荐发布并优化分桶",
      modelText: "概率分桶可靠性 · 最小分桶 8 场",
      candidateBandsText: "反向观察分桶：低于 45%",
      tone: "caution"
    });
    expect(view.learningEffectiveness.deploymentVerdict.actionText).toBe("重新校准概率分桶");
    expect(view.learningEffectiveness.deploymentVerdict.statusText).toBe("校准保护中");
    expect(view.learningEffectiveness.deploymentVerdict.reasonsText).toBe("未跑赢市场、概率分桶反向");
    expect(view.learningEffectiveness.shadowRecalibration).toEqual({
      title: "影子重校准模型",
      detail: "影子模型按概率分桶做贝塔-二项后验重校准，当前选中 1 个只用于持续验证的分桶。",
      methodText: "贝塔-二项分桶后验",
      brierText: "0.2588 -> 0.2124",
      brierDeltaText: "-0.0464",
      walkForwardText: "走步验证 36 场 · Brier 0.2380 · 变化 -0.0208",
      validationText: "12 场 · 命中 66.7% · 收益 +26.7%",
      selectedBandsText: "验证分桶：低于 45%",
      tone: "caution"
    });
    expect(view.recommendationOpportunity.metrics.map((metric) => `${metric.label}:${metric.value}`)).toContain("反向观察:1");
    expect(view.recommendationOpportunity.counterSignal?.title).toBe("校准方向异常");
    expect(view.recommendationOpportunity.counterSignal?.candidates[0].signalLabel).toBe("反向校准观察");
    expect(view.recommendationOpportunity.counterSignal?.candidates[0].actionLabel).toBe("反向观察");
    expect(view.recommendationOpportunity.counterSignal?.candidates[0].metaProbabilityText).toBe("64.3%");
    expect(view.recommendationOpportunity.counterSignal?.candidates[0].metaEdgeText).toBe("+12.3%");
    expect(view.recommendationOpportunity.counterSignal?.candidates[0].confidenceText).toBe("样本偏少 · 12 场");
    expect(JSON.stringify({
      calibrationHealth: view.learningEffectiveness.calibrationHealth,
      shadowRecalibration: view.learningEffectiveness.shadowRecalibration,
      deploymentVerdict: view.learningEffectiveness.deploymentVerdict,
      counterSignal: view.recommendationOpportunity.counterSignal
    })).not.toMatch(/inverted_probability_bands|probability_band_reliability|wilson_roi_band_selector|beta_binomial_probability_band_recalibrator_v1|paper_counter_signal|probability_bands_inverted|run_band_recalibration|under_45/);
  });

  it("builds a match detail view from persisted evidence", () => {
    const view = buildRecordDetailView(detail);

    expect(view.title).toBe("清水鼓动 对 大阪钢巴");
    expect(view.subtitle).toBe("日职联 · 亚盘 · 小注");
    expect(view.marketSummary).toBe("大阪钢巴 +0.25 · 1.82 · 价值边际 +2.0%");
    expect(view.actionText).toBe("观察跟踪 · 满足均衡阈值");
    expect(view.probabilityRows.map((row) => row.label)).toEqual(["模型概率", "学习后概率", "市场隐含"]);
    expect(view.probabilityRows[1].text).toBe("56.9%");
    expect(view.candidateRows[0].edgeText).toBe("+2.0%");
    expect(view.dataFlags).toContain("阵容暂未采集");
    expect(view.riskFlags).toContain("阵容暂未采集");
    expect(view.riskFlags).toContain("结算样本偏少");
    expect([...view.dataFlags, ...view.riskFlags].join(" ")).not.toMatch(/lineup_unavailable|low_settled_sample|lineup:missing/);
    expect(view.hasQueryControls).toBe(false);
  });

  it("builds a rich sample detail view with context and odds snapshots", () => {
    const view = buildMatchDetailView(matchDetail);

    expect(view.title).toBe("清水鼓动 对 大阪钢巴");
    expect(view.subtitle).toBe("日职联 · 推荐发布 · 亚盘");
    expect(view.contextSourceText).toBe("懂球帝 · 543210");
    expect(view.contextRows.map((row) => `${row.label}:${row.value}`)).toContain("比赛场地:IAI 日本平球场");
    expect(view.contextRows.map((row) => `${row.label}:${row.value}`)).toContain("天气:多云 18C");
    expect(view.contextRows.map((row) => `${row.label}:${row.value}`)).toContain("裁判:山本雄大");
    expect(view.lineup.home.players[0].name).toBe("北川航也");
    expect(view.oddsSummary).toBe("2 条 · 2 家公司 · 亚盘");
    expect(view.oddsRows[0].bookmaker).toBe("公司B");
    expect(view.hasQueryControls).toBe(false);
  });

  it("exposes live score text in match detail view", () => {
    const view = buildMatchDetailView({
      ...matchDetail,
      record: {
        ...matchDetail.record,
        status_label: "比赛进行中",
        settlement_status: "open",
        score: "1-0",
        score_type: "live",
        true_result: {
          home_score: null,
          away_score: null,
          score: ""
        }
      }
    });

    expect(view.scoreStatusText).toBe("实时 1-0");
  });

  it("separates source-empty context from uncollected context", () => {
    const view = buildMatchDetailView({
      ...matchDetail,
      match_context: {
        ...matchDetail.match_context,
        source: {
          status: "matched",
          provider: "dongqiudi",
          label: "懂球帝",
          match_id: "54465042",
          detail: "懂球帝已匹配比赛 54465042"
        },
        venue: {
          available: false,
          status: "source_empty",
          text: "源站暂无信息",
          source_text: "暂无信息"
        },
        weather: {
          available: false,
          status: "not_collected",
          text: "暂未采集"
        },
        referee: {
          available: true,
          status: "available",
          text: "测试裁判"
        }
      }
    });

    expect(view.contextRows).toEqual([
      expect.objectContaining({ label: "比赛场地", value: "懂球帝暂无信息", statusText: "懂球帝暂无" }),
      expect.objectContaining({ label: "天气", value: "暂未采集", statusText: "本地未采集" }),
      expect.objectContaining({ label: "裁判", value: "测试裁判", statusText: "已采集" })
    ]);
  });

  it("does not imply source sites lack context when local detail has not collected it", () => {
    const view = buildMatchDetailView({
      ...matchDetail,
      odds_snapshot: {
        ...matchDetail.odds_snapshot,
        snapshot_count: 0,
        bookmaker_count: 0,
        bookmakers: [],
        market_types: [],
        latest_rows: [],
        resolution: {
          status: "local_snapshot_missing",
          provider: "",
          event_id: "",
          league: "",
          home_team: "测试主队",
          away_team: "测试客队",
          source_home_team: "",
          source_away_team: "",
          source_league: "",
          match_score: null,
          reason: ""
        }
      },
      match_context: {
        ...matchDetail.match_context,
        source: {
          status: "not_collected",
          provider: "",
          label: "暂未采集",
          match_id: "",
          detail: "本地样本还没有持久化赛事情报。"
        },
        venue: { available: false, status: "not_collected", text: "暂未采集" },
        weather: { available: false, status: "not_collected", text: "暂未采集" },
        referee: { available: false, status: "not_collected", text: "暂未采集" },
        lineup: {
          ...matchDetail.match_context.lineup,
          available: false,
          basis: "",
          home: { formation: "", starter_count: 0, starters: [] },
          away: { formation: "", starter_count: 0, starters: [] },
          warnings: []
        }
      }
    });

    expect(view.contextDiagnostics.map((item) => item.detail)).toEqual([
      "本地未保存赛事情报，尚未证明懂球帝或雷速没有这些字段。",
      "本场本地尚未保存雷速赛事情报，也没有可展示的雷速赔率快照。"
    ]);
  });

  it("explains whether missing context came from source-empty fields or missing leisu snapshots", () => {
    const view = buildMatchDetailView({
      ...matchDetail,
      odds_snapshot: {
        ...matchDetail.odds_snapshot,
        snapshot_count: 0,
        bookmaker_count: 0,
        bookmakers: [],
        market_types: [],
        latest_rows: [],
        resolution: {
          status: "local_snapshot_missing",
          provider: "",
          event_id: "",
          league: "",
          home_team: "博卡青年女足",
          away_team: "飓风女足",
          source_home_team: "",
          source_away_team: "",
          source_league: "",
          match_score: null,
          reason: ""
        }
      },
      match_context: {
        ...matchDetail.match_context,
        source: {
          status: "matched",
          provider: "dongqiudi",
          label: "懂球帝",
          match_id: "54465042",
          detail: "懂球帝已匹配比赛 54465042"
        },
        venue: { available: false, status: "source_empty", text: "源站暂无信息", source_text: "暂无信息" },
        weather: { available: false, status: "source_empty", text: "源站暂无信息", source_text: "" },
        referee: { available: false, status: "source_empty", text: "源站暂无信息", source_text: "暂无信息" },
        lineup: {
          ...matchDetail.match_context.lineup,
          available: false,
          basis: "unavailable",
          home: { formation: "", starter_count: 0, starters: [] },
          away: { formation: "", starter_count: 0, starters: [] },
          warnings: ["lineup unavailable"]
        }
      }
    });

    expect(view.lineup.warnings).toEqual(["阵容暂未采集"]);
    expect(view.lineup.statusText).toBe("懂球帝暂无阵容");
    expect(view.contextDiagnostics.map((item) => item.detail)).toEqual([
      "已查询懂球帝比赛 54465042，比赛场地、天气、裁判、阵容为源站暂无。",
      "本条记录未匹配到可展示雷速快照，赛事情报以当前已保存的懂球帝结构化字段为准。"
    ]);
    expect(JSON.stringify({ diagnostics: view.contextDiagnostics, lineup: view.lineup })).not.toMatch(/source_empty|local_snapshot_missing|lineup unavailable|lineup_unavailable|未识别状态/);
  });

  it("uses source attempts to explain when leisu only supplies odds snapshots", () => {
    const view = buildMatchDetailView({
      ...matchDetail,
      odds_snapshot: {
        ...matchDetail.odds_snapshot,
        snapshot_count: 12,
        bookmaker_count: 4,
        resolution: {
          status: "matched",
          provider: "leisu",
          event_id: "4528570",
          league: "乌兹杯",
          home_team: "纳萨夫",
          away_team: "古佐尔警察",
          source_home_team: "纳萨夫",
          source_away_team: "休尔坦古佐",
          source_league: "乌兹杯",
          match_score: 0.745,
          reason: "same_league_home_alias"
        }
      },
      match_context: {
        ...matchDetail.match_context,
        source: {
          status: "matched",
          provider: "dongqiudi",
          label: "懂球帝",
          match_id: "54435613",
          detail: "懂球帝已匹配比赛 54435613"
        },
        venue: { available: false, status: "source_empty", text: "源站暂无信息", source_text: "暂无信息" },
        weather: { available: false, status: "source_empty", text: "源站暂无信息", source_text: "暂无信息" },
        referee: { available: false, status: "source_empty", text: "源站暂无信息", source_text: "暂无信息" },
        lineup: {
          ...matchDetail.match_context.lineup,
          available: false,
          basis: "unavailable",
          home: { formation: "", starter_count: 0, starters: [] },
          away: { formation: "", starter_count: 0, starters: [] },
          warnings: ["lineup unavailable"]
        },
        source_attempts: [
          {
            provider: "dongqiudi",
            label: "懂球帝",
            status: "matched",
            match_id: "54435613",
            detail: "懂球帝已匹配比赛 54435613",
            field_statuses: {
              venue: "source_empty",
              weather: "source_empty",
              referee: "source_empty",
              lineup: "source_empty"
            }
          },
          {
            provider: "leisu",
            label: "雷速体育",
            status: "odds_matched_context_not_collected",
            match_id: "4528570",
            detail: "已匹配雷速赔率赛事 4528570，赔率快照 12 条；本条记录尚未保存雷速赛事情报，后续复算会尝试从雷速移动端补齐。",
            field_statuses: {
              venue: "not_collected",
              weather: "not_collected",
              referee: "not_collected",
              lineup: "not_collected"
            }
          }
        ]
      } as any
    });

    expect(view.contextDiagnostics.map((item) => item.detail)).toEqual([
      "已查询懂球帝比赛 54435613，比赛场地、天气、裁判、阵容为源站暂无。",
      "已匹配雷速赛事 4528570 和赔率快照 12 条；本条记录尚未保存雷速赛事情报，比赛场地、天气、裁判、阵容等待复算补齐。"
    ]);
    expect(view.sourceAttemptRows.map((item) => `${item.providerText}:${item.statusText}:${item.fieldSummary}`)).toEqual([
      "懂球帝:已匹配:比赛场地源站暂无、天气源站暂无、裁判源站暂无、阵容源站暂无",
      "雷速体育:仅匹配赔率:比赛场地本地未采集、天气本地未采集、裁判本地未采集、阵容本地未采集"
    ]);
    expect(JSON.stringify(view.contextDiagnostics)).not.toMatch(/odds_matched_context_not_collected|source_empty|not_collected|same_league_home_alias/);
    expect(JSON.stringify(view.sourceAttemptRows)).not.toMatch(/odds_matched_context_not_collected|source_empty|not_collected|same_league_home_alias/);
  });

  it("explains blocked Leisu context access separately from source-empty fields", () => {
    const view = buildMatchDetailView({
      ...matchDetail,
      odds_snapshot: {
        ...matchDetail.odds_snapshot,
        snapshot_count: 12,
        bookmaker_count: 4,
        resolution: {
          status: "matched",
          provider: "leisu",
          event_id: "4528570",
          league: "乌兹杯",
          home_team: "纳萨夫",
          away_team: "古佐尔警察",
          source_home_team: "纳萨夫",
          source_away_team: "休尔坦古佐",
          source_league: "乌兹杯",
          match_score: 0.745,
          reason: "same_league_home_alias"
        }
      },
      match_context: {
        ...matchDetail.match_context,
        source: {
          status: "matched",
          provider: "dongqiudi",
          label: "懂球帝",
          match_id: "54435613",
          detail: "懂球帝已匹配比赛 54435613"
        },
        source_attempts: [
          {
            provider: "dongqiudi",
            label: "懂球帝",
            status: "matched",
            match_id: "54435613",
            detail: "懂球帝已匹配比赛 54435613",
            field_statuses: {
              venue: "source_empty",
              weather: "available",
              referee: "source_empty",
              lineup: "source_empty"
            }
          },
          {
            provider: "leisu",
            label: "雷速体育",
            status: "access_blocked",
            match_id: "4528570",
            detail: "雷速体育已匹配比赛 4528570，但详情接口访问受限：403 访问被拒绝；需要雷速 Cookie 或代理。",
            field_statuses: {
              venue: "access_blocked",
              weather: "access_blocked",
              referee: "access_blocked",
              lineup: "access_blocked"
            }
          }
        ]
      } as any
    });

    expect(view.contextDiagnostics.map((item) => item.detail)).toContain(
      "已匹配雷速赛事 4528570 和赔率快照 12 条；详情接口访问受限，需要雷速 Cookie 或代理，当前只能使用雷速赔率快照。"
    );
    expect(view.sourceAttemptRows.map((item) => `${item.providerText}:${item.statusText}:${item.fieldSummary}`)).toContain(
      "雷速体育:访问受限:比赛场地访问受限、天气访问受限、裁判访问受限、阵容访问受限"
    );
    expect(JSON.stringify(view.contextDiagnostics)).not.toMatch(/access_blocked|source_empty|same_league_home_alias/);
    expect(JSON.stringify(view.sourceAttemptRows)).not.toMatch(/access_blocked|source_empty|same_league_home_alias/);
  });

  it("translates match detail timeline internals before display", () => {
    const view = buildMatchDetailView({
      ...matchDetail,
      timeline: [
        {
          title: "推荐入库",
          detail: "snapshot_reanalysis · balanced_observation",
          at_utc: "2026-05-26T00:24:49.834679+00:00"
        },
        {
          title: "策略阈值",
          detail: "live_calibration_active · samples=80 · minP=0.66",
          at_utc: "2026-05-26T00:25:00.472058+00:00"
        },
        {
          title: "赔率快照",
          detail: "100 条 · 7 家公司 · asian_handicap, h2h, over_under",
          at_utc: "2026-05-26T00:01:22.468364+00:00"
        }
      ]
    });

    expect(view.timeline.map((item) => item.detail)).toEqual([
      "赔率补齐复算 · 均衡观察",
      "实时校准已启用 · 样本数 80 · 最低概率 0.66",
      "100 条 · 7 家公司 · 亚盘、胜平负、大小球"
    ]);
    expect(JSON.stringify(view.timeline)).not.toMatch(/snapshot_reanalysis|balanced_observation|live_calibration_active|samples=|minP=|asian_handicap|over_under|h2h/);
  });

  it("uses matched odds snapshots to correct stale completeness flags in detail view", () => {
    const view = buildMatchDetailView({
      ...matchDetail,
      evidence: {
        ...matchDetail.evidence,
        data_completeness: {
          available_blocks: ["schedule", "asian_handicap"],
          missing_blocks: ["multi_bookmaker_snapshot"],
          core_markets_ready: true,
          ratio: 0.5
        },
        risk_flags: ["multi_bookmaker_snapshot_missing"],
        caution_flags: []
      }
    });

    expect(view.dataFlags).toContain("已采集：赛程、亚盘、多公司赔率快照");
    expect(view.dataFlags).toContain("关键数据块完整");
    expect(view.riskFlags).not.toContain("缺少多公司赔率快照");
    expect([...view.dataFlags, ...view.riskFlags].join(" ")).not.toMatch(/multi_bookmaker_snapshot_missing/);
  });

  it("translates backend enum and completeness flags before display", () => {
    const view = buildMatchDetailView({
      ...matchDetail,
      record: {
        ...matchDetail.record,
        recommendation: "no_value"
      },
      evidence: {
        ...matchDetail.evidence,
        final_execution_advice: {},
        data_completeness: {
          available_blocks: ["schedule", "moneyline_1x2", "asian_handicap", "over_under"],
          core_markets_ready: true,
          missing_blocks: ["multi_bookmaker_snapshot", "lineup"],
          ratio: 0.818182
        },
        risk_flags: ["lineup_unavailable"],
        caution_flags: [
          "asian_handicap_consensus_market_line_split",
          "over_under_consensus_total_line_split",
          "near_kickoff_under_60m"
        ]
      }
    });

    expect(view.actionText).toBe("无正价值");
    expect(view.dataFlags).toContain("已采集：赛程、胜平负、亚盘、大小球、多公司赔率快照");
    expect(view.dataFlags).toContain("核心盘口已就绪");
    expect(view.dataFlags).toContain("缺少：阵容");
    expect(view.dataFlags).toContain("数据完整度 81.8%");
    expect(view.riskFlags).toEqual([
      "阵容暂未采集",
      "亚盘公司盘口分歧",
      "大小球公司盘口分歧",
      "临近开赛 60 分钟内"
    ]);
    expect([...view.dataFlags, ...view.riskFlags].join(" ")).not.toMatch(
      /available_blocks|core_markets_ready|missing_blocks|lineup_unavailable|asian_handicap_consensus|over_under_consensus|near_kickoff/
    );
  });

  it("keeps candidate odds visible when multi-bookmaker snapshots are missing", () => {
    const view = buildMatchDetailView({
      ...matchDetail,
      odds_snapshot: {
        ...matchDetail.odds_snapshot,
        snapshot_count: 0,
        bookmaker_count: 0,
        bookmakers: [],
        market_types: [],
        latest_rows: []
      },
      evidence: {
        ...matchDetail.evidence,
        market_candidates: [
          {
            provider: "乐天*",
            market: "asian_handicap",
            selection: "铂金 +0.25",
            decimal_odds: 1.86,
            model_probability: 0.498419,
            edge: -0.0729
          }
        ]
      }
    });

    expect(view.oddsSummary).toBe("暂无赔率快照");
    expect(view.oddsGroups).toEqual([]);
    expect(view.candidateRows[0].selection).toBe("铂金 +0.25");
    expect(view.candidateRows[0].selectionText).toBe("铂金 +0.25");
    expect((view.candidateRows[0] as any).providerText).toBe("乐天*");
  });

  it("groups odds snapshots by bookmaker for collapsible detail display", () => {
    const view = buildMatchDetailView({
      ...matchDetail,
      odds_snapshot: {
        ...matchDetail.odds_snapshot,
        latest_rows: [
          {
            provider: "leisu",
            bookmaker: "公司B",
            market_type: "asian_handicap",
            selection: "大阪钢巴 +0.25",
            decimal_odds: 1.82,
            line: 0.25,
            source_time_utc: "2026-05-25T08:10:00+00:00",
            fetched_at_utc: "2026-05-25T08:15:00+00:00"
          },
          {
            provider: "leisu",
            bookmaker: "公司B",
            market_type: "h2h",
            selection: "Draw",
            decimal_odds: 2.88,
            line: null,
            source_time_utc: "2026-05-25T08:11:00+00:00",
            fetched_at_utc: "2026-05-25T08:16:00+00:00"
          },
          {
            provider: "leisu",
            bookmaker: "公司A",
            market_type: "over_under",
            selection: "Over",
            decimal_odds: 1.96,
            line: 2.5,
            source_time_utc: "2026-05-25T08:09:00+00:00",
            fetched_at_utc: "2026-05-25T08:14:00+00:00"
          }
        ]
      }
    });

    const groups = (view as any).oddsGroups;

    expect(groups.map((group: any) => group.bookmaker)).toEqual(["公司B", "公司A"]);
    expect(groups[0].rowCountText).toBe("2 条");
    expect(groups[0].marketTypesText).toBe("亚盘、胜平负");
    expect(groups[0].latestFetchedAtUtc).toBe("2026-05-25T08:16:00+00:00");
    expect(groups[0].rows.map((row: any) => row.marketTypeLabel)).toEqual(["胜平负", "亚盘"]);
    expect(groups[0].rows[0].selectionText).toBe("平局");
    expect(groups[1].rows[0].selectionText).toBe("大球");
  });
});
