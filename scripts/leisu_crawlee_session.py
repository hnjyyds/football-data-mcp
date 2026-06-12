from __future__ import annotations

import argparse
import asyncio
import os

from football_data_mcp import crawler_runtime_support


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap a persistent Leisu browser session with Crawlee.")
    parser.add_argument("--match-id", default="", help="Optional Leisu match_id used to open a concrete odds page.")
    parser.add_argument("--url", default="", help="Optional absolute URL; overrides --match-id when provided.")
    parser.add_argument("--profile-dir", default=os.getenv("LEISU_BROWSER_PROFILE_DIR", ".leisu-browser-profile"))
    parser.add_argument("--headless", action="store_true", help="Use headless mode for already-authorized sessions.")
    return parser.parse_args()


async def _run(args: argparse.Namespace) -> int:
    result = await crawler_runtime_support.bootstrap_leisu_session(
        match_id=str(args.match_id or ""),
        url=str(args.url or ""),
        profile_dir=str(args.profile_dir or ""),
        headless=bool(args.headless),
    )
    print(result.get("message") or result.get("status") or "unknown")
    return 0 if result.get("status") in {"ready", "auth_required"} else 2


def main() -> None:
    args = parse_args()
    raise SystemExit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()
