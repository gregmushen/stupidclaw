"""Inbound message handlers for the Telegram bot.

Handles text messages and photos from the authorized Telegram chat,
creating Linear issues for each.
"""

import asyncio
import logging

from telegram import Update
from telegram.ext import ContextTypes

from tgbot.config import get_chat_id
from tgbot.linear_api import create_issue

logger = logging.getLogger("stupidclaw.telegram.inbound")

# Media group buffering for multi-photo albums
_media_group_buffer: dict[str, list] = {}
_media_group_tasks: dict[str, asyncio.Task] = {}


def _build_title_and_description(text: str, default_title: str = "Photo task") -> tuple[str, str]:
    raw = (text or "").strip()
    if not raw:
        return default_title, default_title
    return raw[:200], raw


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming text messages — create a Linear issue."""
    if update.effective_chat.id != int(get_chat_id()):
        return

    text = update.message.text.strip()
    if not text:
        return

    title, description = _build_title_and_description(text, default_title="Task")

    result = create_issue(title=title, description=description)
    identifier = result["identifier"]
    await update.message.reply_text(f"Created {identifier}: {title}")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming photo messages — create a Linear issue with attachment."""
    if update.effective_chat.id != int(get_chat_id()):
        return

    caption = update.message.caption or ""
    photo = update.message.photo[-1]
    file = await photo.get_file()
    photo_bytes = await file.download_as_bytearray()

    media_group_id = update.message.media_group_id

    if media_group_id:
        # Buffer for multi-photo album
        if media_group_id not in _media_group_buffer:
            _media_group_buffer[media_group_id] = []

        _media_group_buffer[media_group_id].append({
            "caption": caption,
            "data": bytes(photo_bytes),
        })

        if media_group_id not in _media_group_tasks:
            _media_group_tasks[media_group_id] = asyncio.create_task(
                _flush_media_group(
                    media_group_id,
                    update.effective_chat.id,
                    context.bot,
                )
            )
    else:
        # Single photo — process immediately
        title, description = _build_title_and_description(caption, default_title="Photo task")

        result = create_issue(
            title=title,
            description=description,
            attachments=[{"filename": "photo.jpg", "data": bytes(photo_bytes)}],
        )
        identifier = result["identifier"]
        att_count = len(result.get("attachments", []))

        reply = f"Created {identifier}: {title}"
        if att_count:
            reply += f" ({att_count} photo{'s' if att_count > 1 else ''})"
        await update.message.reply_text(reply)


async def _flush_media_group(group_id: str, chat_id: int, bot) -> None:
    """Wait for all photos in an album, then create a single issue."""
    await asyncio.sleep(1.5)
    photos = _media_group_buffer.pop(group_id, [])
    _media_group_tasks.pop(group_id, None)
    if not photos:
        return

    caption = next((p["caption"] for p in photos if p["caption"]), "")
    title, description = _build_title_and_description(caption, default_title="Photo task")

    attachments = [
        {"filename": f"photo_{i+1}.jpg", "data": p["data"]}
        for i, p in enumerate(photos)
    ]
    result = create_issue(title=title, description=description, attachments=attachments)
    identifier = result["identifier"]
    att_count = len(result.get("attachments", []))
    reply = f"Created {identifier}: {title} ({att_count} photo{'s' if att_count > 1 else ''})"
    await bot.send_message(chat_id=chat_id, text=reply)
