from __future__ import annotations
from pathlib import Path
from typing import Any, Callable
import subprocess, yaml

def load_profiles(factory: Path) -> dict[str, dict[str, Any]]:
    return {p.parent.name: yaml.safe_load(p.read_text(encoding="utf-8")) for p in factory.glob("profiles/*/profile.yaml")}

def resolve_profiles(factory: Path, selected: list[str]) -> list[dict[str, Any]]:
    catalog = load_profiles(factory); resolved = []; visiting: set[str] = set(); done: set[str] = set()
    def visit(identifier: str) -> None:
        if identifier in done: return
        if identifier in visiting: raise ValueError(f"profile dependency cycle at {identifier}")
        if identifier not in catalog: raise KeyError(f"unknown profile: {identifier}")
        visiting.add(identifier)
        for parent in catalog[identifier].get("extends", []): visit(parent)
        visiting.remove(identifier); done.add(identifier); resolved.append(catalog[identifier])
    for identifier in selected: visit(identifier)
    return resolved

def validation_plan(factory: Path, repository: Path, selected: list[str]) -> list[dict[str, str]]:
    plan = []
    for profile in resolve_profiles(factory, selected):
        files = profile.get("discovery", {}).get("files", [])
        if files and not any((repository / name).exists() for name in files): continue
        for operation, command in profile.get("commands", {}).items():
            plan.append({"profile": profile["metadata"]["id"], "operation": operation, "command": command})
    return plan

def execute_plan(plan: list[dict[str, str]], cwd: Path, execute: bool = False, runner: Callable[..., Any] = subprocess.run) -> list[dict[str, Any]]:
    if not execute: return [{**item, "mode":"plan"} for item in plan]
    results = []
    for item in plan:
        completed = runner(item["command"], cwd=cwd, shell=True, text=True, capture_output=True)
        results.append({**item,"mode":"execute","exitCode":completed.returncode,"stdout":completed.stdout,"stderr":completed.stderr})
    return results

def integration_capabilities(factory: Path, provider: str) -> dict[str, set[str]]:
    path = factory / "integrations" / provider / "integration.yaml"
    if not path.exists(): raise KeyError(f"unknown integration: {provider}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {entry["id"]: set(entry["operations"]) for entry in data["capabilities"]}
