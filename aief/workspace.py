from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
import re
import subprocess

import yaml
from .yamlio import load_yaml


Runner = Callable[..., Any]
FORBIDDEN_GIT_OPTIONS = {"--force", "-f", "--force-with-lease"}


def validate_git_action(command: list[str]) -> None:
    """Reject destructive Git operations at the deterministic boundary."""
    if not command or command[0] != "git":
        raise ValueError("workspace operations must use a structured git command")
    args = command[1:]
    if any(arg in FORBIDDEN_GIT_OPTIONS for arg in args):
        raise PermissionError("force operations are forbidden by workspace safety policy")
    if args[:2] == ["reset", "--hard"] or (args and args[0] == "clean"):
        raise PermissionError("destructive workspace operations are forbidden")
    if args and args[0] == "branch" and any(arg in {"-d", "-D", "--delete"} for arg in args[1:]):
        raise PermissionError("branch deletion is not managed by the Factory Runtime")
    if args and args[0] in {"checkout", "switch"} and "--discard-changes" in args:
        raise PermissionError("discarding local changes is forbidden")


def _run(repo: Path, args: list[str], runner: Runner = subprocess.run) -> str:
    command = ["git", *args]
    validate_git_action(command)
    result = runner(command, cwd=repo, text=True, capture_output=True, shell=False)
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "git command failed").strip()
        raise RuntimeError(f"git {' '.join(args)} failed in {repo}: {message}")
    return result.stdout.strip()


def _exists(repo: Path, args: list[str], runner: Runner = subprocess.run) -> bool:
    command = ["git", *args]
    validate_git_action(command)
    result = runner(command, cwd=repo, text=True, capture_output=True, shell=False)
    return result.returncode == 0


def _task_branch(reference: str, prefix: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", reference).strip("-.").lower()
    if not slug:
        raise ValueError("task reference cannot produce a safe branch name")
    return f"{prefix.rstrip('/')}/{slug}"


class WorkspaceManager:
    """Inspect and isolate Git repositories without touching developer changes."""

    def __init__(self, project_root: Path, project: dict[str, Any], execution_root: Path, runner: Runner = subprocess.run):
        self.project_root = project_root.resolve()
        self.project = project
        self.execution_root = execution_root
        self.runner = runner
        self.config = project.get("workspaceSafety", {})

    @property
    def state_path(self) -> Path:
        return self.execution_root / "workspace.yaml"

    def _repositories(self, identifiers: list[str]) -> list[dict[str, Any]]:
        catalog = {item["id"]: item for item in self.project.get("repositories", [])}
        unknown = sorted(set(identifiers) - set(catalog))
        if unknown:
            raise KeyError(f"unknown impacted repositories: {', '.join(unknown)}")
        return [catalog[item] for item in dict.fromkeys(identifiers)]

    def _path(self, repository: dict[str, Any]) -> Path:
        path = (self.project_root / repository["path"]).resolve()
        if not path.is_relative_to(self.project_root):
            raise ValueError(f"repository path escapes project workspace: {repository['id']}")
        if not path.is_dir():
            raise FileNotFoundError(f"repository path is missing: {repository['id']}: {path}")
        return path

    def inspect(self, identifiers: list[str], task_reference: str) -> dict[str, Any]:
        repositories: dict[str, Any] = {}
        blockers: list[dict[str, str]] = []
        mode = self.config.get("mode", "require-clean")
        prefix = self.config.get("taskBranchPrefix", "aief")
        for repository in self._repositories(identifiers):
            path = self._path(repository)
            git_root = Path(_run(path, ["rev-parse", "--show-toplevel"], self.runner)).resolve()
            if git_root != path:
                raise ValueError(f"configured repository is not a Git root: {repository['id']}: {path}")
            branch = _run(path, ["symbolic-ref", "--quiet", "--short", "HEAD"], self.runner)
            head = _run(path, ["rev-parse", "HEAD"], self.runner)
            status = _run(path, ["status", "--porcelain=v1", "--untracked-files=all"], self.runner)
            changes = [line for line in status.splitlines() if line]
            conflicts = [line[3:] for line in changes if len(line) > 2 and line[:2] in {"DD", "AU", "UD", "UA", "DU", "AA", "UU"}]
            base_branch = repository.get("git", {}).get("baseBranch", self.config.get("baseBranch", "main"))
            base_commit = _run(path, ["rev-parse", base_branch], self.runner)
            task_branch = _task_branch(task_reference, repository.get("git", {}).get("taskBranchPrefix", prefix))
            item = {"path":str(path), "branch":branch, "clean":not changes, "headCommit":head, "baseCommit":base_commit,
                    "baseBranch":base_branch, "taskBranch":task_branch, "changes":changes, "conflicts":conflicts}
            repositories[repository["id"]] = item
            if conflicts:
                blockers.append({"repository":repository["id"], "reason":"unmerged-conflicts"})
            elif changes and mode == "require-clean":
                blockers.append({"repository":repository["id"], "reason":"unrelated-local-changes"})
            elif mode == "require-clean" and branch != base_branch:
                blockers.append({"repository":repository["id"], "reason":"wrong-base-branch"})
        decision = {"status":"blocked" if blockers else ("isolation-required" if mode == "worktree" else "branch-required"),
                    "mode":mode, "reasons":blockers}
        document = {"apiVersion":"factory.gaddigital.io/v1alpha1", "kind":"WorkspaceSnapshot",
                    "metadata":{"id":f"workspace-{self.execution_root.name}"},
                    "capturedAt":datetime.now(timezone.utc).isoformat(), "repositories":repositories, "decision":decision}
        self.state_path.write_text(yaml.safe_dump(document, sort_keys=False, allow_unicode=True), encoding="utf-8")
        return document

    def load(self) -> dict[str, Any]:
        if not self.state_path.is_file():
            raise FileNotFoundError(f"workspace state not found: {self.state_path}")
        return load_yaml(self.state_path)

    def prepare(self, identifiers: list[str], task_reference: str, execute: bool = False) -> dict[str, Any]:
        state = self.inspect(identifiers, task_reference)
        if state["decision"]["status"] == "blocked":
            return state
        if state["decision"]["mode"] == "require-clean":
            operations = [{"repository":identifier, "command":["git", "switch", "-c", repository["taskBranch"]], "cwd":repository["path"]}
                          for identifier, repository in state["repositories"].items()]
            state["operations"] = operations
            if execute:
                collisions = [item["repository"] for item in operations if _exists(Path(item["cwd"]), ["show-ref", "--verify", "--quiet", f"refs/heads/{state['repositories'][item['repository']]['taskBranch']}"], self.runner)]
                if collisions:
                    raise FileExistsError(f"task branch already exists: {', '.join(collisions)}")
                for operation in operations:
                    _run(Path(operation["cwd"]), operation["command"][1:], self.runner)
                state["decision"]["status"] = "ready"
            self.state_path.write_text(yaml.safe_dump(state, sort_keys=False, allow_unicode=True), encoding="utf-8")
            return state
        root = self.project_root / self.project.get("runtime", {}).get("root", ".ai/runtime") / "worktrees" / self.execution_root.name
        operations = []
        for identifier, repository in state["repositories"].items():
            destination = root / identifier
            command = ["git", "worktree", "add", "-b", repository["taskBranch"], str(destination), repository["baseCommit"]]
            validate_git_action(command)
            operations.append({"repository":identifier, "command":command, "cwd":repository["path"], "destination":str(destination)})
        state["operations"] = operations
        if execute:
            collisions = [item["repository"] for item in operations if _exists(Path(item["cwd"]), ["show-ref", "--verify", "--quiet", f"refs/heads/{state['repositories'][item['repository']]['taskBranch']}"], self.runner)]
            if collisions:
                raise FileExistsError(f"task branch already exists: {', '.join(collisions)}")
            for operation in operations:
                destination = Path(operation["destination"])
                if destination.exists():
                    raise FileExistsError(f"worktree destination already exists: {destination}")
                _run(Path(operation["cwd"]), operation["command"][1:], self.runner)
                state["repositories"][operation["repository"]]["executionPath"] = operation["destination"]
            state["decision"]["status"] = "ready"
            state["decision"]["isolated"] = True
        self.state_path.write_text(yaml.safe_dump(state, sort_keys=False, allow_unicode=True), encoding="utf-8")
        return state

    def verify(self) -> dict[str, Any]:
        state = self.load()
        drift: list[dict[str, str]] = []
        for identifier, repository in state["repositories"].items():
            path = Path(repository.get("executionPath", repository["path"]))
            branch = _run(path, ["symbolic-ref", "--quiet", "--short", "HEAD"], self.runner)
            expected_branch = repository["taskBranch"] if state["decision"].get("status") == "ready" else repository["branch"]
            if branch != expected_branch:
                drift.append({"repository":identifier, "reason":"branch-changed"})
            if _run(path, ["ls-files", "--unmerged"], self.runner):
                drift.append({"repository":identifier, "reason":"unmerged-conflicts"})
            if not repository.get("executionPath") and state["decision"].get("status") != "ready":
                head = _run(path, ["rev-parse", "HEAD"], self.runner)
                if head != repository["baseCommit"]:
                    drift.append({"repository":identifier, "reason":"head-changed"})
        return {"status":"blocked" if drift else "ready", "drift":drift, "repositories":state["repositories"]}

    def rollback(self, execute: bool = False) -> dict[str, Any]:
        """Undo Factory-owned workspace preparation without discarding changes."""
        state = self.load()
        operations: list[dict[str, Any]] = []
        for identifier, repository in state["repositories"].items():
            execution_path = repository.get("executionPath")
            path = Path(execution_path or repository["path"])
            if _run(path, ["status", "--porcelain=v1", "--untracked-files=all"], self.runner):
                raise RuntimeError(f"rollback refused because execution workspace is dirty: {identifier}")
            if execution_path:
                expected_root = (self.project_root / self.project.get("runtime", {}).get("root", ".ai/runtime") / "worktrees" / self.execution_root.name).resolve()
                if not path.resolve().is_relative_to(expected_root):
                    raise PermissionError(f"worktree is not owned by this execution: {path}")
                operations.append({"repository":identifier,"command":["git","worktree","remove",str(path)],"cwd":repository["path"]})
            else:
                operations.append({"repository":identifier,"command":["git","switch",repository["baseBranch"]],"cwd":repository["path"]})
        state["rollbackOperations"] = operations
        if execute:
            for operation in operations:
                _run(Path(operation["cwd"]), operation["command"][1:], self.runner)
            state["decision"]["status"] = "rolled-back"
        self.state_path.write_text(yaml.safe_dump(state, sort_keys=False, allow_unicode=True), encoding="utf-8")
        return state
