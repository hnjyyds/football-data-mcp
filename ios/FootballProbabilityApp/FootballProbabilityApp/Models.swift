import Foundation
import SwiftUI

enum AnalysisPerspective: String, CaseIterable, Identifiable {
    case oneXTwo = "胜平负"
    case asian = "亚盘"
    case totals = "大小球"

    var id: String { rawValue }
}

enum ConfidenceLevel: String, Codable {
    case high = "高"
    case medium = "中等"
    case low = "偏低"
}

enum SourceUsage: String, Codable {
    case used = "参与计算"
    case reference = "仅作参考"
    case ignored = "未采用"
}

struct TeamSummary: Identifiable, Codable {
    let id = UUID()
    let name: String
    let shortName: String

    enum CodingKeys: String, CodingKey {
        case name
        case shortName
    }
}

struct ProbabilityTriple: Codable {
    let home: Double
    let draw: Double
    let away: Double
}

struct MarketBaseline: Codable {
    let homeOdds: Double
    let drawOdds: Double
    let awayOdds: Double
    let raw: ProbabilityTriple
    let devig: ProbabilityTriple
    let overround: Double
}

enum OddsMovementDirection: String, Codable {
    case supportsHome
    case supportsAway
    case priceWorse
    case neutral
}

struct OddsMovementPoint: Identifiable, Codable {
    let id = UUID()
    let label: String
    let opening: String
    let current: String
    let change: String
    let direction: OddsMovementDirection
    let note: String

    enum CodingKeys: String, CodingKey {
        case label
        case opening
        case current
        case change
        case direction
        case note
    }
}

struct OddsMovementAnalysis: Codable {
    let openingTime: String
    let currentTime: String
    let summary: String
    let marketSignal: String
    let points: [OddsMovementPoint]
    let riskNote: String
}

struct ExpectedGoals: Codable {
    let home: Double
    let away: Double

    var total: Double { home + away }
}

struct ScoreCell: Identifiable, Codable {
    let id = UUID()
    let homeBucket: Int
    let awayBucket: Int
    let homeLabel: String
    let awayLabel: String
    let probability: Double

    var scoreLabel: String {
        "\(homeLabel)-\(awayLabel)"
    }

    enum CodingKeys: String, CodingKey {
        case homeBucket
        case awayBucket
        case homeLabel
        case awayLabel
        case probability
    }
}

struct DataSourceEvidence: Identifiable, Codable {
    let id = UUID()
    let name: String
    let provider: String
    let freshness: String
    let confidence: ConfidenceLevel
    let usage: SourceUsage
    let note: String

    enum CodingKeys: String, CodingKey {
        case name
        case provider
        case freshness
        case confidence
        case usage
        case note
    }
}

struct ProbabilityAdjustment: Identifiable, Codable {
    let id = UUID()
    let title: String
    let value: Double
    let note: String
    let used: Bool

    enum CodingKeys: String, CodingKey {
        case title
        case value
        case note
        case used
    }
}

struct CalibrationEvidence: Codable {
    let rangeLabel: String
    let actualRate: Double
    let sampleCount: Int
    let note: String
}

struct RiskFlag: Identifiable, Codable {
    let id = UUID()
    let title: String
    let detail: String

    enum CodingKeys: String, CodingKey {
        case title
        case detail
    }
}

struct AsianHandicapAnalysis: Codable {
    let line: Double
    let lineLabel: String
    let sideLabel: String
    let odds: Double
    let fullWin: Double
    let halfWin: Double
    let push: Double
    let halfLoss: Double
    let fullLoss: Double
    let priceNote: String

    var noLossProbability: Double {
        fullWin + halfWin + push
    }
}

struct TotalsAnalysis: Codable {
    let line: Double
    let lineLabel: String
    let overOdds: Double
    let underOdds: Double
    let overProbability: Double
    let underProbability: Double
    let note: String
}

struct MatchAnalysis: Identifiable, Codable {
    let id: String
    let league: String
    let kickoffText: String
    let venue: String
    let homeTeam: TeamSummary
    let awayTeam: TeamSummary
    let finalProbabilities: ProbabilityTriple
    let confidence: ConfidenceLevel
    let dataQuality: String
    let marketBaseline: MarketBaseline
    let oddsMovement: OddsMovementAnalysis
    let expectedGoals: ExpectedGoals
    let scoreMatrix: [ScoreCell]
    let dataSources: [DataSourceEvidence]
    let adjustments: [ProbabilityAdjustment]
    let calibration: CalibrationEvidence
    let asian: AsianHandicapAnalysis
    let totals: TotalsAnalysis
    let risks: [RiskFlag]
}

struct MobileMatchSummary: Identifiable, Codable {
    let id: String
    let query: String
    let homeTeam: String
    let awayTeam: String
    let league: String
    let kickoffText: String
    let kickoffUTC: String?
    let statusLabel: String
    let dataQuality: String
    let analysisReady: Bool
}
