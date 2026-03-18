"""Reply handler for blocked notifications.

When a user replies to a blocked notification in Telegram:
1. Posts the reply text as a Linear comment
2. Uploads photo attachment if present
3. Moves the issue from Blocked -> Backlog
4. Sends confirmation to the user
5. Cleans up the mapping entry
"""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from tgbot.config import get_chat_id
from tgbot.linear_api import add_comment, upload_attachment, update_issue_state

logger = logging.getLogger("stupidclaw.telegram.reply")

# In-memory mapping populated by notify handler
_blocked_messages: dict[int, dict] = {}  # telegram_msg_id -> {issue_id, identifier}


def register_blocked_message(telegram_msg_id: int, issue_id: str, identifier: str = "") -> None:
    """Register a blocked notification message for reply tracking."""
    _blocked_messages[telegram_msg_id] = {"issue_id": issue_id, "identifier": identifier}


async def handle_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle replies to blocked notifications."""
    if update.effective_chat.id != int(get_chat_id()):
        return

    reply_to = update.message.reply_to_message
    if not reply_to or reply_to.message_id not in _blocked_messages:
        return

    info = _blocked_messages[reply_to.message_id]
    issue_id = info["issue_id"]
    identifier = info["identifier"]

    # Post text as comment
    text = update.message.text or update.message.caption or ""
    if text:
        add_comment(issue_id, text)

    # Upload photo if present
    if update.message.photo:
        photo = update.message.photo[-1]
        file = await photo.get_file()
        photo_bytes = await file.download_as_bytearray()
        upload_attachment(issue_id, "reply_photo.jpg", bytes(photo_bytes))

    # Move Blocked -> Backlog
    update_issue_state(issue_id, "backlog")

    await update.message.reply_text(f"Reply posted to {identifier}. Issue unblocked.")
    del _blocked_messages[reply_to.message_id]
