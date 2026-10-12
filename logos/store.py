"""LOGOS store — SQLite (dev) or Postgres (prod), dual-dialect.

WAL mode, proper indexes. Schema is idempotent — CREATE TABLE IF NOT EXISTS
so the dashboard opens the database before the first snapshot ever lands.
"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from logos.models import Anomaly, DailyReport, Insight


def _is_postgres() -> bool:
    return bool(os.environ.get("LOGOS_DATABASE_URL", "").strip())


_SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS federation_snapshots (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    captured_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    payload       TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_snapshots_captured
    ON federation_snapshots(captured_at DESC);

CREATE TABLE IF NOT EXISTS anomaly_log (
    anomaly_id    TEXT    PRIMARY KEY,
    metric        TEXT    NOT NULL,
    hub_url       TEXT    NOT NULL DEFAULT '',
    severity      TEXT    NOT NULL DEFAULT 'info',
    z_score       REAL    NOT NULL DEFAULT 0.0,
    observed_value REAL   NOT NULL DEFAULT 0.0,
    expected_value REAL   NOT NULL DEFAULT 0.0,
    description   TEXT    NOT NULL DEFAULT '',
    detected_at   TEXT    NOT NULL,
    acknowledged  INTEGER NOT NULL DEFAULT 0,
    acknowledged_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_anomaly_detected
    ON anomaly_log(detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_anomaly_unacked
    ON anomaly_log(acknowledged, detected_at DESC);

CREATE TABLE IF NOT EXISTS daily_reports (
    report_id     TEXT    PRIMARY KEY,
    date          TEXT    NOT NULL,
    generated_at  TEXT    NOT NULL,
    payload       TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reports_date
    ON daily_reports(date DESC);

CREATE TABLE IF NOT EXISTS insight_log (
    insight_id    TEXT    PRIMARY KEY,
    kind          TEXT    NOT NULL DEFAULT 'general',
    query_text    TEXT    NOT NULL DEFAULT '',
    payload       TEXT    NOT NULL,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_insight_created
    ON insight_log(created_at DESC);
"""

# Postgres needs its own DDL, not a textual rewrite of the SQLite one:
# `datetime('now')` is not a Postgres function, and `INTEGER PRIMARY KEY`
# there means "no default" rather than SQLite's implicit rowid.
#
# Timestamp columns stay TEXT in both dialects and are written in the same
# 'YYYY-MM-DD HH24:MI:SS' shape, so ordering, `< cutoff` comparisons, and the
# `[:19]` slices in the UI behave identically on either backend.
_PG_TS_NOW = "to_char(now() AT TIME ZONE 'utc', 'YYYY-MM-DD HH24:MI:SS')"

_PG_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS federation_snapshots (
    id            BIGSERIAL PRIMARY KEY,
    captured_at   TEXT    NOT NULL DEFAULT {_PG_TS_NOW},
    payload       TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_snapshots_captured
    ON federation_snapshots(captured_at DESC);

CREATE TABLE IF NOT EXISTS anomaly_log (
    anomaly_id    TEXT    PRIMARY KEY,
    metric        TEXT    NOT NULL,
    hub_url       TEXT    NOT NULL DEFAULT '',
    severity      TEXT    NOT NULL DEFAULT 'info',
    z_score       DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    observed_value DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    expected_value DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    description   TEXT    NOT NULL DEFAULT '',
    detected_at   TEXT    NOT NULL,
    acknowledged  INTEGER NOT NULL DEFAULT 0,
    acknowledged_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_anomaly_detected
    ON anomaly_log(detected_at DESC);
CREATE INDEX IF NOT EXISTS idx_anomaly_unacked
    ON anomaly_log(acknowledged, detected_at DESC);

CREATE TABLE IF NOT EXISTS daily_reports (
    report_id     TEXT    PRIMARY KEY,
    date          TEXT    NOT NULL,
    generated_at  TEXT    NOT NULL,
    payload       TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reports_date
    ON daily_reports(date DESC);

CREATE TABLE IF NOT EXISTS insight_log (
    insight_id    TEXT    PRIMARY KEY,
    kind          TEXT    NOT NULL DEFAULT 'general',
    query_text    TEXT    NOT NULL DEFAULT '',
    payload       TEXT    NOT NULL,
    created_at    TEXT    NOT NULL DEFAULT {_PG_TS_NOW}
);
CREATE INDEX IF NOT EXISTS idx_insight_created
    ON insight_log(created_at DESC);
"""


class LogosStore:
    """SQLite or Postgres store. Works with both backends via simple
    connection wrapper — no ORM, no migrations framework."""

    def __init__(self, data_dir: Path) -> None:
        data_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = data_dir / "logos.db"
        self._pg_url = os.environ.get("LOGOS_DATABASE_URL", "").strip()
        self._conn: Any = None

    # ── lifecycle ─────────────────────────────────────────────────────────

    def open(self) -> None:
        if self._pg_url:
            import psycopg2
            conn = psycopg2.connect(self._pg_url)
            conn.autocommit = False
            cur = conn.cursor()
            cur.execute(_PG_SCHEMA)
            cur.close()
            conn.commit()
            self._conn = conn
        else:
            conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.executescript(_SQLITE_SCHEMA)
            conn.commit()
            self._conn = conn

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    @property
    def conn(self) -> Any:
        if not self._conn:
            raise RuntimeError("LogosStore not opened")
        return self._conn

    def _execute(self, sql: str, params: tuple = ()) -> Any:
        if self._pg_url:
            cur = self.conn.cursor()
            cur.execute(sql, params)
            return cur
        return self.conn.execute(sql, params)

    def _commit(self) -> None:
        self.conn.commit()

    # ── snapshots ──────────────────────────────────────────────────────────

    def save_snapshot(self, data: dict) -> None:
        cur = self._execute(
            "INSERT INTO federation_snapshots (payload) VALUES (?)"
            if not self._pg_url else
            "INSERT INTO federation_snapshots (payload) VALUES (%s)",
            (json.dumps(data, default=str),),
        )
        if self._pg_url:
            cur.close()
        self._commit()

    def recent_snapshots(self, limit: int = 24) -> list[dict]:
        cur = self._execute(
            "SELECT captured_at, payload FROM federation_snapshots "
            "ORDER BY captured_at DESC LIMIT ?" if not self._pg_url else
            "SELECT captured_at, payload FROM federation_snapshots "
            "ORDER BY captured_at DESC LIMIT %s",
            (limit,),
        )
        rows = cur.fetchall()
        if self._pg_url:
            cur.close()
        return [{"captured_at": r[0], **json.loads(r[1])} for r in rows]

    def prune_snapshots(self, retention_days: int) -> None:
        cutoff = max(7, retention_days)
        # Postgres: the interval cannot be a bound parameter inside a literal
        # ('%s days' would be quoted into the string), and captured_at is TEXT,
        # so build the cutoff with make_interval() and compare formatted text.
        cur = self._execute(
            "DELETE FROM federation_snapshots WHERE captured_at < datetime('now', ?)"
            if not self._pg_url else
            "DELETE FROM federation_snapshots WHERE captured_at < to_char("
            "(now() AT TIME ZONE 'utc') - make_interval(days => %s), "
            "'YYYY-MM-DD HH24:MI:SS')",
            (f"-{cutoff} days",) if not self._pg_url else (cutoff,),
        )
        if self._pg_url:
            cur.close()
        self._commit()

    # ── anomalies ─────────────────────────────────────────────────────────

    def save_anomaly(self, a: Anomaly) -> None:
        cur = self._execute(
            "INSERT OR IGNORE INTO anomaly_log "
            "(anomaly_id, metric, hub_url, severity, z_score, observed_value, "
            "expected_value, description, detected_at, acknowledged) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)"
            if not self._pg_url else
            "INSERT INTO anomaly_log "
            "(anomaly_id, metric, hub_url, severity, z_score, observed_value, "
            "expected_value, description, detected_at, acknowledged) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
            (
                a.anomaly_id, a.metric, a.hub_url, a.severity.value,
                a.z_score, a.observed_value, a.expected_value, a.description,
                a.detected_at, int(a.acknowledged),
            ),
        )
        if self._pg_url:
            cur.close()
        self._commit()

    def get_anomalies(self, acknowledged: bool | None = False) -> list[Anomaly]:
        if acknowledged is False:
            where, param = ("WHERE acknowledged = 0", ())
        elif acknowledged is True:
            where, param = ("WHERE acknowledged = 1", ())
        else:
            where, param = ("", ())
        # Explicit column list, not SELECT * — the row order must not depend on
        # the physical column order of whichever dialect created the table.
        cols = [
            "anomaly_id", "metric", "hub_url", "severity", "z_score",
            "observed_value", "expected_value", "description", "detected_at",
            "acknowledged", "acknowledged_at",
        ]
        cur = self._execute(
            f"SELECT {', '.join(cols)} FROM anomaly_log {where} "
            "ORDER BY detected_at DESC LIMIT 100",
            param,
        )
        rows = cur.fetchall()
        if self._pg_url:
            cur.close()
        return [_row_to_anomaly(dict(zip(cols, r))) for r in rows]

    def acknowledge_anomaly(self, anomaly_id: str) -> bool:
        cur = self._execute(
            "UPDATE anomaly_log SET acknowledged=1, acknowledged_at=datetime('now') "
            "WHERE anomaly_id=? AND acknowledged=0"
            if not self._pg_url else
            # NOW() is timestamptz; acknowledged_at is TEXT and Postgres has no
            # implicit assignment cast between them — format it explicitly.
            f"UPDATE anomaly_log SET acknowledged=1, acknowledged_at={_PG_TS_NOW} "
            "WHERE anomaly_id=%s AND acknowledged=0",
            (anomaly_id,),
        )
        ok = cur.rowcount > 0
        if self._pg_url:
            cur.close()
        self._commit()
        return ok

    # ── reports ───────────────────────────────────────────────────────────

    def save_report(self, report: DailyReport) -> None:
        cur = self._execute(
            "INSERT OR REPLACE INTO daily_reports (report_id, date, generated_at, payload) "
            "VALUES (?,?,?,?)"
            if not self._pg_url else
            "INSERT INTO daily_reports (report_id, date, generated_at, payload) "
            "VALUES (%s,%s,%s,%s) ON CONFLICT (report_id) DO UPDATE SET "
            "generated_at=EXCLUDED.generated_at, payload=EXCLUDED.payload",
            (report.report_id, report.date, report.generated_at, report.model_dump_json()),
        )
        if self._pg_url:
            cur.close()
        self._commit()

    def get_report(self, date: str) -> DailyReport | None:
        cur = self._execute(
            "SELECT payload FROM daily_reports WHERE date=? ORDER BY generated_at DESC LIMIT 1"
            if not self._pg_url else
            "SELECT payload FROM daily_reports WHERE date=%s ORDER BY generated_at DESC LIMIT 1",
            (date,),
        )
        row = cur.fetchone()
        if self._pg_url:
            cur.close()
        if row:
            return DailyReport.model_validate_json(row[0])
        return None

    # ── insights ──────────────────────────────────────────────────────────

    def save_insight(self, insight: Insight, query: str = "") -> None:
        # Upsert: same content-addressed insight_id refreshes payload/timestamp
        # instead of stacking duplicates (or being silently ignored forever).
        if self._pg_url:
            cur = self._execute(
                "INSERT INTO insight_log (insight_id, kind, query_text, payload, created_at) "
                "VALUES (%s,%s,%s,%s," + _PG_TS_NOW + ") "
                "ON CONFLICT (insight_id) DO UPDATE SET "
                "kind = EXCLUDED.kind, query_text = EXCLUDED.query_text, "
                "payload = EXCLUDED.payload, created_at = " + _PG_TS_NOW,
                (insight.insight_id, insight.kind.value, query, insight.model_dump_json()),
            )
            cur.close()
        else:
            self._execute(
                "INSERT INTO insight_log (insight_id, kind, query_text, payload, created_at) "
                "VALUES (?,?,?,?,datetime('now')) "
                "ON CONFLICT(insight_id) DO UPDATE SET "
                "kind=excluded.kind, query_text=excluded.query_text, "
                "payload=excluded.payload, created_at=datetime('now')",
                (insight.insight_id, insight.kind.value, query, insight.model_dump_json()),
            )
        self._commit()

    def recent_insights(self, limit: int = 20) -> list[Insight]:
        # Pull a wider window then collapse identical (kind, title) — legacy rows
        # still have unique timestamp ids for the same Federation overview.
        fetch = max(limit * 5, 40)
        if self._pg_url:
            cur = self._execute(
                "SELECT payload FROM insight_log "
                "ORDER BY created_at DESC, ctid DESC LIMIT %s",
                (fetch,),
            )
        else:
            cur = self._execute(
                "SELECT payload FROM insight_log "
                "ORDER BY created_at DESC, rowid DESC LIMIT ?",
                (fetch,),
            )
        rows = cur.fetchall()
        if self._pg_url:
            cur.close()
        out: list[Insight] = []
        seen: set[tuple[str, str]] = set()
        for r in rows:
            insight = Insight.model_validate_json(r[0])
            key = (insight.kind.value, insight.title.strip().lower())
            if key in seen:
                continue
            seen.add(key)
            out.append(insight)
            if len(out) >= limit:
                break
        return out

    def recent_insight_queries(self, limit: int = 10) -> list[dict]:
        """Return (kind, query_text, created_at) for recent queries.

        The assistant context needs the stored query text, which is a column
        of its own rather than part of the serialised Insight payload.
        """
        cur = self._execute(
            "SELECT kind, query_text, created_at FROM insight_log "
            "ORDER BY created_at DESC LIMIT ?"
            if not self._pg_url else
            "SELECT kind, query_text, created_at FROM insight_log "
            "ORDER BY created_at DESC LIMIT %s",
            (limit,),
        )
        rows = cur.fetchall()
        if self._pg_url:
            cur.close()
        return [
            {"kind": r[0], "query_text": r[1] or "", "created_at": r[2] or ""}
            for r in rows
        ]


def _row_to_anomaly(d: dict) -> Anomaly:
    d["acknowledged"] = bool(d.get("acknowledged", 0))
    return Anomaly(**d)
