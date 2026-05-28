import { useMemo } from "react";
import { Icon } from "../components/shared/Icon";
import { Badge, toneVariant } from "../components/shared/Badge";
import { LoadingSpinner } from "../components/shared/LoadingSpinner";
import { TeamMatchup } from "../components/shared/TeamLogo";
import { Panel, Metric } from "../components/shared/Panel";
import { OddsChart } from "../components/detail/OddsChart";
import {
  buildMatchDetailView,
  formatOdds,
  formatPercent,
  formatSignedPercent,
  statusFlagLabel,
} from "../dashboardModel";
import { formatBeijingShort } from "../formatTime";
import type { DashboardMatchDetail } from "../types";

type LineupPlayer = { number?: number | string | null; name?: string; position?: string };
type LineupSide = { formation?: string; starterCountText?: string; players?: LineupPlayer[] };

const localTime = formatBeijingShort;

export function MatchDetailPage({
  detail,
  loading,
  error,
  onBack,
}: {
  ledgerId: string;
  detail: DashboardMatchDetail | null;
  loading: boolean;
  error: string | null;
  onBack: () => void;
}) {
  const view = useMemo(() => (detail ? buildMatchDetailView(detail) : null), [detail]);

  return (
    <div className="max-w-screen-lg mx-auto px-4 py-4 pb-20 lg:pb-4">
      <button
        type="button"
        onClick={onBack}
        className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white mb-4 transition-colors"
      >
        <Icon name="back" size={16} />
        返回总览
      </button>

      {loading && <LoadingSpinner label="读取比赛详情..." />}
      {error && (
        <div className="rounded-xl border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-900/20 p-4 text-sm text-red-700 dark:text-red-300">
          {error}
        </div>
      )}

      {detail && view && (
        <div className="flex flex-col gap-4">
          {/* Hero: match info + result */}
          <div className="rounded-xl border border-ink-200 dark:border-ink-700 bg-gradient-to-br from-white to-ink-50 dark:from-ink-800 dark:to-ink-900 shadow-sm p-4 sm:p-5">
            <div className="text-2xs text-ink-500 dark:text-ink-400 uppercase tracking-wider mb-1">{detail.record.league}</div>
            <div className="flex items-center gap-4 flex-wrap">
              <TeamMatchup
                home={detail.record.home_team ?? ""}
                away={detail.record.away_team ?? ""}
                homeLogo={detail.record.home_team_logo_url}
                awayLogo={detail.record.away_team_logo_url}
                size="md"
              />
              <div className="ml-auto text-right">
                <div className="text-display-xs text-ink-900 dark:text-white tabular-nums">
                  {view.scoreStatusText || "vs"}
                </div>
                <div className="text-xs text-ink-500 dark:text-ink-400 mt-1">{localTime(detail.record.kickoff_utc_plus_8)}</div>
                {detail.record.settlement_status === "settled" && (
                  <div className="mt-2">
                    <Badge variant={detail.record.hit === 1 ? "success" : "error"}>
                      {detail.record.hit === 1 ? "命中" : "未命中"} · {detail.record.profit_units != null ? (detail.record.profit_units > 0 ? "+" : "") + detail.record.profit_units.toFixed(2) : "—"}
                    </Badge>
                  </div>
                )}
              </div>
            </div>
            <div className="mt-4 pt-4 border-t border-ink-100 dark:border-ink-700/50 grid grid-cols-2 sm:grid-cols-4 gap-3">
              <Metric label="盘口" value={detail.record.selection || "—"} />
              <Metric label="赔率" value={detail.record.decimal_odds != null ? formatOdds(detail.record.decimal_odds) : "—"} />
              <Metric label="价值边际" value={detail.record.edge != null ? formatSignedPercent(detail.record.edge) : "—"} />
              <Metric label="建议" value={view.actionText || detail.record.recommendation || "—"} />
            </div>
          </div>

          <Panel title="概率分析" icon="gauge">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
              <Metric label="模型概率" value={detail.record.model_probability != null ? formatPercent(detail.record.model_probability) : "—"} />
              <Metric label="校准概率" value={detail.record.learned_probability != null ? formatPercent(detail.record.learned_probability) : "—"} />
              <Metric label="市场概率" value={detail.record.market_probability != null ? formatPercent(detail.record.market_probability) : "—"} />
              <Metric label="预期回报" value={detail.record.expected_multiplier != null ? `×${Number(detail.record.expected_multiplier).toFixed(3)}` : "—"} />
            </div>
            {view.probabilityRows?.length > 0 && (
              <div className="space-y-1 pt-3 border-t border-ink-100 dark:border-ink-700/50">
                {view.probabilityRows.map((row, i) => (
                  <div key={i} className="flex items-center justify-between text-xs">
                    <span className="text-ink-600 dark:text-ink-400">{row.label}</span>
                    <span className="font-medium tabular-nums text-ink-900 dark:text-white">{row.value}</span>
                  </div>
                ))}
              </div>
            )}
          </Panel>

          {view.predictionDiagnostic && (view.predictionDiagnostic.summary || view.predictionDiagnostic.reasonText) && (
            <Panel title={view.predictionDiagnostic.title || "预测诊断"} icon="brain">
              <div className="flex items-center gap-2 mb-2">
                <Badge variant={toneVariant(view.predictionDiagnostic.tone)}>{view.predictionDiagnostic.statusText}</Badge>
                <span className="text-xs text-ink-500 dark:text-ink-400">{view.predictionDiagnostic.passText}</span>
              </div>
              {view.predictionDiagnostic.summary && (
                <div className="text-xs text-ink-700 dark:text-ink-300 mb-3">{view.predictionDiagnostic.summary}</div>
              )}
              {view.predictionDiagnostic.reasonText && (
                <div className="text-xs text-ink-600 dark:text-ink-400 mb-3">{view.predictionDiagnostic.reasonText}</div>
              )}
              {view.predictionDiagnostic.gapRows?.length > 0 && (
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 pt-2 border-t border-ink-100 dark:border-ink-700/50">
                  {view.predictionDiagnostic.gapRows.map((row, i) => (
                    <div key={i}>
                      <div className="text-2xs text-ink-500 dark:text-ink-400">{row.label}</div>
                      <div className="text-xs font-medium tabular-nums text-ink-900 dark:text-white">{row.value}</div>
                    </div>
                  ))}
                </div>
              )}
              {view.predictionDiagnostic.explanationRows?.length > 0 && (
                <div className="space-y-1.5 mt-3 pt-3 border-t border-ink-100 dark:border-ink-700/50">
                  {view.predictionDiagnostic.explanationRows.map((row, i) => (
                    <div key={i} className="text-xs">
                      <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-2xs mr-2 ${
                        row.tone === "good" ? "bg-success-500/10 text-success-700 dark:text-success-500" :
                        row.tone === "bad" ? "bg-danger-500/10 text-danger-700 dark:text-danger-500" :
                        row.tone === "caution" ? "bg-warning-500/10 text-warning-700 dark:text-warning-500" :
                        "bg-ink-100 dark:bg-ink-800 text-ink-600 dark:text-ink-400"
                      }`}>{row.label}</span>
                      <span className="text-ink-700 dark:text-ink-300">{row.value}</span>
                      {row.detail && <div className="text-2xs text-ink-500 dark:text-ink-400 ml-1 mt-0.5">{row.detail}</div>}
                    </div>
                  ))}
                </div>
              )}
            </Panel>
          )}

          {view.contextRows?.length > 0 && (
            <Panel title="比赛情报" icon="location">
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-3">
                {view.contextRows.map((row, i) => (
                  <div key={i}>
                    <div className="text-2xs text-ink-500 dark:text-ink-400 flex items-center gap-1">
                      {row.label}
                      {!row.available && <span className="text-ink-400 dark:text-ink-600">·{row.statusText}</span>}
                    </div>
                    <div className={`text-xs font-medium mt-0.5 ${row.available ? "text-ink-900 dark:text-white" : "text-ink-400 dark:text-ink-500"}`}>
                      {row.value || "—"}
                    </div>
                    {row.sourceText && <div className="text-2xs text-ink-400 dark:text-ink-500">{row.sourceText}</div>}
                  </div>
                ))}
              </div>
              {view.contextSourceText && (
                <div className="text-2xs text-ink-500 dark:text-ink-400 pt-2 border-t border-ink-100 dark:border-ink-700/50">
                  {view.contextSourceText}
                </div>
              )}
            </Panel>
          )}

          {view.lineup?.available && (
            <Panel title="首发阵容" icon="team">
              <div className="text-xs text-ink-500 dark:text-ink-400 mb-3">
                {view.lineup.basis} · {view.lineup.statusText}
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {(["home", "away"] as const).map((side) => {
                  const lineup = view.lineup as unknown as { home: LineupSide; away: LineupSide };
                  const team = lineup[side];
                  const teamName = side === "home" ? detail.record.home_team : detail.record.away_team;
                  return (
                    <div key={side}>
                      <div className="flex items-center gap-2 mb-2">
                        <strong className="text-sm text-ink-900 dark:text-white">{teamName}</strong>
                        <Badge variant="neutral">{team.formation || "—"}</Badge>
                        <span className="text-2xs text-ink-500 dark:text-ink-400">{team.starterCountText}</span>
                      </div>
                      <div className="space-y-1">
                        {(team.players ?? []).slice(0, 11).map((p, i) => (
                          <div key={i} className="flex items-center gap-2 text-xs">
                            <span className="w-6 text-right text-ink-400 dark:text-ink-500 tabular-nums">{p.number ?? "—"}</span>
                            <span className="text-ink-700 dark:text-ink-300 truncate flex-1">{p.name || "—"}</span>
                            {p.position && <span className="text-2xs text-ink-500 dark:text-ink-400">{p.position}</span>}
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
              {view.lineup.warnings?.length > 0 && (
                <div className="mt-3 pt-3 border-t border-ink-100 dark:border-ink-700/50 space-y-1">
                  {view.lineup.warnings.map((w, i) => (
                    <div key={i} className="text-2xs text-warning-700 dark:text-warning-500 flex items-center gap-1">
                      <Icon name="warn" size={10} />{w}
                    </div>
                  ))}
                </div>
              )}
            </Panel>
          )}

          {view.candidateRows?.length > 0 && (
            <Panel title="候选盘口对比" icon="chart">
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead className="text-2xs text-ink-500 dark:text-ink-400 border-b border-ink-100 dark:border-ink-700/50">
                    <tr>
                      <th className="text-left py-2 px-2 font-medium">选项</th>
                      <th className="text-left py-2 px-2 font-medium">来源</th>
                      <th className="text-right py-2 px-2 font-medium">概率</th>
                      <th className="text-right py-2 px-2 font-medium">赔率</th>
                      <th className="text-right py-2 px-2 font-medium">边际</th>
                      <th className="text-left py-2 px-2 font-medium">移动</th>
                    </tr>
                  </thead>
                  <tbody>
                    {view.candidateRows.map((row, i) => (
                      <tr key={i} className="border-b border-ink-50 dark:border-ink-700/30">
                        <td className="py-1.5 px-2 text-ink-700 dark:text-ink-300">{row.selectionText}</td>
                        <td className="py-1.5 px-2 text-2xs text-ink-500 dark:text-ink-400">{row.providerText}</td>
                        <td className="py-1.5 px-2 text-right tabular-nums">{row.probabilityText}</td>
                        <td className="py-1.5 px-2 text-right tabular-nums font-medium text-ink-900 dark:text-white">{row.oddsText}</td>
                        <td className="py-1.5 px-2 text-right tabular-nums font-medium text-ink-700 dark:text-ink-300">
                          {row.edgeText}
                        </td>
                        <td className="py-1.5 px-2 text-2xs">
                          {row.movementText ? (
                            <Badge variant={toneVariant(row.movementTone ?? "neutral")}>{row.movementText}</Badge>
                          ) : <span className="text-ink-400 dark:text-ink-500">—</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Panel>
          )}

          {view.oddsTrend && view.oddsTrend.points.length > 0 && (
            <OddsChart
              title={view.oddsTrend.title || "赔率走势"}
              points={view.oddsTrend.points.map((p) => {
                const point = p as Record<string, unknown> & { label?: string; x?: string | number };
                const label = typeof point.label === "string" ? point.label : String(point.x ?? "");
                return { ...point, label };
              })}
              lines={(view.oddsTrend.series ?? []).map((s) => {
                const series = s as { key?: string; id?: string };
                return series.key ?? series.id ?? "";
              }).filter(Boolean)}
            />
          )}

          {view.clvTracking?.detail && (
            <Panel title={view.clvTracking.title || "CLV 收盘价"} icon="trendUp">
              <div className="grid grid-cols-3 gap-3">
                <Metric label="预测赔率" value={view.clvTracking.priceText} />
                <Metric label="CLV" value={view.clvTracking.clvText} />
                <Metric label="收盘时间" value={view.clvTracking.timeText} />
              </div>
              <div className="text-2xs text-ink-500 dark:text-ink-400 mt-2 pt-2 border-t border-ink-100 dark:border-ink-700/50">
                {view.clvTracking.detail}
              </div>
            </Panel>
          )}

          {view.marketMovement?.rows?.length > 0 && (
            <Panel title={view.marketMovement.title || "盘口移动"} icon="trendUp">
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead className="text-2xs text-ink-500 dark:text-ink-400 border-b border-ink-100 dark:border-ink-700/50">
                    <tr>
                      <th className="text-left py-2 px-2 font-medium">市场</th>
                      <th className="text-left py-2 px-2 font-medium">选项</th>
                      <th className="text-left py-2 px-2 font-medium">方向</th>
                      <th className="text-right py-2 px-2 font-medium">价格</th>
                    </tr>
                  </thead>
                  <tbody>
                    {view.marketMovement.rows.slice(0, 12).map((row) => (
                      <tr key={row.key} className="border-b border-ink-50 dark:border-ink-700/30">
                        <td className="py-1.5 px-2 text-ink-700 dark:text-ink-300">{row.marketText}</td>
                        <td className="py-1.5 px-2 text-ink-700 dark:text-ink-300">{row.selectionText}</td>
                        <td className="py-1.5 px-2">
                          <Badge variant={toneVariant(row.tone)}>{row.directionText}</Badge>
                        </td>
                        <td className="py-1.5 px-2 text-right tabular-nums text-ink-900 dark:text-white">{row.priceText}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Panel>
          )}

          {view.oddsGroups?.length > 0 && (
            <Panel title="多公司赔率快照" icon="database" badge={`${view.oddsGroups.length} 家`}>
              <div className="space-y-3">
                {view.oddsGroups.map((group) => (
                  <div key={group.id} className="border border-ink-100 dark:border-ink-700/50 rounded-lg overflow-hidden">
                    <div className="flex items-center justify-between bg-ink-50 dark:bg-ink-800/60 px-3 py-2 text-xs">
                      <span className="font-semibold text-ink-800 dark:text-ink-200">{group.bookmaker}</span>
                      <span className="text-2xs text-ink-500 dark:text-ink-400">
                        {group.rowCountText} · {group.marketTypesText} · {group.latestFetchedAtUtc ? localTime(group.latestFetchedAtUtc) : "—"}
                      </span>
                    </div>
                    <div className="p-3 overflow-x-auto">
                      <table className="w-full text-xs">
                        <tbody>
                          {group.rows.slice(0, 6).map((odd, i) => (
                            <tr key={i} className="border-b border-ink-50 dark:border-ink-700/30 last:border-0">
                              <td className="py-1.5 pr-2 text-2xs text-ink-500 dark:text-ink-400">{odd.marketTypeLabel}</td>
                              <td className="py-1.5 px-2 text-ink-700 dark:text-ink-300">{odd.selectionText}</td>
                              <td className="py-1.5 px-2 text-2xs text-ink-500 dark:text-ink-400">{odd.lineText}</td>
                              <td className="py-1.5 pl-2 text-right tabular-nums font-medium text-ink-900 dark:text-white">{odd.oddsText}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                ))}
              </div>
            </Panel>
          )}

          {view.sourceAttemptRows?.length > 0 && (
            <Panel title="数据源采集" icon="data">
              <div className="space-y-1.5">
                {view.sourceAttemptRows.map((row, i) => (
                  <div key={i} className="flex items-start gap-2 text-xs">
                    <Badge variant={toneVariant(row.tone)} className="flex-shrink-0">{row.statusText}</Badge>
                    <div className="flex-1 min-w-0">
                      <div className="text-ink-700 dark:text-ink-300">
                        <strong>{row.providerText}</strong>
                        {row.matchIdText && <span className="text-2xs text-ink-500 dark:text-ink-400 ml-2">{row.matchIdText}</span>}
                      </div>
                      {row.fieldSummary && <div className="text-2xs text-ink-500 dark:text-ink-400">{row.fieldSummary}</div>}
                      {row.detail && <div className="text-2xs text-ink-500 dark:text-ink-400">{row.detail}</div>}
                    </div>
                  </div>
                ))}
              </div>
            </Panel>
          )}

          {(view.riskFlags?.length > 0 || view.dataFlags?.length > 0) && (
            <Panel title="风险与提示" icon="warn">
              {view.riskFlags?.length > 0 && (
                <div className="mb-3">
                  <div className="text-2xs text-ink-500 dark:text-ink-400 mb-1.5">风险标记</div>
                  <div className="flex flex-wrap gap-1.5">
                    {view.riskFlags.map((flag, i) => (
                      <Badge key={i} variant="error">{statusFlagLabel(flag)}</Badge>
                    ))}
                  </div>
                </div>
              )}
              {view.dataFlags?.length > 0 && (
                <div>
                  <div className="text-2xs text-ink-500 dark:text-ink-400 mb-1.5">提示标记</div>
                  <div className="flex flex-wrap gap-1.5">
                    {view.dataFlags.map((flag, i) => (
                      <Badge key={i} variant="warning">{statusFlagLabel(flag)}</Badge>
                    ))}
                  </div>
                </div>
              )}
            </Panel>
          )}

          {view.timeline?.length > 0 && (
            <Panel title="决策时间线" icon="clock">
              <div className="space-y-2">
                {view.timeline.map((event, i) => (
                  <div key={i} className="flex items-start gap-3 text-xs">
                    <div className="w-2 h-2 rounded-full bg-brand-500 mt-1 flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <strong className="text-ink-800 dark:text-ink-200">{event.title || "事件"}</strong>
                        <span className="text-2xs text-ink-500 dark:text-ink-400 tabular-nums">{localTime(event.at_utc)}</span>
                      </div>
                      {event.detail && (
                        <div className="text-2xs text-ink-600 dark:text-ink-400 mt-0.5">{event.detail}</div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </Panel>
          )}
        </div>
      )}
    </div>
  );
}

export default MatchDetailPage;
