import json
import os
from datetime import date

from shared.config import get_cost_tracker_path, get_daily_budget_cap, get_per_task_token_cap

INPUT_COST_PER_TOKEN = 3.0 / 1_000_000
OUTPUT_COST_PER_TOKEN = 15.0 / 1_000_000


def _today() -> str:
    return str(date.today())


def _empty() -> dict:
    return {
        "date": _today(),
        "daily_tokens": {"input": 0, "output": 0},
        "tasks": {},
    }


def _load() -> dict:
    path = get_cost_tracker_path()
    if not os.path.exists(path):
        return _empty()
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _save(data: dict) -> None:
    path = get_cost_tracker_path()
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)


def _reset_if_new_day(data: dict) -> tuple[dict, bool]:
    if data.get("date") == _today():
        return data, False
    data["date"] = _today()
    data["daily_tokens"] = {"input": 0, "output": 0}
    data.setdefault("tasks", {})
    return data, True


def _estimate_cost(input_tokens: int, output_tokens: int) -> float:
    return (input_tokens * INPUT_COST_PER_TOKEN) + (output_tokens * OUTPUT_COST_PER_TOKEN)


def check_daily_budget() -> tuple[bool, float]:
    data, changed = _reset_if_new_day(_load())
    if changed:
        _save(data)
    spent = _estimate_cost(data["daily_tokens"]["input"], data["daily_tokens"]["output"])
    cap = get_daily_budget_cap()
    remaining = cap - spent
    return spent < cap, remaining


def check_task_budget(parent_issue_id: str) -> tuple[bool, int]:
    data = _load()
    usage = data.get("tasks", {}).get(parent_issue_id, {"input": 0, "output": 0})
    total = int(usage["input"]) + int(usage["output"])
    return total < get_per_task_token_cap(), total


def record_usage(parent_issue_id: str, input_tokens: int, output_tokens: int) -> None:
    data, _ = _reset_if_new_day(_load())
    data["daily_tokens"]["input"] += int(input_tokens)
    data["daily_tokens"]["output"] += int(output_tokens)
    data.setdefault("tasks", {})
    data["tasks"].setdefault(parent_issue_id, {"input": 0, "output": 0})
    data["tasks"][parent_issue_id]["input"] += int(input_tokens)
    data["tasks"][parent_issue_id]["output"] += int(output_tokens)
    _save(data)
