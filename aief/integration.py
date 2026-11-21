"""Governed integration of an execution's task branch into its base branch.

At high or critical risk the policy requires a human `before-merge` approval.
Merging is a Git mutation of the base branch, so the Runtime performs it
itself once a human approved the gate through an OBSERVED channel, and keeps
the result as evidence. The agent never merges (see the coding agent harness
permission rules); a merge performed outside AIEF is invisible to it, which
is why the gate stays pending, not closed, until the integration happens.
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable

from .workspace import _exists, _run

Runner = Callable[..., Any]

MERGE_GATE = "before-merge"


def integration_targets(workspace: dict[str, Any]) -> list[dict[str, str]]:
    """Repositories whose task branch the execution produced."""
    targets = []
    for identifier, binding in workspace.get("repositories", {}).items():
        task, base, root = binding.get("taskBranch"), binding.get("baseBranch"), binding.get("gitRoot")
        if task and base and root:
            targets.append({"repository": identifier, "gitRoot": str(root), "taskBranch": task, "baseBranch": base})
    return targets


def _worktree_of(root: Path, branch: str, runner: Runner) -> Path | None:
    """Worktree that has `branch` checked out, if any."""
    current: Path | None = None
    for line in _run(root, ["worktree", "list", "--porcelain"], runner).splitlines():
        if line.startswith("worktree "):
            current = Path(line[len("worktree "):])
        elif line == f"branch refs/heads/{branch}" and current is not None:
            return current
    return None


def _merge(where: Path, target: dict[str, str], message: str, runner: Runner) -> str:
    try:
        _run(where, ["merge", "--no-ff", "--no-edit", "-m", message, target["taskBranch"]], runner)
    except RuntimeError as error:
        if _exists(where, ["rev-parse", "-q", "--verify", "MERGE_HEAD"], runner):
            _run(where, ["merge", "--abort"], runner)
        raise ValueError(f"{target['taskBranch']} does not merge cleanly into {target['baseBranch']} "
                         f"({target['repository']}): {error}. Nothing was integrated; update the task branch "
                         f"in a new execution, then approve the integration again") from error
    return _run(where, ["rev-parse", "HEAD"], runner)


def integrate(target: dict[str, str], execution_id: str, runner: Runner = subprocess.run) -> dict[str, str]:
    """Merge the task branch into the base branch, without touching any
    other branch or uncommitted work. Fails closed when the base branch is
    checked out with local changes."""
    root = Path(target["gitRoot"])
    for branch in (target["taskBranch"], target["baseBranch"]):
        if not _exists(root, ["rev-parse", "--verify", "-q", f"refs/heads/{branch}"], runner):
            raise ValueError(f"branch {branch} does not exist in {target['repository']}")
    task_commit = _run(root, ["rev-parse", target["taskBranch"]], runner)
    base_before = _run(root, ["rev-parse", target["baseBranch"]], runner)
    if _exists(root, ["merge-base", "--is-ancestor", task_commit, base_before], runner):
        return {**target, "taskCommit": task_commit, "baseBefore": base_before, "baseAfter": base_before,
                "method": "already-integrated"}
    message = f"Merge {target['taskBranch']} into {target['baseBranch']} (AIEF execution {execution_id})"
    checked_out = _worktree_of(root, target["baseBranch"], runner)
    if checked_out is not None:
        if _run(checked_out, ["status", "--porcelain", "--untracked-files=no"], runner):
            raise PermissionError(f"{target['baseBranch']} is checked out in {checked_out} with local changes: "
                                  "commit or stash them, then approve the integration again")
        merged = _merge(checked_out, target, message, runner)
    else:
        temporary = Path(tempfile.mkdtemp(prefix="aief-integration-")) / "base"
        _run(root, ["worktree", "add", str(temporary), target["baseBranch"]], runner)
        try:
            merged = _merge(temporary, target, message, runner)
        finally:
            _run(root, ["worktree", "remove", str(temporary)], runner)
    return {**target, "taskCommit": task_commit, "baseBefore": base_before, "baseAfter": merged, "method": "merge"}
