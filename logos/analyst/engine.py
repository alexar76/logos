"""LOGOS analyst engine — the main orchestrator.

query → IntentPlanner → ParallelExecutor → CrossSourceCorrelator → Insights
"""

from __future__ import annotations

import time
from typing import Any

from logos.analyst.correlator import CrossSourceCorrelator
from logos.analyst.executor import ParallelExecutor
from logos.analyst.planner import IntentPlanner
from logos.analyst.reporter import DailyReporter
from logos.models import AskRequest, AskResponse, DailyReport, Insight, InsightKind


class AnalystEngine:
    """The main entry point for LOGOS analytics."""

    def __init__(self, config) -> None:
        self._cfg = config
        self._planner = IntentPlanner(config.metis_url, config.hub_timeout_s)
        self._executor = ParallelExecutor(config)
        self._correlator = CrossSourceCorrelator()
        self._reporter = DailyReporter()

    async def ask(self, req: AskRequest) -> AskResponse:
        """Process a natural-language or structured query."""
        started = time.monotonic()

        # 1. Plan
        plan = await self._planner.plan(req.query)
        intent = InsightKind(plan["intent"])
        sources = plan["sources"]
        metis_used = plan.get("metis_used", False)

        # 2. Execute
        results = await self._executor.execute(sources)

        # 3. Correlate
        insights = self._correlator.correlate(
            query=plan.get("structured_query", req.query),
            intent=intent,
            results=results,
            metis_used=metis_used,
        )

        elapsed = (time.monotonic() - started) * 1000

        return AskResponse(
            query=req.query,
            interpreted_intent=intent,
            insights=insights[: req.max_insights],
            taken_ms=round(elapsed, 2),
        )

    async def snapshot(self) -> dict:
        """Return current federation snapshot."""
        results = await self._executor.execute(["hub", "momus", "treasury"])
        return results

    async def daily_report(
        self, snapshot: dict, findings: dict, remediation: dict, treasury: dict,
        anomalies: list, recent_insights: list[Insight],
    ) -> DailyReport:
        return self._reporter.build_daily(
            snapshot=snapshot,
            findings=findings,
            remediation=remediation,
            treasury=treasury,
            anomalies=anomalies,
            recent_insights=recent_insights,
        )
