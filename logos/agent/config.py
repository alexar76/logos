"""Agent configuration — LLM provider, model, context budget.

Named presets, same as MOMUS: anthropic, openai, deepseek (default), ollama, lmstudio.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

# ── provider presets (mirrors MOMUS providers.py) ─────────────────────────

_PROVIDER_PRESETS: dict[str, dict[str, str]] = {
    "anthropic": {
        "kind": "anthropic",
        "base_url": "https://api.anthropic.com",
        "model": "claude-sonnet-4-5",
        "api_key": "",
    },
    "openai": {
        "kind": "openai_compat",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "api_key": "",
    },
    "deepseek": {
        "kind": "openai_compat",
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-v4-pro",
        "api_key": "",
    },
    "ollama": {
        "kind": "openai_compat",
        "base_url": "http://host.docker.internal:11434/v1",
        "model": "llama3.1",
        "api_key": "ollama",
    },
    "lmstudio": {
        "kind": "openai_compat",
        "base_url": "http://host.docker.internal:1234/v1",
        "model": "local-model",
        "api_key": "lm-studio",
    },
}

_ALIASES = {
    "claude": "anthropic", "openai_compatible": "openai", "oai": "openai",
    "lm_studio": "lmstudio", "deep-seek": "deepseek", "": "deepseek",
}


def _resolve_provider(raw: str) -> dict[str, str]:
    name = _ALIASES.get(raw.strip().lower(), raw.strip().lower())
    return _PROVIDER_PRESETS.get(name, _PROVIDER_PRESETS["deepseek"])


@dataclass
class AgentConfig:
    """LLM provider config for the LOGOS assistant. Every setting from env.

    Provider presets: deepseek (default), anthropic, openai, ollama, lmstudio.
    Same names and semantics as MOMUS."""

    provider_name: str = field(
        default_factory=lambda: os.environ.get("LOGOS_LLM_PROVIDER", "deepseek").strip().lower()
    )
    provider_kind: str = field(init=False)  # anthropic | openai_compat
    model: str = field(init=False)
    api_key: str = field(init=False)
    base_url: str = field(init=False)

    def __post_init__(self) -> None:
        preset = _resolve_provider(self.provider_name)
        self.provider_kind = preset["kind"]
        self.model = (
            os.environ.get("LOGOS_LLM_MODEL", "").strip()
            or preset["model"]
        )
        self.base_url = (
            os.environ.get("LOGOS_LLM_BASE_URL", "").strip()
            or preset["base_url"]
        )
        self.api_key = (
            os.environ.get("LOGOS_LLM_API_KEY", "").strip()
            or preset["api_key"]
            or os.environ.get("DEEPSEEK_API_KEY", "").strip()
            or os.environ.get("ANTHROPIC_API_KEY", "").strip()
            or os.environ.get("OPENAI_API_KEY", "").strip()
        )

    # Runtime knobs
    max_context_chars: int = field(
        default_factory=lambda: int(os.environ.get("LOGOS_LLM_MAX_CONTEXT_CHARS", "24000"))
    )
    max_output_tokens: int = field(
        default_factory=lambda: int(os.environ.get("LOGOS_LLM_MAX_OUTPUT_TOKENS", "2048"))
    )
    temperature: float = field(
        default_factory=lambda: float(os.environ.get("LOGOS_LLM_TEMPERATURE", "0.3"))
    )
    timeout_s: float = field(
        default_factory=lambda: float(os.environ.get("LOGOS_LLM_TIMEOUT_S", "45"))
    )
    include_finding_detail: bool = field(
        default_factory=lambda: os.environ.get("LOGOS_LLM_INCLUDE_FINDING_DETAIL", "").lower()
        in ("1", "true", "yes")
    )

    @classmethod
    def from_env(cls) -> "AgentConfig":
        return cls()

    @classmethod
    def provider_choices(cls) -> list[dict[str, str]]:
        return [
            {"name": n, "kind": p["kind"], "default_model": p["model"],
             "default_base_url": p["base_url"]}
            for n, p in _PROVIDER_PRESETS.items()
        ]
