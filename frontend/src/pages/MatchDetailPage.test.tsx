import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { MatchDetailPage } from "./MatchDetailPage";
import type { DashboardMatchDetail } from "../types";

function detail(): DashboardMatchDetail {
  return {
    status: "ok",
    tool: "dashboard_match_detail",
    generated_at_utc: "2026-06-02T10:00:00+00:00",
    record: {
      ledger_id: "recommendation:2726",
      league: "测试联赛",
      matchup: "主队 vs 客队",
      home_team: "主队",
      away_team: "客队",
      kickoff_utc_plus_8: "06/02 20:00",
      market: "asian_handicap",
      selection: "主队 +0.25",
      decimal_odds: 1.88,
      edge: 0.04,
      recommendation: "condition_observe",
    } as any,
    match_context: {
      source: { status: "matched", provider: "test", label: "测试源", match_id: "m1", detail: "ok" },
      venue: { available: true, text: "测试球场", status: "available" },
      weather: { available: false, text: "源站暂无信息", status: "source_empty" },
      referee: { available: false, text: "源站暂无信息", status: "source_empty" },
      lineup: {
        available: false,
        basis: "not_collected",
        home: { formation: "", starter_count: 0, starters: [] },
        away: { formation: "", starter_count: 0, starters: [] },
        warnings: [],
        analysis: {},
      },
      players: { available: false, home: [], away: [] },
      available_blocks: ["venue"],
      source_attempts: [],
    } as any,
    odds_snapshot: { snapshot_count: 0, latest_rows: [] } as any,
    evidence: {
      core_metrics: {
        decimal_odds: 1.88,
        model_probability: 0.57,
        learned_probability: 0.55,
        market_probability: 0.51,
        edge: 0.04,
        expected_multiplier: 1.034,
      },
      final_execution_advice: {
        action: "observe",
        reason: "formal_gate_closed",
      },
      prediction_diagnostic: {
        actionability_label: "观察样本",
        primary_reason: "正式推荐门禁未开放",
      },
      market_candidates: [],
      risk_flags: [],
      caution_flags: [],
    } as any,
    strategy_state: {} as any,
    timeline: [],
    policy: {} as any,
  };
}

describe("MatchDetailPage Lark action", () => {
  it("sends the prediction sample to Lark without labeling it as a recommendation action", () => {
    const onSendPredictionToLark = vi.fn();

    render(
      <MatchDetailPage
        ledgerId="recommendation:2726"
        detail={detail()}
        loading={false}
        error={null}
        onBack={vi.fn()}
        onSendPredictionToLark={onSendPredictionToLark}
      />,
    );

    const button = screen.getByRole("button", { name: "发送预测到 Lark" });
    fireEvent.click(button);

    expect(onSendPredictionToLark).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("button", { name: /发送推荐/ })).not.toBeInTheDocument();
  });
});
