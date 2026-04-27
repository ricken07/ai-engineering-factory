from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any

RISK = {name: rank for rank, name in enumerate(("unknown", "low", "medium", "high", "critical"))}
AUTONOMY = {f"L{i}": i for i in range(5)}

@dataclass
class PolicyDecision:
    effectiveRisk: str
    requestedAutonomy: str
    authorizedAutonomy: str
    allowedActions: list[str]
    deniedActions: list[str]
    requiredGates: list[str]
    reasons: list[dict[str, Any]]
    def as_dict(self) -> dict[str, Any]: return asdict(self)

def resolve_policy(requested: str, constraints: list[dict[str, Any]]) -> PolicyDecision:
    if requested not in AUTONOMY: raise ValueError(f"invalid autonomy: {requested}")
    risk, maximum = "unknown", requested
    allowed: set[str] = set(); denied: set[str] = set(); gates: set[str] = set(); reasons = []
    for constraint in constraints:
        source = constraint.get("source", "unknown")
        candidate = constraint.get("risk", "unknown")
        if candidate not in RISK: raise ValueError(f"invalid risk: {candidate}")
        if RISK[candidate] > RISK[risk]: risk = candidate
        limit = constraint.get("maximumAutonomy", requested)
        if limit not in AUTONOMY: raise ValueError(f"invalid autonomy: {limit}")
        if AUTONOMY[limit] < AUTONOMY[maximum]: maximum = limit
        allowed.update(constraint.get("allowedActions", [])); denied.update(constraint.get("deniedActions", []))
        gates.update(constraint.get("requiredGates", []))
        reasons.append({"source": source, "risk": candidate, "maximumAutonomy": limit})
    allowed -= denied
    return PolicyDecision(risk, requested, maximum, sorted(allowed), sorted(denied), sorted(gates), reasons)
