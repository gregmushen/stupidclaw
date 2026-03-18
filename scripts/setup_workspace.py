#!/usr/bin/env python3
"""One-time setup: query STU team for state and label IDs.

Run this after creating the STU team with states and labels in Linear UI.
Outputs env var assignments to paste into .env.

Usage:
    LINEAR_API_KEY="$LINEAR_KEY_GREG" python scripts/setup_workspace.py
"""

import sys
import os

# Add parent directory to path so we can import shared modules
sys.path.insert(0, os.path.dirname(__file__))

from shared.linear_client import graphql


def main():
    print("# === STU Team State IDs ===")
    print("# Paste these into your .env file")
    print()

    # Query workflow states for the STU team
    result = graphql("""
        query {
            workflowStates(filter: { team: { key: { eq: "STU" } } }) {
                nodes { id name type }
            }
        }
    """)

    states = result["workflowStates"]["nodes"]
    if not states:
        print("ERROR: No workflow states found for team STU.", file=sys.stderr)
        print("Did you create the STU team and add workflow states?", file=sys.stderr)
        sys.exit(1)

    # Map state names to env var names
    STATE_MAP = {
        "Backlog": "STATE_BACKLOG",
        "Todo": "STATE_TODO",
        "Triaged": "STATE_TRIAGED",
        "Planning Complete": "STATE_PLANNING_COMPLETE",
        "In Progress": "STATE_IN_PROGRESS",
        "In Review": "STATE_IN_REVIEW",
        "Blocked": "STATE_BLOCKED",
        "Done": "STATE_DONE",
        "Cancelled": "STATE_CANCELLED",
    }

    for state in states:
        env_key = STATE_MAP.get(state["name"])
        if env_key:
            print(f"{env_key}={state['id']}")
        else:
            print(f"# Unknown state: {state['name']} ({state['type']}) = {state['id']}")

    found_states = {s["name"] for s in states}
    missing = set(STATE_MAP.keys()) - found_states
    if missing:
        print(f"\n# WARNING: Missing states: {', '.join(sorted(missing))}", file=sys.stderr)

    print()
    print("# === Label IDs ===")
    print()

    # Query labels (workspace-level, not team-scoped)
    result = graphql("""
        query {
            issueLabels(filter: { team: { key: { eq: "STU" } } }) {
                nodes { id name }
            }
        }
    """)

    labels = result["issueLabels"]["nodes"]

    LABEL_MAP = {
        "agent-task": "LABEL_AGENT_TASK",
        "human-task": "LABEL_HUMAN_TASK",
        "clarification": "LABEL_CLARIFICATION",
        "scope-change": "LABEL_SCOPE_CHANGE",
        "stupidclaw:error": "LABEL_ERROR",
        "type:research": "LABEL_TYPE_RESEARCH",
        "type:purchase": "LABEL_TYPE_PURCHASE",
        "type:maintenance": "LABEL_TYPE_MAINTENANCE",
        "type:admin": "LABEL_TYPE_ADMIN",
        "type:software": "LABEL_TYPE_SOFTWARE",
    }

    for label in labels:
        env_key = LABEL_MAP.get(label["name"])
        if env_key:
            print(f"{env_key}={label['id']}")
        else:
            print(f"# Unknown label: {label['name']} = {label['id']}")

    found_labels = {l["name"] for l in labels}
    missing_labels = set(LABEL_MAP.keys()) - found_labels
    if missing_labels:
        print(f"\n# WARNING: Missing labels: {', '.join(sorted(missing_labels))}", file=sys.stderr)

    # Also get the team ID
    print()
    print("# === Team ID ===")
    team_result = graphql("""
        query {
            teams(filter: { key: { eq: "STU" } }) {
                nodes { id name key }
            }
        }
    """)
    teams = team_result["teams"]["nodes"]
    if teams:
        print(f"LINEAR_TEAM_ID={teams[0]['id']}")
    else:
        print("# ERROR: STU team not found!", file=sys.stderr)


if __name__ == "__main__":
    main()
