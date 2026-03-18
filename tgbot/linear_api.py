"""Linear GraphQL client for the Telegram bot.

Handles issue creation, file attachment upload, comment posting,
and state transitions.
"""

import logging
import os

import httpx

logger = logging.getLogger("stupidclaw.telegram.linear")

LINEAR_API_URL = "https://api.linear.app/graphql"


def _get_api_key() -> str:
    """Read LINEAR_API_KEY from env at call time."""
    from tgbot.config import get_linear_api_key
    return get_linear_api_key()


def _graphql(query: str, variables: dict = None) -> dict:
    """POST a GraphQL query to the Linear API.

    Args:
        query: GraphQL query or mutation string.
        variables: Optional variables dict.

    Returns:
        The 'data' field from the response.

    Raises:
        httpx.HTTPStatusError: on 4xx/5xx responses.
        ValueError: if the response contains GraphQL errors.
    """
    headers = {
        "Authorization": _get_api_key(),
        "Content-Type": "application/json",
    }
    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    response = httpx.post(
        LINEAR_API_URL,
        json=payload,
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()

    body = response.json()
    if "errors" in body:
        raise ValueError(f"Linear GraphQL error: {body['errors']}")

    return body.get("data", {})


def create_issue(
    title: str,
    description: str,
    attachments: list[dict] = None,
) -> dict:
    """Create a Linear issue in the STU team.

    Args:
        title: Issue title.
        description: Markdown body for the issue.
        attachments: Optional list of attachment dicts (already uploaded).

    Returns:
        {"id": str, "identifier": str, "attachments": list}
    """
    from tgbot.config import get_linear_team_id

    mutation = """
    mutation CreateIssue($input: IssueCreateInput!) {
        issueCreate(input: $input) {
            success
            issue {
                id
                identifier
            }
        }
    }
    """

    safe_title = (title or "").strip() or "Task"
    safe_description = (description or "").strip() or safe_title

    variables = {
        "input": {
            "teamId": get_linear_team_id(),
            "title": safe_title,
            "description": safe_description,
        }
    }

    data = _graphql(mutation, variables)
    issue = data["issueCreate"]["issue"]

    uploaded_attachments: list[dict] = []
    for attachment in attachments or []:
        filename = attachment.get("filename", "attachment.bin")
        payload = attachment.get("data")
        if payload is None:
            logger.warning("Skipping attachment with missing data: %s", filename)
            continue
        try:
            uploaded_attachments.append(upload_attachment(issue["id"], filename, payload))
        except Exception as exc:  # pragma: no cover - defensive logging for runtime failures
            logger.exception("Attachment upload failed for %s on issue %s: %s", filename, issue["identifier"], exc)

    return {
        "id": issue["id"],
        "identifier": issue["identifier"],
        "attachments": uploaded_attachments,
    }


def upload_attachment(issue_id: str, filename: str, data: bytes) -> dict:
    """Upload a file and attach it to a Linear issue.

    Uses Linear's 3-step upload flow:
      1. Get a presigned upload URL via fileUpload mutation.
      2. PUT the file data to the presigned URL.
      3. Create an attachment record on the issue via attachmentCreate mutation.

    Args:
        issue_id: The Linear issue ID (UUID).
        filename: The original filename (e.g. "photo.jpg").
        data: Raw file bytes.

    Returns:
        {"id": str, "url": str} — the created attachment record.
    """
    # Step 1: Get presigned upload URL
    upload_mutation = """
    mutation FileUpload($filename: String!, $contentType: String!) {
        fileUpload(filename: $filename, contentType: $contentType) {
            success
            uploadFile {
                uploadUrl
                assetUrl
                headers {
                    key
                    value
                }
            }
        }
    }
    """
    content_type = _infer_content_type(filename)
    upload_data = _graphql(upload_mutation, {
        "filename": filename,
        "contentType": content_type,
    })
    upload_file = upload_data["fileUpload"]["uploadFile"]
    upload_url = upload_file["uploadUrl"]
    asset_url = upload_file["assetUrl"]
    extra_headers = {h["key"]: h["value"] for h in upload_file.get("headers", [])}

    # Step 2: PUT file data to presigned URL
    put_headers = {"Content-Type": content_type, **extra_headers}
    response = httpx.put(upload_url, content=data, headers=put_headers, timeout=60)
    response.raise_for_status()

    # Step 3: Create attachment record on the issue
    attach_mutation = """
    mutation AttachmentCreate($input: AttachmentCreateInput!) {
        attachmentCreate(input: $input) {
            success
            attachment {
                id
                url
            }
        }
    }
    """
    attach_data = _graphql(attach_mutation, {
        "input": {
            "issueId": issue_id,
            "url": asset_url,
            "title": filename,
        }
    })
    attachment = attach_data["attachmentCreate"]["attachment"]
    return {"id": attachment["id"], "url": attachment["url"]}


def add_comment(issue_id: str, body: str) -> dict:
    """Post a comment on a Linear issue.

    Args:
        issue_id: The Linear issue ID (UUID).
        body: Markdown comment body.

    Returns:
        {"id": str}
    """
    mutation = """
    mutation CommentCreate($input: CommentCreateInput!) {
        commentCreate(input: $input) {
            success
            comment {
                id
            }
        }
    }
    """
    data = _graphql(mutation, {"input": {"issueId": issue_id, "body": body}})
    return {"id": data["commentCreate"]["comment"]["id"]}


def update_issue_state(issue_id: str, state_name: str) -> dict:
    """Move a Linear issue to a named state.

    Looks up the state ID from env vars using the naming convention:
    state_name "backlog" -> env var STATE_BACKLOG

    Args:
        issue_id: The Linear issue ID (UUID).
        state_name: Lowercase state name with underscores (e.g. "backlog").

    Returns:
        {"id": str, "state": str}

    Raises:
        EnvironmentError: if the corresponding STATE_* env var is not set.
    """
    env_key = f"STATE_{state_name.upper()}"
    state_id = os.environ.get(env_key)
    if not state_id:
        raise EnvironmentError(f"{env_key} is required for state '{state_name}'")

    mutation = """
    mutation IssueUpdate($id: String!, $input: IssueUpdateInput!) {
        issueUpdate(id: $id, input: $input) {
            success
            issue {
                id
                state {
                    name
                }
            }
        }
    }
    """
    data = _graphql(mutation, {"id": issue_id, "input": {"stateId": state_id}})
    issue = data["issueUpdate"]["issue"]
    return {"id": issue["id"], "state": issue["state"]["name"]}


def _infer_content_type(filename: str) -> str:
    """Return MIME type based on file extension. Defaults to application/octet-stream."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "webp": "image/webp",
        "pdf": "application/pdf",
    }.get(ext, "application/octet-stream")
