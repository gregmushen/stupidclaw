"""Telegram bot configuration accessors.

All functions read from os.environ at call time (lazy reads).
No module-level reads. This allows safe import in tests without env vars.
"""

import os


def get_bot_token() -> str:
    """Return TELEGRAM_BOT_TOKEN. Raises EnvironmentError if not set."""
    val = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not val:
        raise EnvironmentError("TELEGRAM_BOT_TOKEN is required")
    return val


def get_chat_id() -> str:
    """Return TELEGRAM_CHAT_ID. Raises EnvironmentError if not set."""
    val = os.environ.get("TELEGRAM_CHAT_ID")
    if not val:
        raise EnvironmentError("TELEGRAM_CHAT_ID is required")
    return val


def get_notify_port() -> int:
    """Return TELEGRAM_NOTIFY_PORT as int. Defaults to 8080."""
    return int(os.environ.get("TELEGRAM_NOTIFY_PORT", "8080"))


def get_linear_api_key() -> str:
    """Return LINEAR_API_KEY. Raises EnvironmentError if not set."""
    val = os.environ.get("LINEAR_API_KEY")
    if not val:
        raise EnvironmentError("LINEAR_API_KEY is required")
    return val


def get_linear_team_id() -> str:
    """Return LINEAR_TEAM_ID (STU team). Raises EnvironmentError if not set."""
    val = os.environ.get("LINEAR_TEAM_ID")
    if not val:
        raise EnvironmentError("LINEAR_TEAM_ID is required")
    return val
