from __future__ import annotations

import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


BACKEND_URL = os.getenv("DASHBOARD_BACKEND_URL", "http://football-data-mcp:8910").rstrip("/")
ROOT = Path(__file__).resolve().parent / "dist"

SECURITY_HEADERS = [
    ("X-Content-Type-Options", "nosniff"),
    ("X-Frame-Options", "DENY"),
    ("Referrer-Policy", "strict-origin-when-cross-origin"),
    (
        "Content-Security-Policy",
        "default-src 'self'; "
        "img-src 'self' data: https:; "
        "font-src 'self' data: https://fonts.gstatic.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "script-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'",
    ),
]


def cache_header_for(path: str) -> str:
    # Hashed asset files under /assets/ are content-addressed; safe to cache forever
    if path.startswith("/assets/") or path.startswith("assets/"):
        return "public, max-age=31536000, immutable"
    # The HTML shell and dynamic responses must always be revalidated
    return "no-store"


class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def _send_security_headers(self) -> None:
        for name, value in SECURITY_HEADERS:
            self.send_header(name, value)

    def end_headers(self) -> None:
        self.send_header("Cache-Control", cache_header_for(self.path))
        self._send_security_headers()
        super().end_headers()

    def do_OPTIONS(self) -> None:
        if self.path.startswith("/api/"):
            self.send_response(204)
            origin = self.headers.get("Origin", "")
            # Only allow same-origin / configured trusted origins
            allowed = os.getenv("DASHBOARD_CORS_ORIGIN", "")
            if allowed and origin == allowed:
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
            return
        super().do_OPTIONS()

    def do_GET(self) -> None:
        if self.path == "/healthz":
            self.serve_healthz()
            return
        if self.path.startswith("/api/"):
            self.proxy_api()
            return
        requested = ROOT / self.path.lstrip("/")
        if self.path == "/" or not requested.exists():
            self.path = "/index.html"
        super().do_GET()

    def serve_healthz(self) -> None:
        """Healthcheck that verifies backend reachability."""
        target = f"{BACKEND_URL}/api/dashboard"
        request = Request(target, headers={"Accept": "application/json"})
        try:
            with urlopen(request, timeout=3) as response:
                ok = 200 <= response.status < 500
        except Exception:
            ok = False
        body = b"ok\n" if ok else b"backend unreachable\n"
        self.send_response(200 if ok else 503)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _maybe_cors(self) -> None:
        origin = self.headers.get("Origin", "")
        allowed = os.getenv("DASHBOARD_CORS_ORIGIN", "")
        if allowed and origin == allowed:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")

    def proxy_api(self) -> None:
        target = f"{BACKEND_URL}{self.path}"
        request = Request(target, headers={"Accept": "application/json"})
        try:
            with urlopen(request, timeout=30) as response:
                body = response.read()
                self.send_response(response.status)
                self.send_header("Content-Type", response.headers.get("Content-Type", "application/json"))
                self.send_header("Content-Length", str(len(body)))
                self._maybe_cors()
                self.end_headers()
                self.wfile.write(body)
        except HTTPError as exc:
            body = exc.read()
            self.send_response(exc.code)
            self.send_header("Content-Type", exc.headers.get("Content-Type", "application/json"))
            self.send_header("Content-Length", str(len(body)))
            self._maybe_cors()
            self.end_headers()
            self.wfile.write(body)
        except URLError as exc:
            body = f'{{"status":"error","message":"backend unavailable: {exc.reason}"}}'.encode()
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self._maybe_cors()
            self.end_headers()
            self.wfile.write(body)


if __name__ == "__main__":
    port = int(os.getenv("DASHBOARD_PORT", "80"))
    server = ThreadingHTTPServer(("0.0.0.0", port), DashboardHandler)
    server.serve_forever()
