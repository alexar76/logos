"""MOMUS findings source."""

from __future__ import annotations

from typing import Any

import httpx

from logos.models import FindingDigest


class MomusSource:
    def __init__(self, url: str | None, timeout_s: float = 15) -> None:
        self._url = url.rstrip("/") if url else None
        self._timeout = timeout_s

    async def fetch_findings(self) -> dict:
        """Aggregated findings digest.  When MOMUS is unreachable the result
        says so rather than returning zeros — an absent count is not a zero count."""
        if not self._url:
            return {"status": "no_data", "hub_url": "", "total_findings": 0, "by_severity": {}}

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as c:
                health_r = await c.get(f"{self._url}/health")
                health_r.raise_for_status()
                health = health_r.json()

                findings_r = await c.get(f"{self._url}/findings")
                findings_r.raise_for_status()
                findings = findings_r.json()
        except Exception:
            return {"status": "unreachable", "hub_url": self._url, "total_findings": 0, "by_severity": {}}

        counts = findings.get("finding_counts") or findings.get("counts") or {}
        corpus = findings.get("corpus") or {}
        by_severity = {
            k: int(v)
            for k, v in counts.items()
            if isinstance(v, (int, float)) and k in {"critical", "high", "medium", "low", "info"}
        }

        # top probes / categories from the findings list
        findings_list = findings.get("findings") or []
        probe_counts: dict[str, int] = {}
        cat_counts: dict[str, int] = {}
        for f in findings_list[:200]:  # sample
            probe = f.get("probe", "")
            cat = f.get("category", "")
            if probe:
                probe_counts[probe] = probe_counts.get(probe, 0) + 1
            if cat:
                cat_counts[cat] = cat_counts.get(cat, 0) + 1

        return {
            "status": "ok",
            "hub_url": self._url,
            "total_findings": corpus.get("total_findings", sum(by_severity.values())),
            "by_severity": by_severity,
            "new_24h": 0,  # Not directly available — could be derived from created_at
            "recurring": corpus.get("recurring", 0),
            "top_probes": sorted(probe_counts, key=probe_counts.get, reverse=True)[:5],
            "top_categories": sorted(cat_counts, key=cat_counts.get, reverse=True)[:5],
        }
