import { describe, expect, it } from "vitest";
import { dashboardPath, matchDetailPath, parseDashboardRoute } from "./appRouting";

describe("dashboard routing", () => {
  it("routes root paths to the dashboard", () => {
    expect(parseDashboardRoute("/")).toEqual({ page: "dashboard" });
    expect(parseDashboardRoute("/?filter=open")).toEqual({ page: "dashboard" });
  });

  it("routes encoded ledger ids to match detail pages", () => {
    expect(parseDashboardRoute("/match/recommendation%3A1413")).toEqual({
      page: "match",
      ledgerId: "recommendation:1413"
    });
  });

  it("builds stable same-tab paths", () => {
    expect(matchDetailPath("shadow_prediction:22")).toBe("/match/shadow_prediction%3A22");
    expect(dashboardPath()).toBe("/");
  });
});
