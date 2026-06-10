import asyncio
import json

from football_data_mcp.api.controllers import data_sources as data_sources_controller
from football_data_mcp.services.data_source_service import DataSourceService


class _FakeRequest:
    def __init__(self, payload: dict[str, object]):
        self.method = "POST"
        self._payload = payload
        self.headers = {}

    async def json(self):
        return self._payload


def test_data_source_service_exposes_betexplorer_status(tmp_path):
    db_path = str(tmp_path / "snapshots.sqlite3")
    status = DataSourceService().odds_source_status(db_path=db_path)

    assert "betexplorer_scraper" in status["sources"]
    assert status["sources"]["betexplorer_scraper"]["role"].startswith("structured fallback odds crawler")


def test_betexplorer_sync_api_uses_service(monkeypatch):
    async def fake_start(self, *, event_urls, markets, limit, force):
        return {
            "status": "ok",
            "provider": "betexplorer_scraper",
            "job_id": "betexplorer-test",
            "requested_event_count": len(event_urls),
            "requested_markets": markets,
            "saved_snapshot_count": 3,
        }

    monkeypatch.setattr(DataSourceService, "start_betexplorer_sync", fake_start)

    response = asyncio.run(
        data_sources_controller.betexplorer_sync_api(
            _FakeRequest(
                {
                    "event_urls": ["https://www.betexplorer.com/football/australia/npl-act/x/y/"],
                    "markets": ["h2h"],
                    "limit": 1,
                    "force": True,
                }
            )
        )
    )
    body = json.loads(response.body)

    assert body["status"] == "ok"
    assert body["provider"] == "betexplorer_scraper"
