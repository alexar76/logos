"""ARGUS Warden decisions source."""

from __future__ import annotations

import httpx


class ArgusSource:
    """Reads ARGUS Warden firewall decisions — blocked/allowed, threat feed hits."""

    def __init__(self, url: str | None, timeout_s: float = 15) -> None:
        self._url = url.rstrip("/") if url else None
        self._timeout = timeout_s

    async def fetch(self) -> dict:
        if not self._url:
            return {"status": "no_data"}

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as c:
                h_r = await c.get(f"{self._url}/health")
                h_r.raise_for_status()
                health = h_r.json()

                # Try to get Warden stats if available
                stats = {}
                try:
                    s_r = await c.get(f"{self._url}/stats")
                    if s_r.status_code == 200:
                        stats = s_r.json()
                except Exception:
                    pass
        except Exception:
            return {"status": "unreachable"}

        return {
            "status": "ok",
            "hub_url": self._url,
            "active_agents": stats.get("active_agents", 0) or health.get("agents_connected", 0),
            "gates_passed": stats.get("gates_passed", 0),
            "gates_blocked": stats.get("gates_blocked", 0),
            "threat_feed_hits": stats.get("threat_feed_hits", 0),
            "sandbox_rejections": stats.get("sandbox_rejections", 0),
            "mode": health.get("mode", "unknown"),
        }
