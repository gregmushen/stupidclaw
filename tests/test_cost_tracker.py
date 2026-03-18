import json

import pytest

from shared.cost_tracker import check_daily_budget, check_task_budget, record_usage


@pytest.fixture
def tracker_file(tmp_path, monkeypatch):
    path = tmp_path / "cost_tracker.json"
    monkeypatch.setenv("COST_TRACKER_PATH", str(path))
    return path


def test_daily_reset(tracker_file):
    tracker_file.write_text(
        json.dumps(
            {
                "date": "2000-01-01",
                "daily_tokens": {"input": 999999, "output": 999999},
                "tasks": {"legacy": {"input": 2, "output": 3}},
            }
        ),
        encoding="utf-8",
    )
    within, remaining = check_daily_budget()
    assert within is True
    assert remaining == pytest.approx(5.0, abs=0.01)


def test_budget_pass(tracker_file):
    record_usage("task-1", 100, 100)
    within, remaining = check_daily_budget()
    assert within is True
    assert remaining > 4.99


def test_budget_fail(tracker_file):
    record_usage("task-1", 0, 400_000)
    within, remaining = check_daily_budget()
    assert within is False
    assert remaining < 0


def test_per_task_accumulation(tracker_file):
    record_usage("task-1", 300, 200)
    record_usage("task-1", 700, 800)
    within, used = check_task_budget("task-1")
    assert within is True
    assert used == 2000


def test_new_day_auto_reset(tracker_file):
    tracker_file.write_text(
        json.dumps(
            {
                "date": "2000-01-01",
                "daily_tokens": {"input": 1, "output": 1},
                "tasks": {"task-1": {"input": 10, "output": 20}},
            }
        ),
        encoding="utf-8",
    )
    check_daily_budget()
    within, used = check_task_budget("task-1")
    assert within is True
    assert used == 30
