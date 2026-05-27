export type Severity = "ok" | "info" | "warning" | "error" | "blocked" | "missing";

export interface DashboardKpis {
  open_records: number;
  settled_records: number;
  tracked_only_records: number;
  duplicate_ignored_records: number;
  asian_pick_count: number;
  observation_count: number;
  calibration_bucket_count: number;
  strategy_sample_count: number;
  live_calibration_active: boolean;
}

export interface PredictionKpis {
  total_count: number;
  recommended_count: number;
  observation_count: number;
  open_count: number;
  live_count?: number;
  scheduled_count?: number;
  final_pending_count?: number;
  maybe_live_count?: number;
  result_pending_count?: number;
  postponed_count?: number;
  match_phase_counts?: Record<string, number>;
  settled_count: number;
  hit_count: number;
  miss_count: number;
  hit_rate: number | null;
  roi: number | null;
  recommended_settled_count?: number;
  recommended_hit_count?: number;
  recommended_miss_count?: number;
  recommended_hit_rate?: number | null;
  recommended_roi?: number | null;
  observation_settled_count?: number;
  observation_hit_count?: number;
  observation_miss_count?: number;
  observation_hit_rate?: number | null;
  observation_roi?: number | null;
}

export interface MarketSnapshotProviderSummary {
  provider: string;
  snapshot_count: number;
  event_count: number;
  bookmaker_count: number;
  market_type_count: number;
  first_fetched_at_utc: string | null;
  latest_fetched_at_utc: string | null;
  market_types: string[];
}

export interface MarketSnapshotSummary {
  db_path: string;
  total_snapshot_count: number;
  event_count: number;
  bookmaker_count: number;
  latest_fetched_at_utc: string | null;
  provider_count: number;
  providers: MarketSnapshotProviderSummary[];
  market_type_counts: Array<Record<string, unknown>>;
  latest_events: Array<Record<string, unknown>>;
  last_sync?: {
    enabled?: boolean;
    provider?: string;
    status?: string;
    saved_snapshot_count?: number;
    generated_snapshot_count?: number;
    candidate_match_count?: number;
    probed_match_count?: number;
    accessible_match_count?: number;
    promotable_match_count?: number;
    hard_flags?: string[];
    soft_flags?: string[];
    error?: string;
    at_utc?: string;
  };
}

export interface StrategyState {
  key: string;
  market: string;
  mode: string;
  status: string;
  active: boolean;
  sample_count: number;
  hit_rate: number | null;
  roi: number | null;
  avg_model_probability: number | null;
  min_live_sample_count: number;
  prior_strength: number;
  min_calibrated_probability: number;
  min_decimal_odds: number;
  max_decimal_odds: number;
  min_value_edge: number;
  updated_at_utc: string | null;
  raw: Record<string, unknown>;
}

export interface DashboardRecord {
  id: number | string;
  league: string;
  matchup: string;
  home_team: string;
  away_team: string;
  home_team_logo_url?: string | null;
  away_team_logo_url?: string | null;
  kickoff_utc_plus_8: string;
  market: string;
  selection: string;
  selection_key: string;
  line: number | null;
  decimal_odds: number | null;
  model_probability: number | null;
  learned_probability: number | null;
  market_probability?: number | null;
  edge: number | null;
  recommendation: string;
  stake_level: string;
  risk_flags: string[];
  caution_flags: string[];
  settlement_status: string;
  created_at_utc: string;
  score?: string;
  hit?: number | null;
  payout_multiplier?: number | null;
  profit_units?: number | null;
  settled_at_utc?: string;
}

export interface DashboardMatchState {
  phase: string;
  label: string;
  score: string;
  home_score?: number | null;
  away_score?: number | null;
  minute?: string;
  period?: string;
  status?: string;
  source?: string;
  updated_at_utc?: string;
}

export interface PredictionDiagnostic {
  actionability: string;
  actionability_label: string;
  recommended: boolean;
  paper_tracked: boolean;
  backtest_eligible: boolean;
  learning_active: boolean;
  learning_application_status?: string;
  learning_application_label?: string;
  learning_application_detail?: string;
  strategy_status: string;
  primary_reason: string;
  primary_reason_label: string;
  model_probability: number | null;
  learned_probability: number | null;
  market_probability: number | null;
  governed_probability?: number | null;
  probability_source?: string;
  probability_source_label?: string;
  probability_source_fallback?: boolean;
  probability_governance_status?: string;
  probability_governance_detail?: string;
  learned_adjustment: number | null;
  thresholds: {
    min_calibrated_probability: number | null;
    min_value_edge: number | null;
    min_decimal_odds: number | null;
    max_decimal_odds: number | null;
  };
  threshold_gaps: {
    probability: number | null;
    value_edge: number | null;
    min_decimal_odds: number | null;
    max_decimal_odds: number | null;
  };
  odds_in_range: boolean;
  threshold_passed: boolean;
  feature_explanations?: Array<{
    key: string;
    label: string;
    value: string;
    detail: string;
    tone?: KpiCard["tone"] | string;
  }>;
  diagnostic_summary: string;
}

export interface PredictionLedgerRow {
  ledger_id: string;
  source: string;
  source_id: number | string;
  prediction_type: string;
  prediction_type_label: string;
  status_label: string;
  league: string;
  matchup: string;
  home_team: string;
  away_team: string;
  home_team_logo_url?: string | null;
  away_team_logo_url?: string | null;
  kickoff_utc_plus_8: string;
  market: string;
  selection: string;
  selection_key: string;
  line: number | null;
  decimal_odds: number | null;
  model_probability: number | null;
  learned_probability: number | null;
  market_probability?: number | null;
  governed_probability?: number | null;
  probability_source?: string;
  probability_source_label?: string;
  edge: number | null;
  recommendation: string;
  rejection_reason: string;
  settlement_status: string;
  score: string;
  score_type?: string;
  match_state?: DashboardMatchState;
  true_result: {
    home_score: number | null;
    away_score: number | null;
    score: string;
  };
  hit: number | null;
  payout_multiplier: number | null;
  profit_units: number | null;
  settled_at_utc: string;
  created_at_utc: string;
  has_odds_snapshot?: boolean;
  odds_snapshot_count?: number;
  odds_bookmaker_count?: number;
  odds_market_type_count?: number;
  odds_latest_fetched_at_utc?: string;
  prediction_diagnostic?: PredictionDiagnostic;
}

export interface DashboardRecordDetail {
  status: string;
  tool: string;
  generated_at_utc: string;
  record: DashboardRecord;
  evidence: {
    core_metrics: {
      line: number | null;
      decimal_odds: number | null;
      model_probability: number | null;
      learned_probability: number | null;
      market_probability: number | null;
      edge: number | null;
      expected_multiplier: number | null;
    };
    final_execution_advice: Record<string, unknown>;
    final_decision?: Record<string, unknown>;
    data_completeness: Record<string, unknown>;
    live_calibration: Record<string, unknown>;
    prediction_diagnostic?: PredictionDiagnostic;
    market_candidates: Array<Record<string, unknown>>;
    risk_flags: string[];
    caution_flags: string[];
  };
  strategy_state: StrategyState;
  timeline: Array<{
    title: string;
    detail: string;
    at_utc: string;
  }>;
  policy: {
    read_only: boolean;
    no_real_bet: boolean;
    data_rule: string;
  };
}

export interface DashboardContextField {
  available: boolean;
  text: string;
  status?: string;
  source_text?: string;
}

export interface DashboardContextSource {
  status: string;
  provider: string;
  label: string;
  match_id: string;
  detail: string;
}

export interface DashboardPlayerSummary {
  name: string;
  position: string;
  shirt_number: string;
  nationality: string;
  captain: boolean;
}

export interface DashboardLineupSide {
  formation: string;
  starter_count: number;
  starters: DashboardPlayerSummary[];
}

export interface DashboardMatchContext {
  source: DashboardContextSource;
  venue: DashboardContextField;
  weather: DashboardContextField;
  referee: DashboardContextField;
  lineup: {
    available: boolean;
    basis: string;
    home: DashboardLineupSide;
    away: DashboardLineupSide;
    warnings: string[];
    analysis: Record<string, unknown>;
  };
  players: {
    available: boolean;
    home: DashboardPlayerSummary[];
    away: DashboardPlayerSummary[];
  };
  source_attempts?: Array<{
    provider: string;
    label: string;
    status: string;
    match_id: string;
    detail: string;
    field_statuses: Record<string, string>;
    urls?: Record<string, string>;
    access?: {
      blocked?: boolean;
      requires_cookie_or_proxy?: boolean;
      reason?: string;
    };
  }>;
  available_blocks: string[];
}

export interface DashboardOddsSnapshotRow {
  provider: string;
  bookmaker: string;
  market_type: string;
  selection: string;
  decimal_odds: number | null;
  line: number | null;
  source_time_utc: string;
  fetched_at_utc: string;
}

export interface DashboardOddsResolution {
  status: string;
  provider: string;
  event_id: string;
  league: string;
  home_team: string;
  away_team: string;
  source_home_team: string;
  source_away_team: string;
  source_league: string;
  match_score: number | null;
  reason: string;
}

export interface DashboardOddsSnapshotDetail {
  snapshot_count: number;
  bookmaker_count: number;
  bookmakers: string[];
  market_types: string[];
  latest_fetched_at_utc: string;
  latest_source_time_utc: string;
  latest_rows: DashboardOddsSnapshotRow[];
  resolution?: DashboardOddsResolution;
  consensus: Record<string, unknown>;
  movement?: Record<string, unknown>;
}

export interface DashboardClvResult {
  status: string;
  method: string;
  reason?: string;
  home_team?: string;
  away_team?: string;
  selection?: string;
  market_type?: string;
  line?: number | null;
  prediction_decimal_odds?: number;
  closing_decimal_odds?: number;
  clv_decimal_delta?: number;
  clv_return?: number;
  clv_implied_probability_delta?: number;
  closing_bookmaker_count?: number;
  closing_snapshot_count?: number;
  closing_window_minutes?: number;
  latest_closing_snapshot_utc?: string;
  prediction_snapshot_count?: number;
  rule?: string;
}

export interface DashboardClvRecord {
  record_id: number | string | null;
  record_key: string | null;
  home_team: string;
  away_team: string;
  market: string;
  selection: string;
  selection_key: string;
  status: string;
  clv: DashboardClvResult;
}

export interface DashboardClvTracking {
  status: string;
  method: string;
  record_count: number;
  tracked_count: number;
  skipped_count: number;
  available_count: number;
  positive_clv_count: number;
  positive_clv_rate: number | null;
  avg_clv_return: number | null;
  records: DashboardClvRecord[];
  rule: string;
}

export interface DashboardMatchDetail {
  status: string;
  tool: string;
  generated_at_utc: string;
  record: PredictionLedgerRow;
  match_context: DashboardMatchContext;
  odds_snapshot: DashboardOddsSnapshotDetail;
  clv_tracking?: DashboardClvTracking;
  evidence: DashboardRecordDetail["evidence"];
  strategy_state: StrategyState;
  timeline: DashboardRecordDetail["timeline"];
  policy: DashboardRecordDetail["policy"];
}

export interface CandidateFilter {
  reason: string;
  count: number;
  examples: DashboardRecord[];
}

export interface LearningEvent {
  kind: string;
  severity: Severity;
  title: string;
  detail: string;
  at_utc: string;
}

export interface DashboardAuditReason {
  reason: string;
  count: number;
}

export interface DashboardAuditHealthItem {
  key: string;
  label: string;
  status: Severity;
  title: string;
  detail: string;
  current: number | null;
  target: number | null;
  ratio: number | null;
}

export interface DashboardDecisionAudit {
  generated_at_utc: string;
  prediction: {
    status: Severity;
    title: string;
    detail: string;
    total_count: number;
    evaluation_count: number;
    recommended_count: number;
    observation_count: number;
    open_count: number;
    settled_count: number;
  };
  recommendation: {
    status: Severity;
    title: string;
    detail: string;
    recommended_count: number;
    observation_count: number;
    open_count: number;
    top_rejection_reasons: DashboardAuditReason[];
  };
  learning: {
    status: Severity;
    title: string;
    detail: string;
    active: boolean;
    sample_count: number;
    min_sample_count: number;
    settled_count: number;
    hit_rate: number | null;
    roi: number | null;
  };
  settlement: {
    status: Severity;
    title: string;
    detail: string;
    open_count: number;
    settled_count: number;
    hit_count: number;
    miss_count: number;
  };
  odds: {
    status: Severity;
    title: string;
    detail: string;
    covered_count: number;
    ledger_count: number;
    coverage_ratio: number | null;
    snapshot_count: number;
    bookmaker_count: number;
  };
  health_items: DashboardAuditHealthItem[];
}

export interface DashboardLearningDiagnostics {
  status: string;
  severity: Severity;
  title: string;
  detail: string;
  prediction_total: number;
  formal_count: number;
  observation_count: number;
  open_count: number;
  settled_count: number;
  hit_count: number;
  miss_count: number;
  backtested_count: number;
  waiting_result_count: number;
  ready_for_backtest_count: number;
  sample_count: number;
  settled_sample_target: number;
  remaining_to_live_calibration: number;
  live_calibration_active: boolean;
  odds_covered_count: number;
  odds_ledger_count: number;
  odds_coverage_ratio: number | null;
  snapshot_count: number;
  bookmaker_count: number;
  reanalysis_backlog_count: number;
  hit_rate: number | null;
  roi: number | null;
  readiness_items: DashboardAuditHealthItem[];
  top_blockers: DashboardAuditReason[];
}

export interface DashboardProbabilityQuality {
  sample_count: number;
  brier_score: number | null;
  calibration_error: number | null;
  avg_probability: number | null;
  hit_rate: number | null;
}

export interface DashboardProbabilityBand {
  key: string;
  label: string;
  min_probability: number | null;
  max_probability: number | null;
  sample_count: number;
  hit_count: number;
  hit_rate: number | null;
  avg_probability: number | null;
  calibration_error: number | null;
  brier_score: number | null;
  roi: number | null;
  sample_quality: string;
}

export interface DashboardCalibrationHealth {
  status: string;
  severity: Severity;
  title: string;
  detail: string;
  recommended_action: string;
  best_band_key: string;
  candidate_band_keys: string[];
  monotonicity_violations: number;
  meta_model?: {
    name?: string;
    type?: string;
    min_band_sample_count?: number;
    confidence_z?: number;
  };
  bands?: Array<{
    key: string;
    label: string;
    sample_count: number;
    hit_rate: number | null;
    roi: number | null;
    wilson_hit_rate_low?: number | null;
  }>;
}

export interface DashboardShadowRecalibration {
  status: string;
  severity: Severity;
  title: string;
  detail: string;
  method: string;
  selected_band_keys: string[];
  quality: {
    sample_count: number;
    learned_brier_score: number | null;
    recalibrated_brier_score: number | null;
    brier_delta: number | null;
    validation_mode?: string;
    walk_forward_sample_count?: number;
    walk_forward_recalibrated_brier_score?: number | null;
    walk_forward_brier_delta?: number | null;
  };
  validation: {
    mode?: string;
    sample_count: number;
    hit_count?: number;
    hit_rate: number | null;
    roi: number | null;
    walk_forward_brier_score?: number | null;
  };
  bands: Array<{
    key: string;
    label: string;
    sample_count: number;
    hit_count: number;
    hit_rate: number | null;
    posterior_probability: number | null;
    avg_learned_probability: number | null;
    avg_market_probability: number | null;
    posterior_edge: number | null;
    expected_multiplier: number | null;
    roi: number | null;
    selected: boolean;
    confidence?: string;
    walk_forward_brier_score?: number | null;
  }>;
}

export interface DashboardProbabilityGovernance {
  status: string;
  severity: Severity;
  title: string;
  detail: string;
  active_probability_source: string;
  active_source_label: string;
  policy_mode: string;
  production_ready: boolean;
  threshold_probability_field: string;
  guardrails: string[];
  candidates: Array<{
    source: string;
    label: string;
    sample_count: number;
    brier_score: number | null;
    calibration_error: number | null;
    avg_probability?: number | null;
    hit_rate?: number | null;
    rank: number;
    selected: boolean;
  }>;
  rule?: string;
}

export interface DashboardLearningEffectiveness {
  status: string;
  severity: Severity;
  title: string;
  detail: string;
  sample_count: number;
  model: DashboardProbabilityQuality;
  learned: DashboardProbabilityQuality;
  market: DashboardProbabilityQuality;
  probability_bands: DashboardProbabilityBand[];
  calibration_health?: DashboardCalibrationHealth;
  shadow_recalibration?: DashboardShadowRecalibration;
  probability_governance?: DashboardProbabilityGovernance;
  deltas: {
    learned_brier_minus_model: number | null;
    learned_brier_minus_market: number | null;
    learned_calibration_error_minus_model: number | null;
  };
  learning_improved: boolean;
  beats_market: boolean;
  deployment_verdict?: {
    status: string;
    severity: Severity;
    title: string;
    detail: string;
    production_ready: boolean;
    action: string;
    sample_count: number;
    roi: number | null;
    reasons: string[];
  };
  metric_rule: string;
}

export interface DashboardPredictionQualitySegment {
  key: string;
  reason: string;
  label: string;
  total_count: number;
  open_count: number;
  settled_count: number;
  hit_count: number;
  miss_count: number;
  hit_rate: number | null;
  roi: number | null;
  avg_probability: number | null;
  avg_edge: number | null;
  odds_covered_count: number;
  odds_coverage_ratio: number | null;
  signal_count: number;
  sample_quality: string;
  tone: string;
  adjustment?: {
    action: string;
    label: string;
    detail: string;
    weight_multiplier: number;
    formal_gate_eligible: boolean;
  };
}

export interface DashboardPredictionQuality {
  status: string;
  severity: Severity;
  title: string;
  detail: string;
  summary: {
    total_count: number;
    settled_count: number;
    open_count: number;
    segment_count: number;
    negative_segment_count: number;
    best_reason: string;
    worst_reason: string;
  };
  segments: DashboardPredictionQualitySegment[];
}

export interface DashboardAdaptiveLearningAction {
  key: string;
  label: string;
  status: string;
  title: string;
  detail: string;
  reason: string;
  applies_to: string;
  evidence: string;
  current: number | null;
  target: number | null;
  policy_effect: string;
}

export interface DashboardAdaptiveLearningPlan {
  status: string;
  severity: Severity;
  title: string;
  detail: string;
  summary: {
    action_count: number;
    blocked_action_count: number;
    warning_action_count: number;
    collection_action_count: number;
    frozen_model_count: number;
  };
  actions: DashboardAdaptiveLearningAction[];
}

export interface DashboardRecommendationOpportunityCandidate {
  ledger_id: string;
  league: string;
  matchup: string;
  home_team?: string;
  away_team?: string;
  home_team_logo_url?: string | null;
  away_team_logo_url?: string | null;
  selection: string;
  recommendation: string;
  primary_blocker: string;
  threshold_ready: boolean;
  has_odds_snapshot: boolean;
  learned_probability: number | null;
  probability_gap: number | null;
  value_edge: number | null;
  value_edge_gap: number | null;
  decimal_odds: number | null;
  odds_snapshot_count: number;
  settlement_status?: string;
  status_label?: string;
  meta_signal_label?: string;
  meta_signal_reason?: string;
  probability_band_key?: string;
  meta_probability?: number | null;
  meta_edge?: number | null;
  meta_expected_multiplier?: number | null;
  meta_sample_count?: number;
  meta_confidence?: string;
}

export interface DashboardReleaseGateItem {
  key: string;
  label: string;
  status: string;
  title: string;
  detail: string;
  current: number | null;
  target: number | null;
  ratio: number | null;
}

export interface DashboardRecommendationOpportunity {
  status: string;
  severity: Severity;
  title: string;
  detail: string;
  formal_count: number;
  paper_count: number;
  paper_signal_count: number;
  counter_signal_count?: number;
  current_open_count: number;
  historical_paper_signal_count: number;
  settled_signal_count: number;
  no_value_count: number;
  threshold_ready_count: number;
  reanalysis_backlog_count: number;
  missing_snapshot_count: number;
  gate_thresholds: {
    min_calibrated_probability: number | null;
    min_value_edge: number | null;
    min_decimal_odds: number | null;
    max_decimal_odds: number | null;
  };
  release_gate?: {
    status: string;
    formal_enabled: boolean;
    severity: Severity;
    title: string;
    detail: string;
    sample_count: number;
    min_sample_count: number;
    hit_rate: number | null;
    roi: number | null;
    signal_settled_count?: number;
    signal_hit_rate?: number | null;
    signal_roi?: number | null;
    min_signal_sample_count?: number;
    learning_improved: boolean;
    beats_market: boolean;
    prediction_policy: string;
    gates?: DashboardReleaseGateItem[];
  };
  top_blockers: DashboardAuditReason[];
  top_candidates: DashboardRecommendationOpportunityCandidate[];
  counter_signal_rule?: {
    status: string;
    title: string;
    detail: string;
    candidate_band_keys: string[];
    meta_model?: {
      name?: string;
      type?: string;
      min_band_sample_count?: number;
      confidence_z?: number;
    };
    shadow_recalibration?: {
      status: string;
      method: string;
      quality?: DashboardShadowRecalibration["quality"];
      validation?: DashboardShadowRecalibration["validation"];
    };
  };
  counter_signal_candidates?: DashboardRecommendationOpportunityCandidate[];
}

export interface DashboardContextCoverageSource {
  status: string;
  provider: string;
  label: string;
  count: number;
}

export interface DashboardContextCoverageField {
  key: string;
  label: string;
  total_count: number;
  available_count: number;
  source_empty_count: number;
  not_collected_count: number;
  coverage_ratio: number;
  summary: string;
}

export interface DashboardContextCoverage {
  total_count: number;
  source_counts: DashboardContextCoverageSource[];
  fields: DashboardContextCoverageField[];
  summary: string;
}

export interface DashboardContractSection {
  key: string;
  label: string;
  status: string;
  title: string;
  detail: string;
  current: number | null;
  target: number | null;
  ratio: number | null;
  required: boolean;
  frontend_visible: boolean;
}

export interface DashboardContract {
  contract_version: string;
  status: Severity;
  severity: Severity;
  title: string;
  detail: string;
  policy: {
    prediction_policy: string;
    formal_recommendation_enabled: boolean;
    release_gate_status: string;
    read_only: boolean;
  };
  summary: {
    required_count: number;
    ok_count: number;
    warning_count: number;
    blocked_count: number;
    missing_required_count: number;
    frontend_visible_count: number;
  };
  sections: DashboardContractSection[];
}

export interface DashboardProductionReadinessGate {
  key: string;
  label: string;
  status: Severity;
  title: string;
  detail: string;
  current: number | null;
  target: number | null;
  ratio: number | null;
}

export interface DashboardProductionReadiness {
  status: string;
  severity: Severity;
  title: string;
  detail: string;
  is_toy: boolean;
  production_ready: boolean;
  recommended_action: string;
  summary: {
    prediction_total: number;
    settled_count: number;
    open_count: number;
    hit_rate: number | null;
    roi: number | null;
    learning_improved: boolean;
    beats_market: boolean;
    clv_available_count?: number | null;
    clv_tracked_count?: number | null;
    avg_clv_return?: number | null;
    positive_clv_rate?: number | null;
    clv_ready?: boolean | null;
    formal_recommendation_enabled: boolean;
    blocked_count: number;
    warning_count: number;
  };
  gates: DashboardProductionReadinessGate[];
}

export interface DashboardPredictionAccountabilityCheck {
  key: string;
  label: string;
  status: Severity;
  title: string;
  detail: string;
  current: number | null;
  target: number | null;
  ratio: number | null;
}

export interface DashboardPredictionAccountability {
  status: string;
  severity: Severity;
  headline: string;
  title: string;
  detail: string;
  summary: {
    total_predictions: number;
    formal_recommendations: number;
    paper_predictions: number;
    settled_predictions: number;
    open_predictions: number;
    hit_rate: number | null;
    roi: number | null;
    learning_active: boolean;
    learning_improved: boolean;
    beats_market: boolean;
    formal_gate_enabled: boolean;
    primary_blocker: string;
    primary_blocker_label: string;
  };
  checks: DashboardPredictionAccountabilityCheck[];
  policy: {
    prediction_policy: string;
    formal_recommendation_policy: string;
    paper_prediction_policy: string;
    no_real_bet: boolean;
  };
}

export interface DashboardModelGovernanceCheck {
  key: string;
  label: string;
  status: Severity;
  title: string;
  detail: string;
  current: number | null;
  target: number | null;
  ratio: number | null;
}

export interface DashboardModelGovernance {
  status: string;
  severity: Severity;
  title: string;
  detail: string;
  summary: {
    record_count: number;
    model_engine_count: number;
    model_available_count: number;
    historical_rho_count: number;
    market_anchor_count: number;
    fallback_count: number;
    calibration_sample_count: number;
    clv_tracked_count: number;
    clv_available_count: number;
    avg_clv_return: number | null;
    positive_clv_rate: number | null;
  };
  rho: {
    source_counts: Record<string, number>;
    avg_rho: number | null;
    historical_avg_rho: number | null;
    historical_avg_sample_count: number | null;
  };
  calibration: {
    status: string;
    title: string;
    detail: string;
    sample_count: number;
    learning_improved: boolean;
    beats_market: boolean;
    active_probability_source: string;
    shadow_method: string;
    shadow_status: string;
    walk_forward_sample_count: number;
    walk_forward_brier_delta: number | null;
  };
  clv: {
    status: string;
    available_count: number;
    positive_clv_rate: number | null;
    avg_clv_return: number | null;
  };
  method_counts: Record<string, number>;
  version_counts: Record<string, number>;
  checks: DashboardModelGovernanceCheck[];
  rule: string;
}

export interface DashboardBacktestCurvePoint {
  index: number;
  ledger_id: string;
  matchup: string;
  prediction_type_label: string;
  at_utc: string;
  hit: number;
  profit_units: number | null;
  cumulative_profit: number | null;
  roi: number | null;
  drawdown_units: number | null;
  rolling_hit_rate: number | null;
}

export interface DashboardBacktestCurve {
  status: string;
  severity: Severity;
  title: string;
  detail: string;
  summary: {
    settled_count: number;
    hit_count: number;
    miss_count: number;
    hit_rate: number | null;
    profit_units: number | null;
    roi: number | null;
    max_drawdown_units: number | null;
    longest_loss_streak: number;
    current_streak_type: string;
    current_streak_count: number;
    rolling_window: number;
  };
  points: DashboardBacktestCurvePoint[];
}

export interface DashboardSnapshot {
  status: string;
  tool: string;
  generated_at_utc: string;
  db_path: string;
  kpis: DashboardKpis;
  prediction_kpis: PredictionKpis;
  market_snapshot_summary: MarketSnapshotSummary;
  context_coverage?: DashboardContextCoverage;
  strategy_state: StrategyState;
  asian_picks: DashboardRecord[];
  candidate_filters: CandidateFilter[];
  recent_settlements: DashboardRecord[];
  prediction_ledger: PredictionLedgerRow[];
  learning_events: LearningEvent[];
  auto_learning_state: Record<string, unknown>;
  decision_audit?: DashboardDecisionAudit;
  learning_diagnostics?: DashboardLearningDiagnostics;
  learning_effectiveness?: DashboardLearningEffectiveness;
  model_governance?: DashboardModelGovernance;
  clv_tracking?: DashboardClvTracking;
  backtest_curve?: DashboardBacktestCurve;
  prediction_quality?: DashboardPredictionQuality;
  adaptive_learning_plan?: DashboardAdaptiveLearningPlan;
  recommendation_opportunity?: DashboardRecommendationOpportunity;
  dashboard_contract?: DashboardContract;
  production_readiness?: DashboardProductionReadiness;
  prediction_accountability?: DashboardPredictionAccountability;
  profitability_forecast?: DashboardProfitabilityForecast;
  market_breakdown?: DashboardMarketBreakdown;
  buckets: Array<Record<string, unknown>>;
  policy: {
    read_only: boolean;
    no_search_inputs: boolean;
    data_rule: string;
  };
}

export interface DashboardProfitabilityForecast {
  available: boolean;
  method?: string;
  observed_hit_rate?: number;
  assumed_avg_odds?: number;
  implied_roi_per_bet?: number;
  settled_per_day_estimate?: number;
  required_bets_total?: number;
  settled_bets_so_far?: number;
  remaining_bets?: number;
  remaining_days?: number | null;
  confidence_level?: number;
  reason?: string;
  min_required?: number;
  settled_count?: number;
  notes?: string;
  interpretation?: string;
}

export interface DashboardMarketBreakdown {
  by_market: Array<{
    market: string;
    sample_count: number;
    hit_count: number;
    hit_rate: number | null;
    roi: number | null;
  }>;
  heatmap_cells: Array<{
    league: string;
    market: string;
    sample_count: number;
    hit_rate: number | null;
    roi: number | null;
  }>;
  total_settled: number;
  markets: string[];
  leagues: string[];
}

export interface KpiCard {
  label: string;
  value: string;
  tone: "neutral" | "good" | "caution" | "bad";
}

export interface AuditHealthCard {
  key: string;
  label: string;
  status: Severity;
  tone: KpiCard["tone"];
  title: string;
  detail: string;
  metricText: string;
  progressText: string;
  progressValue: number | null;
}

export interface PickView extends DashboardRecord {
  oddsText: string;
  modelProbabilityText: string;
  learnedProbabilityText: string;
  edgeText: string;
}

export interface ProbabilityRow {
  label: string;
  value: number | null;
  text: string;
}

export interface CandidateRow {
  selection: string;
  selectionText: string;
  providerText: string;
  oddsText: string;
  probabilityText: string;
  edgeText: string;
  movementText?: string;
  movementTone?: KpiCard["tone"];
}

export interface PredictionLedgerViewRow extends PredictionLedgerRow {
  statusText: string;
  oddsText: string;
  probabilityText: string;
  edgeText: string;
  scoreText: string;
  profitText: string;
  oddsCoverageText: string;
  diagnosticLabel: string;
  diagnosticReasonText: string;
  diagnosticGapText: string;
}

export interface MarketSnapshotProviderView extends MarketSnapshotProviderSummary {
  providerLabel: string;
  marketTypesText: string;
}

export interface RecommendationFunnelView {
  reason: string;
  label: string;
  count: number;
  countText: string;
  ratio: number;
  width: string;
}

export interface AuditBlockView {
  status: Severity;
  tone: KpiCard["tone"];
  title: string;
  detail: string;
  progressText: string;
  progressValue: number | null;
}

export interface LearningDiagnosticMetric {
  label: string;
  value: string;
  caption: string;
  tone: KpiCard["tone"];
}

export interface LearningDiagnosticsView {
  severity: Severity;
  tone: KpiCard["tone"];
  title: string;
  detail: string;
  metrics: LearningDiagnosticMetric[];
  readinessItems: AuditHealthCard[];
  blockerRows: RecommendationFunnelView[];
}

export interface LearningEffectivenessView {
  severity: Severity;
  tone: KpiCard["tone"];
  title: string;
  detail: string;
  metricRule: string;
  calibrationHealth?: {
    title: string;
    detail: string;
    actionText: string;
    modelText: string;
    candidateBandsText: string;
    tone: KpiCard["tone"];
  };
  shadowRecalibration?: {
    title: string;
    detail: string;
    methodText: string;
    brierText: string;
    brierDeltaText: string;
    walkForwardText: string;
    validationText: string;
    selectedBandsText: string;
    tone: KpiCard["tone"];
  };
  probabilityGovernance?: {
    title: string;
    detail: string;
    activeText: string;
    policyText: string;
    thresholdText: string;
    guardrailsText: string;
    tone: KpiCard["tone"];
    candidateRows: string[];
  };
  metrics: Array<{
    label: string;
    value: string;
    caption: string;
    tone: KpiCard["tone"];
  }>;
  summaryRows: Array<{
    label: string;
    value: string;
  }>;
  deploymentVerdict: {
    title: string;
    detail: string;
    actionText: string;
    statusText: string;
    tone: KpiCard["tone"];
    sampleText: string;
    roiText: string;
    reasonsText: string;
  };
  bandRows: Array<{
    key: string;
    label: string;
    sampleText: string;
    hitRateText: string;
    avgProbabilityText: string;
    roiText: string;
    calibrationText: string;
    qualityText: string;
    hitWidth: string;
    probabilityWidth: string;
    tone: KpiCard["tone"];
  }>;
}

export interface ModelGovernanceView {
  severity: Severity;
  tone: KpiCard["tone"];
  title: string;
  detail: string;
  methodText: string;
  ruleText: string;
  metrics: Array<{
    label: string;
    value: string;
    caption: string;
    tone: KpiCard["tone"];
  }>;
  checkRows: Array<{
    key: string;
    label: string;
    title: string;
    detail: string;
    statusText: string;
    progressText: string;
    width: string;
    tone: KpiCard["tone"];
  }>;
}

export interface ClvTrackingView {
  severity: Severity;
  tone: KpiCard["tone"];
  title: string;
  detail: string;
  ruleText: string;
  metrics: Array<{
    label: string;
    value: string;
    caption: string;
    tone: KpiCard["tone"];
  }>;
  recordRows: Array<{
    id: string;
    matchup: string;
    marketText: string;
    selectionText: string;
    priceText: string;
    clvText: string;
    timeText: string;
    tone: KpiCard["tone"];
  }>;
}

export interface BacktestCurveView {
  severity: Severity;
  tone: KpiCard["tone"];
  title: string;
  detail: string;
  metrics: Array<{
    label: string;
    value: string;
    caption: string;
    tone: KpiCard["tone"];
  }>;
  points: Array<{
    index: number;
    matchup: string;
    typeText: string;
    resultText: string;
    cumulativeValue: number;
    cumulativeText: string;
    drawdownText: string;
    rollingHitText: string;
    profitValue: number;
    profitText: string;
    x: number;
    y: number;
    tone: KpiCard["tone"];
  }>;
  polyline: string;
  zeroLineY: number;
}

export interface PredictionQualityView {
  severity: Severity;
  tone: KpiCard["tone"];
  title: string;
  detail: string;
  metricRows: Array<{
    label: string;
    value: string;
    caption: string;
    tone: KpiCard["tone"];
  }>;
  segmentRows: Array<{
    label: string;
    totalText: string;
    settledText: string;
    hitRateText: string;
    roiText: string;
    avgProbabilityText: string;
    avgEdgeText: string;
    oddsCoverageText: string;
    qualityText: string;
    adjustmentLabel: string;
    adjustmentDetail: string;
    weightText: string;
    width: string;
    tone: KpiCard["tone"];
  }>;
}

export interface AdaptiveLearningPlanView {
  tone: KpiCard["tone"];
  title: string;
  detail: string;
  metrics: Array<{
    label: string;
    value: string;
    caption: string;
    tone: KpiCard["tone"];
  }>;
  actionRows: Array<{
    key: string;
    label: string;
    title: string;
    detail: string;
    evidence: string;
    policyEffect: string;
    statusText: string;
    progressText: string;
    width: string;
    tone: KpiCard["tone"];
  }>;
}

export interface DashboardContractView {
  tone: KpiCard["tone"];
  title: string;
  detail: string;
  policyText: string;
  metricRows: Array<{
    label: string;
    value: string;
    caption: string;
    tone: KpiCard["tone"];
  }>;
  sectionRows: Array<{
    label: string;
    title: string;
    detail: string;
    statusText: string;
    progressText: string;
    width: string;
    tone: KpiCard["tone"];
  }>;
}

export interface ProductionReadinessView {
  tone: KpiCard["tone"];
  title: string;
  detail: string;
  actionText: string;
  metrics: Array<{
    label: string;
    value: string;
    caption: string;
    tone: KpiCard["tone"];
  }>;
  gateRows: Array<{
    key: string;
    label: string;
    title: string;
    detail: string;
    statusText: string;
    progressText: string;
    width: string;
    tone: KpiCard["tone"];
  }>;
}

export interface ProductionOpsView {
  tone: KpiCard["tone"];
  headline: string;
  detail: string;
  releaseText: string;
  statusCards: Array<{
    label: string;
    value: string;
    caption: string;
    tone: KpiCard["tone"];
  }>;
  blockerRows: Array<{
    key: string;
    label: string;
    title: string;
    detail: string;
    statusText: string;
    progressText: string;
    width: string;
    tone: KpiCard["tone"];
  }>;
  workflowRows: Array<{
    key: string;
    label: string;
    title: string;
    detail: string;
    statusText: string;
    metaText: string;
    tone: KpiCard["tone"];
  }>;
}

export interface DataSourceHealthView {
  tone: KpiCard["tone"];
  title: string;
  detail: string;
  issueText: string;
  statusCards: Array<{
    label: string;
    value: string;
    caption: string;
    tone: KpiCard["tone"];
  }>;
  checkRows: Array<{
    key: string;
    label: string;
    title: string;
    detail: string;
    statusText: string;
    metaText: string;
    width: string;
    tone: KpiCard["tone"];
  }>;
}

export interface PredictionAccountabilityView {
  tone: KpiCard["tone"];
  headline: string;
  title: string;
  detail: string;
  policyText: string;
  metrics: Array<{
    label: string;
    value: string;
    caption: string;
    tone: KpiCard["tone"];
  }>;
  checkRows: Array<{
    key: string;
    label: string;
    title: string;
    detail: string;
    statusText: string;
    progressText: string;
    width: string;
    tone: KpiCard["tone"];
  }>;
}

export interface MatchPhaseCard {
  key: string;
  label: string;
  value: string;
  caption: string;
  tone: KpiCard["tone"];
  ratio: number | null;
  width: string;
}

export interface RecordDetailView {
  title: string;
  subtitle: string;
  marketSummary: string;
  actionText: string;
  probabilityRows: ProbabilityRow[];
  candidateRows: CandidateRow[];
  dataFlags: string[];
  riskFlags: string[];
  timeline: DashboardRecordDetail["timeline"];
  hasQueryControls: false;
}

export type OddsSnapshotRowView = DashboardOddsSnapshotRow & {
  providerLabel: string;
  marketTypeLabel: string;
  selectionText: string;
  oddsText: string;
  lineText: string;
};

export interface OddsSnapshotBookmakerGroup {
  id: string;
  bookmaker: string;
  rowCountText: string;
  marketTypesText: string;
  latestFetchedAtUtc: string;
  rows: OddsSnapshotRowView[];
}

export interface OddsTrendPoint {
  observedAtUtc: string;
  label: string;
  [seriesKey: string]: string | number | null;
}

export interface OddsTrendSeries {
  key: string;
  bookmaker: string;
  color: string;
  latestOddsText: string;
  latestIndexText: string;
  pointCountText: string;
}

export interface OddsDistributionRow {
  key: string;
  bookmaker: string;
  oddsText: string;
  indexText: string;
  pointCountText: string;
  positionPercent: string;
  color: string;
}

export interface PredictionDiagnosticView {
  title: string;
  statusText: string;
  reasonText: string;
  summary: string;
  learningDetail: string;
  tone: KpiCard["tone"];
  passText: string;
  gapRows: Array<{
    label: string;
    value: string;
  }>;
  explanationRows: Array<{
    label: string;
    value: string;
    detail: string;
    tone: KpiCard["tone"];
  }>;
}

export interface MatchDetailView extends RecordDetailView {
  scoreStatusText: string;
  predictionDiagnostic: PredictionDiagnosticView;
  contextSourceText: string;
  contextDiagnostics: Array<{
    label: string;
    detail: string;
    tone: KpiCard["tone"];
  }>;
  sourceAttemptRows: Array<{
    providerText: string;
    matchIdText: string;
    statusText: string;
    fieldSummary: string;
    detail: string;
    tone: KpiCard["tone"];
  }>;
  contextRows: Array<{
    label: string;
    value: string;
    available: boolean;
    statusText: string;
    sourceText?: string;
  }>;
  lineup: {
    available: boolean;
    basis: string;
    statusText: string;
    home: {
      formation: string;
      starterCountText: string;
      players: DashboardPlayerSummary[];
    };
    away: {
      formation: string;
      starterCountText: string;
      players: DashboardPlayerSummary[];
    };
    warnings: string[];
  };
  oddsSummary: string;
  clvTracking: {
    title: string;
    detail: string;
    priceText: string;
    clvText: string;
    timeText: string;
    tone: KpiCard["tone"];
  };
  oddsTrend: {
    mode: "trend" | "distribution" | "empty";
    title: string;
    detail: string;
    statusText: string;
    tone: KpiCard["tone"];
    targetText: string;
    points: OddsTrendPoint[];
    series: OddsTrendSeries[];
    distributionRows: OddsDistributionRow[];
    distributionSummary: {
      lowOddsText: string;
      medianOddsText: string;
      highOddsText: string;
      spreadText: string;
    };
  };
  marketMovement: {
    title: string;
    detail: string;
    statusText: string;
    tone: KpiCard["tone"];
    rows: Array<{
      key: string;
      marketText: string;
      selectionText: string;
      directionText: string;
      priceText: string;
      probabilityText: string;
      lineText: string;
      metaText: string;
      tone: KpiCard["tone"];
    }>;
  };
  oddsRows: OddsSnapshotRowView[];
  oddsGroups: OddsSnapshotBookmakerGroup[];
}

export type DashboardSectionKey = "overview" | "production" | "model" | "signals" | "data";

export interface DashboardSection {
  key: DashboardSectionKey;
  label: string;
  description: string;
  badge: string;
  tone: KpiCard["tone"];
}

export interface DashboardView {
  kpiCards: KpiCard[];
  dashboardSections: DashboardSection[];
  strategyLabel: string;
  primaryPick: PickView | null;
  pickRows: PickView[];
  predictionRows: PredictionLedgerViewRow[];
  matchPhaseCards: MatchPhaseCard[];
  predictionSummary: string;
  oddsCoveredCount: number;
  snapshotProviders: MarketSnapshotProviderView[];
  snapshotSummary: string;
  snapshotEmptyText: string;
  contextCoverage: ContextCoverageView;
  filterGroups: Array<CandidateFilter & { label: string }>;
  healthCards: AuditHealthCard[];
  predictionAudit: AuditBlockView;
  recommendationAudit: AuditBlockView;
  learningAudit: AuditBlockView;
  settlementAudit: AuditBlockView;
  oddsAudit: AuditBlockView;
  learningDiagnostics: LearningDiagnosticsView;
  modelGovernance: ModelGovernanceView;
  clvTracking: ClvTrackingView;
  learningEffectiveness: LearningEffectivenessView;
  backtestCurve: BacktestCurveView;
  predictionQuality: PredictionQualityView;
  adaptiveLearningPlan: AdaptiveLearningPlanView;
  dashboardContract: DashboardContractView;
  productionReadiness: ProductionReadinessView;
  productionOps: ProductionOpsView;
  dataSourceHealth: DataSourceHealthView;
  predictionAccountability: PredictionAccountabilityView;
  recommendationOpportunity: RecommendationOpportunityView;
  recommendationFunnel: RecommendationFunnelView[];
  hasQueryControls: false;
}

export interface RecommendationOpportunityView {
  severity: Severity;
  tone: KpiCard["tone"];
  title: string;
  detail: string;
  thresholdText: string;
  releaseGate: {
    title: string;
    detail: string;
    tone: KpiCard["tone"];
    gateRows: Array<{
      key: string;
      label: string;
      title: string;
      detail: string;
      tone: KpiCard["tone"];
      progressText: string;
      width: string;
    }>;
  } | null;
  metrics: Array<{
    label: string;
    value: string;
    caption: string;
    tone: KpiCard["tone"];
  }>;
  blockers: Array<{
    key: string;
    label: string;
    count: number;
    countText: string;
    ratio: number;
    width: string;
  }>;
  candidates: Array<{
    ledgerId: string;
    matchup: string;
    league: string;
    homeTeam?: string;
    awayTeam?: string;
    homeTeamLogoUrl?: string | null;
    awayTeamLogoUrl?: string | null;
    selection: string;
    actionLabel: string;
    blockerLabel: string;
    probabilityText: string;
    probabilityGapText: string;
    edgeText: string;
    edgeGapText: string;
    oddsText: string;
    snapshotText: string;
    thresholdReady: boolean;
  }>;
  counterSignal?: {
    title: string;
    detail: string;
    modelText: string;
    candidateBandsText: string;
    tone: KpiCard["tone"];
    candidates: Array<{
      ledgerId: string;
      matchup: string;
      league: string;
      homeTeam?: string;
      awayTeam?: string;
      homeTeamLogoUrl?: string | null;
      awayTeamLogoUrl?: string | null;
      selection: string;
      signalLabel: string;
      signalReason: string;
      actionLabel: string;
      blockerLabel: string;
      probabilityText: string;
      metaProbabilityText: string;
      edgeText: string;
      metaEdgeText: string;
      confidenceText: string;
      oddsText: string;
      snapshotText: string;
      bandText: string;
    }>;
  };
}

export interface ContextCoverageView {
  totalText: string;
  summary: string;
  sourceText: string;
  fields: Array<{
    key: string;
    label: string;
    value: string;
    caption: string;
    width: string;
    tone: KpiCard["tone"];
  }>;
}
