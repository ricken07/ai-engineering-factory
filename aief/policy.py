from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any
from pathlib import Path
import yaml

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


def _contains(condition: Any, values: set[str]) -> bool:
    return bool(values.intersection(condition.get("containsAny", []))) if isinstance(condition, dict) else False


def evaluate_runtime_policy(factory: Path, project: dict[str, Any], task: dict[str, Any], observations: dict[str, Any]) -> dict[str, Any]:
    """Evaluate risk, autonomy, permissions and gates with most-restrictive-wins semantics."""
    classification=task.get("classification",{})
    domains=set(classification.get("domains",[])) | set(observations.get("domains",[]))
    change_types=set(classification.get("changeTypes",[])) | set(observations.get("changeTypes",[]))
    repositories=list(dict.fromkeys([*task.get("scope",{}).get("repositories",[]),*observations.get("repositories",[])]))
    supplied=observations.get("risk") or classification.get("risk","unknown")
    matched: list[str]=[]; risks=[supplied,classification.get("risk","unknown")]
    policy=yaml.safe_load((factory/"core/policies/risk-policy.yaml").read_text(encoding="utf-8"))
    for rule in policy["rules"]:
        when=rule.get("when",{}); applies=True
        if "domains" in when: applies=applies and _contains(when["domains"],domains)
        if "changeTypes" in when:
            condition=when["changeTypes"]
            if "containsAny" in condition: applies=applies and bool(change_types.intersection(condition["containsAny"]))
            if "containsOnly" in condition: applies=applies and bool(change_types) and change_types <= set(condition["containsOnly"])
        if "impactedRepositories" in when: applies=applies and len(repositories) > when["impactedRepositories"].get("greaterThan",10**9)
        if applies:
            effect=rule["effect"]; candidate=effect.get("risk") or effect.get("riskAtLeast")
            if candidate: risks.append(candidate); matched.append(rule["id"])
    effective=max(risks,key=lambda value:RISK[value])
    requested=task.get("autonomy",{}).get("requested") or project.get("autonomy",{}).get("default","L0")
    maximum=project.get("autonomy",{}).get("maximum",requested)
    risk_limit={"unknown":requested,"low":"L4","medium":"L3","high":"L2","critical":"L1"}[effective]
    authorized=min((requested,maximum,risk_limit),key=lambda value:AUTONOMY[value])
    autonomy_policy=yaml.safe_load((factory/"core/policies/autonomy-policy.yaml").read_text(encoding="utf-8"))
    allowed: set[str]=set()
    for rule in autonomy_policy["rules"]:
        if rule.get("when",{}).get("authorizedAutonomy") == authorized:
            allowed.update(rule["effect"].get("allow",[])); matched.append(rule["id"])
    all_actions={action for rule in autonomy_policy["rules"] for action in rule.get("effect",{}).get("allow",[])}
    gate_policy=yaml.safe_load((factory/"core/policies/human-approval-policy.yaml").read_text(encoding="utf-8"))
    gates: set[str]=set()
    for rule in gate_policy["rules"]:
        when=rule.get("when",{})
        if when.get("risk") == effective:
            gates.update(rule["effect"].get("requireApproval",[])); matched.append(rule["id"])
    return {"effectiveRisk":effective,"requestedAutonomy":requested,"authorizedAutonomy":authorized,
            "allowedActions":sorted(allowed),"deniedActions":sorted(all_actions-allowed),"requiredGates":sorted(gates),
            "matchedRules":sorted(set(matched)),"observations":{"repositories":repositories,"domains":sorted(domains),"changeTypes":sorted(change_types)},
            "reasons":[f"effective risk is {effective}",f"authorized autonomy is {authorized}"]}
