from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .intake import TaskRegistry
from .yamlio import load_yaml

# An Execution owns its Task from creation, including while it still sits at
# `pending`: no second Execution should be opened for the same work. Only these
# two outcomes release it again.
RETRYABLE = {"failed", "cancelled"}


def task_executions(project_root: Path) -> dict[str, list[tuple[str, str]]]:
    """Map every Task id to its ``(execution id, status)`` pairs, oldest first.

    Execution identifiers embed a UTC timestamp, so the sorted glob already
    yields them chronologically without reading any clock.
    """
    root = project_root / ".ai" / "runtime" / "executions"
    executions: dict[str, list[tuple[str, str]]] = {}
    if not root.is_dir():
        return executions
    for path in sorted(root.glob("*/execution.yaml")):
        data = load_yaml(path)
        task = data.get("task")
        if task:
            executions.setdefault(task, []).append((path.parent.name, data.get("status", "pending")))
    return executions


def derive_state(executions: list[tuple[str, str]]) -> str:
    """A Task inherits the status of its most recent Execution."""
    return executions[-1][1] if executions else "pending"


def derive_readiness(state: str, blocked_by: list[str], unknown: list[str], owned: bool) -> str:
    """Readiness is derived from state, never declared.

    ``done``    the Task reached a completed Execution.
    ``blocked`` at least one declared dependency is unsatisfied or unknown.
    ``active``  an Execution already owns the Task and has not terminated.
    ``ready``   no Execution owns the Task — either none was ever opened, or the
                last one failed or was cancelled, which stays retryable.
    """
    if state == "completed":
        return "done"
    if blocked_by or unknown:
        return "blocked"
    if owned and state not in RETRYABLE:
        return "active"
    return "ready"


def order_tasks(tasks: dict[str, dict[str, Any]]) -> list[str]:
    """Topologically order Task ids by ``dependsOn``; a cycle is an error.

    ``parent`` is hierarchy, not sequence, so it never participates in the
    ordering. Unknown references cannot be ordered and are reported as blockers
    instead of silently dropped.
    """
    state: dict[str, str] = {}
    ordered: list[str] = []

    def visit(identifier: str, chain: tuple[str, ...]) -> None:
        if state.get(identifier) == "done":
            return
        if state.get(identifier) == "visiting":
            raise ValueError(f"dependency cycle detected among tasks: {' -> '.join(chain + (identifier,))}")
        state[identifier] = "visiting"
        for reference in tasks[identifier].get("dependsOn", []):
            if reference in tasks:
                visit(reference, chain + (identifier,))
        state[identifier] = "done"
        ordered.append(identifier)

    for identifier in sorted(tasks):
        visit(identifier, ())
    return ordered


def build_backlog(project_root: Path, project_id: str, ready_only: bool = False) -> dict[str, Any]:
    """Project the registered Tasks into a dependency-ordered readiness view."""
    tasks = {task["metadata"]["id"]: task for task in TaskRegistry(project_root).list()}
    executions = task_executions(project_root)
    states = {identifier: derive_state(executions.get(identifier, [])) for identifier in tasks}

    entries: list[dict[str, Any]] = []
    for position, identifier in enumerate(order_tasks(tasks), start=1):
        task = tasks[identifier]
        declared = list(task.get("dependsOn", []))
        unknown = [reference for reference in declared if reference not in tasks]
        blocked_by = [reference for reference in declared if reference in tasks and states[reference] != "completed"]
        entry: dict[str, Any] = {
            "task": identifier,
            "position": position,
            "state": states[identifier],
            "readiness": derive_readiness(states[identifier], blocked_by, unknown, bool(executions.get(identifier))),
        }
        for key, value in (
            ("summary", task.get("objective", {}).get("summary")),
            ("workflow", task.get("workflow")),
            ("intent", task.get("intent", {}).get("type")),
            ("parent", task.get("parent")),
        ):
            if value:
                entry[key] = value
        for key, value in (
            ("dependsOn", declared), ("blockedBy", blocked_by), ("unknownDependsOn", unknown),
            ("executions", [execution for execution, _ in executions.get(identifier, [])]),
        ):
            if value:
                entry[key] = value
        entries.append(entry)

    if ready_only:
        entries = [entry for entry in entries if entry["readiness"] == "ready"]
        for position, entry in enumerate(entries, start=1):
            entry["position"] = position

    return {
        "apiVersion": "aief.dev/v1alpha1",
        "kind": "TaskBacklog",
        "metadata": {"id": "task-backlog"},
        "project": project_id,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "filter": "ready" if ready_only else "all",
        "tasks": entries,
    }
