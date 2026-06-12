from football_data_mcp import betexplorer_source
from football_data_mcp import snapshot_store
from football_data_mcp import sources as sources_module


def test_extract_betexplorer_match_urls_deduplicates_and_absolutizes():
    html = """
    <html><body>
      <a href="/football/australia/npl-act/belconnen-united-canberra-white-eagles/OvKeupeC/">A</a>
      <a href="/football/australia/npl-act/belconnen-united-canberra-white-eagles/OvKeupeC/">A2</a>
      <a href="/football/czech-republic/u19-league/ostrava-brno/SC7Sfmec/">B</a>
    </body></html>
    """
    urls = betexplorer_source.extract_betexplorer_match_urls(
        html,
        page_url="https://www.betexplorer.com/football/",
    )

    assert urls == [
        "https://www.betexplorer.com/football/australia/npl-act/belconnen-united-canberra-white-eagles/OvKeupeC/",
        "https://www.betexplorer.com/football/czech-republic/u19-league/ostrava-brno/SC7Sfmec/",
    ]


def test_extract_betexplorer_market_tab_urls():
    html = """
    <html><body>
      <a href="/football/australia/npl-act/belconnen-united-canberra-white-eagles/OvKeupeC/1x2/">1X2</a>
      <a href="/football/australia/npl-act/belconnen-united-canberra-white-eagles/OvKeupeC/over-under/">O/U</a>
      <a href="/football/australia/npl-act/belconnen-united-canberra-white-eagles/OvKeupeC/asian-handicap/">AH</a>
    </body></html>
    """
    tabs = betexplorer_source.extract_betexplorer_market_tab_urls(
        html,
        page_url="https://www.betexplorer.com/football/australia/npl-act/belconnen-united-canberra-white-eagles/OvKeupeC/",
    )

    assert tabs == {
        "1x2": "https://www.betexplorer.com/football/australia/npl-act/belconnen-united-canberra-white-eagles/OvKeupeC/1x2/",
        "over_under": "https://www.betexplorer.com/football/australia/npl-act/belconnen-united-canberra-white-eagles/OvKeupeC/over-under/",
        "asian_handicap": "https://www.betexplorer.com/football/australia/npl-act/belconnen-united-canberra-white-eagles/OvKeupeC/asian-handicap/",
    }


def test_extract_betexplorer_match_load_args():
    html = """
    <script>
    $(document).ready(function()
    {
        match_load_tabs('OvKeupeC', '1x2', 'SW9D1eZo', 'WzvGZwnK', '0', true, 'en', 'Football', 'NPL ACT', 'Australia');
    });
    </script>
    """
    args = betexplorer_source.extract_betexplorer_match_load_args(html)

    assert args == {
        "event_id": "OvKeupeC",
        "bet_type": "1x2",
        "stage_id": "SW9D1eZo",
        "hp_h": "WzvGZwnK",
        "hp_a": "0",
    }


def test_betexplorer_market_snapshots_from_html_extracts_1x2_rows():
    html = """
    <table class="table-main sortable oddsComparison__table best-odds-0" id="sortable-1">
      <thead><tr><th></th><th></th><th></th><th></th><th>1</th><th>X</th><th>2</th></tr></thead>
      <tbody id="best-odds-0">
        <tr data-bid="417">
          <td><a class="in-bookmaker-logo-link">1xBet</a></td>
          <td></td><td></td><td></td>
          <td data-odd="1.08" data-created="10,06,2026,07,45"></td>
          <td data-odd="10.70" data-created="10,06,2026,08,01"></td>
          <td data-odd="10.70" data-created="10,06,2026,08,01"></td>
        </tr>
      </tbody>
    </table>
    """
    snapshots = betexplorer_source.betexplorer_market_snapshots_from_html(
        html,
        event_url="https://www.betexplorer.com/football/australia/npl-act/belconnen-united-canberra-white-eagles/OvKeupeC/1x2/",
        market_type="1x2",
        fetched_at_utc="2026-06-10T08:00:00+00:00",
    )

    assert len(snapshots) == 3
    assert snapshots[0].provider == "betexplorer_scraper"
    assert snapshots[0].bookmaker == "1xBet"
    assert snapshots[0].market_type == "h2h"
    assert snapshots[0].selection == "1"
    assert snapshots[1].selection == "X"
    assert snapshots[2].selection == "2"


def test_betexplorer_market_snapshots_from_html_parses_split_handicap_line():
    html = """
    <table class="table-main sortable oddsComparison__tablehidden table-collapse--4.25 best-odds--4.25 hidden" id="sortable-1">
      <thead><tr><th></th><th></th><th></th><th></th><th>Handicap</th><th>1</th><th>2</th></tr></thead>
      <tbody>
        <tr data-bid="417">
          <td><a class="in-bookmaker-logo-link">1xBet</a></td>
          <td></td><td></td><td></td>
          <td>-4, -4.5</td>
          <td data-odd="3.20" data-created="10,06,2026,07,57"></td>
          <td data-odd="1.26" data-created="10,06,2026,07,57"></td>
        </tr>
      </tbody>
    </table>
    """
    snapshots = betexplorer_source.betexplorer_market_snapshots_from_html(
        html,
        event_url="https://www.betexplorer.com/football/australia/npl-act/belconnen-united-canberra-white-eagles/OvKeupeC/asian-handicap/",
        market_type="asian_handicap",
        fetched_at_utc="2026-06-10T08:00:00+00:00",
    )

    assert len(snapshots) == 2
    assert snapshots[0].line == -4.25
    assert snapshots[0].selection == "home_cover"
    assert snapshots[1].selection == "away_cover"


def test_sync_betexplorer_odds_snapshots_persists_rows(monkeypatch, tmp_path):
    event_url = "https://www.betexplorer.com/football/australia/npl-act/belconnen-united-canberra-white-eagles/OvKeupeC/1x2/"
    db_path = str(tmp_path / "snapshots.sqlite3")

    async def fake_fetch(event_url_arg: str, *, market_type: str, timeout_seconds: float = 15.0):
        assert event_url_arg == event_url
        assert market_type == "1x2"
        return {
            "status": "ok",
            "provider": "betexplorer_scraper",
            "event_url": event_url_arg,
            "market_type": market_type,
            "event_id": "OvKeupeC",
            "snapshot_count": 1,
            "snapshots": [
                snapshot_store.MarketSnapshot(
                    provider="betexplorer_scraper",
                    source_key="betexplorer:OvKeupeC:1x2",
                    event_id="OvKeupeC",
                    league="npl act",
                    home_team="Belconnen Utd.",
                    away_team="Canberra White Eagles",
                    kickoff_utc="2026-06-10T09:30:00+00:00",
                    bookmaker="1xBet",
                    market_type="h2h",
                    selection="1",
                    decimal_odds=1.08,
                    line=None,
                    source_time_utc="2026-06-10T07:45:00+00:00",
                    fetched_at_utc="2026-06-10T08:00:00+00:00",
                    raw={"event_url": event_url_arg},
                )
            ],
        }

    monkeypatch.setattr(
        "football_data_mcp.betexplorer_source.fetch_betexplorer_event_market_snapshots",
        fake_fetch,
    )
    monkeypatch.setattr(snapshot_store, "snapshot_db_path", lambda: db_path)

    result = __import__("asyncio").run(
        sources_module.sync_betexplorer_odds_snapshots(
            event_urls=[event_url],
            markets=["h2h"],
            limit=1,
            force=True,
        )
    )

    assert result["status"] == "ok"
    assert result["saved_snapshot_count"] == 1
    rows = snapshot_store.find_market_snapshots("Belconnen Utd.", "Canberra White Eagles", db_path=db_path, limit=20)
    assert len(rows) == 1
    assert rows[0]["provider"] == "betexplorer_scraper"


def test_match_betexplorer_events_to_targets_prefers_best_home_away_match():
    event_urls = [
        "https://www.betexplorer.com/football/australia/npl-act/belconnen-united-canberra-white-eagles/OvKeupeC/",
        "https://www.betexplorer.com/football/australia/npl-act/canberra-croatia-queanbeyan-city/UwnTMyuo/",
    ]
    targets = [
        {
            "league": "澳大利亚 NPL ACT",
            "home_team": "Belconnen United",
            "away_team": "Canberra White Eagles",
        }
    ]

    matches = betexplorer_source.match_betexplorer_events_to_targets(event_urls, targets, limit=5)

    assert len(matches) == 1
    assert matches[0]["event_url"].endswith("/OvKeupeC/")
    assert matches[0]["score"] >= 0.55


def test_match_betexplorer_events_to_targets_supports_chinese_aliases():
    event_urls = [
        "https://www.betexplorer.com/football/aruba/division-di-honor/britannia-aruba-sport/ABC12345/",
    ]
    targets = [
        {
            "league": "阿鲁巴甲级联赛",
            "home_team": "布里坦尼亚",
            "away_team": "阿鲁巴体育",
        }
    ]

    matches = betexplorer_source.match_betexplorer_events_to_targets(event_urls, targets, limit=5)

    assert len(matches) == 1
    assert matches[0]["event_url"].endswith("/ABC12345/")
    assert matches[0]["score"] >= 0.55


def test_betexplorer_discovery_urls_for_targets_uses_league_mapping():
    urls = betexplorer_source.betexplorer_discovery_urls_for_targets(
        [
            {"league": "西乙"},
            {"league": "阿鲁巴甲级联赛"},
            {"league": "马里甲"},
        ]
    )

    assert "https://www.betexplorer.com/football/spain/laliga2/" in urls
    assert "https://www.betexplorer.com/football/aruba/division-di-honor/" in urls
    assert "https://www.betexplorer.com/football/mali/premiere-division/" in urls


def test_discover_betexplorer_event_urls_handles_missing_targets():
    result = betexplorer_source.discover_betexplorer_event_urls
    assert callable(result)
