from __future__ import annotations

import importlib.util
import json
import threading
import urllib.request
from urllib.error import HTTPError
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import ModuleType

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_dashboard_server() -> ModuleType:
    spec = importlib.util.spec_from_file_location("dashboard_server_under_test", PROJECT_ROOT / "frontend" / "server.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("frontend server module could not be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _start_server(handler: type[BaseHTTPRequestHandler]) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def _stop_server(server: ThreadingHTTPServer) -> None:
    server.shutdown()
    server.server_close()


def test_dashboard_proxy_forwards_post_body_and_content_type() -> None:
    captured: dict[str, object] = {}

    class BackendHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            captured["method"] = self.command
            captured["path"] = self.path
            captured["content_type"] = self.headers.get("Content-Type")
            captured["body"] = self.rfile.read(length).decode("utf-8")
            body = json.dumps({"status": "ok", "method": self.command}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args: object) -> None:
            return

    backend = _start_server(BackendHandler)
    module = _load_dashboard_server()
    setattr(module, "BACKEND_URL", f"http://127.0.0.1:{backend.server_port}")
    dashboard = _start_server(module.DashboardHandler)
    try:
        payload = b'{"resume":true}'
        request = urllib.request.Request(
            f"http://127.0.0.1:{dashboard.server_port}/api/validation/holdout/jobs/job-1/retry",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(request, timeout=5) as response:
            body = json.loads(response.read().decode("utf-8"))

        assert response.status == 200
        assert body == {"status": "ok", "method": "POST"}
        assert captured == {
            "method": "POST",
            "path": "/api/validation/holdout/jobs/job-1/retry",
            "content_type": "application/json",
            "body": '{"resume":true}',
        }
    finally:
        _stop_server(dashboard)
        _stop_server(backend)


def test_dashboard_proxy_forwards_head_without_body() -> None:
    captured: dict[str, object] = {}

    class BackendHandler(BaseHTTPRequestHandler):
        def do_HEAD(self) -> None:
            captured["method"] = self.command
            captured["path"] = self.path
            self.send_response(204)
            self.send_header("Content-Type", "application/json")
            self.send_header("X-Upstream-Health", "ok")
            self.send_header("Content-Length", "123")
            self.end_headers()

        def log_message(self, *_args: object) -> None:
            return

    backend = _start_server(BackendHandler)
    module = _load_dashboard_server()
    setattr(module, "BACKEND_URL", f"http://127.0.0.1:{backend.server_port}")
    dashboard = _start_server(module.DashboardHandler)
    try:
        request = urllib.request.Request(
            f"http://127.0.0.1:{dashboard.server_port}/api/health",
            method="HEAD",
        )

        with urllib.request.urlopen(request, timeout=5) as response:
            body = response.read()

        assert response.status == 204
        assert body == b""
        assert response.headers.get("Content-Type") == "application/json"
        assert response.headers.get("Content-Length") == "123"
        assert captured == {"method": "HEAD", "path": "/api/health"}
    finally:
        _stop_server(dashboard)
        _stop_server(backend)


def test_dashboard_proxy_options_allows_post_for_api_routes() -> None:
    module = _load_dashboard_server()
    dashboard = _start_server(module.DashboardHandler)
    try:
        request = urllib.request.Request(
            f"http://127.0.0.1:{dashboard.server_port}/api/validation/holdout/jobs/job-1/cancel",
            method="OPTIONS",
        )

        with urllib.request.urlopen(request, timeout=5) as response:
            allow_methods = response.headers.get("Access-Control-Allow-Methods", "")

        assert response.status == 204
        assert "POST" in allow_methods
    finally:
        _stop_server(dashboard)


def test_dashboard_healthz_uses_lightweight_backend_health_endpoint() -> None:
    captured: dict[str, object] = {}

    class BackendHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            captured["path"] = self.path
            body = b'{"status":"ok"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args: object) -> None:
            return

    backend = _start_server(BackendHandler)
    module = _load_dashboard_server()
    setattr(module, "BACKEND_URL", f"http://127.0.0.1:{backend.server_port}")
    dashboard = _start_server(module.DashboardHandler)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{dashboard.server_port}/healthz", timeout=5) as response:
            body = response.read().decode("utf-8")

        assert response.status == 200
        assert body == "ok\n"
        assert captured["path"] == "/api/health"
    finally:
        _stop_server(dashboard)
        _stop_server(backend)


def test_dashboard_healthz_head_returns_no_body() -> None:
    class BackendHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            body = b'{"status":"ok"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args: object) -> None:
            return

    backend = _start_server(BackendHandler)
    module = _load_dashboard_server()
    setattr(module, "BACKEND_URL", f"http://127.0.0.1:{backend.server_port}")
    dashboard = _start_server(module.DashboardHandler)
    try:
        request = urllib.request.Request(
            f"http://127.0.0.1:{dashboard.server_port}/healthz",
            method="HEAD",
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            body = response.read()

        assert response.status == 200
        assert body == b""
        assert response.headers.get("Content-Type") == "text/plain"
        assert response.headers.get("Cache-Control") == "no-store"
    finally:
        _stop_server(dashboard)
        _stop_server(backend)


def test_dashboard_healthz_requires_backend_success_status() -> None:
    class BackendHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            body = b"temporary redirect without target"
            self.send_response(302)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_args: object) -> None:
            return

    backend = _start_server(BackendHandler)
    module = _load_dashboard_server()
    setattr(module, "BACKEND_URL", f"http://127.0.0.1:{backend.server_port}")
    dashboard = _start_server(module.DashboardHandler)
    try:
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{dashboard.server_port}/healthz", timeout=5)
        except HTTPError as exc:
            body = exc.read().decode("utf-8")
            assert exc.code == 503
            assert body == "backend unreachable\n"
            assert exc.headers.get("Cache-Control") == "no-store"
        else:
            raise AssertionError("dashboard healthz unexpectedly accepted a non-2xx backend status")
    finally:
        _stop_server(dashboard)
        _stop_server(backend)


def test_dashboard_spa_routes_fallback_to_index_for_get_and_head(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><title>Football dashboard</title>", encoding="utf-8")

    module = _load_dashboard_server()
    setattr(module, "ROOT", dist)
    dashboard = _start_server(module.DashboardHandler)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{dashboard.server_port}/model", timeout=5) as response:
            body = response.read().decode("utf-8")

        assert response.status == 200
        assert "Football dashboard" in body
        assert response.headers.get("Cache-Control") == "no-store"

        request = urllib.request.Request(
            f"http://127.0.0.1:{dashboard.server_port}/match/recommendation%3A415",
            method="HEAD",
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            head_body = response.read()

        assert response.status == 200
        assert head_body == b""
        assert response.headers.get("Cache-Control") == "no-store"

        with urllib.request.urlopen(
            f"http://127.0.0.1:{dashboard.server_port}/model?tab=quality",
            timeout=5,
        ) as response:
            query_body = response.read().decode("utf-8")

        assert response.status == 200
        assert "Football dashboard" in query_body
    finally:
        _stop_server(dashboard)


def test_dashboard_missing_assets_do_not_fallback_to_index(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><title>Football dashboard</title>", encoding="utf-8")

    module = _load_dashboard_server()
    setattr(module, "ROOT", dist)
    dashboard = _start_server(module.DashboardHandler)
    try:
        request = urllib.request.Request(
            f"http://127.0.0.1:{dashboard.server_port}/assets/missing.js",
            method="GET",
        )
        try:
            urllib.request.urlopen(request, timeout=5)
        except HTTPError as exc:
            assert exc.code == 404
            assert exc.headers.get("Cache-Control") == "no-store"
        else:
            raise AssertionError("missing asset unexpectedly fell back to the SPA index")
    finally:
        _stop_server(dashboard)


@pytest.mark.parametrize(
    "unsafe_path",
    [
        "/%2e%2e/server",
        "/%252e%252e/server",
        "/model%5c..%5cserver",
    ],
)
def test_dashboard_rejects_unsafe_spa_paths(tmp_path: Path, unsafe_path: str) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><title>Football dashboard</title>", encoding="utf-8")

    module = _load_dashboard_server()
    setattr(module, "ROOT", dist)
    dashboard = _start_server(module.DashboardHandler)
    try:
        request = urllib.request.Request(
            f"http://127.0.0.1:{dashboard.server_port}{unsafe_path}",
            method="GET",
        )
        try:
            urllib.request.urlopen(request, timeout=5)
        except HTTPError as exc:
            assert exc.code == 404
            assert exc.headers.get("Cache-Control") == "no-store"
        else:
            raise AssertionError("unsafe path unexpectedly fell back to the SPA index")
    finally:
        _stop_server(dashboard)
