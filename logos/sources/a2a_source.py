"""A2A wire observer source — agent-to-agent delegation logs."""

from __future__ import annotations

import httpx


class A2ASource:
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
            "total_envelopes": health.get("total_envelopes", 0),
            "rejected": health.get("rejected", 0),
            "avg_latency_ms": health.get("avg_latency_ms"),
            "peers": health.get("peers", 0),
            "by_skill": health.get("by_skill", {}),
        }
