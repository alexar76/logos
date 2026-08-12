"""Unit tests for the LOGOS anomaly detector."""

from logos.anomalies.detector import AnomalyDetector


class TestAnomalyDetector:
    def _stable_data(self):
        return (
            {"total_hubs": 5, "healthy_hubs": 5, "total_capabilities": 100, "federated_capabilities": 50},
            {"total_findings": 10, "recurring": 2, "by_severity": {"critical": 0, "high": 1, "medium": 3}},
            {},
        )

    def test_no_anomaly_on_stable_data(self):
        d = AnomalyDetector(z_threshold=3.0, min_samples=3, window_days=30)
        for _ in range(10):
            snap, find, treas = self._stable_data()
            anoms = d.ingest_snapshot(snap, find, treas)
            assert len(anoms) == 0

    def test_detects_spike(self):
        d = AnomalyDetector(z_threshold=2.0, min_samples=5, window_days=30)
        for _ in range(6):
            snap, find, treas = self._stable_data()
            d.ingest_snapshot(snap, find, treas)
        anoms = d.ingest_snapshot(
            {"total_hubs": 5, "healthy_hubs": 5, "total_capabilities": 100, "federated_capabilities": 50},
            {"total_findings": 50, "recurring": 8, "by_severity": {"critical": 5, "high": 10, "medium": 15}},
            {},
        )
        assert len(anoms) > 0

    def test_not_enough_samples(self):
        d = AnomalyDetector(z_threshold=2.0, min_samples=10, window_days=30)
        anoms = d.ingest_snapshot(
            {"total_hubs": 5, "healthy_hubs": 5, "total_capabilities": 100, "federated_capabilities": 50},
            {"total_findings": 500, "recurring": 0, "by_severity": {}},
            {},
        )
        assert len(anoms) == 0

    def test_extract_metrics(self):
        d = AnomalyDetector()
        m = d._extract_metrics(
            {"total_hubs": 5, "healthy_hubs": 4, "total_capabilities": 200, "federated_capabilities": 150},
            {"total_findings": 12, "recurring": 3, "by_severity": {"critical": 1, "high": 2, "medium": 4}},
            {"available_usd": 5000.0},
        )
        assert m["total_hubs"] == 5
        assert m["healthy_hubs"] == 4
        assert m["findings_critical"] == 1
        assert m["treasury_available_usd"] == 5000.0

    def test_stdev(self):
        d = AnomalyDetector()
        assert d._stdev([1, 1, 1], 1) == 0.0
        assert d._stdev([1, 2, 3], 2) > 0.8

    def test_classify(self):
        d = AnomalyDetector()
        assert d._classify(5.5).value == "critical"
        assert d._classify(4.2).value == "high"
        assert d._classify(3.1).value == "medium"
        assert d._classify(2.0).value == "info"

    def test_unreachable_sources_do_not_become_zero_measurements(self):
        d = AnomalyDetector()
        metrics = d._extract_metrics(
            {"status": "unreachable", "total_hubs": 0},
            {"status": "unreachable", "total_findings": 0},
            {"status": "unreachable", "available_usd": 0},
        )
        assert metrics == {}

    def test_candidate_is_not_included_in_its_own_baseline(self):
        d = AnomalyDetector(z_threshold=2.0, min_samples=5)
        baseline = [99, 100, 101, 100, 99]
        for value in baseline:
            d.ingest_snapshot({"total_hubs": value}, {}, {})
        anomalies = d.ingest_snapshot({"total_hubs": 130}, {}, {})
        assert any(a.metric == "total_hubs" for a in anomalies)
