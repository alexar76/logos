"""aimarket-bridges source — framework-native tools with signed receipts."""

from __future__ import annotations

import httpx


class BridgesSource:
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

        counters = health.get("counters", {})
        return {
            "status": "ok",
            "tools_exported": counters.get("tools_exported", 0),
            "paid_invokes": counters.get("paid_invokes", 0),
            "receipts_issued": counters.get("receipts_issued", 0),
            "receipts_verified": counters.get("receipts_verified", 0),
            "budget_rejections": counters.get("budget_rejections", 0),
            "spend_usd": health.get("spend_usd"),
            "settlement_mode": health.get("settlement_mode", ""),
        }
