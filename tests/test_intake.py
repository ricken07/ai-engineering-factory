from pathlib import Path

from aief.intake import TaskRegistry, create_request, normalize_task, resolve_intent
from aief.project import initialize


def test_explicit_and_natural_requests_share_the_same_workflow():
    command = resolve_intent(create_request("/fix EGW-327"))
    natural = resolve_intent(create_request("Corrige le bug EGW-327"))
    assert command["workflow"] == natural["workflow"] == "fix-bug"
    assert command["taskReference"] == natural["taskReference"] == "EGW-327"
    assert command["source"] == "explicit-command"


def test_ambiguous_request_falls_back_to_non_mutating_analysis():
    resolution = resolve_intent(create_request("Regarde PaymentOrchestrator"))
    assert resolution["intent"] == "analyze"
    assert resolution["confidence"] == "ambiguous"
    assert resolution["mutating"] is False


def test_local_task_is_normalized_and_persisted(tmp_path: Path):
    project = tmp_path / "project"
    initialize(Path("templates/project"), project)
    request = create_request("Refactore PaymentOrchestrator sans changer son comportement")
    task = normalize_task(request, resolve_intent(request))
    path = TaskRegistry(project).save(task)
    assert task["source"]["type"] == "local"
    assert task["workflow"] == "refactor-code"
    assert TaskRegistry(project).load(task["metadata"]["id"])["objective"] == task["objective"]
    assert path.name == "task.yaml"

