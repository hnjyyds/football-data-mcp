from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from typing import Any

from football_data_mcp import browser_session_runtime
from football_data_mcp import sources


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def crawlee_runtime_support() -> dict[str, Any]:
    crawlee_installed = _module_available("crawlee")
    playwright_installed = _module_available("playwright")
    supported = crawlee_installed and playwright_installed
    if supported:
        status = "ready"
        message = "Crawlee + Playwright 已安装，可用于浏览器辅助抓取运行时。"
    elif crawlee_installed:
        status = "missing_playwright"
        message = "已安装 Crawlee，但缺少 Playwright。"
    elif playwright_installed:
        status = "missing_crawlee"
        message = "已安装 Playwright，但缺少 Crawlee。"
    else:
        status = "not_installed"
        message = "未安装 Crawlee / Playwright 运行时。"
    return {
        "engine": "crawlee_playwright",
        "status": status,
        "supported": supported,
        "crawlee_installed": crawlee_installed,
        "playwright_installed": playwright_installed,
        "message": message,
    }


def leisu_crawlee_runtime_plan() -> dict[str, Any]:
    support = crawlee_runtime_support()
    profile_dir = os.getenv("LEISU_BROWSER_PROFILE_DIR", ".leisu-browser-profile").strip() or ".leisu-browser-profile"
    proxy_url = os.getenv("LEISU_ODDS_PROXY_URL", "").strip()
    status_url = os.getenv("LEISU_BROWSER_PROXY_STATUS_URL", "").strip()
    if not status_url and "/leisu/odds" in proxy_url:
        status_url = f"{proxy_url.split('/leisu/odds', 1)[0]}/leisu/session"
    return {
        **support,
        "provider": "leisu",
        "profile_dir": str(Path(profile_dir)),
        "recommended_entrypoint": "uv run --extra crawler-runtime python -m scripts.leisu_crawlee_session",
        "browser_proxy_status_url": status_url,
        "browser_proxy_url": proxy_url,
        "uses_persistent_profile": True,
        "notes": [
            "Leisu 应优先使用单会话、持久 profile，而不是多会话随机轮换。",
            "独立爬虫主源恢复后，服务层仍只读取统一 snapshot/health contract。",
        ],
    }


async def bootstrap_leisu_session(
    *,
    match_id: str = "",
    url: str = "",
    profile_dir: str | None = None,
    headless: bool = False,
) -> dict[str, Any]:
    support = leisu_crawlee_runtime_plan()
    resolved_url = str(url or "").strip()
    normalized_match_id = str(match_id or "").strip()
    if not resolved_url:
        resolved_url = (
            f"{sources.LEISU_MOBILE_WEBSITE_URL}/live/odds-{normalized_match_id}"
            if normalized_match_id
            else sources.LEISU_MOBILE_WEBSITE_URL
        )
    resolved_profile_dir = str(Path(profile_dir or support["profile_dir"]).expanduser())
    if not bool(support.get("supported")):
        browser_session_runtime.record_provider_status(
            "leisu",
            "error",
            message=str(support.get("message") or "缺少 Crawlee / Playwright 运行时。"),
            last_error=str(support.get("status") or "runtime_not_ready"),
            mode="crawlee_playwright",
            profile_dir=resolved_profile_dir,
            target_url=resolved_url,
        )
        return {
            "status": "runtime_not_ready",
            "provider": "leisu",
            "engine": "crawlee_playwright",
            "message": str(support.get("message") or "缺少 Crawlee / Playwright 运行时。"),
            "runtime_support": support,
            "target_url": resolved_url,
            "profile_dir": resolved_profile_dir,
        }

    import importlib

    crawlee_module = importlib.import_module("crawlee")
    crawlers_module = importlib.import_module("crawlee.crawlers")
    Request = getattr(crawlee_module, "Request")
    PlaywrightCrawler = getattr(crawlers_module, "PlaywrightCrawler")

    browser_session_runtime.record_provider_status(
        "leisu",
        "starting",
        message="正在通过 Crawlee 启动 Leisu 浏览器会话。",
        profile_dir=resolved_profile_dir,
        mode="crawlee_playwright",
        target_url=resolved_url,
        match_id=normalized_match_id,
    )

    crawler = PlaywrightCrawler(
        headless=bool(headless),
        browser_type="chromium",
        use_session_pool=True,
        max_requests_per_crawl=1,
        max_request_retries=0,
        max_session_rotations=0,
        user_data_dir=resolved_profile_dir,
    )
    result: dict[str, Any] = {
        "status": "unknown",
        "provider": "leisu",
        "engine": "crawlee_playwright",
        "runtime_support": support,
        "target_url": resolved_url,
        "profile_dir": resolved_profile_dir,
        "match_id": normalized_match_id or None,
        "headless": bool(headless),
    }

    @crawler.router.default_handler
    async def handle(context: Any) -> None:
        page = context.page
        await page.goto(resolved_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(1000)
        text = await page.content()
        access = sources.leisu_odds_access_status(text)
        if access.get("blocked"):
            browser_session_runtime.record_provider_status(
                "leisu",
                "auth_required",
                message="Crawlee 会话打开了雷速页面，但仍需手动完成人工验证。",
                profile_dir=resolved_profile_dir,
                mode="crawlee_playwright",
                target_url=resolved_url,
                match_id=normalized_match_id,
                last_verification_url=resolved_url,
                last_error=str(access.get("reason") or access.get("status") or "interactive_captcha"),
            )
            result.update(
                {
                    "status": "auth_required",
                    "message": "需要人工完成雷速验证。",
                    "access": access,
                }
            )
            return
        browser_session_runtime.record_provider_status(
            "leisu",
            "ready",
            message="Crawlee 浏览器会话已就绪，可复用当前 profile。",
            profile_dir=resolved_profile_dir,
            mode="crawlee_playwright",
            target_url=resolved_url,
            match_id=normalized_match_id,
        )
        result.update(
            {
                "status": "ready",
                "message": "Crawlee 浏览器会话已就绪。",
            }
        )

    await crawler.run([Request.from_url(resolved_url)])
    return result
