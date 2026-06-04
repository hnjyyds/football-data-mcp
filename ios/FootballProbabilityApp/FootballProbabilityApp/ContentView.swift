import SwiftUI

struct ContentView: View {
    @StateObject private var model = FootballAppModel()

    var body: some View {
        TabView {
            NavigationStack {
                TodayView(model: model)
            }
            .tabItem {
                Label("今日", systemImage: "sun.max")
            }

            NavigationStack {
                MatchesView(model: model)
            }
            .tabItem {
                Label("比赛", systemImage: "sportscourt")
            }

            NavigationStack {
                NewsView(analysis: model.featuredAnalysis)
            }
            .tabItem {
                Label("资讯", systemImage: "newspaper")
            }

            NavigationStack {
                LabView(analysis: model.featuredAnalysis)
            }
            .tabItem {
                Label("模型", systemImage: "chart.xyaxis.line")
            }
        }
        .tint(.blue)
        .task {
            await model.loadHome()
        }
    }
}

struct TodayView: View {
    @ObservedObject var model: FootballAppModel

    private var analysis: MatchAnalysis {
        model.featuredAnalysis
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                BackendStatusCard(model: model)
                DataHealthStrip(analysis: analysis)

                SectionTitle("下一场重点比赛", subtitle: "点进比赛后可以看完整计算过程。")
                NavigationLink {
                    if let first = model.matches.first {
                        RemoteMatchDetailView(match: first, client: model.client)
                    } else {
                        MatchDetailView(analysis: analysis)
                    }
                } label: {
                    MatchSummaryCard(analysis: analysis)
                }
                .buttonStyle(.plain)

                Card {
                    SectionTitle("刚出现的信号", subtitle: "未确认的信息默认只作提示。")
                    SignalRow(icon: "person.crop.circle.badge.exclamationmark", title: "伤停消息", detail: "主队后防有人出战成疑，暂未强行改动概率。", usage: "仅作参考")
                    SignalRow(icon: "arrow.left.arrow.right", title: "盘口变化", detail: "主队方向价格变紧，系统已在亚盘页展示风险。", usage: "参与计算")
                    SignalRow(icon: "newspaper", title: "赛前新闻", detail: "教练提到可能轮换，来源语气不确定。", usage: "未采用")
                }
            }
            .padding()
        }
        .background(Color(.systemGroupedBackground))
        .navigationTitle("今日")
        .refreshable {
            await model.loadHome()
        }
    }
}

struct MatchesView: View {
    @ObservedObject var model: FootballAppModel
    @State private var window = "今日"

    private let windows = ["今日", "24小时", "7天", "关注"]

    var body: some View {
        VStack(spacing: 0) {
            Picker("时间范围", selection: $window) {
                ForEach(windows, id: \.self) { value in
                    Text(value)
                }
            }
            .pickerStyle(.segmented)
            .padding()

            List {
                Section("可分析比赛") {
                    if model.matches.isEmpty {
                        NavigationLink {
                            MatchDetailView(analysis: model.featuredAnalysis)
                        } label: {
                            MatchListRow(analysis: model.featuredAnalysis)
                        }
                    } else {
                        ForEach(model.matches) { match in
                            NavigationLink {
                                RemoteMatchDetailView(match: match, client: model.client)
                            } label: {
                                MobileMatchListRow(match: match)
                            }
                        }
                    }
                }
                Section("状态说明") {
                    Label("完整：赔率、预期进球和校准都可用", systemImage: "checkmark.circle")
                    Label("部分：可以算基础概率，但部分增强信号仅作参考", systemImage: "exclamationmark.circle")
                    Label("缓存：后端暂时不可达时显示上次结果", systemImage: "clock.arrow.circlepath")
                }
                .font(.caption)
                .foregroundStyle(.secondary)
            }
            .listStyle(.insetGrouped)
        }
        .navigationTitle("比赛")
        .refreshable {
            await model.loadHome()
        }
    }
}

struct RemoteMatchDetailView: View {
    let match: MobileMatchSummary
    let client: FootballAPIClient

    @State private var analysis: MatchAnalysis?
    @State private var isLoading = true
    @State private var errorMessage: String?

    var body: some View {
        Group {
            if let analysis {
                MatchDetailView(analysis: analysis)
            } else {
                VStack(spacing: 14) {
                    if isLoading {
                        ProgressView("正在请求后端分析")
                    } else {
                        Image(systemName: "wifi.exclamationmark")
                            .font(.largeTitle)
                            .foregroundStyle(.orange)
                        Text("后端暂时不可用")
                            .font(.headline)
                        Text(errorMessage ?? "请确认 football-data-mcp 已启动。")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                            .multilineTextAlignment(.center)
                        Button {
                            Task { await load() }
                        } label: {
                            Label("重试", systemImage: "arrow.clockwise")
                        }
                        .buttonStyle(.borderedProminent)
                    }
                }
                .padding()
            }
        }
        .navigationTitle(match.homeTeam)
        .navigationBarTitleDisplayMode(.inline)
        .task {
            await load()
        }
    }

    private func load() async {
        isLoading = true
        errorMessage = nil
        do {
            analysis = try await client.analyze(match: match)
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }
}

struct BackendStatusCard: View {
    @ObservedObject var model: FootballAppModel

    var body: some View {
        Card {
            HStack {
                Label(model.usingFallback ? "样板模式" : "已连接后端", systemImage: model.usingFallback ? "wifi.slash" : "checkmark.icloud")
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(model.usingFallback ? .orange : .green)
                Spacer()
                if model.isLoading {
                    ProgressView()
                }
            }
            Text(statusText)
                .font(.caption)
                .foregroundStyle(.secondary)
        }
    }

    private var statusText: String {
        if let error = model.errorMessage {
            return "后端地址：http://127.0.0.1:8910。当前错误：\(error)"
        }
        if model.usingFallback {
            return "还没有真实比赛数据，先用样板展示完整流程。"
        }
        return "比赛列表和详情分析来自本机 football-data-mcp 后端。"
    }
}

struct NewsView: View {
    let analysis: MatchAnalysis

    var body: some View {
        List {
            Section("与本场相关") {
                ArticleSignalCard(
                    source: "RSSHub · 14分钟前",
                    title: "北城主帅暗示可能小幅轮换",
                    signal: "轮换风险",
                    usage: "未采用",
                    detail: "表达不够明确，系统只展示提醒，不让它直接影响胜率。"
                )
                ArticleSignalCard(
                    source: "公开新闻源 · 28分钟前",
                    title: "海港城连续客场，体能压力增加",
                    signal: "赛程压力",
                    usage: "参与计算",
                    detail: "和赛程数据一致，作为轻微信号参与修正。"
                )
            }
        }
        .navigationTitle("资讯")
    }
}

struct LabView: View {
    let analysis: MatchAnalysis

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                Card {
                    SectionTitle("模型状态", subtitle: "当前版本只做个人分析参考。")
                    ProbabilityBar(label: "历史相似区间实际命中", value: analysis.calibration.actualRate, color: .teal, caption: "样本 \(analysis.calibration.sampleCount) 场")
                    Text("系统会优先回答：这个概率有没有历史校准证据，而不是只给一个看起来很准的数字。")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }

                Card {
                    SectionTitle("小白解释", subtitle: "点开比赛时也会看到这些解释。")
                    ExplanationRow(title: "预期进球", detail: "不是预测最终比分，而是估算两队平均能进几个球。")
                    ExplanationRow(title: "比分概率图", detail: "把所有可能比分列出来，每个格子都是一种比分的概率。")
                    ExplanationRow(title: "亚盘", detail: "不是看谁赢球，而是看加上让球后是否赢盘、走水或输盘。")
                    ExplanationRow(title: "校准", detail: "检查模型过去说 45%-50% 时，实际发生率是否也接近。")
                }
            }
            .padding()
        }
        .background(Color(.systemGroupedBackground))
        .navigationTitle("模型")
    }
}

struct DataHealthStrip: View {
    let analysis: MatchAnalysis

    var body: some View {
        Card {
            HStack(spacing: 8) {
                StatusChip(text: "赔率新鲜", color: .green)
                StatusChip(text: "预期进球可用", color: .teal)
                StatusChip(text: "伤停待确认", color: .orange)
            }
            Text("先保证基础概率可算，再让可靠的增强信号参与修正。")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
    }
}

struct MatchSummaryCard: View {
    let analysis: MatchAnalysis

    var body: some View {
        Card {
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: 5) {
                    Text("\(analysis.homeTeam.name) vs \(analysis.awayTeam.name)")
                        .font(.headline)
                    Text("\(analysis.kickoffText) · \(analysis.league) · \(analysis.venue)")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                Spacer()
                StatusChip(text: "完整", color: .green)
            }
            ProbabilityPills(probabilities: analysis.finalProbabilities)
            Text("不是保证结果，而是把赔率、比分模型、盘口和校准证据放在一起算出的概率。")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
    }
}

struct MatchListRow: View {
    let analysis: MatchAnalysis

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(analysis.kickoffText)
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.secondary)
                Text(analysis.league)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Spacer()
                Text("可分析")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.green)
            }
            Text("\(analysis.homeTeam.name) vs \(analysis.awayTeam.name)")
                .font(.subheadline.weight(.semibold))
            ProbabilityPills(probabilities: analysis.finalProbabilities)
        }
        .padding(.vertical, 4)
    }
}

struct MobileMatchListRow: View {
    let match: MobileMatchSummary

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(match.kickoffText)
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
                Text(match.league)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
                Spacer()
                Text(match.statusLabel)
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(match.analysisReady ? .green : .orange)
            }
            Text("\(match.homeTeam) vs \(match.awayTeam)")
                .font(.subheadline.weight(.semibold))
            HStack(spacing: 8) {
                StatusChip(text: "数据：\(match.dataQuality)", color: match.analysisReady ? .green : .orange)
                StatusChip(text: "点开实时计算", color: .blue)
            }
        }
        .padding(.vertical, 4)
    }
}

struct SignalRow: View {
    let icon: String
    let title: String
    let detail: String
    let usage: String

    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: icon)
                .foregroundStyle(.blue)
                .frame(width: 22)
            VStack(alignment: .leading, spacing: 3) {
                HStack {
                    Text(title)
                        .font(.subheadline.weight(.semibold))
                    Spacer()
                    StatusChip(text: usage, color: usage == "参与计算" ? .green : usage == "未采用" ? .gray : .orange)
                }
                Text(detail)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
    }
}

struct ArticleSignalCard: View {
    let source: String
    let title: String
    let signal: String
    let usage: String
    let detail: String

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(source)
                .font(.caption)
                .foregroundStyle(.secondary)
            Text(title)
                .font(.subheadline.weight(.semibold))
            HStack {
                StatusChip(text: signal, color: .blue)
                StatusChip(text: usage, color: usage == "参与计算" ? .green : .gray)
            }
            Text(detail)
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .padding(.vertical, 5)
    }
}

struct ExplanationRow: View {
    let title: String
    let detail: String

    var body: some View {
        VStack(alignment: .leading, spacing: 3) {
            Text(title)
                .font(.subheadline.weight(.semibold))
            Text(detail)
                .font(.caption)
                .foregroundStyle(.secondary)
        }
    }
}
