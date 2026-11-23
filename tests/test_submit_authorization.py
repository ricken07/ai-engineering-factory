from pathlib import Path

import pytest

from aief.intake import TaskRegistry
from test_dynamic_policy import output, runtime


def at_submission(tmp_path: Path, autonomy: str):
    """Execution of a submitting workflow whose submission phase is about to complete."""
    service, execution = runtime(tmp_path)
    identifier = execution.data["metadata"]["id"]
    task = TaskRegistry(service.project_root).load(execution.data["task"])
    task["autonomy"] = {"requested": autonomy}
    TaskRegistry(service.project_root).save(task)
    service.prepare_phase(identifier)
    service.complete_phase(identifier, output("Impact", {"risk": "medium", "repositories": ["main"], "changeTypes": ["source-code"]}))
    current = service.execution(identifier)
    for phase in current.data["phases"]:
        if phase["skill"] == "submit-change":
            break
        phase["status"] = "completed"
    current.data["status"] = "running"
    current.save()
    service.prepare_phase(identifier)
    assert service.execution(identifier).next_phase()["skill"] == "submit-change"
    return service, identifier


def test_a_submission_is_refused_when_the_governed_plan_denies_submit_change(tmp_path: Path):
    service, identifier = at_submission(tmp_path, "L2")
    plan = service.execution(identifier).data["governedExecutionPlan"]
    assert "submit-change" in (service.execution(identifier).root / plan).read_text()
    with pytest.raises(PermissionError, match="denied by governed execution plan: submit-change"):
        service.complete_phase(identifier, output("Submitted", {}))
    current = service.execution(identifier)
    assert current.next_phase()["skill"] == "submit-change" and current.data["status"] != "completed"


def test_a_submission_is_checked_against_its_evidence_when_the_plan_allows_submit_change(tmp_path: Path):
    service, identifier = at_submission(tmp_path, "L3")
    with pytest.raises(ValueError, match="submission evidence is incomplete"):
        service.complete_phase(identifier, output("Submitted", {}))
