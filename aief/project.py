from __future__ import annotations
from pathlib import Path
from typing import Any
import os, shutil, subprocess, yaml
from .yamlio import load_yaml


class StateStoreConflict(RuntimeError):
    """A linked worktree contains state outside the canonical Project store."""


def runtime_root(project_root: Path, project: dict[str, Any] | None = None) -> Path:
    """Resolve the configured Project-owned Runtime State Store."""
    if project is None:
        config = project_root / ".ai" / "project.yaml"
        project = load_yaml(config) if config.is_file() else {}
    configured = project.get("runtime", {}).get("root", ".ai/runtime")
    root = Path(configured)
    return root.resolve() if root.is_absolute() else (project_root / root).resolve()


def _has_runtime_state(root: Path) -> bool:
    runtime = runtime_root(root)
    if not runtime.is_dir():
        return False
    return any(item.name != "README.md" for item in runtime.iterdir())


def _canonical_git_project(candidate: Path) -> Path:
    """Map a linked Git worktree to the main checkout's logical Project root.

    The relative location of ``.ai/project.yaml`` inside the repository is
    preserved. Non-Git and independently initialized projects keep their
    existing path-based behavior.
    """
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel", "--git-common-dir"],
        cwd=candidate, text=True, capture_output=True, check=False,
    )
    if result.returncode != 0:
        return candidate
    lines = result.stdout.splitlines()
    if len(lines) != 2:
        return candidate
    worktree_root = Path(lines[0]).resolve()
    common_dir = Path(lines[1])
    if not common_dir.is_absolute():
        common_dir = (candidate / common_dir).resolve()
    main_root = common_dir.parent
    try:
        relative_project = candidate.relative_to(worktree_root)
    except ValueError:
        return candidate
    canonical = (main_root / relative_project).resolve()
    if canonical == candidate or not (canonical / ".ai" / "project.yaml").is_file():
        return candidate
    if _has_runtime_state(candidate):
        raise StateStoreConflict(
            "linked worktree contains a non-canonical .ai/runtime state store; "
            f"preserve and migrate {candidate / '.ai' / 'runtime'} to {canonical / '.ai' / 'runtime'} before continuing"
        )
    return canonical


def find_project(start: Path) -> Path:
    for path in (start.resolve(), *start.resolve().parents):
        if (path / ".ai" / "project.yaml").is_file():
            return _canonical_git_project(path)
    raise FileNotFoundError("no .ai/project.yaml found")

def load_project(root: Path) -> dict[str, Any]:
    return load_yaml(root / ".ai" / "project.yaml")

def factory_home(project: dict[str, Any]) -> Path:
    key = project["factory"].get("homeEnv", "AI_FACTORY_HOME")
    value = os.environ.get(key)
    if not value: raise FileNotFoundError(f"environment variable {key} is not set")
    base = Path(value).expanduser()
    versioned = base / project["factory"]["version"]
    if not versioned.is_dir():
        raise FileNotFoundError(f"Factory version {project['factory']['version']} is not installed at {versioned}")
    return versioned

def initialize(template: Path, destination: Path, force: bool = False) -> None:
    if (destination / ".ai").exists() and not force: raise FileExistsError("project is already initialized")
    shutil.copytree(template, destination, dirs_exist_ok=force)
