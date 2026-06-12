from __future__ import annotations

from football_data_mcp import browser_session_runtime


def test_browser_session_runtime_records_and_reads_provider_status(tmp_path):
    status_path = tmp_path / "leisu-session.json"

    written = browser_session_runtime.record_provider_status(
        "leisu",
        "ready",
        path=status_path,
        message="session ready",
        last_verification_url="https://m.leisu.com/live/odds-1",
    )
    loaded = browser_session_runtime.provider_status("leisu", path=status_path)

    assert written["provider"] == "leisu"
    assert written["status"] == "ready"
    assert written["last_ready_at_utc"]
    assert loaded["message"] == "session ready"
    assert loaded["last_verification_url"] == "https://m.leisu.com/live/odds-1"
