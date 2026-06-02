import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ProfitabilityPanel } from "./ProfitabilityPanel";
import type { DashboardProfitabilityForecast } from "../../types";

describe("ProfitabilityPanel", () => {
  it("does not present a losing model as ready", () => {
    const forecast: DashboardProfitabilityForecast = {
      available: true,
      model_state: "losing",
      method: "diagnostic_only",
      observed_hit_rate: 0.47,
      implied_roi_per_bet: -0.166,
      assumed_avg_odds: 1.77,
      settled_per_day_estimate: 20,
      settled_bets_so_far: 411,
      required_bets_total: null,
      remaining_bets: null,
      remaining_days: null,
      confidence_level: 0.95,
      break_even_hit_rate_needed: 0.563,
      hit_rate_gap: 0.093,
      interpretation: "模型当前在亏损，无法证明盈利路径。",
    };

    render(<ProfitabilityPanel forecast={forecast} />);

    expect(screen.getByText("无法证明盈利路径")).toBeInTheDocument();
    expect(screen.getByText("模型当前在亏损，无法证明盈利路径。")).toBeInTheDocument();
    expect(screen.queryByText("已达成")).not.toBeInTheDocument();
    expect(screen.queryByText("可启动正式策略验证")).not.toBeInTheDocument();
  });
});
