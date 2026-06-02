import type { DashboardSectionKey } from "./types";

export type DashboardRoute =
  | { page: "dashboard"; section: DashboardSectionKey }
  | { page: "match"; ledgerId: string };

const SECTION_PATHS: Record<DashboardSectionKey, string> = {
  overview: "/",
  production: "/production",
  model: "/model",
  signals: "/signals",
  data: "/data",
};

const PATH_SECTIONS = new Map<string, DashboardSectionKey>(
  Object.entries(SECTION_PATHS).map(([section, path]) => [path, section as DashboardSectionKey]),
);

export function dashboardPath(section: DashboardSectionKey = "overview"): string {
  return SECTION_PATHS[section] ?? "/";
}

export function matchDetailPath(ledgerId: string): string {
  return `/match/${encodeURIComponent(ledgerId)}`;
}

export function parseDashboardRoute(pathWithSearch: string): DashboardRoute {
  const url = new URL(pathWithSearch || "/", "http://dashboard.local");
  const match = url.pathname.match(/^\/match\/([^/]+)$/);
  if (!match) {
    return { page: "dashboard", section: PATH_SECTIONS.get(url.pathname) ?? "overview" };
  }
  return {
    page: "match",
    ledgerId: decodeURIComponent(match[1])
  };
}
