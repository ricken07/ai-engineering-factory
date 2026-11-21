"""Bound plan: a task plan fixed before the execution starts.

A team may prepare and review the plan of a task before any agent runs, for
example to compare executions that must follow the same plan. The execution is
then started with that plan bound: the Runtime copies the plan and its
verification specification unchanged into the execution directory, records
their SHA-256, and performs the `create-plan` phase itself. The planning
artifact only references the bound files and copies the acceptance criteria of
the verification specification verbatim, so no agent writes another plan.
"""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Any

import yaml

from .evidence import acceptance_criteria_gaps

BOUND_DIRECTORY = "bound-plan"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _criteria(verification: Path) -> list[Any] | None:
    try:
        data = yaml.safe_load(verification.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, yaml.YAMLError) as error:
        raise ValueError(f"bound verification {verification.name} is not YAML: {error}") from error
    if not isinstance(data, dict):
        raise ValueError(f"bound verification {verification.name} must be a YAML mapping")
    return data.get("acceptanceCriteria")


def check_binding(plan: Path, verification: Path | None, workflow: dict[str, Any]) -> None:
    """Refuses, before any execution exists, a binding the planning phase could not record."""
    if not any(phase.get("skill") == "create-plan" for phase in workflow["phases"]):
        raise ValueError(f"workflow {workflow['id']} has no create-plan phase: a plan cannot be bound to it")
    for path in (plan, verification):
        if path is not None and not path.is_file():
            raise FileNotFoundError(f"bound plan file not found: {path}")
    if verification is not None and plan.name == verification.name:
        raise ValueError("the bound plan and the bound verification need distinct file names")
    criteria = _criteria(verification) if verification is not None else None
    if any(phase.get("skill") == "submit-change" for phase in workflow["phases"]):
        if verification is None:
            raise ValueError(f"workflow {workflow['id']} ends with submission: bind a verification specification "
                             "that lists acceptanceCriteria as {id, statement}")
        gaps = acceptance_criteria_gaps({"acceptanceCriteria": criteria})
        if gaps:
            raise ValueError(f"bound verification {verification.name}: " + "; ".join(gaps))
    elif criteria is not None:
        gaps = acceptance_criteria_gaps({"acceptanceCriteria": criteria})
        if gaps:
            raise ValueError(f"bound verification {verification.name}: " + "; ".join(gaps))


def bind(root: Path, plan: Path, verification: Path | None, at: str) -> dict[str, Any]:
    """Copies the bound files byte for byte into the execution directory."""
    directory = root / BOUND_DIRECTORY
    directory.mkdir(parents=True, exist_ok=True)
    record: dict[str, Any] = {"boundAt": at}
    for role, source in (("plan", plan), ("verification", verification)):
        if source is None:
            continue
        target = directory / source.name
        shutil.copyfile(source, target)
        if _sha256(target) != _sha256(source):
            raise RuntimeError(f"bound {role} {source.name} changed while it was copied")
        record[role] = {"artifact": f"{BOUND_DIRECTORY}/{source.name}", "sha256": _sha256(target)}
    return record


def verify_binding(root: Path, record: dict[str, Any]) -> None:
    """The bound files are read back from the execution directory; a changed file is refused."""
    for role in ("plan", "verification"):
        item = record.get(role)
        if item is None:
            continue
        path = root / item["artifact"]
        if not path.is_file():
            raise RuntimeError(f"bound {role} {item['artifact']} is missing from the execution directory")
        if _sha256(path) != item["sha256"]:
            raise RuntimeError(f"bound {role} {item['artifact']} changed after it was bound (sha256 mismatch)")


def fingerprints(record: dict[str, Any]) -> list[str]:
    return [f"{record[role]['artifact']}:sha256:{record[role]['sha256']}" for role in ("plan", "verification") if role in record]


def planning_output(root: Path, record: dict[str, Any], planner: dict[str, Any]) -> dict[str, Any]:
    """The create-plan output the Runtime records for a bound plan: references and verbatim criteria only."""
    verify_binding(root, record)
    details: dict[str, Any] = {"skill": "create-plan", "binding": {key: value for key, value in record.items()},
                               "planner": planner}
    if "verification" in record:
        criteria = _criteria(root / record["verification"]["artifact"])
        if criteria is not None:
            details["acceptanceCriteria"] = criteria
    return {
        "summary": f"The plan of this execution is the bound plan {record['plan']['artifact']}; the Runtime recorded it unchanged.",
        "status": "completed",
        "evidence": fingerprints(record),
        "unknowns": [],
        "details": details,
    }


def brief_section(record: dict[str, Any]) -> list[str]:
    lines = ["", "## Bound plan", "",
             "This execution follows a plan bound before it started. Read these files in the execution directory;",
             "they are the plan and the verification of this change. Do not replace or extend the plan: if it cannot",
             "be followed, ask the human.", ""]
    for role in ("plan", "verification"):
        if role in record:
            lines.append(f"- {role.capitalize()}: `{record[role]['artifact']}` (sha256 `{record[role]['sha256']}`)")
    return lines
