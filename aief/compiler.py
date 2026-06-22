from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import yaml


class CompilationError(ValueError):
    pass


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise CompilationError(f"missing required Factory resource: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise CompilationError(f"resource must contain an object: {path}")
    return data


def compile_workflow(factory: Path, workflow_id: str) -> dict[str, Any]:
    workflow_path = factory / "core" / "workflows" / workflow_id / "workflow.yaml"
    workflow = _load_yaml(workflow_path)
    if workflow.get("metadata", {}).get("id") != workflow_id:
        raise CompilationError(f"workflow id mismatch in {workflow_path}")
    available: set[str] = set(workflow.get("inputs", []))
    phases: list[dict[str, Any]] = []
    capabilities: set[str] = set()
    for phase in workflow.get("phases", []):
        skill_id = phase["skill"]
        skill_root = factory / "core" / "skills" / skill_id
        skill = _load_yaml(skill_root / "skill.yaml")
        if skill.get("metadata", {}).get("id") != skill_id:
            raise CompilationError(f"skill id mismatch for phase {phase['id']}")
        instructions = skill_root / "SKILL.md"
        output_schema = skill_root / "output.schema.json"
        if not instructions.is_file() or not output_schema.is_file():
            raise CompilationError(f"skill {skill_id} is incomplete")
        try:
            json.loads(output_schema.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CompilationError(f"invalid output schema for skill {skill_id}: {exc}") from exc
        contract = skill["contract"]
        missing_inputs = sorted(set(contract.get("inputs", [])) - available)
        # Inputs can also be resolved dynamically by policy/profile/integration layers.
        produced = list(contract.get("outputs", []))
        available.update(produced)
        capabilities.update(contract.get("requiresCapabilities", []))
        phases.append({
            **phase,
            "skillVersion": skill["metadata"].get("version", "0.0.0"),
            "mode": skill["mode"],
            "inputs": list(contract.get("inputs", [])),
            "outputs": produced,
            "unresolvedInputs": missing_inputs,
            "capabilities": list(contract.get("requiresCapabilities", [])),
            "instructions": str(instructions.relative_to(factory)),
            "outputSchema": str(output_schema.relative_to(factory)),
            "engineeringContext": list(skill.get("engineeringContext", {}).get("requires", [])),
        })
    return {
        "id": workflow_id,
        "version": workflow["metadata"].get("version", "0.0.0"),
        "inputs": list(workflow.get("inputs", [])),
        "outputs": list(workflow.get("outputs", [])),
        "policyRefs": list(workflow.get("policyRefs", [])),
        "capabilities": sorted(capabilities),
        "phases": phases,
    }
