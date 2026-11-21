from __future__ import annotations

from pathlib import Path
from typing import Any
from hashlib import sha256
import json
import subprocess
import yaml

from .identity import independent_review_satisfied, review_independence
from .yamlio import load_yaml


def git_sha(path: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=path,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"unable to resolve Git commit for {path}: {result.stderr.strip()}")
    return result.stdout.strip()


def fingerprint(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"


def file_fingerprint(path: Path) -> str:
    return f"sha256:{sha256(path.read_bytes()).hexdigest()}"


def acceptance_criteria_gaps(plan_details: dict[str, Any]) -> list[str]:
    """A plan that leads to submission declares the criteria it must prove."""
    criteria = plan_details.get("acceptanceCriteria")
    if not isinstance(criteria, list) or not criteria:
        return ["planning.details.acceptanceCriteria is missing: list each criterion as {id, statement}"]
    gaps = []
    ids = [item.get("id") for item in criteria if isinstance(item, dict)]
    if len(ids) != len(criteria) or not all(isinstance(item, str) and item for item in ids):
        gaps.append("each acceptance criterion needs a non-empty id")
    elif len(set(ids)) != len(ids):
        gaps.append("acceptance criterion ids must be unique")
    if any(not isinstance(item, dict) or not item.get("statement") for item in criteria):
        gaps.append("each acceptance criterion needs a statement")
    return gaps


def evidence_matrix_gaps(criteria: list[Any], matrix: Any, observed: set[str] | None,
                         accepted: set[str] | None = None) -> list[str]:
    """Coverage of the acceptance criteria by a matrix.

    With `observed`, each evidence entry must be a validation result the
    Runtime observed, or an explicit reviewer observation (`review:...`).
    `accepted` lists criteria the human accepted although the reviewer did
    not mark them verified (see aief.findings.accepted_criteria)."""
    if not isinstance(matrix, list) or not matrix:
        return ["evidenceMatrix is missing or empty"]
    gaps = []
    for index, item in enumerate(matrix):
        if isinstance(item, dict) and item.get("status") != "verified" and item.get("id") in (accepted or set()):
            continue
        if not isinstance(item, dict) or item.get("status") != "verified":
            gaps.append(f"evidence matrix item {item.get('id', index) if isinstance(item, dict) else index} is not verified")
        elif not item.get("evidence"):
            gaps.append(f"evidence matrix item {index} has no evidence")
        elif observed is not None:
            unknown = [entry for entry in item["evidence"] if entry not in observed and not str(entry).startswith("review:")]
            if unknown:
                gaps.append(f"evidence matrix item {item.get('id', index)} cites evidence the Runtime did not observe: {', '.join(map(str, unknown))}")
    covered = {item.get("id") for item in matrix if isinstance(item, dict)}
    missing = [item.get("id", str(index)) for index, item in enumerate(criteria) if isinstance(item, dict) and item.get("id") not in covered]
    if missing:
        gaps.append("evidence matrix does not cover: " + ", ".join(missing))
    return gaps


def observed_validation_evidence(validation: dict[str, Any]) -> set[str]:
    """Evidence ids of a Runtime-written validation report (exit 0 only)."""
    return {f"{item['repository']}:{item['profile']}:{item['operation']}:exit-0"
            for item in validation.get("details", {}).get("results", [])
            if isinstance(item, dict) and item.get("exitCode") == 0 and {"repository", "profile", "operation"} <= set(item)}


def submission_evidence_gaps(execution_root: Path) -> list[str]:
    gaps: list[str] = []
    validation_path = execution_root / "validation.yaml"
    review_path = execution_root / "review.yaml"
    plan_path = execution_root / "planning.yaml"
    if not plan_path.is_file():
        gaps.append("planning.yaml is missing")
    if not validation_path.is_file():
        gaps.append("validation.yaml is missing")
    if not review_path.is_file():
        gaps.append("review.yaml is missing")
    if gaps:
        return gaps

    plan = load_yaml(plan_path)
    validation = load_yaml(validation_path)
    review = load_yaml(review_path)
    criteria = plan.get("details", {}).get("acceptanceCriteria", [])
    # The independent review maps criteria to evidence; a validation-level
    # matrix is accepted for executions recorded before that rule.
    review_matrix = review.get("details", {}).get("evidenceMatrix")
    if review_matrix is not None:
        from .findings import accepted_criteria
        execution_file = execution_root / "execution.yaml"
        accepted = accepted_criteria(load_yaml(execution_file) if execution_file.is_file() else {}, review_path,
                                     [item.get("id") for item in criteria if isinstance(item, dict)])
        gaps += ["review.details." + gap if gap.startswith("evidenceMatrix") else gap
                 for gap in evidence_matrix_gaps(criteria, review_matrix, observed_validation_evidence(validation), accepted)]
    else:
        gaps += ["validation.details." + gap if gap.startswith("evidenceMatrix") else gap
                 for gap in evidence_matrix_gaps(criteria, validation.get("details", {}).get("evidenceMatrix"), None)]
    results = validation.get("details", {}).get("results", [])
    if not isinstance(results, list) or not results:
        gaps.append("validation.details.results is missing or empty")
    elif any(not isinstance(item, dict) or item.get("exitCode") != 0 for item in results):
        gaps.append("validation contains a failed command")
    review_details = review.get("details", {})
    execution_path = execution_root / "execution.yaml"
    execution = load_yaml(execution_path) if execution_path.is_file() else {}
    actors = execution.get("actors", {})
    required = execution.get("review", {}).get("independentRequired", True)
    independence = review_independence(actors.get("producer"), actors.get("reviewer"), required=required)
    if not independent_review_satisfied(independence, required):
        gaps.append(f"review independence is {independence}; INDEPENDENT is required")
    # A blocking finding the human explicitly decided not to block (see
    # aief.findings) no longer blocks; a review with no other reason to
    # withhold approval is then accepted.
    from .findings import unresolved
    blocking = review_details.get("blockingFindings") or []
    remaining = unresolved(execution, execution_root / "review.yaml") if blocking else []
    if review_details.get("decision") != "approved" and not (blocking and not remaining):
        gaps.append("review.details.decision must be approved")
    if remaining:
        gaps.append("review contains blocking findings without a human decision")
    if not criteria:
        gaps.append("planning.details.acceptanceCriteria is missing")
    return gaps


def build_evidence_bundle(execution_root: Path, *, factory: Path | None = None,
                          project_root: Path | None = None) -> dict[str, Any]:
    execution_path = execution_root / "execution.yaml"
    execution = load_yaml(execution_path)
    references: list[dict[str, Any]] = []
    for name in execution.get("artifacts", []):
        path = execution_root / name
        if path.is_file():
            references.append({"type": "artifact", "id": name, "path": name, "fingerprint": file_fingerprint(path)})
    for point in execution.get("enforcementPoints", []):
        path = execution_root / point
        if path.is_file():
            references.append({"type": "enforcement", "id": point, "path": point, "fingerprint": file_fingerprint(path)})
    policy_ref = execution.get("policyDecision")
    plan_ref = execution.get("governedExecutionPlan")
    validation = load_yaml(execution_root / "validation.yaml") if (execution_root / "validation.yaml").is_file() else {}
    review = execution.get("review", {})
    bundle = {
        "apiVersion": execution.get("apiVersion", "aief.dev/v1alpha1"),
        "kind": "EvidenceBundle",
        "metadata": {"id": f"evidence-{execution['metadata']['id']}"},
        "task": execution["task"],
        "execution": execution["metadata"]["id"],
        "references": references,
        "governance": {
            "governedExecutionPlan": plan_ref,
            "policyDecision": policy_ref,
            "enforcementPoints": list(execution.get("enforcementPoints", [])),
        },
        "identity": {"actors": execution.get("actors", {}), "reviewIndependence": review.get("independence", "UNVERIFIED")},
        "verification": {
            "revision": validation.get("details", {}).get("commits", {}),
            "validation": "validation.yaml" if validation else None,
            "findingDecisions": list(execution.get("findingDecisions", [])),
            "integration": execution.get("integration"),
        },
        "gates": execution.get("policyGates", []),
        "metrics": execution.get("metrics", {}),
        "reproducibility": execution.get("reproducibility", {}),
        "finalArtifacts": list(execution.get("artifacts", [])),
    }
    bundle["fingerprint"] = fingerprint(bundle)
    path = execution_root / "evidence-bundle.yaml"
    path.write_text(yaml.safe_dump(bundle, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return bundle


def experimental_metrics(execution_root: Path, execution: dict[str, Any]) -> dict[str, Any]:
    """Legacy evaluation projection plus the authoritative structured timing.

    Lower-case availability values are retained for the existing evaluation
    contract; Runtime timing remains available unchanged under ``timing``.
    """
    validation = load_yaml(execution_root / "validation.yaml") if (execution_root / "validation.yaml").is_file() else {}
    results = validation.get("details", {}).get("results", [])
    return {"taskId":execution["task"], "executionId":execution["metadata"]["id"],
            "timing": execution.get("metrics", {}),
            "metrics":{"validationCount":{"value":len(results),"availability":"observed"},
                       "validationFailures":{"value":sum(item.get("exitCode") != 0 for item in results if isinstance(item,dict)),"availability":"observed"},
                       "gateCount":{"value":len(execution.get("policyGates",[])),"availability":"observed"},
                       "evidenceCompleteness":{"value":not submission_evidence_gaps(execution_root),"availability":"observed"},
                       "duration":{"value":None,"availability":"unavailable"},"agentDuration":{"value":None,"availability":"unavailable"},
                       "runtimeDuration":{"value":None,"availability":"unavailable"},"tokenUsage":{"value":None,"availability":"unavailable"},
                       "modelCost":{"value":None,"availability":"unavailable"},"toolCalls":{"value":None,"availability":"unavailable"},"agentTurns":{"value":None,"availability":"unavailable"}}}
