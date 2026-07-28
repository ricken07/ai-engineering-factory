from pathlib import Path

from aief.intake import TaskRegistry, create_request, normalize_task, resolve_intent
from aief.project import initialize
from aief.service import RuntimeService


def test_explicit_and_natural_requests_share_the_same_workflow():
    command = resolve_intent(create_request("/fix EGW-327"))
    natural = resolve_intent(create_request("Corrige le bug EGW-327"))
    assert command["workflow"] == natural["workflow"] == "fix-bug"
    assert command["taskReference"] == natural["taskReference"] == "EGW-327"
    assert command["source"] == "explicit-command"


def test_gitlab_issue_url_and_qualified_reference_are_preserved():
    url="https://gitlab.com/Gad-Digital-IT/products/emi-ai/app/-/issues/42"
    url_resolution=resolve_intent(create_request(f"/implement {url}"))
    url_task=normalize_task(create_request(f"/implement {url}"),url_resolution)
    assert url_resolution["taskReference"] == url
    assert url_task["source"] == {"type":"issue","reference":url,"provider":"gitlab"}

    qualified="Gad-Digital-IT/products/emi-ai/app#42"
    qualified_task=normalize_task(create_request(f"Corrige {qualified}"),resolve_intent(create_request(f"Corrige {qualified}")))
    assert qualified_task["source"]["reference"] == qualified
    assert qualified_task["source"]["provider"] == "gitlab"


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


def test_adapter_intent_prevents_loss_of_native_implement_command(tmp_path):
    project = tmp_path / "project"
    initialize(Path("templates/project"), project)
    service = RuntimeService(project, Path("."))

    result = service.intake(
        "Feature 1.1 — Fixer les trois contrats cassés",
        "claude-code",
        intent="implement",
        expected_workflow="implement-task",
    )

    assert result["request"]["text"] == "Feature 1.1 — Fixer les trois contrats cassés"
    assert result["intent"]["intent"] == "implement"
    assert result["intent"]["workflow"] == "implement-task"
    assert result["intent"]["mutating"] is True


def test_adapter_expected_workflow_fails_closed(tmp_path):
    project = tmp_path / "project"
    initialize(Path("templates/project"), project)
    service = RuntimeService(project, Path("."))

    import pytest
    with pytest.raises(RuntimeError, match="expected workflow fix-bug"):
        service.intake("Feature 1.1", intent="implement", expected_workflow="fix-bug")
