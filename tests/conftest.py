from unittest.mock import MagicMock

import pytest

from shared.config import get_labels, get_states
from tests.mock_linear import MockLinearClient


@pytest.fixture(autouse=True)
def clear_config_cache():
    get_states.cache_clear()
    get_labels.cache_clear()
    yield
    get_states.cache_clear()
    get_labels.cache_clear()


@pytest.fixture(autouse=True)
def minimal_env(monkeypatch):
    for name in [
        "BACKLOG",
        "TRIAGED",
        "PLANNING_COMPLETE",
        "IN_PROGRESS",
        "IN_REVIEW",
        "DONE",
        "BLOCKED",
        "CANCELLED",
        "TODO",
    ]:
        monkeypatch.setenv(f"STATE_{name}", f"state-{name.lower()}")

    for name in [
        "AGENT_TASK",
        "HUMAN_TASK",
        "CLARIFICATION",
        "SCOPE_CHANGE",
        "ERROR",
        "TYPE_RESEARCH",
        "TYPE_PURCHASE",
        "TYPE_MAINTENANCE",
        "TYPE_ADMIN",
        "TYPE_SOFTWARE",
    ]:
        monkeypatch.setenv(f"LABEL_{name}", f"label-{name.lower()}")

    monkeypatch.setenv("LINEAR_API_KEY", "lin_api_test")
    monkeypatch.setenv("LINEAR_TEAM_ID", "team-stu-test")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")


@pytest.fixture
def mock_linear(monkeypatch):
    client = MockLinearClient()
    monkeypatch.setattr("shared.linear_client.graphql", client.graphql)
    monkeypatch.setattr("shared.comment_markers.graphql", client.graphql)
    return client


@pytest.fixture
def mock_claude(monkeypatch):
    def make_response(text: str, input_tokens: int = 100, output_tokens: int = 50):
        message = MagicMock()
        block = MagicMock()
        block.text = text
        message.content = [block]
        message.usage = MagicMock(input_tokens=input_tokens, output_tokens=output_tokens)
        return message

    queued: list = []
    default = make_response("mock-response")

    def set_response(text: str):
        nonlocal default
        default = make_response(text)

    def set_responses(texts: list[str]):
        queued.clear()
        queued.extend(make_response(text) for text in texts)

    def call_side_effect(*_args, **_kwargs):
        if queued:
            return queued.pop(0)
        return default

    stub = MagicMock()
    stub.set_response = set_response
    stub.set_responses = set_responses
    monkeypatch.setattr("shared.claude_client.call_claude", call_side_effect)
    monkeypatch.setattr("shared.claude_client.call_claude_with_tools", call_side_effect)
    return stub
