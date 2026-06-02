from __future__ import annotations

import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse
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


def request_path(raw_path: str) -> str:
    """Return only the URL path; query strings must not affect static routing."""
    return urlparse(raw_path).path or "/"


def decoded_request_path(path: str) -> str:
    decoded = path
    for _ in range(3):
        next_decoded = unquote(decoded)
        if next_decoded == decoded:
            break
        decoded = next_decoded
    return decoded


def is_safe_static_path(path: str) -> bool:
    """Reject encoded traversal before static lookup or SPA fallback."""
    decoded = decoded_request_path(path)
    if "\x00" in decoded or "\\" in decoded:
        return False
    return ".." not in Path(decoded).parts


def should_fallback_to_spa(path: str) -> bool:
    """SPA routes use index.html, while missing assets/files should stay 404."""
    if not is_safe_static_path(path):
        return False
    if path == "/":
        return True
    if path.startswith("/api/") or path == "/healthz":
        return False
    if path.startswith("/assets/"):
        return False
    return Path(unquote(path)).suffix == ""


class DashboardHandler(SimpleHTTPRequestHandler):
    _sending_error = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def _send_security_headers(self) -> None:
        for name, value in SECURITY_HEADERS:
            self.send_header(name, value)

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store" if self._sending_error else cache_header_for(self.path))
        self._send_security_headers()
        super().end_headers()

    def send_error(self, code: int, message: str | None = None, explain: str | None = None) -> None:
        self._sending_error = True
        try:
            super().send_error(code, message, explain)
        finally:
            self._sending_error = False

    def do_OPTIONS(self) -> None:
        if self.path.startswith("/api/"):
            self.send_response(204)
            origin = self.headers.get("Origin", "")
            # Only allow same-origin / configured trusted origins
            allowed = os.getenv("DASHBOARD_CORS_ORIGIN", "")
            if allowed and origin == allowed:
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
            return
        self.send_error(404, "Not found")

    def do_GET(self) -> None:
        path = request_path(self.path)
        if path == "/healthz":
            self.serve_healthz()
            return
        if path.startswith("/api/"):
            self.proxy_api()
            return
        self.serve_static_or_spa(head_only=False)

    def do_HEAD(self) -> None:
        path = request_path(self.path)
        if path == "/healthz":
            self.serve_healthz(write_body=False)
            return
        if path.startswith("/api/"):
            self.proxy_api()
            return
        self.serve_static_or_spa(head_only=True)

    def do_POST(self) -> None:
        if self.path.startswith("/api/"):
            self.proxy_api()
            return
        self.send_error(404, "Not found")

    def serve_static_or_spa(self, *, head_only: bool) -> None:
        path = request_path(self.path)
        if not is_safe_static_path(path):
            self.send_error(404, "Not found")
            return
        requested = ROOT / decoded_request_path(path).lstrip("/")
        if should_fallback_to_spa(path) and not requested.exists():
            self.path = "/index.html"
        if head_only:
            super().do_HEAD()
        else:
            super().do_GET()

    def serve_healthz(self, *, write_body: bool = True) -> None:
        """Healthcheck that verifies backend reachability."""
        target = f"{BACKEND_URL}/api/health"
        request = Request(target, headers={"Accept": "application/json"})
        try:
            with urlopen(request, timeout=3) as response:
                ok = 200 <= response.status < 300
        except Exception:
            ok = False
        body = b"ok\n" if ok else b"backend unreachable\n"
        self.send_response(200 if ok else 503)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if write_body:
            self.wfile.write(body)

    def _maybe_cors(self) -> None:
        origin = self.headers.get("Origin", "")
        allowed = os.getenv("DASHBOARD_CORS_ORIGIN", "")
        if allowed and origin == allowed:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")

    def proxy_api(self) -> None:
        target = f"{BACKEND_URL}{self.path}"
        headers = {"Accept": "application/json"}
        body = None
        method = self.command.upper()
        if self.command.upper() == "POST":
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length > 0 else b""
            content_type = self.headers.get("Content-Type")
            if content_type:
                headers["Content-Type"] = content_type
        request = Request(target, data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=30) as response:
                body = response.read()
                self.send_response(response.status)
                self.send_header("Content-Type", response.headers.get("Content-Type", "application/json"))
                content_length = response.headers.get("Content-Length") if method == "HEAD" else str(len(body))
                self.send_header("Content-Length", content_length or str(len(body)))
                self._maybe_cors()
                self.end_headers()
                if method != "HEAD":
                    self.wfile.write(body)
        except HTTPError as exc:
            body = exc.read()
            self.send_response(exc.code)
            self.send_header("Content-Type", exc.headers.get("Content-Type", "application/json"))
            content_length = exc.headers.get("Content-Length") if method == "HEAD" else str(len(body))
            self.send_header("Content-Length", content_length or str(len(body)))
            self._maybe_cors()
            self.end_headers()
            if method != "HEAD":
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
