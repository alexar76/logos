"""Telegram notification sender — anomaly alerts + daily reports.

Configure with LOGOS_TELEGRAM_BOT_TOKEN and LOGOS_TELEGRAM_CHAT_ID.
When both are set, critical/high anomalies and the daily report are posted
to the configured Telegram chat. Same pattern as SKOPOS telegram_notify.py.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

logger = logging.getLogger("logos.telegram")


async def send_message(
    token: str,
    chat_id: str,
    text: str,
    *,
    parse_mode: str = "Markdown",
    timeout_s: float = 10.0,
) -> tuple[bool, str]:
    """Send a Telegram message. Returns (ok, error_text)."""
    url = f"https://api.telegram.org/bot{token.strip()}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as c:
            r = await c.post(
                url,
                json={
                    "chat_id": chat_id,
                    "text": text[:4096],
                    "parse_mode": parse_mode,
                    "disable_web_page_preview": True,
                },
            )
            if r.status_code == 200:
                body = r.json()
                if body.get("ok"):
                    return True, ""
                return False, body.get("description", "unknown")
            return False, f"HTTP {r.status_code}"
    except Exception as exc:
        return False, str(exc)


def _escape_md(text: str) -> str:
    """Escape Telegram MarkdownV2 special characters."""
    for ch in "_*[]()~`>#+-=|{}.!":
        text = text.replace(ch, f"\\{ch}")
    return text


async def send_anomaly_alert(
    token: str,
    chat_id: str,
    metric: str,
    severity: str,
    z_score: float,
    description: str,
    detected_at: str,
) -> bool:
    """Post a single anomaly alert to Telegram."""
    emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵", "info": "🔵"}
    e = emoji.get(severity, "🔵")
    ts = detected_at[:19] if detected_at else "?"

    text = (
        f"{e} *LOGOS Anomaly*\n\n"
        f"*Metric:* `{_escape_md(metric)}`\n"
        f"*Severity:* {severity.upper()}\n"
        f"*Z-score:* {z_score:.1f}σ\n"
        f"*Detected:* {ts}\n\n"
        f"{_escape_md(description[:300])}"
    )

    ok, err = await send_message(token, chat_id, text)
    if not ok:
        logger.warning("Telegram anomaly alert failed: %s", err)
    return ok


async def send_daily_report(
    token: str,
    chat_id: str,
    report_summary: str,
    kpis: list[dict],
    anomaly_count: int,
    overall_status: str,
) -> bool:
    """Post the daily briefing to Telegram."""
    emoji = {"ok": "🟢", "warn": "🟡", "critical": "🔴"}
    e = emoji.get(overall_status, "🔵")

    kpi_lines = []
    for k in kpis:
        s = k.get("status", "ok")
        se = {"ok": "✅", "warn": "⚠️", "critical": "🚨"}.get(s, "·")
        kpi_lines.append(f"{se} *{_escape_md(str(k.get('label', '?')))}*: {_escape_md(str(k.get('value', '?')))}")

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    text = (
        f"{e} *LOGOS Daily Briefing*\n{_escape_md(today)}\n\n"
        f"{_escape_md(report_summary[:200])}\n\n"
        f"*KPIs:*\n" + "\n".join(kpi_lines) + f"\n\n"
        f"*Active Anomalies:* {anomaly_count}\n"
        f"*Overall:* {overall_status.upper()}"
    )

    ok, err = await send_message(token, chat_id, text)
    if not ok:
        logger.warning("Telegram daily report failed: %s", err)
    return ok
