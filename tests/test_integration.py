"""Governed integration: a human approves before-merge, the Runtime merges."""
from pathlib import Path
import subprocess

import pytest
import yaml

from test_dynamic_policy import ROOT, assert_schema, runtime


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=root, check=True,
                          capture_output=True, text=True).stdout.strip()


def completed_with_task_branch(tmp_path: Path, conflicting: bool = False):
    """A completed execution whose task branch aief/t holds one commit, with
    before-merge required, in a project that is a Git repository on main."""
    service, execution = runtime(tmp_path); identifier = execution.data["metadata"]["id"]
    root = service.project_root
    (root / ".gitignore").write_text(".ai/runtime/\n"); (root / "app.txt").write_text("one\n")
    git(root, "init", "-q", "-b", "main"); git(root, "add", "-A"); git(root, "commit", "-qm", "init")
    git(root, "switch", "-q", "-c", "aief/t"); (root / "app.txt").write_text("two\n"); git(root, "commit", "-qam", "change")
    git(root, "switch", "-q", "-c", "elsewhere", "main")  # the developer works on another branch
    if conflicting:
        git(root, "switch", "-q", "main"); (root / "app.txt").write_text("three\n"); git(root, "commit", "-qam", "other")
        git(root, "switch", "-q", "elsewhere")
    current = service.execution(identifier)
    (current.root / "workspace.yaml").write_text(yaml.safe_dump({"repositories": {"main": {
        "gitRoot": str(root), "taskBranch": "aief/t", "baseBranch": "main"}}}))
    gates = current.data.setdefault("policyGates", [])
    if not any(item["id"] == "before-merge" for item in gates):
        gates.append({"id": "before-merge", "status": "pending"})
    last = current.data["phases"][-1]
    for item in current.data["phases"][:-1]:
        item["status"] = "completed"
    last.update({"status": "waiting-approval", "gate": last.get("gate") or {"id": "submission-gate"}})
    current.data["status"] = "waiting-approval"; current.save()
    service.approve_execution(identifier, approver="alice")
    return service, identifier, root


def test_completion_keeps_before_merge_waiting_for_the_integration(tmp_path: Path):
    service, identifier, root = completed_with_task_branch(tmp_path)
    current = service.execution(identifier)
    assert current.data["status"] == "completed"
    assert next(item for item in current.data["policyGates"] if item["id"] == "before-merge")["status"] == "pending"
    assert current.data["integration"] == {"status": "awaiting-approval", "gate": "before-merge", "repositories": ["main"]}
    from aief.approval_hook import awaited_approvals
    assert {"execution": identifier, "gate": "before-merge", "kind": "policy"} in awaited_approvals(service)


def test_approving_before_merge_makes_the_runtime_merge_the_task_branch(tmp_path: Path):
    service, identifier, root = completed_with_task_branch(tmp_path)
    service.approve_policy_gate(identifier, "before-merge", approver="alice")
    current = service.execution(identifier)
    assert git(root, "show", "main:app.txt") == "two"
    assert git(root, "branch", "--show-current") == "elsewhere" and "aief-integration" not in git(root, "worktree", "list")
    integration = current.data["integration"]
    assert integration["status"] == "integrated" and integration["approvedBy"] == "alice"
    result = integration["repositories"][0]
    assert result["method"] == "merge" and result["baseAfter"] == git(root, "rev-parse", "main")
    assert "AIEF execution" in git(root, "log", "-1", "--format=%s", "main")
    gate = next(item for item in current.data["policyGates"] if item["id"] == "before-merge")
    assert gate["status"] == "approved" and gate["actor"]["assurance"] == "OBSERVED"
    bundle = yaml.safe_load((current.root / "evidence-bundle.yaml").read_text())
    assert bundle["verification"]["integration"]["status"] == "integrated"
    assert "execution.integrated" in [event["event"]["type"] for event in service.task_events(current.data["task"])]
    assert_schema(ROOT, "execution.schema.json", current.data)


def test_a_conflicting_integration_changes_nothing_and_keeps_the_gate(tmp_path: Path):
    service, identifier, root = completed_with_task_branch(tmp_path, conflicting=True)
    before = git(root, "rev-parse", "main")
    with pytest.raises(ValueError, match="does not merge cleanly"):
        service.approve_policy_gate(identifier, "before-merge", approver="alice")
    current = service.execution(identifier)
    assert git(root, "rev-parse", "main") == before and git(root, "show", "main:app.txt") == "three"
    assert next(item for item in current.data["policyGates"] if item["id"] == "before-merge")["status"] == "pending"
    assert current.data["integration"]["status"] == "awaiting-approval"


def test_the_base_branch_checked_out_with_local_changes_blocks_the_integration(tmp_path: Path):
    service, identifier, root = completed_with_task_branch(tmp_path)
    git(root, "switch", "-q", "main"); (root / "app.txt").write_text("uncommitted\n")
    with pytest.raises(PermissionError, match="local changes"):
        service.approve_policy_gate(identifier, "before-merge", approver="alice")
    assert (root / "app.txt").read_text() == "uncommitted\n"
    (root / "app.txt").write_text("one\n")
    service.approve_policy_gate(identifier, "before-merge", approver="alice")
    assert (root / "app.txt").read_text() == "two\n"  # merged in the checked-out base worktree


def test_a_cancelled_execution_does_not_wait_for_integration(tmp_path: Path):
    service, execution = runtime(tmp_path); identifier = execution.data["metadata"]["id"]
    current = service.execution(identifier)
    current.data.setdefault("policyGates", []).append({"id": "before-merge", "status": "pending"}); current.save()
    service.cancel_execution(identifier, "stop")
    gate = next(item for item in service.execution(identifier).data["policyGates"] if item["id"] == "before-merge")
    assert gate["status"] == "not-triggered"
