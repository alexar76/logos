"""Parallel executor — runs all selected source adapters concurrently.

Each adapter returns a dict with a ``"status"`` key.  The executor collects them
all, never raising — a failed adapter is a degraded answer, not a crash.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Awaitable, Callable

logger = logging.getLogger("logos.executor")

from logos.sources.hub import HubSource
from logos.sources.momus import MomusSource
from logos.sources.skopos import SkoposSource, TreasurySource
from logos.sources.argus import ArgusSource
from logos.sources.bridges import BridgesSource
from logos.sources.lumen import LumenSource
from logos.sources.a2a_source import A2ASource


class ParallelExecutor:
    """Execute a set of data-source fetches in parallel and return the collected
    results.  Every fetch is individually guarded so one broken source never
    blocks the others."""

    def __init__(self, config) -> None:
        self._cfg = config
        self._hub = HubSource(config.hub_url, config.hub_timeout_s)
        self._momus = MomusSource(config.momus_url, config.hub_timeout_s)
        self._skopos = SkoposSource(config.skopos_url, config.hub_timeout_s)
        self._treasury = TreasurySource(config.treasury_url, config.hub_timeout_s)
        self._argus = ArgusSource(config.argus_url, config.hub_timeout_s)
        self._bridges = BridgesSource(config.bridges_url, config.hub_timeout_s)
        self._lumen = LumenSource(config.lumen_url, config.hub_timeout_s)
        self._a2a = A2ASource(None, config.hub_timeout_s)  # no separate A2A URL

    async def execute(self, sources: list[str]) -> dict[str, Any]:
        """Run the named sources in parallel and return {source_name: result}.

        ``sources`` is a list of adapter names: hub, momus, skopos, treasury.
        """
        tasks: dict[str, Awaitable[dict]] = {}
        for name in sources:
            fetcher = self._fetcher_for(name)
            if fetcher:
                tasks[name] = self._guarded(name, fetcher)

        if not tasks:
            return {}

        results: dict[str, Any] = {}
        names = list(tasks.keys())
        coros = list(tasks.values())
        gathered = await asyncio.gather(*coros)
        for name, result in zip(names, gathered):
            results[name] = result
        return results

    def _fetcher_for(self, name: str) -> Callable[[], Awaitable[dict]] | None:
        if name == "hub":
            return self._hub.fetch_snapshot
        if name == "momus":
            return self._momus.fetch_findings
        if name == "skopos":
            return self._skopos.fetch_remediation
        if name == "treasury":
            return self._treasury.fetch_balance
        if name == "argus":
            return self._argus.fetch
        if name == "bridges":
            return self._bridges.fetch
        if name == "lumen":
            return self._lumen.fetch
        if name == "a2a":
            return self._a2a.fetch
        return None

    async def _guarded(self, name: str, fetcher: Callable[[], Awaitable[dict]]) -> dict:
        started = time.monotonic()
        try:
            result = await fetcher()
        except Exception as exc:
            logger.warning("Source %s failed: %s", name, exc)
            result = {"status": "unreachable", "error": f"{name} adapter raised"}
        elapsed_ms = (time.monotonic() - started) * 1000
        result["_elapsed_ms"] = round(elapsed_ms, 2)
        result["_source"] = name
        return result
