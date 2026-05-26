from __future__ import annotations

import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BACKEND_URL = os.getenv("DASHBOARD_BACKEND_URL", "http://football-data-mcp:8910").rstrip("/")
ROOT = Path(__file__).resolve().parent / "dist"


class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        if self.path.startswith("/api/"):
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
            return
        super().do_OPTIONS()

    def do_GET(self) -> None:
        if self.path.startswith("/api/"):
            self.proxy_api()
            return
        requested = ROOT / self.path.lstrip("/")
        if self.path == "/" or not requested.exists():
            self.path = "/index.html"
        super().do_GET()

    def proxy_api(self) -> None:
        target = f"{BACKEND_URL}{self.path}"
        request = Request(target, headers={"Accept": "application/json"})
        try:
            with urlopen(request, timeout=20) as response:
                body = response.read()
                self.send_response(response.status)
                self.send_header("Content-Type", response.headers.get("Content-Type", "application/json"))
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(body)
        except HTTPError as exc:
            body = exc.read()
            self.send_response(exc.code)
            self.send_header("Content-Type", exc.headers.get("Content-Type", "application/json"))
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except URLError as exc:
            body = f'{{"status":"error","message":"backend unavailable: {exc.reason}"}}'.encode()
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)


if __name__ == "__main__":
    port = int(os.getenv("DASHBOARD_PORT", "80"))
    server = ThreadingHTTPServer(("0.0.0.0", port), DashboardHandler)
    server.serve_forever()
