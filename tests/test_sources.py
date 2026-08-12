"""Public Hub contract tests for LOGOS data sources.

These paths intentionally include the Hub's mounted ``/ai-market/v2`` prefix.
A missing prefix returns the marketing site or a 404 in production and makes real
telemetry look unavailable, so the exact URLs are part of the integration contract.
"""

from __future__ import annotations

import pytest

from logos.sources.consumption import ConsumptionSource
from logos.sources.hub import HubSource


class _Response:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.headers = {"content-type": "application/json"}

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if not 200 <= self.status_code < 300:
            raise RuntimeError(f"HTTP {self.status_code}")


class _HubClient:
    urls: list[str] = []

    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args) -> None:
        return None

    async def get(self, url: str) -> _Response:
        self.urls.append(url)
        if url.endswith("/ai-market/v2/federation/peers"):
            return _Response({"peers": [{"url": "https://peer.example", "name": "peer", "healthy": True}]})
        if url.endswith("/ai-market/v2/manifest"):
            return _Response({"total_capabilities": 4, "local_capabilities": 1, "federated_capabilities": 3})
        return _Response({}, 404)


class _ConsumptionClient:
    urls: list[str] = []

    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args) -> None:
        return None

    async def get(self, url: str) -> _Response:
        self.urls.append(url)
        if url.endswith("/ai-market/v2/stats/live"):
            return _Response({"summary": {
                "invocations_24h": 7,
                "settled_only_volume_usd": 10.0,
                "settled_volume_24h_usd": 2.5,
                "open_channels": 2,
            }})
        if url.endswith("/ai-market/v2/manifest"):
            return _Response({"tools": [
                {"price_per_call_usd": 0.0, "provider_hub": "local"},
                {"price_per_call_usd": 0.2, "routed_price_usd": 0.202, "source_hub": "https://peer.example"},
            ]})
        return _Response({}, 404)


@pytest.mark.asyncio
async def test_hub_source_uses_public_v2_federation_route(monkeypatch) -> None:
    _HubClient.urls = []
    monkeypatch.setattr("logos.sources.hub.httpx.AsyncClient", _HubClient)

    snapshot = await HubSource("https://modelmarket.dev").fetch_snapshot()

    assert "https://modelmarket.dev/ai-market/v2/federation/peers" in _HubClient.urls
    assert snapshot["status"] == "ok"
    assert snapshot["total_hubs"] == 2
    assert snapshot["total_capabilities"] == 4


@pytest.mark.asyncio
async def test_consumption_uses_public_v2_stats_and_measured_volume(monkeypatch) -> None:
    _ConsumptionClient.urls = []
    monkeypatch.setattr("logos.sources.consumption.httpx.AsyncClient", _ConsumptionClient)

    digest = await ConsumptionSource("https://modelmarket.dev").fetch()

    assert "https://modelmarket.dev/ai-market/v2/stats/live" in _ConsumptionClient.urls
    assert digest["status"] == "ok"
    assert digest["invocations_24h"] == 7
    assert digest["settled_volume_usd"] == 10.0
    assert digest["volume_24h_usd"] == 2.5
    assert digest["estimated_monthly_spend_usd"] == 75.0
    assert digest["spend_basis"] == "measured_24h_settlement_volume"
    assert digest["by_hub"] == [
        {"url": "local", "capabilities": 1, "paid_capabilities": 0, "max_price": 0.0},
        {"url": "https://peer.example", "capabilities": 1, "paid_capabilities": 1, "max_price": 0.202},
    ]


def test_cumulative_settlement_is_never_used_as_a_daily_projection() -> None:
    digest = ConsumptionSource("https://modelmarket.dev")._build(
        {"summary": {
            "invocations_24h": 0,
            "settled_only_volume_usd": 0.04,
            "open_channels": 0,
        }},
        {"tools": []},
        stats_available=True,
        manifest_available=True,
    )

    assert digest["invocations_24h"] == 0
    assert digest["settled_volume_usd"] == 0.04
    assert digest["volume_24h_usd"] is None
    assert digest["estimated_daily_spend_usd"] is None
    assert digest["estimated_monthly_spend_usd"] is None
    assert digest["spend_basis"] == "unavailable"
