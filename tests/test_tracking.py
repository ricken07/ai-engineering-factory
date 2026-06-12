import pytest

from aief.tracking import evaluate_tracking, promotion_plan


def task(nature="change"):
    return {"metadata":{"id":"local-1"},"source":{"type":"local"},"nature":nature,"classification":{}}


def test_tracking_is_required_for_dynamic_high_risk_or_cross_repo_impact():
    assert evaluate_tracking(task(), {"risk":"high","repositories":["api"]}).level == "required"
    decision = evaluate_tracking(task(), {"risk":"medium","repositories":["api","app"]})
    assert decision.level == "required"
    assert decision.required_before == "implementation"


def test_tracking_avoids_bureaucracy_for_information_and_recommends_changes():
    assert evaluate_tracking(task("informational")).level == "optional"
    assert evaluate_tracking(task(), {"changeTypes":["source-code"]}).level == "recommended"


def test_promotion_plan_requires_duplicate_search_and_human_gate(monkeypatch):
    monkeypatch.setattr("aief.tracking.resolve_capability", lambda factory, project, capability, operation, environment: {"provider":"jira","operation":operation})
    plan = promotion_plan(None, {}, task())
    assert plan["requiredOperations"] == ["search-task", "create-task", "link-task"]
    assert plan["duplicateSearchRequired"] is True
    assert plan["approved"] is False

    external = task(); external["source"] = {"type":"issue","reference":"EGW-1"}
    with pytest.raises(ValueError, match="only a local Task"):
        promotion_plan(None, {}, external)
