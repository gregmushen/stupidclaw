"""Tests for telegram/linear_api.py

All tests mock _graphql to avoid network calls.
The attachment test additionally mocks httpx.put.
"""

import os
import pytest
from unittest.mock import patch, MagicMock


class TestCreateIssue:

    def test_create_issue(self):
        """create_issue calls issueCreate mutation with correct team_id and returns identifier."""
        team_id = "team-uuid-123"

        mock_response = {
            "issueCreate": {
                "success": True,
                "issue": {
                    "id": "issue-uuid-abc",
                    "identifier": "STU-42",
                }
            }
        }

        with patch.dict(os.environ, {"LINEAR_API_KEY": "lin_test_key", "LINEAR_TEAM_ID": team_id}):
            with patch("tgbot.linear_api._graphql", return_value=mock_response) as mock_gql:
                from tgbot.linear_api import create_issue

                result = create_issue(
                    title="Check this out",
                    description="Something under the hood",
                )

        assert result["identifier"] == "STU-42"
        assert result["id"] == "issue-uuid-abc"

        # Verify the mutation was called with the correct team_id
        call_args = mock_gql.call_args
        variables = call_args[0][1]  # second positional arg is variables
        assert variables["input"]["teamId"] == team_id
        assert variables["input"]["title"] == "Check this out"

    def test_create_issue_falls_back_description_to_title(self):
        """If description is blank, create_issue should use title as description."""
        team_id = "team-uuid-123"
        mock_response = {
            "issueCreate": {
                "success": True,
                "issue": {
                    "id": "issue-uuid-abc",
                    "identifier": "STU-42",
                },
            }
        }

        with patch.dict(os.environ, {"LINEAR_API_KEY": "lin_test_key", "LINEAR_TEAM_ID": team_id}):
            with patch("tgbot.linear_api._graphql", return_value=mock_response) as mock_gql:
                from tgbot.linear_api import create_issue

                create_issue(title="Short title", description="")

        variables = mock_gql.call_args[0][1]
        assert variables["input"]["title"] == "Short title"
        assert variables["input"]["description"] == "Short title"

    def test_create_issue_uploads_attachments_and_returns_uploaded_metadata(self):
        """create_issue should upload each attachment and return uploaded attachment records."""
        team_id = "team-uuid-123"
        mock_response = {
            "issueCreate": {
                "success": True,
                "issue": {
                    "id": "issue-uuid-abc",
                    "identifier": "STU-42",
                },
            }
        }

        with patch.dict(os.environ, {"LINEAR_API_KEY": "lin_test_key", "LINEAR_TEAM_ID": team_id}):
            with patch("tgbot.linear_api._graphql", return_value=mock_response):
                with patch(
                    "tgbot.linear_api.upload_attachment",
                    side_effect=[
                        {"id": "att-1", "url": "https://cdn.linear.app/assets/1.jpg"},
                        {"id": "att-2", "url": "https://cdn.linear.app/assets/2.jpg"},
                    ],
                ) as mock_upload:
                    from tgbot.linear_api import create_issue

                    result = create_issue(
                        title="Photo issue",
                        description="Photo issue",
                        attachments=[
                            {"filename": "photo_1.jpg", "data": b"one"},
                            {"filename": "photo_2.jpg", "data": b"two"},
                        ],
                    )

        assert mock_upload.call_count == 2
        assert result["attachments"] == [
            {"id": "att-1", "url": "https://cdn.linear.app/assets/1.jpg"},
            {"id": "att-2", "url": "https://cdn.linear.app/assets/2.jpg"},
        ]


class TestUploadAttachment:

    def test_upload_attachment(self):
        """upload_attachment makes 3 calls: fileUpload mutation, PUT, attachmentCreate mutation."""
        file_data = b"fake image bytes"
        issue_id = "issue-uuid-abc"
        filename = "photo.jpg"

        # Responses for the two _graphql calls (fileUpload, then attachmentCreate)
        graphql_responses = [
            {
                "fileUpload": {
                    "success": True,
                    "uploadFile": {
                        "uploadUrl": "https://s3.example.com/upload?token=abc",
                        "assetUrl": "https://cdn.linear.app/assets/photo.jpg",
                        "headers": [{"key": "x-amz-acl", "value": "public-read"}],
                    }
                }
            },
            {
                "attachmentCreate": {
                    "success": True,
                    "attachment": {
                        "id": "attach-uuid-456",
                        "url": "https://cdn.linear.app/assets/photo.jpg",
                    }
                }
            },
        ]

        mock_put_response = MagicMock()
        mock_put_response.raise_for_status = MagicMock()

        with patch.dict(os.environ, {"LINEAR_API_KEY": "lin_test_key"}):
            with patch("tgbot.linear_api._graphql", side_effect=graphql_responses) as mock_gql:
                with patch("httpx.put", return_value=mock_put_response) as mock_put:
                    from tgbot.linear_api import upload_attachment

                    result = upload_attachment(issue_id, filename, file_data)

        # Verify 3-step flow
        assert mock_gql.call_count == 2
        assert mock_put.call_count == 1

        # Step 1: fileUpload mutation called
        first_call_variables = mock_gql.call_args_list[0][0][1]
        assert first_call_variables["filename"] == filename
        assert first_call_variables["contentType"] == "image/jpeg"

        # Step 2: PUT to the upload URL with correct headers
        put_call = mock_put.call_args
        assert put_call[0][0] == "https://s3.example.com/upload?token=abc"
        assert put_call[1]["content"] == file_data

        # Step 3: attachmentCreate called with asset URL and issue_id
        second_call_variables = mock_gql.call_args_list[1][0][1]
        assert second_call_variables["input"]["issueId"] == issue_id
        assert second_call_variables["input"]["url"] == "https://cdn.linear.app/assets/photo.jpg"

        # Final result
        assert result["id"] == "attach-uuid-456"


class TestAddComment:

    def test_add_comment(self):
        """add_comment calls commentCreate mutation with correct issueId and body."""
        issue_id = "issue-uuid-abc"
        body = "Here is some research: check the radiator."

        mock_response = {
            "commentCreate": {
                "success": True,
                "comment": {"id": "comment-uuid-789"},
            }
        }

        with patch.dict(os.environ, {"LINEAR_API_KEY": "lin_test_key"}):
            with patch("tgbot.linear_api._graphql", return_value=mock_response) as mock_gql:
                from tgbot.linear_api import add_comment

                result = add_comment(issue_id, body)

        assert result["id"] == "comment-uuid-789"

        call_variables = mock_gql.call_args[0][1]
        assert call_variables["input"]["issueId"] == issue_id
        assert call_variables["input"]["body"] == body


class TestUpdateIssueState:

    def test_update_issue_state(self):
        """update_issue_state reads STATE_BACKLOG from env and calls issueUpdate with correct state_id."""
        issue_id = "issue-uuid-abc"
        state_id = "state-uuid-backlog"

        mock_response = {
            "issueUpdate": {
                "success": True,
                "issue": {
                    "id": issue_id,
                    "state": {"name": "Backlog"},
                }
            }
        }

        env_vars = {
            "LINEAR_API_KEY": "lin_test_key",
            "STATE_BACKLOG": state_id,
        }

        with patch.dict(os.environ, env_vars):
            with patch("tgbot.linear_api._graphql", return_value=mock_response) as mock_gql:
                from tgbot.linear_api import update_issue_state

                result = update_issue_state(issue_id, "backlog")

        assert result["state"] == "Backlog"

        call_variables = mock_gql.call_args[0][1]
        assert call_variables["id"] == issue_id
        assert call_variables["input"]["stateId"] == state_id
