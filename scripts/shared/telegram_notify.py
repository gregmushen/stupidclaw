"""Pipeline-side helper for sending Telegram notifications.

Used by stage1_triage and stage3_research to notify the user when
issues are blocked or completed. All failures are caught and logged —
notification errors must never crash the pipeline.
"""

import logging
import os

logger = logging.getLogger("stupidclaw.telegram_notify")

_NOTIFY_TIMEOUT = 5


def _get_bot_url():
    """Return TELEGRAM_BOT_URL from env, or None if not set."""
    return os.environ.get("TELEGRAM_BOT_URL")


def notify_blocked(
    issue_id: str,
    identifier: str,
    title: str,
    blocked_message: str,
) -> bool:
    """Notify the Telegram bot that a pipeline issue is blocked.

    POSTs to TELEGRAM_BOT_URL/notify with type:blocked payload.

    Returns:
        True if notification was sent successfully, False on any failure.
    """
    try:
        import httpx

        bot_url = _get_bot_url()
        if not bot_url:
            logger.debug("TELEGRAM_BOT_URL not set — skipping blocked notification")
            return False

        payload = {
            "type": "blocked",
            "issue_id": issue_id,
            "identifier": identifier,
            "title": title,
            "blocked_message": blocked_message,
        }
        response = httpx.post(
            f"{bot_url}/notify",
            json=payload,
            timeout=_NOTIFY_TIMEOUT,
        )
        response.raise_for_status()
        logger.info(f"Blocked notification sent for {identifier}")
        return True

    except Exception as e:
        logger.warning(f"Failed to send blocked notification for {identifier}: {e}")
        return False


def notify_completed(
    issue_id: str,
    identifier: str,
    title: str,
    state: str,
    human_tasks_remaining: int,
    link: str,
) -> bool:
    """Notify the Telegram bot that a pipeline issue has completed agent work.

    POSTs to TELEGRAM_BOT_URL/notify with type:completed payload.

    Returns:
        True if notification was sent successfully, False on any failure.
    """
    try:
        import httpx

        bot_url = _get_bot_url()
        if not bot_url:
            logger.debug("TELEGRAM_BOT_URL not set — skipping completed notification")
            return False

        payload = {
            "type": "completed",
            "issue_id": issue_id,
            "identifier": identifier,
            "title": title,
            "state": state,
            "human_tasks_remaining": human_tasks_remaining,
            "link": link,
        }
        response = httpx.post(
            f"{bot_url}/notify",
            json=payload,
            timeout=_NOTIFY_TIMEOUT,
        )
        response.raise_for_status()
        logger.info(f"Completed notification sent for {identifier}")
        return True

    except Exception as e:
        logger.warning(f"Failed to send completed notification for {identifier}: {e}")
        return False
