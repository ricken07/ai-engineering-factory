"""Change proposals: implementation when local file modification is denied.

At an autonomy level that allows `propose-change` but not
`modify-local-files` (L1), the agent delivers its change as patches instead of
editing the workspace. The Runtime enforces the denial deterministically: it
fingerprints every Git root of the execution when the phase starts and
refuses the phase output when the workspace changed. The patches reach the
workspace only through the `apply-proposal` gate: a human approves, and the
Runtime itself applies them.
"""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Any, Callable

from .workspace import _run

Runner = Callable[..., Any]

APPLY_GATE = "apply-proposal"


def implementation_action(plan: dict[str, Any] | None) -> str:
    """Action an implementation phase may perform under the governed plan."""
    if plan is None:
        # Executions without a governed plan predate policy reassessment.
        return "modify-local-files"
    allowed = set(plan.get("allowedActions", []))
    denied = set(plan.get("deniedActions", []))
    if "modify-local-files" in allowed and "modify-local-files" not in denied:
        return "modify-local-files"
    if "propose-change" in allowed and "propose-change" not in denied:
        return "propose-change"
    raise PermissionError("the governed execution plan allows neither modify-local-files nor propose-change")


def repository_roots(workspace: dict[str, Any], runner: Runner = subprocess.run) -> dict[str, str]:
    """Git root (worktree root in worktree mode) of every workspace repository."""
    roots: dict[str, str] = {}
    for identifier, binding in workspace.get("repositories", {}).items():
        root = binding.get("worktreeRoot") or binding.get("gitRoot")
        if not root:
            root = _run(Path(binding.get("executionPath") or binding["path"]), ["rev-parse", "--show-toplevel"], runner)
        roots[identifier] = str(Path(root).resolve())
    return roots


def _state(root: str, ignored: list[str], runner: Runner) -> str:
    path = Path(root)
    status = [line for line in _run(path, ["status", "--porcelain=v1", "--untracked-files=all"], runner).splitlines()
              if not any(line[3:].startswith(prefix) for prefix in ignored)]
    diff = _run(path, ["diff", "HEAD", "--binary"], runner)
    head = _run(path, ["rev-parse", "HEAD"], runner)
    return hashlib.sha256("\n".join([head, *status, diff]).encode("utf-8")).hexdigest()


def _ignored(root: str, runtime: Path) -> list[str]:
    """The Runtime state store may live inside a Git root; it is not the change."""
    try:
        relative = runtime.resolve().relative_to(Path(root))
    except ValueError:
        return []
    return [f"{relative.as_posix()}/"]


def snapshot(roots: dict[str, str], runtime: Path, runner: Runner = subprocess.run) -> dict[str, str]:
    return {root: _state(root, _ignored(root, runtime), runner) for root in sorted(set(roots.values()))}


def changed_roots(baseline: dict[str, str], runtime: Path, runner: Runner = subprocess.run) -> list[str]:
    return [root for root, state in baseline.items() if _state(root, _ignored(root, runtime), runner) != state]


def proposal_patches(output: dict[str, Any], roots: dict[str, str], execution_root: Path) -> list[dict[str, str]]:
    """Validated patch list of an implementation output in propose-change mode."""
    patches = (output.get("details", {}).get("proposal") or {}).get("patches")
    if not isinstance(patches, list) or not patches:
        raise ValueError("a propose-change implementation lists its patches in details.proposal.patches")
    result = []
    for item in patches:
        if not isinstance(item, dict) or not item.get("repository") or not item.get("path"):
            raise ValueError("each proposal patch declares a repository and a path")
        if item["repository"] not in roots:
            raise ValueError(f"proposal patch targets a repository outside the execution workspace: {item['repository']}")
        path = Path(item["path"])
        path = (path if path.is_absolute() else execution_root / path).resolve()
        if not path.is_relative_to(execution_root.resolve()) or not path.is_file():
            raise ValueError(f"proposal patch must be a file inside the execution directory: {item['path']}")
        content = path.read_bytes()
        result.append({"repository": item["repository"], "root": roots[item["repository"]],
                       "path": path.relative_to(execution_root.resolve()).as_posix(),
                       "sha256": hashlib.sha256(content).hexdigest()})
    return result


def _apply(patches: list[dict[str, str]], execution_root: Path, check: bool, runner: Runner) -> None:
    for patch in patches:
        args = ["apply", "--recount", "--whitespace=nowarn"] + (["--check"] if check else [])
        try:
            _run(Path(patch["root"]), [*args, str(execution_root / patch["path"])], runner)
        except RuntimeError as error:
            raise ValueError(f"proposal patch {patch['path']} does not apply to {patch['repository']}: {error}") from error


def check_patches(patches: list[dict[str, str]], execution_root: Path, runner: Runner = subprocess.run) -> None:
    _apply(patches, execution_root, True, runner)


def apply_patches(patches: list[dict[str, str]], execution_root: Path, runner: Runner = subprocess.run) -> None:
    for patch in patches:
        content = (execution_root / patch["path"]).read_bytes()
        if hashlib.sha256(content).hexdigest() != patch["sha256"]:
            raise PermissionError(f"proposal patch changed after it was proposed: {patch['path']}")
    _apply(patches, execution_root, True, runner)
    _apply(patches, execution_root, False, runner)
