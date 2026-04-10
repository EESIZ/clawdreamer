"""Error alerting for Dreamer.

Sends failure notifications to the operator (never to the AI agent).
Dreamer runs as an invisible background process — the agent must not
know it exists, so alerts bypass the agent session entirely.

Supported providers: telegram, slack, webhook (generic POST).
Configure via environment variables (see config.py).
"""

import json
import logging
import urllib.request

from config import (
    ALERT_PROVIDER,
    ALERT_TELEGRAM_BOT_TOKEN,
    ALERT_TELEGRAM_CHAT_ID,
    ALERT_SLACK_WEBHOOK_URL,
    ALERT_WEBHOOK_URL,
)

log = logging.getLogger("dreamer.alerts")


def _post_json(url: str, payload: dict, timeout: int = 10) -> bool:
    body = json.dumps(payload, ensure_ascii=False).encode()
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(req, timeout=timeout)
        return True
    except Exception as e:
        log.error("Alert delivery failed (%s): %s", url[:40], e)
        return False


def _send_telegram(text: str) -> bool:
    if not ALERT_TELEGRAM_BOT_TOKEN or not ALERT_TELEGRAM_CHAT_ID:
        log.warning("Telegram alert skipped: missing bot token or chat ID")
        return False
    url = f"https://api.telegram.org/bot{ALERT_TELEGRAM_BOT_TOKEN}/sendMessage"
    return _post_json(url, {
        "chat_id": ALERT_TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
    })


def _send_slack(text: str) -> bool:
    if not ALERT_SLACK_WEBHOOK_URL:
        log.warning("Slack alert skipped: missing webhook URL")
        return False
    return _post_json(ALERT_SLACK_WEBHOOK_URL, {"text": text})


def _send_webhook(text: str, error: str) -> bool:
    if not ALERT_WEBHOOK_URL:
        log.warning("Webhook alert skipped: missing URL")
        return False
    return _post_json(ALERT_WEBHOOK_URL, {
        "source": "dreamer",
        "text": text,
        "error": error,
    })


def send_alert(error: Exception) -> bool:
    """Send an error alert to the configured provider.

    Returns True if the alert was delivered, False otherwise.
    When no provider is configured, returns False silently.
    """
    if not ALERT_PROVIDER:
        return False

    err_type = type(error).__name__
    err_msg = str(error)
    is_quota = "429" in err_msg or "quota" in err_msg.lower()

    icon = "\U0001f4b8" if is_quota else "\U0001f480"
    summary = "API quota exceeded" if is_quota else f"{err_type}"
    detail = err_msg[:300]

    provider = ALERT_PROVIDER.lower().strip()

    if provider == "telegram":
        text = (
            f"{icon} <b>Dreamer Error</b>\n\n"
            f"{summary}\n"
            f"<code>{err_type}: {detail}</code>"
        )
        ok = _send_telegram(text)
    elif provider == "slack":
        text = f"{icon} *Dreamer Error*\n{summary}\n```{err_type}: {detail}```"
        ok = _send_slack(text)
    elif provider == "webhook":
        text = f"{icon} Dreamer Error: {summary}"
        ok = _send_webhook(text, f"{err_type}: {detail}")
    else:
        log.warning("Unknown alert provider: %s", provider)
        return False

    if ok:
        log.info("Alert sent via %s", provider)
    return ok
