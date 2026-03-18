from unittest.mock import MagicMock

import stage1_triage
import stage2_breakdown
import stage3_research
import run_pipeline


def _make_response(text: str):
    response = MagicMock()
    block = MagicMock()
    block.text = text
    response.content = [block]
    return response


def test_triage_happy_path(mock_linear, monkeypatch):
    monkeypatch.setattr(stage1_triage, "graphql", mock_linear.graphql)
    mock_linear.seed_issue(
        id="parent-1",
        title="Low fluid reservoir",
        state="backlog",
        description="Need classification",
    )
    monkeypatch.setattr(
        stage1_triage,
        "call_claude",
        lambda **_: _make_response(
            '{"task_type":"maintenance","complexity":"low","priority":3,"blocked":false,"block_reason":"","confidence":0.9,"notes":"ok"}'
        ),
    )
    processed = stage1_triage.run(max_iterations=1)
    assert processed == 1
    mock_linear.assert_issue_state("parent-1", "triaged")
    mock_linear.assert_comment_contains("parent-1", "<!-- triage-result -->")


def test_triage_blocked(mock_linear, monkeypatch):
    monkeypatch.setattr(stage1_triage, "graphql", mock_linear.graphql)
    mock_linear.seed_issue(
        id="parent-2",
        title="Fix the thing",
        state="backlog",
        description="Ambiguous request",
    )
    monkeypatch.setattr(
        stage1_triage,
        "call_claude",
        lambda **_: _make_response(
            '{"task_type":"maintenance","complexity":"low","priority":3,"blocked":true,"block_reason":"Need specific component","confidence":0.8,"notes":"blocked"}'
        ),
    )
    processed = stage1_triage.run(max_iterations=1)
    assert processed == 1
    mock_linear.assert_issue_state("parent-2", "blocked")
    mock_linear.assert_comment_contains("parent-2", "<!-- blocked -->")


def test_breakdown_creates_ordered_subtasks(mock_linear, monkeypatch):
    monkeypatch.setattr(stage2_breakdown, "graphql", mock_linear.graphql)
    mock_linear.seed_issue(
        id="parent-3",
        title="Address reservoir issue",
        state="triaged",
        description="create plan",
    )
    monkeypatch.setattr(
        stage2_breakdown,
        "call_claude",
        lambda **_: _make_response(
            """
            {"tasks":[
              {"title":"Identify fluid","type":"agent","description":"Analyze context"},
              {"title":"Buy fluid","type":"human","description":"Purchase correct fluid"},
              {"title":"Confirm fill steps","type":"agent","description":"Provide final checklist"}
            ]}
            """
        ),
    )
    processed = stage2_breakdown.run(max_iterations=1)
    assert processed == 1
    issue = mock_linear.graphql("query issue($id: String!) { issue(id: $id) { children { nodes { sortOrder labels { nodes { name } } } } } }", {"id": "parent-3"})["issue"]
    children = issue["children"]["nodes"]
    assert [child["sortOrder"] for child in children] == [1.0, 2.0, 3.0]
    assert children[0]["labels"]["nodes"][0]["name"] == "agent-task"
    assert children[1]["labels"]["nodes"][0]["name"] == "human-task"
    mock_linear.assert_issue_state("parent-3", "planning_complete")


def test_research_completes_and_advances_sibling(mock_linear, monkeypatch):
    monkeypatch.setattr(stage3_research, "graphql", mock_linear.graphql)
    mock_linear.seed_issue(
        id="parent-4",
        title="Parent research flow",
        state="in_progress",
        description="Parent task",
        children=[
            {
                "id": "child-1",
                "title": "Research first",
                "state": "in_progress",
                "labels": ["agent-task"],
                "sortOrder": 1.0,
            },
            {
                "id": "child-2",
                "title": "Research second",
                "state": "todo",
                "labels": ["agent-task"],
                "sortOrder": 2.0,
            },
        ],
    )
    monkeypatch.setattr(
        stage3_research,
        "call_claude",
        lambda **_: _make_response(
            '{"result":"completed","summary":"ok","details":"first research complete","confidence":0.9}'
        ),
    )
    processed = stage3_research.run(max_iterations=1)
    assert processed == 1
    mock_linear.assert_issue_state("child-1", "done")
    mock_linear.assert_issue_state("child-2", "in_progress")
    mock_linear.assert_comment_contains("child-1", "<!-- research-result -->")


def test_research_rollup_when_all_children_terminal(mock_linear, monkeypatch):
    monkeypatch.setattr(stage3_research, "graphql", mock_linear.graphql)
    mock_linear.seed_issue(
        id="parent-5",
        title="Parent rollup flow",
        state="in_progress",
        description="Parent task",
        children=[
            {
                "id": "child-3",
                "title": "Final agent task",
                "state": "in_progress",
                "labels": ["agent-task"],
                "sortOrder": 1.0,
            },
            {
                "id": "child-4",
                "title": "Human follow-through",
                "state": "done",
                "labels": ["human-task"],
                "sortOrder": 2.0,
            },
        ],
    )
    monkeypatch.setattr(
        stage3_research,
        "call_claude",
        lambda **_: _make_response(
            '{"result":"completed","summary":"ok","details":"completed final research","confidence":0.95}'
        ),
    )
    processed = stage3_research.run(max_iterations=1)
    assert processed == 1
    mock_linear.assert_issue_state("child-3", "done")
    mock_linear.assert_issue_state("parent-5", "done")
    mock_linear.assert_comment_contains("parent-5", "<!-- summary -->")


def test_full_pipeline_lifecycle(mock_linear, monkeypatch):
    monkeypatch.setattr(stage1_triage, "graphql", mock_linear.graphql)
    monkeypatch.setattr(stage2_breakdown, "graphql", mock_linear.graphql)
    monkeypatch.setattr(stage3_research, "graphql", mock_linear.graphql)

    mock_linear.seed_issue(
        id="parent-6",
        title="Fix low reservoir level",
        state="backlog",
        description="Need full lifecycle processing",
    )

    monkeypatch.setattr(
        stage1_triage,
        "call_claude",
        lambda **_: _make_response(
            '{"task_type":"maintenance","complexity":"medium","priority":2,"blocked":false,"block_reason":"","confidence":0.93,"notes":"triaged"}'
        ),
    )
    monkeypatch.setattr(
        stage2_breakdown,
        "call_claude",
        lambda **_: _make_response(
            """
            {"tasks":[
              {"title":"Identify fluid type","type":"agent","description":"Determine reservoir fluid"},
              {"title":"Provide refill checklist","type":"agent","description":"List exact refill steps"}
            ]}
            """
        ),
    )

    research_responses = iter(
        [
            '{"result":"completed","summary":"identified","details":"Likely washer fluid","confidence":0.9}',
            '{"result":"completed","summary":"checklist","details":"Use washer fluid and fill to max","confidence":0.92}',
        ]
    )
    monkeypatch.setattr(
        stage3_research,
        "call_claude",
        lambda **_: _make_response(next(research_responses)),
    )

    run_pipeline.run_cycle(stage_iterations=1)
    run_pipeline.run_cycle(stage_iterations=1)

    mock_linear.assert_issue_state("parent-6", "done")
    mock_linear.assert_comment_contains("parent-6", "<!-- summary -->")


def test_blocked_reentry_backlog_to_blocked_to_triaged(mock_linear, monkeypatch):
    monkeypatch.setattr(stage1_triage, "graphql", mock_linear.graphql)
    mock_linear.seed_issue(
        id="parent-7",
        title="Fix the thing",
        state="backlog",
        description="Ambiguous initial request",
    )

    triage_responses = iter(
        [
            '{"task_type":"maintenance","complexity":"low","priority":3,"blocked":true,"block_reason":"Need specific component","confidence":0.7,"notes":"blocked"}',
            '{"task_type":"maintenance","complexity":"low","priority":3,"blocked":false,"block_reason":"","confidence":0.9,"notes":"clear now"}',
        ]
    )
    monkeypatch.setattr(stage1_triage, "call_claude", lambda **_: _make_response(next(triage_responses)))

    processed_first = stage1_triage.run(max_iterations=1)
    assert processed_first == 1
    mock_linear.assert_issue_state("parent-7", "blocked")

    mock_linear._comments["parent-7"].append(
        {
            "id": "human-reply-1",
            "body": "It is the garage door opener rail assembly.",
            "createdAt": "2026-03-18T19:00:00Z",
            "user": {"id": "human", "name": "Greg", "isMe": False},
        }
    )

    processed_second = stage1_triage.run(max_iterations=1)
    assert processed_second == 1
    mock_linear.assert_issue_state("parent-7", "triaged")
    mock_linear.assert_comment_contains("parent-7", "<!-- blocked -->")
    mock_linear.assert_comment_contains("parent-7", "<!-- triage-result -->")
