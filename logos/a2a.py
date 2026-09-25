"""A2A agent card — makes LOGOS discoverable as an agent skill.

Exposes the agent card at `/.well-known/agent-card.json` so any A2A peer
can discover that LOGOS offers an `analytics.ask` skill.
"""

from __future__ import annotations


def agent_card(public_url: str) -> dict:
    """Return the A2A Agent Card for LOGOS (protocol v0.2)."""
    base = public_url.rstrip("/")
    return {
        "protocolVersion": "0.2",
        "name": "LOGOS",
        "description": (
            "Federation analytics engine — answers natural-language questions "
            "about the AIMarket federation using live data from every component."
        ),
        "version": "0.1.0",
        "url": base,
        "endpoints": {
            "tasks": f"{base}/api/v1/a2a/tasks",
        },
        "skills": [
            {
                "id": "analytics.ask",
                "name": "Federation analytics query",
                "description": (
                    "Ask LOGOS a natural-language question about the AIMarket "
                    "federation and receive typed insights with recommendations."
                ),
                "input": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Natural-language question about the federation",
                        },
                    },
                    "required": ["query"],
                },
                "output": {
                    "type": "object",
                    "properties": {
                        "insights": {
                            "type": "array",
                            "description": "Typed insights with severity, sources, and recommendations",
                        },
                    },
                },
                "tags": ["analytics", "federation", "monitoring", "security", "economy"],
            },
        ],
    }
