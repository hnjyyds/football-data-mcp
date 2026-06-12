from __future__ import annotations

from typing import Any

from football_data_mcp import data_sources_registry
from football_data_mcp import betexplorer_source
from football_data_mcp import learning_store
from football_data_mcp import oddsportal_source
from football_data_mcp import snapshot_store


class DataSourceRepository:
    """Gateway for fixture and source-health reads."""

    async def fetch_fdo_matches(self, *, date_from: str | None, date_to: str | None) -> dict[str, Any]:
        return await data_sources_registry.fetch_all_upcoming_matches(date_from=date_from, date_to=date_to)

    async def probe_all_sources(self) -> dict[str, Any]:
        return await data_sources_registry.probe_all_sources()

    def odds_source_status(self, *, db_path: str | None = None) -> dict[str, Any]:
        return {
            "snapshot_summary": snapshot_store.market_snapshot_summary(db_path=db_path),
            "provider_counts": snapshot_store.provider_snapshot_counts(db_path=db_path),
            "sync_state": snapshot_store.odds_source_sync_summary(db_path=db_path),
        }

    def mark_oddsportal_sync_queued(
        self,
        *,
        event_urls: list[str],
        markets: list[str],
        job_id: str,
        db_path: str | None = None,
    ) -> None:
        for event_url in event_urls:
            snapshot_store.upsert_odds_source_sync_state(
                source=oddsportal_source.ODDSPORTAL_PROVIDER,
                scope_key="manual_event_url",
                external_id=event_url,
                status="queued",
                cursor={"markets": markets, "job_id": job_id},
                db_path=db_path,
            )

    def retryable_oddsportal_event_urls(
        self,
        *,
        statuses: list[str],
        limit: int,
        db_path: str | None = None,
    ) -> list[str]:
        """Return failed/empty OddsPortal event URLs that can be resumed."""
        allowed_statuses = {str(status).strip() for status in statuses if str(status).strip()}
        rows = snapshot_store.list_odds_source_sync_state(
            source=oddsportal_source.ODDSPORTAL_PROVIDER,
            db_path=db_path,
            limit=max(1, min(int(limit or 20) * 5, 1000)),
        )
        urls: list[str] = []
        seen: set[str] = set()
        for row in rows:
            if allowed_statuses and str(row.get("status") or "") not in allowed_statuses:
                continue
            event_url = str(row.get("external_id") or "").strip()
            if not event_url or event_url in seen:
                continue
            seen.add(event_url)
            urls.append(event_url)
            if len(urls) >= max(1, min(int(limit or 20), 20)):
                break
        return urls

    def open_prediction_odds_targets(
        self,
        *,
        limit: int,
        db_path: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return open prediction records that need independent odds snapshots."""
        bounded_limit = max(1, min(int(limit or 50), 500))
        records: list[dict[str, Any]] = []
        records.extend(learning_store.list_recommendation_records(db_path=db_path, status="open", limit=bounded_limit))
        records.extend(learning_store.list_shadow_prediction_records(db_path=db_path, status="open", limit=bounded_limit))
        targets: list[dict[str, Any]] = []
        seen: set[str] = set()
        for record in records:
            home = str(record.get("home_team") or "").strip()
            away = str(record.get("away_team") or "").strip()
            if not home or not away:
                continue
            identity = "|".join(
                [
                    home.lower(),
                    away.lower(),
                    str(record.get("kickoff_utc") or record.get("kickoff_utc_plus_8") or "").lower(),
                ]
            )
            if identity in seen:
                continue
            seen.add(identity)
            targets.append(
                {
                    "record_id": record.get("id"),
                    "match_id": record.get("match_id") or "",
                    "league": record.get("league") or "",
                    "home_team": home,
                    "away_team": away,
                    "kickoff_utc": record.get("kickoff_utc") or "",
                    "kickoff_utc_plus_8": record.get("kickoff_utc_plus_8") or "",
                    "market": record.get("market") or "",
                    "settlement_status": record.get("settlement_status") or "",
                }
            )
            if len(targets) >= bounded_limit:
                break
        return targets

    def recent_analysis_odds_targets(
        self,
        *,
        limit: int,
        db_path: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return recent analysis-derived events that can seed independent odds discovery.

        这些目标不是生产赔率源本身，而是“去哪补采”的线索：当 open 台账为空、
        雷速又过期时，系统仍可以用最近分析过的比赛去匹配独立赔率源。
        """
        bounded_limit = max(1, min(int(limit or 50), 500))
        summary = snapshot_store.market_snapshot_summary(db_path=db_path, latest_event_limit=bounded_limit)
        targets: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in summary.get("latest_events") or []:
            if str(item.get("provider") or "") != "analysis_odds":
                continue
            home = str(item.get("home_team") or "").strip()
            away = str(item.get("away_team") or "").strip()
            kickoff = str(item.get("kickoff_utc") or "").strip()
            if not home or not away:
                continue
            identity = "|".join([home.lower(), away.lower(), kickoff.lower()])
            if identity in seen:
                continue
            seen.add(identity)
            targets.append(
                {
                    "target_source": "analysis_odds",
                    "match_id": item.get("event_id") or "",
                    "source_key": item.get("source_key") or "",
                    "league": item.get("league") or "",
                    "home_team": home,
                    "away_team": away,
                    "kickoff_utc": kickoff,
                    "latest_fetched_at_utc": item.get("latest_fetched_at_utc") or "",
                    "snapshot_count": item.get("snapshot_count") or 0,
                    "bookmaker_count": item.get("bookmaker_count") or 0,
                }
            )
            if len(targets) >= bounded_limit:
                break
        return targets

    async def discover_oddsportal_event_urls(
        self,
        *,
        targets: list[dict[str, Any]],
        discovery_urls: list[str],
        limit: int,
    ) -> dict[str, Any]:
        return await oddsportal_source.discover_oddsportal_event_urls(
            targets=targets,
            discovery_urls=discovery_urls,
            limit=limit,
        )

    async def discover_betexplorer_event_urls(
        self,
        *,
        targets: list[dict[str, Any]],
        discovery_urls: list[str],
        limit: int,
    ) -> dict[str, Any]:
        return await betexplorer_source.discover_betexplorer_event_urls(
            targets=targets,
            discovery_urls=discovery_urls,
            limit=limit,
        )

    async def sync_oddsportal_odds_snapshots(
        self,
        *,
        event_urls: list[str],
        markets: list[str],
        limit: int,
        force: bool,
        job_id: str,
    ) -> dict[str, Any]:
        from football_data_mcp import sources

        return await sources.sync_oddsportal_odds_snapshots(
            event_urls=event_urls,
            markets=markets,
            limit=limit,
            force=force,
            job_id=job_id,
        )

    async def sync_betexplorer_odds_snapshots(
        self,
        *,
        event_urls: list[str],
        markets: list[str],
        limit: int,
        force: bool,
        job_id: str,
        target_map: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        from football_data_mcp import sources

        return await sources.sync_betexplorer_odds_snapshots(
            event_urls=event_urls,
            markets=markets,
            limit=limit,
            force=force,
            job_id=job_id,
            target_map=target_map,
        )
