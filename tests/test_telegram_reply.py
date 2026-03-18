"""Tests for tgbot/handlers/reply.py

Tests the reply-to-blocked-notification flow.
"""

import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


AUTHORIZED_CHAT_ID = 12345
ENV = {
    "TELEGRAM_CHAT_ID": str(AUTHORIZED_CHAT_ID),
    "LINEAR_API_KEY": "test",
    "STATE_BACKLOG": "state-uuid-backlog",
}


def _make_reply_update(chat_id, reply_to_message_id, text=None, caption=None, photo=False):
    """Create a mock Telegram Update for a reply message."""
    update = MagicMock()
    update.effective_chat.id = chat_id

    message = AsyncMock()
    message.text = text
    message.caption = caption
    message.reply_text = AsyncMock()

    reply_to = MagicMock()
    reply_to.message_id = reply_to_message_id
    message.reply_to_message = reply_to

    if photo:
        mock_photo = MagicMock()
        mock_file = AsyncMock()
        mock_file.download_as_bytearray = AsyncMock(return_value=bytearray(b"reply photo bytes"))
        mock_photo.get_file = AsyncMock(return_value=mock_file)
        message.photo = [MagicMock(), mock_photo]
    else:
        message.photo = None

    update.message = message
    return update


class TestReplyHandler:

    @pytest.mark.asyncio
    async def test_reply_posts_comment_and_unblocks(self):
        """Reply to blocked message -> add_comment called, issue unblocked, confirmation sent."""
        from tgbot.handlers.reply import _blocked_messages, handle_reply

        # Set up the mapping
        _blocked_messages[100] = {"issue_id": "issue-uuid-1", "identifier": "STU-50"}

        update = _make_reply_update(AUTHORIZED_CHAT_ID, reply_to_message_id=100, text="Use 24-inch wipers")
        context = MagicMock()

        with patch.dict(os.environ, ENV):
            with patch("tgbot.handlers.reply.add_comment") as mock_comment:
                with patch("tgbot.handlers.reply.update_issue_state") as mock_state:
                    await handle_reply(update, context)

        mock_comment.assert_called_once_with("issue-uuid-1", "Use 24-inch wipers")
        mock_state.assert_called_once_with("issue-uuid-1", "backlog")
        update.message.reply_text.assert_called_once_with("Reply posted to STU-50. Issue unblocked.")

    @pytest.mark.asyncio
    async def test_reply_with_photo_uploads_attachment(self):
        """Reply with photo -> upload_attachment called, issue unblocked."""
        from tgbot.handlers.reply import _blocked_messages, handle_reply

        _blocked_messages[200] = {"issue_id": "issue-uuid-2", "identifier": "STU-51"}

        update = _make_reply_update(AUTHORIZED_CHAT_ID, reply_to_message_id=200, caption="Here's a photo", photo=True)
        context = MagicMock()

        with patch.dict(os.environ, ENV):
            with patch("tgbot.handlers.reply.add_comment") as mock_comment:
                with patch("tgbot.handlers.reply.upload_attachment") as mock_upload:
                    with patch("tgbot.handlers.reply.update_issue_state"):
                        await handle_reply(update, context)

        mock_comment.assert_called_once_with("issue-uuid-2", "Here's a photo")
        mock_upload.assert_called_once()
        assert mock_upload.call_args[0][0] == "issue-uuid-2"
        assert mock_upload.call_args[0][1] == "reply_photo.jpg"

    @pytest.mark.asyncio
    async def test_reply_to_non_blocked_message_ignored(self):
        """Reply to regular message (not in mapping) -> handler returns early."""
        from tgbot.handlers.reply import _blocked_messages, handle_reply

        _blocked_messages.clear()

        update = _make_reply_update(AUTHORIZED_CHAT_ID, reply_to_message_id=999, text="Random reply")
        context = MagicMock()

        with patch.dict(os.environ, ENV):
            with patch("tgbot.handlers.reply.add_comment") as mock_comment:
                await handle_reply(update, context)

        mock_comment.assert_not_called()
        update.message.reply_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_unknown_reply_ignored(self):
        """reply_to_message.message_id not in mapping -> handler returns early."""
        from tgbot.handlers.reply import _blocked_messages, handle_reply

        _blocked_messages[100] = {"issue_id": "issue-uuid-1", "identifier": "STU-50"}

        # Reply to message 777, which is not in the mapping
        update = _make_reply_update(AUTHORIZED_CHAT_ID, reply_to_message_id=777, text="Wrong reply")
        context = MagicMock()

        with patch.dict(os.environ, ENV):
            with patch("tgbot.handlers.reply.add_comment") as mock_comment:
                await handle_reply(update, context)

        mock_comment.assert_not_called()

        # Clean up
        _blocked_messages.clear()

    @pytest.mark.asyncio
    async def test_mapping_cleaned_up_after_reply(self):
        """After handling reply, message_id removed from _blocked_messages."""
        from tgbot.handlers.reply import _blocked_messages, handle_reply

        _blocked_messages[300] = {"issue_id": "issue-uuid-3", "identifier": "STU-52"}

        update = _make_reply_update(AUTHORIZED_CHAT_ID, reply_to_message_id=300, text="Done")
        context = MagicMock()

        with patch.dict(os.environ, ENV):
            with patch("tgbot.handlers.reply.add_comment"):
                with patch("tgbot.handlers.reply.update_issue_state"):
                    await handle_reply(update, context)

        assert 300 not in _blocked_messages
