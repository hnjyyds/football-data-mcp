import SwiftUI

enum MatrixHighlight {
    case oneXTwo
    case asian(line: Double)
    case totals(line: Double)
}

extension Double {
    func percentString(digits: Int = 1) -> String {
        String(format: "%.\(digits)f%%", self * 100)
    }

    func decimalString(digits: Int = 2) -> String {
        String(format: "%.\(digits)f", self)
    }

    var signedPercentPointString: String {
        let value = self * 100
        let sign = value >= 0 ? "+" : ""
        return "\(sign)\(String(format: "%.1f", value))%"
    }
}

struct Card<Content: View>: View {
    private let content: Content

    init(@ViewBuilder content: () -> Content) {
        self.content = content()
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            content
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color(.secondarySystemGroupedBackground))
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
    }
}

struct StatusChip: View {
    let text: String
    let color: Color

    var body: some View {
        Text(text)
            .font(.caption.weight(.semibold))
            .foregroundStyle(color)
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(color.opacity(0.12))
            .clipShape(Capsule())
            .lineLimit(1)
    }
}

struct SectionTitle: View {
    let index: Int?
    let title: String
    let subtitle: String?

    init(_ title: String, index: Int? = nil, subtitle: String? = nil) {
        self.title = title
        self.index = index
        self.subtitle = subtitle
    }

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 8) {
            if let index {
                Text("\(index)")
                    .font(.caption.weight(.bold))
                    .foregroundStyle(.white)
                    .frame(width: 22, height: 22)
                    .background(Color.accentColor)
                    .clipShape(Circle())
            }
            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.headline)
                if let subtitle {
                    Text(subtitle)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
        }
    }
}

struct ProbabilityBar: View {
    let label: String
    let value: Double
    let color: Color
    let caption: String?

    init(label: String, value: Double, color: Color, caption: String? = nil) {
        self.label = label
        self.value = value
        self.color = color
        self.caption = caption
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text(label)
                    .font(.subheadline.weight(.medium))
                Spacer()
                Text(value.percentString())
                    .font(.subheadline.monospacedDigit().weight(.semibold))
            }
            GeometryReader { proxy in
                ZStack(alignment: .leading) {
                    Capsule()
                        .fill(Color(.tertiarySystemFill))
                    Capsule()
                        .fill(color)
                        .frame(width: max(8, proxy.size.width * min(max(value, 0), 1)))
                }
            }
            .frame(height: 9)
            if let caption {
                Text(caption)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(label)，概率 \(value.percentString())")
    }
}

struct ProbabilityPills: View {
    let probabilities: ProbabilityTriple

    var body: some View {
        HStack(spacing: 8) {
            ProbabilityPill(title: "主胜", value: probabilities.home, color: .green)
            ProbabilityPill(title: "平局", value: probabilities.draw, color: .blue)
            ProbabilityPill(title: "客胜", value: probabilities.away, color: .orange)
        }
    }
}

struct ProbabilityPill: View {
    let title: String
    let value: Double
    let color: Color

    var body: some View {
        VStack(spacing: 4) {
            Text(title)
                .font(.caption)
                .foregroundStyle(.secondary)
            Text(value.percentString())
                .font(.headline.monospacedDigit())
                .foregroundStyle(color)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 10)
        .background(color.opacity(0.10))
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(title)概率 \(value.percentString())")
    }
}

struct SourceRow: View {
    let source: DataSourceEvidence

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 2) {
                    Text(source.name)
                        .font(.subheadline.weight(.semibold))
                    Text("\(source.provider) · \(source.freshness)")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                Spacer()
                StatusChip(text: source.usage.rawValue, color: usageColor)
            }
            Text(source.note)
                .font(.caption)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(.vertical, 4)
    }

    private var usageColor: Color {
        switch source.usage {
        case .used: return .green
        case .reference: return .orange
        case .ignored: return .gray
        }
    }
}

struct ScoreMatrixHeatmap: View {
    let cells: [ScoreCell]
    let highlight: MatrixHighlight
    let title: String
    let explanation: String

    private let buckets = [0, 1, 2, 3, 4]

    var body: some View {
        Card {
            SectionTitle(title, subtitle: explanation)
            VStack(spacing: 5) {
                HStack(spacing: 5) {
                    Text("主\\客")
                        .font(.caption2.weight(.semibold))
                        .foregroundStyle(.secondary)
                        .frame(width: 42, height: 26)
                    ForEach(buckets, id: \.self) { bucket in
                        Text(bucket == 4 ? "4+" : "\(bucket)")
                            .font(.caption2.weight(.semibold))
                            .foregroundStyle(.secondary)
                            .frame(maxWidth: .infinity)
                    }
                }
                ForEach(buckets, id: \.self) { homeBucket in
                    HStack(spacing: 5) {
                        Text(homeBucket == 4 ? "4+" : "\(homeBucket)")
                            .font(.caption2.weight(.semibold))
                            .foregroundStyle(.secondary)
                            .frame(width: 42, height: 38)
                        ForEach(buckets, id: \.self) { awayBucket in
                            if let cell = cell(home: homeBucket, away: awayBucket) {
                                MatrixCell(cell: cell, color: color(for: cell))
                            }
                        }
                    }
                }
            }
            Text("读法：每个格子是一种比分。把符合条件的格子概率相加，就得到胜平负、亚盘或大小球概率。")
                .font(.caption)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    private func cell(home: Int, away: Int) -> ScoreCell? {
        cells.first { $0.homeBucket == home && $0.awayBucket == away }
    }

    private func color(for cell: ScoreCell) -> Color {
        let intensity = max(0.10, min(0.82, cell.probability * 8.5))
        switch highlight {
        case .oneXTwo:
            if cell.homeBucket > cell.awayBucket { return Color.green.opacity(intensity) }
            if cell.homeBucket == cell.awayBucket { return Color.blue.opacity(intensity) }
            return Color.orange.opacity(intensity)
        case .asian(let line):
            let adjusted = Double(cell.homeBucket - cell.awayBucket) + line
            if adjusted > 0 { return Color.green.opacity(intensity) }
            if abs(adjusted) < 0.001 { return Color.blue.opacity(intensity) }
            return Color.red.opacity(intensity)
        case .totals(let line):
            let total = Double(cell.homeBucket + cell.awayBucket)
            return total > line ? Color.teal.opacity(intensity) : Color.gray.opacity(intensity)
        }
    }
}

struct MatrixCell: View {
    let cell: ScoreCell
    let color: Color

    var body: some View {
        VStack(spacing: 1) {
            Text(cell.scoreLabel)
                .font(.caption2.weight(.semibold))
            Text(cell.probability.percentString())
                .font(.caption2.monospacedDigit())
        }
        .minimumScaleFactor(0.75)
        .lineLimit(1)
        .frame(maxWidth: .infinity, minHeight: 38)
        .background(color)
        .clipShape(RoundedRectangle(cornerRadius: 6, style: .continuous))
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("比分 \(cell.scoreLabel)，概率 \(cell.probability.percentString())")
    }
}

struct RiskList: View {
    let risks: [RiskFlag]

    var body: some View {
        Card {
            SectionTitle("风险提示", subtitle: "这些不会否定概率，但会影响解读。")
            ForEach(risks) { risk in
                HStack(alignment: .top, spacing: 8) {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .foregroundStyle(.orange)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(risk.title)
                            .font(.subheadline.weight(.semibold))
                        Text(risk.detail)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }
            }
        }
    }
}
