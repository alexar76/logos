"""Statistical anomaly detector — rolling z-score over time-series snapshots.

No external deps (numpy/scipy not required). The murmuration consensus library
is a natural post-processing step for outlier-resistant aggregation, but the
detector itself uses pure-Python statistics.
"""

from __future__ import annotations

import hashlib
import math
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from logos.models import Anomaly, Severity


class AnomalyDetector:
    """Tracks time-series of per-metric values from snapshots and flags
    observations beyond ``z_threshold`` standard deviations from the rolling
    mean."""

    def __init__(
        self,
        z_threshold: float = 3.0,
        min_samples: int = 7,
        window_days: int = 30,
        poll_interval_s: int = 300,
    ) -> None:
        self._z = z_threshold
        self._min = min_samples
        self._window = window_days
        self._poll_interval = poll_interval_s
        # metric_key → list of (ts, value)
        self._history: dict[str, list[tuple[str, float]]] = defaultdict(list)

    def ingest_snapshot(self, snapshot: dict, findings: dict, treasury: dict | None = None) -> list[Anomaly]:
        """Feed the latest numbers; return any NEW anomalies detected right now."""
        now = datetime.now(timezone.utc).isoformat()
        anomalies: list[Anomaly] = []

        metrics = self._extract_metrics(snapshot, findings, treasury or {})
        for key, value in metrics.items():
            series = self._history[key]
            # Score the new observation against the PREVIOUS window. Including
            # the candidate in its own baseline systematically suppresses z.
            values = [v for _, v in series]
            if len(values) >= self._min:
                mean = sum(values) / len(values)
                std = self._stdev(values, mean)
                # A change from a perfectly stable baseline is maximally
                # informative, not invisible. Use a scale-aware numerical
                # floor so the score remains finite and JSON-safe.
                epsilon = max(abs(mean) * 1e-9, 1e-9)
                z = abs(value - mean) / max(std, epsilon)
                if z >= self._z:
                    anomalies.append(Anomaly(
                        anomaly_id=_anomaly_id(key, now),
                        metric=key,
                        hub_url=snapshot.get("hub_url", ""),
                        severity=self._classify(z),
                        z_score=round(z, 2),
                        observed_value=round(value, 4),
                        expected_value=round(mean, 4),
                        description=f"{key}: observed {value:.4f}, expected {mean:.4f} ± {std:.4f} (z={z:.1f})",
                        detected_at=now,
                    ))

            series.append((now, value))
            max_points = self._window * 24 * 3600 // max(1, self._poll_interval)
            if len(series) > max_points:
                del series[:-max_points]

        return anomalies

    # ── internal ──────────────────────────────────────────────────────────

    @staticmethod
    def _extract_metrics(snapshot: dict, findings: dict, treasury: dict) -> dict[str, float]:
        m: dict[str, float] = {}
        # Hub metrics
        if snapshot.get("status", "ok") == "ok":
            for key in ("total_hubs", "healthy_hubs", "total_capabilities", "federated_capabilities"):
                if isinstance(snapshot.get(key), (int, float)):
                    m[key] = float(snapshot[key])
        # Findings
        if findings.get("status", "ok") == "ok":
            if isinstance(findings.get("total_findings"), (int, float)):
                m["total_findings"] = float(findings["total_findings"])
            if isinstance(findings.get("recurring"), (int, float)):
                m["recurring_findings"] = float(findings["recurring"])
            by_sev = findings.get("by_severity", {})
            for s in ("critical", "high", "medium"):
                if isinstance(by_sev.get(s), (int, float)):
                    m[f"findings_{s}"] = float(by_sev[s])
        # Treasury — from treasury dict, not findings
        t_avail = treasury.get("available_usd")
        if treasury.get("status", "ok") == "ok" and isinstance(t_avail, (int, float)):
            m["treasury_available_usd"] = float(t_avail)
        return m

    @staticmethod
    def _stdev(values: list[float], mean: float) -> float:
        n = len(values)
        if n < 2:
            return 0.0
        return math.sqrt(sum((v - mean) ** 2 for v in values) / (n - 1))

    @staticmethod
    def _classify(z: float) -> Severity:
        if z >= 5.0:
            return Severity.critical
        if z >= 4.0:
            return Severity.high
        if z >= 3.0:
            return Severity.medium
        return Severity.info


def _anomaly_id(metric: str, ts: str) -> str:
    h = hashlib.sha256(f"{metric}{ts}".encode()).hexdigest()[:12]
    return f"anom-{h}"
