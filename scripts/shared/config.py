import os
from functools import lru_cache


def _env(key: str, default: str = None) -> str:
    """Lazy env read — only evaluated when accessed, not at import time."""
    val = os.environ.get(key, default)
    if val is None:
        raise EnvironmentError(f"Missing required env var: {key}")
    return val


@lru_cache()
def get_states() -> dict[str, str]:
    return {
        "backlog": _env("STATE_BACKLOG"),
        "triaged": _env("STATE_TRIAGED"),
        "planning_complete": _env("STATE_PLANNING_COMPLETE"),
        "in_progress": _env("STATE_IN_PROGRESS"),
        "in_review": _env("STATE_IN_REVIEW"),
        "done": _env("STATE_DONE"),
        "blocked": _env("STATE_BLOCKED"),
        "cancelled": _env("STATE_CANCELLED"),
        "todo": _env("STATE_TODO"),
    }


@lru_cache()
def get_labels() -> dict[str, str]:
    return {
        "agent_task": _env("LABEL_AGENT_TASK"),
        "human_task": _env("LABEL_HUMAN_TASK"),
        "clarification": _env("LABEL_CLARIFICATION"),
        "scope_change": _env("LABEL_SCOPE_CHANGE"),
        "error": _env("LABEL_ERROR"),
        "type_research": _env("LABEL_TYPE_RESEARCH"),
        "type_purchase": _env("LABEL_TYPE_PURCHASE"),
        "type_maintenance": _env("LABEL_TYPE_MAINTENANCE"),
        "type_admin": _env("LABEL_TYPE_ADMIN"),
        "type_software": _env("LABEL_TYPE_SOFTWARE"),
    }


LINEAR_API_URL = "https://api.linear.app/graphql"

def get_linear_api_key() -> str:
    return _env("LINEAR_API_KEY")

def get_linear_team_id() -> str:
    return _env("LINEAR_TEAM_ID")

def get_linear_workspace_slug() -> str:
    return _env("LINEAR_WORKSPACE_SLUG", "stupidclaw")

def get_anthropic_api_key() -> str:
    return _env("ANTHROPIC_API_KEY")

def get_claude_model() -> str:
    return _env("CLAUDE_MODEL", "claude-sonnet-4-20250514")

def get_daily_budget_cap() -> float:
    return float(_env("DAILY_BUDGET_CAP", "5.00"))

def get_per_task_token_cap() -> int:
    return int(_env("PER_TASK_TOKEN_CAP", "100000"))

def get_cost_tracker_path() -> str:
    return _env("COST_TRACKER_PATH", "/var/data/stupidclaw/cost_tracker.json")

def get_lockfile_path() -> str:
    return _env("LOCKFILE_PATH", "/tmp/stupidclaw.lock")

def get_stale_blocked_hours() -> int:
    return int(_env("STALE_BLOCKED_HOURS", "48"))
