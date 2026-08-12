"""Input guard — ARGUS Warden pattern applied to LLM prompts.

Before any user message reaches the LLM, it passes through a deterministic
guard pipeline. Each guard returns a verdict — the pipeline stops at the
first BLOCK, ensuring a hostile prompt never reaches the model.

The guard is deliberately simple and overridable: it is NOT a substitute
for the full ARGUS Warden (which runs in the MCP host). It is a fast,
deterministic first line that catches obvious attacks — injections,
prompt-leaking, and token-smuggling — without an API call.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class GuardAction(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"


@dataclass
class GuardVerdict:
    action: GuardAction
    gate: str
    reason: str = ""


@dataclass
class InputGuard:
    """Deterministic prompt-injection guard. Stateless — call ``check()`` on
    every user message before it reaches the model."""

    # Patterns that are ALWAYS blocked — they indicate an active injection
    # attempt, not legitimate use.
    _BLOCK_PATTERNS: list[tuple[str, str]] = field(default_factory=lambda: [
        # Direct system-prompt extraction
        ("system prompt leak", re.compile(
            r"(ignore|forget|disregard)\s+(all\s+)?(previous|prior|above|your)\s+(instructions?|prompts?|rules?)",
            re.IGNORECASE,
        )),
        # Role-switching injection
        ("role switch", re.compile(
            r"you\s+are\s+now\s+(DAN|jailbreak|a\s+different|no\s+longer)",
            re.IGNORECASE,
        )),
        # Token smuggling
        ("token smuggling", re.compile(
            r"(print|show|reveal|output|dump|display)\s+(your\s+)?(system\s+)?(prompt|instructions?|rules?)",
            re.IGNORECASE,
        )),
        # Delimiter injection (tries to close our system prompt)
        ("delimiter injection", re.compile(
            r"</system>|</instructions>|\[/INST\]|\[/SYS\]",
        )),
    ])

    # Patterns that trigger a warning log but don't block — useful for
    # monitoring without breaking legitimate queries.
    _WARN_PATTERNS: list[tuple[str, str]] = field(default_factory=lambda: [
        ("sql injection keyword", re.compile(
            r"\b(DROP\s+TABLE|ALTER\s+TABLE|TRUNCATE|EXEC\s*\(|xp_cmdshell)\b",
            re.IGNORECASE,
        )),
    ])

    max_input_length: int = 8000

    def check(self, text: str) -> GuardVerdict:
        """Run the guard pipeline. Returns BLOCK or ALLOW."""

        # Length gate
        if len(text) > self.max_input_length:
            return GuardVerdict(
                action=GuardAction.BLOCK,
                gate="input-length",
                reason=f"Input exceeds {self.max_input_length} characters",
            )

        # Block-list patterns
        for name, pattern in self._BLOCK_PATTERNS:
            if pattern.search(text):
                return GuardVerdict(
                    action=GuardAction.BLOCK,
                    gate=f"injection-{name}",
                    reason=f"Matched blocked pattern: {name}",
                )

        return GuardVerdict(action=GuardAction.ALLOW, gate="ok")

    def warn_patterns(self, text: str) -> list[str]:
        """Return names of warning patterns matched (for logging only)."""
        return [name for name, p in self._WARN_PATTERNS if p.search(text)]
