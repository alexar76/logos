"""Data-source adapters — each returns a typed model or a status-degraded fallback.

Every adapter follows the same contract:

    async def fetch(ctx: dict) -> dict

`ctx` carries at least ``{"hub_url": str, "timeout_s": float}`` and optionally
service-specific URLs (``momus_url``, etc.).  The returned dict always has a
``"status"`` key: ``"ok"``, ``"unreachable"``, or ``"no_data"``.

An adapter MUST NOT raise — a broken remote is a degraded answer, not a crash.
"""

from logos.sources.hub import HubSource
from logos.sources.momus import MomusSource
from logos.sources.skopos import SkoposSource, TreasurySource

__all__ = ["HubSource", "MomusSource", "SkoposSource", "TreasurySource"]
