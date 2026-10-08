"""LOGOS AI assistant — chat with full read-only access to the analytics store.

Pattern: SKOPOS's agent/analyst.py (structured prompt, fallback-first) +
         ARGUS Warden's input guard (deterministic first line).
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, AsyncIterator

import httpx

from logos.agent.config import AgentConfig
from logos.agent.context import LOGOS_KNOWLEDGE, build_assistant_context
from logos.agent.guard import GuardAction, InputGuard

if TYPE_CHECKING:  # pragma: no cover — typing only
    from logos.store import LogosStore

logger = logging.getLogger("logos.agent")

SYSTEM_PROMPT = """You are the LOGOS assistant — an AI analyst for the AIMarket federation.

{knowledge}

## Current state
{context}

## Instructions
Answer the operator's question clearly and concisely. Use the data above.
If the data does not contain the answer, say what you CAN see and suggest
what the operator should check. Never invent numbers or findings.

Format your response in Markdown. Use bullet lists for multiple items.
For severity, match the colours: 🔴 critical, 🟠 high, 🟡 medium, 🔵 info.
"""

FALLBACK_RESPONSES: dict[str, str] = {
    "guard_blocked": (
        "Your message was blocked by the input guard. This happens when a message "
        "matches known prompt-injection patterns. If this is a legitimate query, "
        "please rephrase it without system-prompt language."
    ),
    "llm_unreachable": (
        "The LLM provider is currently unreachable. I can still answer basic "
        "questions from the stored data — try asking about the federation "
        "snapshot, active anomalies, or recent insights."
    ),
    "no_api_key": (
        "No LLM API key is configured. Set `LOGOS_LLM_API_KEY` or "
        "`DEEPSEEK_API_KEY` in the environment to enable the AI assistant."
    ),
}


class LogosAssistant:
    """The LOGOS chat assistant. Reads the local store, sends context to the
    configured LLM provider, and streams the response back."""

    def __init__(self, store: LogosStore, config: AgentConfig | None = None) -> None:
        self._store = store
        self._cfg = config or AgentConfig.from_env()
        self._guard = InputGuard()

    async def chat(self, message: str) -> str:
        """Non-streaming chat — returns the full response."""
        verdict = self._guard.check(message)
        if verdict.action == GuardAction.BLOCK:
            logger.warning("guard blocked: gate=%s reason=%s", verdict.gate, verdict.reason)
            return FALLBACK_RESPONSES["guard_blocked"]

        if not self._cfg.api_key:
            return FALLBACK_RESPONSES["no_api_key"]

        context = build_assistant_context(self._store)
        system = SYSTEM_PROMPT.format(knowledge=LOGOS_KNOWLEDGE, context=context)
        if len(system) > self._cfg.max_context_chars:
            system = system[: self._cfg.max_context_chars]

        try:
            return await self._call_llm(system, message)
        except Exception as exc:
            logger.warning("LLM call failed: %s", exc)
            return FALLBACK_RESPONSES["llm_unreachable"]

    async def chat_stream(self, message: str) -> AsyncIterator[str]:
        """Streaming chat — yields tokens as they arrive."""
        verdict = self._guard.check(message)
        if verdict.action == GuardAction.BLOCK:
            yield FALLBACK_RESPONSES["guard_blocked"]
            return

        if not self._cfg.api_key:
            yield FALLBACK_RESPONSES["no_api_key"]
            return

        context = build_assistant_context(self._store)
        system = SYSTEM_PROMPT.format(knowledge=LOGOS_KNOWLEDGE, context=context)
        if len(system) > self._cfg.max_context_chars:
            system = system[: self._cfg.max_context_chars]

        try:
            async for token in self._call_llm_stream(system, message):
                yield token
        except Exception as exc:
            logger.warning("LLM stream failed: %s", exc)
            yield FALLBACK_RESPONSES["llm_unreachable"]

    # ── internal ──────────────────────────────────────────────────────────

    async def _call_llm(self, system: str, user: str) -> str:
        if self._cfg.provider_kind == "anthropic":
            return await self._call_anthropic(system, user)
        return await self._call_openai_compat(system, user)

    async def _call_llm_stream(self, system: str, user: str) -> AsyncIterator[str]:
        if self._cfg.provider_kind == "anthropic":
            async for token in self._stream_anthropic(system, user):
                yield token
        else:
            async for token in self._stream_openai_compat(system, user):
                yield token

    # ── Anthropic /v1/messages ──────────────────────────────────────────

    async def _call_anthropic(self, system: str, user: str) -> str:
        base = self._cfg.base_url.rstrip("/")
        if base.endswith("/v1"):
            base = base[:-3]
        async with httpx.AsyncClient(timeout=self._cfg.timeout_s) as c:
            r = await c.post(
                f"{base}/v1/messages",
                headers={
                    "x-api-key": self._cfg.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._cfg.model,
                    "max_tokens": self._cfg.max_output_tokens,
                    "temperature": self._cfg.temperature,
                    "system": system,
                    "messages": [{"role": "user", "content": user}],
                },
            )
            r.raise_for_status()
            body = r.json()
            return body.get("content", [{}])[0].get("text", "")

    async def _stream_anthropic(self, system: str, user: str) -> AsyncIterator[str]:
        base = self._cfg.base_url.rstrip("/")
        if base.endswith("/v1"):
            base = base[:-3]
        async with httpx.AsyncClient(timeout=self._cfg.timeout_s) as c:
            async with c.stream(
                "POST", f"{base}/v1/messages",
                headers={
                    "x-api-key": self._cfg.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._cfg.model,
                    "max_tokens": self._cfg.max_output_tokens,
                    "temperature": self._cfg.temperature,
                    "system": system,
                    "messages": [{"role": "user", "content": user}],
                    "stream": True,
                },
            ) as r:
                r.raise_for_status()
                async for line in r.aiter_lines():
                    if line.startswith("data: "):
                        d = line[6:]
                        if d == "[DONE]":
                            break
                        try:
                            event = json.loads(d)
                            text = event.get("delta", {}).get("text", "")
                            if text:
                                yield text
                        except json.JSONDecodeError:
                            continue

    # ── OpenAI-compatible /v1/chat/completions ──────────────────────────

    async def _call_openai_compat(self, system: str, user: str) -> str:
        url = self._cfg.base_url.rstrip("/") + "/chat/completions"
        async with httpx.AsyncClient(timeout=self._cfg.timeout_s) as c:
            h = {"Content-Type": "application/json"}
            if self._cfg.api_key:
                h["Authorization"] = f"Bearer {self._cfg.api_key}"
            r = await c.post(url, headers=h, json={
                "model": self._cfg.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "max_tokens": self._cfg.max_output_tokens,
                "temperature": self._cfg.temperature,
            })
            r.raise_for_status()
            body = r.json()
            try:
                choice = body.get("choices", [{}])[0].get("message", {})
                return (choice.get("content") or choice.get("reasoning_content") or "").strip()
            except (KeyError, IndexError, TypeError):
                logger.warning("Unexpected LLM response shape: %s", str(body)[:200])
                return ""

    async def _stream_openai_compat(self, system: str, user: str) -> AsyncIterator[str]:
        url = self._cfg.base_url.rstrip("/") + "/chat/completions"
        async with httpx.AsyncClient(timeout=self._cfg.timeout_s) as c:
            h = {"Content-Type": "application/json"}
            if self._cfg.api_key:
                h["Authorization"] = f"Bearer {self._cfg.api_key}"
            async with c.stream("POST", url, headers=h, json={
                "model": self._cfg.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "max_tokens": self._cfg.max_output_tokens,
                "temperature": self._cfg.temperature,
                "stream": True,
            }) as r:
                r.raise_for_status()
                async for line in r.aiter_lines():
                    if line.startswith("data: "):
                        d = line[6:]
                        if d == "[DONE]":
                            break
                        try:
                            event = json.loads(d)
                            delta = event.get("choices", [{}])[0].get("delta", {})
                            text = delta.get("content", "")
                            if text:
                                yield text
                        except json.JSONDecodeError:
                            continue
