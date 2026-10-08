"""LOGOS publishes a federation surface, so its knock means something.

Every analytics read LOGOS makes against the hub carries the crawler header, which the hub
records as a knock. Publishing nothing made that knock a permanent `fail` — a client
rattling a door it never meant to enter. These pin the three routes a peer must serve, and
that what they serve verifies with the same signer the hub checks it with.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from oracle_core.signing import Signer

from logos.aimarket import SUMMARY_CAPABILITY
from logos.app import create_app
from logos.config import LogosConfig


@pytest.fixture
def peer_client():
    with tempfile.TemporaryDirectory() as td:
        cfg = LogosConfig()
        cfg.data_dir = Path(td)
        cfg.cors_origins = "http://test"
        cfg.hub_url = "http://127.0.0.1:19999"  # unreachable: the surface must not need it
        cfg.public_url = "https://logos.test"
        app = create_app(cfg)
        with TestClient(app) as c:
            yield c


def test_discovery_names_the_manifest_and_the_invoke_route(peer_client):
    wk = peer_client.get("/.well-known/ai-market.json").json()
    assert wk["manifest_url"] == "https://logos.test/ai-market/v2/manifest"
    assert wk["mcp_endpoint"] == "https://logos.test/ai-market/v2/invoke"
    assert wk["signer_public_key"]
    assert wk["capabilities_count"] == 1


def test_the_manifest_verifies_with_the_advertised_key(peer_client):
    key = peer_client.get("/.well-known/ai-market.json").json()["signer_public_key"]
    manifest = peer_client.get("/ai-market/v2/manifest").json()
    assert manifest["tools"][0]["capability_id"] == SUMMARY_CAPABILITY
    assert Signer.verify(
        Signer(key_path="unused").manifest_canonical(manifest),
        manifest["signature"]["value"],
        key,
    ), "a peer's manifest must verify under the key its discovery document advertises"


def test_the_free_capability_is_free_and_signed(peer_client):
    key = peer_client.get("/.well-known/ai-market.json").json()["signer_public_key"]
    r = peer_client.post(
        "/ai-market/v2/invoke",
        json={"capability_id": SUMMARY_CAPABILITY, "product_id": "prod-logos", "input": {}},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["price_usd"] == 0.0
    assert body["output"]["source"] == "logos"
    assert body["output"]["ok"] is True
    receipt = body["receipt"]
    assert Signer.verify(
        Signer.receipt_canonical(receipt), receipt["signature"]["value"], key,
    ), "the receipt must verify under the advertised key, or the hub scores it a foreign signer"


def test_an_unreachable_hub_does_not_break_the_sample(peer_client):
    """The sample reports what LOGOS observed. Observing nothing is zero, not a 500."""
    body = peer_client.post(
        "/ai-market/v2/invoke",
        json={"capability_id": SUMMARY_CAPABILITY, "input": {}},
    ).json()
    assert body["output"]["hubs_seen"] == 0
    assert body["output"]["capabilities_indexed"] == 0


def test_an_unknown_capability_is_a_404(peer_client):
    r = peer_client.post("/ai-market/v2/invoke", json={"capability_id": "nope@v1", "input": {}})
    assert r.status_code == 404


def test_the_summary_does_not_republish_the_peer_list(peer_client):
    """Counts, not somebody else's catalogue signed under our key."""
    body = peer_client.post(
        "/ai-market/v2/invoke",
        json={"capability_id": SUMMARY_CAPABILITY, "input": {}},
    ).json()
    assert "peers" not in body["output"]
    assert "capabilities" not in body["output"]
