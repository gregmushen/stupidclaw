from shared.comment_markers import (
    get_all_marker_contents,
    get_marker_content,
    has_marker,
    write_marker_comment,
)


def test_has_marker_true():
    comments = [{"body": "<!-- triage-result -->\nLooks valid"}]
    assert has_marker(comments, "triage") is True


def test_has_marker_false():
    comments = [{"body": "No marker in this comment"}]
    assert has_marker(comments, "triage") is False


def test_get_marker_content_found():
    comments = [
        {"body": "irrelevant"},
        {"body": "<!-- breakdown-result -->\nGenerated subtasks"},
    ]
    assert get_marker_content(comments, "breakdown") == "<!-- breakdown-result -->\nGenerated subtasks"


def test_get_marker_content_not_found():
    comments = [{"body": "plain text"}]
    assert get_marker_content(comments, "breakdown") is None


def test_write_marker_comment_format(mock_linear):
    issue_id = "issue-1"
    mock_linear.seed_issue(id=issue_id, title="Test", state="backlog")
    comment_id = write_marker_comment(issue_id, "triage", "Classified as maintenance")
    assert comment_id.startswith("comment-")
    marker_comments = get_all_marker_contents(
        mock_linear.graphql("query { comments { nodes { body } } }", {"id": issue_id})["comments"]["nodes"],
        "triage",
    )
    assert marker_comments == ["<!-- triage-result -->\n\nClassified as maintenance"]
