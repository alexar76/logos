"""SKOPOS remediation source."""

from __future__ import annotations

import httpx


class SkoposSource:
    def __init__(self, url: str | None, timeout_s: float = 15) -> None:
        self._url = url.rstrip("/") if url else None
        self._timeout = timeout_s

    async def fetch_remediation(self) -> dict:
        if not self._url:
            return {"status": "no_data", "total_jobs": 0}

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as c:
                r = await c.get(f"{self._url}/api/remediation/stats")
                r.raise_for_status()
                data = r.json()
        except httpx.HTTPStatusError as exc:
            # A 404 here used to read as "unreachable", which is how a missing route
            # stayed invisible: SKOPOS was up and answering, just not on this path.
            return {"status": "error", "http_status": exc.response.status_code,
                    "detail": f"SKOPOS returned {exc.response.status_code} for "
                              f"/api/remediation/stats", "total_jobs": 0}
        except Exception:
            return {"status": "unreachable", "total_jobs": 0}

        return {
            "status": "ok",
            "hub_url": self._url,
            "total_jobs": data.get("total", 0),
            "closed": data.get("closed", 0),
            "confirmed_fixed": data.get("confirmed_fixed", 0),
            "escalated": data.get("escalated", 0),
            "orders_signed": data.get("orders_signed", 0),
        }


class TreasurySource:
    def __init__(self, url: str | None, timeout_s: float = 15) -> None:
        self._url = url.rstrip("/") if url else None
        self._timeout = timeout_s

    async def fetch_balance(self) -> dict:
        if not self._url:
            return {"status": "no_data"}

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as c:
                h_r = await c.get(f"{self._url}/health")
                h_r.raise_for_status()
                health = h_r.json()

                v_r = await c.get(f"{self._url}/vault")
                v_r.raise_for_status()
                vault = v_r.json()

                l_r = await c.get(f"{self._url}/ledger?limit=50")
                l_r.raise_for_status()
                ledger_data = l_r.json()
        except Exception:
            return {"status": "unreachable"}

        # 24h payout volume from ledger
        payouts_24h = 0
        volume_24h = 0.0
        entries = ledger_data.get("entries") or []
        for e in entries:
            if e.get("kind") == "release":
                payouts_24h += 1
                volume_24h += float(e.get("amount_usd", 0))

        # depletion projection
        depletion = None
        available = vault.get("available_usd")
        if available and volume_24h > 0:
            daily_rate = volume_24h
            depletion = round(available / daily_rate, 1) if daily_rate > 0 else None

        return {
            "status": "ok",
            "hub_url": self._url,
            "balance_usd": vault.get("balance_usd"),
            "reserved_usd": vault.get("reserved_usd"),
            "available_usd": vault.get("available_usd"),
            "payouts_24h": payouts_24h,
            "payout_volume_24h_usd": round(volume_24h, 2),
            "projected_depletion_days": depletion,
            "settlement_mode": vault.get("settlement_mode", ""),
        }
