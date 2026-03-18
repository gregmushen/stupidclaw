from shared.claude_client import build_user_message
from stage1_triage import build_triage_input
from stage2_breakdown import format_breakdown_comment
from stage3_research import build_research_input


def test_build_triage_input_includes_title_and_description():
    issue = {"title": "Low reservoir", "description": "Below min line", "attachments": {"nodes": []}}
    text = build_triage_input(issue)
    assert "Title: Low reservoir" in text
    assert "Description:" in text


def test_build_triage_input_includes_attachments():
    issue = {
        "title": "Issue",
        "description": "Desc",
        "attachments": {"nodes": [{"title": "photo.jpg", "url": "https://x"}]},
    }
    text = build_triage_input(issue)
    assert "- photo.jpg" in text


def test_build_triage_input_handles_no_attachments():
    issue = {"title": "Issue", "description": "Desc", "attachments": {"nodes": []}}
    text = build_triage_input(issue)
    assert "- none" in text


def test_build_triage_input_includes_human_answer():
    issue = {"title": "Issue", "description": "Desc", "attachments": {"nodes": []}}
    text = build_triage_input(issue, "It is the garage opener")
    assert "Clarification:" in text
    assert "garage opener" in text


def test_build_user_message_text_only():
    message = build_user_message("hello")
    assert message["role"] == "user"
    assert message["content"] == [{"type": "text", "text": "hello"}]


def test_build_user_message_single_image():
    message = build_user_message("hello", [{"media_type": "image/jpeg", "data": "abc"}])
    assert message["content"][0]["type"] == "image"
    assert message["content"][1]["type"] == "text"


def test_build_user_message_multiple_images():
    message = build_user_message(
        "hello",
        [
            {"media_type": "image/jpeg", "data": "aaa"},
            {"media_type": "image/png", "data": "bbb"},
        ],
    )
    assert len(message["content"]) == 3
    assert message["content"][0]["source"]["media_type"] == "image/jpeg"
    assert message["content"][1]["source"]["media_type"] == "image/png"


def test_build_user_message_preserves_text():
    message = build_user_message("some text", [])
    assert message["content"][-1]["text"] == "some text"


def test_format_breakdown_comment_three_tasks():
    text = format_breakdown_comment(
        [
            {"title": "A", "type": "agent", "description": "d1"},
            {"title": "B", "type": "human", "description": "d2"},
            {"title": "C", "type": "agent", "description": "d3"},
        ]
    )
    assert "1. [agent] A - d1" in text
    assert "2. [human] B - d2" in text
    assert "3. [agent] C - d3" in text


def test_format_breakdown_comment_single_task():
    text = format_breakdown_comment([{"title": "Only", "type": "agent", "description": "x"}])
    assert text.startswith("Subtasks created:")
    assert "1. [agent] Only - x" in text


def test_format_breakdown_comment_preserves_order():
    text = format_breakdown_comment(
        [
            {"title": "First", "type": "agent", "description": "x"},
            {"title": "Second", "type": "human", "description": "y"},
        ]
    )
    assert text.find("First") < text.find("Second")


def test_build_research_input_first_subtask_no_siblings():
    text = build_research_input(
        {"title": "Parent", "description": "Parent desc"},
        {"title": "Child", "description": "Child desc"},
        [],
    )
    assert "Prior sibling results:" in text
    assert "(none)" in text


def test_build_research_input_multiple_sibling_results():
    text = build_research_input(
        {"title": "Parent", "description": "Parent desc"},
        {"title": "Child", "description": "Child desc"},
        ["first result", "second result"],
    )
    assert "1. first result" in text
    assert "2. second result" in text


def test_build_research_input_with_human_context():
    text = build_research_input(
        {"title": "Parent", "description": "Parent desc"},
        {"title": "Child", "description": "Child desc"},
        [],
        human_context="User says prioritize low cost",
    )
    assert "Human context:" in text
    assert "prioritize low cost" in text


def test_build_research_input_no_parent_description():
    text = build_research_input(
        {"title": "Parent", "description": ""},
        {"title": "Child", "description": "Child desc"},
        [],
    )
    assert "Parent description:" in text
    assert "(none)" in text
