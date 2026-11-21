"""Comparator evidence for human gate decisions.

A deterministic gate rule says which recorded facts a human checks and which
outcome leads to which decision. The Runtime computes those facts itself, so
the approver and anyone auditing the decision see the same inputs, each with
its expected value, observed value and outcome:

| Gate | Comparator | What it compares |
|---|---|---|
| plan gate, bound plan | `bound-plan-hashes` | frozen, bound, current and referenced hashes (aief.plan_binding) |
| plan gate, no bound plan | `plan-criteria` | acceptance criteria of the planning artifact |
| `before-implementation` | `governed-plan` | integrity of the governed plan and policy decision, enforceable points, approved plan |
| `apply-proposal` | `proposal` | patch integrity, unchanged workspace, patches that still apply |
| `before-commit`, `before-submission`, submission gate | `submission-evidence` | submission evidence gaps and required enforcement |

A check is `match`, `mismatch` or `unavailable`; the comparator outcome is
`mismatch` when any check differs, `match` when every check holds, and
`incomplete` otherwise. The Runtime records the evidence with the decision;
it does not decide in the human's place.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import yaml

from .enforcement import required_enforcement_satisfied
from .evidence import acceptance_criteria_gaps, submission_evidence_gaps
from .governance import _fingerprint

SUBMISSION_GATES = {"before-commit", "before-submission", "submission-gate"}


def check(item: str, expected: Any, observed: Any, artifact: str | None = None) -> dict[str, Any]:
    outcome = "unavailable" if expected is None or observed is None else ("match" if expected == observed else "mismatch")
    result = {"item": item, "expected": _text(expected), "observed": _text(observed), "outcome": outcome}
    if artifact:
        result["artifact"] = artifact
    return result


def _text(value: Any) -> str | None:
    return None if value is None else (value if isinstance(value, str) else yaml.safe_dump(value, default_flow_style=True).strip())


def result(comparator: str, checks: list[dict[str, Any]]) -> dict[str, Any]:
    outcomes = {item["outcome"] for item in checks}
    overall = "mismatch" if "mismatch" in outcomes else ("match" if outcomes == {"match"} else "incomplete")
    return {"comparator": comparator, "checks": checks, "outcome": overall}


def _load(path: Path) -> dict[str, Any] | None:
    return yaml.safe_load(path.read_text(encoding="utf-8")) if path.is_file() else None


def plan_criteria(root: Path) -> dict[str, Any]:
    planning = _load(root / "planning.yaml")
    if planning is None:
        return result("plan-criteria", [check("planning", "planning.yaml", None)])
    gaps = acceptance_criteria_gaps(planning.get("details", {}))
    return result("plan-criteria", [check("acceptance-criteria", "no gap", "; ".join(gaps) or "no gap", "planning.yaml")])


def governed_plan(root: Path, execution: dict[str, Any], bound_plan: dict[str, Any] | None) -> dict[str, Any]:
    reproducibility = execution.get("reproducibility", {})
    checks = []
    name = execution.get("governedExecutionPlan")
    plan = _load(root / name) if name else None
    if plan is None:
        checks.append(check("governed-plan:present", name or "governed-execution-plan", None))
    else:
        body = {key: value for key, value in plan.items() if key != "fingerprint"}
        checks.append(check("governed-plan:integrity", plan.get("fingerprint"), _fingerprint(body), name))
        checks.append(check("governed-plan:recorded", reproducibility.get("governedExecutionPlanFingerprint", {}).get("value"),
                            plan.get("fingerprint"), name))
        blocked = [point.get("action") for point in plan.get("enforcementPoints", [])
                   if not point.get("status", {}).get("enforceable", False)]
        checks.append(check("enforcement-points:enforceable", "all", "all" if not blocked else ", ".join(map(str, blocked)), name))
    decision_name = execution.get("policyDecision")
    decision = _load(root / decision_name) if decision_name else None
    if decision is not None:
        from .evidence import fingerprint
        checks.append(check("policy-decision:recorded", reproducibility.get("policyFingerprint", {}).get("value"),
                            fingerprint(decision), decision_name))
    planning_phase = next((phase for phase in execution.get("phases", []) if phase.get("skill") == "create-plan"), None)
    if planning_phase is not None:
        checks.append(check("plan:approved", "completed", planning_phase.get("status")))
    if bound_plan is not None:
        checks.append(check("bound-plan:hashes", "match", bound_plan["outcome"]))
    return result("governed-plan", checks)


def proposal(root: Path, execution: dict[str, Any], changed_roots: Callable[[], list[str]],
             patches_apply: Callable[[], str | None]) -> dict[str, Any]:
    """`changed_roots` lists workspace roots changed since the proposal; `patches_apply` returns an error or None."""
    import hashlib
    data = execution.get("proposal") or {}
    if data.get("status") != "proposed":
        return result("proposal", [check("proposal:status", "proposed", data.get("status"))])
    checks = []
    for patch in data.get("patches", []):
        path = root / patch["path"]
        current = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        checks.append(check(f"patch:{patch['path']}:integrity", patch.get("sha256"), current, patch["path"]))
    changed = changed_roots()
    checks.append(check("workspace:unchanged", "none", ", ".join(changed) if changed else "none"))
    error = patches_apply()
    checks.append(check("patches:apply", "applies", error or "applies"))
    return result("proposal", checks)


def submission(root: Path, execution: dict[str, Any]) -> dict[str, Any]:
    gaps = submission_evidence_gaps(root)
    checks = [check("submission-evidence", "no gap", gap, "execution.yaml") for gap in gaps] or \
        [check("submission-evidence", "no gap", "no gap", "execution.yaml")]
    points = [_load(root / name) for name in execution.get("enforcementPoints", [])]
    failing = [str(point.get("action")) for point in points if point and not required_enforcement_satisfied(point)]
    checks.append(check("required-enforcement", "proven", ", ".join(failing) if failing else "proven"))
    return result("submission-evidence", checks)
