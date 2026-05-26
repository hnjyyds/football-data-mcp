export type DashboardRoute =
  | { page: "dashboard" }
  | { page: "match"; ledgerId: string };

export function dashboardPath(): string {
  return "/";
}

export function matchDetailPath(ledgerId: string): string {
  return `/match/${encodeURIComponent(ledgerId)}`;
}

export function parseDashboardRoute(pathWithSearch: string): DashboardRoute {
  const url = new URL(pathWithSearch || "/", "http://dashboard.local");
  const match = url.pathname.match(/^\/match\/([^/]+)$/);
  if (!match) return { page: "dashboard" };
  return {
    page: "match",
    ledgerId: decodeURIComponent(match[1])
  };
}
