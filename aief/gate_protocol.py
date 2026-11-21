"""Human gate protocol: who may decide a gate, by which rule, and how long the gate waits.

The approval channel (aief.approval) establishes that a human decided. The
protocol adds what a controlled use of human gates needs to fix in advance,
for example a study whose runs must all meet the same human rules:

- `approvers`: the approver identities allowed to decide; empty allows any
  human whose decision the Runtime observed;
- `responseLimitMinutes`: how long a gate may hold the execution; past it, the
  gate expires and the execution is cancelled, whatever decision comes later;
- `decisionRule`: the reference of the rule approvers apply (a document or an
  identifier). The Runtime records it with every decision; it cannot judge
  whether the human followed it.

The protocol is read from `humanGates` in the project configuration and
snapshotted when the execution starts, so a later configuration change does
not alter a running execution. Every gate decision (approved, rejected,
expired) is recorded in `gateDecisions` with its timing, actor and rule.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

DEFAULT = {"approvers": [], "responseLimitMinutes": None, "decisionRule": None}


def from_project(project: dict[str, Any]) -> dict[str, Any]:
    configured = project.get("humanGates") or {}
    return {"approvers": sorted(set(configured.get("approvers") or [])),
            "responseLimitMinutes": configured.get("responseLimitMinutes"),
            "decisionRule": configured.get("decisionRule")}


def of_execution(execution: dict[str, Any]) -> dict[str, Any]:
    """The protocol snapshotted at start; executions created before it have the default."""
    value = execution.get("reproducibility", {}).get("humanGateProtocol", {}).get("value")
    return {**DEFAULT, **value} if isinstance(value, dict) else dict(DEFAULT)


def holding_gates(execution: dict[str, Any]) -> list[dict[str, Any]]:
    """Gates currently holding the execution and waiting for a human decision."""
    held = []
    for phase in execution.get("phases", []):
        if phase.get("status") == "waiting-approval" and "gateTiming" in phase:
            timing = phase["gateTiming"].get("timing", phase["gateTiming"])
            held.append({"kind": "phase-gate", "gate": phase["gateTiming"].get("gate", "phase-gate"),
                         "phase": phase["id"], "trigger": f"phase:{phase['id']}", "timing": timing})
    for gate in execution.get("policyGates", []):
        timing = gate.get("timing", {})
        if gate.get("status") == "pending" and timing.get("blockedAt") and not timing.get("decidedAt"):
            held.append({"kind": "policy-gate", "gate": gate["id"], "phase": None,
                         "trigger": gate.get("trigger"), "timing": timing})
    return held


def deadline(held: dict[str, Any], protocol: dict[str, Any]) -> datetime | None:
    limit = protocol.get("responseLimitMinutes")
    started = held["timing"].get("blockedAt")
    if limit is None or not started:
        return None
    return datetime.fromisoformat(started) + timedelta(minutes=limit)


def decision(held: dict[str, Any], outcome: str, at: str, protocol: dict[str, Any],
             actor: dict[str, Any] | None = None, rationale: str | None = None) -> dict[str, Any]:
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
    if actor is not None:
        record["actor"] = {key: actor[key] for key in ("id", "type", "channel", "assurance") if key in actor}
    return record
