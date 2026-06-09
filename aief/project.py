from __future__ import annotations
from pathlib import Path
from typing import Any
import os, shutil, yaml

def find_project(start: Path) -> Path:
    for path in (start.resolve(), *start.resolve().parents):
        if (path / ".ai" / "project.yaml").is_file(): return path
    raise FileNotFoundError("no .ai/project.yaml found")

def load_project(root: Path) -> dict[str, Any]:
    return yaml.safe_load((root / ".ai" / "project.yaml").read_text(encoding="utf-8"))

def factory_home(project: dict[str, Any]) -> Path:
    key = project["factory"].get("homeEnv", "GAD_AI_FACTORY_HOME")
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
