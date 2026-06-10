import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PickGrid } from "./PickCard";
import type { DashboardRecord } from "../../types";

function record(overrides: Partial<DashboardRecord>): DashboardRecord {
  return {
    id: "rec-1",
    league: "EPL",
    matchup: "Arsenal vs Chelsea",
    home_team: "Arsenal",
    away_team: "Chelsea",
    kickoff_utc_plus_8: "2026-06-06T20:00:00+08:00",
    market: "asian_handicap",
    selection: "Arsenal -0.5",
    selection_key: "home_cover",
    line: -0.5,
    decimal_odds: 1.92,
    model_probability: 0.5,
    learned_probability: 0.5,
    edge: 0.03,
    recommendation: "immediate_bet",
    stake_level: "small",
    risk_flags: [],
    caution_flags: [],
    settlement_status: "open",
    created_at_utc: "2026-06-06T10:00:00+00:00",
    ...overrides,
  };
}

describe("PickGrid", () => {
  it("groups records into three probability tiers and sorts within each tier", () => {
    render(
      <PickGrid
        records={[
          record({ id: "low-1", home_team: "Low FC", away_team: "Away A", learned_probability: 0.54, matchup: "Low FC vs Away A" }),
          record({ id: "high-1", home_team: "High FC", away_team: "Away B", learned_probability: 0.73, matchup: "High FC vs Away B", created_at_utc: "2026-06-06T10:00:00+00:00" }),
          record({ id: "mid-1", home_team: "Mid FC", away_team: "Away C", learned_probability: 0.61, matchup: "Mid FC vs Away C" }),
          record({ id: "high-2", home_team: "Higher FC", away_team: "Away D", learned_probability: 0.68, matchup: "Higher FC vs Away D", created_at_utc: "2026-06-07T10:00:00+00:00" }),
        ]}
      />,
    );

    expect(screen.getByText("高概率")).toBeInTheDocument();
    expect(screen.getByText("中概率")).toBeInTheDocument();
    expect(screen.getByText("低概率")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /低概率/ }));

    const highCards = screen.getAllByText(/High FC|Higher FC/).map((node) => node.textContent);
    expect(highCards).toEqual(["Higher FC", "High FC"]);
    expect(screen.getByText("Mid FC")).toBeInTheDocument();
    expect(screen.getByText("Low FC")).toBeInTheDocument();
  });

  it("supports collapsing and paginating each probability group", () => {
    const highRecords = Array.from({ length: 7 }, (_, index) =>
      record({
        id: `high-${index}`,
        home_team: `High ${index}`,
        away_team: `Away ${index}`,
        matchup: `High ${index} vs Away ${index}`,
        learned_probability: 0.7 - index * 0.001,
      }),
    );

    render(<PickGrid records={highRecords} />);

    expect(screen.getByText("第 1 / 2 页")).toBeInTheDocument();
    expect(screen.getByText("High 0")).toBeInTheDocument();
    expect(screen.queryByText("High 6")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "下一页" }));
    expect(screen.getByText("第 2 / 2 页")).toBeInTheDocument();
    expect(screen.getByText("High 6")).toBeInTheDocument();

    const highToggle = screen.getByRole("button", { name: /高概率/ });
    fireEvent.click(highToggle);
    expect(screen.queryByText("High 6")).not.toBeInTheDocument();
  });

  it("shows final score and settlement result for finished predictions", () => {
    render(
      <PickGrid
        records={[
          record({
            id: "settled-1",
            home_team: "Settled FC",
            away_team: "Away Done",
            learned_probability: 0.62,
            settlement_status: "settled",
            status_label: "命中",
            score: "2-1",
            true_result: { home_score: 2, away_score: 1, score: "2-1" },
            hit: 1,
            profit_units: 0.92,
            settled_at_utc: "2026-06-06T14:00:00+00:00",
          }),
        ]}
      />,
    );

    expect(screen.getAllByText("命中").length).toBeGreaterThan(0);
    expect(screen.getByText("赛果")).toBeInTheDocument();
    expect(screen.getByText("2-1")).toBeInTheDocument();
    expect(screen.getByText("+0.92u")).toBeInTheDocument();
  });

  it("renders immediate_bet as observation-style badge", () => {
    render(
      <PickGrid
        records={[
          record({
            id: "immediate-1",
            recommendation: "immediate_bet",
            learned_probability: 0.62,
          }),
        ]}
      />,
    );

    expect(screen.getByText("观察")).toBeInTheDocument();
    expect(screen.queryByText("强买")).not.toBeInTheDocument();
  });
});
