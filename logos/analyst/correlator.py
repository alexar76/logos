"""Cross-source correlator — finds patterns across different data sources.

Given the raw results from executor, the correlator produces typed Insights.
It operates entirely on already-fetched data — no network calls.
"""

from __future__ import annotations

import hashlib
from typing import Any

from logos.models import (
    DataSource,
    Insight,
    InsightKind,
    Recommendation,
    Severity,
)


class CrossSourceCorrelator:
    """Stateless correlator: raw results in → Insights out."""

    def correlate(
        self,
        query: str,
        intent: InsightKind,
        results: dict[str, Any],
        metis_used: bool = False,
    ) -> list[Insight]:
        """Produce 0–N Insights from the collected results."""
        insights: list[Insight] = []

        sources_used = [
            DataSource(name=k, status=v.get("status", "ok"), hub_url=v.get("hub_url", ""))
            for k, v in results.items()
        ]

        generator = getattr(self, f"_correlate_{intent.value}", None) or self._correlate_general
        raw = generator(query, results)
        if raw:
            items = raw if isinstance(raw, list) else [raw]
            for item in items:
                item["sources"] = item.get("sources", sources_used)
                item["generated_by"] = "metis-council" if metis_used else "rule-engine"
                # Content-addressed id so identical answers upsert instead of stacking
                # four "Federation overview" cards in insight_log.
                item["insight_id"] = _make_id(
                    str(item.get("kind", intent.value)),
                    str(item.get("title", "")),
                    str(item.get("summary", "")),
                )
                insights.append(Insight(**item))

        return insights

    # ── per-intent correlators ────────────────────────────────────────────

    def _correlate_economy(self, query: str, results: dict) -> list[dict] | None:
        treasury = results.get("treasury", {})
        if treasury.get("status") != "ok":
            return [{
                "insight_id": _make_id("econ"),
                "kind": "economy",
                "title": "Treasury data unavailable",
                "severity": "info",
                "summary": "The Treasury service did not respond. No economic data can be shown.",
                "explanation": "Check that the Treasury service is running and LOGOS_TREASURY_URL is set.",
                "recommendations": [],
            }]

        insights: list[dict] = []

        # Balance projection
        depletion = treasury.get("projected_depletion_days")
        avail = treasury.get("available_usd") or 0.0
        reserved = treasury.get("reserved_usd") or 0.0
        balance = treasury.get("balance_usd") or 0.0
        vol = treasury.get("payout_volume_24h_usd") or 0.0
        payouts = treasury.get("payouts_24h") or 0
        if depletion is not None:
            sev = Severity.critical if depletion < 14 else Severity.high if depletion < 30 else Severity.info
            insights.append({
                "insight_id": _make_id("econ-depletion"),
                "kind": "economy",
                "title": f"Treasury: {depletion} days until depletion",
                "severity": sev,
                "summary": f"At current payout rate (${float(vol):.2f}/day), "
                           f"the available balance of ${float(avail):.2f} "
                           f"will last approximately {depletion} days.",
                "explanation": f"Reserved: ${float(reserved):.2f}. "
                               f"Balance: ${float(balance):.2f}. "
                               f"24h payouts: {int(payouts)} transactions, "
                               f"${float(vol):.2f} volume.",
                "recommendations": [
                    Recommendation(
                        priority=1,
                        action="Top up the Treasury vault",
                        impact="Prevents payout disruption",
                        verification="Check /vault after deposit",
                    ),
                ] if sev in (Severity.critical, Severity.high) else [],
            })
        else:
            insights.append({
                "insight_id": _make_id("econ-balance"),
                "kind": "economy",
                "title": f"Treasury available: ${float(avail):.2f}",
                "severity": "info",
                "summary": (
                    f"Balance ${float(balance):.2f}, reserved ${float(reserved):.2f}, "
                    f"24h payouts {int(payouts)} (${float(vol):.2f}). "
                    "No projected_depletion_days in this snapshot."
                ),
                "explanation": "Runway is only shown when Treasury publishes a depletion projection.",
                "recommendations": [],
            })

        return insights or None

    def _correlate_latency(self, query: str, results: dict) -> list[dict] | None:
        hub = results.get("hub", {})
        if hub.get("status") != "ok":
            return [{
                "insight_id": _make_id("lat"),
                "kind": "latency",
                "title": "Hub latency data unavailable",
                "severity": "info",
                "summary": "The Hub snapshot did not respond, so peer latency cannot be ranked.",
                "explanation": "Verify LOGOS_HUB_URL and that the Hub publishes peers with measured latency.",
                "recommendations": [],
            }]

        peers = list(hub.get("peers") or [])
        measured = [p for p in peers if isinstance(p.get("latency_ms"), (int, float))]
        if not measured:
            healthy = hub.get("healthy_hubs")
            total = hub.get("total_hubs")
            return [{
                "insight_id": _make_id("lat"),
                "kind": "latency",
                "title": "No peer latency samples in the current snapshot",
                "severity": "info",
                "summary": (
                    f"The Hub lists {len(peers)} peer(s)"
                    + (f" ({healthy}/{total} healthy)" if None not in (healthy, total) else "")
                    + ", but none published a measured latency_ms for this snapshot."
                ),
                "explanation": (
                    "LOGOS does not invent latency. Re-check after peers report "
                    "latency, or inspect Hub peer health directly."
                ),
                "recommendations": [],
            }]

        slow_peers = [p for p in measured if float(p["latency_ms"]) > 500]
        ranked = sorted(measured, key=lambda p: float(p["latency_ms"]), reverse=True)
        top = ranked[:5]
        lines = ", ".join(
            f"{p.get('name') or p.get('url') or '?'}={int(float(p['latency_ms']))}ms"
            for p in top
        )

        if slow_peers:
            names = ", ".join(p.get("name") or p.get("url") or "?" for p in slow_peers[:3])
            return [{
                "insight_id": _make_id("lat"),
                "kind": "latency",
                "title": f"High latency on {len(slow_peers)} hub(s): {names}",
                "severity": "high",
                "summary": (
                    f"{len(slow_peers)} of {len(measured)} measured peers exceed 500ms. "
                    f"Slowest samples: {lines}."
                ),
                "explanation": "Elevated latency may indicate CPU contention, network issues, or overloaded services.",
                "recommendations": [
                    Recommendation(
                        priority=1,
                        action="Check CPU/memory on the slowest hosts first",
                        impact="Restores federation responsiveness",
                        verification="Re-query latency after intervention",
                    ),
                ],
            }]

        return [{
            "insight_id": _make_id("lat"),
            "kind": "latency",
            "title": f"No hubs above the 500ms latency threshold ({len(measured)} measured)",
            "severity": "info",
            "summary": f"All measured peers are within threshold. Slowest samples: {lines}.",
            "explanation": "Threshold is 500ms on published peer latency_ms from the Hub snapshot.",
            "recommendations": [],
        }]

    def _correlate_security(self, query: str, results: dict) -> list[dict] | None:
        momus = results.get("momus", {})
        skopos = results.get("skopos", {})

        if momus.get("status") != "ok":
            return [{
                "insight_id": _make_id("sec"),
                "kind": "security",
                "title": "MOMUS data unavailable",
                "severity": "info",
                "summary": "The security scanner did not respond. No finding data can be shown.",
                "explanation": "Verify MOMUS is running and LOGOS_MOMUS_URL is set.",
                "recommendations": [],
            }]

        insights: list[dict] = []
        by_sev = momus.get("by_severity", {}) or {}
        critical = int(by_sev.get("critical", 0) or 0)
        high = int(by_sev.get("high", 0) or 0)
        total = int(momus.get("total_findings", 0) or 0)

        if critical > 0:
            insights.append({
                "insight_id": _make_id("sec-crit"),
                "kind": "security",
                "title": f"{critical} critical finding(s) require immediate attention",
                "severity": "critical",
                "summary": f"MOMUS found {critical} critical and {high} high-severity issues "
                           f"across the federation.",
                "explanation": f"Total findings: {total}. Top probes: {', '.join(momus.get('top_probes', []) or [])}. "
                               f"Recurring: {momus.get('recurring', 0)}.",
                "recommendations": [
                    Recommendation(
                        priority=1,
                        action="Review each critical finding in MOMUS live panel",
                        impact="Prevents exploitation of known vulnerabilities",
                        verification="Check Finding IDs in the SKOPOS remediation board",
                    ),
                ],
            })
        else:
            insights.append({
                "insight_id": _make_id("sec-clear"),
                "kind": "security",
                "title": "No critical findings in the current MOMUS snapshot",
                "severity": "info",
                "summary": (
                    f"Critical=0, high={high}, total findings={total}, "
                    f"recurring={momus.get('recurring', 0)}."
                ),
                "explanation": (
                    "This answers the critical-findings question from measured MOMUS "
                    "aggregates — not an invented clean bill of health beyond that window."
                ),
                "recommendations": [],
            })

        # SKOPOS remediation rate
        if skopos.get("status") == "ok" and skopos.get("total_jobs", 0) > 0:
            fixed = skopos.get("confirmed_fixed", 0)
            total_jobs = skopos.get("total_jobs", 1)
            fix_rate = fixed / max(total_jobs, 1)
            if fix_rate < 0.5:
                insights.append({
                    "insight_id": _make_id("sec-fixrate"),
                    "kind": "security",
                    "title": f"Low remediation rate: {round(fix_rate * 100)}% findings fixed",
                    "severity": "high",
                    "summary": f"Only {fixed} of {total_jobs} findings have been confirmed fixed.",
                    "explanation": f"Escalated: {skopos.get('escalated', 0)}. "
                                   f"Deploy orders signed: {skopos.get('orders_signed', 0)}.",
                    "recommendations": [
                        Recommendation(
                            priority=1,
                            action="Prioritise remediation of outstanding findings",
                            impact="Prevents accumulation of known security debt",
                            verification="Monitor the SKOPOS remediation board",
                        ),
                    ],
                })

        return insights or None
    def _correlate_reputation(self, query: str, results: dict) -> list[dict] | None:
        hub = results.get("hub", {})
        peers = hub.get("peers", [])

        sorted_peers = sorted(peers, key=lambda p: p.get("trust_score", 0), reverse=True)
        if sorted_peers:
            best = sorted_peers[0]
            worst = sorted_peers[-1]
            return [{
                "insight_id": _make_id("rep"),
                "kind": "reputation",
                "title": f"Reputation leaderboard: {best.get('name', best.get('url', '?'))} "
                         f"leads with {best.get('trust_score', 0):.2f}",
                "severity": "info",
                "summary": f"Most trusted hub: {best.get('name', best.get('url', '?'))} "
                           f"(score {best.get('trust_score', 0):.2f}). "
                           f"Lowest: {worst.get('name', worst.get('url', '?'))} "
                           f"(score {worst.get('trust_score', 0):.2f}). "
                           f"Total peers indexed: {len(peers)}.",
                "explanation": f"Healthy hubs: {hub.get('healthy_hubs', 0)}/{hub.get('total_hubs', 0)}. "
                               f"Federated capabilities: {hub.get('federated_capabilities', 0)}.",
                "recommendations": [],
            }]

        return None

    def _correlate_general(self, query: str, results: dict) -> list[dict] | None:
        hub = results.get("hub", {})
        momus = results.get("momus", {})
        treasury = results.get("treasury", {})

        total_caps = hub.get("total_capabilities")
        fed_caps = hub.get("federated_capabilities")
        findings = momus.get("total_findings")
        balance = treasury.get("available_usd")

        parts: list[str] = []
        healthy = hub.get("healthy_hubs")
        total_hubs = hub.get("total_hubs")
        if hub.get("status") == "ok" and None not in (healthy, total_hubs, total_caps, fed_caps):
            parts.append(
                f"Federation: {healthy}/{total_hubs} hubs healthy, "
                f"{total_caps} capabilities ({fed_caps} federated)"
            )
        if momus.get("status") == "ok" and findings is not None:
            parts.append(f"Security: {findings} findings ({momus.get('recurring', 0)} recurring)")
        if treasury.get("status") == "ok" and balance is not None:
            parts.append(f"Treasury: ${balance:.2f} available")

        return [{
            "insight_id": _make_id("gen"),
            "kind": "general",
            "title": "Federation overview",
            "severity": "info" if parts else "high",
            "summary": " · ".join(parts) if parts else "Federation sources are unavailable; no values were inferred.",
            "explanation": "" if parts else "Check the configured Hub, MOMUS, and Treasury endpoints.",
            "recommendations": [],
        }]


def _make_id(*parts: str) -> str:
    """Stable id from content parts (kind/title/summary).

    Timestamp-based ids made every identical overview a new row; the UI then
    loaded four copies of «Federation overview» from insight_log. Hashing the
    answer body keeps INSERT upserts and recent_insights dedupe honest.
    """
    material = "\0".join(p.strip() for p in parts if p is not None)
    h = hashlib.sha256(material.encode()).hexdigest()[:12]
    return f"logos-{h}"
