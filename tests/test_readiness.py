from pathlib import Path

import pytest
import yaml

from aief.intake import TaskRegistry
from aief.project import initialize, load_project
from aief.readiness import build_backlog, order_tasks
from aief.service import RuntimeService


def _project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    initialize(Path("templates/project"), project)
    return project


def _task(project: Path, identifier: str, **fields) -> None:
    TaskRegistry(project).save({
        "apiVersion": "aief.dev/v1alpha1", "kind": "Task",
        "metadata": {"id": identifier}, "source": {"type": "local"}, "nature": "change",
        "intent": {"type": "implement", "confidence": "high"},
        "objective": {"summary": f"Objective of {identifier}"},
        "workflow": "implement-task", **fields,
    })


def _execution(project: Path, identifier: str, task: str, status: str) -> None:
    root = project / ".ai" / "runtime" / "executions" / identifier
    root.mkdir(parents=True, exist_ok=True)
    (root / "execution.yaml").write_text(yaml.safe_dump({
        "apiVersion": "aief.dev/v1alpha1", "kind": "Execution",
        "metadata": {"id": identifier}, "project": "local-project", "task": task,
        "workflow": {"id": "implement-task", "version": "1.0.0"},
        "status": status, "phases": [], "artifacts": [],
    }, sort_keys=False), encoding="utf-8")


def _by_task(backlog: dict) -> dict[str, dict]:
    return {entry["task"]: entry for entry in backlog["tasks"]}


def test_project_without_task_yields_an_empty_backlog(tmp_path: Path):
    backlog = build_backlog(_project(tmp_path), "local-project")
    assert backlog["kind"] == "TaskBacklog"
    assert backlog["filter"] == "all"
    assert backlog["tasks"] == []


def test_dependency_declares_order_and_blocks_until_it_completes(tmp_path: Path):
    project = _project(tmp_path)
    _task(project, "task-b", dependsOn=["task-a"])
    _task(project, "task-a")

    entries = _by_task(build_backlog(project, "local-project"))
    assert entries["task-a"]["position"] < entries["task-b"]["position"]
    assert entries["task-a"]["readiness"] == "ready"
    assert entries["task-b"]["readiness"] == "blocked"
    assert entries["task-b"]["blockedBy"] == ["task-a"]

    _execution(project, "20260101T000000Z-aaaaaaaa", "task-a", "completed")
    entries = _by_task(build_backlog(project, "local-project"))
    assert entries["task-a"]["readiness"] == "done"
    assert entries["task-b"]["readiness"] == "ready"
    assert "blockedBy" not in entries["task-b"]


def test_state_follows_the_most_recent_execution(tmp_path: Path):
    project = _project(tmp_path)
    _task(project, "task-a")
    _execution(project, "20260101T000000Z-aaaaaaaa", "task-a", "failed")
    _execution(project, "20260102T000000Z-bbbbbbbb", "task-a", "running")

    entry = _by_task(build_backlog(project, "local-project"))["task-a"]
    assert entry["state"] == "running"
    assert entry["readiness"] == "active"
    assert entry["executions"] == ["20260101T000000Z-aaaaaaaa", "20260102T000000Z-bbbbbbbb"]


def test_a_freshly_created_execution_already_owns_the_task(tmp_path: Path):
    project = _project(tmp_path)
    _task(project, "task-a")
    _execution(project, "20260101T000000Z-aaaaaaaa", "task-a", "pending")

    entry = _by_task(build_backlog(project, "local-project"))["task-a"]
    assert entry["state"] == "pending"
    assert entry["readiness"] == "active"
    assert build_backlog(project, "local-project", ready_only=True)["tasks"] == []


def test_cancelled_execution_leaves_the_task_retryable(tmp_path: Path):
    project = _project(tmp_path)
    _task(project, "task-a")
    _execution(project, "20260101T000000Z-aaaaaaaa", "task-a", "cancelled")

    assert _by_task(build_backlog(project, "local-project"))["task-a"]["readiness"] == "ready"


def test_failed_execution_leaves_the_task_retryable(tmp_path: Path):
    project = _project(tmp_path)
    _task(project, "task-a")
    _execution(project, "20260101T000000Z-aaaaaaaa", "task-a", "failed")

    entry = _by_task(build_backlog(project, "local-project"))["task-a"]
    assert entry["state"] == "failed"
    assert entry["readiness"] == "ready"


def test_unknown_dependency_blocks_instead_of_being_silently_dropped(tmp_path: Path):
    project = _project(tmp_path)
    _task(project, "task-a", dependsOn=["task-missing"])

    entry = _by_task(build_backlog(project, "local-project"))["task-a"]
    assert entry["readiness"] == "blocked"
    assert entry["unknownDependsOn"] == ["task-missing"]


def test_running_an_unsatisfied_dependency_is_reported_as_an_ordering_violation(tmp_path: Path):
    project = _project(tmp_path)
    _task(project, "task-a")
    _task(project, "task-b", dependsOn=["task-a"])
    _execution(project, "20260101T000000Z-aaaaaaaa", "task-b", "running")

    entry = _by_task(build_backlog(project, "local-project"))["task-b"]
    assert entry["state"] == "running"
    assert entry["readiness"] == "blocked"


def test_parent_is_hierarchy_and_never_blocks(tmp_path: Path):
    project = _project(tmp_path)
    _task(project, "task-epic")
    _task(project, "task-child", parent="task-epic")

    entry = _by_task(build_backlog(project, "local-project"))["task-child"]
    assert entry["parent"] == "task-epic"
    assert entry["readiness"] == "ready"


def test_dependency_cycle_is_an_error(tmp_path: Path):
    project = _project(tmp_path)
    _task(project, "task-a", dependsOn=["task-b"])
    _task(project, "task-b", dependsOn=["task-a"])

    with pytest.raises(ValueError, match="dependency cycle"):
        build_backlog(project, "local-project")


def test_ready_filter_keeps_only_actionable_tasks_and_renumbers(tmp_path: Path):
    project = _project(tmp_path)
    _task(project, "task-a")
    _task(project, "task-b", dependsOn=["task-a"])
    _task(project, "task-c")
    _task(project, "task-d")
    _execution(project, "20260101T000000Z-aaaaaaaa", "task-c", "completed")
    _execution(project, "20260102T000000Z-bbbbbbbb", "task-d", "running")

    backlog = build_backlog(project, "local-project", ready_only=True)
    assert backlog["filter"] == "ready"
    assert [entry["task"] for entry in backlog["tasks"]] == ["task-a"]
    assert [entry["position"] for entry in backlog["tasks"]] == [1]


def test_ordering_is_deterministic_regardless_of_declaration_order(tmp_path: Path):
    tasks = {
        "task-c": {"dependsOn": ["task-a"]},
        "task-a": {},
        "task-b": {"dependsOn": ["task-c"]},
    }
    assert order_tasks(tasks) == ["task-a", "task-c", "task-b"]
    assert order_tasks(dict(reversed(list(tasks.items())))) == ["task-a", "task-c", "task-b"]


def test_service_validates_the_projection_against_its_schema(tmp_path: Path):
    project = _project(tmp_path)
    _task(project, "task-a")
    _task(project, "task-b", dependsOn=["task-a"], parent="task-a")

    backlog = RuntimeService(project, Path(".")).task_backlog()
    assert backlog["project"] == load_project(project)["metadata"]["id"]
    assert [entry["task"] for entry in backlog["tasks"]] == ["task-a", "task-b"]
