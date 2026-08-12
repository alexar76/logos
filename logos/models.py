"""LOGOS data models — Pydantic v2, every field documented.

These are the WIRE MODELS. The store may add denormalised columns, but the API
surface and the source adapters speak these types.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── severity ladder (mirrors MOMUS) ──────────────────────────────────────────

class Severity(str, Enum):
    info = "info"
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class InsightKind(str, Enum):
    economy = "economy"
    security = "security"
    latency = "latency"
    reputation = "reputation"
    general = "general"


# ── federation snapshot ──────────────────────────────────────────────────────

class HubPeer(BaseModel):
    url: str
    name: str = ""
    capabilities_count: int = 0
    trust_score: float = 0.0
    last_crawl: str = ""
    depth: int = 0
    categories: List[str] = Field(default_factory=list)
    healthy: bool = True
    latency_ms: Optional[float] = None


class FederationSnapshot(BaseModel):
    generated_at: str = ""  # ISO 8601
    total_hubs: int = 0
    healthy_hubs: int = 0
    total_capabilities: int = 0
    local_capabilities: int = 0
    federated_capabilities: int = 0
    peers: List[HubPeer] = Field(default_factory=list)
    anomaly_count: int = 0


# ── findings digest ──────────────────────────────────────────────────────────

class FindingDigest(BaseModel):
    """Aggregated MOMUS findings — one row per hub in the federation."""
    hub_url: str = ""
    hub_name: str = ""
    total_findings: int = 0
    by_severity: Dict[str, int] = Field(default_factory=dict)
    new_24h: int = 0
    recurring: int = 0
    top_probes: List[str] = Field(default_factory=list)
    top_categories: List[str] = Field(default_factory=list)
    status: str = "ok"  # ok | unreachable | no_data


# ── remediation digest ───────────────────────────────────────────────────────

class RemediationDigest(BaseModel):
    hub_url: str = ""
    total_jobs: int = 0
    closed: int = 0
    confirmed_fixed: int = 0
    escalated: int = 0
    orders_signed: int = 0
    avg_cycle_hours: Optional[float] = None
    status: str = "ok"


# ── treasury digest ──────────────────────────────────────────────────────────

class TreasuryDigest(BaseModel):
    hub_url: str = ""
    balance_usd: Optional[float] = None
    reserved_usd: Optional[float] = None
    available_usd: Optional[float] = None
    payouts_24h: int = 0
    payout_volume_24h_usd: float = 0.0
    projected_depletion_days: Optional[float] = None
    settlement_mode: str = ""
    status: str = "ok"


# ── reputation digest ────────────────────────────────────────────────────────

class ReputationDigest(BaseModel):
    hub_url: str = ""
    trust_score: float = 0.0
    rank: int = 0
    of: int = 0
    events_24h: int = 0
    recent_slashes: int = 0
    recently_downgraded: bool = False
    status: str = "ok"


# ── insight (the product) ────────────────────────────────────────────────────

class DataSource(BaseModel):
    """Which source contributed to this insight."""
    name: str  # e.g. "MOMUS", "Hub", "Lumen"
    hub_url: str = ""
    status: str = "ok"  # ok | degraded | unreachable


class Recommendation(BaseModel):
    priority: int = 1  # 1 = highest
    action: str = ""
    impact: str = ""
    verification: str = ""


class Insight(BaseModel):
    insight_id: str = ""  # logos-<hex12>
    kind: InsightKind = InsightKind.general
    title: str = ""
    severity: Severity = Severity.info
    summary: str = ""
    explanation: str = ""
    sources: List[DataSource] = Field(default_factory=list)
    recommendations: List[Recommendation] = Field(default_factory=list)
    raw_data: Dict[str, Any] = Field(default_factory=dict)
    generated_at: str = ""  # ISO 8601
    generated_by: str = ""  # "metis-council" | "rule-engine"


# ── anomaly ──────────────────────────────────────────────────────────────────

class Anomaly(BaseModel):
    anomaly_id: str = ""
    metric: str = ""  # e.g. "hub_latency_ms", "finding_rate"
    hub_url: str = ""
    severity: Severity = Severity.info
    z_score: float = 0.0
    observed_value: float = 0.0
    expected_value: float = 0.0
    description: str = ""
    detected_at: str = ""
    acknowledged: bool = False
    acknowledged_at: Optional[str] = None


# ── daily report ─────────────────────────────────────────────────────────────

class DailyReportKPI(BaseModel):
    label: str = ""
    value: str = ""
    status: str = "ok"  # ok | warn | critical


class DailyReport(BaseModel):
    report_id: str = ""
    date: str = ""  # YYYY-MM-DD
    generated_at: str = ""
    overall_status: str = "ok"  # ok | warn | critical
    summary: str = ""
    kpis: List[DailyReportKPI] = Field(default_factory=list)
    insights: List[Insight] = Field(default_factory=list)
    anomalies: List[Anomaly] = Field(default_factory=list)


# ── NL query ─────────────────────────────────────────────────────────────────

class AskRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=8000)
    max_insights: int = Field(default=5, ge=1, le=20)


class AskResponse(BaseModel):
    query: str = ""
    interpreted_intent: InsightKind = InsightKind.general
    insights: List[Insight] = Field(default_factory=list)
    taken_ms: float = 0.0
