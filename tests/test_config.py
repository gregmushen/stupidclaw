import os
import pytest
from shared.config import get_states, get_labels, _env, get_daily_budget_cap, get_linear_workspace_slug


class TestEnvHelper:
    def test_env_returns_value_when_set(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR", "hello")
        assert _env("TEST_VAR") == "hello"

    def test_env_returns_default_when_not_set(self):
        assert _env("NONEXISTENT_VAR_12345", "fallback") == "fallback"

    def test_env_raises_when_missing_and_no_default(self):
        with pytest.raises(EnvironmentError, match="Missing required env var: NONEXISTENT_VAR_12345"):
            _env("NONEXISTENT_VAR_12345")


class TestGetStates:
    def setup_method(self):
        # CRITICAL: Clear the cache before each test so env changes take effect
        get_states.cache_clear()
        get_labels.cache_clear()

    def test_get_states_returns_correct_dict(self, monkeypatch):
        # Set all 9 required state vars
        states = {
            "STATE_BACKLOG": "uuid-backlog",
            "STATE_TRIAGED": "uuid-triaged",
            "STATE_PLANNING_COMPLETE": "uuid-planning",
            "STATE_IN_PROGRESS": "uuid-progress",
            "STATE_IN_REVIEW": "uuid-review",
            "STATE_DONE": "uuid-done",
            "STATE_BLOCKED": "uuid-blocked",
            "STATE_CANCELLED": "uuid-cancelled",
            "STATE_TODO": "uuid-todo",
        }
        for k, v in states.items():
            monkeypatch.setenv(k, v)

        result = get_states()
        assert result["backlog"] == "uuid-backlog"
        assert result["done"] == "uuid-done"
        assert len(result) == 9

    def test_get_states_raises_on_missing_var(self, monkeypatch):
        # Remove one required var to validate missing env behavior.
        monkeypatch.delenv("STATE_BACKLOG", raising=False)
        get_states.cache_clear()
        with pytest.raises(EnvironmentError, match="STATE_BACKLOG"):
            get_states()

    def test_cache_clear_allows_reread(self, monkeypatch):
        # Set vars, call get_states, change a var, clear cache, call again
        for s in ["BACKLOG", "TRIAGED", "PLANNING_COMPLETE", "IN_PROGRESS",
                   "IN_REVIEW", "DONE", "BLOCKED", "CANCELLED", "TODO"]:
            monkeypatch.setenv(f"STATE_{s}", f"uuid-{s.lower()}")

        result1 = get_states()
        assert result1["backlog"] == "uuid-backlog"

        monkeypatch.setenv("STATE_BACKLOG", "uuid-changed")
        get_states.cache_clear()

        result2 = get_states()
        assert result2["backlog"] == "uuid-changed"


class TestWorkspaceSlug:
    def test_workspace_slug_defaults(self, monkeypatch):
        monkeypatch.delenv("LINEAR_WORKSPACE_SLUG", raising=False)
        assert get_linear_workspace_slug() == "stupidclaw"

    def test_workspace_slug_from_env(self, monkeypatch):
        monkeypatch.setenv("LINEAR_WORKSPACE_SLUG", "acme")
        assert get_linear_workspace_slug() == "acme"
