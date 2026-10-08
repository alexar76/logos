"""Unit tests for LOGOS data models."""

from logos.models import (
    AskRequest,
    AskResponse,
    Anomaly,
    DailyReport,
    DailyReportKPI,
    Insight,
    InsightKind,
    Recommendation,
    Severity,
)


class TestModels:
    def test_ask_request_defaults(self):
        r = AskRequest(query="test")
        assert r.max_insights == 5

    def test_ask_request_valid(self):
        r = AskRequest(query="valid query", max_insights=5)
        assert r.max_insights == 5

    def test_ask_query_too_long(self):
        from pydantic import ValidationError
        try:
            AskRequest(query="x" * 9000, max_insights=5)
            assert False, "Should have raised ValidationError"
        except ValidationError:
            pass

    def test_insight_kind_enum(self):
        assert InsightKind.economy.value == "economy"
        assert InsightKind.security.value == "security"

    def test_severity_enum(self):
        assert Severity.critical.value == "critical"
        assert Severity.info.value == "info"

    def test_insight_minimal(self):
        i = Insight(insight_id="logos-test", kind="general", title="Test", severity="info",
                     summary="ok", explanation="all good", recommendations=[], sources=[])
        assert i.insight_id == "logos-test"
        assert i.generated_by == ""  # default

    def test_anomaly_defaults(self):
        a = Anomaly(anomaly_id="anom-1", metric="test", description="test anomaly",
                     severity="info", z_score=3.5, observed_value=10, expected_value=5,
                     detected_at="2026-01-01T00:00:00")
        assert not a.acknowledged
        assert a.acknowledged_at is None

    def test_daily_report_serialization(self):
        r = DailyReport(
            report_id="logos-report-2026-01-01",
            date="2026-01-01",
            generated_at="2026-01-01T09:00:00",
            overall_status="ok",
            summary="All good",
            kpis=[DailyReportKPI(label="Hubs", value="3/3", status="ok")],
        )
        d = r.model_dump()
        assert d["report_id"] == "logos-report-2026-01-01"
        assert d["kpis"][0]["label"] == "Hubs"

    def test_ask_response_serialization(self):
        r = AskResponse(query="test", interpreted_intent=InsightKind.general,
                         insights=[], taken_ms=100.5)
        d = r.model_dump()
        assert d["taken_ms"] == 100.5
