from datetime import datetime, timedelta, timezone

from stage1_triage import extract_human_answer, is_stale


def test_extract_human_answer_single_reply():
    comments = [
        {"body": "<!-- blocked -->\nNeed more detail", "user": {"isMe": True}},
        {"body": "It is the garage door opener", "user": {"isMe": False}},
    ]
    assert extract_human_answer(comments) == "It is the garage door opener"


def test_extract_human_answer_multiple_replies_takes_latest():
    comments = [
        {"body": "<!-- blocked -->\nNeed more detail", "user": {"isMe": True}},
        {"body": "first answer", "user": {"isMe": False}},
        {"body": "second answer", "user": {"isMe": False}},
    ]
    assert extract_human_answer(comments) == "second answer"


def test_extract_human_answer_no_reply_returns_none():
    comments = [
        {"body": "<!-- blocked -->\nNeed more detail", "user": {"isMe": True}},
    ]
    assert extract_human_answer(comments) is None


def test_extract_human_answer_skips_agent_comments():
    comments = [
        {"body": "<!-- blocked -->\nNeed more detail", "user": {"isMe": True}},
        {"body": "internal note", "user": {"isMe": True}},
    ]
    assert extract_human_answer(comments) is None


def test_is_stale_at_threshold():
    ts = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat().replace("+00:00", "Z")
    assert is_stale(ts, threshold_hours=48) is True


def test_is_stale_past_threshold():
    ts = (datetime.now(timezone.utc) - timedelta(hours=49)).isoformat().replace("+00:00", "Z")
    assert is_stale(ts, threshold_hours=48) is True


def test_is_stale_not_stale():
    ts = (datetime.now(timezone.utc) - timedelta(hours=12)).isoformat().replace("+00:00", "Z")
    assert is_stale(ts, threshold_hours=48) is False
