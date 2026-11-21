"""Payload ledger: what the Runtime actually delivered to the agent, phase by phase.

Input fingerprints (context, plan, policy) show which artifacts an execution
started from; they do not show what an agent was given to read. The Runtime
renders that itself: the phase brief (skill contract, bound plan, rework
findings, human decisions, authorized action, task context, practices), the
Core Skill files the brief points to, and the `execution next` output. Each
time it prepares a phase for an agent, the Runtime appends an entry to
`payload-ledger.yaml`:

- every rendered file is snapshotted under `payloads/`, because a phase brief
  is rewritten when the phase runs again after a rework;
- every item carries its SHA-256 and a classification of the information it
  carries, and the phase brief is also hashed section by section, so that a
  comparison between executions can isolate, for instance, review feedback;
- a section the ledger cannot classify is recorded as `unclassified` and
  reported as a gap, never silently accepted.

The ledger records and classifies; comparing ledgers across executions (for
example, checking that two runs received the same task information) belongs
to whoever runs the comparison.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import yaml

LEDGER = "payload-ledger.yaml"
SNAPSHOTS = "payloads"

# Classification of the information an item or brief section carries.
PROCEDURAL = "procedural"            # how to work: contracts, schemas, authorized action
PROJECT_CONTEXT = "project-context"  # persistent project knowledge: repositories, practices
TASK_CONTEXT = "task-context"        # facts about the task itself
TASK_PLAN = "task-plan"              # pointers to a plan and verification bound before the execution
REVIEW_FEEDBACK = "review-feedback"  # findings of a review the change must address
HUMAN_DECISION = "human-decision"    # decisions a human made during the execution
RUNTIME_STATE = "runtime-state"      # command output describing the execution state
UNCLASSIFIED = "unclassified"

_SECTIONS: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r"^# Phase brief: "), "preamble", PROCEDURAL),
    (re.compile(r"^## Skill contract$"), "skill-contract", PROCEDURAL),
    (re.compile(r"^## Bound plan$"), "bound-plan", TASK_PLAN),
    (re.compile(r"^## Rework \d+: "), "rework", REVIEW_FEEDBACK),
    (re.compile(r"^## Human decisions on review findings$"), "human-decisions", HUMAN_DECISION),
    (re.compile(r"^## Authorized action: "), "authorized-action", PROCEDURAL),
    (re.compile(r"^## Repositories$"), "repositories", PROJECT_CONTEXT),
    (re.compile(r"^## Task context$"), "task-context", TASK_CONTEXT),
    (re.compile(r"^## Practices$"), "practices", PROJECT_CONTEXT),
]


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _section(heading: str) -> tuple[str, str] | None:
    return next(((name, kind) for pattern, name, kind in _SECTIONS if pattern.match(heading)), None)


def brief_sections(text: str) -> list[dict[str, Any]]:
    """Splits a rendered phase brief on the headings the brief itself emits and classifies each section.

    Practice contents carry their own Markdown headings; they stay inside the
    section that quotes them. Every heading `render_phase_brief` can emit is
    matched here (tests/test_payload_ledger.py checks it)."""
    sections: list[dict[str, Any]] = []
    current: list[str] = []
    heading: str | None = None

    def close() -> None:
        if heading is None:
            return
        identifier, classification = _section(heading) or (heading.lstrip("# ").strip(), UNCLASSIFIED)
        content = "\n".join(current).encode("utf-8")
        sections.append({"id": identifier, "heading": heading, "classification": classification,
                         "sha256": _sha256(content), "bytes": len(content)})

    for line in text.splitlines():
        if heading is None or _section(line):
            close(); heading = line; current = [line]
        else:
            current.append(line)
    close()
    return sections


def _file_item(kind: str, path: Path, classification: str, bases: dict[str, Path]) -> dict[str, Any]:
    """A delivered file, located relative to the first base (execution, factory, project) that holds it."""
    resolved = path.resolve()
    base, relative = "absolute", str(resolved)
    for name, directory in bases.items():
        try:
            relative = str(resolved.relative_to(directory.resolve())); base = name
            break
        except ValueError:
            continue
    content = resolved.read_bytes()
    return {"kind": kind, "base": base, "path": relative, "sha256": _sha256(content), "bytes": len(content),
            "classification": classification}


def load(root: Path) -> dict[str, Any] | None:
    path = root / LEDGER
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.is_file() else None


def record_phase(root: Path, execution: dict[str, Any], phase: dict[str, Any], skill_contract: dict[str, Any],
                 brief_path: Path, command_output: dict[str, Any], *, factory: Path, project_root: Path,
                 api_version: str, at: str) -> dict[str, Any]:
    """Appends the payload delivered for one phase preparation and returns the entry."""
    ledger = load(root) or {
        "apiVersion": api_version, "kind": "PayloadLedger",
        "metadata": {"id": f"payload-ledger-{execution['metadata']['id']}"},
        "task": execution["task"], "execution": execution["metadata"]["id"],
        "experimentalCondition": execution.get("reproducibility", {}).get("experimentalCondition", {}).get("value"),
        "entries": [],
    }
    sequence = len(ledger["entries"]) + 1
    snapshots = root / SNAPSHOTS
    snapshots.mkdir(exist_ok=True)
    brief_text = brief_path.read_text(encoding="utf-8")
    brief_snapshot = snapshots / f"{sequence:03d}-{brief_path.name}"
    brief_snapshot.write_text(brief_text, encoding="utf-8")
    output_bytes = json.dumps(command_output, indent=2, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    output_snapshot = snapshots / f"{sequence:03d}-execution-next-{phase['id']}.json"
    output_snapshot.write_bytes(output_bytes)

    bases = {"execution": root, "factory": factory, "project": project_root}
    items = [
        {**_file_item("phase-brief", brief_snapshot, PROCEDURAL, bases), "sections": brief_sections(brief_text)},
        _file_item("execution-next-output", output_snapshot, RUNTIME_STATE, bases),
        _file_item("skill-instructions", Path(skill_contract["instructions"]), PROCEDURAL, bases),
        _file_item("skill-manifest", Path(skill_contract["manifest"]), PROCEDURAL, bases),
        _file_item("output-schema", Path(skill_contract["outputSchema"]), PROCEDURAL, bases),
    ]
    items += [_file_item("output-contract", Path(contract["schema"]), PROCEDURAL, bases)
              for contract in skill_contract.get("outputContracts", [])]
    for role in ("plan", "verification"):
        bound = (execution.get("planBinding") or {}).get(role)
        if bound:
            items.append(_file_item(f"bound-{role}", root / bound["artifact"], TASK_PLAN, bases))
    entry = {"sequence": sequence, "phase": phase["id"], "skill": phase["skill"],
             "attempt": (phase.get("rework") or {}).get("number", 0), "at": at, "items": items}
    entry["fingerprint"] = "sha256:" + _sha256(json.dumps(entry, sort_keys=True).encode("utf-8"))
    ledger["entries"].append(entry)
    ledger["fingerprint"] = "sha256:" + _sha256(json.dumps(ledger["entries"], sort_keys=True).encode("utf-8"))
    (root / LEDGER).write_text(yaml.safe_dump(ledger, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return entry


def gaps(root: Path, *, factory: Path, project_root: Path) -> list[str]:
    """Checks a ledger: every snapshot and file still matches its hash, every section is classified."""
    ledger = load(root)
    if ledger is None:
        return []
    problems = []
    expected = "sha256:" + _sha256(json.dumps(ledger["entries"], sort_keys=True).encode("utf-8"))
    if ledger.get("fingerprint") != expected:
        problems.append("ledger fingerprint does not match its entries")
    for entry in ledger["entries"]:
        for item in entry["items"]:
            bases = {"execution": root, "factory": factory, "project": project_root}
            path = bases[item["base"]] / item["path"] if item["base"] in bases else Path(item["path"])
            if not path.is_file():
                problems.append(f"entry {entry['sequence']}: {item['kind']} {item['path']} is missing")
            elif _sha256(path.read_bytes()) != item["sha256"]:
                problems.append(f"entry {entry['sequence']}: {item['kind']} {item['path']} changed after it was delivered")
            for section in item.get("sections", []):
                if section["classification"] == UNCLASSIFIED:
                    problems.append(f"entry {entry['sequence']}: brief section {section['heading']!r} is unclassified")
    return problems
