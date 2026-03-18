from stage3_research import (
    all_children_terminal,
    check_predecessors,
    determine_parent_state,
    find_next_agent_sibling,
)


def _child(id_, order, state, labels):
    return {
        "id": id_,
        "sortOrder": float(order),
        "state": {"name": state},
        "labels": {"nodes": [{"name": label} for label in labels]},
    }


def test_check_predecessors_first_task_true():
    children = [_child("a", 1, "in_progress", ["agent-task"])]
    assert check_predecessors(children, "a") is True


def test_check_predecessors_previous_done_true():
    children = [
        _child("a", 1, "done", ["agent-task"]),
        _child("b", 2, "in_progress", ["agent-task"]),
    ]
    assert check_predecessors(children, "b") is True


def test_check_predecessors_previous_blocked_true():
    children = [
        _child("a", 1, "blocked", ["agent-task"]),
        _child("b", 2, "in_progress", ["agent-task"]),
    ]
    assert check_predecessors(children, "b") is True


def test_check_predecessors_previous_todo_false():
    children = [
        _child("a", 1, "todo", ["agent-task"]),
        _child("b", 2, "in_progress", ["agent-task"]),
    ]
    assert check_predecessors(children, "b") is False


def test_check_predecessors_missing_current_false():
    children = [_child("a", 1, "done", ["agent-task"])]
    assert check_predecessors(children, "missing") is False


def test_find_next_agent_sibling_simple():
    children = [
        _child("a", 1, "done", ["agent-task"]),
        _child("b", 2, "todo", ["agent-task"]),
    ]
    assert find_next_agent_sibling(children, "a")["id"] == "b"


def test_find_next_agent_sibling_skips_human():
    children = [
        _child("a", 1, "done", ["agent-task"]),
        _child("b", 2, "todo", ["human-task"]),
        _child("c", 3, "backlog", ["agent-task"]),
    ]
    assert find_next_agent_sibling(children, "a")["id"] == "c"


def test_find_next_agent_sibling_skips_terminal_agent():
    children = [
        _child("a", 1, "done", ["agent-task"]),
        _child("b", 2, "done", ["agent-task"]),
        _child("c", 3, "todo", ["agent-task"]),
    ]
    assert find_next_agent_sibling(children, "a")["id"] == "c"


def test_find_next_agent_sibling_none_when_absent():
    children = [
        _child("a", 1, "done", ["agent-task"]),
        _child("b", 2, "done", ["agent-task"]),
    ]
    assert find_next_agent_sibling(children, "a") is None


def test_find_next_agent_sibling_missing_current_none():
    children = [_child("a", 1, "todo", ["agent-task"])]
    assert find_next_agent_sibling(children, "missing") is None


def test_all_children_terminal_true():
    children = [_child("a", 1, "done", []), _child("b", 2, "blocked", [])]
    assert all_children_terminal(children) is True


def test_all_children_terminal_false():
    children = [_child("a", 1, "done", []), _child("b", 2, "in_progress", [])]
    assert all_children_terminal(children) is False


def test_all_children_terminal_empty_true():
    assert all_children_terminal([]) is True


def test_determine_parent_state_done():
    children = [_child("a", 1, "done", []), _child("b", 2, "cancelled", [])]
    assert determine_parent_state(children) == "done"


def test_determine_parent_state_blocked():
    children = [_child("a", 1, "done", []), _child("b", 2, "blocked", [])]
    assert determine_parent_state(children) == "blocked"
