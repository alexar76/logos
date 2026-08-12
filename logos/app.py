"""LOGOS FastAPI application.

Routes:
  GET  /health                          — service health
  GET  /api/v1/snapshot                 — current federation state
  POST /api/v1/ask                      — NL query → insights
  GET  /api/v1/insights                 — recent insights
  GET  /api/v1/report/daily             — today's briefing
  GET  /api/v1/anomalies                — anomalies (status=open|acknowledged|all)
  POST /api/v1/anomalies/{id}/acknowledge
  GET  /api/v1/trend                    — metric time-series from snapshots
  GET  /api/v1/consumption              — measured settlement + catalog-pricing digest
  GET  /api/v1/federation/peers         — hub peer list
  GET  /api/v1/federation/capabilities  — federated capability catalog
  POST /api/v1/federation/invoke        — NEXUS read-only invoke proxy
  GET  /.well-known/agent-card.json     — A2A agent card
  POST /api/v1/a2a/tasks                — A2A analytics.ask delegation
  POST /api/v1/chat                     — AI assistant (non-streaming)
  POST /api/v1/chat/stream              — AI assistant (SSE streaming)
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import time
from collections import defaultdict
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from logos.agent.assistant import LogosAssistant
from logos.agent.config import AgentConfig
from logos.agent.guard import InputGuard
from logos.analyst.engine import AnalystEngine
from logos.anomalies.detector import AnomalyDetector
from logos.config import LogosConfig
from logos.models import AskRequest
from logos.store import LogosStore


# Request/response models at module scope — FastAPI generates the schema from
# them, so they must not be nested inside create_app().
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)


class ChatResponse(BaseModel):
    reply: str
    guard_verdict: str = "allow"


logger = logging.getLogger("logos")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s %(message)s")


def _client_key(request: Request) -> str:
    """Who to rate-limit.

    `request.client.host` is the nginx address for every public caller, because the
    app binds loopback and the edge is the only way in — so one bucket was shared by
    the entire internet and a single eager poller 429'd everyone else. (The Alien
    Monitor did exactly that: four endpoints on a 1.5 s tick.) The edge sets
    X-Real-IP / X-Forwarded-For, and nothing else can reach this process, so the
    header is the trustworthy identity here and the socket address is not.
    """
    real = (request.headers.get("x-real-ip") or "").strip()
    if real:
        return real
    fwd = (request.headers.get("x-forwarded-for") or "").strip()
    if fwd:
        # Leftmost is the original client; the rest are proxies.
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def create_app(config: LogosConfig | None = None) -> FastAPI:
    cfg = config or LogosConfig.from_env()
    store = LogosStore(cfg.data_dir)
    engine = AnalystEngine(cfg)
    detector = AnomalyDetector(
        z_threshold=cfg.anomaly_zscore_threshold,
        min_samples=cfg.anomaly_min_samples,
        window_days=cfg.anomaly_window_days,
        poll_interval_s=cfg.poll_interval_s,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        store.open()
        app.state.store = store
        app.state.engine = engine
        app.state.detector = detector
        app.state.cfg = cfg

        # Rebuild the statistical baseline from real persisted telemetry so a
        # process restart does not erase anomaly context. Generated alerts are
        # discarded during warm-up; only the rolling observations are restored.
        warm_limit = max(cfg.anomaly_min_samples, min(
            cfg.anomaly_window_days * 24 * 3600 // max(1, cfg.poll_interval_s),
            50_000,
        ))
        for saved in reversed(store.recent_snapshots(warm_limit)):
            detector.ingest_snapshot(
                saved,
                saved.get("findings", {}),
                saved.get("treasury", {}),
            )

        # Background poll task
        poll_task = asyncio.create_task(_poll_loop(store, engine, detector, cfg))

        yield

        poll_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await poll_task
        store.close()

    app = FastAPI(
        title="LOGOS — Federation Analytics Engine",
        description="Cross-hub analytics, anomaly detection, and NL insights.",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS — reject * with credentials
    origins = [o.strip() for o in cfg.cors_origins.split(",") if o.strip()]
    if "*" in origins and len(origins) > 1:
        logger.warning("CORS: '*' mixed with specific origins — removing '*'")
        origins = [o for o in origins if o != "*"]
    if "*" in origins:
        allow_credentials = False
    else:
        allow_credentials = True
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── auth middleware ──────────────────────────────────────────────────
    # Shared token from LOGOS_API_TOKEN env. When set, every /api/ route
    # requires X-Logos-Token header.  When unset (the default), API is open
    # — appropriate for the localhost-only federation tier behind nginx.
    _API_TOKEN = os.environ.get("LOGOS_API_TOKEN", "").strip()

    @app.middleware("http")
    async def _auth_middleware(request: Request, call_next):
        if _API_TOKEN and request.url.path.startswith("/api/"):
            if request.headers.get("X-Logos-Token") != _API_TOKEN:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "X-Logos-Token header required"},
                )
        return await call_next(request)

    # ── simple in-memory rate limiter ─────────────────────────────────────
    # Per-IP token bucket, resets every window_s.  Lightweight — no Redis
    # needed for the federation tier (single-digit concurrent users).
    _RATE_WINDOW_S = int(os.environ.get("LOGOS_RATE_WINDOW_S", "60"))
    _RATE_MAX = int(os.environ.get("LOGOS_RATE_MAX", "30"))
    _rate_buckets: dict[str, list[float]] = defaultdict(list)

    @app.middleware("http")
    async def _rate_limit_middleware(request: Request, call_next):
        if not request.url.path.startswith("/api/"):
            return await call_next(request)
        ip = _client_key(request)
        now = time.monotonic()
        # Sweep stale IPs once the table grows past 1000 entries
        if len(_rate_buckets) > 1000:
            stale = [k for k, v in _rate_buckets.items() if not v or v[-1] < now - _RATE_WINDOW_S * 2]
            for k in stale:
                del _rate_buckets[k]
        bucket = _rate_buckets[ip]
        cutoff = now - _RATE_WINDOW_S
        while bucket and bucket[0] < cutoff:
            bucket.pop(0)
        if len(bucket) >= _RATE_MAX:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded", "retry_after_s": _RATE_WINDOW_S},
            )
        bucket.append(now)
        return await call_next(request)

    # ── routes ────────────────────────────────────────────────────────────

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "logos", "version": "0.1.0"}

    @app.get("/api/v1/snapshot")
    async def snapshot():
        engine: AnalystEngine = app.state.engine
        results = await engine.snapshot()
        hub = results.get("hub", {})
        momus = results.get("momus", {})
        treasury = results.get("treasury", {})
        return {
            **hub,
            "findings": momus,
            "treasury": treasury,
        }

    @app.post("/api/v1/ask")
    async def ask(req: AskRequest):
        engine: AnalystEngine = app.state.engine
        store: LogosStore = app.state.store
        # Guard /ask queries too: an attacker can POST an injection payload
        # here, it lands in insight_log.query_text, and the assistant later
        # embeds it in its system prompt.
        guard = InputGuard()
        gv = guard.check(req.query)
        if gv.action.value == "block":
            raise HTTPException(status_code=400, detail=f"Query blocked: {gv.reason}")
        # Sanitize before storing: strip injection markers, cap length
        safe_query = req.query[:200].replace("\n", " ").replace("\r", "")
        resp = await engine.ask(req)
        for insight in resp.insights:
            store.save_insight(insight, safe_query)
        return resp

    @app.get("/api/v1/insights")
    async def insights(since: str = Query(default=""), limit: int = Query(default=20, le=100)):
        store: LogosStore = app.state.store
        items = store.recent_insights(limit)
        if since:
            items = [i for i in items if i.generated_at >= since]
        return {"insights": [i.model_dump() for i in items]}

    @app.get("/api/v1/report/daily")
    async def daily_report():
        engine: AnalystEngine = app.state.engine
        store: LogosStore = app.state.store
        # Fetch latest data
        results = await engine.snapshot()
        hub = results.get("hub", {})
        momus = results.get("momus", {})
        skopos = results.get("skopos", {})
        treasury = results.get("treasury", {})
        anomalies_list = store.get_anomalies(acknowledged=False)
        recent = store.recent_insights(10)

        report = await engine.daily_report(
            snapshot=hub, findings=momus, remediation=skopos,
            treasury=treasury, anomalies=anomalies_list, recent_insights=recent,
        )
        store.save_report(report)
        return report

    @app.get("/api/v1/anomalies")
    async def anomalies(status: str = Query(default="open", pattern="^(open|acknowledged|all)$")):
        """List anomalies.

        ``status=open`` (default) returns unacknowledged alerts — the operator's
        working set. ``acknowledged`` returns the handled ones, ``all`` returns
        both, which is what the history heatmap needs.
        """
        store: LogosStore = app.state.store
        wanted = {"open": False, "acknowledged": True, "all": None}[status]
        items = store.get_anomalies(acknowledged=wanted)
        return {"anomalies": [a.model_dump() for a in items]}

    @app.post("/api/v1/anomalies/{anomaly_id}/acknowledge")
    async def acknowledge_anomaly(anomaly_id: str):
        store: LogosStore = app.state.store
        ok = store.acknowledge_anomaly(anomaly_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Anomaly not found or already acknowledged")
        return {"status": "ok", "anomaly_id": anomaly_id}

    @app.get("/api/v1/federation/peers")
    async def federation_peers():
        results = await engine.snapshot()
        hub = results.get("hub", {})
        return {"peers": hub.get("peers", []), "total": hub.get("total_hubs")}

    @app.get("/api/v1/trend")
    async def trend(metric: str = Query(default="total_capabilities"), limit: int = Query(default=24, le=100)):
        """Return time-series of a metric from stored snapshots."""
        store: LogosStore = app.state.store
        snapshots = store.recent_snapshots(limit)
        points = []
        for s in reversed(snapshots):
            try:
                # ``recent_snapshots`` returns the stored payload flattened next
                # to ``captured_at``.  Missing/None metrics are unavailable, not
                # zero-valued observations, and must not enter a trend line.
                if metric not in s or s[metric] is None:
                    continue
                points.append({"ts": s.get("captured_at", ""), "v": float(s[metric])})
            except (TypeError, ValueError):
                continue
        return {"metric": metric, "points": points}

    @app.get("/api/v1/consumption")
    async def consumption():
        """Federation-wide LLM consumption — spend, invocations, per-hub breakdown."""
        from logos.sources.consumption import ConsumptionSource
        src = ConsumptionSource(cfg.hub_url, cfg.hub_timeout_s)
        return await src.fetch()

    @app.get("/api/v1/federation/capabilities")
    async def federation_capabilities():
        """Return the federated capability catalog from the hub manifest."""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=cfg.hub_timeout_s) as c:
                r = await c.get(f"{cfg.hub_url.rstrip('/')}/ai-market/v2/manifest")
                r.raise_for_status()
                manifest = r.json()
                tools = manifest.get("tools", [])
                return {
                    "capabilities": [
                        {
                            "capability_id": t.get("capability_id", ""),
                            "description": t.get("description", ""),
                            "price_per_call_usd": t.get("routed_price_usd") if t.get("routed_price_usd") is not None else t.get("price_per_call_usd"),
                            "provider_hub": t.get("source_hub") or t.get("provider_hub", ""),
                        }
                        for t in tools
                    ],
                    "total": len(tools),
                    "hubs_indexed": manifest.get("hubs_indexed"),
                }
        except Exception:
            return {"capabilities": [], "total": 0, "hubs_indexed": 0, "error": "hub unreachable"}

    @app.post("/api/v1/federation/invoke")
    async def federation_invoke(request: Request):
        """Proxy a hub.invoke call — the NEXUS playground's one-button invoke."""
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON body")
        capability_id = body.get("capability_id", "")
        inp = body.get("input", {})
        if not capability_id:
            raise HTTPException(status_code=400, detail="capability_id required")
        if not _is_read_only_capability(capability_id):
            raise HTTPException(
                status_code=403,
                detail="LOGOS NEXUS is read-only; mutating capability refused",
            )
        try:
            import httpx
            async with httpx.AsyncClient(timeout=cfg.hub_timeout_s) as c:
                r = await c.post(
                    f"{cfg.hub_url.rstrip('/')}/ai-market/v2/invoke",
                    json={
                        "product_id": capability_id.rsplit("@", 1)[0] if "@" in capability_id else capability_id,
                        "capability_id": capability_id,
                        "input": inp,
                    },
                )
                r.raise_for_status()
                data = r.json()
                return {
                    "status": "ok",
                    "result": data.get("result", data.get("output", data)),
                    "price_usd": data.get("price_usd"),
                    "routing_fee_usd": data.get("routing_fee_usd"),
                    "source": data.get("source", "hub"),
                    "verifiable": data.get("verifiable"),
                    "routed_via": cfg.hub_url,
                }
        except Exception as exc:
            return {"status": "error", "error": str(exc)[:200]}

    # ── A2A agent card ────────────────────────────────────────────────

    @app.get("/.well-known/agent-card.json")
    async def agent_card_endpoint():
        from logos.a2a import agent_card
        return agent_card(cfg.public_url)

    @app.post("/api/v1/a2a/tasks")
    async def a2a_tasks(request: Request):
        """A2A tasks endpoint — accepts analytics.ask skill delegations."""
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON body")
        skill = body.get("skill", "")
        if skill != "analytics.ask":
            raise HTTPException(status_code=400, detail=f"Unknown skill: {skill}")
        q = body.get("input", {}).get("query", "")
        if not q:
            raise HTTPException(status_code=400, detail="Missing query in task input")
        verdict = InputGuard().check(q)
        if verdict.action.value == "block":
            raise HTTPException(status_code=400, detail=f"Query blocked: {verdict.reason}")
        engine: AnalystEngine = app.state.engine
        resp = await engine.ask(AskRequest(query=q[:8000], max_insights=5))
        return {
            "status": "completed",
            "output": {
                "insights": [i.model_dump() for i in resp.insights],
                "interpreted_intent": resp.interpreted_intent.value,
            },
        }

    # ── AI assistant routes ─────────────────────────────────────────

    @app.post("/api/v1/chat")
    async def chat(req: ChatRequest):
        """Non-streaming chat with the LOGOS AI assistant."""
        assistant = LogosAssistant(
            store=app.state.store,
            config=AgentConfig.from_env(),
        )
        reply = await assistant.chat(req.message)
        return ChatResponse(reply=reply)

    @app.post("/api/v1/chat/stream")
    async def chat_stream(req: ChatRequest):
        """SSE-streaming chat with the LOGOS AI assistant."""
        assistant = LogosAssistant(
            store=app.state.store,
            config=AgentConfig.from_env(),
        )

        async def _stream():
            async for token in assistant.chat_stream(req.message):
                safe = token.replace("\n", " ").replace("\r", "")
                yield f"data: {safe}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            _stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    return app


_MUTATING_CAPABILITY_TOKENS = frozenset({
    "delete", "remove", "drop", "write", "create", "update", "patch",
    "deploy", "remediate", "pay", "payout", "transfer", "withdraw",
    "deposit", "mint", "burn", "sign", "execute", "submit", "publish",
    "acknowledge", "trigger", "start", "stop", "restart", "rotate",
})


def _is_read_only_capability(capability_id: str) -> bool:
    """Conservative boundary for the public NEXUS proxy.

    Capability identifiers are dot/slash/dash separated in the federation.
    Unknown verbs are allowed for discovery compatibility, while explicit
    mutation verbs are refused before any network request is made.
    """
    import re
    tokens = {p for p in re.split(r"[^a-z0-9]+", capability_id.lower()) if p}
    return not bool(tokens & _MUTATING_CAPABILITY_TOKENS)


# ── background poll loop ──────────────────────────────────────────────────────

async def _poll_loop(
    store: LogosStore,
    engine: AnalystEngine,
    detector: AnomalyDetector,
    cfg: LogosConfig,
) -> None:
    """Periodically refresh federation data, detect anomalies, and generate
    the daily report at the configured hour."""
    last_report_date: str = ""

    while True:
        try:
            results = await engine.snapshot()
            hub = results.get("hub", {})
            momus = results.get("momus", {})
            treasury = results.get("treasury", {})

            merged = {**hub, "findings": momus, "treasury": treasury}
            store.save_snapshot(merged)

            # Detect anomalies — pass treasury for balance tracking
            new_anomalies = detector.ingest_snapshot(hub, momus, treasury)
            for a in new_anomalies:
                store.save_anomaly(a)

            # Telegram alerts for new anomalies (same bot as SKOPOS)
            tg_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
            tg_chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
            for a in new_anomalies:
                if tg_token and tg_chat and a.severity.value in ("critical", "high"):
                    from logos.telegram import send_anomaly_alert
                    await send_anomaly_alert(
                        tg_token, tg_chat, a.metric, a.severity.value,
                        a.z_score, a.description, a.detected_at,
                    )
            if new_anomalies:
                logger.info("Detected %d new anomalies", len(new_anomalies))

            # Daily report at the configured hour
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            today = now.strftime("%Y-%m-%d")
            if now.hour == cfg.daily_report_hour and today != last_report_date:
                report = await engine.daily_report(
                    snapshot=hub, findings=momus,
                    remediation={}, treasury=treasury,
                    anomalies=store.get_anomalies(acknowledged=False),
                    recent_insights=store.recent_insights(10),
                )
                store.save_report(report)
                last_report_date = today
                logger.info("Generated daily report: %s", report.report_id)

                # Telegram daily report (same bot as SKOPOS)
                if tg_token and tg_chat:
                    from logos.telegram import send_daily_report
                    await send_daily_report(
                        tg_token, tg_chat,
                        report.summary,
                        [k.model_dump() for k in report.kpis],
                        len(report.anomalies),
                        report.overall_status,
                    )

            # Prune old snapshots beyond retention window (uses dual-dialect store method)
            try:
                store.prune_snapshots(cfg.snapshot_retention_days)
            except Exception:
                pass

        except Exception as exc:
            logger.warning("Poll cycle failed: %s", exc)

        await asyncio.sleep(cfg.poll_interval_s)
