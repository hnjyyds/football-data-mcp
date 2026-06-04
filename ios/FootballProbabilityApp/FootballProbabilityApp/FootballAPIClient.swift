import Foundation

struct MobileMatchesResponse: Decodable {
    let status: String
    let generatedAtUTC: String
    let matches: [MobileMatchSummary]
}

struct MobileAnalysisResponse: Decodable {
    let status: String
    let generatedAtUTC: String
    let analysis: MatchAnalysis
}

enum FootballAPIError: LocalizedError {
    case invalidURL
    case badStatus(Int)

    var errorDescription: String? {
        switch self {
        case .invalidURL:
            return "后端地址不正确。"
        case .badStatus(let status):
            return "后端返回异常状态：\(status)。"
        }
    }
}

struct FootballAPIClient {
    let baseURL: URL
    var session: URLSession = .shared

    init(baseURL: URL = URL(string: "http://127.0.0.1:8910")!) {
        self.baseURL = baseURL
    }

    func fetchMatches(windowHours: Int = 24, limit: Int = 30) async throws -> [MobileMatchSummary] {
        var components = URLComponents(url: baseURL.appending(path: "/api/mobile/matches"), resolvingAgainstBaseURL: false)
        components?.queryItems = [
            URLQueryItem(name: "window_hours", value: "\(windowHours)"),
            URLQueryItem(name: "limit", value: "\(limit)")
        ]
        let response: MobileMatchesResponse = try await get(components)
        return response.matches
    }

    func analyze(match: MobileMatchSummary, windowHours: Int = 24) async throws -> MatchAnalysis {
        try await analyze(query: match.query, league: match.league, windowHours: windowHours)
    }

    func analyze(query: String, league: String? = nil, windowHours: Int = 24) async throws -> MatchAnalysis {
        var components = URLComponents(url: baseURL.appending(path: "/api/mobile/analysis"), resolvingAgainstBaseURL: false)
        var items = [
            URLQueryItem(name: "query", value: query),
            URLQueryItem(name: "window_hours", value: "\(windowHours)")
        ]
        if let league, !league.isEmpty {
            items.append(URLQueryItem(name: "league", value: league))
        }
        components?.queryItems = items
        let response: MobileAnalysisResponse = try await get(components)
        return response.analysis
    }

    private func get<Response: Decodable>(_ components: URLComponents?) async throws -> Response {
        guard let url = components?.url else {
            throw FootballAPIError.invalidURL
        }
        var request = URLRequest(url: url)
        request.cachePolicy = .reloadIgnoringLocalCacheData
        request.timeoutInterval = 45
        let (data, urlResponse) = try await session.data(for: request)
        if let http = urlResponse as? HTTPURLResponse, !(200..<300).contains(http.statusCode) {
            throw FootballAPIError.badStatus(http.statusCode)
        }
        let decoder = JSONDecoder()
        return try decoder.decode(Response.self, from: data)
    }
}

@MainActor
final class FootballAppModel: ObservableObject {
    let client: FootballAPIClient

    @Published var matches: [MobileMatchSummary] = []
    @Published var featuredAnalysis: MatchAnalysis = MockAnalysisData.sample
    @Published var isLoading = false
    @Published var errorMessage: String?
    @Published var usingFallback = true

    init(client: FootballAPIClient = FootballAPIClient()) {
        self.client = client
    }

    func loadHome() async {
        isLoading = true
        defer { isLoading = false }
        do {
            let remoteMatches = try await client.fetchMatches()
            matches = remoteMatches
            usingFallback = remoteMatches.isEmpty
            errorMessage = remoteMatches.isEmpty ? "后端没有返回可分析比赛，先显示样板。" : nil
            if let first = remoteMatches.first {
                do {
                    featuredAnalysis = try await client.analyze(match: first)
                    usingFallback = false
                } catch {
                    featuredAnalysis = MockAnalysisData.sample
                    usingFallback = true
                    errorMessage = "比赛列表已加载，但首场详情暂时失败：\(error.localizedDescription)"
                }
            }
        } catch {
            matches = []
            featuredAnalysis = MockAnalysisData.sample
            usingFallback = true
            errorMessage = error.localizedDescription
        }
    }
}
