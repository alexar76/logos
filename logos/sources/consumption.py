"""Consumption analytics — measured federation activity and catalog prices.

The public Hub API does not expose a per-invocation cost ledger.  LOGOS therefore
projects spend only when the stats endpoint publishes measured 24-hour settlement
volume.  Missing endpoints stay ``None``/``unreachable``; they never become zeroes.
"""

from __future__ import annotations

from typing import Any

import httpx


class ConsumptionSource:
    """Reads measured Hub settlement stats and manifest catalog prices."""

    def __init__(self, hub_url: str, timeout_s: float = 15) -> None:
        self._url = hub_url.rstrip("/")
        self._timeout = timeout_s

    async def fetch(self) -> dict[str, Any]:
        """Return a consumption digest. Never raises."""
        stats, stats_available, manifest, manifest_available = await self._fetch_all()
        return self._build(stats, manifest, stats_available, manifest_available)

    # ── internal ──────────────────────────────────────────────────────

    async def _fetch_all(self) -> tuple[dict, bool, dict, bool]:
        stats: dict = {}
        manifest: dict = {}
        stats_available = False
        manifest_available = False
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as c:
                sr, ss = await self._get(c, f"{self._url}/ai-market/v2/stats/live")
                mr, ms = await self._get(c, f"{self._url}/ai-market/v2/manifest")
                stats_available = 200 <= ss < 300 and isinstance(sr, dict)
                manifest_available = 200 <= ms < 300 and isinstance(mr, dict)
                stats = sr if stats_available else {}
                manifest = mr if manifest_available else {}
        except Exception:
            pass
        return stats, stats_available, manifest, manifest_available

    def _build(
        self,
        stats: dict,
        manifest: dict,
        stats_available: bool | None = None,
        manifest_available: bool | None = None,
    ) -> dict:
        # Optional flags preserve compatibility for direct callers while the fetch
        # path uses HTTP status, not payload truthiness, as the availability signal.
        if stats_available is None:
            stats_available = bool(stats)
        if manifest_available is None:
            manifest_available = bool(manifest)

        def optional_number(source: dict, key: str, cast):
            if key not in source:
                return None
            try:
                return cast(source[key])
            except (TypeError, ValueError):
                return None

        # ── aggregate numbers ──────────────────────────────────────
        # Hub v2 publishes measured counters inside ``summary``.  Older
        # deployments used a flat payload, so accept both shapes without ever
        # treating a missing field as zero.
        summary = stats.get("summary") if stats_available and isinstance(stats.get("summary"), dict) else stats

        def first_number(source: dict, keys: tuple[str, ...], cast):
            for key in keys:
                if key in source:
                    return optional_number(source, key, cast)
            return None

        invocations_24h = first_number(summary, ("invocations_24h", "total_invocations_24h"), int) if stats_available else None
        channels = first_number(summary, ("open_channels", "active_channels"), int) if stats_available else None
        settled_volume = first_number(summary, ("settled_only_volume_usd", "settled_volume_usd"), float) if stats_available else None

        # A cumulative settlement counter is not a 24-hour spend window.  Only
        # explicitly windowed fields can drive daily/monthly projections.
        volume_24h = first_number(
            summary,
            ("settled_volume_24h_usd", "volume_24h_usd", "total_volume_24h_usd"),
            float,
        ) if stats_available else None

        # ── per-capability pricing ─────────────────────────────────
        raw_tools = manifest.get("tools") if manifest_available else None
        tools = raw_tools if isinstance(raw_tools, list) else []
        catalog_available = manifest_available and isinstance(raw_tools, list)
        by_hub: dict[str, dict] = {}
        total_caps = 0
        paid_caps = 0
        free_caps = 0
        max_price = 0.0

        for t in tools:
            total_caps += 1
            # ``routed_price_usd`` is the effective catalog offer to this Hub;
            # fall back to the upstream base price on older manifests.
            raw_price = t.get("routed_price_usd")
            if raw_price is None:
                raw_price = t.get("price_per_call_usd")
            try:
                price = float(raw_price) if raw_price is not None else 0.0
            except (TypeError, ValueError):
                price = 0.0
            if price > 0:
                paid_caps += 1
                if price > max_price:
                    max_price = price
            else:
                free_caps += 1

            hub = t.get("source_hub") or t.get("provider_hub") or "local"
            if hub not in by_hub:
                by_hub[hub] = {"caps": 0, "paid": 0, "max_price": 0.0}
            by_hub[hub]["caps"] += 1
            if price > 0:
                by_hub[hub]["paid"] += 1
                if price > by_hub[hub]["max_price"]:
                    by_hub[hub]["max_price"] = price

        # ── estimated daily spend ───────────────────────────────────
        # A projection is valid only from measured 24h settlement volume.
        # Average catalog price × invocation count is not spend telemetry.
        has_measured_volume = volume_24h is not None
        projected_daily = volume_24h if has_measured_volume else None
        projected_monthly = volume_24h * 30 if has_measured_volume else None

        # ── per-hub breakdown ───────────────────────────────────────
        hubs_list = []
        for url, h in sorted(by_hub.items(), key=lambda x: x[1]["caps"], reverse=True):
            hubs_list.append({
                "url": url,
                "capabilities": h["caps"],
                "paid_capabilities": h["paid"],
                "max_price": round(h["max_price"], 4),
            })

        return {
            "status": "ok" if stats_available and catalog_available else "partial" if stats_available or catalog_available else "unreachable",
            "stats_available": stats_available,
            "catalog_available": catalog_available,
            "invocations_24h": invocations_24h,
            "settled_volume_usd": round(settled_volume, 4) if settled_volume is not None else None,
            "volume_24h_usd": round(volume_24h, 4) if volume_24h is not None else None,
            "active_channels": channels,
            "total_capabilities": total_caps if catalog_available else None,
            "paid_capabilities": paid_caps if catalog_available else None,
            "free_capabilities": free_caps if catalog_available else None,
            "max_price_per_call": round(max_price, 4) if catalog_available else None,
            "estimated_daily_spend_usd": round(projected_daily, 2) if projected_daily is not None else None,
            "estimated_monthly_spend_usd": round(projected_monthly, 2) if projected_monthly is not None else None,
            "spend_basis": "measured_24h_settlement_volume" if has_measured_volume else "unavailable",
            "by_hub": hubs_list,
            "source": "hub manifest + stats",
            "source_key": "hub_manifest_stats",
            "note": "30-day projection from measured 24h settlement volume." if has_measured_volume else "Projection unavailable: the hub did not publish a 24-hour settlement window.",
        }

    @staticmethod
    async def _get(client: httpx.AsyncClient, url: str) -> tuple[Any, int]:
        r = await client.get(url)
        try:
            return r.json(), r.status_code
        except Exception:
            return {}, r.status_code
