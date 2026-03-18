from shared.linear_client import graphql

MARKERS = {
    "triage": "<!-- triage-result -->",
    "breakdown": "<!-- breakdown-result -->",
    "research": "<!-- research-result -->",
    "summary": "<!-- summary -->",
    "blocked": "<!-- blocked -->",
}


def has_marker(comments: list[dict], marker_key: str) -> bool:
    marker = MARKERS[marker_key]
    return any(marker in comment.get("body", "") for comment in comments)


def get_marker_content(comments: list[dict], marker_key: str) -> str | None:
    marker = MARKERS[marker_key]
    for comment in comments:
        body = comment.get("body", "")
        if marker in body:
            return body
    return None


def get_all_marker_contents(comments: list[dict], marker_key: str) -> list[str]:
    marker = MARKERS[marker_key]
    return [comment.get("body", "") for comment in comments if marker in comment.get("body", "")]


def write_marker_comment(issue_id: str, marker_key: str, content: str) -> str:
    marker = MARKERS[marker_key]
    body = f"{marker}\n\n{content}"
    data = graphql(
        """
        mutation($id: String!, $body: String!) {
          commentCreate(input: { issueId: $id, body: $body }) {
            success
            comment { id }
          }
        }
        """,
        {"id": issue_id, "body": body},
    )
    return data["commentCreate"]["comment"]["id"]
