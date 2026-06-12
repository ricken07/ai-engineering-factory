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
    "RepositoryMap": "repository-map.schema.json", "Task": "task.schema.json",
    "Workflow": "workflow.schema.json", "Skill": "skill.schema.json",
    "Policy": "policy.schema.json", "Standard": "standard.schema.json",
    "Profile": "profile.schema.json", "Integration": "integration.schema.json",
    "AgentAdapter": "adapter.schema.json", "Execution": "execution.schema.json",
    "Gate": "gate.schema.json", "Artifact": "artifact.schema.json",
    "Handoff": "handoff.schema.json", "PolicyDecision": "policy-decision.schema.json",
    "TaskMemory": "task-memory.schema.json", "MemoryCandidate": "memory-candidate.schema.json",
    "KnowledgePromotion": "knowledge-promotion.schema.json",
    "McpBinding": "mcp-binding.schema.json",
    "IntegrationContract": "integration-contract.schema.json", "IntegrationLock": "integration-lock.schema.json",
    "Request": "request.schema.json", "IntentResolution": "intent-resolution.schema.json",
}


@dataclass(frozen=True)
class ValidationIssue:
    path: str
    message: str


def load_yaml(path: Path) -> Any:
    with path.open(encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def validate_project(project_root: Path, factory_root: Path) -> list[ValidationIssue]:
    project_root, factory_root = project_root.resolve(), factory_root.resolve()
    schemas: dict[str, dict[str, Any]] = {}
    registry = Registry()
    issues: list[ValidationIssue] = []
    for path in sorted((factory_root / "core" / "schemas").glob("*.json")):
        try:
            schema = json.loads(path.read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(schema)
            schemas[path.name] = schema
            registry = registry.with_resource(schema["$id"], Resource.from_contents(schema))
        except Exception as exc:
            issues.append(ValidationIssue(str(path), str(exc)))
    candidates = [project_root / ".ai" / "project.yaml", project_root / ".ai" / "repository-map.yaml"]
    runtime = project_root / ".ai" / "runtime"
    if runtime.is_dir():
        candidates.extend(sorted(runtime.rglob("*.yaml")))
    for path in candidates:
        if not path.is_file():
            issues.append(ValidationIssue(str(path.relative_to(project_root)), "required document is missing"))
            continue
        try:
            data = load_yaml(path)
            kind = data.get("kind") if isinstance(data, dict) else None
            if kind not in KIND_SCHEMAS:
                raise ValueError(f"unsupported or missing kind: {kind}")
            errors = Draft202012Validator(schemas[KIND_SCHEMAS[kind]], registry=registry).iter_errors(data)
            for error in sorted(errors, key=lambda item: list(item.path)):
                location = ".".join(map(str, error.path)) or "root"
                issues.append(ValidationIssue(str(path.relative_to(project_root)), f"{location}: {error.message}"))
        except Exception as exc:
            issues.append(ValidationIssue(str(path.relative_to(project_root)), str(exc)))
    return issues


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
    contract_operations = {data["metadata"]["id"]: set(data["operations"]) for _, data in documents if data.get("kind") == "IntegrationContract"}
    for path, data in documents:
        for field, kind in ref_kinds.items():
            for ref in data.get(field, []):
                if ref not in catalogs.get(kind, set()):
                    issues.append(ValidationIssue(str(path.relative_to(root)), f"unknown {field} '{ref}'"))
        if data.get("kind") == "Workflow":
            if "recovery-policy" not in data.get("policyRefs", []):
                issues.append(ValidationIssue(str(path.relative_to(root)), "workflow must reference recovery-policy"))
            for phase in data.get("phases", []):
                if phase.get("skill") not in catalogs.get("Skill", set()):
                    issues.append(ValidationIssue(str(path.relative_to(root)), f"unknown skill '{phase.get('skill')}'"))
        if data.get("kind") == "AgentAdapter":
            for group, kind in (("workflows", "Workflow"), ("skills", "Skill")):
                for identifier in data.get("mappings", {}).get(group, {}):
                    if identifier not in catalogs.get(kind, set()):
                        issues.append(ValidationIssue(str(path.relative_to(root)), f"unknown mapped {kind} '{identifier}'"))
        if data.get("kind") == "Skill":
            if "recovery-policy" not in data.get("policyRefs", []):
                issues.append(ValidationIssue(str(path.relative_to(root)), "skill must reference recovery-policy"))
            if "recovery" not in data.get("standardRefs", []):
                issues.append(ValidationIssue(str(path.relative_to(root)), "skill must reference recovery standard"))
        if data.get("kind") == "Project":
            for capability, binding in data.get("integrations", {}).items():
                provider = binding if isinstance(binding, str) else binding.get("provider")
                if provider not in catalogs.get("Integration", set()):
                    issues.append(ValidationIssue(str(path.relative_to(root)), f"unknown integration provider '{provider}' for '{capability}'"))
        if data.get("kind") == "Integration":
            contracts = catalogs.get("IntegrationContract", set())
            for capability in data.get("capabilities", []):
                if capability.get("id") not in contracts:
                    issues.append(ValidationIssue(str(path.relative_to(root)), f"unknown integration contract '{capability.get('id')}'"))
                elif not set(capability.get("operations", [])) <= contract_operations[capability["id"]]:
                    unknown = sorted(set(capability.get("operations", [])) - contract_operations[capability["id"]])
                    issues.append(ValidationIssue(str(path.relative_to(root)), f"operations outside contract '{capability['id']}': {unknown}"))
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
