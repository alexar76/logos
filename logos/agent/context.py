"""SQL-safe assistant context builder.

The assistant reads through ``LogosStore``, which is the single place that
holds SQL in this service: every statement there is a fixed string with bound
parameters — no column name, table name, or predicate is ever assembled from
user input. Going through the store also means the context works on both
backends (SQLite in dev, Postgres in the federation tier) instead of only the
one that happens to have a local file.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover — typing only
    from logos.store import LogosStore


# ── LOGOS knowledge base (injected into system prompt) ─────────────────────

LOGOS_KNOWLEDGE = """
## LOGOS platform knowledge

LOGOS is the AIMarket federation analytics engine — one node that queries and
correlates data from every component in the federation through transparent
hub.invoke() proxy.

### Data sources available
- **Hub** — federation peers, capabilities count, trust scores, crawl status.
- **MOMUS** — signed security findings by severity, probe type, category, remediation status.
- **SKOPOS** — remediation cycles: fix attempts, gate verdicts, deploy orders.
- **Treasury** — balance, reserved/available split, payout rate, depletion projection.
- **Lumen** — EigenTrust / PageRank reputation scores across the federation graph.

### Operator surfaces
- `/api/v1/snapshot` — current federation state.
- `/api/v1/ask` — natural-language query returns typed Insights.
- `/api/v1/report/daily` — morning briefing with KPIs and anomaly highlights.
- `/api/v1/anomalies` — active anomaly alerts with z-score details.

### Assistant capabilities
You have direct read-only access to the LOGOS analytics store. You can:
- Query recent federation snapshots (time-series of hub health).
- List active anomalies with severity and z-score.
- Retrieve past insights and daily reports.
- Answer questions about the federation's current and historical state.

### Rules
1. **Never invent data.** If the store has no data for a question, say so.
2. **Quote specific numbers** when they exist — avoid vague summaries.
3. **Use the severity ladder** consistently: info < low < medium < high < critical.
4. **When recommending actions**, be concrete: name the service, the action, and how to verify.
5. **Not a control plane** — you cannot scan, pay, remediate, or deploy. Say "this requires the MOMUS scanner" or "this requires the Treasury operator".
"""


def build_assistant_context(
    store: LogosStore,
    *,
    snapshot_limit: int = 10,
    anomaly_limit: int = 20,
    insight_limit: int = 10,
) -> str:
    """Assemble a context block for the LOGOS assistant from the store.

    Reads go through ``LogosStore``, so the same context is available on
    SQLite and on Postgres. The returned string is truncated by the caller to
    the LLM context budget.

    Returns an empty context block when the store is unreadable — the
    assistant degrades to answering from the knowledge base alone.
    """
    parts: list[str] = []

    try:
        # ── recent snapshots ──────────────────────────────────────────
        snaps = store.recent_snapshots(snapshot_limit)
        if snaps:
            parts.append("## Recent federation snapshots")
            for snap in snaps:
                hubs = f"{snap.get('healthy_hubs', '?')}/{snap.get('total_hubs', '?')}"
                caps = snap.get("total_capabilities", "?")
                parts.append(
                    f"- {str(snap.get('captured_at', ''))[:19]}: "
                    f"{hubs} hubs, {caps} capabilities"
                )

        # ── active anomalies ─────────────────────────────────────────
        anoms = sorted(
            store.get_anomalies(acknowledged=False),
            key=lambda a: a.z_score,
            reverse=True,
        )[:anomaly_limit]
        if anoms:
            parts.append("\n## Active anomalies (unacknowledged)")
            for a in anoms:
                parts.append(
                    f"- [{a.severity.value.upper()}] {a.metric}: "
                    f"z={a.z_score:.1f}, observed {a.observed_value:.1f}, "
                    f"expected {a.expected_value:.1f} ({a.detected_at[:19]})"
                )

        # ── recent insights ──────────────────────────────────────────
        queries = store.recent_insight_queries(insight_limit)
        if queries:
            parts.append("\n## Recent queries & insights")
            for ins in queries:
                q = ins["query_text"][:120]
                parts.append(f"- [{ins['kind']}] {q} ({ins['created_at'][:19]})")

    except Exception:
        pass

    if not parts:
        parts.append("No stored data available yet — the poll loop may not have run.")

    return "\n".join(parts)
