"""LOGOS as a federation *peer*, not only a reader of one.

LOGOS crawls the hub for analytics, and every one of those reads carries the crawler
header — which the hub records as a knock. So LOGOS has been sitting in the pending queue
since 2026-08-28 with verdict `fail`, for the honest reason that it published no
`/.well-known/ai-market.json` at all: a client knocking on a door it never meant to enter.

It does have something to sell, though: a federation-wide view nobody else computes. One
free capability makes it a peer on the same terms as everyone else — a working sample,
like GAIA's fleet status, small enough to be evidence and true enough to be worth reading.

The whole v2 surface (discovery, signed manifest, invoke with signed receipts) comes from
`oracle_core.Protocol`. No canonical string is written here on purpose: five
implementations of that formula already exist and two of them had drifted by the time
anybody compared them — see tests/test_protocol_vector_conformance.py.
"""

from __future__ import annotations

import logging
from typing import Any

from oracle_core.protocol import Capability, OracleSpec, Protocol

logger = logging.getLogger(__name__)

SUMMARY_CAPABILITY = "logos.federation.summary@v1"

_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "ok": {"type": "boolean"},
        "hubs_seen": {"type": "integer"},
        "hubs_healthy": {"type": "integer"},
        "capabilities_indexed": {"type": "integer"},
        "open_findings": {"type": "integer"},
        "observed_at": {"type": "string"},
        "source": {"type": "string"},
    },
    "required": ["ok", "observed_at", "source"],
}


def _int_or_zero(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def build_protocol(app_state: Any, cfg: Any) -> Protocol:
    """Bind the one capability to whatever the running engine can already answer."""

    async def summary(_input: dict[str, Any]) -> dict[str, Any]:
        from oracle_core.protocol import utc_now_z

        engine = getattr(app_state, "engine", None)
        if engine is None:  # pragma: no cover - only before startup completes
            return {"ok": False, "observed_at": utc_now_z(), "source": "logos"}
        results = await engine.snapshot()
        hub = results.get("hub") or {}
        momus = results.get("momus") or {}
        return {
            "ok": True,
            # Counts, never the peer list: the catalogue is the hub's to publish, and a
            # summary that enumerated peers would be republishing somebody else's data
            # under this signature.
            "hubs_seen": _int_or_zero(hub.get("total_hubs")),
            "hubs_healthy": _int_or_zero(hub.get("healthy_hubs")),
            "capabilities_indexed": _int_or_zero(hub.get("total_capabilities")),
            "open_findings": _int_or_zero(momus.get("open_findings") or momus.get("total")),
            "observed_at": utc_now_z(),
            "source": "logos",
        }

    spec = OracleSpec(
        name="LOGOS Federation Analytics",
        product_id="prod-logos",
        description=(
            "Cross-hub analytics for the AIMarket federation: catalogue size, hub health "
            "and open audit findings, computed from LOGOS's own observations."
        ),
        public_url=str(getattr(cfg, "public_url", "") or "https://logos.modelmarket.dev"),
        categories=["analytics", "federation", "observability"],
        capabilities=[
            Capability(
                capability_id=SUMMARY_CAPABILITY,
                product_id="prod-logos",
                description=(
                    "Counts LOGOS currently observes across the federation it watches: hubs "
                    "seen and healthy, capabilities indexed, open findings. Reports on the "
                    "public federation, takes no input, and is free — a working sample of "
                    "LOGOS output rather than a report about the caller."
                ),
                price_per_call_usd=0.0,
                input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                output_schema=_OUTPUT_SCHEMA,
                handler=summary,
            ),
        ],
        signing_key_path=str(getattr(cfg, "data_dir", "data")) + "/aimarket_signing_key",
        version="0.1.0",
        related=["https://modelmarket.dev", "https://momus.modelmarket.dev"],
    )
    return Protocol(spec)
