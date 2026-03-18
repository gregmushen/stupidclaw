import json
import os
import re
from typing import Any

from shared.claude_client import call_claude
from shared.comment_markers import (
    get_all_marker_contents,
    write_marker_comment,
)
from shared.config import get_labels, get_states
from shared.linear_client import graphql
from shared.logging_config import setup_logging

PROMPT_PATH = os.path.join(os.path.dirname(__file__), "..", "prompts", "research.md")
TERMINAL_STATES = {"done", "blocked", "cancelled", "canceled"}


def _strip_fenced_json(text: str) -> str:
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.S | re.I)
    if match:
        return match.group(1)
    return text


def parse_research_response(text: str) -> dict[str, Any]:
    raw = _strip_fenced_json(text).strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Malformed research JSON: {exc}") from exc

    if "result" not in parsed:
        # Back-compat flags with deterministic precedence.
        scope_change = bool(parsed.get("scope_change"))
        needs_human = bool(parsed.get("needs_human"))
        blocked = bool(parsed.get("blocked"))
        if scope_change:
            result = "scope_change"
        elif needs_human:
            result = "needs_human"
        elif blocked:
            result = "blocked"
        else:
            result = "completed"
    else:
        result = str(parsed["result"]).strip().lower()

    if result not in {"completed", "blocked", "needs_human", "scope_change"}:
        raise ValueError("Invalid research result")

    confidence = parsed.get("confidence", 0.0)
    try:
        confidence = float(confidence)
    except (TypeError, ValueError) as exc:
        raise ValueError("confidence must be numeric") from exc
    confidence = max(0.0, min(1.0, confidence))

    return {
        "result": result,
        "summary": str(parsed.get("summary", "")).strip(),
        "details": str(parsed.get("details", "")).strip(),
        "confidence": confidence,
    }


def build_research_input(
    parent_issue: dict,
    child_issue: dict,
    sibling_results: list[str],
    human_context: str | None = None,
) -> str:
    parent_title = parent_issue.get("title", "").strip()
    parent_desc = (parent_issue.get("description") or "").strip()
    child_title = child_issue.get("title", "").strip()
    child_desc = (child_issue.get("description") or "").strip()

    lines = [
        f"Parent: {parent_title}",
        "Parent description:",
        parent_desc or "(none)",
        "",
        f"Current subtask: {child_title}",
        "Subtask description:",
        child_desc or "(none)",
        "",
        "Prior sibling results:",
    ]
    if sibling_results:
        for idx, result in enumerate(sibling_results, start=1):
            lines.append(f"{idx}. {result}")
    else:
        lines.append("(none)")
    if human_context:
        lines.extend(["", "Human context:", human_context.strip()])
    return "\n".join(lines)


def check_predecessors(children: list[dict], current_id: str) -> bool:
    ordered = sorted(children, key=lambda c: float(c.get("sortOrder", 0.0)))
    current = next((c for c in ordered if c["id"] == current_id), None)
    if current is None:
        return False
    current_order = float(current.get("sortOrder", 0.0))
    for child in ordered:
        if float(child.get("sortOrder", 0.0)) >= current_order:
            continue
        state = str(child.get("state", {}).get("name", "")).strip().lower()
        if state not in TERMINAL_STATES:
            return False
    return True


def find_next_agent_sibling(children: list[dict], current_id: str) -> dict | None:
    ordered = sorted(children, key=lambda c: float(c.get("sortOrder", 0.0)))
    current = next((c for c in ordered if c["id"] == current_id), None)
    if current is None:
        return None
    current_order = float(current.get("sortOrder", 0.0))
    for child in ordered:
        if float(child.get("sortOrder", 0.0)) <= current_order:
            continue
        labels = [node.get("name", "") for node in child.get("labels", {}).get("nodes", [])]
        if "agent-task" not in labels:
            continue
        state = str(child.get("state", {}).get("name", "")).strip().lower()
        if state in {"todo", "backlog", "triaged", "planning_complete"}:
            return child
    return None


def all_children_terminal(children: list[dict]) -> bool:
    if not children:
        return True
    for child in children:
        state = str(child.get("state", {}).get("name", "")).strip().lower()
        if state not in TERMINAL_STATES:
            return False
    return True


def determine_parent_state(children: list[dict]) -> str:
    lowered = [str(child.get("state", {}).get("name", "")).strip().lower() for child in children]
    if any(state == "blocked" for state in lowered):
        return "blocked"
    return "done"


def build_rollup_summary(parent_issue: dict, children: list[dict]) -> str:
    lines = [f"Rollup summary for {parent_issue.get('identifier', parent_issue.get('id', 'parent'))}:"]
    for child in sorted(children, key=lambda c: float(c.get("sortOrder", 0.0))):
        identifier = child.get("identifier", child.get("id", "unknown"))
        state = child.get("state", {}).get("name", "unknown")
        comments = child.get("comments", {}).get("nodes", [])
        research_notes = get_all_marker_contents(comments, "research")
        details = research_notes[-1].split("\n", 1)[-1] if research_notes else "No research note"
        lines.append(f"- {identifier} [{state}]: {details}")
    return "\n".join(lines)


def _load_prompt() -> str:
    with open(PROMPT_PATH, encoding="utf-8") as fh:
        return fh.read()


def _list_active_agent_subtasks(state_id: str, agent_label_id: str) -> list[dict]:
    data = graphql(
        """
        query($stateId: String!, $labelId: String!) {
          issues(filter: { state: { id: { eq: $stateId } }, labels: { id: { eq: $labelId } } }) {
            nodes {
              id
              identifier
              title
              description
              sortOrder
              state { id name }
              labels { nodes { id name } }
              parent { id identifier }
              comments { nodes { id body createdAt user { id name isMe } } }
            }
          }
        }
        """,
        {"stateId": state_id, "labelId": agent_label_id},
    )
    return data["issues"]["nodes"]


def _get_parent_with_children(parent_id: str) -> dict:
    data = graphql(
        """
        query($id: String!) {
          issue(id: $id) {
            id
            identifier
            title
            description
            state { id name }
            comments { nodes { id body createdAt user { id name isMe } } }
            children {
              nodes {
                id
                identifier
                title
                description
                sortOrder
                state { id name }
                labels { nodes { id name } }
                comments { nodes { id body createdAt user { id name isMe } } }
              }
            }
          }
        }
        """,
        {"id": parent_id},
    )
    return data["issue"]


def _state_id_for_name(states: dict[str, str], state_name: str) -> str:
    return states[state_name]


def run(max_iterations: int = 1) -> int:
    logger = setup_logging()
    states = get_states()
    labels = get_labels()
    prompt = _load_prompt()

    processed = 0
    for _ in range(max_iterations):
        current_tasks = _list_active_agent_subtasks(states["in_progress"], labels["agent_task"])
        if not current_tasks:
            break

        for task in current_tasks:
            parent = task.get("parent")
            if not parent:
                continue
            parent_issue = _get_parent_with_children(parent["id"])
            children = parent_issue.get("children", {}).get("nodes", [])
            if not check_predecessors(children, task["id"]):
                continue

            ordered = sorted(children, key=lambda c: float(c.get("sortOrder", 0.0)))
            sibling_results: list[str] = []
            for child in ordered:
                if child["id"] == task["id"]:
                    break
                notes = get_all_marker_contents(child.get("comments", {}).get("nodes", []), "research")
                if notes:
                    sibling_results.append(notes[-1].split("\n", 1)[-1])

            user_text = build_research_input(parent_issue, task, sibling_results)
            response = call_claude(system=prompt, messages=[{"role": "user", "content": user_text}])
            parsed = parse_research_response(response.content[0].text)

            if parsed["result"] == "completed":
                graphql(
                    """
                    mutation($issueId: String!, $stateId: String!) {
                      issueUpdate(id: $issueId, input: { stateId: $stateId }) { success }
                    }
                    """,
                    {"issueId": task["id"], "stateId": _state_id_for_name(states, "done")},
                )
                note = parsed["details"] or parsed["summary"] or "Research completed"
                write_marker_comment(task["id"], "research", note)

                refreshed_parent = _get_parent_with_children(parent["id"])
                refreshed_children = refreshed_parent.get("children", {}).get("nodes", [])
                next_sibling = find_next_agent_sibling(refreshed_children, task["id"])
                if next_sibling:
                    graphql(
                        """
                        mutation($issueId: String!, $stateId: String!) {
                          issueUpdate(id: $issueId, input: { stateId: $stateId }) { success }
                        }
                        """,
                        {"issueId": next_sibling["id"], "stateId": _state_id_for_name(states, "in_progress")},
                    )

                if all_children_terminal(refreshed_children):
                    parent_state_key = determine_parent_state(refreshed_children)
                    graphql(
                        """
                        mutation($issueId: String!, $stateId: String!) {
                          issueUpdate(id: $issueId, input: { stateId: $stateId }) { success }
                        }
                        """,
                        {"issueId": refreshed_parent["id"], "stateId": _state_id_for_name(states, parent_state_key)},
                    )
                    write_marker_comment(
                        refreshed_parent["id"],
                        "summary",
                        build_rollup_summary(refreshed_parent, refreshed_children),
                    )
                    try:
                        from shared.telegram_notify import notify_completed
                        human_remaining = sum(
                            1 for c in refreshed_children
                            if c["state"]["name"].lower() == "todo"
                            and any(l["name"] == "human-task" for l in c.get("labels", {}).get("nodes", []))
                        )
                        notify_completed(
                            issue_id=refreshed_parent["id"],
                            identifier=refreshed_parent.get("identifier", ""),
                            title=refreshed_parent.get("title", ""),
                            state=parent_state_key,
                            human_tasks_remaining=human_remaining,
                            link=f"https://linear.app/gre/issue/{refreshed_parent.get('identifier', '')}",
                        )
                    except Exception as e:
                        logger.warning("Telegram completed notification failed: %s", e)

            elif parsed["result"] in {"blocked", "needs_human", "scope_change"}:
                label_ids = [labels["clarification"]] if parsed["result"] == "needs_human" else []
                if parsed["result"] == "scope_change":
                    label_ids.append(labels["scope_change"])

                graphql(
                    """
                    mutation($issueId: String!, $stateId: String!, $labelIds: [String!]) {
                      issueUpdate(id: $issueId, input: { stateId: $stateId, labelIds: $labelIds }) { success }
                    }
                    """,
                    {
                        "issueId": task["id"],
                        "stateId": _state_id_for_name(states, "blocked"),
                        "labelIds": label_ids,
                    },
                )
                marker = "blocked" if parsed["result"] != "scope_change" else "summary"
                write_marker_comment(task["id"], marker, parsed["details"] or parsed["summary"] or parsed["result"])
                try:
                    from shared.telegram_notify import notify_blocked
                    notify_blocked(
                        issue_id=task["id"],
                        identifier=task.get("identifier", ""),
                        title=task.get("title", ""),
                        blocked_message=parsed["details"] or parsed["summary"] or "",
                    )
                except Exception as e:
                    logger.warning("Telegram blocked notification failed: %s", e)

            processed += 1
            logger.info("Processed research for %s", task.get("identifier", task["id"]))
    return processed


if __name__ == "__main__":
    run(max_iterations=1)
