"""Hub federation source — manifest, peers, stats."""

from __future__ import annotations

from typing import Any

import httpx

from logos.models import FederationSnapshot, HubPeer


def _peer_healthy(peer: dict) -> bool:
    """Map Hub peer records to a boolean health flag.

    The Hub publishes ``status`` (``active``, ``key_mismatch``, …) and does not
    emit ``healthy``. LOGOS used to treat only ``status == \"online\"`` as healthy,
    which made every ``active`` peer look dead — 1/7 on a fully live federation.
    """
    if "healthy" in peer:
        return bool(peer["healthy"])
    status = str(peer.get("status") or "active").strip().lower()
    if status in {"online", "active", "ok"}:
        return True
    if status in {"key_mismatch", "offline", "unreachable", "down", "error", "rejected"}:
        return False
    return True


class HubSource:
    """Reads the Hub's public surface. No admin token needed — the manifest,
    peers list, and stats are open endpoints."""

    def __init__(self, hub_url: str, timeout_s: float = 15) -> None:
        self._url = hub_url.rstrip("/")
        self._timeout = timeout_s

    async def fetch_snapshot(self) -> dict:
        """Returns a dict ready to hydrate FederationSnapshot."""
        peers, manifest, peers_available, manifest_available = await self._fetch_peers_and_manifest()
        status = "ok" if peers_available and manifest_available else "partial" if peers_available or manifest_available else "unreachable"
        return {
            "status": status,
            "peers_available": peers_available,
            "manifest_available": manifest_available,
            "generated_at": manifest.get("generated_at") if manifest_available else None,
            # The local Hub is healthy when its peers endpoint answered.  If that
            # endpoint is unavailable the federation size is unknown, not zero.
            "total_hubs": len(peers) + 1 if peers_available else None,
            "healthy_hubs": sum(1 for p in peers if p.healthy) + 1 if peers_available else None,
            "total_capabilities": manifest.get("total_capabilities") if manifest_available else None,
            "local_capabilities": manifest.get("local_capabilities") if manifest_available else None,
            "federated_capabilities": manifest.get("federated_capabilities") if manifest_available else None,
            "peers": [p.model_dump() for p in peers],
            "anomaly_count": None,  # filled by the anomaly detector later
        }

    async def fetch_peers(self) -> list[dict]:
        """Raw peer list — useful for per-hub health checks."""
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as c:
                r = await c.get(f"{self._url}/ai-market/v2/federation/peers")
                r.raise_for_status()
                data = r.json()
                return data.get("peers", [])
        except Exception:
            return []

    # ── internal ──────────────────────────────────────────────────────────────

    async def _fetch_peers_and_manifest(self) -> tuple[list[HubPeer], dict[str, Any], bool, bool]:
        peers_raw: list[dict] = []
        manifest: dict[str, Any] = {}
        peers_available = False
        manifest_available = False
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as c:
                pr, ps = await self._get_json(c, f"{self._url}/ai-market/v2/federation/peers")
                peers_available = 200 <= ps < 300 and isinstance(pr, dict) and isinstance(pr.get("peers", []), list)
                peers_raw = pr.get("peers", []) if peers_available else []
        except Exception:
            pass

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as c:
                manifest, ms = await self._get_json(c, f"{self._url}/ai-market/v2/manifest")
                manifest_available = 200 <= ms < 300 and isinstance(manifest, dict)
                if not manifest_available:
                    manifest = {}
        except Exception:
            pass

        peers: list[HubPeer] = []
        for p in peers_raw:
            peers.append(
                HubPeer(
                    url=p.get("url", ""),
                    name=p.get("name", ""),
                    capabilities_count=p.get("capabilities_count", 0),
                    trust_score=p.get("trust_score", 0.0),
                    last_crawl=p.get("last_crawl", ""),
                    depth=p.get("depth", 0),
                    categories=p.get("categories", []),
                    healthy=_peer_healthy(p),
                    latency_ms=p.get("latency_ms"),
                )
            )
        return peers, manifest, peers_available, manifest_available

    async def _try_get(self, path: str, default: dict) -> dict:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as c:
                r = await c.get(f"{self._url}{path}")
                r.raise_for_status()
                return r.json() if r.headers.get("content-type", "").startswith("application/json") else default
        except Exception:
            return default

    @staticmethod
    async def _get_json(client: httpx.AsyncClient, url: str) -> tuple[Any, int]:
        r = await client.get(url)
        try:
            return r.json(), r.status_code
        except Exception:
            return {}, r.status_code
