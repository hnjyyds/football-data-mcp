import Foundation

enum ScoreMatrixCalculator {
    static func matrix(homeXG: Double, awayXG: Double, bucketMax: Int = 4, exactMax: Int = 9) -> [ScoreCell] {
        var buckets: [String: Double] = [:]
        for homeGoals in 0...exactMax {
            for awayGoals in 0...exactMax {
                let homeBucket = min(homeGoals, bucketMax)
                let awayBucket = min(awayGoals, bucketMax)
                let key = "\(homeBucket)-\(awayBucket)"
                let probability = poisson(mean: homeXG, goals: homeGoals) * poisson(mean: awayXG, goals: awayGoals)
                buckets[key, default: 0] += probability
            }
        }

        let total = buckets.values.reduce(0, +)
        return (0...bucketMax).flatMap { homeBucket in
            (0...bucketMax).map { awayBucket in
                let key = "\(homeBucket)-\(awayBucket)"
                return ScoreCell(
                    homeBucket: homeBucket,
                    awayBucket: awayBucket,
                    homeLabel: homeBucket == bucketMax ? "\(bucketMax)+" : "\(homeBucket)",
                    awayLabel: awayBucket == bucketMax ? "\(bucketMax)+" : "\(awayBucket)",
                    probability: (buckets[key] ?? 0) / max(total, 0.0001)
                )
            }
        }
    }

    static func oneXTwo(from cells: [ScoreCell]) -> ProbabilityTriple {
        let home = cells.filter { $0.homeBucket > $0.awayBucket }.map(\.probability).reduce(0, +)
        let draw = cells.filter { $0.homeBucket == $0.awayBucket }.map(\.probability).reduce(0, +)
        let away = cells.filter { $0.homeBucket < $0.awayBucket }.map(\.probability).reduce(0, +)
        return ProbabilityTriple(home: home, draw: draw, away: away)
    }

    static func asianHandicap(from cells: [ScoreCell], line: Double, odds: Double) -> AsianHandicapAnalysis {
        var fullWin = 0.0
        var halfWin = 0.0
        var push = 0.0
        var halfLoss = 0.0
        var fullLoss = 0.0
        let splitLines = splitQuarterLine(line)

        for cell in cells {
            let margin = Double(cell.homeBucket - cell.awayBucket)
            let outcomes = splitLines.map { settlement(margin: margin, line: $0) }
            let probability = cell.probability
            let score = outcomes.reduce(0, +) / Double(outcomes.count)

            if score >= 0.99 {
                fullWin += probability
            } else if score > 0.01 {
                halfWin += probability
            } else if abs(score) < 0.01 {
                push += probability
            } else if score > -0.99 {
                halfLoss += probability
            } else {
                fullLoss += probability
            }
        }

        return AsianHandicapAnalysis(
            line: line,
            lineLabel: "主队 -0.25（让平/半）",
            sideLabel: "主队方向",
            odds: odds,
            fullWin: fullWin,
            halfWin: halfWin,
            push: push,
            halfLoss: halfLoss,
            fullLoss: fullLoss,
            priceNote: "模型认为主队方向价格偏紧，适合继续观察盘口变化。"
        )
    }

    static func totals(from cells: [ScoreCell], line: Double, overOdds: Double, underOdds: Double) -> TotalsAnalysis {
        var over = 0.0
        var under = 0.0
        for cell in cells {
            let totalGoals = Double(cell.homeBucket + cell.awayBucket)
            if totalGoals > line {
                over += cell.probability
            } else {
                under += cell.probability
            }
        }

        return TotalsAnalysis(
            line: line,
            lineLabel: "2.5球",
            overOdds: overOdds,
            underOdds: underOdds,
            overProbability: over,
            underProbability: under,
            note: "大小球同样来自比分概率图：总进球超过 2.5 算大球，否则算小球。"
        )
    }

    private static func poisson(mean: Double, goals: Int) -> Double {
        exp(-mean) * pow(mean, Double(goals)) / factorial(goals)
    }

    private static func factorial(_ value: Int) -> Double {
        guard value > 1 else { return 1 }
        return (2...value).map(Double.init).reduce(1, *)
    }

    private static func splitQuarterLine(_ line: Double) -> [Double] {
        let doubled = line * 2
        if abs(doubled.rounded() - doubled) < 0.0001 {
            return [line]
        }
        let lower = floor(doubled) / 2
        return [lower, lower + 0.5]
    }

    private static func settlement(margin: Double, line: Double) -> Double {
        let adjusted = margin + line
        if adjusted > 0.0001 { return 1 }
        if adjusted < -0.0001 { return -1 }
        return 0
    }
}

enum MockAnalysisData {
    static var sample: MatchAnalysis {
        let home = TeamSummary(name: "北城 FC", shortName: "北城")
        let away = TeamSummary(name: "海港城", shortName: "海港")
        let matrix = ScoreMatrixCalculator.matrix(homeXG: 1.52, awayXG: 1.08)
        let market = buildMarketBaseline(homeOdds: 2.10, drawOdds: 3.40, awayOdds: 3.60)
        let oddsMovement = buildOddsMovement()
        let asian = ScoreMatrixCalculator.asianHandicap(from: matrix, line: -0.25, odds: 1.92)
        let totals = ScoreMatrixCalculator.totals(from: matrix, line: 2.5, overOdds: 1.90, underOdds: 1.94)

        return MatchAnalysis(
            id: "sample-north-harbor",
            league: "英超",
            kickoffText: "今晚 20:45",
            venue: "北城球场",
            homeTeam: home,
            awayTeam: away,
            finalProbabilities: ProbabilityTriple(home: 0.456, draw: 0.271, away: 0.273),
            confidence: .medium,
            dataQuality: "良好",
            marketBaseline: market,
            oddsMovement: oddsMovement,
            expectedGoals: ExpectedGoals(home: 1.52, away: 1.08),
            scoreMatrix: matrix,
            dataSources: [
                DataSourceEvidence(name: "赛程", provider: "公开赛程源", freshness: "已确认", confidence: .high, usage: .used, note: "比赛时间、双方和赛事已确认。"),
                DataSourceEvidence(name: "赔率/盘口", provider: "历史赔率源 + 盘口源", freshness: "6分钟前", confidence: .high, usage: .used, note: "用于换算市场基础概率。"),
                DataSourceEvidence(name: "预期进球", provider: "公开 xG / 历史表现", freshness: "今日更新", confidence: .medium, usage: .used, note: "用来生成比分概率图。"),
                DataSourceEvidence(name: "伤停", provider: "新闻/RSS/名单源", freshness: "有待确认", confidence: .low, usage: .reference, note: "存在来源不一致，暂不强行改动概率。"),
                DataSourceEvidence(name: "新闻", provider: "RSSHub + 文章摘要", freshness: "14分钟前", confidence: .medium, usage: .reference, note: "已提取轮换风险，当前只作提示。")
            ],
            adjustments: [
                ProbabilityAdjustment(title: "基础主胜", value: 0.450, note: "赔率去水后的市场参考概率。", used: true),
                ProbabilityAdjustment(title: "近期表现", value: 0.018, note: "近几场创造机会质量更好。", used: true),
                ProbabilityAdjustment(title: "休息更充分", value: 0.008, note: "主队多休息一天，轻微加分。", used: true),
                ProbabilityAdjustment(title: "后卫伤停", value: -0.014, note: "主队后防有不确定性。", used: true),
                ProbabilityAdjustment(title: "盘口变化", value: -0.006, note: "当前价格比初盘更紧。", used: true),
                ProbabilityAdjustment(title: "新闻轮换", value: 0, note: "消息未确认，只展示不参与计算。", used: false)
            ],
            calibration: CalibrationEvidence(
                rangeLabel: "45%-50%",
                actualRate: 0.468,
                sampleCount: 312,
                note: "历史上模型给出类似主胜概率时，实际主胜率接近模型输出。"
            ),
            asian: asian,
            totals: totals,
            risks: [
                RiskFlag(title: "阵容未完全确认", detail: "首发名单通常赛前才更可靠。"),
                RiskFlag(title: "盘口价格偏紧", detail: "主队方向热度已反映在价格里。"),
                RiskFlag(title: "模型仍是研究用途", detail: "概率不是保证，只能作为分析参考。")
            ]
        )
    }

    private static func buildMarketBaseline(homeOdds: Double, drawOdds: Double, awayOdds: Double) -> MarketBaseline {
        let rawHome = 1 / homeOdds
        let rawDraw = 1 / drawOdds
        let rawAway = 1 / awayOdds
        let total = rawHome + rawDraw + rawAway
        return MarketBaseline(
            homeOdds: homeOdds,
            drawOdds: drawOdds,
            awayOdds: awayOdds,
            raw: ProbabilityTriple(home: rawHome, draw: rawDraw, away: rawAway),
            devig: ProbabilityTriple(home: rawHome / total, draw: rawDraw / total, away: rawAway / total),
            overround: total - 1
        )
    }

    private static func buildOddsMovement() -> OddsMovementAnalysis {
        OddsMovementAnalysis(
            openingTime: "早盘 09:20",
            currentTime: "当前 20:39",
            summary: "主队方向从早盘到当前略微升温，但水位已经变紧，说明市场更认可主队，同时价格不如早盘友好。",
            marketSignal: "主队热度上升，价格优势被压缩",
            points: [
                OddsMovementPoint(
                    label: "主胜欧赔",
                    opening: "2.18",
                    current: "2.10",
                    change: "下降 0.08",
                    direction: .supportsHome,
                    note: "主胜赔率下降，市场隐含主胜概率上升。"
                ),
                OddsMovementPoint(
                    label: "平局欧赔",
                    opening: "3.35",
                    current: "3.40",
                    change: "上升 0.05",
                    direction: .neutral,
                    note: "平局方向略微降温，变化不大。"
                ),
                OddsMovementPoint(
                    label: "客胜欧赔",
                    opening: "3.45",
                    current: "3.60",
                    change: "上升 0.15",
                    direction: .supportsHome,
                    note: "客胜赔率上升，客队方向支持变弱。"
                ),
                OddsMovementPoint(
                    label: "亚盘主队水位",
                    opening: "-0.25 @ 1.98",
                    current: "-0.25 @ 1.92",
                    change: "水位下降 0.06",
                    direction: .priceWorse,
                    note: "盘口没变但主队水位下降，主队方向更热，入场价格变差。"
                )
            ],
            riskNote: "赔率变化是强信号，但不能单独决定结论。需要和比分矩阵、盘口概率、阵容消息一起看。"
        )
    }
}
