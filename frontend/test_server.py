"""Tests for the dashboard sidecar (frontend/server.py)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))

from server import cache_header_for, SECURITY_HEADERS  # noqa: E402


def test_hashed_assets_get_immutable_cache():
    assert cache_header_for("/assets/index-abc.js") == "public, max-age=31536000, immutable"
    assert cache_header_for("/assets/app.css") == "public, max-age=31536000, immutable"


def test_html_shell_uses_no_store():
    assert cache_header_for("/") == "no-store"
    assert cache_header_for("/index.html") == "no-store"
    assert cache_header_for("/match/rec%3A1") == "no-store"


def test_security_headers_present():
    names = {name for name, _ in SECURITY_HEADERS}
    assert {"X-Content-Type-Options", "X-Frame-Options", "Referrer-Policy", "Content-Security-Policy"}.issubset(names)


def test_csp_disallows_inline_scripts():
    csp = dict(SECURITY_HEADERS)["Content-Security-Policy"]
    assert "script-src 'self'" in csp
    assert "unsafe-inline" not in csp.split("script-src")[1].split(";")[0]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
