import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { LedgerTable } from "./LedgerTable";
import type { PredictionLedgerRow } from "../../types";

function row(overrides: Partial<PredictionLedgerRow>): PredictionLedgerRow {
  return {
    ledger_id: "rec:1",
    prediction_type: "recommendation",
    league: "EPL",
    home_team: "Arsenal",
    away_team: "Chelsea",
    home_team_logo_url: null,
    away_team_logo_url: null,
    market: "asian_handicap",
    selection: "home -0.5",
    line: -0.5,
    decimal_odds: 1.92,
    learned_probability: 0.55,
    model_probability: 0.52,
    edge: 0.03,
    settlement_status: "settled",
    hit: 1,
    kickoff_utc: "2026-05-26T11:00:00+00:00",
    kickoff_utc_plus_8: "2026-05-26T19:00:00+00:00",
    created_at_utc: "2026-05-26T05:00:00+00:00",
    settled_at_utc: "2026-05-26T13:00:00+00:00",
    ...overrides,
  } as PredictionLedgerRow;
}

describe("LedgerTable a11y", () => {
  it("rows are buttons (keyboard navigable) and fire onSelect on Enter", () => {
    const onSelect = vi.fn();
    render(<LedgerTable rows={[row({ ledger_id: "rec:1" })]} onSelect={onSelect} />);
    const r = screen.getByRole("button", { name: /Arsenal/i });
    expect(r).toHaveAttribute("tabindex", "0");
    fireEvent.keyDown(r, { key: "Enter" });
    expect(onSelect).toHaveBeenCalledWith("rec:1");
  });

  it("Space key also activates a row", () => {
    const onSelect = vi.fn();
    render(<LedgerTable rows={[row({ ledger_id: "rec:1" })]} onSelect={onSelect} />);
    const r = screen.getByRole("button", { name: /Arsenal/i });
    fireEvent.keyDown(r, { key: " " });
    expect(onSelect).toHaveBeenCalledWith("rec:1");
  });

  it("provides accessible text alongside hit/miss color badges", () => {
    const { container } = render(
      <LedgerTable
        rows={[
          row({ ledger_id: "a", hit: 1, settlement_status: "settled" }),
          row({ ledger_id: "b", hit: 0, settlement_status: "settled", home_team: "Liverpool", away_team: "Spurs" }),
        ]}
      />
    );
    const cellText = Array.from(container.querySelectorAll("tbody td"))
      .map((el) => el.textContent ?? "")
      .join("|");
    expect(cellText).toContain("命中");
    expect(cellText).toContain("未中");
  });

  it("StatusIcon has aria-label so screen readers pick up status", () => {
    const { container } = render(<LedgerTable rows={[row({ ledger_id: "a", hit: 1, settlement_status: "settled" })]} />);
    const iconWithLabel = container.querySelector('tbody [aria-label="命中"]');
    expect(iconWithLabel).not.toBeNull();
  });

  it("shows filter counts and can focus awaiting reanalysis rows", () => {
    render(
      <LedgerTable
        rows={[
          row({
            ledger_id: "awaiting:1",
            home_team: "Awaiting FC",
            away_team: "Snapshot United",
            settlement_status: "open",
            rejection_reason: "awaiting_reanalysis_after_snapshot",
            prediction_diagnostic: {
              primary_reason: "awaiting_reanalysis_after_snapshot",
            } as PredictionLedgerRow["prediction_diagnostic"],
          }),
          row({
            ledger_id: "open:1",
            home_team: "Open FC",
            away_team: "Normal United",
            settlement_status: "open",
            rejection_reason: "no_positive_edge",
          }),
        ]}
      />,
    );

    expect(screen.getByRole("button", { name: "待复算 1" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "待复算 1" }));
    expect(screen.getByText("Awaiting FC")).toBeInTheDocument();
    expect(screen.queryByText("Open FC")).not.toBeInTheDocument();
  });

  it("accepts an external blocker reason filter and exposes a clear action", () => {
    const onClear = vi.fn();
    render(
      <LedgerTable
        reasonFilter={{ reason: "no_positive_edge", label: "无正向边际" }}
        onReasonFilterClear={onClear}
        rows={[
          row({
            ledger_id: "blocked:1",
            home_team: "Blocked FC",
            away_team: "Reason United",
            rejection_reason: "no_positive_edge",
          }),
          row({
            ledger_id: "other:1",
            home_team: "Other FC",
            away_team: "Reason United",
            rejection_reason: "edge_below_threshold",
          }),
        ]}
      />,
    );

    expect(screen.getByText("无正向边际")).toBeInTheDocument();
    expect(screen.getByText("Blocked FC")).toBeInTheDocument();
    expect(screen.queryByText("Other FC")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "清除阻断筛选" }));
    expect(onClear).toHaveBeenCalledTimes(1);
  });
});
