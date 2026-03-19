"""Tests for tgbot/server/notify.py and scripts/shared/telegram_notify.py

Tests the HTTP notification server and the pipeline-side notification helpers.
"""

import os
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.fixture
async def notify_client(aiohttp_client):
    """Create a test client for the notify app with a mocked bot."""
    mock_bot = AsyncMock()
    mock_sent_message = MagicMock()
    mock_sent_message.message_id = 42
    mock_bot.send_message = AsyncMock(return_value=mock_sent_message)

    from tgbot.server.notify import create_notify_app, set_bot
    set_bot(mock_bot)
    app = create_notify_app()
    client = await aiohttp_client(app)

    return client, mock_bot


class TestNotifyServer:

    @pytest.mark.asyncio
    async def test_blocked_notification_sends_message(self, notify_client):
        """POST blocked payload -> bot.send_message called with correct format."""
        client, mock_bot = notify_client

        payload = {
            "type": "blocked",
            "issue_id": "abc-123",
            "identifier": "STU-42",
            "title": "Replace windshield wipers",
            "blocked_message": "Which wiper size fits your car?",
        }
        with patch("tgbot.server.notify.get_chat_id", return_value="12345"):
            resp = await client.post("/notify", json=payload)
        assert resp.status == 200

        mock_bot.send_message.assert_called_once()
        call_kwargs = mock_bot.send_message.call_args[1]
        assert "*STU-42 blocked:*" in call_kwargs["text"]
        assert "Which wiper size fits your car?" in call_kwargs["text"]
        assert "_Reply to this message to answer._" in call_kwargs["text"]
        assert call_kwargs["parse_mode"] == "Markdown"

    @pytest.mark.asyncio
    async def test_completed_notification_sends_message(self, notify_client):
        """POST completed payload -> bot.send_message called with Linear link."""
        client, mock_bot = notify_client

        payload = {
            "type": "completed",
            "issue_id": "abc-123",
            "identifier": "STU-42",
            "title": "Replace windshield wipers",
            "state": "in_review",
            "human_tasks_remaining": 1,
            "link": "https://linear.app/gregmushen/issue/STU-42",
            "answer": "Likely domestic shorthair. Feed high-protein indoor adult formula.",
        }
        with patch("tgbot.server.notify.get_chat_id", return_value="12345"):
            resp = await client.post("/notify", json=payload)
        assert resp.status == 200

        mock_bot.send_message.assert_called_once()
        call_kwargs = mock_bot.send_message.call_args[1]
        assert "STU-42 ready for review:" in call_kwargs["text"]
        assert "1 human task remaining" in call_kwargs["text"]
        assert "Likely domestic shorthair" in call_kwargs["text"]
        assert "https://linear.app/gregmushen/issue/STU-42" in call_kwargs["text"]

    @pytest.mark.asyncio
    async def test_invalid_json_returns_400(self, notify_client):
        """POST non-JSON body -> 400 response."""
        client, _ = notify_client

        resp = await client.post("/notify", data=b"not json", headers={"Content-Type": "application/json"})
        assert resp.status == 400

    @pytest.mark.asyncio
    async def test_unknown_type_returns_400(self, notify_client):
        """POST {type: "garbage"} -> 400 with 'Unknown type: garbage'."""
        client, _ = notify_client

        resp = await client.post("/notify", json={"type": "garbage"})
        assert resp.status == 400
        text = await resp.text()
        assert "Unknown type: garbage" in text


class TestPipelineNotifyGracefulFailure:

    def test_pipeline_notify_graceful_failure(self):
        """notify_blocked() returns False (no exception) when bot is unreachable."""
        with patch.dict(os.environ, {"TELEGRAM_BOT_URL": "http://localhost:99999"}):
            with patch("httpx.post", side_effect=Exception("Connection refused")):
                from scripts.shared.telegram_notify import notify_blocked, notify_completed

                result_blocked = notify_blocked(
                    issue_id="abc",
                    identifier="STU-1",
                    title="Test",
                    blocked_message="Blocked",
                )
                assert result_blocked is False

                result_completed = notify_completed(
                    issue_id="abc",
                    identifier="STU-1",
                    title="Test",
                    state="blocked",
                    human_tasks_remaining=0,
                    link="https://example.com",
                )
                assert result_completed is False
