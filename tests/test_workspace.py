from pathlib import Path
import subprocess

import pytest
import yaml

from aief.project import initialize
from aief.service import RuntimeService
from aief.workspace import WorkspaceManager, validate_git_action


def git(path: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=path, text=True, capture_output=True, check=True)
    return result.stdout.strip()


def repository(path: Path, dirty: bool = False) -> None:
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init", "-b", "main")
    git(path, "config", "user.email", "factory@example.invalid")
    git(path, "config", "user.name", "Factory Test")
    (path / "README.md").write_text("baseline\n")
    git(path, "add", "README.md")
    git(path, "commit", "-m", "baseline")
    if dirty:
        (path / "developer.txt").write_text("do not touch\n")


def manager(tmp_path: Path, mode: str = "require-clean", dirty: bool = False):
    root = tmp_path / "project"; root.mkdir(); repo = root / "api"; repository(repo, dirty)
    execution = root / ".ai/runtime/executions/exec-1"; execution.mkdir(parents=True)
    project = {"workspaceSafety":{"mode":mode,"baseBranch":"main","taskBranchPrefix":"aief"},
               "repositories":[{"id":"api","path":"api","role":"application"}], "runtime":{"root":".ai/runtime"}}
    return WorkspaceManager(root, project, execution), repo


def test_dirty_workspace_blocks_and_preserves_developer_changes(tmp_path: Path):
    workspace, repo = manager(tmp_path, dirty=True)
    state = workspace.inspect(["api"], "EGW-142")
    assert state["decision"]["status"] == "blocked"
    assert state["decision"]["reasons"][0]["reason"] == "unrelated-local-changes"
    assert (repo / "developer.txt").read_text() == "do not touch\n"
    assert git(repo, "branch", "--show-current") == "main"


def test_clean_workspace_requires_explicit_task_branch_creation(tmp_path: Path):
    workspace, repo = manager(tmp_path)
    plan = workspace.prepare(["api"], "EGW-142")
    assert plan["decision"]["status"] == "branch-required"
    assert git(repo, "branch", "--show-current") == "main"
    prepared = workspace.prepare(["api"], "EGW-142", execute=True)
    assert prepared["decision"]["status"] == "ready"
    assert git(repo, "branch", "--show-current") == "aief/egw-142"
    assert workspace.verify()["status"] == "ready"


def test_worktree_mode_isolates_execution_from_original_repository(tmp_path: Path):
    workspace, repo = manager(tmp_path, mode="worktree", dirty=True)
    planned = workspace.prepare(["api"], "EGW-142")
    assert planned["decision"]["status"] == "isolation-required"
    prepared = workspace.prepare(["api"], "EGW-142", execute=True)
    execution_path = Path(prepared["repositories"]["api"]["executionPath"])
    assert execution_path.is_dir()
    assert git(execution_path, "branch", "--show-current") == "aief/egw-142"
    assert git(repo, "branch", "--show-current") == "main"
    assert (repo / "developer.txt").read_text() == "do not touch\n"


@pytest.mark.parametrize("command", [
    ["git","push","--force"], ["git","push","-f"], ["git","reset","--hard"],
    ["git","clean","-fd"], ["git","branch","-D","work"], ["git","switch","--discard-changes","main"],
])
def test_destructive_git_actions_are_rejected(command):
    with pytest.raises(PermissionError):
        validate_git_action(command)


def test_polyrepo_snapshot_blocks_if_one_repository_is_dirty(tmp_path: Path):
    root=tmp_path/"project"; root.mkdir(); repository(root/"api"); repository(root/"app",dirty=True)
    execution=root/".ai/runtime/executions/exec-1"; execution.mkdir(parents=True)
    project={"workspaceSafety":{"mode":"require-clean"},"repositories":[
        {"id":"api","path":"api","role":"backend"},{"id":"app","path":"app","role":"frontend"}]}
    state=WorkspaceManager(root,project,execution).inspect(["api","app"],"EGW-142")
    assert state["repositories"]["api"]["clean"] is True
    assert state["repositories"]["app"]["clean"] is False
    assert state["decision"]["status"] == "blocked"


def test_wrong_base_branch_blocks_strict_mode(tmp_path: Path):
    workspace, repo = manager(tmp_path)
    git(repo, "switch", "-c", "developer-work")
    state = workspace.inspect(["api"], "EGW-142")
    assert state["decision"]["status"] == "blocked"
    assert state["decision"]["reasons"][0]["reason"] == "wrong-base-branch"


def test_worktree_uses_configured_base_commit_not_developer_head(tmp_path: Path):
    workspace, repo = manager(tmp_path, mode="worktree")
    base = git(repo, "rev-parse", "main")
    git(repo, "switch", "-c", "developer-work")
    (repo / "developer-commit.txt").write_text("private\n")
    git(repo, "add", "developer-commit.txt"); git(repo, "commit", "-m", "developer work")
    state = workspace.prepare(["api"], "EGW-142", execute=True)
    isolated = Path(state["repositories"]["api"]["executionPath"])
    assert git(isolated, "rev-parse", "HEAD") == base
    assert not (isolated / "developer-commit.txt").exists()


def test_rollback_only_removes_clean_execution_owned_worktree(tmp_path: Path):
    workspace, repo = manager(tmp_path, mode="worktree")
    state = workspace.prepare(["api"], "EGW-142", execute=True)
    isolated = Path(state["repositories"]["api"]["executionPath"])
    plan = workspace.rollback()
    assert isolated.exists() and plan["rollbackOperations"][0]["command"][1:3] == ["worktree", "remove"]
    rolled_back = workspace.rollback(execute=True)
    assert rolled_back["decision"]["status"] == "rolled-back"
    assert not isolated.exists() and git(repo, "branch", "--show-current") == "main"


def test_rollback_refuses_to_discard_execution_changes(tmp_path: Path):
    workspace, _ = manager(tmp_path, mode="worktree")
    state = workspace.prepare(["api"], "EGW-142", execute=True)
    isolated = Path(state["repositories"]["api"]["executionPath"])
    (isolated / "agent-change.txt").write_text("keep\n")
    with pytest.raises(RuntimeError, match="rollback refused"):
        workspace.rollback(execute=True)
    assert (isolated / "agent-change.txt").exists()


def test_workspace_snapshot_is_schema_valid(tmp_path: Path):
    from aief.validation import assert_schema
    workspace, _ = manager(tmp_path)
    state = workspace.inspect(["api"], "EGW-142")
    assert_schema(Path("."), "workspace-snapshot.schema.json", state)
