export interface MobileMatchSummary {
  id: string;
  query: string;
  homeTeam: string;
  awayTeam: string;
  league: string;
  kickoffText: string;
  kickoffUTC?: string | null;
  statusLabel: string;
  dataQuality: string;
  analysisReady: boolean;
}

export interface ProbabilityTriple {
  home: number;
  draw: number;
  away: number;
}

export interface TeamSummary {
  name: string;
  shortName: string;
}

export interface MarketBaseline {
  homeOdds: number;
  drawOdds: number;
  awayOdds: number;
  raw: ProbabilityTriple;
  devig: ProbabilityTriple;
  overround: number;
}

export interface OddsMovementPoint {
  label: string;
  opening: string;
  current: string;
  change: string;
  direction: "supportsHome" | "supportsAway" | "priceWorse" | "neutral";
  note: string;
}

export interface OddsMovementAnalysis {
  openingTime: string;
  currentTime: string;
  summary: string;
  marketSignal: string;
  points: OddsMovementPoint[];
  riskNote: string;
}

export interface ExpectedGoals {
  home: number;
  away: number;
}

export interface ScoreCell {
  homeBucket: number;
  awayBucket: number;
  homeLabel: string;
  awayLabel: string;
  probability: number;
}

export interface DataSourceEvidence {
  name: string;
  provider: string;
  freshness: string;
  confidence: "高" | "中等" | "偏低";
  usage: "参与计算" | "仅作参考" | "未采用";
  note: string;
}

export interface ProbabilityAdjustment {
  title: string;
  value: number;
  note: string;
  used: boolean;
}

export interface AsianHandicapAnalysis {
  line: number;
  lineLabel: string;
  sideLabel: string;
  odds: number;
  fullWin: number;
  halfWin: number;
  push: number;
  halfLoss: number;
  fullLoss: number;
  priceNote: string;
}

export interface TotalsAnalysis {
  line: number;
  lineLabel: string;
  overOdds: number;
  underOdds: number;
  overProbability: number;
  underProbability: number;
  note: string;
}

export interface RiskFlag {
  title: string;
  detail: string;
}

export interface ModelReadiness {
  status: string;
  label: string;
  summary: string;
  detail: string;
  updatedAtUTC?: string | null;
  method?: string | null;
  evaluatedCount: number;
  betCount: number;
  roi?: number | null;
  beatsMarket?: boolean | null;
  productionApproved: boolean;
}

export interface OddsSourceHealth {
  status: string;
  label: string;
  summary: string;
  detail: string;
  activeSource?: string | null;
  activeSourceLabel: string;
  productionReady: boolean;
  checkedAtUTC?: string | null;
  nextAction: string;
}

export interface MobileAnalysis {
  id: string;
  league: string;
  kickoffText: string;
  venue: string;
  homeTeam: TeamSummary;
  awayTeam: TeamSummary;
  finalProbabilities: ProbabilityTriple;
  confidence: "高" | "中等" | "偏低";
  dataQuality: string;
  marketBaseline: MarketBaseline;
  oddsMovement: OddsMovementAnalysis;
  expectedGoals: ExpectedGoals;
  scoreMatrix: ScoreCell[];
  dataSources: DataSourceEvidence[];
  adjustments: ProbabilityAdjustment[];
  modelReadiness: ModelReadiness;
  oddsSourceHealth: OddsSourceHealth;
  asian: AsianHandicapAnalysis;
  totals: TotalsAnalysis;
  risks: RiskFlag[];
}

export interface MobileMatchesResponse {
  status: string;
  generatedAtUTC: string;
  matches: MobileMatchSummary[];
  modelReadiness: ModelReadiness;
  oddsSourceHealth: OddsSourceHealth;
}

export interface MobileAnalysisResponse {
  status: string;
  generatedAtUTC: string;
  analysis: MobileAnalysis;
}

function buildQuery(params: Record<string, string | number | boolean | null | undefined>): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") return;
    search.set(key, String(value));
  });
  const text = search.toString();
  return text ? `?${text}` : "";
}

async function readJson<T>(url: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(url, {
    headers: { Accept: "application/json" },
    signal,
  });
  if (!response.ok) {
    throw new Error(`请求失败：${response.status}`);
  }
  return await response.json() as T;
}

export async function fetchMobileMatches(
  params: {
    query?: string;
    league?: string;
    windowHours?: number;
    limit?: number;
    includeUnready?: boolean;
  } = {},
  signal?: AbortSignal,
): Promise<MobileMatchesResponse> {
  return readJson<MobileMatchesResponse>(
    `/api/mobile/matches${buildQuery({
      query: params.query,
      league: params.league,
      window_hours: params.windowHours ?? 24,
      limit: params.limit ?? 20,
      include_unready: params.includeUnready,
      timezone: "Asia/Shanghai",
    })}`,
    signal,
  );
}

export async function fetchMobileAnalysis(
  params: {
    query?: string;
    homeTeam?: string;
    awayTeam?: string;
    league?: string;
    windowHours?: number;
  },
  signal?: AbortSignal,
): Promise<MobileAnalysisResponse> {
  return readJson<MobileAnalysisResponse>(
    `/api/mobile/analysis${buildQuery({
      query: params.query,
      home_team: params.homeTeam,
      away_team: params.awayTeam,
      league: params.league,
      window_hours: params.windowHours ?? 24,
      timezone: "Asia/Shanghai",
    })}`,
    signal,
  );
}
