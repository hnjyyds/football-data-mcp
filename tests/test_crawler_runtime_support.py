from __future__ import annotations

import importlib.util

from football_data_mcp import crawler_runtime_support


def test_crawlee_runtime_support_reports_missing_modules(monkeypatch):
    def fake_find_spec(name: str):
        return None

    monkeypatch.setattr(importlib.util, "find_spec", fake_find_spec)

    support = crawler_runtime_support.crawlee_runtime_support()

    assert support["status"] == "not_installed"
    assert support["supported"] is False


def test_leisu_crawlee_runtime_plan_derives_status_url(monkeypatch):
    monkeypatch.setenv("LEISU_ODDS_PROXY_URL", "http://127.0.0.1:8918/leisu/odds/{match_id}")

    plan = crawler_runtime_support.leisu_crawlee_runtime_plan()

    assert plan["provider"] == "leisu"
    assert plan["browser_proxy_status_url"] == "http://127.0.0.1:8918/leisu/session"
    assert plan["uses_persistent_profile"] is True
