from __future__ import annotations

import argparse
from collections.abc import Mapping
import json
import os
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
import time
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

from football_data_mcp import sources


HOST = os.getenv("LEISU_BROWSER_PROXY_HOST", "127.0.0.1")
PORT = int(os.getenv("LEISU_BROWSER_PROXY_PORT", "8918"))
DEFAULT_PROFILE_DIR = Path(os.getenv("LEISU_BROWSER_PROFILE_DIR", ".leisu-browser-profile"))
TIMEOUT_MS = int(float(os.getenv("LEISU_BROWSER_PROXY_TIMEOUT_SECONDS", "15")) * 1000)
DETAIL_COMPANY_LIMIT = int(os.getenv("LEISU_BROWSER_PROXY_DETAIL_COMPANY_LIMIT", "3"))
AUTH_COOLDOWN_SECONDS = float(os.getenv("LEISU_BROWSER_PROXY_AUTH_COOLDOWN_SECONDS", "90"))


class UpstreamAccessError(RuntimeError):
    def __init__(self, *, status_code: int, payload: Mapping[str, Any]) -> None:
        super().__init__(str(payload.get("message") or payload.get("error") or "Leisu upstream access failed"))
        self.status_code = status_code
        self.payload = dict(payload)


class LeisuBrowserSession:
    def __init__(self, *, profile_dir: Path, headless: bool = False, connect_cdp: str = "") -> None:
        self.profile_dir = profile_dir
        self.headless = headless
        self.connect_cdp = connect_cdp
        self._playwright: Any = None
        self._browser: Any = None
        self._context: Any = None
        self._page: Any = None
        self._auth_pending_until = 0.0
        self._auth_pending_payload: dict[str, Any] | None = None

    def start(self) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise SystemExit(
                "缺少 Playwright。请先执行：uv pip install playwright && uv run python -m playwright install chromium"
            ) from exc

        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self._playwright = sync_playwright().start()
        if self.connect_cdp:
            self._browser = self._playwright.chromium.connect_over_cdp(self.connect_cdp)
            self._context = self._browser.contexts[0] if self._browser.contexts else self._browser.new_context()
        else:
            self._context = self._playwright.chromium.launch_persistent_context(
                str(self.profile_dir),
                headless=self.headless,
                viewport={"width": 430, "height": 932},
                user_agent=sources.LEISU_MOBILE_HEADERS["User-Agent"],
                locale="zh-CN",
                timezone_id="Asia/Shanghai",
            )
        self._page = self._context.pages[0] if self._context.pages else self._context.new_page()
        self._page.goto(sources.LEISU_MOBILE_WEBSITE_URL, wait_until="domcontentloaded", timeout=TIMEOUT_MS)

    def close(self) -> None:
        if self._context is not None and not self.connect_cdp:
            self._context.close()
        if self._browser is not None:
            self._browser.close()
        if self._playwright is not None:
            self._playwright.stop()

    def open_verification_page(self, match_id: str) -> str:
        verification_url = f"{sources.LEISU_MOBILE_WEBSITE_URL}/live/odds-{match_id}"
        self._page.goto(verification_url, wait_until="domcontentloaded", timeout=TIMEOUT_MS)
        self._page.bring_to_front()
        return verification_url

    def _cache_auth_pending(self, payload: dict[str, Any]) -> None:
        self._auth_pending_until = time.time() + AUTH_COOLDOWN_SECONDS
        self._auth_pending_payload = payload

    def _auth_pending_response(self) -> dict[str, Any] | None:
        if self._auth_pending_payload and time.time() < self._auth_pending_until:
            retry_after = max(1, int(self._auth_pending_until - time.time()))
            return {**self._auth_pending_payload, "retry_after_seconds": retry_after}
        self._auth_pending_until = 0.0
        self._auth_pending_payload = None
        return None

    def _ensure_leisu_page(self, referer: str) -> None:
        current_url = str(getattr(self._page, "url", "") or "")
        current_path = urlparse(current_url).path
        referer_path = urlparse(referer).path
        if not current_url.startswith(sources.LEISU_MOBILE_WEBSITE_URL) or current_path != referer_path:
            self._page.goto(referer, wait_until="domcontentloaded", timeout=TIMEOUT_MS)
            self._page.wait_for_timeout(500)

    def _request_json(self, path: str, params: dict[str, Any], *, referer: str) -> tuple[Any, str]:
        url = f"{sources.LEISU_MOBILE_API_BASE_URL}{path}"
        signed_params = sources.leisu_mobile_api_signed_params(path, params)
        fetch_url = f"{url}?{urlencode(signed_params)}"
        self._ensure_leisu_page(referer)
        result = self._page.evaluate(
            """
            async ({ url, referer }) => {
                const response = await fetch(url, {
                    method: "GET",
                    credentials: "include",
                    referrer: referer,
                    referrerPolicy: "strict-origin-when-cross-origin",
                    headers: { "Accept": "application/json,text/plain,*/*" },
                });
                return {
                    status: response.status,
                    url: response.url,
                    text: await response.text(),
                };
            }
            """,
            {"url": fetch_url, "referer": referer},
        )
        response_status = int(result.get("status") or 0)
        response_url = str(result.get("url") or fetch_url)
        text = str(result.get("text") or "")
        access = sources.leisu_odds_access_status(text)
        if response_status in (401, 403):
            raise UpstreamAccessError(
                status_code=428,
                payload={
                    "status": "forbidden",
                    "access": {
                        "status": "forbidden",
                        "blocked": True,
                        "requires_cookie_or_proxy": True,
                        "reason": f"http_{response_status}_session_invalid",
                    },
                    "message": "雷速浏览器会话已失效，请在打开的窗口中重新完成人工验证。",
                },
            )
        if access.get("blocked"):
            raise UpstreamAccessError(
                status_code=428 if access.get("status") == "interactive_captcha" else 502,
                payload={
                    "status": access.get("status") or "blocked",
                    "access": access,
                    "message": "请在打开的雷速浏览器窗口中完成人工滑块验证，然后重试该请求。",
                },
            )
        if response_status >= 400:
            raise UpstreamAccessError(
                status_code=502,
                payload={
                    "status": "upstream_error",
                    "error": f"http_{response_status}",
                    "body_snippet": text[:500],
                },
            )
        try:
            raw_payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise UpstreamAccessError(
                status_code=502,
                payload={"status": "json_decode_error", "error": f"{type(exc).__name__}: {exc}", "body_snippet": text[:500]},
            ) from exc
        return sources.decode_leisu_mobile_api_response(raw_payload), response_url

    def fetch_odds(self, match_id: str) -> dict[str, Any]:
        match_id = str(match_id or "").strip()
        if not match_id:
            raise UpstreamAccessError(status_code=400, payload={"status": "missing_match_id"})
        pending = self._auth_pending_response()
        if pending:
            raise UpstreamAccessError(status_code=428, payload=pending)

        referer = f"{sources.LEISU_MOBILE_WEBSITE_URL}/live/odds-{match_id}"
        try:
            list_payload, source_url = self._request_json(
                sources.LEISU_MOBILE_ODDS_LIST_PATH,
                {"sport_id": 1, "match_id": match_id},
                referer=referer,
            )
        except UpstreamAccessError as exc:
            if (exc.payload.get("access") or {}).get("blocked"):
                exc.payload["verification_url"] = self.open_verification_page(match_id)
                exc.payload["message"] = (
                    "请在已打开的雷速浏览器窗口中完成人工滑块验证；"
                    "验证完成后等待几十秒或手动重试该代理地址。"
                )
                self._cache_auth_pending(exc.payload)
            raise

        if not isinstance(list_payload, dict):
            raise UpstreamAccessError(
                status_code=502,
                payload={"status": "unexpected_payload", "payload_type": type(list_payload).__name__},
            )

        detail_payloads: dict[str, dict[Any, Any]] = {"asia": {}, "eu": {}, "bs": {}}
        detail_errors: list[dict[str, Any]] = []
        for market_key, handicap in sources.LEISU_MOBILE_MARKET_HANDICAPS.items():
            market_items = [item for item in (list_payload.get(market_key) or []) if isinstance(item, dict)]
            selected_items = market_items if DETAIL_COMPANY_LIMIT <= 0 else market_items[:DETAIL_COMPANY_LIMIT]
            for item in selected_items:
                cid = item.get("cid")
                if cid in (None, ""):
                    continue
                try:
                    detail_payload, _ = self._request_json(
                        sources.LEISU_MOBILE_ODDS_DETAIL_PATH,
                        {"sport_id": 1, "match_id": match_id, "cid": cid, "handicap": handicap},
                        referer=referer,
                    )
                except UpstreamAccessError as exc:
                    detail_errors.append(
                        {
                            "market": market_key,
                            "cid": cid,
                            "status": exc.payload.get("status") or "error",
                            "reason": (exc.payload.get("access") or {}).get("reason", ""),
                        }
                    )
                    continue
                if isinstance(detail_payload, list):
                    detail_payloads[market_key][cid] = detail_payload

        classic_payload = sources.leisu_classic_payload_from_mobile_payload(
            list_payload,
            match_id=match_id,
            detail_payloads=detail_payloads,
        )
        classic_payload["proxy_meta"] = {
            "source_url": source_url,
            "detail_company_limit": DETAIL_COMPANY_LIMIT,
            "detail_error_count": len(detail_errors),
            "detail_errors": detail_errors[:10],
            "verification": "manual_browser_session",
        }
        return classic_payload


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: Mapping[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


def _http_status_for_proxy_payload(exc: UpstreamAccessError) -> int:
    if exc.payload.get("status") in {"interactive_captcha", "forbidden"}:
        return 200
    return exc.status_code


class Handler(BaseHTTPRequestHandler):
    server: "LeisuBrowserProxyServer"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        if path == "/health":
            _json_response(self, 200, {"ok": True, "service": "leisu_browser_proxy"})
            return
        match_id = ""
        if path.startswith("/leisu/odds/"):
            match_id = path.rsplit("/", 1)[-1]
        elif path == "/leisu/odds":
            match_id = (parse_qs(parsed.query).get("match_id") or [""])[0]
        if not match_id:
            _json_response(self, 404, {"status": "not_found"})
            return

        try:
            payload = self.server.browser_session.fetch_odds(match_id)
        except UpstreamAccessError as exc:
            _json_response(self, _http_status_for_proxy_payload(exc), exc.payload)
            return
        except Exception as exc:
            _json_response(self, 500, {"status": "error", "error": f"{type(exc).__name__}: {exc}"})
            return
        _json_response(self, 200, payload)

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"leisu_browser_proxy - {fmt % args}")


class LeisuBrowserProxyServer(HTTPServer):
    browser_session: LeisuBrowserSession


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Leisu manual browser-session proxy")
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", default=PORT, type=int)
    parser.add_argument("--profile-dir", default=str(DEFAULT_PROFILE_DIR))
    parser.add_argument(
        "--connect-cdp",
        default=os.getenv("LEISU_BROWSER_CDP_URL", ""),
        help="连接已用 --remote-debugging-port 启动的真实 Chrome，例如 http://127.0.0.1:9222",
    )
    parser.add_argument("--headless", action="store_true", help="仅用于已授权 profile；首次验证请不要启用")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    browser_session = LeisuBrowserSession(
        profile_dir=Path(args.profile_dir),
        headless=args.headless,
        connect_cdp=args.connect_cdp,
    )
    browser_session.start()
    server = LeisuBrowserProxyServer((args.host, args.port), Handler)
    server.browser_session = browser_session
    print(
        "Leisu browser proxy listening on "
        f"http://{args.host}:{args.port}/leisu/odds/{{match_id}}\n"
        "首次返回 interactive_captcha/forbidden 时，请在弹出的浏览器中手动完成雷速滑块后重试。"
    )
    try:
        server.serve_forever()
    finally:
        browser_session.close()


if __name__ == "__main__":
    main()
