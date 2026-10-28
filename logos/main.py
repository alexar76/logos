"""LOGOS entry point — ``python -m logos.main`` or ``uvicorn logos.main:app``."""

from __future__ import annotations

import os

import uvicorn

from logos.app import create_app
from logos.config import LogosConfig

app = create_app()


def main() -> None:
    cfg = LogosConfig.from_env()
    # Loopback unless told otherwise, as the other packages do: 0.0.0.0 answered whoever reached the
    # port (Vulnetix GCVE-110-VULN-PYPI-2026-000638). The container's own nginx reaches it over
    # loopback; serving other machines directly takes LOGOS_HOST=0.0.0.0.
    uvicorn.run(
        "logos.main:app",
        host=os.environ.get("LOGOS_HOST", "127.0.0.1"),
        port=cfg.port,
        reload=not cfg.prod,
        log_level="info" if cfg.prod else "debug",
    )


if __name__ == "__main__":
    main()
