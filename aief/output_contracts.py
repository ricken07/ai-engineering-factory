"""Layered output contracts: extra JSON Schemas a Skill output must satisfy.

An organization catalog or a project may require more than the Core Skill
`output.schema.json`. Contracts only add constraints: the Core schema is always
checked first, and every applicable contract must also pass. The Runtime checks
them when a phase completes, so conformance is observed, not declared.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .engineering import EngineeringContextError, _resolve_catalogs


def _schema(path: Path, root: Path, owner: str, reference: str) -> dict[str, Any]:
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise EngineeringContextError(f"{owner} output contract escapes its root: {reference}")
    if not resolved.is_file():
        raise EngineeringContextError(f"{owner} output contract is missing: {reference}")
    try:
        schema = json.loads(resolved.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
    except Exception as exc:
        raise EngineeringContextError(f"{owner} output contract is not a valid JSON Schema: {reference}: {exc}") from exc
    return schema


def _declared(factory: Path, project_root: Path, project: dict[str, Any]) -> list[dict[str, Any]]:
    engineering = project.get("engineering", {})
    declared = []
    for catalog in _resolve_catalogs(factory, engineering.get("organizationCatalogs", ["factory-default@1.0.0"])):
        identifier = catalog["metadata"]["id"]
        for item in catalog.get("outputContracts", []):
            declared.append({"source": f"organization:{identifier}", "skill": item["skill"], "reference": item["schema"],
                             "root": factory / "organization", "path": factory / "organization" / item["schema"]})
    for item in engineering.get("outputContracts", []):
        declared.append({"source": "project", "skill": item["skill"], "reference": item["schema"],
                         "root": project_root, "path": project_root / item["schema"]})
    return declared


def resolve_output_contracts(factory: Path, project_root: Path, project: dict[str, Any], skill_id: str) -> list[dict[str, Any]]:
    contracts = []
    for item in _declared(factory, project_root, project):
        if item["skill"] != skill_id:
            continue
        schema = _schema(item["path"], item["root"], item["source"], item["reference"])
        content = item["path"].read_bytes()
        contracts.append({"source": item["source"], "skill": skill_id, "schema": str(item["path"].resolve()),
                          "sha256": hashlib.sha256(content).hexdigest(), "_schema": schema})
    return contracts


def public(contracts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{key: value for key, value in item.items() if not key.startswith("_")} for item in contracts]


def contract_errors(contracts: list[dict[str, Any]], output: dict[str, Any]) -> list[str]:
    errors = []
    for contract in contracts:
        for error in sorted(Draft202012Validator(contract["_schema"]).iter_errors(output), key=lambda item: list(item.path)):
            location = ".".join(map(str, error.path)) or "root"
            errors.append(f"{contract['source']}: {location}: {error.message}")
    return errors


def validate_output_contracts(factory: Path, project_root: Path, project: dict[str, Any], skills: set[str]) -> list[str]:
    try:
        declared = _declared(factory, project_root, project)
    except EngineeringContextError as exc:
        return [str(exc)]
    errors = [f"repository {repository['id']}: outputContracts are only supported at project level"
              for repository in project.get("repositories", []) if repository.get("engineering", {}).get("outputContracts")]
    for item in declared:
        if item["skill"] not in skills:
            errors.append(f"{item['source']}: output contract targets unknown skill {item['skill']}")
            continue
        try:
            _schema(item["path"], item["root"], item["source"], item["reference"])
        except EngineeringContextError as exc:
            errors.append(str(exc))
    return errors
