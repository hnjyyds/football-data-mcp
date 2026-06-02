from __future__ import annotations

from datetime import datetime, timezone
from importlib import metadata


class ProjectService:
    def overview(self, *, controllers: list[str]) -> dict[str, object]:
        """Expose architecture metadata so the frontend can verify API shape."""
        try:
            version = metadata.version("football-data-mcp")
        except metadata.PackageNotFoundError:
            version = "0.1.0"
        return {
            "status": "ok",
            "name": "football-data-mcp",
            "version": version,
            "architecture": [
                {"name": "api", "responsibility": "HTTP request parsing, response schemas, and controller wiring"},
                {"name": "service", "responsibility": "Business orchestration, authorization rules, and process flow"},
                {"name": "repository", "responsibility": "Database and external-source access"},
                {"name": "core", "responsibility": "Shared errors, configuration, logging, and infrastructure contracts"},
            ],
            "controllers": controllers,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        }
