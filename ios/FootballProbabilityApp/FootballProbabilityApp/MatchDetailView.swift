import SwiftUI

struct MatchDetailView: View {
    let analysis: MatchAnalysis
    @State private var perspective: AnalysisPerspective = .oneXTwo

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                MatchHeaderCard(analysis: analysis)

                Picker("分析类型", selection: $perspective) {
                    ForEach(AnalysisPerspective.allCases) { mode in
                        Text(mode.rawValue).tag(mode)
                    }
                }
                .pickerStyle(.segmented)

                switch perspective {
                case .oneXTwo:
                    OneXTwoFlowView(analysis: analysis)
                case .asian:
                    AsianFlowView(analysis: analysis)
                case .totals:
                    TotalsFlowView(analysis: analysis)
                }
            }
            .padding()
        }
        .background(Color(.systemGroupedBackground))
        .navigationTitle("比赛分析")
        .navigationBarTitleDisplayMode(.inline)
    }
}

struct MatchHeaderCard: View {
    let analysis: MatchAnalysis

    var body: some View {
        Card {
            VStack(alignment: .leading, spacing: 8) {
                HStack(alignment: .top) {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("\(analysis.homeTeam.name) vs \(analysis.awayTeam.name)")
                            .font(.title3.weight(.bold))
                        Text("\(analysis.kickoffText) · \(analysis.league) · \(analysis.venue)")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                    Spacer()
                    StatusChip(text: "数据已更新", color: .green)
                }

                Divider()

                Text("最终胜平负概率（模型估算）")
                    .font(.subheadline.weight(.semibold))
                ProbabilityPills(probabilities: analysis.finalProbabilities)

                HStack(spacing: 8) {
                    StatusChip(text: "可信度：\(analysis.confidence.rawValue)", color: .blue)
                    StatusChip(text: "数据质量：\(analysis.dataQuality)", color: .green)
                }

                Text("小提示：概率不是保证结果，而是根据当前数据算出的可能性。")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
    }
}

struct OneXTwoFlowView: View {
    let analysis: MatchAnalysis

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            DataSourcesPanel(sources: analysis.dataSources)
            MarketBaselinePanel(market: analysis.marketBaseline)
            OddsMovementPanel(movement: analysis.oddsMovement, index: 3)
            ExpectedGoalsPanel(expectedGoals: analysis.expectedGoals, home: analysis.homeTeam.shortName, away: analysis.awayTeam.shortName, index: 4)
            ScoreMatrixHeatmap(
                cells: analysis.scoreMatrix,
                highlight: .oneXTwo,
                title: "比分概率图",
                explanation: "绿色偏主队赢，蓝色是平局，橙色偏客队赢。"
            )
            AdjustmentsPanel(adjustments: analysis.adjustments, finalHome: analysis.finalProbabilities.home)
            CalibrationPanel(calibration: analysis.calibration)
            RiskList(risks: analysis.risks)
        }
    }
}

struct AsianFlowView: View {
    let analysis: MatchAnalysis

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            AsianMeaningPanel(asian: analysis.asian)
            OddsMovementPanel(movement: analysis.oddsMovement, index: 2)
            AsianOutcomePanel(asian: analysis.asian)
            ScoreMatrixHeatmap(
                cells: analysis.scoreMatrix,
                highlight: .asian(line: analysis.asian.line),
                title: "亚盘比分图",
                explanation: "绿色表示主队方向赢盘，红色表示主队方向输盘，蓝色表示走水。"
            )
            AsianPricePanel(asian: analysis.asian)
            DataSourcesPanel(sources: analysis.dataSources.filter { $0.name == "赔率/盘口" || $0.name == "伤停" || $0.name == "新闻" })
            RiskList(risks: analysis.risks)
        }
    }
}

struct TotalsFlowView: View {
    let analysis: MatchAnalysis

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            TotalsSummaryPanel(totals: analysis.totals)
            ExpectedGoalsPanel(expectedGoals: analysis.expectedGoals, home: analysis.homeTeam.shortName, away: analysis.awayTeam.shortName, index: 2)
            ScoreMatrixHeatmap(
                cells: analysis.scoreMatrix,
                highlight: .totals(line: analysis.totals.line),
                title: "大小球比分图",
                explanation: "青色表示大球区域，灰色表示小球区域。"
            )
            Card {
                SectionTitle("小白解释", index: 4, subtitle: "大小球看的是总进球，不是看谁赢。")
                Text(analysis.totals.note)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            CalibrationPanel(calibration: analysis.calibration)
        }
    }
}

struct DataSourcesPanel: View {
    let sources: [DataSourceEvidence]

    var body: some View {
        Card {
            SectionTitle("数据准备", index: 1, subtitle: "先看哪些数据真的参与了计算。")
            ForEach(sources) { source in
                SourceRow(source: source)
                if source.id != sources.last?.id {
                    Divider()
                }
            }
        }
    }
}

struct MarketBaselinePanel: View {
    let market: MarketBaseline

    var body: some View {
        Card {
            SectionTitle("赔率换算成基础概率", index: 2, subtitle: "去掉庄家利润后的参考概率。")
            HStack(spacing: 8) {
                OddsChip(title: "主胜", odds: market.homeOdds)
                OddsChip(title: "平局", odds: market.drawOdds)
                OddsChip(title: "客胜", odds: market.awayOdds)
            }
            ProbabilityBar(label: "主胜基础概率", value: market.devig.home, color: .green)
            ProbabilityBar(label: "平局基础概率", value: market.devig.draw, color: .blue)
            ProbabilityBar(label: "客胜基础概率", value: market.devig.away, color: .orange)
            StatusChip(text: "庄家利润约 \(market.overround.percentString())", color: .gray)
        }
    }
}

struct OddsChip: View {
    let title: String
    let odds: Double

    var body: some View {
        VStack(spacing: 3) {
            Text(title)
                .font(.caption)
                .foregroundStyle(.secondary)
            Text(odds.decimalString())
                .font(.subheadline.monospacedDigit().weight(.semibold))
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 8)
        .background(Color(.tertiarySystemFill))
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
    }
}

struct ExpectedGoalsPanel: View {
    let expectedGoals: ExpectedGoals
    let home: String
    let away: String
    let index: Int

    var body: some View {
        Card {
            SectionTitle("预期进球", index: index, subtitle: "用来生成所有可能比分。")
            ProbabilityBar(label: "\(home) 预期进球 \(expectedGoals.home.decimalString()) 球", value: expectedGoals.home / 3.5, color: .green)
            ProbabilityBar(label: "\(away) 预期进球 \(expectedGoals.away.decimalString()) 球", value: expectedGoals.away / 3.5, color: .orange)
            HStack {
                Text("合计预期进球")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Spacer()
                Text("\(expectedGoals.total.decimalString()) 球")
                    .font(.caption.monospacedDigit().weight(.semibold))
            }
        }
    }
}

struct OddsMovementPanel: View {
    let movement: OddsMovementAnalysis
    let index: Int

    var body: some View {
        Card {
            SectionTitle("赔率变化", index: index, subtitle: "赔率不是只看当前，还要看从早盘到现在怎么变。")
            HStack(spacing: 8) {
                StatusChip(text: movement.openingTime, color: .gray)
                StatusChip(text: movement.currentTime, color: .blue)
            }
            Text(movement.summary)
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
            HStack {
                Image(systemName: "waveform.path.ecg")
                    .foregroundStyle(.orange)
                VStack(alignment: .leading, spacing: 2) {
                    Text(movement.marketSignal)
                        .font(.subheadline.weight(.semibold))
                    Text("小白理解：同一个方向越热，赔率/水位通常越不划算。")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
            .padding(.vertical, 4)
            ForEach(movement.points) { point in
                OddsMovementRow(point: point)
                if point.id != movement.points.last?.id {
                    Divider()
                }
            }
            Text(movement.riskNote)
                .font(.caption)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
        }
    }
}

struct OddsMovementRow: View {
    let point: OddsMovementPoint

    var body: some View {
        VStack(alignment: .leading, spacing: 7) {
            HStack(alignment: .firstTextBaseline) {
                Text(point.label)
                    .font(.subheadline.weight(.semibold))
                Spacer()
                StatusChip(text: point.change, color: color)
            }
            HStack(spacing: 8) {
                MovementValueBox(title: "早盘", value: point.opening)
                Image(systemName: "arrow.right")
                    .font(.caption.weight(.bold))
                    .foregroundStyle(.secondary)
                MovementValueBox(title: "当前", value: point.current)
            }
            Text(point.note)
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .padding(.vertical, 4)
    }

    private var color: Color {
        switch point.direction {
        case .supportsHome:
            return .green
        case .supportsAway:
            return .orange
        case .priceWorse:
            return .red
        case .neutral:
            return .gray
        }
    }
}

struct MovementValueBox: View {
    let title: String
    let value: String

    var body: some View {
        VStack(spacing: 3) {
            Text(title)
                .font(.caption)
                .foregroundStyle(.secondary)
            Text(value)
                .font(.caption.monospacedDigit().weight(.semibold))
                .lineLimit(1)
                .minimumScaleFactor(0.78)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 8)
        .background(Color(.tertiarySystemFill))
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
    }
}

struct AdjustmentsPanel: View {
    let adjustments: [ProbabilityAdjustment]
    let finalHome: Double

    var body: some View {
        Card {
            SectionTitle("影响因素修正", index: 5, subtitle: "只让已验证或可信的信号改变概率。")
            ForEach(adjustments) { adjustment in
                HStack(alignment: .firstTextBaseline) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text(adjustment.title)
                            .font(.subheadline.weight(.semibold))
                        Text(adjustment.note)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                    Spacer()
                    Text(valueText(for: adjustment))
                        .font(.subheadline.monospacedDigit().weight(.semibold))
                        .foregroundStyle(valueColor(for: adjustment))
                }
                if adjustment.id != adjustments.last?.id {
                    Divider()
                }
            }
            HStack {
                Text("校准后主胜")
                    .font(.subheadline.weight(.bold))
                Spacer()
                Text(finalHome.percentString())
                    .font(.headline.monospacedDigit())
                    .foregroundStyle(.green)
            }
            .padding(.top, 2)
        }
    }

    private func valueText(for adjustment: ProbabilityAdjustment) -> String {
        if adjustment.title == "基础主胜" {
            return adjustment.value.percentString()
        }
        if !adjustment.used {
            return "未采用"
        }
        return adjustment.value.signedPercentPointString
    }

    private func valueColor(for adjustment: ProbabilityAdjustment) -> Color {
        if !adjustment.used { return .gray }
        if adjustment.value > 0 { return .green }
        if adjustment.value < 0 { return .red }
        return .secondary
    }
}

struct CalibrationPanel: View {
    let calibration: CalibrationEvidence

    var body: some View {
        Card {
            SectionTitle("历史校准", index: 6, subtitle: "检查模型过去说得准不准。")
            HStack(spacing: 8) {
                CalibrationMetric(title: "相似区间", value: calibration.rangeLabel)
                CalibrationMetric(title: "实际主胜率", value: calibration.actualRate.percentString())
                CalibrationMetric(title: "样本", value: "\(calibration.sampleCount)场")
            }
            Text(calibration.note)
                .font(.caption)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
        }
    }
}

struct CalibrationMetric: View {
    let title: String
    let value: String

    var body: some View {
        VStack(spacing: 4) {
            Text(title)
                .font(.caption)
                .foregroundStyle(.secondary)
            Text(value)
                .font(.subheadline.monospacedDigit().weight(.semibold))
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 8)
        .background(Color.teal.opacity(0.10))
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
    }
}

struct AsianMeaningPanel: View {
    let asian: AsianHandicapAnalysis

    var body: some View {
        Card {
            SectionTitle("当前亚盘怎么理解", index: 1, subtitle: "亚盘不是只看谁赢球。")
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text(asian.lineLabel)
                        .font(.title3.weight(.bold))
                    Text("\(asian.sideLabel) · 当前水位 \(asian.odds.decimalString())")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                Spacer()
                StatusChip(text: "亚盘", color: .purple)
            }
            VStack(alignment: .leading, spacing: 5) {
                Text("主队赢球：主队方向赢盘")
                Text("双方打平：主队方向输半")
                Text("主队输球：主队方向全输")
            }
            .font(.subheadline)
            .foregroundStyle(.secondary)
        }
    }
}

struct AsianOutcomePanel: View {
    let asian: AsianHandicapAnalysis

    var body: some View {
        Card {
            SectionTitle("亚盘打出概率", index: 2, subtitle: "从比分概率图按盘口规则加总。")
            ProbabilityBar(label: "全赢", value: asian.fullWin, color: .green)
            ProbabilityBar(label: "赢半", value: asian.halfWin, color: .mint)
            ProbabilityBar(label: "走水", value: asian.push, color: .blue)
            ProbabilityBar(label: "输半", value: asian.halfLoss, color: .orange)
            ProbabilityBar(label: "全输", value: asian.fullLoss, color: .red)
            Text("不亏概率：\(asian.noLossProbability.percentString())。这里的不亏包含全赢、赢半和走水。")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
    }
}

struct AsianPricePanel: View {
    let asian: AsianHandicapAnalysis

    var body: some View {
        Card {
            SectionTitle("价格参考", index: 4, subtitle: "只评价价格，不给保证结论。")
            HStack {
                Text("当前水位")
                    .font(.subheadline)
                Spacer()
                Text(asian.odds.decimalString())
                    .font(.headline.monospacedDigit())
            }
            Text(asian.priceNote)
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
        }
    }
}

struct TotalsSummaryPanel: View {
    let totals: TotalsAnalysis

    var body: some View {
        Card {
            SectionTitle("当前大小球", index: 1, subtitle: "看两队总进球是否超过盘口线。")
            HStack {
                Text("盘口：\(totals.lineLabel)")
                    .font(.title3.weight(.bold))
                Spacer()
                StatusChip(text: "大小球", color: .teal)
            }
            ProbabilityBar(label: "大球概率", value: totals.overProbability, color: .teal, caption: "当前大球水位 \(totals.overOdds.decimalString())")
            ProbabilityBar(label: "小球概率", value: totals.underProbability, color: .gray, caption: "当前小球水位 \(totals.underOdds.decimalString())")
        }
    }
}
