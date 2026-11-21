"""Human gate protocol: who may decide a gate, by which rule, and how long the gate waits.

The approval channel (aief.approval) establishes that a human decided. The
protocol adds what a controlled use of human gates needs to fix in advance,
for example a study whose runs must all meet the same human rules:

- `approvers`: the approver identities allowed to decide; empty allows any
  human whose decision the Runtime observed;
- `responseLimitMinutes`: how long a gate may hold the execution; past it, the
  gate expires and the execution is cancelled, whatever decision comes later;
- `decisionRule`: the path, relative to the project root, of the document that
  states the rule approvers apply, optionally pinned by `decisionRuleSha256`.
  The Runtime hashes the document when the execution starts, refuses a
  document whose hash differs from the pin, keeps an immutable copy in the
  execution directory and records the rule (path and hash) with every
  decision. It cannot judge whether the human followed the rule; it records
  the comparator evidence the rule is applied to (see `evidence` below).

The protocol is read from `humanGates` in the project configuration and
snapshotted when the execution starts, so a later configuration change does
not alter a running execution. Every gate decision (approved, rejected,
expired) is recorded in `gateDecisions` with its timing, actor and rule.
"""
from __future__ import annotations

import hashlib
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

RULES_DIRECTORY = "gate-rules"

DEFAULT = {"approvers": [], "responseLimitMinutes": None, "decisionRule": None}


def _rule(project_root: Path, configured: dict[str, Any]) -> dict[str, Any] | None:
    reference = configured.get("decisionRule")
    if reference is None:
        if configured.get("decisionRuleSha256"):
            raise ValueError("humanGates.decisionRuleSha256 pins a rule document, but humanGates.decisionRule is not set")
        return None
    path = (project_root / reference).resolve()
    if not path.is_relative_to(project_root.resolve()):
        raise ValueError(f"humanGates.decisionRule must stay inside the project: {reference}")
    if not path.is_file():
        raise FileNotFoundError(f"humanGates.decisionRule document not found: {reference}")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    pinned = configured.get("decisionRuleSha256")
    if pinned and pinned != digest:
        raise ValueError(f"humanGates.decisionRule {reference} does not match decisionRuleSha256 "
                         f"(expected {pinned}, found {digest}): the rule document changed")
    return {"path": str(reference), "sha256": digest}


def from_project(project: dict[str, Any], project_root: Path) -> dict[str, Any]:
    configured = project.get("humanGates") or {}
    return {"approvers": sorted(set(configured.get("approvers") or [])),
            "responseLimitMinutes": configured.get("responseLimitMinutes"),
            "decisionRule": _rule(project_root, configured)}


def keep_rule(root: Path, project_root: Path, protocol: dict[str, Any]) -> str | None:
    """Copies the rule document into the execution directory; the copy is what decisions refer to."""
    rule = protocol.get("decisionRule")
    if not rule:
        return None
    source = project_root / rule["path"]
    target = root / RULES_DIRECTORY / Path(rule["path"]).name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    if hashlib.sha256(target.read_bytes()).hexdigest() != rule["sha256"]:
        raise RuntimeError(f"rule document {rule['path']} changed while the execution started")
    rule["artifact"] = f"{RULES_DIRECTORY}/{target.name}"
    return rule["artifact"]


def of_execution(execution: dict[str, Any]) -> dict[str, Any]:
    """The protocol snapshotted at start; executions created before it have the default."""
    value = execution.get("reproducibility", {}).get("humanGateProtocol", {}).get("value")
    return {**DEFAULT, **value} if isinstance(value, dict) else dict(DEFAULT)


def holding_gates(execution: dict[str, Any]) -> list[dict[str, Any]]:
    """Gates currently holding the execution and waiting for a human decision.

    A cancelled or failed execution waits for nothing: the Runtime cancels it
    without reopening the phase that held it, so its gate is decided or
    closed, never waiting."""
    held = []
    if execution.get("status") in {"cancelled", "failed"}:
        return held
    for phase in execution.get("phases", []):
        timing_record = phase.get("gateTiming") or {}
        if phase.get("status") == "waiting-approval" and "gateTiming" in phase \
                and not timing_record.get("decidedAt") and not timing_record.get("closedAt"):
            timing = phase["gateTiming"].get("timing", phase["gateTiming"])
            held.append({"kind": "phase-gate", "gate": phase["gateTiming"].get("gate", "phase-gate"),
                         "phase": phase["id"], "trigger": f"phase:{phase['id']}", "timing": timing})
    for gate in execution.get("policyGates", []):
        timing = gate.get("timing", {})
        if gate.get("status") == "pending" and timing.get("blockedAt") and not timing.get("decidedAt"):
            held.append({"kind": "policy-gate", "gate": gate["id"], "phase": None,
                         "trigger": gate.get("trigger"), "timing": timing})
    # A completed execution does not wait, but its integration does: the merge
    # gate waits for a human from the moment the Runtime requested the
    # integration, not from the earlier moment the policy required the gate.
    integration = execution.get("integration") or {}
    if integration.get("status") == "awaiting-approval":
        for gate in execution.get("policyGates", []):
            timing = gate.get("timing", {})
            if gate["id"] == integration.get("gate") and gate.get("status") == "pending" and not timing.get("decidedAt") \
                    and gate["id"] not in {item["gate"] for item in held}:
                held.append({"kind": "policy-gate", "gate": gate["id"], "phase": None, "trigger": gate.get("trigger"),
                             "integration": True,
                             "timing": {**timing, "blockedAt": integration.get("requestedAt") or timing.get("blockedAt")
                                        or timing.get("requestedAt")}})
    return held


def deadline(held: dict[str, Any], protocol: dict[str, Any]) -> datetime | None:
    limit = protocol.get("responseLimitMinutes")
    started = held["timing"].get("blockedAt")
    if limit is None or not started:
        return None
    return datetime.fromisoformat(started) + timedelta(minutes=limit)


def decision(held: dict[str, Any], outcome: str, at: str, protocol: dict[str, Any],
             actor: dict[str, Any] | None = None, rationale: str | None = None,
             evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    timing = held["timing"]
    record: dict[str, Any] = {
        "gate": held["gate"], "kind": held["kind"], "decision": outcome, "at": at,
        "requestedAt": timing.get("requestedAt"), "waitStartedAt": timing.get("blockedAt"),
        "decidedAt": timing.get("decidedAt") or timing.get("closedAt") or at,
        "waitDurationMs": timing.get("durationMs"),
        "decisionRule": protocol.get("decisionRule"),
        "responseLimitMinutes": protocol.get("responseLimitMinutes"),
    }
    for key, value in (("phase", held.get("phase")), ("trigger", held.get("trigger")), ("rationale", rationale)):
        if value:
            record[key] = value
    if held.get("integration") and outcome != "expired" and record["waitStartedAt"]:
        # The integration wait does not hold the execution, so no monotonic
        # clock measured it: it is derived from the two recorded instants.
        elapsed = datetime.fromisoformat(record["decidedAt"]) - datetime.fromisoformat(record["waitStartedAt"])
        record["waitDurationMs"] = {"value": max(0, round(elapsed.total_seconds() * 1000)), "availability": "DERIVED"}
    if evidence is not None:
        record["evidence"] = evidence
    if actor is not None:
        record["actor"] = {key: actor[key] for key in ("id", "type", "channel", "assurance") if key in actor}
    return record
