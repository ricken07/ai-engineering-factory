"""Deterministic execution-control artifacts; no agent/provider dependency."""
from __future__ import annotations
import hashlib
import json
from typing import Any


def _fingerprint(value: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def enforcement_points(decision: dict[str, Any]) -> list[dict[str, Any]]:
    points = []
    for action in decision["deniedActions"]:
        points.append({"id": f"deny-{action}", "action": action, "decision": "denied",
                       "mechanism": {"type":"runtime", "capability":"action-authorization"},
                       "status": {"enforceable": True}})
    for gate in decision["requiredGates"]:
        points.append({"id": f"gate-{gate}", "action": gate, "decision": "required-gate",
                       "mechanism": {"type":"runtime", "capability":"phase-gate"},
                       "status": {"enforceable": True}})
    return points


def governed_execution_plan(api_version: str, execution: dict[str, Any], decision: dict[str, Any], policy_ref: str,
                            context_fingerprints: list[str] | None = None) -> dict[str, Any]:
    body = {"apiVersion":api_version, "kind":"GovernedExecutionPlan",
            "metadata":{"id":f"plan-{execution['metadata']['id']}"}, "task":execution["task"],
            "execution":execution["metadata"]["id"], "workflow":execution["workflow"],
            "contextFingerprints":sorted(context_fingerprints or []),
            "risk":{"level":decision["effectiveRisk"], "reasons":decision.get("reasons",[])},
            "autonomy":{"requested":decision["requestedAutonomy"], "authorized":decision["authorizedAutonomy"]},
            "allowedActions":decision["allowedActions"], "deniedActions":decision["deniedActions"],
            "requiredGates":decision["requiredGates"], "repositories":decision["observations"]["repositories"],
            "scope":decision["observations"], "policyDecisionRef":policy_ref,
            "enforcementPoints":enforcement_points(decision)}
    body["fingerprint"] = _fingerprint(body)
    return body


def assert_action_authorized(plan: dict[str, Any], action: str) -> None:
    if action in plan.get("deniedActions", []):
        raise PermissionError(f"action is denied by governed execution plan: {action}")
    for point in plan.get("enforcementPoints", []):
        if point["action"] == action and not point["status"].get("enforceable", False):
            raise PermissionError(f"required enforcement is unavailable: {action}")
