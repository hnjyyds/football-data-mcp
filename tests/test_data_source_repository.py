import asyncio

from football_data_mcp.repositories.data_source_repository import DataSourceRepository


def test_repository_delegates_betexplorer_discovery(monkeypatch):
    captured = {}

    async def fake_discover_betexplorer_event_urls(*, targets, discovery_urls, limit, timeout_seconds=15.0):
        captured["targets"] = targets
        captured["discovery_urls"] = discovery_urls
        captured["limit"] = limit
        captured["timeout_seconds"] = timeout_seconds
        return {"status": "ok", "event_urls": ["https://www.betexplorer.com/football/x/y/z/"]}

    monkeypatch.setattr(
        "football_data_mcp.betexplorer_source.discover_betexplorer_event_urls",
        fake_discover_betexplorer_event_urls,
    )

    result = asyncio.run(
        DataSourceRepository().discover_betexplorer_event_urls(
            targets=[{"home_team": "A", "away_team": "B"}],
            discovery_urls=["https://www.betexplorer.com/football/"],
            limit=5,
        )
    )

    assert result["status"] == "ok"
    assert captured["targets"] == [{"home_team": "A", "away_team": "B"}]
    assert captured["discovery_urls"] == ["https://www.betexplorer.com/football/"]
    assert captured["limit"] == 5
