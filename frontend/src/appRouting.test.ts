import { describe, expect, it } from "vitest";
import { dashboardPath, matchDetailPath, parseDashboardRoute } from "./appRouting";

describe("dashboard routing", () => {
  it("routes root paths to the dashboard", () => {
    expect(parseDashboardRoute("/")).toEqual({ page: "dashboard", section: "overview" });
    expect(parseDashboardRoute("/?filter=open")).toEqual({ page: "dashboard", section: "overview" });
  });

  it("routes dashboard sections to shareable URLs", () => {
    expect(parseDashboardRoute("/production")).toEqual({ page: "dashboard", section: "production" });
    expect(parseDashboardRoute("/model")).toEqual({ page: "dashboard", section: "model" });
    expect(parseDashboardRoute("/signals")).toEqual({ page: "dashboard", section: "signals" });
    expect(parseDashboardRoute("/data")).toEqual({ page: "dashboard", section: "data" });
  });

  it("falls back unknown dashboard paths to overview", () => {
    expect(parseDashboardRoute("/unknown")).toEqual({ page: "dashboard", section: "overview" });
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
    expect(dashboardPath("data")).toBe("/data");
    expect(dashboardPath("overview")).toBe("/");
  });
});
