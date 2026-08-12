"""Intent planner — maps NL queries or structured questions to a data-source
execution plan.  When Metis is available the council does the heavy lifting;
otherwise a keyword-based fallback classifies and routes."""

from __future__ import annotations

import json
import re
from typing import Any

import httpx

from logos.models import InsightKind


# ── keyword fallback (always available) ──────────────────────────────────────

_INTENT_KEYWORDS: dict[InsightKind, list[str]] = {
    InsightKind.economy: [
        "money", "balance", "treasury", "payout", "bounty", "reward",
        "spend", "cost", "price", "usd", "usdc", "budget", "deposit",
        "reserve", "available", "fund", "fee", "volume", "revenue",
        "runway", "depletion", "how long",
        # RU — matches UI chips like «На сколько хватит казначейства?»
        "сколько денег", "баланс", "выплат", "бюджет", "казначей",
        "хватит", "казна", "treasury",
        # ES / FR / ZH
        "cuánto", "dinero", "saldo", "pago", "recompensa", "tesorería",
        "tesoreria", "durará", "durara",
        "trésorerie", "tresorerie", "combien", "combien de temps",
        "国库", "金库", "还能用多久", "预算", "余额",
    ],
    InsightKind.security: [
        "finding", "vulnerability", "exploit", "attack", "breach",
        "probe", "scan", "audit", "threat", "warden", "injection",
        "severity", "critical", "high", "remediation", "fix",
        "momus",
        # RU — «Есть критические находки?»
        "уязвимость", "атака", "сканирование", "аудит", "находк",
        "критическ", "момус", "momus",
        # ES / FR / ZH
        "vulnerabilidad", "ataque", "hallazgo", "escaneo", "crític", "critic",
        "vulnérabilit", "attaque", "constat", "critique",
        "发现", "漏洞", "关键", "严重",
    ],
    InsightKind.latency: [
        "slow", "latency", "timeout", "delay", "performance",
        "response time", "ms", "lag", "hang", "stuck", "bottleneck",
        "sluggish", "unresponsive",
        # RU — «Какие хабы тормозят?»
        "медленно", "задержка", "тормоз", "тормозит", "лаг", "долго",
        "отклик", "пинг", "ping",
        # ES / FR / ZH
        "latencia", "lenteur", "retraso", "lento", "lentos", "ralent",
        "retard", "lent",
        "延迟", "很慢", "卡顿", "慢",
    ],
    InsightKind.reputation: [
        "trust", "reputation", "score", "rank", "peer", "lumen",
        "downgrade", "slash", "reliability", "reliable", "trusted",
        # RU — «Кто самый надёжный хаб?»
        "доверие", "репутация", "рейтинг", "надёжн", "надежн", "честн",
        # ES / FR / ZH
        "confianza", "reputación", "reputacion", "fiable", "confiable",
        "confiance", "réputation", "reputation", "fiable",
        "信任", "声誉", "可靠", "最靠谱",
    ],
}

_INTENT_PATTERNS: dict[InsightKind, list[str]] = {
    InsightKind.economy: [
        r"how\s+much\s+(?:money|usd|usdc)",
        r"how\s+long\s+(?:will|can).*(?:treasury|money|fund|runway)",
        r"what\s+(?:is|are)\s+the\s+(?:balance|payout|treasury)",
        r"сколько\s+(?:денег|выплат|баланс)",
        r"(?:на\s+)?сколько\s+хватит",
        r"казначейств",
        r"(?:cuánto|cuánta)\s+(?:dinero|saldo|tiempo)",
        r"tesorer[ií]a",
        r"combien\s+de\s+temps",
        r"tr[eé]sorerie",
        r"国库|金库|还能用多久",
    ],
    InsightKind.security: [
        r"(?:any|how\s+many)\s+(?:finding|vulnerabilit|exploit)",
        r"what\s+(?:did\s+)?momus\s+(?:find|scan)",
        r"(?:критическ\w*\s+)?находк",
        r"(?:какие\s+)?(?:находки|уязвимости)",
        r"(?:hallazgos|vulnerabilidades)",
        r"критическ",
        r"(?:constats?|vulnérabilit)",
        r"发现|漏洞|严重",
    ],
    InsightKind.latency: [
        r"(?:why|what|which).*(?:slow|latency|timeout|lag|bottleneck)",
        r"(?:почему|что|какие?).*(?:медлен|задержк|тормоз|лаг|latenc)",
        r"тормоз",
        r"(?:hubs?|хабы?).*(?:slow|тормоз|lent|延迟)",
        r"(?:which|qué|quelles?).*(?:hubs?|хабы?).*(?:slow|tor|lent)",
        r"(?:lents?|ralent|retraso|latencia)",
        r"延迟|很慢|卡顿",
    ],
    InsightKind.reputation: [
        r"(?:most|least)\s+(?:trusted|reliable)",
        r"(?:who|which)\s+(?:has|is).*(?:trust|reputation|score|reliable)",
        r"(?:кто|какой).*(?:довери|репутац|над[её]жн)",
        r"над[её]жн",
        r"(?:más|mas)\s+(?:fiable|confiable|confiable)",
        r"(?:plus|le plus)\s+fiable",
        r"信任|可靠|最靠谱",
    ],
}


class IntentPlanner:
    """Classify a user query and select the data sources needed to answer it.

    Two modes:
    1. Metis council — the query is sent to Metis for council-based NL
       understanding and a structured plan is returned.
    2. Keyword fallback — fast, offline, deterministic classification.
    """

    def __init__(self, metis_url: str | None = None, timeout_s: float = 15) -> None:
        self._metis = metis_url.rstrip("/") if metis_url else None
        self._timeout = timeout_s

    async def plan(self, query: str) -> dict:
        """Return a plan dict: {intent, sources[], metis_used, confidence}."""
        if self._metis:
            plan = await self._plan_via_metis(query)
            if plan:
                return plan

        return self._plan_keyword(query)

    async def _plan_via_metis(self, query: str) -> dict | None:
        prompt = (
            "You are LOGOS, a federation analytics engine. Classify this query "
            "into one intent: economy, security, latency, reputation, or general. "
            "List which data sources to query: hub, momus, skopos, treasury, "
            "lumen, argus, bridges. Return JSON only:\n"
            '{"intent": "<intent>", "sources": ["<source>", ...], '
            '"structured_query": "<rewritten for data retrieval>"}\n\n'
            f"Query: {query}"
        )
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as c:
                r = await c.post(
                    f"{self._metis}/v1/chat/completions",
                    json={
                        "model": "metis-fast",
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 200,
                        "temperature": 0.0,
                    },
                )
                r.raise_for_status()
                body = r.json()
                content = body.get("choices", [{}])[0].get("message", {}).get("content", "")
                return self._parse_metis_response(content, query)
        except Exception:
            return None

    def _parse_metis_response(self, raw: str, query: str) -> dict | None:
        try:
            # Try JSON block first
            m = re.search(r"\{[^{}]*\}", raw, re.DOTALL)
            if m:
                parsed = json.loads(m.group(0))
                intent = self._validate_intent(parsed.get("intent", "general"))
                sources = parsed.get("sources", [])
                return {
                    "intent": intent,
                    "sources": [s for s in sources if isinstance(s, str)],
                    "structured_query": parsed.get("structured_query", query),
                    "metis_used": True,
                    "confidence": 0.85,
                }
        except (json.JSONDecodeError, KeyError):
            pass
        return None

    def _plan_keyword(self, query: str) -> dict:
        lower = query.lower()
        scores: dict[InsightKind, int] = {}
        for kind, keywords in _INTENT_KEYWORDS.items():
            scores[kind] = sum(1 for kw in keywords if kw in lower)

        for kind, patterns in _INTENT_PATTERNS.items():
            scores[kind] = scores.get(kind, 0) + sum(
                3 for p in patterns if re.search(p, lower)
            )

        best = max(scores, key=scores.get) if any(scores.values()) else InsightKind.general
        if scores.get(best, 0) == 0:
            best = InsightKind.general

        # Map intent → default sources
        source_map: dict[InsightKind, list[str]] = {
            InsightKind.economy: ["treasury", "hub", "bridges"],
            InsightKind.security: ["momus", "skopos", "argus"],
            InsightKind.latency: ["hub", "momus"],
            InsightKind.reputation: ["lumen", "hub"],
            InsightKind.general: ["hub", "momus", "treasury", "skopos"],
        }

        return {
            "intent": best.value,
            "sources": source_map.get(best, ["hub"]),
            "structured_query": query,
            "metis_used": False,
            "confidence": 0.6,
        }

    @staticmethod
    def _validate_intent(raw: str) -> str:
        try:
            InsightKind(raw)
            return raw
        except ValueError:
            return "general"
