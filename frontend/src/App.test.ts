import { describe, expect, it } from "vitest";

import {
  DASHBOARD_POLL_ACTIVE_VALIDATION_MS,
  DASHBOARD_POLL_IDLE_MS,
  dashboardPollIntervalMs,
  formatDashboardCacheForDisplay,
  formatProgramCapabilityActionPlan,
  formatProductionGatesForDisplay,
  formatRecommendationGateRowsForDisplay,
  formatSignalWorkbenchForDisplay,
  formatTaskQueueForDisplay,
  formatAsianHandicapValidation,
  formatValidationMetricScope,
  formatValidationJobTimeline,
  formatValidationLeagueRunDiagnostics,
  formatValidationJobRunSummary,
  nextRefreshActivityCount,
  validationLeagueLogLossDiff,
  validationVerdictTone,
} from "./App";

describe("nextRefreshActivityCount", () => {
  it("keeps refresh activity busy while overlapping refreshes are still running", () => {
    let count = 0;
    count = nextRefreshActivityCount(count, 1);
    count = nextRefreshActivityCount(count, 1);
    count = nextRefreshActivityCount(count, -1);

    expect(count).toBe(1);
  });

  it("clamps extra finish calls at zero", () => {
    expect(nextRefreshActivityCount(0, -1)).toBe(0);
  });
});

describe("formatProductionGatesForDisplay", () => {
  it("uses backend gate labels instead of internal keys for production gates", () => {
    const [gate] = formatProductionGatesForDisplay([
      {
        key: "0-预测闭环",
        label: "预测闭环",
        title: "已持续预测",
        detail: "台账共有 410 条预测。",
        statusText: "通过",
        progressText: "",
        width: "100%",
        tone: "good",
      },
    ]);

    expect(gate).toEqual({
      name: "预测闭环",
      status: "通过",
      tone: "good",
      detail: "已持续预测：台账共有 410 条预测。",
      required: false,
    });
    expect(JSON.stringify(gate)).not.toContain("未识别状态");
  });
});

describe("formatRecommendationGateRowsForDisplay", () => {
  it("formats recommendation release gates with user-facing statuses", () => {
    const [gate] = formatRecommendationGateRowsForDisplay({
      title: "模型失利策略阻断",
      detail: "无正向边际已命中模型失利策略。",
      tone: "caution",
      gateRows: [
        {
          key: "0-失利策略",
          label: "失利策略",
          title: "策略阻断候选",
          detail: "无正向边际阻断 2 场候选。",
          statusText: "阻断",
          progressText: "0/2",
          width: "0%",
          tone: "bad",
        },
      ],
    });

    expect(gate).toEqual({
      key: "0-失利策略",
      name: "失利策略",
      status: "阻断",
      tone: "bad",
      detail: "策略阻断候选：无正向边际阻断 2 场候选。",
      progressText: "0/2",
      width: "0%",
    });
    expect(JSON.stringify(gate)).not.toContain("paper_only_model_failure_policy");
    expect(JSON.stringify(gate)).not.toContain("未识别状态");
  });
});

describe("formatSignalWorkbenchForDisplay", () => {
  it("summarizes candidate and blocker counts for the signal workbench", () => {
    const summary = formatSignalWorkbenchForDisplay({
      severity: "warning",
      tone: "caution",
      title: "有观察信号",
      detail: "等待闸门。",
      thresholdText: "最低概率 58.0%",
      releaseGate: null,
      metrics: [],
      blockers: [
        { key: "b1", label: "无正向边际", count: 12, countText: "12", ratio: 0.6, width: "60%" },
      ],
      candidates: [
        {
          ledgerId: "observation:1",
          matchup: "A 对 B",
          league: "测试联赛",
          selection: "A -0.5",
          actionLabel: "观察跟踪",
          blockerLabel: "赔率已补齐待复算",
          probabilityText: "62.0%",
          probabilityGapText: "+4.0%",
          edgeText: "+5.0%",
          edgeGapText: "+3.0%",
          oddsText: "1.88",
          snapshotText: "2 条快照",
          thresholdReady: true,
        },
      ],
    });

    expect(summary).toEqual({
      candidateCount: 1,
      blockerCount: 1,
      counterSignalCount: 0,
      headline: "候选池有可跟踪信号",
      badge: "1 候选 · 1 阻断",
      monitoringText: "候选、阻断和反向观察会同步进入台账筛选，方便从发布闸门追到具体样本。",
      emptyCandidateText: "点击候选查看详情。",
      emptyBlockerText: "点击阻断分组筛选台账。",
      emptyCounterSignalText: "当前没有反向校准观察。",
    });
  });

  it("explains empty signal workbench as active monitoring instead of missing data", () => {
    const summary = formatSignalWorkbenchForDisplay({
      severity: "ok",
      tone: "good",
      title: "持续监控中",
      detail: "没有候选。",
      thresholdText: "最低概率 58.0%",
      releaseGate: null,
      metrics: [],
      blockers: [],
      candidates: [],
      counterSignal: {
        title: "反向观察",
        detail: "没有反向候选。",
        modelText: "影子模型",
        candidateBandsText: "0 分组",
        tone: "neutral",
        candidates: [],
      },
    });

    expect(summary).toEqual({
      candidateCount: 0,
      blockerCount: 0,
      counterSignalCount: 0,
      headline: "持续监控，当前没有可跟踪信号",
      badge: "0 候选 · 0 阻断",
      monitoringText: "链路正常监控中：没有候选或阻断不代表任务停止，台账仍会接收后续赔率、赛果和复算结果。",
      emptyCandidateText: "当前没有达到概率、边际和赔率门槛的候选；系统仍在采样、回测和等待盘口更新。",
      emptyBlockerText: "当前没有命中主要阻断分组，这代表漏斗没有拦截到可归因样本，不是任务停止。",
      emptyCounterSignalText: "当前没有反向校准观察。",
    });
    expect(JSON.stringify(summary)).not.toContain("未识别状态");
  });
});

describe("validationLeagueLogLossDiff", () => {
  it("derives model-minus-market log loss from backend validation fields", () => {
    expect(
      validationLeagueLogLossDiff({
        calibrated_validation_result: {
          model_log_loss_1x2: 0.48,
          market_log_loss_1x2: 0.52,
        },
      }),
    ).toBeCloseTo(-0.04);
  });

  it("uses explicit model-minus-market when backend provides it", () => {
    expect(
      validationLeagueLogLossDiff({
        calibrated_validation_result: {
          log_loss_model_minus_market: -0.025,
          model_log_loss_1x2: 0.7,
          market_log_loss_1x2: 0.6,
        },
      }),
    ).toBeCloseTo(-0.025);
  });
});

describe("formatTaskQueueForDisplay", () => {
  it("summarizes a healthy ARQ queue with Redis and worker details", () => {
    const summary = formatTaskQueueForDisplay({
      backend: "arq",
      status: "ok",
      redis_reachable: true,
      redis_host: "football-data-redis",
      redis_port: 6379,
      redis_database: 0,
      queue_name: "football-data-mcp",
      queued_jobs: 2,
      worker_healthy: true,
      worker_health: "j_complete=3 queued=2",
      worker_health_ttl_seconds: 300,
      max_jobs: 1,
      job_timeout_seconds: 3600,
      validation_job_stale_after_seconds: 3900,
      detail: "ARQ worker 已上报健康检查。",
    });

    expect(summary).toEqual({
      badge: "ARQ 正常",
      tone: "good",
      backendText: "ARQ 异步队列",
      redisText: "football-data-redis:6379 / DB 0",
      workerText: "worker 在线 · 心跳剩余 5 分钟",
      queuedJobsText: "2 个任务",
      concurrencyText: "并发 1 · 超时 60 分钟 · 恢复 65 分钟",
      detail: "ARQ worker 已上报健康检查。",
      nextAction: "后台验证、续跑和重试会进入 Redis 队列，由 worker 异步执行。",
    });
    expect(JSON.stringify(summary)).not.toContain("worker_healthy");
  });

  it("explains degraded ARQ state without internal field names", () => {
    const summary = formatTaskQueueForDisplay({
      backend: "arq",
      status: "degraded",
      redis_reachable: true,
      queue_name: "football-data-mcp",
      queued_jobs: 4,
      worker_healthy: false,
      detail: "Redis 可达，但暂未看到 ARQ worker 健康检查。",
    });

    expect(summary.tone).toBe("caution");
    expect(summary.badge).toBe("ARQ 需关注");
    expect(summary.workerText).toBe("worker 未确认");
    expect(summary.nextAction).toBe("Redis 可达但 worker 未确认，请优先恢复 worker，否则任务会积压。");
  });
});

describe("formatDashboardCacheForDisplay", () => {
  it("summarizes a fresh dashboard snapshot cache", () => {
    const summary = formatDashboardCacheForDisplay({
      status: "fresh",
      age_seconds: 4.2,
      ttl_seconds: 10,
      stale_seconds: 120,
    });

    expect(summary).toEqual({
      badge: "缓存命中",
      tone: "good",
      statusText: "直接使用新鲜快照",
      ageText: "4 秒前生成",
      ttlText: "新鲜期 10 秒 · 后台保底 2 分钟",
      detail: "看板读取走短缓存，避免每次切页都重新扫描数据库和模型指标。",
      nextAction: "需要立刻复算时使用刷新动作；普通浏览会复用缓存以保持页面响应。",
    });
  });

  it("explains stale snapshots that are refreshing in the background", () => {
    const summary = formatDashboardCacheForDisplay({
      status: "stale_refreshing",
      age_seconds: 42,
      ttl_seconds: 10,
      stale_seconds: 120,
    });

    expect(summary.tone).toBe("caution");
    expect(summary.badge).toBe("后台刷新中");
    expect(summary.statusText).toBe("先展示旧快照，同时后台刷新");
    expect(summary.nextAction).toBe("页面不是卡住：当前先返回旧快照，刷新完成后下一次轮询会自动换成新快照。");
    expect(JSON.stringify(summary)).not.toContain("stale_refreshing");
  });

  it("handles missing cache metadata without exposing raw status", () => {
    const summary = formatDashboardCacheForDisplay(undefined);

    expect(summary.badge).toBe("缓存待确认");
    expect(summary.statusText).toBe("等待缓存状态");
    expect(summary.ageText).toBe("—");
  });
});

describe("formatProgramCapabilityActionPlan", () => {
  it("prioritizes blocked and weakest learning capabilities for product action", () => {
    const plan = formatProgramCapabilityActionPlan([
      {
        key: "continuous_prediction",
        title: "持续预测与观察入库",
        status: "ok",
        available: true,
        current: 444,
        target: 20,
        ratio: 1,
        detail: "已入库。",
        next_action: "继续保持。",
      },
      {
        key: "clv_tracking",
        title: "CLV 收盘线追踪",
        status: "warning",
        available: true,
        current: 7,
        target: 30,
        ratio: 0.233333,
        detail: "样本偏少。",
        next_action: "继续采后续赔率。",
      },
      {
        key: "context_coverage",
        title: "比赛上下文覆盖",
        status: "warning",
        available: true,
        current: 397,
        target: 444,
        ratio: 0.894,
        detail: "情报不足。",
        next_action: "补阵容、天气、裁判。",
      },
      {
        key: "production_release_gate",
        title: "正式推荐发布门禁",
        status: "blocked",
        available: false,
        current: 0,
        target: 1,
        ratio: 0,
        detail: "正式推荐关闭。",
        next_action: "命中率、ROI、CLV 同时过关后再开放。",
      },
    ]);

    expect(plan).toEqual({
      headline: "优先处理 3 个产品短板",
      badge: "1 阻断 · 2 学习",
      items: [
        {
          title: "正式推荐发布门禁",
          statusText: "阻塞",
          tone: "bad",
          progressText: "0/1",
          gapText: "还差 1",
          nextAction: "命中率、ROI、CLV 同时过关后再开放。",
        },
        {
          title: "CLV 收盘线追踪",
          statusText: "学习中",
          tone: "caution",
          progressText: "7/30",
          gapText: "还差 23",
          nextAction: "继续采后续赔率。",
        },
        {
          title: "比赛上下文覆盖",
          statusText: "学习中",
          tone: "caution",
          progressText: "397/444",
          gapText: "还差 47",
          nextAction: "补阵容、天气、裁判。",
        },
      ],
    });
    expect(JSON.stringify(plan)).not.toContain("production_release_gate");
  });

  it("reports ready state when every capability is available", () => {
    const plan = formatProgramCapabilityActionPlan([
      {
        key: "task_queue",
        title: "异步任务队列",
        status: "ok",
        available: true,
        detail: "正常。",
      },
    ]);

    expect(plan.headline).toBe("核心能力已就绪");
    expect(plan.badge).toBe("无阻断");
    expect(plan.items).toEqual([]);
  });
});

describe("formatValidationJobRunSummary", () => {
  it("explains cache hits and resumable leagues while a job is still running", () => {
    const summary = formatValidationJobRunSummary({
      job_id: "holdout-1",
      method: "holdout_validation_job_v1",
      status: "running",
      divisions: ["E0", "SP1", "D1", "I1"],
      training_seasons: ["2122"],
      validation_seasons: ["2223"],
      queue_backend: "arq",
      queue_job_id: "holdout-validation:holdout-1",
      queued_at_utc: "2026-06-02T05:41:35+00:00",
      queue_status_message: "Holdout validation was queued in ARQ and will be executed by the worker.",
      current_runner_id: "runnerabcdef123456",
      attempt_count: 3,
      retry_count: 2,
      last_claim_reason: "recovered_stale_runner",
      last_retry_at_utc: "2026-06-02T05:45:00+00:00",
      runner_heartbeat_at_utc: "2026-06-02T05:50:00+00:00",
      execution_health: {
        state: "running",
        severity: "info",
        title: "Worker 正在执行",
        detail: "runner 心跳正常。",
        next_action: "继续观察联赛进度和时间线。",
        is_stale: false,
        age_seconds: 600,
        queue_wait_seconds: 30,
        run_seconds: 500,
        heartbeat_age_seconds: 10,
        stale_after_seconds: 3900,
      },
      failure_summary: {
        failed_count: 1,
        recoverable: true,
        recoverable_count: 3,
        latest_error: "RuntimeError: source unavailable",
        category: "data_source",
        stage: "league_validation",
        severity: "error",
        title: "数据源或样本读取失败",
        detail: "验证阶段无法稳定读取比赛、赔率或样本数据。",
        next_action: "检查数据源健康、赔率/赛程快照和缓存；修复后点重试，已成功联赛会保留结果。",
        failed_leagues: [
          { division: "SP1", league: "西甲", status: "failed", error: "RuntimeError: source unavailable" },
        ],
      },
      progress: {
        total_leagues: 4,
        completed_leagues: 1,
        failed_leagues: 1,
        running_leagues: 1,
        pending_leagues: 1,
        processed_leagues: 2,
        progress_ratio: 0.5,
        success_ratio: 0.5,
      },
      events: [
        {
          id: 1,
          event_type: "job_created",
          severity: "info",
          message: "Created holdout validation job for 4 leagues.",
          metadata: {},
          created_at_utc: "2026-06-02T05:40:00+00:00",
        },
      ],
      league_results: [
        { division: "E0", league: "英超", status: "succeeded", cache_hit: true },
        { division: "SP1", league: "西甲", status: "failed", cache_hit: false, error: "source unavailable" },
        {
          division: "D1",
          league: "德甲",
          status: "running",
          cache_hit: false,
          runtime: { state: "running", is_running: true, run_seconds: 75, updated_age_seconds: 8, heartbeat_age_seconds: 6 },
        },
        { division: "I1", league: "意甲", status: "pending", cache_hit: false },
      ],
    });

    expect(summary).toEqual({
      tone: "caution",
      headline: "已处理 2/4 联赛，成功 1，失败 1",
      progressText: "50% 处理进度",
      cacheText: "1 个联赛复用缓存",
      activeText: "正在运行：德甲",
      resumeText: "可从未成功联赛继续：西甲、意甲",
      queueText: "ARQ worker 队列 · 06/02 13:41:35 入队",
      queueDetail: "Holdout validation was queued in ARQ and will be executed by the worker.",
      queueJobText: "holdout-validation:holdout-1",
      runnerText: "runner runnerabcdef",
      healthText: "Worker 正在执行 · runner 心跳正常。",
      healthNextAction: "继续观察联赛进度和时间线。",
      attemptText: "第 3 次执行 · 已从断联 worker 接管续跑",
      heartbeatText: "最近心跳 06/02 13:50:00",
      retryText: "已重试 2 次 · 06/02 13:45:00",
      failureText: "数据源或样本读取失败：西甲 · RuntimeError: source unavailable · 检查数据源健康、赔率/赛程快照和缓存；修复后点重试，已成功联赛会保留结果。",
      detail: "验证任务没有卡住；成功联赛会保留结果，失败和待跑联赛可由继续/重试动作续跑。",
    });
    expect(JSON.stringify(summary)).not.toContain("cache_hit");
  });

  it("marks a fully completed validation job without suggesting unnecessary resume", () => {
    const summary = formatValidationJobRunSummary({
      job_id: "holdout-2",
      method: "holdout_validation_job_v1",
      status: "completed",
      divisions: ["E0", "SP1"],
      training_seasons: ["2122"],
      validation_seasons: ["2223"],
      execution_health: {
        state: "completed",
        severity: "ok",
        title: "验证已完成",
        detail: "所有可处理联赛已经形成结果。",
        next_action: "查看验证结论和指标；需要复核时可重跑验证。",
        is_stale: false,
        age_seconds: 900,
        run_seconds: 120,
        stale_after_seconds: 3900,
      },
      progress: {
        total_leagues: 2,
        completed_leagues: 2,
        failed_leagues: 0,
        running_leagues: 0,
        pending_leagues: 0,
        processed_leagues: 2,
        progress_ratio: 1,
      },
      events: [],
      league_results: [
        { division: "E0", league: "英超", status: "succeeded", cache_hit: true },
        { division: "SP1", league: "西甲", status: "succeeded", cache_hit: true },
      ],
    });

    expect(summary.tone).toBe("good");
    expect(summary.headline).toBe("已处理 2/2 联赛，成功 2，失败 0");
    expect(summary.resumeText).toBe("全部联赛已有结果；重跑会复用缓存并只补缺失部分。");
    expect(summary.queueText).toBe("验证已完成 · 无需等待队列");
    expect(summary.queueDetail).toBe("任务已结束；队列只负责启动执行，不影响当前结论。");
    expect(summary.queueJobText).toBe("无队列任务 id");
    expect(summary.runnerText).toBe("执行已结束");
    expect(summary.attemptText).toBe("任务已完成");
    expect(summary.heartbeatText).toBe("无需 worker 心跳");
    expect(JSON.stringify(summary)).not.toContain("等待入队");
    expect(JSON.stringify(summary)).not.toContain("待接管");
    expect(JSON.stringify(summary)).not.toContain("等待 worker");
  });
});

describe("formatValidationLeagueRunDiagnostics", () => {
  it("prioritizes failed and active leagues with user-facing next actions", () => {
    const diagnostics = formatValidationLeagueRunDiagnostics({
      job_id: "holdout-1",
      method: "holdout_validation_job_v1",
      status: "running",
      divisions: ["E0", "SP1", "D1", "I1"],
      training_seasons: ["2122"],
      validation_seasons: ["2223"],
      progress: {
        total_leagues: 4,
        completed_leagues: 1,
        failed_leagues: 1,
        running_leagues: 1,
        pending_leagues: 1,
        processed_leagues: 2,
        progress_ratio: 0.5,
      },
      events: [],
      league_results: [
        {
          division: "E0",
          league: "英超",
          status: "succeeded",
          cache_hit: true,
          result: {
            calibrated_validation_result: {
              model_log_loss_1x2: 0.5,
              market_log_loss_1x2: 0.55,
              roi: 0.12,
            },
          },
        },
        { division: "SP1", league: "西甲", status: "failed", cache_hit: false, error: "RuntimeError: source unavailable" },
        {
          division: "D1",
          league: "德甲",
          status: "running",
          cache_hit: false,
          runtime: { state: "running", is_running: true, run_seconds: 75, updated_age_seconds: 8, heartbeat_age_seconds: 6 },
        },
        { division: "I1", league: "意甲", status: "pending", cache_hit: false },
      ],
    });

    expect(diagnostics.headline).toBe("1 个联赛失败，优先查看错误原因");
    expect(diagnostics.badge).toBe("1 失败 · 1 运行 · 1 等待");
    expect(diagnostics.rows.map((row) => row.name)).toEqual(["西甲", "德甲", "意甲", "英超"]);
    expect(diagnostics.rows[0]).toMatchObject({
      statusText: "失败",
      tone: "bad",
      errorText: "RuntimeError: source unavailable",
      actionText: "修复数据源或参数后点重试；已成功联赛会保留结果。",
    });
    expect(diagnostics.rows[1].runtimeText).toBe("已运行 1 分 15 秒 · 最近更新 8 秒前 · 心跳 6 秒前");
    expect(diagnostics.rows[3]).toMatchObject({
      cacheText: "命中缓存",
      logLossText: "-0.0500",
      roiText: "+12.0%",
    });
    expect(JSON.stringify(diagnostics)).not.toContain("cache_hit");
  });

  it("turns stale-runner recovery messages into readable guidance", () => {
    const diagnostics = formatValidationLeagueRunDiagnostics({
      job_id: "holdout-2",
      method: "holdout_validation_job_v1",
      status: "running",
      divisions: ["E0"],
      training_seasons: ["2122"],
      validation_seasons: ["2223"],
      progress: {
        total_leagues: 1,
        completed_leagues: 0,
        failed_leagues: 0,
        running_leagues: 0,
        pending_leagues: 1,
        processed_leagues: 0,
        progress_ratio: 0,
      },
      events: [],
      league_results: [
        {
          division: "E0",
          league: "英超",
          status: "pending",
          cache_hit: false,
          error: "Previous validation runner exceeded heartbeat window (60s); released for retry.",
        },
      ],
    });

    expect(diagnostics.headline).toBe("1 个联赛等待调度");
    expect(diagnostics.rows[0].errorText).toBe("上次运行超过恢复窗口，已释放给队列续跑。");
    expect(diagnostics.rows[0].actionText).toBe("等待队列调度；无需人工处理。");
  });
});

describe("formatValidationJobTimeline", () => {
  it("formats recent validation events newest first", () => {
    const timeline = formatValidationJobTimeline({
      job_id: "holdout-1",
      method: "holdout_validation_job_v1",
      status: "failed",
      divisions: ["E0"],
      training_seasons: ["2122"],
      validation_seasons: ["2223"],
      progress: {
        total_leagues: 1,
        completed_leagues: 0,
        failed_leagues: 1,
        running_leagues: 0,
        pending_leagues: 0,
        processed_leagues: 1,
        progress_ratio: 1,
      },
      events: [
        {
          id: 1,
          event_type: "job_created",
          severity: "info",
          message: "Created holdout validation job for 1 leagues.",
          metadata: {},
          created_at_utc: "2026-06-02T05:40:00+00:00",
        },
        {
          id: 2,
          event_type: "job_claimed",
          severity: "info",
          message: "Worker claimed the validation job.",
          runner_id: "runnerabcdef",
          metadata: {},
          created_at_utc: "2026-06-02T05:41:00+00:00",
        },
        {
          id: 3,
          event_type: "league_failed",
          severity: "error",
          message: "英超 failed: RuntimeError: source unavailable",
          division: "E0",
          runner_id: "runnerabcdef",
          metadata: {},
          created_at_utc: "2026-06-02T05:42:00+00:00",
        },
      ],
      league_results: [
        { division: "E0", league: "英超", status: "failed", cache_hit: false },
      ],
    });

    expect(timeline.badge).toBe("3 条事件");
    expect(timeline.rows.map((row) => row.title)).toEqual(["E0 验证失败", "Worker 接管", "创建验证任务"]);
    expect(timeline.rows[0]).toMatchObject({
      tone: "bad",
      timeText: "06/02 13:42:00",
      detailText: "联赛 E0 · runner runnerab",
    });
  });
});

describe("validationVerdictTone", () => {
  it("maps backend validation verdicts to user-facing tones", () => {
    expect(validationVerdictTone({ tone: "bad", status: "model_underperforms_market" })).toBe("bad");
    expect(validationVerdictTone({ status: "watchlist_candidate" })).toBe("good");
    expect(validationVerdictTone({ status: "insufficient_sample" })).toBe("caution");
  });
});

describe("formatValidationMetricScope", () => {
  it("explains that 1X2 holdout metrics do not validate Asian handicap accuracy", () => {
    const scope = formatValidationMetricScope({
      metric_scope: {
        probability_market: "moneyline_1x2",
        probability_market_label: "胜平负/1X2",
        asian_handicap_specific: false,
        asian_handicap_evaluated_count: 0,
        warning: "当前 Holdout 的 Log Loss/Brier 是胜平负/1X2 概率校验，不是亚盘专属验证。",
      },
      evaluated_count: 1,
      bet_count: 1,
    });

    expect(scope.tone).toBe("caution");
    expect(scope.badge).toBe("1X2 口径");
    expect(scope.title).toBe("不是亚盘专属验证");
    expect(scope.detail).toContain("不能证明亚盘模型已准确");
    expect(scope.sampleText).toBe("1 场可评估 · 1 条下注样本");
  });
});

describe("formatAsianHandicapValidation", () => {
  it("keeps Asian handicap validation separate when samples are still insufficient", () => {
    const display = formatAsianHandicapValidation({
      asian_handicap_validation: {
        market: "asian_handicap",
        status: "insufficient_sample",
        available_count: 110,
        evaluated_count: 110,
        bet_count: 30,
        hit_count: 16,
        push_count: 2,
        loss_count: 12,
        roi: 0.1,
        profit: 3,
        sample_gate: { min_bets_for_validation: 50, passed: false },
      },
    });

    expect(display.tone).toBe("caution");
    expect(display.badge).toBe("亚盘样本不足");
    expect(display.title).toBe("亚盘验证样本不足");
    expect(display.detail).toContain("不能证明 asian_handicap 模型已准确");
    expect(display.sampleText).toBe("30/110 下注/可评估");
    expect(display.roiText).toBe("+10.0%");
  });

  it("reports a ready Asian handicap validation sample as its own contract", () => {
    const display = formatAsianHandicapValidation({
      asian_handicap_validation: {
        market: "asian_handicap",
        status: "sample_ready",
        evaluated_count: 80,
        bet_count: 60,
        hit_count: 34,
        push_count: 4,
        loss_count: 22,
        roi: 0.04,
        profit: 2.4,
        sample_gate: { min_bets_for_validation: 50, passed: true },
      },
    });

    expect(display.tone).toBe("good");
    expect(display.badge).toBe("亚盘样本可评估");
    expect(display.title).toBe("亚盘专属验证已形成");
    expect(display.detail).toContain("和 1X2 Log Loss/Brier 分开判断");
    expect(display.resultText).toBe("命中 34 · 走水 4 · 亏损 22");
  });
});

describe("dashboardPollIntervalMs", () => {
  it("polls faster while a holdout validation job is pending or running", () => {
    expect(dashboardPollIntervalMs(null)).toBe(DASHBOARD_POLL_IDLE_MS);
    expect(dashboardPollIntervalMs({ validation_job: { status: "completed" } })).toBe(DASHBOARD_POLL_IDLE_MS);
    expect(dashboardPollIntervalMs({ validation_job: { status: "pending" } })).toBe(DASHBOARD_POLL_ACTIVE_VALIDATION_MS);
    expect(dashboardPollIntervalMs({ validation_job: { status: "running" } })).toBe(DASHBOARD_POLL_ACTIVE_VALIDATION_MS);
  });
});
