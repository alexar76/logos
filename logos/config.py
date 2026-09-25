"""LOGOS — the federation analytics engine.

Reads what the federation already publishes; writes only its own store.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class LogosConfig:
    """Every setting from the environment. No file config needed — the ecosystem
    passes everything through env vars in the compose file."""

    # ── server ──
    port: int = field(default_factory=lambda: int(os.environ.get("LOGOS_PORT", "9460")))
    public_url: str = field(
        default_factory=lambda: os.environ.get("LOGOS_PUBLIC_URL", "http://127.0.0.1:9460")
    )
    cors_origins: str = field(
        default_factory=lambda: os.environ.get("LOGOS_CORS_ORIGINS", "http://127.0.0.1:5199")
    )
    data_dir: Path = field(
        default_factory=lambda: Path(os.environ.get("LOGOS_DATA_DIR", "data/logos"))
    )
    prod: bool = field(
        default_factory=lambda: os.environ.get("AIFACTORY_PROD", "").strip() == "1"
    )
    crypto_enabled: bool = field(
        default_factory=lambda: os.environ.get("AIFACTORY_CRYPTO_ENABLED", "").strip() == "1"
    )

    # ── hub ──
    hub_url: str = field(
        default_factory=lambda: os.environ.get("LOGOS_HUB_URL", os.environ.get("HUB_URL", "http://127.0.0.1:9083"))
    )
    hub_timeout_s: float = field(
        default_factory=lambda: float(os.environ.get("LOGOS_HUB_TIMEOUT_S", "15"))
    )

    # ── metis (optional — enables NL query understanding) ──
    metis_url: str | None = field(
        default_factory=lambda: os.environ.get("LOGOS_METIS_URL") or os.environ.get("METIS_URL")
    )
    metis_model: str = field(
        default_factory=lambda: os.environ.get("LOGOS_METIS_MODEL", "metis-fast")
    )

    # ── polling ──
    poll_interval_s: int = field(
        default_factory=lambda: int(os.environ.get("LOGOS_POLL_INTERVAL_S", "300"))
    )
    anomaly_window_days: int = field(
        default_factory=lambda: int(os.environ.get("LOGOS_ANOMALY_WINDOW_DAYS", "30"))
    )
    daily_report_hour: int = field(
        default_factory=lambda: int(os.environ.get("LOGOS_DAILY_REPORT_HOUR", "9"))
    )
    snapshot_retention_days: int = field(
        default_factory=lambda: int(os.environ.get("LOGOS_SNAPSHOT_RETENTION_DAYS", "90"))
    )

    # ── anomaly thresholds ──
    anomaly_zscore_threshold: float = field(
        default_factory=lambda: float(os.environ.get("LOGOS_ANOMALY_ZSCORE", "3.0"))
    )
    anomaly_min_samples: int = field(
        default_factory=lambda: int(os.environ.get("LOGOS_ANOMALY_MIN_SAMPLES", "7"))
    )

    # ── data sources (URLs for direct-poll services; hub.invoke covers the rest) ──
    momus_url: str | None = field(
        default_factory=lambda: os.environ.get("LOGOS_MOMUS_URL") or os.environ.get("MOMUS_URL")
    )
    skopos_url: str | None = field(
        default_factory=lambda: os.environ.get("LOGOS_SKOPOS_URL") or os.environ.get("SKOPOS_URL")
    )
    treasury_url: str | None = field(
        default_factory=lambda: os.environ.get("LOGOS_TREASURY_URL") or os.environ.get("TREASURY_URL")
    )
    lumen_url: str | None = field(
        default_factory=lambda: os.environ.get("LOGOS_LUMEN_URL") or os.environ.get("LUMEN_URL")
    )
    argus_url: str | None = field(
        default_factory=lambda: os.environ.get("LOGOS_ARGUS_URL") or os.environ.get("ARGUS_URL")
    )
    bridges_url: str | None = field(
        default_factory=lambda: os.environ.get("LOGOS_BRIDGES_URL")
    )

    def ensure_data_dir(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_env(cls) -> "LogosConfig":
        cfg = cls()
        cfg.ensure_data_dir()
        return cfg
