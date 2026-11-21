"""Bound plan: a task plan fixed before the execution starts.

A team may prepare and review the plan of a task before any agent runs, for
example to compare executions that must follow the same plan. The execution is
then started with that plan bound: the Runtime copies the plan and its
verification specification unchanged into the execution directory, records
their SHA-256, and performs the `create-plan` phase itself. The planning
artifact only references the bound files and copies the acceptance criteria of
the verification specification verbatim, so no agent writes another plan.

The verification specification may also list `commands`, each
`{id, command: [argv...], repository?, cwd?}`. The Runtime runs them during
`validate-change` with the profile commands, so the governed execution checks
at least what the bound verification asks for; their results are evidence
`<repository>:bound-verification:<id>:exit-<code>`.
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


def _specification(verification: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(verification.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, yaml.YAMLError) as error:
        raise ValueError(f"bound verification {verification.name} is not YAML: {error}") from error
    if not isinstance(data, dict):
        raise ValueError(f"bound verification {verification.name} must be a YAML mapping")
    return data


def _criteria(verification: Path) -> list[Any] | None:
    return _specification(verification).get("acceptanceCriteria")


def verification_commands(verification: Path) -> list[dict[str, Any]]:
    """The commands of a bound verification, checked: unique ids, argv arrays, relative working directories."""
    commands = _specification(verification).get("commands")
    if commands is None:
        return []
    if not isinstance(commands, list):
        raise ValueError(f"bound verification {verification.name}: commands must be a list")
    seen: set[str] = set()
    for index, item in enumerate(commands):
        where = f"bound verification {verification.name}: commands[{index}]"
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not item["id"].strip():
            raise ValueError(f"{where} needs an id")
        if item["id"] in seen:
            raise ValueError(f"{where}: duplicate id {item['id']}")
        seen.add(item["id"])
        argv = item.get("command")
        if not isinstance(argv, list) or not argv or not all(isinstance(value, str) and value for value in argv):
            raise ValueError(f"{where}: command must be a non-empty argv array")
        cwd = item.get("cwd", ".")
        if not isinstance(cwd, str) or Path(cwd).is_absolute() or ".." in Path(cwd).parts:
            raise ValueError(f"{where}: cwd must be a relative path inside the repository")
        if "repository" in item and not isinstance(item["repository"], str):
            raise ValueError(f"{where}: repository must be a repository id")
    return commands


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
    if verification is not None:
        verification_commands(verification)
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


def bind(root: Path, plan: Path, verification: Path | None, at: str,
         expected: dict[str, str | None] | None = None) -> dict[str, Any]:
    """Copies the bound files byte for byte into the execution directory.

    `expected` carries the SHA-256 of the frozen files as the treatment freeze
    recorded them. A difference is not refused here: it is what the plan gate
    comparator reports, so that the human decision rests on it."""
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
        if (expected or {}).get(role):
            record[role]["expectedSha256"] = expected[role]
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


def plan_gate_evidence(root: Path, record: dict[str, Any]) -> dict[str, Any]:
    """Comparator inputs and outcomes for the plan gate of an execution with a bound plan.

    For each bound file:
    - `frozen`: the hash the treatment freeze expects against the hash bound
      at start (`unavailable` when no expected hash was given);
    - `integrity`: the hash bound at start against the file as it is now;
    - `planning-reference`: the hash bound at start against the hash the
      planning artifact references.
    The outcome is `mismatch` when any check differs, `match` when every check
    holds, and `incomplete` otherwise."""
    planning_path = root / "planning.yaml"
    planning = yaml.safe_load(planning_path.read_text(encoding="utf-8")) if planning_path.is_file() else {}
    referenced = ((planning or {}).get("details") or {}).get("binding") or {}
    checks = []
    for role in ("plan", "verification"):
        bound = record.get(role)
        if bound is None:
            continue
        path = root / bound["artifact"]
        current = _sha256(path) if path.is_file() else None
        pairs = (("frozen", bound.get("expectedSha256"), bound["sha256"]),
                 ("integrity", bound["sha256"], current),
                 ("planning-reference", bound["sha256"], (referenced.get(role) or {}).get("sha256")))
        for check, expected_value, observed in pairs:
            outcome = "unavailable" if expected_value is None or observed is None else \
                ("match" if expected_value == observed else "mismatch")
            checks.append({"item": f"{role}:{check}", "artifact": bound["artifact"],
                           "expected": expected_value, "observed": observed, "outcome": outcome})
    outcomes = {check["outcome"] for check in checks}
    overall = "mismatch" if "mismatch" in outcomes else ("match" if outcomes == {"match"} else "incomplete")
    return {"comparator": "bound-plan-hashes", "checks": checks, "outcome": overall}
