import json
import os
import re
from typing import Any


class MockLinearClient:
    """In-memory GraphQL router used by tests to replace Linear API calls."""

    def __init__(self) -> None:
        self._issues: dict[str, dict[str, Any]] = {}
        self._comments: dict[str, list[dict[str, Any]]] = {}
        self._state_map: dict[str, str] = {}
        self._label_map: dict[str, str] = {}
        self._id_counter = 1

    def graphql(self, query: str, variables: dict | None = None) -> dict:
        """Drop-in replacement for shared.linear_client.graphql."""
        variables = variables or {}

        # 7 handlers routed by query shape.
        if re.search(r"issues\s*\(\s*filter:.*state:.*labels:", query, flags=re.S):
            return self._handle_issues_by_state_label(variables)
        if re.search(r"issues\s*\(\s*filter:.*state:", query, flags=re.S):
            return self._handle_issues_by_state(variables)
        if re.search(r"issue\s*\(", query):
            return self._handle_issue_by_id_or_identifier(variables)
        if re.search(r"issueCreate", query):
            return self._handle_issue_create(variables)
        if re.search(r"issueUpdate", query):
            return self._handle_issue_update(variables)
        if re.search(r"commentCreate", query):
            return self._handle_comment_create(variables)
        if re.search(r"\bcomments\b", query):
            return self._handle_comments_for_issue(variables)
        raise ValueError(f"MockLinearClient: unsupported query: {query[:120]}")

    def _handle_issues_by_state(self, variables: dict) -> dict:
        state_id = variables.get("stateId")
        matches = [
            self._expand_issue(issue)
            for issue in self._issues.values()
            if issue["state"]["id"] == state_id
        ]
        return {"issues": {"nodes": matches}}

    def _handle_issues_by_state_label(self, variables: dict) -> dict:
        state_id = variables.get("stateId")
        label_id = variables.get("labelId")
        normalized_label_id = str(label_id).replace("_", "-")
        matches = [
            self._expand_issue(issue)
            for issue in self._issues.values()
            if issue["state"]["id"] == state_id
            and any(node["id"].replace("_", "-") == normalized_label_id for node in issue["labels"]["nodes"])
        ]
        return {"issues": {"nodes": matches}}

    def _handle_issue_by_id_or_identifier(self, variables: dict) -> dict:
        issue_id = variables.get("id")
        identifier = variables.get("identifier")

        issue = None
        if issue_id:
            issue = self._issues.get(issue_id)
        elif identifier:
            issue = next((i for i in self._issues.values() if i["identifier"] == identifier), None)
        if issue is None:
            return {"issue": None}
        return {"issue": self._expand_issue(issue)}

    def _handle_issue_create(self, variables: dict) -> dict:
        new_id = f"auto-{self._id_counter}"
        new_identifier = f"STU-{1000 + self._id_counter}"
        self._id_counter += 1

        state_id = variables.get("stateId", "state-backlog")
        issue = {
            "id": new_id,
            "identifier": new_identifier,
            "title": variables.get("title", ""),
            "description": variables.get("description", ""),
            "priority": variables.get("priority", 0),
            "sortOrder": float(variables.get("sortOrder", 0.0)),
            "state": {"id": state_id, "name": self._state_name_for_id(state_id)},
            "parent": {"id": variables["parentId"], "identifier": ""} if variables.get("parentId") else None,
            "labels": {
                "nodes": [
                    {"id": lid, "name": self._label_name_for_id(lid)}
                    for lid in variables.get("labelIds", [])
                ]
            },
            "attachments": {"nodes": []},
        }
        self._issues[new_id] = issue
        self._comments[new_id] = []
        return {
            "issueCreate": {
                "success": True,
                "issue": {"id": new_id, "identifier": new_identifier},
            }
        }

    def _handle_issue_update(self, variables: dict) -> dict:
        issue_id = variables.get("issueId", variables.get("id"))
        issue = self._issues[issue_id]

        if "stateId" in variables:
            state_id = variables["stateId"]
            issue["state"] = {"id": state_id, "name": self._state_name_for_id(state_id)}
        if "labelIds" in variables:
            issue["labels"] = {
                "nodes": [
                    {"id": lid, "name": self._label_name_for_id(lid)}
                    for lid in variables["labelIds"]
                ]
            }
        if "description" in variables:
            issue["description"] = variables["description"]
        return {"issueUpdate": {"success": True}}

    def _handle_comment_create(self, variables: dict) -> dict:
        issue_id = variables.get("issueId", variables.get("id"))
        body = variables.get("body", "")
        comment_id = f"comment-{self._id_counter}"
        self._id_counter += 1

        self._comments.setdefault(issue_id, []).append(
            {
                "id": comment_id,
                "body": body,
                "createdAt": "2026-01-01T00:00:00Z",
                "user": {"id": "bot", "name": "StupidClaw", "isMe": True},
            }
        )
        return {"commentCreate": {"success": True, "comment": {"id": comment_id}}}

    def _handle_comments_for_issue(self, variables: dict) -> dict:
        issue_id = variables.get("issueId", variables.get("id"))
        return {"comments": {"nodes": list(self._comments.get(issue_id, []))}}

    def _expand_issue(self, issue: dict) -> dict:
        issue_id = issue["id"]
        children = [
            i
            for i in self._issues.values()
            if i.get("parent") and i["parent"]["id"] == issue_id
        ]
        children.sort(key=lambda i: i.get("sortOrder", 0.0))
        return {
            **issue,
            "children": {
                "nodes": [
                    {
                        "id": child["id"],
                        "identifier": child["identifier"],
                        "state": child["state"],
                        "sortOrder": child.get("sortOrder", 0.0),
                        "labels": child["labels"],
                    }
                    for child in children
                ]
            },
            "comments": {"nodes": list(self._comments.get(issue_id, []))},
        }

    def _state_name_for_id(self, state_id: str) -> str:
        for name, candidate in self._state_map.items():
            if candidate == state_id:
                return name
        if state_id.startswith("state-"):
            return state_id[len("state-") :]
        return state_id

    def _label_name_for_id(self, label_id: str) -> str:
        for name, candidate in self._label_map.items():
            if candidate == label_id:
                return name
        if label_id.startswith("label-"):
            return label_id[len("label-") :].replace("_", "-")
        return label_id

    def seed_issue(
        self,
        *,
        id: str,
        title: str,
        state: str,
        description: str = "",
        labels: list[str] | None = None,
        attachments: list[dict] | None = None,
        comments: list[dict] | None = None,
        children: list[dict] | None = None,
        parent_id: str | None = None,
        sort_order: float = 0.0,
    ) -> None:
        state_id = f"state-{state}"
        self._state_map[state] = state_id

        label_nodes = []
        for label in labels or []:
            label_id = f"label-{label}"
            self._label_map[label] = label_id
            label_nodes.append({"id": label_id, "name": label})

        issue = {
            "id": id,
            "identifier": f"STU-{id}",
            "title": title,
            "description": description,
            "priority": 0,
            "sortOrder": float(sort_order),
            "state": {"id": state_id, "name": state},
            "parent": {"id": parent_id, "identifier": ""} if parent_id else None,
            "labels": {"nodes": label_nodes},
            "attachments": {"nodes": attachments or []},
        }
        self._issues[id] = issue
        self._comments.setdefault(id, [])

        for comment in comments or []:
            self._comments[id].append(
                {
                    "id": f"comment-{self._id_counter}",
                    "body": comment["body"],
                    "createdAt": comment.get("createdAt", "2026-01-01T00:00:00Z"),
                    "user": comment.get(
                        "user",
                        {"id": "seed", "name": "Fixture", "isMe": False},
                    ),
                }
            )
            self._id_counter += 1

        for child in children or []:
            self.seed_issue(
                id=child["id"],
                title=child.get("title", ""),
                state=child["state"],
                description=child.get("description", ""),
                labels=child.get("labels", []),
                attachments=child.get("attachments", []),
                comments=child.get("comments", []),
                children=child.get("children", []),
                parent_id=id,
                sort_order=float(child.get("sortOrder", 0.0)),
            )

    def seed_from_file(self, fixture_name: str) -> None:
        fixture_dir = os.path.join(os.path.dirname(__file__), "fixtures")
        full_path = os.path.join(fixture_dir, fixture_name)
        with open(full_path, encoding="utf-8") as fh:
            payload = json.load(fh)
        for issue in payload.get("issues", []):
            self.seed_issue(
                id=issue["id"],
                title=issue["title"],
                state=issue["state"],
                description=issue.get("description", ""),
                labels=issue.get("labels", []),
                attachments=issue.get("attachments", []),
                comments=issue.get("comments", []),
                children=issue.get("children", []),
                parent_id=issue.get("parent_id"),
                sort_order=float(issue.get("sortOrder", 0.0)),
            )

    def assert_issue_state(self, issue_id: str, expected_state: str) -> None:
        actual = self._issues[issue_id]["state"]["name"]
        if actual != expected_state:
            raise AssertionError(f"Issue {issue_id} state is {actual}, expected {expected_state}")

    def assert_comment_contains(self, issue_id: str, text: str) -> None:
        bodies = [comment["body"] for comment in self._comments.get(issue_id, [])]
        if not any(text in body for body in bodies):
            raise AssertionError(f"No comment on {issue_id} contained: {text}")
