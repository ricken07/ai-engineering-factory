from __future__ import annotations

from hashlib import sha256
import json
from typing import Any


STATUSES = {"ENFORCED", "ENFORCEABLE", "UNAVAILABLE", "UNVERIFIED"}


def enforcement_point(
    *,
    execution: str,
    action: str,
    decision: str,
    mechanism_type: str,
    capability: str,
    status: str,
    evidence_ref: str | None = None,
    required: bool = False,
) -> dict[str, Any]:
    if status not in STATUSES:
        raise ValueError(f"unknown enforcement assurance status: {status}")
    if status == "ENFORCED" and not evidence_ref:
        raise ValueError("ENFORCED requires evidenceRef")
    identity = json.dumps(
        [execution, action, decision, mechanism_type, capability, status, evidence_ref, required],
        separators=(",", ":"),
    )
    point: dict[str, Any] = {
        "apiVersion": "aief.dev/v1alpha1",
        "kind": "EnforcementPoint",
        "metadata": {"id": f"enforcement-{sha256(identity.encode()).hexdigest()[:16]}"},
        "execution": execution,
        "action": action,
        "decision": decision,
        "mechanism": {"type": mechanism_type, "capability": capability},
        "assurance": {"status": status},
        "required": required,
    }
    if evidence_ref:
        point["evidenceRef"] = evidence_ref
    return point


def required_enforcement_satisfied(point: dict[str, Any]) -> bool:
    return not point.get("required", False) or point.get("assurance", {}).get("status") == "ENFORCED"


def assert_required_enforcement(points: list[dict[str, Any]]) -> None:
    failures = [
        f"{item.get('action')}={item.get('assurance', {}).get('status', 'UNAVAILABLE')}"
        for item in points
        if not required_enforcement_satisfied(item)
    ]
    if failures:
        raise PermissionError("required enforcement is not proven: " + ", ".join(failures))
