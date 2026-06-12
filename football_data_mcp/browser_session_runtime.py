from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def session_status_path(provider: str, *, explicit_path: str | None = None) -> Path:
    if explicit_path:
        return Path(explicit_path)
    provider = str(provider or "").strip().lower()
    env_name = f"{provider.upper()}_BROWSER_SESSION_STATUS_PATH" if provider else ""
    configured = os.getenv(env_name, "").strip() if env_name else ""
    if configured:
        return Path(configured)
    shared = os.getenv("FOOTBALL_DATA_BROWSER_SESSION_STATUS_PATH", "").strip()
    if shared:
        return Path(shared)
    suffix = provider or "shared"
    return Path(f"/tmp/football-data-{suffix}-browser-session.json")


def load_status(*, path: str | Path | None = None) -> dict[str, Any]:
    target = Path(path) if path else session_status_path("")
    try:
        raw = target.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {"providers": {}}
    except OSError:
        return {"providers": {}}
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {"providers": {}}
    return payload if isinstance(payload, dict) else {"providers": {}}


def provider_status(provider: str, *, path: str | Path | None = None) -> dict[str, Any]:
    provider_key = str(provider or "").strip().lower()
    target = Path(path) if path else session_status_path(provider_key)
    payload = load_status(path=target)
    providers = payload.get("providers")
    if not isinstance(providers, dict):
        return {}
    entry = providers.get(provider_key)
    return dict(entry) if isinstance(entry, dict) else {}


def record_provider_status(
    provider: str,
    status: str,
    *,
    path: str | Path | None = None,
    **fields: Any,
) -> dict[str, Any]:
    provider_key = str(provider or "").strip().lower()
    target = Path(path) if path else session_status_path(provider_key)
    payload = load_status(path=target)
    providers = payload.get("providers")
    if not isinstance(providers, dict):
        providers = {}
    previous_raw = providers.get(provider_key)
    previous: dict[str, Any] = dict(previous_raw) if isinstance(previous_raw, dict) else {}
    now = _utc_now()
    merged: dict[str, Any] = {
        **previous,
        "provider": provider_key,
        "status": str(status or "").strip() or "unknown",
        "updated_at_utc": now,
        **fields,
    }
    if merged["status"] == "ready":
        merged["last_ready_at_utc"] = now
    providers[provider_key] = merged
    payload["providers"] = providers
    payload["updated_at_utc"] = now

    target.parent.mkdir(parents=True, exist_ok=True)
    temp_path = target.with_suffix(f"{target.suffix}.tmp")
    temp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temp_path.replace(target)
    return merged
