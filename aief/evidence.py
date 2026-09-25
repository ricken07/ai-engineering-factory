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
    matrix = validation.get("details", {}).get("evidenceMatrix")
    matrix_ids: set[Any] = set()
    if not isinstance(matrix, list) or not matrix:
        gaps.append("validation.details.evidenceMatrix is missing or empty")
    else:
        matrix_ids = {item.get("id") for item in matrix if isinstance(item, dict)}
        for index, item in enumerate(matrix):
            if not isinstance(item, dict) or item.get("status") != "verified":
                gaps.append(f"evidence matrix item {index} is not verified")
            elif not item.get("evidence"):
                gaps.append(f"evidence matrix item {index} has no evidence")
    results = validation.get("details", {}).get("results", [])
    if not isinstance(results, list) or not results:
        gaps.append("validation.details.results is missing or empty")
    elif any(not isinstance(item, dict) or item.get("exitCode") != 0 for item in results):
        gaps.append("validation contains a failed command")
    criteria = plan.get("details", {}).get("acceptanceCriteria", [])
    missing_criteria = [item.get("id", str(index)) for index, item in enumerate(criteria) if isinstance(item, dict) and item.get("id") not in matrix_ids]
    if missing_criteria:
        gaps.append("evidence matrix does not cover: " + ", ".join(missing_criteria))
    review_details = review.get("details", {})
    execution_path = execution_root / "execution.yaml"
    execution = load_yaml(execution_path) if execution_path.is_file() else {}
    actors = execution.get("actors", {})
    required = execution.get("review", {}).get("independentRequired", True)
    independence = review_independence(actors.get("producer"), actors.get("reviewer"), required=required)
    if not independent_review_satisfied(independence, required):
        gaps.append(f"review independence is {independence}; INDEPENDENT is required")
    if review_details.get("decision") != "approved":
        gaps.append("review.details.decision must be approved")
    if review_details.get("blockingFindings"):
        gaps.append("review contains blocking findings")
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
