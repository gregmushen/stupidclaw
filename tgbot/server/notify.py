"""HTTP notification server for pipeline-to-Telegram communication.

Accepts POST requests from the pipeline when issues are blocked or completed.
Translates payloads into formatted Telegram messages.
"""

import logging

from aiohttp import web

from tgbot.config import get_chat_id
from tgbot.handlers.reply import register_blocked_message

logger = logging.getLogger("stupidclaw.telegram.notify")

# Set by bot.py during initialization
_bot = None


def set_bot(bot) -> None:
    """Store a reference to the Telegram bot instance."""
    global _bot
    _bot = bot


async def handle_notify(request: web.Request) -> web.Response:
    """Handle POST /notify from the pipeline."""
    try:
        payload = await request.json()
    except Exception:
        return web.Response(status=400, text="Invalid JSON")

    notify_type = payload.get("type")

    if notify_type == "blocked":
        identifier = payload.get("identifier", "")
        message = payload.get("blocked_message", "")
        text = f"*{identifier} blocked:*\n{message}\n\n_Reply to this message to answer._"

        try:
            sent = await _bot.send_message(
                chat_id=int(get_chat_id()),
                text=text,
                parse_mode="Markdown",
            )
            register_blocked_message(
                sent.message_id,
                payload.get("issue_id", ""),
                identifier,
            )
        except Exception as e:
            logger.error(f"Failed to send blocked notification: {e}")
            return web.Response(status=500, text=str(e))

    elif notify_type == "completed":
        identifier = payload.get("identifier", "")
        title = payload.get("title", "")
        human_remaining = payload.get("human_tasks_remaining", 0)
        link = payload.get("link", "")
        answer = (payload.get("answer") or "").strip()

        if human_remaining and human_remaining > 0:
            text = f"{identifier} ready for review:\n{title} — {human_remaining} human task{'s' if human_remaining > 1 else ''} remaining."
        else:
            text = f"{identifier} complete:\n{title}"

        if answer:
            excerpt = answer[:1400]
            if len(answer) > 1400:
                excerpt += "..."
            text += f"\n\nAnswer:\n{excerpt}"

        if link:
            text += f"\n{link}"

        try:
            await _bot.send_message(
                chat_id=int(get_chat_id()),
                text=text,
            )
        except Exception as e:
            logger.error(f"Failed to send completed notification: {e}")
            return web.Response(status=500, text=str(e))

    else:
        return web.Response(status=400, text=f"Unknown type: {notify_type}")

    return web.Response(status=200, text="ok")


def create_notify_app() -> web.Application:
    """Create the aiohttp application with the /notify route."""
    app = web.Application()
    app.router.add_post("/notify", handle_notify)
    return app
