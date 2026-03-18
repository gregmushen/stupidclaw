import json
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from shared.claude_client import build_user_message, call_claude
from shared.comment_markers import write_marker_comment
from shared.config import get_labels, get_states, get_stale_blocked_hours
from shared.image_handler import download_attachments
from shared.linear_client import graphql
from shared.logging_config import setup_logging

PROMPT_PATH = os.path.join(os.path.dirname(__file__), "..", "prompts", "triage.md")
VALID_TASK_TYPES = {"research", "purchase", "maintenance", "admin", "software"}
VALID_COMPLEXITIES = {"low", "medium", "high"}


def _strip_fenced_json(text: str) -> str:
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.S | re.I)
    if match:
        return match.group(1)
    return text


def parse_triage_response(text: str) -> dict[str, Any]:
    raw = _strip_fenced_json(text).strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Malformed triage JSON: {exc}") from exc

    required = ["task_type", "complexity", "priority", "blocked", "block_reason", "confidence", "notes"]
    missing = [key for key in required if key not in parsed]
    if missing:
        raise ValueError(f"Missing triage fields: {', '.join(missing)}")

    task_type = str(parsed["task_type"]).strip().lower()
    if task_type not in VALID_TASK_TYPES:
        raise ValueError("Invalid task_type")

    complexity = str(parsed["complexity"]).strip().lower()
    if complexity not in VALID_COMPLEXITIES:
        raise ValueError("Invalid complexity")

    try:
        priority = int(parsed["priority"])
    except (TypeError, ValueError) as exc:
        raise ValueError("priority must be int") from exc
    if priority < 0 or priority > 4:
        raise ValueError("priority out of range")

    blocked = bool(parsed["blocked"])
    block_reason = str(parsed["block_reason"]).strip()
    if not blocked:
        block_reason = ""
    elif not block_reason:
        raise ValueError("block_reason required when blocked")

    try:
        confidence = float(parsed["confidence"])
    except (TypeError, ValueError) as exc:
        raise ValueError("confidence must be numeric") from exc
    confidence = max(0.0, min(1.0, confidence))

    return {
        "task_type": task_type,
        "complexity": complexity,
        "priority": priority,
        "blocked": blocked,
        "block_reason": block_reason,
        "confidence": confidence,
        "notes": str(parsed["notes"]).strip(),
    }


def build_triage_input(issue: dict, human_answer: str | None = None) -> str:
    attachments = issue.get("attachments", {}).get("nodes", [])
    attachment_lines = [f"- {att.get('title') or att.get('url', '')}" for att in attachments]
    description = (issue.get("description") or "").strip()
    parts = [
        f"Title: {issue.get('title', '').strip()}",
        f"Description:\n{description}",
        "Attachments:",
    ]
    parts.extend(attachment_lines or ["- none"])
    if human_answer:
        parts.append(f"Clarification:\n{human_answer.strip()}")
    return "\n".join(parts).strip()


def extract_human_answer(comments: list[dict]) -> str | None:
    if not comments:
        return None

    blocked_idx = -1
    for idx, comment in enumerate(comments):
        body = comment.get("body", "")
        if "<!-- blocked -->" in body:
            blocked_idx = idx
    if blocked_idx == -1:
        return None

    for comment in reversed(comments[blocked_idx + 1 :]):
        user = comment.get("user") or {}
        if user.get("isMe"):
            continue
        body = (comment.get("body") or "").strip()
        if body and not body.startswith("<!--"):
            return body
    return None


def is_stale(timestamp: str, threshold_hours: int | None = None) -> bool:
    threshold = threshold_hours if threshold_hours is not None else get_stale_blocked_hours()
    normalized = timestamp.replace("Z", "+00:00")
    updated_at = datetime.fromisoformat(normalized).astimezone(timezone.utc)
    return datetime.now(timezone.utc) - updated_at >= timedelta(hours=threshold)


def _load_prompt() -> str:
    with open(PROMPT_PATH, encoding="utf-8") as fh:
        return fh.read()


def _list_backlog_issues(state_id: str) -> list[dict]:
    data = graphql(
        """
        query($stateId: ID!) {
          issues(filter: { state: { id: { eq: $stateId } } }) {
            nodes {
              id
              identifier
              title
              description
              updatedAt
              attachments { nodes { id title url metadata } }
              comments { nodes { id body createdAt user { id name isMe } } }
            }
          }
        }
        """,
        {"stateId": state_id},
    )
    return data["issues"]["nodes"]


def _list_blocked_issues(state_id: str) -> list[dict]:
    data = graphql(
        """
        query($stateId: ID!) {
          issues(filter: { state: { id: { eq: $stateId } } }) {
            nodes {
              id
              identifier
              title
              description
              updatedAt
              comments { nodes { id body createdAt user { id name isMe } } }
            }
          }
        }
        """,
        {"stateId": state_id},
    )
    return data["issues"]["nodes"]


def _requeue_blocked_issues(states: dict, logger) -> int:
    moved = 0
    blocked_issues = _list_blocked_issues(states["blocked"])
    for issue in blocked_issues:
        comments = issue.get("comments", {}).get("nodes", [])
        answer = extract_human_answer(comments)
        if not answer:
            continue
        graphql(
            """
            mutation($issueId: String!, $stateId: String!) {
              issueUpdate(id: $issueId, input: { stateId: $stateId }) { success }
            }
            """,
            {"issueId": issue["id"], "stateId": states["backlog"]},
        )
        moved += 1
        logger.info("Re-queued blocked issue %s to backlog after human reply", issue.get("identifier", issue["id"]))
    return moved


def _apply_triage(issue: dict, triage: dict, states: dict, labels: dict) -> None:
    label_map = {
        "research": labels["type_research"],
        "purchase": labels["type_purchase"],
        "maintenance": labels["type_maintenance"],
        "admin": labels["type_admin"],
        "software": labels["type_software"],
    }
    if triage["blocked"]:
        graphql(
            """
            mutation($issueId: String!, $stateId: String!, $labelIds: [String!]) {
              issueUpdate(id: $issueId, input: { stateId: $stateId, labelIds: $labelIds }) { success }
            }
            """,
            {
                "issueId": issue["id"],
                "stateId": states["blocked"],
                "labelIds": [labels["clarification"], label_map[triage["task_type"]]],
            },
        )
        write_marker_comment(issue["id"], "blocked", triage["block_reason"])
        try:
            from shared.telegram_notify import notify_blocked
            notify_blocked(
                issue_id=issue["id"],
                identifier=issue.get("identifier", ""),
                title=issue.get("title", ""),
                blocked_message=triage["block_reason"],
            )
        except Exception as e:
            logger.warning("Telegram blocked notification failed: %s", e)
        return

    graphql(
        """
        mutation($issueId: String!, $stateId: String!, $labelIds: [String!]) {
          issueUpdate(id: $issueId, input: { stateId: $stateId, labelIds: $labelIds }) { success }
        }
        """,
        {
            "issueId": issue["id"],
            "stateId": states["triaged"],
            "labelIds": [label_map[triage["task_type"]]],
        },
    )
    write_marker_comment(
        issue["id"],
        "triage",
        json.dumps(triage, ensure_ascii=True, sort_keys=True, indent=2),
    )


def run(max_iterations: int = 1) -> int:
    logger = setup_logging()
    states = get_states()
    labels = get_labels()
    prompt = _load_prompt()

    processed = 0
    for _ in range(max_iterations):
        _requeue_blocked_issues(states, logger)
        issues = _list_backlog_issues(states["backlog"])
        if not issues:
            break
        for issue in issues:
            human_answer = extract_human_answer(issue.get("comments", {}).get("nodes", []))
            user_input = build_triage_input(issue, human_answer)
            images = download_attachments(issue.get("attachments", {}).get("nodes", []))
            response = call_claude(
                system=prompt,
                messages=[build_user_message(user_input, images=images)],
            )
            text = response.content[0].text
            triage = parse_triage_response(text)
            _apply_triage(issue, triage, states, labels)
            processed += 1
            logger.info("Triaged %s", issue.get("identifier", issue["id"]))
    return processed


if __name__ == "__main__":
    run(max_iterations=1)
