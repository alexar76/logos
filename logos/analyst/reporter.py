"""Daily / weekly report generator — produces a typed DailyReport from the
latest snapshot + findings + treasury data."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from logos.models import (
    Anomaly,
    DailyReport,
    DailyReportKPI,
    Insight,
)


class DailyReporter:
    """Stateless: data in → report out."""

    def build_daily(
        self,
        snapshot: dict,
        findings: dict,
        remediation: dict,
        treasury: dict,
        anomalies: list[Anomaly],
        recent_insights: list[Insight],
    ) -> DailyReport:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        now = datetime.now(timezone.utc).isoformat()

        kpis = self._build_kpis(snapshot, findings, treasury)
        overall = self._overall_status(kpis, anomalies, findings)

        return DailyReport(
            report_id=f"logos-report-{today}",
            date=today,
            generated_at=now,
            overall_status=overall,
            summary=self._build_summary(snapshot, findings, treasury, anomalies, overall),
            kpis=kpis,
            insights=recent_insights[:5],
            anomalies=[a for a in anomalies if not a.acknowledged][:5],
        )

    # ── internal ──────────────────────────────────────────────────────────

    def _build_kpis(self, snapshot: dict, findings: dict, treasury: dict) -> list[DailyReportKPI]:
        kpis: list[DailyReportKPI] = []

        # Hub health
        total = snapshot.get("total_hubs")
        healthy = snapshot.get("healthy_hubs")
        if snapshot.get("status") == "ok" and isinstance(total, (int, float)) and isinstance(healthy, (int, float)):
            ok = healthy == total
            kpis.append(DailyReportKPI(
                label="Hubs online",
                value=f"{healthy}/{total}",
                status="ok" if ok else "warn",
            ))

        # Capabilities
        capabilities = snapshot.get("total_capabilities")
        if snapshot.get("status") == "ok" and isinstance(capabilities, (int, float)):
            kpis.append(DailyReportKPI(
                label="Capabilities",
                value=str(capabilities),
                status="ok",
            ))

        # Findings
        total_f = findings.get("total_findings")
        if findings.get("status") == "ok" and isinstance(total_f, (int, float)):
            by_sev = findings.get("by_severity", {})
            critical = by_sev.get("critical", 0)
            high = by_sev.get("high", 0)
            if critical > 0:
                status = "critical"
            elif high > 0:
                status = "warn"
            else:
                status = "ok"
            kpis.append(DailyReportKPI(
                label="Findings",
                value=str(total_f),
                status=status,
            ))

        # Treasury
        available = treasury.get("available_usd")
        if treasury.get("status") == "ok" and available is not None:
            depletion = treasury.get("projected_depletion_days")
            ts = "ok"
            if depletion is not None:
                if depletion < 14:
                    ts = "critical"
                elif depletion < 30:
                    ts = "warn"
            kpis.append(DailyReportKPI(
                label="Treasury",
                value=f"${available:,.2f}",
                status=ts,
            ))

        return kpis

    def _overall_status(
        self, kpis: list[DailyReportKPI], anomalies: list[Anomaly], findings: dict
    ) -> str:
        unacked = [a for a in anomalies if not a.acknowledged]
        if any(a.severity.value == "critical" for a in unacked):
            return "critical"
        if any(k.status == "critical" for k in kpis):
            return "critical"
        if any(k.status == "warn" for k in kpis):
            return "warn"
        if unacked:
            return "warn"
        return "ok" if kpis else "warn"

    def _build_summary(
        self, snapshot: dict, findings: dict, treasury: dict,
        anomalies: list[Anomaly], overall: str,
    ) -> str:
        emoji = {"ok": "🟢", "warn": "🟡", "critical": "🔴"}.get(overall, "🟢")

        parts: list[str] = []
        total_h = snapshot.get("total_hubs")
        healthy_h = snapshot.get("healthy_hubs")
        total_c = snapshot.get("total_capabilities")
        if snapshot.get("status") == "ok" and None not in (total_h, healthy_h, total_c):
            parts.append(f"Federation: {healthy_h}/{total_h} hubs healthy · {total_c} capabilities")

        findings_t = findings.get("total_findings")
        if findings.get("status") == "ok" and findings_t is not None:
            parts.append(f"{findings_t} findings")

        available = treasury.get("available_usd")
        if treasury.get("status") == "ok" and available is not None:
            parts.append(f"${available:,.2f} Treasury available")

        unacked = sum(1 for a in anomalies if not a.acknowledged)
        if anomalies:
            parts.append(f"{unacked} unacknowledged anomalies")

        if not parts:
            return f"{emoji} No source telemetry available; no values were inferred."
        return f"{emoji} " + " · ".join(parts)
