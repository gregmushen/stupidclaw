"""Tests for telegram/handlers/inbound.py

Tests text and photo message handlers. All tests mock create_issue
and Telegram API objects to avoid network calls.
"""

import asyncio
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def _make_update(chat_id, text=None, caption=None, photo=None, media_group_id=None):
    """Create a mock Telegram Update object."""
    update = MagicMock()
    update.effective_chat.id = chat_id

    message = AsyncMock()
    message.text = text
    message.caption = caption
    message.media_group_id = media_group_id
    message.reply_text = AsyncMock()

    if photo:
        mock_photo = MagicMock()
        mock_file = AsyncMock()
        mock_file.download_as_bytearray = AsyncMock(return_value=bytearray(b"fake photo bytes"))
        mock_photo.get_file = AsyncMock(return_value=mock_file)
        message.photo = [MagicMock(), mock_photo]  # [small, large]
    else:
        message.photo = None

    update.message = message
    return update


AUTHORIZED_CHAT_ID = 12345
ENV = {"TELEGRAM_CHAT_ID": str(AUTHORIZED_CHAT_ID), "LINEAR_API_KEY": "test", "LINEAR_TEAM_ID": "team-123"}


class TestTextHandler:

    @pytest.mark.asyncio
    async def test_text_creates_issue(self):
        """Text message creates a Linear issue and replies with identifier."""
        update = _make_update(AUTHORIZED_CHAT_ID, text="Fix the garage door")
        context = MagicMock()

        mock_result = {"id": "uuid-1", "identifier": "STU-10", "attachments": []}

        with patch.dict(os.environ, ENV):
            with patch("tgbot.handlers.inbound.create_issue", return_value=mock_result) as mock_create:
                from tgbot.handlers.inbound import handle_text
                await handle_text(update, context)

        mock_create.assert_called_once_with(title="Fix the garage door", description="Fix the garage door")
        update.message.reply_text.assert_called_once_with("Created STU-10: Fix the garage door")

    @pytest.mark.asyncio
    async def test_long_text_truncates_title(self):
        """300-char text: title is first 200 chars, description is full text."""
        long_text = "A" * 300
        update = _make_update(AUTHORIZED_CHAT_ID, text=long_text)
        context = MagicMock()

        mock_result = {"id": "uuid-1", "identifier": "STU-11", "attachments": []}

        with patch.dict(os.environ, ENV):
            with patch("tgbot.handlers.inbound.create_issue", return_value=mock_result) as mock_create:
                from tgbot.handlers.inbound import handle_text
                await handle_text(update, context)

        call_kwargs = mock_create.call_args[1]
        assert len(call_kwargs["title"]) == 200
        assert call_kwargs["description"] == long_text

    @pytest.mark.asyncio
    async def test_empty_message_ignored(self):
        """Empty/whitespace text: no issue created, no reply sent."""
        update = _make_update(AUTHORIZED_CHAT_ID, text="   ")
        context = MagicMock()

        with patch.dict(os.environ, ENV):
            with patch("tgbot.handlers.inbound.create_issue") as mock_create:
                from tgbot.handlers.inbound import handle_text
                await handle_text(update, context)

        mock_create.assert_not_called()
        update.message.reply_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_unauthorized_chat_rejected(self):
        """Wrong chat ID: no issue created, no reply sent."""
        update = _make_update(99999, text="Should not work")
        context = MagicMock()

        with patch.dict(os.environ, ENV):
            with patch("tgbot.handlers.inbound.create_issue") as mock_create:
                from tgbot.handlers.inbound import handle_text
                await handle_text(update, context)

        mock_create.assert_not_called()
        update.message.reply_text.assert_not_called()


class TestPhotoHandler:

    @pytest.mark.asyncio
    async def test_photo_creates_issue_with_attachment(self):
        """Photo with caption creates issue with attachment, reply includes (1 photo)."""
        update = _make_update(AUTHORIZED_CHAT_ID, caption="Check this crack", photo=True)
        context = MagicMock()

        mock_result = {
            "id": "uuid-2",
            "identifier": "STU-12",
            "attachments": [{"filename": "photo.jpg"}],
        }

        with patch.dict(os.environ, ENV):
            with patch("tgbot.handlers.inbound.create_issue", return_value=mock_result) as mock_create:
                from tgbot.handlers.inbound import handle_photo
                await handle_photo(update, context)

        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["title"] == "Check this crack"
        assert call_kwargs["description"] == "Check this crack"
        assert len(call_kwargs["attachments"]) == 1

        reply_text = update.message.reply_text.call_args[0][0]
        assert "STU-12" in reply_text
        assert "(1 photo)" in reply_text

    @pytest.mark.asyncio
    async def test_multi_photo_groups_into_single_issue(self):
        """3 photos with same media_group_id -> 1 create_issue call with 3 attachments."""
        from tgbot.handlers import inbound
        # Clear any leftover buffer state
        inbound._media_group_buffer.clear()
        inbound._media_group_tasks.clear()

        group_id = "album-123"
        bot = AsyncMock()

        mock_result = {
            "id": "uuid-3",
            "identifier": "STU-13",
            "attachments": [{"filename": f"photo_{i}.jpg"} for i in range(3)],
        }

        with patch.dict(os.environ, ENV):
            with patch("tgbot.handlers.inbound.create_issue", return_value=mock_result) as mock_create:
                for i in range(3):
                    update = _make_update(
                        AUTHORIZED_CHAT_ID,
                        caption="Album caption" if i == 0 else "",
                        photo=True,
                        media_group_id=group_id,
                    )
                    context = MagicMock()
                    context.bot = bot
                    await inbound.handle_photo(update, context)

                # Wait for the flush task to complete (1.5s sleep inside)
                task = inbound._media_group_tasks.get(group_id)
                if task:
                    await task

        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args[1]
        assert len(call_kwargs["attachments"]) == 3
        assert call_kwargs["title"] == "Album caption"
        assert call_kwargs["description"] == "Album caption"

        # Bot.send_message was used (not update.message.reply_text) for grouped photos
        bot.send_message.assert_called_once()
        reply_text = bot.send_message.call_args[1]["text"]
        assert "(3 photos)" in reply_text
