from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator
from referencing import Registry, Resource


KIND_SCHEMAS = {
    "Factory": "factory.schema.json", "Project": "project.schema.json",
    "RepositoryMap": "repository.schema.json", "Task": "task.schema.json",
    "Workflow": "workflow.schema.json", "Skill": "skill.schema.json",
    "Policy": "policy.schema.json", "Standard": "standard.schema.json",
    "Profile": "profile.schema.json", "Integration": "integration.schema.json",
    "AgentAdapter": "adapter.schema.json", "Execution": "execution.schema.json",
    "Gate": "gate.schema.json", "Artifact": "artifact.schema.json",
    "Handoff": "handoff.schema.json", "PolicyDecision": "policy-decision.schema.json",
}


@dataclass(frozen=True)
class ValidationIssue:
    path: str
    message: str


def load_yaml(path: Path) -> Any:
    with path.open(encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def validate_package(root: Path) -> list[ValidationIssue]:
    root = root.resolve()
    schemas_dir = root / "core" / "schemas"
    issues: list[ValidationIssue] = []
    schemas: dict[str, dict[str, Any]] = {}
    registry = Registry()
    for path in sorted(schemas_dir.glob("*.json")):
        try:
            schema = json.loads(path.read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(schema)
            schemas[path.name] = schema
            registry = registry.with_resource(schema["$id"], Resource.from_contents(schema))
        except Exception as exc:
            issues.append(ValidationIssue(str(path.relative_to(root)), str(exc)))

    documents: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(root.rglob("*.yaml")):
        if any(part in {".git", ".venv", "build"} for part in path.parts):
            continue
        try:
            data = load_yaml(path)
            if not isinstance(data, dict):
                raise ValueError("document root must be an object")
            documents.append((path, data))
            kind = data.get("kind")
            if kind in KIND_SCHEMAS:
                schema = schemas[KIND_SCHEMAS[kind]]
                errors = Draft202012Validator(schema, registry=registry).iter_errors(data)
                for error in sorted(errors, key=lambda item: list(item.path)):
                    location = ".".join(map(str, error.path)) or "root"
                    issues.append(ValidationIssue(str(path.relative_to(root)), f"{location}: {error.message}"))
            elif kind is not None:
                issues.append(ValidationIssue(str(path.relative_to(root)), f"unsupported kind: {kind}"))
        except Exception as exc:
            issues.append(ValidationIssue(str(path.relative_to(root)), str(exc)))

    ids: dict[tuple[str, str], Path] = {}
    catalogs: dict[str, set[str]] = {}
    for path, data in documents:
        kind, identifier = data.get("kind"), data.get("metadata", {}).get("id")
        if kind and identifier:
            key = (kind, identifier)
            if key in ids:
                issues.append(ValidationIssue(str(path.relative_to(root)), f"duplicate {kind} id '{identifier}'"))
            ids[key] = path
            catalogs.setdefault(kind, set()).add(identifier)

    ref_kinds = {"policyRefs": "Policy", "standardRefs": "Standard"}
    for path, data in documents:
        for field, kind in ref_kinds.items():
            for ref in data.get(field, []):
                if ref not in catalogs.get(kind, set()):
                    issues.append(ValidationIssue(str(path.relative_to(root)), f"unknown {field} '{ref}'"))
        if data.get("kind") == "Workflow":
            for phase in data.get("phases", []):
                if phase.get("skill") not in catalogs.get("Skill", set()):
                    issues.append(ValidationIssue(str(path.relative_to(root)), f"unknown skill '{phase.get('skill')}'"))
        if data.get("kind") == "AgentAdapter":
            for group, kind in (("workflows", "Workflow"), ("skills", "Skill")):
                for identifier in data.get("mappings", {}).get(group, {}):
                    if identifier not in catalogs.get(kind, set()):
                        issues.append(ValidationIssue(str(path.relative_to(root)), f"unknown mapped {kind} '{identifier}'"))
    for directory in sorted((root / "core" / "skills").iterdir()):
        if not directory.is_dir(): continue
        for required in ("skill.yaml", "SKILL.md", "output.schema.json", "examples/output.yaml"):
            if not (directory / required).is_file(): issues.append(ValidationIssue(str(directory.relative_to(root)), f"missing {required}"))
        try:
            output_schema = json.loads((directory / "output.schema.json").read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(output_schema)
            example = load_yaml(directory / "examples/output.yaml")
            for error in Draft202012Validator(output_schema).iter_errors(example):
                issues.append(ValidationIssue(str(directory.relative_to(root)), f"invalid output example: {error.message}"))
        except Exception as exc: issues.append(ValidationIssue(str(directory.relative_to(root)), str(exc)))
    return issues
