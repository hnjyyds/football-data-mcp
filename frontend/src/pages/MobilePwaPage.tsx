import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent, type ReactNode } from "react";
import {
  Activity,
  BarChart3,
  CalendarClock,
  ChevronRight,
  Gauge,
  LineChart,
  RefreshCw,
  Search,
  ShieldCheck,
  Trophy,
  Waves,
} from "lucide-react";
import {
  fetchMobileAnalysis,
  fetchMobileMatches,
  type AsianHandicapAnalysis,
  type DataSourceEvidence,
  type MobileAnalysis,
  type MobileMatchSummary,
  type ModelReadiness,
  type OddsMovementPoint,
  type OddsSourceHealth,
  type ProbabilityAdjustment,
  type ProbabilityTriple,
  type ScoreCell,
  type TotalsAnalysis,
} from "../api/mobileClient";

type Perspective = "胜平负" | "亚盘" | "大小球";

const DEMO_MATCHES: MobileMatchSummary[] = [
  {
    id: "demo-ars-che",
    query: "阿森纳 vs 切尔西",
    homeTeam: "阿森纳",
    awayTeam: "切尔西",
    league: "英超",
    kickoffText: "今晚 22:00",
    statusLabel: "可分析",
    dataQuality: "演示",
    analysisReady: true,
  },
  {
    id: "demo-int-juv",
    query: "国际米兰 vs 尤文图斯",
    homeTeam: "国际米兰",
    awayTeam: "尤文图斯",
    league: "意甲",
    kickoffText: "明天 02:45",
    statusLabel: "可分析",
    dataQuality: "演示",
    analysisReady: true,
  },
];

const DEMO_ANALYSIS: MobileAnalysis = {
  id: "demo-ars-che",
  league: "英超",
  kickoffText: "今晚 22:00",
  venue: "主场",
  homeTeam: { name: "阿森纳", shortName: "阿森纳" },
  awayTeam: { name: "切尔西", shortName: "切尔西" },
  finalProbabilities: { home: 0.47, draw: 0.27, away: 0.26 },
  confidence: "中等",
  dataQuality: "演示样本",
  marketBaseline: {
    homeOdds: 2.05,
    drawOdds: 3.38,
    awayOdds: 3.76,
    raw: { home: 0.4878, draw: 0.2959, away: 0.266 },
    devig: { home: 0.464, draw: 0.281, away: 0.255 },
    overround: 0.0497,
  },
  oddsMovement: {
    openingTime: "早盘",
    currentTime: "当前",
    summary: "盘口走势：阿森纳升温，赔率 2.18->2.05，隐含概率 +2.9%。",
    marketSignal: "盘口走势支持当前候选",
    riskNote: "赔率研究：模型 47.0% vs 去水市场 46.4%，EV 较薄，最好价很重要。",
    points: [
      {
        label: "主胜",
        opening: "2.18",
        current: "2.05",
        change: "+2.9%",
        direction: "supportsHome",
        note: "隐含概率上升，市场更认可主队方向，但价格也变紧。",
      },
      {
        label: "亚盘 -0.25",
        opening: "-0.25 @ 1.98",
        current: "-0.25 @ 1.88",
        change: "+2.7%",
        direction: "supportsHome",
        note: "亚盘方向同样升温。",
      },
    ],
  },
  expectedGoals: { home: 1.44, away: 1.08 },
  scoreMatrix: [
    { homeBucket: 0, awayBucket: 0, homeLabel: "0", awayLabel: "0", probability: 0.073 },
    { homeBucket: 1, awayBucket: 0, homeLabel: "1", awayLabel: "0", probability: 0.105 },
    { homeBucket: 1, awayBucket: 1, homeLabel: "1", awayLabel: "1", probability: 0.114 },
    { homeBucket: 2, awayBucket: 1, homeLabel: "2", awayLabel: "1", probability: 0.082 },
    { homeBucket: 2, awayBucket: 0, homeLabel: "2", awayLabel: "0", probability: 0.075 },
    { homeBucket: 0, awayBucket: 1, homeLabel: "0", awayLabel: "1", probability: 0.079 },
    { homeBucket: 2, awayBucket: 2, homeLabel: "2", awayLabel: "2", probability: 0.044 },
    { homeBucket: 1, awayBucket: 2, homeLabel: "1", awayLabel: "2", probability: 0.049 },
    { homeBucket: 3, awayBucket: 1, homeLabel: "3+", awayLabel: "1", probability: 0.039 },
  ],
  dataSources: [
    { name: "赔率/盘口", provider: "多源赔率", freshness: "当前快照", confidence: "高", usage: "参与计算", note: "用于换算基础概率和当前价值。" },
    { name: "赔率走势", provider: "market_snapshots", freshness: "历史快照", confidence: "中等", usage: "参与计算", note: "用于小幅校准概率，并提示价格是否已经变紧。" },
    { name: "比分模型", provider: "Dixon-Coles/Poisson", freshness: "本次计算", confidence: "中等", usage: "参与计算", note: "把赔率、大小球和亚盘转换成比分分布。" },
  ],
  adjustments: [
    { title: "原始模型概率", value: 0.47, note: "由当前赔率、亚盘、大小球和比分模型得到。", used: true },
    { title: "赔率走势校准", value: 0.012, note: "只在有历史快照时小幅调整。", used: true },
    { title: "当前赔率价值", value: -0.0365, note: "最终仍按当前赔率重新计算 EV。", used: true },
    { title: "去水市场对照", value: 0.006, note: "比较模型概率和去水后的市场共识。", used: true },
  ],
  modelReadiness: {
    status: "not_ready",
    label: "未通过验证",
    summary: "最近 holdout 仍未通过，不能把当前模型当成生产自动化信号。",
    detail: "方法 holdout_v2 · 评估 84 场 · ROI -5.0% · log-loss 差值 +0.020",
    updatedAtUTC: "2026-06-03T12:00:00+00:00",
    method: "holdout_v2",
    evaluatedCount: 84,
    betCount: 0,
    roi: -0.05,
    beatsMarket: false,
    productionApproved: false,
  },
  oddsSourceHealth: {
    status: "fallback",
    label: "使用兜底赔率源",
    summary: "雷速不可用或过期，当前使用独立爬虫赔率源兜底。",
    detail: "雷速不可用或过期，当前使用独立爬虫赔率源兜底。",
    activeSource: "oddsportal_scraper",
    activeSourceLabel: "OddsPortal",
    productionReady: true,
    checkedAtUTC: "2026-06-03T12:05:00+00:00",
    nextAction: "OddsPortal 兜底快照正常运行，等待雷速恢复后切回主源。",
  },
  asian: {
    line: -0.25,
    lineLabel: "主队 -0.25",
    sideLabel: "阿森纳",
    odds: 1.88,
    fullWin: 0.39,
    halfWin: 0.08,
    push: 0.0,
    halfLoss: 0.27,
    fullLoss: 0.26,
    priceNote: "亚盘概率来自比分分布，当前赔率决定是否还有价值。",
  },
  totals: {
    line: 2.5,
    lineLabel: "2.5 球",
    overOdds: 1.95,
    underOdds: 1.89,
    overProbability: 0.51,
    underProbability: 0.49,
    note: "总进球分布接近均衡，价格变化比单点概率更重要。",
  },
  risks: [
    { title: "价格已变紧", detail: "盘口支持方向升温，但可买价格下降后 EV 变薄。" },
  ],
};

export default function MobilePwaPage() {
  const [matches, setMatches] = useState<MobileMatchSummary[]>([]);
  const [selected, setSelected] = useState<MobileMatchSummary | null>(null);
  const [analysis, setAnalysis] = useState<MobileAnalysis | null>(null);
  const [perspective, setPerspective] = useState<Perspective>("胜平负");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("正在连接实时数据");
  const [matchesLoading, setMatchesLoading] = useState(false);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const matchesControllerRef = useRef<AbortController | null>(null);
  const analysisControllerRef = useRef<AbortController | null>(null);
  const latestAnalysisKeyRef = useRef("");
  const analysisCacheRef = useRef<Map<string, MobileAnalysis>>(new Map());
  const loading = matchesLoading || analysisLoading;
  const visibleMatches = matches.length > 0 ? matches : DEMO_MATCHES;
  const displayAnalysis = analysis ?? DEMO_ANALYSIS;

  const loadMatches = useCallback(async (searchText = "") => {
    matchesControllerRef.current?.abort();
    const controller = new AbortController();
    matchesControllerRef.current = controller;
    setMatchesLoading(true);
    try {
      const response = await fetchMobileMatches({ query: searchText.trim(), limit: 20 }, controller.signal);
      if (controller.signal.aborted) return;
      if (response.matches.length > 0) {
        setMatches(response.matches);
        setSelected((current) => {
          if (!current) return response.matches[0];
          const stillVisible = response.matches.find((match) => matchKey(match) === matchKey(current));
          return stillVisible ?? response.matches[0];
        });
        setStatus("实时数据");
      } else {
        setMatches(DEMO_MATCHES);
        setSelected(DEMO_MATCHES[0]);
        setAnalysis(DEMO_ANALYSIS);
        setStatus("暂无真实比赛，显示演示样本");
      }
    } catch (error) {
      if (controller.signal.aborted) return;
      setStatus("后端未连接，显示演示样本");
      setMatches(DEMO_MATCHES);
      setSelected(DEMO_MATCHES[0]);
      setAnalysis(DEMO_ANALYSIS);
    } finally {
      if (matchesControllerRef.current === controller) {
        matchesControllerRef.current = null;
        setMatchesLoading(false);
      }
    }
  }, []);

  const loadAnalysis = useCallback(async (match: MobileMatchSummary, options: { force?: boolean } = {}) => {
    const key = matchKey(match);
    if (isDemoMatch(match)) {
      analysisControllerRef.current?.abort();
      setAnalysis({
        ...DEMO_ANALYSIS,
        id: match.id,
        league: match.league,
        kickoffText: match.kickoffText,
        homeTeam: { name: match.homeTeam, shortName: match.homeTeam.slice(0, 4) },
        awayTeam: { name: match.awayTeam, shortName: match.awayTeam.slice(0, 4) },
      });
      setStatus("演示模式");
      setAnalysisLoading(false);
      return;
    }

    if (!options.force) {
      const cached = analysisCacheRef.current.get(key);
      if (cached) {
        setAnalysis(cached);
        setStatus("实时数据");
        return;
      }
    }

    analysisControllerRef.current?.abort();
    const controller = new AbortController();
    analysisControllerRef.current = controller;
    latestAnalysisKeyRef.current = key;
    setAnalysisLoading(true);
    try {
      const response = await fetchMobileAnalysis({
        query: match.query,
        homeTeam: match.homeTeam,
        awayTeam: match.awayTeam,
        league: match.league,
      }, controller.signal);
      if (controller.signal.aborted || latestAnalysisKeyRef.current !== key) return;
      rememberAnalysis(analysisCacheRef.current, key, response.analysis);
      setAnalysis(response.analysis);
      setStatus("实时数据");
    } catch (error) {
      if (controller.signal.aborted) return;
      setAnalysis({
        ...DEMO_ANALYSIS,
        id: match.id,
        league: match.league,
        kickoffText: match.kickoffText,
        homeTeam: { name: match.homeTeam, shortName: match.homeTeam.slice(0, 4) },
        awayTeam: { name: match.awayTeam, shortName: match.awayTeam.slice(0, 4) },
      });
      setStatus("后端未连接，显示演示样本");
    } finally {
      if (analysisControllerRef.current === controller) {
        analysisControllerRef.current = null;
        setAnalysisLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    loadMatches();
    return () => {
      matchesControllerRef.current?.abort();
      analysisControllerRef.current?.abort();
    };
  }, [loadMatches]);

  useEffect(() => {
    if (selected) {
      loadAnalysis(selected);
    }
  }, [loadAnalysis, selected]);

  const topScores = useMemo(() => [...displayAnalysis.scoreMatrix].sort((a, b) => b.probability - a.probability).slice(0, 9), [displayAnalysis.scoreMatrix]);

  const selectMatch = useCallback((match: MobileMatchSummary) => {
    setSelected((current) => (current && matchKey(current) === matchKey(match) ? current : match));
  }, []);

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    loadMatches(query.trim());
  }

  return (
    <main className="min-h-screen bg-[#f7f8fa] text-ink-900" aria-busy={loading}>
      <div className="mx-auto flex min-h-screen w-full max-w-md flex-col bg-[#fbfcfd] shadow-elevated">
        <header className="sticky top-0 z-20 border-b border-ink-200 bg-[#fbfcfd]/95 px-4 pb-3 pt-[max(0.75rem,env(safe-area-inset-top))] backdrop-blur">
          <div className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <p className="text-xs font-semibold text-brand-700">足球胜率研究</p>
              <h1 className="truncate text-xl font-bold">比赛分析</h1>
            </div>
            <button
              type="button"
              onClick={() => selected ? loadAnalysis(selected, { force: true }) : loadMatches(query.trim())}
              className="grid h-10 w-10 shrink-0 place-items-center rounded-lg border border-ink-200 bg-white text-ink-700 shadow-sm"
              disabled={loading}
              aria-label="刷新"
            >
              <RefreshCw size={18} className={loading ? "animate-spin" : ""} />
            </button>
          </div>
          <form onSubmit={submitSearch} className="mt-3 flex h-11 items-center gap-2 rounded-lg border border-ink-200 bg-white px-3">
            <Search size={17} className="text-ink-400" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="搜索球队或赛事"
              className="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-ink-400"
            />
            <button type="submit" className="rounded-md bg-ink-900 px-3 py-1.5 text-xs font-semibold text-white">
              搜索
            </button>
          </form>
        </header>

        <section className="px-4 pt-4">
          <div className="flex gap-2 overflow-x-auto pb-1">
            {visibleMatches.map((match) => (
              <button
                key={match.id}
                type="button"
                onClick={() => selectMatch(match)}
                className={`min-w-[168px] rounded-lg border p-3 text-left transition ${
                  selected?.id === match.id
                    ? "border-brand-500 bg-brand-50 shadow-sm"
                    : "border-ink-200 bg-white"
                }`}
              >
                <div className="flex items-center justify-between gap-2 text-[11px] text-ink-500">
                  <span className="truncate">{match.league}</span>
                  <span>{match.statusLabel}</span>
                </div>
                <div className="mt-2 text-sm font-bold leading-5">{match.homeTeam}</div>
                <div className="text-sm font-bold leading-5 text-ink-600">{match.awayTeam}</div>
                <div className="mt-2 flex items-center gap-1 text-[11px] text-ink-500">
                  <CalendarClock size={13} />
                  <span className="truncate">{match.kickoffText}</span>
                </div>
              </button>
            ))}
          </div>
        </section>

        <section className="px-4 pt-3">
          <div className="rounded-lg border border-ink-200 bg-white p-4 shadow-sm">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="flex items-center gap-2 text-xs font-semibold text-brand-700">
                  <Trophy size={15} />
                  <span>{displayAnalysis.league}</span>
                </div>
                <h2 className="mt-2 text-lg font-bold leading-6">
                  {displayAnalysis.homeTeam.name} vs {displayAnalysis.awayTeam.name}
                </h2>
                <p className="mt-1 text-xs text-ink-500">{displayAnalysis.kickoffText} · {displayAnalysis.venue}</p>
              </div>
              <div className="rounded-lg bg-ink-900 px-3 py-2 text-center text-white">
                <div className="text-[10px] text-ink-300">置信</div>
                <div className="text-sm font-bold">{displayAnalysis.confidence}</div>
              </div>
            </div>

            <div className="mt-4 grid grid-cols-3 gap-2">
              <ProbabilityTile label="主胜" value={displayAnalysis.finalProbabilities.home} tone="home" />
              <ProbabilityTile label="平局" value={displayAnalysis.finalProbabilities.draw} tone="draw" />
              <ProbabilityTile label="客胜" value={displayAnalysis.finalProbabilities.away} tone="away" />
            </div>
            <ProbabilityStack probabilities={displayAnalysis.finalProbabilities} />
            <StatusOverview readiness={displayAnalysis.modelReadiness} oddsSourceHealth={displayAnalysis.oddsSourceHealth} />
          </div>
        </section>

        <section className="px-4 pt-3">
          <div className="grid grid-cols-3 rounded-lg border border-ink-200 bg-white p-1 shadow-sm">
            {(["胜平负", "亚盘", "大小球"] as Perspective[]).map((item) => (
              <button
                key={item}
                type="button"
                onClick={() => setPerspective(item)}
                className={`h-9 rounded-md text-sm font-semibold ${
                  perspective === item ? "bg-ink-900 text-white" : "text-ink-500"
                }`}
              >
                {item}
              </button>
            ))}
          </div>
        </section>

        <section className="space-y-3 px-4 py-3">
          {perspective === "胜平负" && (
            <>
              <MarketBaselineCard analysis={displayAnalysis} />
              <OddsMovementCard movement={displayAnalysis.oddsMovement.points} summary={displayAnalysis.oddsMovement.summary} signal={displayAnalysis.oddsMovement.marketSignal} riskNote={displayAnalysis.oddsMovement.riskNote} />
              <ScoreGrid cells={topScores} />
            </>
          )}
          {perspective === "亚盘" && (
            <>
              <AsianCard asian={displayAnalysis.asian} />
              <AdjustmentCard adjustments={displayAnalysis.adjustments} />
            </>
          )}
          {perspective === "大小球" && (
            <>
              <TotalsCard totals={displayAnalysis.totals} expectedGoals={displayAnalysis.expectedGoals} />
              <ScoreGrid cells={topScores} />
            </>
          )}
          <DataSourceCard sources={displayAnalysis.dataSources} risks={displayAnalysis.risks} />
        </section>

        <footer className="px-4 pb-[max(1.25rem,env(safe-area-inset-bottom))] pt-1 text-center text-[11px] text-ink-400">
          {status} · 只做研究，不执行交易
        </footer>
      </div>
    </main>
  );
}

function isDemoMatch(match: MobileMatchSummary): boolean {
  return match.id.startsWith("demo-") || match.dataQuality === "演示";
}

function matchKey(match: MobileMatchSummary): string {
  return [match.id, match.query, match.league].join("|").toLowerCase();
}

function rememberAnalysis(cache: Map<string, MobileAnalysis>, key: string, analysis: MobileAnalysis) {
  cache.set(key, analysis);
  if (cache.size <= 30) return;
  const oldestKey = cache.keys().next().value;
  if (oldestKey) cache.delete(oldestKey);
}

function ProbabilityTile({ label, value, tone }: { label: string; value: number; tone: "home" | "draw" | "away" }) {
  const colors = {
    home: "bg-brand-50 text-brand-800",
    draw: "bg-ink-100 text-ink-700",
    away: "bg-strike-50 text-strike-800",
  };
  return (
    <div className={`rounded-lg p-3 ${colors[tone]}`}>
      <div className="text-xs font-semibold opacity-80">{label}</div>
      <div className="mt-1 text-xl font-bold tabular-nums">{percent(value)}</div>
    </div>
  );
}

function ProbabilityStack({ probabilities }: { probabilities: ProbabilityTriple }) {
  return (
    <div className="mt-4 h-3 overflow-hidden rounded-full bg-ink-100">
      <div className="flex h-full">
        <div className="bg-brand-500" style={{ width: percent(probabilities.home) }} />
        <div className="bg-ink-400" style={{ width: percent(probabilities.draw) }} />
        <div className="bg-strike-500" style={{ width: percent(probabilities.away) }} />
      </div>
    </div>
  );
}

function StatusOverview({ readiness, oddsSourceHealth }: { readiness: ModelReadiness; oddsSourceHealth: OddsSourceHealth }) {
  const cards = [
    {
      title: "模型验证",
      label: readiness.label,
      detail: readiness.summary,
      tone: readiness.productionApproved ? "bg-emerald-50 text-emerald-900 border-emerald-200" : "bg-amber-50 text-amber-900 border-amber-200",
    },
    {
      title: "赔率源",
      label: oddsSourceHealth.label,
      detail: oddsSourceHealth.summary,
      tone: oddsSourceHealth.status === "healthy" ? "bg-emerald-50 text-emerald-900 border-emerald-200" : "bg-sky-50 text-sky-900 border-sky-200",
    },
  ] as const;
  return (
    <div className="mt-4 grid gap-2">
      {cards.map((card) => (
        <div key={card.title} className={`rounded-lg border px-3 py-2 ${card.tone}`}>
          <div className="text-[11px] font-semibold opacity-80">{card.title}</div>
          <div className="mt-1 text-sm font-bold">{card.label}</div>
          <div className="mt-1 text-xs leading-5 opacity-90">{card.detail}</div>
        </div>
      ))}
    </div>
  );
}

function MarketBaselineCard({ analysis }: { analysis: MobileAnalysis }) {
  const rows = [
    ["主胜", analysis.marketBaseline.homeOdds, analysis.marketBaseline.raw.home, analysis.marketBaseline.devig.home],
    ["平局", analysis.marketBaseline.drawOdds, analysis.marketBaseline.raw.draw, analysis.marketBaseline.devig.draw],
    ["客胜", analysis.marketBaseline.awayOdds, analysis.marketBaseline.raw.away, analysis.marketBaseline.devig.away],
  ] as const;
  return (
    <Panel title="赔率如何变成概率" icon={<Gauge size={17} />}>
      <div className="space-y-2">
        {rows.map(([label, odds, raw, devig]) => (
          <div key={label} className="grid grid-cols-[44px_1fr_52px] items-center gap-2 text-sm">
            <span className="font-semibold text-ink-700">{label}</span>
            <div className="h-2 overflow-hidden rounded-full bg-ink-100">
              <div className="h-full rounded-full bg-brand-500" style={{ width: percent(devig) }} />
            </div>
            <span className="text-right font-mono text-xs text-ink-500">{odds.toFixed(2)}</span>
            <span className="col-start-2 text-[11px] text-ink-500">原始 {percent(raw)} · 去水 {percent(devig)}</span>
          </div>
        ))}
      </div>
      <div className="mt-3 rounded-lg bg-ink-50 px-3 py-2 text-xs text-ink-600">
        庄家水位约 {percent(analysis.marketBaseline.overround)}，模型会先做去水对照，再看当前赔率是否仍有价值。
      </div>
    </Panel>
  );
}

function OddsMovementCard({ movement, summary, signal, riskNote }: { movement: OddsMovementPoint[]; summary: string; signal: string; riskNote: string }) {
  return (
    <Panel title="赔率走势" icon={<LineChart size={17} />}>
      <div className="rounded-lg bg-brand-50 px-3 py-2 text-sm font-semibold text-brand-900">{signal}</div>
      <p className="mt-3 text-sm leading-6 text-ink-700">{summary}</p>
      <div className="mt-3 space-y-2">
        {movement.map((point) => (
          <div key={`${point.label}-${point.current}`} className="rounded-lg border border-ink-200 bg-white p-3">
            <div className="flex items-center justify-between gap-2">
              <span className="font-semibold">{point.label}</span>
              <span className="rounded-md bg-ink-100 px-2 py-1 text-xs font-semibold text-ink-700">{point.change}</span>
            </div>
            <div className="mt-2 flex items-center gap-2 text-sm text-ink-600">
              <span>{point.opening}</span>
              <ChevronRight size={15} />
              <span className="font-semibold text-ink-900">{point.current}</span>
            </div>
            <p className="mt-2 text-xs leading-5 text-ink-500">{point.note}</p>
          </div>
        ))}
      </div>
      <p className="mt-3 text-xs leading-5 text-ink-500">{riskNote}</p>
    </Panel>
  );
}

function AsianCard({ asian }: { asian: AsianHandicapAnalysis }) {
  const parts = [
    ["全赢", asian.fullWin, "bg-success-500"],
    ["半赢", asian.halfWin, "bg-brand-500"],
    ["走水", asian.push, "bg-ink-400"],
    ["半输", asian.halfLoss, "bg-warning-500"],
    ["全输", asian.fullLoss, "bg-danger-500"],
  ] as const;
  return (
    <Panel title="亚盘结算分布" icon={<ShieldCheck size={17} />}>
      <div className="flex items-center justify-between rounded-lg bg-ink-900 px-3 py-3 text-white">
        <div>
          <div className="text-xs text-ink-300">当前方向</div>
          <div className="mt-1 font-bold">{asian.sideLabel} {asian.lineLabel}</div>
        </div>
        <div className="text-right">
          <div className="text-xs text-ink-300">赔率</div>
          <div className="mt-1 font-mono text-lg font-bold">{asian.odds.toFixed(2)}</div>
        </div>
      </div>
      <div className="mt-3 h-4 overflow-hidden rounded-full bg-ink-100">
        <div className="flex h-full">
          {parts.map(([label, value, color]) => (
            <div key={label} title={label} className={color} style={{ width: percent(value) }} />
          ))}
        </div>
      </div>
      <div className="mt-3 grid grid-cols-5 gap-1 text-center text-[11px]">
        {parts.map(([label, value]) => (
          <div key={label} className="rounded-md bg-ink-50 py-2">
            <div className="font-semibold text-ink-700">{label}</div>
            <div className="mt-1 font-mono text-ink-500">{percent(value)}</div>
          </div>
        ))}
      </div>
      <p className="mt-3 text-xs leading-5 text-ink-500">{asian.priceNote}</p>
    </Panel>
  );
}

function TotalsCard({ totals, expectedGoals }: { totals: TotalsAnalysis; expectedGoals: { home: number; away: number } }) {
  const total = expectedGoals.home + expectedGoals.away;
  return (
    <Panel title="大小球" icon={<Waves size={17} />}>
      <div className="grid grid-cols-2 gap-2">
        <div className="rounded-lg bg-brand-50 p-3">
          <div className="text-xs font-semibold text-brand-700">大 {totals.lineLabel}</div>
          <div className="mt-1 text-xl font-bold text-brand-900">{percent(totals.overProbability)}</div>
          <div className="mt-1 text-xs text-brand-700">@ {totals.overOdds.toFixed(2)}</div>
        </div>
        <div className="rounded-lg bg-strike-50 p-3">
          <div className="text-xs font-semibold text-strike-700">小 {totals.lineLabel}</div>
          <div className="mt-1 text-xl font-bold text-strike-900">{percent(totals.underProbability)}</div>
          <div className="mt-1 text-xs text-strike-700">@ {totals.underOdds.toFixed(2)}</div>
        </div>
      </div>
      <div className="mt-3 rounded-lg bg-ink-50 px-3 py-2 text-sm text-ink-700">
        预期总进球 <span className="font-mono font-bold">{total.toFixed(2)}</span> · 盘口线 {totals.line.toFixed(1)}
      </div>
      <p className="mt-3 text-xs leading-5 text-ink-500">{totals.note}</p>
    </Panel>
  );
}

function AdjustmentCard({ adjustments }: { adjustments: ProbabilityAdjustment[] }) {
  return (
    <Panel title="胜率计算流程" icon={<Activity size={17} />}>
      <div className="space-y-2">
        {adjustments.map((item, index) => (
          <div key={`${item.title}-${index}`} className="flex gap-3 rounded-lg bg-ink-50 p-3">
            <div className={`grid h-7 w-7 shrink-0 place-items-center rounded-md text-xs font-bold ${item.used ? "bg-brand-600 text-white" : "bg-ink-200 text-ink-500"}`}>
              {index + 1}
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center justify-between gap-2">
                <h3 className="text-sm font-bold">{item.title}</h3>
                <span className="font-mono text-xs text-ink-500">{signedPercent(item.value)}</span>
              </div>
              <p className="mt-1 text-xs leading-5 text-ink-500">{item.note}</p>
            </div>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function ScoreGrid({ cells }: { cells: ScoreCell[] }) {
  return (
    <Panel title="常见比分" icon={<BarChart3 size={17} />}>
      <div className="grid grid-cols-3 gap-2">
        {cells.map((cell) => (
          <div key={`${cell.homeLabel}-${cell.awayLabel}`} className="rounded-lg bg-ink-50 p-3 text-center">
            <div className="text-lg font-bold">{cell.homeLabel}-{cell.awayLabel}</div>
            <div className="mt-1 font-mono text-xs text-ink-500">{percent(cell.probability)}</div>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function DataSourceCard({ sources, risks }: { sources: DataSourceEvidence[]; risks: { title: string; detail: string }[] }) {
  return (
    <Panel title="数据证据" icon={<ShieldCheck size={17} />}>
      <div className="space-y-2">
        {sources.map((source) => (
          <div key={`${source.name}-${source.provider}`} className="rounded-lg border border-ink-200 bg-white p-3">
            <div className="flex items-center justify-between gap-2">
              <span className="font-semibold">{source.name}</span>
              <span className="rounded-md bg-ink-100 px-2 py-1 text-[11px] font-semibold text-ink-600">{source.usage}</span>
            </div>
            <div className="mt-1 text-xs text-ink-500">{source.provider} · {source.freshness} · {source.confidence}</div>
            <p className="mt-2 text-xs leading-5 text-ink-500">{source.note}</p>
          </div>
        ))}
      </div>
      {risks.length > 0 && (
        <div className="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-800">
          <span className="font-bold">{risks[0].title}</span>：{risks[0].detail}
        </div>
      )}
    </Panel>
  );
}

function Panel({ title, icon, children }: { title: string; icon: ReactNode; children: ReactNode }) {
  return (
    <section className="rounded-lg border border-ink-200 bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-center gap-2 text-sm font-bold text-ink-900">
        <span className="grid h-8 w-8 place-items-center rounded-lg bg-ink-100 text-ink-700">{icon}</span>
        <span>{title}</span>
      </div>
      {children}
    </section>
  );
}

function percent(value: number): string {
  if (!Number.isFinite(value)) return "0.0%";
  return `${(value * 100).toFixed(1)}%`;
}

function signedPercent(value: number): string {
  if (!Number.isFinite(value)) return "0.0%";
  const sign = value > 0 ? "+" : "";
  return `${sign}${(value * 100).toFixed(1)}%`;
}
