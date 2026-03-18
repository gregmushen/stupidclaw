import pytest

from stage1_triage import parse_triage_response
from stage2_breakdown import parse_breakdown_response
from stage3_research import parse_research_response


def test_triage_valid_json():
    result = parse_triage_response(
        """
        {"task_type":"maintenance","complexity":"medium","priority":2,"blocked":false,"block_reason":"","confidence":0.8,"notes":"ok"}
        """
    )
    assert result["task_type"] == "maintenance"
    assert result["blocked"] is False


def test_triage_fenced_json():
    result = parse_triage_response(
        """
        ```json
        {"task_type":"software","complexity":"high","priority":1,"blocked":true,"block_reason":"missing logs","confidence":0.72,"notes":"need logs"}
        ```
        """
    )
    assert result["task_type"] == "software"
    assert result["blocked"] is True


def test_triage_missing_fields_raises():
    with pytest.raises(ValueError, match="Missing triage fields"):
        parse_triage_response('{"task_type":"maintenance"}')


def test_triage_malformed_raises():
    with pytest.raises(ValueError, match="Malformed triage JSON"):
        parse_triage_response("{bad json")


def test_triage_confidence_coercion_and_case_normalization():
    result = parse_triage_response(
        """
        {"task_type":"Maintenance","complexity":"LOW","priority":"3","blocked":false,"block_reason":"x","confidence":"2.7","notes":"n"}
        """
    )
    assert result["task_type"] == "maintenance"
    assert result["complexity"] == "low"
    assert result["priority"] == 3
    assert result["confidence"] == 1.0
    assert result["block_reason"] == ""


def test_breakdown_three_task_response():
    tasks = parse_breakdown_response(
        """
        {"tasks":[
          {"title":"Identify issue","type":"agent","description":"Analyze context"},
          {"title":"Buy part","type":"human","description":"Purchase required part"},
          {"title":"Validate","type":"agent","description":"Confirm resolution"}
        ]}
        """
    )
    assert len(tasks) == 3
    assert tasks[1]["type"] == "human"


def test_breakdown_single_task():
    tasks = parse_breakdown_response(
        '{"tasks":[{"title":"Answer question","type":"agent","description":"Provide direct answer"}]}'
    )
    assert len(tasks) == 1
    assert tasks[0]["title"] == "Answer question"


def test_breakdown_mixed_types_case_normalization():
    tasks = parse_breakdown_response(
        """
        {"tasks":[
          {"title":"Research","type":"AGENT","description":"read docs"},
          {"title":"Approve","type":"Human","description":"provide approval"}
        ]}
        """
    )
    assert tasks[0]["type"] == "agent"
    assert tasks[1]["type"] == "human"


def test_breakdown_missing_type_raises():
    with pytest.raises(ValueError, match="missing task field: type"):
        parse_breakdown_response('{"tasks":[{"title":"X","description":"Y"}]}')


def test_breakdown_malformed_raises():
    with pytest.raises(ValueError, match="Malformed breakdown JSON"):
        parse_breakdown_response("```json\n{oops}\n```")


def test_research_normal_completion():
    result = parse_research_response(
        '{"result":"completed","summary":"done","details":"final answer","confidence":0.91}'
    )
    assert result["result"] == "completed"
    assert result["details"] == "final answer"


def test_research_blocked():
    result = parse_research_response(
        '{"result":"blocked","summary":"missing info","details":"need serial number","confidence":0.7}'
    )
    assert result["result"] == "blocked"


def test_research_needs_human():
    result = parse_research_response(
        '{"result":"needs_human","summary":"decision needed","details":"pick option A or B","confidence":0.6}'
    )
    assert result["result"] == "needs_human"


def test_research_scope_change():
    result = parse_research_response(
        '{"result":"scope_change","summary":"request changed","details":"now asks for replacement plan","confidence":0.55}'
    )
    assert result["result"] == "scope_change"


def test_research_multiple_flags_priority():
    result = parse_research_response(
        '{"blocked":true,"needs_human":true,"scope_change":true,"summary":"x","details":"y","confidence":0.4}'
    )
    assert result["result"] == "scope_change"
