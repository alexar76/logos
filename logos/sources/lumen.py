"""LUMEN reputation source — EigenTrust/PageRank over the trust graph."""

from __future__ import annotations

import httpx


class LumenSource:
    def __init__(self, url: str | None, timeout_s: float = 15) -> None:
        self._url = url.rstrip("/") if url else None
        self._timeout = timeout_s

    async def fetch(self) -> dict:
        if not self._url:
            return {"status": "no_data"}

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as c:
                r = await c.get(f"{self._url}/health")
                r.raise_for_status()
                health = r.json()
        except Exception:
            return {"status": "unreachable"}

        return {
            "status": "ok",
            "hub_url": self._url,
            "nodes_indexed": health.get("nodes_indexed", 0),
            "edges": health.get("edges", 0),
            "top_trusted": health.get("top_trusted", ""),
            "last_convergence": health.get("last_convergence", ""),
            "active_events_24h": health.get("active_events_24h", 0),
        }
