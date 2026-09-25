"""Unit tests for the CrossSourceCorrelator."""

from logos.analyst.correlator import CrossSourceCorrelator
from logos.models import InsightKind


class TestCorrelator:
    def test_economy_treasury_ok(self):
        c = CrossSourceCorrelator()
        results = {
            "treasury": {
                "status": "ok", "available_usd": 5000, "balance_usd": 7500,
                "reserved_usd": 2500, "payouts_24h": 3, "payout_volume_24h_usd": 100,
                "projected_depletion_days": 50,
            },
        }
        insights = c.correlate("treasury status", InsightKind.economy, results)
        assert len(insights) == 1
        assert "50 days" in insights[0].title

    def test_economy_treasury_unreachable(self):
        c = CrossSourceCorrelator()
        results = {"treasury": {"status": "unreachable"}}
        insights = c.correlate("treasury status", InsightKind.economy, results)
        assert len(insights) == 1
        assert "unavailable" in insights[0].title.lower()

    def test_security_critical_findings(self):
        c = CrossSourceCorrelator()
        results = {
            "momus": {
                "status": "ok", "total_findings": 5, "recurring": 1,
                "by_severity": {"critical": 3, "high": 1, "medium": 1},
                "top_probes": ["prompt_injection"], "top_categories": ["injection"],
            },
        }
        insights = c.correlate("security status", InsightKind.security, results)
        assert len(insights) == 1
        assert insights[0].severity.value == "critical"
        assert "3 critical" in insights[0].title

    def test_security_momus_unreachable(self):
        c = CrossSourceCorrelator()
        results = {"momus": {"status": "unreachable"}}
        insights = c.correlate("security status", InsightKind.security, results)
        assert len(insights) == 1
        assert "unavailable" in insights[0].title.lower()

    def test_latency_slow_peers(self):
        c = CrossSourceCorrelator()
        results = {
            "hub": {
                "status": "ok", "peers": [
                    {"name": "hub-a", "url": "http://a", "latency_ms": 800},
                    {"name": "hub-b", "url": "http://b", "latency_ms": 100},
                ],
            },
        }
        insights = c.correlate("latency check", InsightKind.latency, results)
        assert len(insights) == 1
        assert "hub-a" in insights[0].title

    def test_latency_all_healthy(self):
        c = CrossSourceCorrelator()
        results = {
            "hub": {
                "status": "ok", "peers": [
                    {"name": "hub-a", "latency_ms": 120},
                    {"name": "hub-b", "latency_ms": 80},
                ],
            },
        }
        insights = c.correlate("latency check", InsightKind.latency, results)
        assert len(insights) == 1
        assert "500ms" in insights[0].title

    def test_latency_no_samples(self):
        c = CrossSourceCorrelator()
        results = {
            "hub": {
                "status": "ok", "healthy_hubs": 1, "total_hubs": 4,
                "peers": [{"name": "hub-a"}, {"name": "hub-b"}],
            },
        }
        insights = c.correlate("latency check", InsightKind.latency, results)
        assert len(insights) == 1
        assert "No peer latency" in insights[0].title

    def test_security_no_critical(self):
        c = CrossSourceCorrelator()
        results = {
            "momus": {
                "status": "ok", "total_findings": 2, "recurring": 0,
                "by_severity": {"critical": 0, "high": 1, "medium": 1},
                "top_probes": [],
            },
        }
        insights = c.correlate("critical findings?", InsightKind.security, results)
        assert len(insights) == 1
        assert insights[0].severity.value == "info"
        assert "No critical" in insights[0].title

    def test_reputation_leaderboard(self):
        c = CrossSourceCorrelator()
        results = {
            "hub": {
                "status": "ok", "healthy_hubs": 2, "total_hubs": 3,
                "federated_capabilities": 20,
                "peers": [
                    {"name": "hub-a", "url": "http://a", "trust_score": 0.95},
                    {"name": "hub-b", "url": "http://b", "trust_score": 0.30},
                ],
            },
        }
        insights = c.correlate("reputation check", InsightKind.reputation, results)
        assert len(insights) == 1
        assert "hub-a" in insights[0].title
        assert "0.95" in insights[0].title

    def test_general_overview(self):
        c = CrossSourceCorrelator()
        results = {
            "hub": {"status": "ok", "total_hubs": 3, "healthy_hubs": 3, "total_capabilities": 150, "federated_capabilities": 80, "peers": []},
            "momus": {"status": "ok", "total_findings": 10, "recurring": 2},
            "treasury": {"status": "ok", "available_usd": 5000},
        }
        insights = c.correlate("overview", InsightKind.general, results)
        assert len(insights) == 1
        assert "Federation" in insights[0].title

    def test_identical_answers_share_insight_id(self):
        """Repeat asks must not invent a new id for the same overview body."""
        c = CrossSourceCorrelator()
        results = {
            "hub": {"status": "ok", "total_hubs": 3, "healthy_hubs": 3, "total_capabilities": 150, "federated_capabilities": 80, "peers": []},
            "momus": {"status": "ok", "total_findings": 0, "recurring": 0},
            "treasury": {"status": "unreachable"},
        }
        a = c.correlate("overview", InsightKind.general, results)[0]
        b = c.correlate("overview again", InsightKind.general, results)[0]
        assert a.insight_id == b.insight_id
        assert a.insight_id.startswith("logos-")
        assert len(a.insight_id) > len("logos-")
