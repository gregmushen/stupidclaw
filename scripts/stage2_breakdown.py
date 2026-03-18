import json
import os
import re
from typing import Any

from shared.claude_client import call_claude
from shared.comment_markers import write_marker_comment
from shared.config import get_labels, get_states
from shared.linear_client import graphql
from shared.logging_config import setup_logging

PROMPT_PATH = os.path.join(os.path.dirname(__file__), "..", "prompts", "breakdown.md")
VALID_TYPES = {"agent", "human"}


def _strip_fenced_json(text: str) -> str:
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.S | re.I)
    if match:
        return match.group(1)
    return text


def parse_breakdown_response(text: str) -> list[dict[str, str]]:
    raw = _strip_fenced_json(text).strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Malformed breakdown JSON: {exc}") from exc

    if "tasks" not in parsed or not isinstance(parsed["tasks"], list):
        raise ValueError("tasks array is required")
    if not parsed["tasks"]:
        raise ValueError("at least one task required")

    normalized: list[dict[str, str]] = []
    for task in parsed["tasks"]:
        if not isinstance(task, dict):
            raise ValueError("task must be object")
        for key in ["title", "type", "description"]:
            if key not in task:
                raise ValueError(f"missing task field: {key}")
        task_type = str(task["type"]).strip().lower()
        if task_type not in VALID_TYPES:
            raise ValueError("task type must be agent or human")
        normalized.append(
            {
                "title": str(task["title"]).strip(),
                "type": task_type,
                "description": str(task["description"]).strip(),
            }
        )
    return normalized


def format_breakdown_comment(tasks: list[dict[str, str]]) -> str:
    lines = ["Subtasks created:"]
    for idx, task in enumerate(tasks, start=1):
        lines.append(f"{idx}. [{task['type']}] {task['title']} - {task['description']}")
    return "\n".join(lines)


def _load_prompt() -> str:
    with open(PROMPT_PATH, encoding="utf-8") as fh:
        return fh.read()


def _list_triaged_issues(state_id: str) -> list[dict]:
    data = graphql(
        """
        query($stateId: String!) {
          issues(filter: { state: { id: { eq: $stateId } } }) {
            nodes {
              id
              identifier
              title
              description
              attachments { nodes { id title url metadata } }
            }
          }
        }
        """,
        {"stateId": state_id},
    )
    return data["issues"]["nodes"]


def _create_subtasks(parent_issue: dict, tasks: list[dict[str, str]], labels: dict, states: dict) -> None:
    first_agent_started = False
    for index, task in enumerate(tasks, start=1):
        label_id = labels["agent_task"] if task["type"] == "agent" else labels["human_task"]
        if task["type"] == "agent" and not first_agent_started:
            state_id = states["in_progress"]
            first_agent_started = True
        else:
            state_id = states["todo"]
        graphql(
            """
            mutation(
              $title: String!,
              $description: String!,
              $parentId: String!,
              $labelIds: [String!],
              $sortOrder: Float!,
              $stateId: String!
            ) {
              issueCreate(
                input: {
                  title: $title,
                  description: $description,
                  parentId: $parentId,
                  labelIds: $labelIds,
                  sortOrder: $sortOrder,
                  stateId: $stateId
                }
              ) {
                success
                issue { id identifier }
              }
            }
            """,
            {
                "title": task["title"],
                "description": task["description"],
                "parentId": parent_issue["id"],
                "labelIds": [label_id],
                "sortOrder": float(index),
                "stateId": state_id,
            },
        )


def run(max_iterations: int = 1) -> int:
    logger = setup_logging()
    states = get_states()
    labels = get_labels()
    prompt = _load_prompt()

    processed = 0
    for _ in range(max_iterations):
        issues = _list_triaged_issues(states["triaged"])
        if not issues:
            break
        for issue in issues:
            user_input = f"Title: {issue.get('title', '')}\n\nDescription:\n{issue.get('description', '')}"
            response = call_claude(system=prompt, messages=[{"role": "user", "content": user_input}])
            tasks = parse_breakdown_response(response.content[0].text)
            _create_subtasks(issue, tasks, labels, states)
            graphql(
                """
                mutation($issueId: String!, $stateId: String!) {
                  issueUpdate(id: $issueId, input: { stateId: $stateId }) { success }
                }
                """,
                {"issueId": issue["id"], "stateId": states["planning_complete"]},
            )
            write_marker_comment(issue["id"], "breakdown", format_breakdown_comment(tasks))
            processed += 1
            logger.info("Broke down %s into %s subtasks", issue.get("identifier", issue["id"]), len(tasks))
    return processed


if __name__ == "__main__":
    run(max_iterations=1)
