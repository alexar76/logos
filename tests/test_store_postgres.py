"""Postgres dialect tests for LogosStore.

The federation tier (docker-compose.everything.yml) runs LOGOS against
Postgres, so the PG branch of every statement has to be exercised somewhere.
It previously was not, and the schema it produced was not valid Postgres at
all: `datetime('now')` defaults, an id column with no sequence, an interval
built by string interpolation, and NOW() assigned into a TEXT column.

Set LOGOS_TEST_DATABASE_URL to a scratch database to run these; without it
the module skips, so the default SQLite suite stays dependency-free.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from logos.models import Anomaly, DailyReport, Insight, InsightKind, Severity

PG_URL = os.environ.get("LOGOS_TEST_DATABASE_URL", "").strip()

pytestmark = pytest.mark.skipif(
    not PG_URL, reason="LOGOS_TEST_DATABASE_URL not set — Postgres dialect tests skipped"
)


@pytest.fixture
def pg_store(monkeypatch):
    """A store bound to the scratch Postgres, truncated before each test."""
    monkeypatch.setenv("LOGOS_DATABASE_URL", PG_URL)
    from logos.store import LogosStore

    store = LogosStore(Path(tempfile.mkdtemp()))
    store.open()
    for table in ("federation_snapshots", "anomaly_log", "daily_reports", "insight_log"):
        cur = store._execute(f"DELETE FROM {table}")
        cur.close()
    store._commit()
    yield store
    store.close()


def _anomaly(anomaly_id: str = "pg-1", **kw) -> Anomaly:
    return Anomaly(
        anomaly_id=anomaly_id, metric=kw.get("metric", "total_findings"),
        hub_url="", severity=kw.get("severity", Severity.high),
        z_score=kw.get("z_score", 4.25), observed_value=40, expected_value=10,
        description="spike", detected_at=kw.get("detected_at", "2026-01-01T00:00:00"),
    )


class TestPostgresSchema:
    def test_open_creates_schema_and_snapshots_get_an_id(self, pg_store):
        """A snapshot insert supplies no id — the column needs its own sequence."""
        pg_store.save_snapshot({"healthy_hubs": 2, "total_hubs": 3, "total_capabilities": 41})
        pg_store.save_snapshot({"healthy_hubs": 3, "total_hubs": 3, "total_capabilities": 42})
        rows = pg_store.recent_snapshots(5)
        assert len(rows) == 2
        assert {r["total_capabilities"] for r in rows} == {41, 42}

    def test_captured_at_default_matches_sqlite_shape(self, pg_store):
        """Timestamps are TEXT in both dialects and must share one format, or
        ordering, cutoff comparisons and the UI's [:19] slice diverge."""
        pg_store.save_snapshot({"total_capabilities": 1})
        captured = pg_store.recent_snapshots(1)[0]["captured_at"]
        assert len(captured) == 19
        assert captured[4] == "-" and captured[10] == " " and captured[13] == ":"

    def test_open_is_idempotent(self, pg_store):
        """CREATE TABLE IF NOT EXISTS — a restart must not fail on existing tables."""
        pg_store.open()
        pg_store.save_snapshot({"total_capabilities": 7})
        assert pg_store.recent_snapshots(1)[0]["total_capabilities"] == 7


class TestPostgresAnomalies:
    def test_save_is_idempotent(self, pg_store):
        pg_store.save_anomaly(_anomaly())
        pg_store.save_anomaly(_anomaly())  # ON CONFLICT DO NOTHING
        assert len(pg_store.get_anomalies(acknowledged=None)) == 1

    def test_acknowledge_writes_text_timestamp(self, pg_store):
        """acknowledged_at is TEXT; Postgres has no implicit cast from NOW()."""
        pg_store.save_anomaly(_anomaly())
        assert pg_store.acknowledge_anomaly("pg-1") is True
        assert pg_store.get_anomalies(acknowledged=False) == []
        acked = pg_store.get_anomalies(acknowledged=True)
        assert [a.anomaly_id for a in acked] == ["pg-1"]
        assert pg_store.acknowledge_anomaly("pg-1") is False  # already acked

    def test_float_columns_round_trip(self, pg_store):
        pg_store.save_anomaly(_anomaly(z_score=6.125))
        assert pg_store.get_anomalies(acknowledged=None)[0].z_score == pytest.approx(6.125)


class TestPostgresRetention:
    def test_prune_deletes_rows_past_the_window(self, pg_store):
        """The old PG branch interpolated the interval into a quoted literal, so
        this DELETE raised every cycle — swallowed by the poll loop's except."""
        cur = pg_store._execute(
            "INSERT INTO federation_snapshots (captured_at, payload) VALUES (%s, %s)",
            ("2020-01-01 00:00:00", '{"total_capabilities": 1}'),
        )
        cur.close()
        pg_store._commit()
        pg_store.save_snapshot({"total_capabilities": 2})

        pg_store.prune_snapshots(30)

        kept = pg_store.recent_snapshots(10)
        assert [r["total_capabilities"] for r in kept] == [2]

    def test_prune_keeps_recent_rows(self, pg_store):
        pg_store.save_snapshot({"total_capabilities": 3})
        pg_store.prune_snapshots(30)
        assert len(pg_store.recent_snapshots(10)) == 1


class TestPostgresReportsAndInsights:
    def test_report_upsert(self, pg_store):
        rep = DailyReport(
            report_id="pg-rep-1", date="2026-01-01", generated_at="2026-01-01T00:00:00",
            overall_status="green", summary="all good", kpis=[], insights=[], anomalies=[],
        )
        pg_store.save_report(rep)
        rep.summary = "revised"
        pg_store.save_report(rep)  # ON CONFLICT ... DO UPDATE
        stored = pg_store.get_report("2026-01-01")
        assert stored is not None
        assert stored.summary == "revised"

    def test_insight_queries_round_trip(self, pg_store):
        ins = Insight(
            insight_id="pg-ins-1", kind=InsightKind.economy, title="t", severity="info",
            summary="s", explanation="e", sources=[], recommendations=[],
            generated_at="2026-01-01T00:00:00", generated_by="test",
        )
        pg_store.save_insight(ins, "treasury balance?")
        assert len(pg_store.recent_insights(10)) == 1
        queries = pg_store.recent_insight_queries(5)
        assert queries[0]["query_text"] == "treasury balance?"
        assert queries[0]["kind"] == "economy"


class TestPostgresAssistantContext:
    def test_context_built_without_a_sqlite_file(self, pg_store):
        """The assistant used to open cfg.data_dir/logos.db directly, which does
        not exist under Postgres — it silently answered with no data at all."""
        from logos.agent.context import build_assistant_context

        pg_store.save_snapshot({"healthy_hubs": 2, "total_hubs": 3, "total_capabilities": 41})
        pg_store.save_anomaly(_anomaly(severity=Severity.critical, z_score=6.1))

        ctx = build_assistant_context(pg_store)

        assert "2/3 hubs, 41 capabilities" in ctx
        assert "[CRITICAL] total_findings" in ctx
