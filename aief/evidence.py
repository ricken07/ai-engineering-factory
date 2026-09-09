from __future__ import annotations

from pathlib import Path
from typing import Any
import subprocess
import hashlib
import json

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
    if not isinstance(review_details.get("independent"), bool) or not review_details["independent"]:
        gaps.append("review.details.independent must be true")
    if not review_details.get("reviewerSession") or not review_details.get("implementationSession"):
        gaps.append("reviewerSession and implementationSession are required")
    elif review_details["reviewerSession"] == review_details["implementationSession"]:
        gaps.append("reviewerSession must differ from implementationSession")
    if review_details.get("decision") != "approved":
        gaps.append("review.details.decision must be approved")
    if review_details.get("blockingFindings"):
        gaps.append("review contains blocking findings")
    if not criteria:
        gaps.append("planning.details.acceptanceCriteria is missing")
    return gaps


def build_evidence_bundle(factory: Path, execution_root: Path, execution: dict[str, Any]) -> dict[str, Any]:
    """Create an audit artifact from persisted evidence only; never infer agent facts."""
    def read(name: str) -> dict[str, Any]:
        path = execution_root / name
        return load_yaml(path) if path.is_file() else {}
    policy = read(execution.get("policyDecision", ""))
    plan = read(execution.get("governedExecutionPlan", ""))
    validation, review = read("validation.yaml"), read("review.yaml")
    body = {"apiVersion":"aief.dev/v1alpha1", "kind":"EvidenceBundle",
            "metadata":{"id":f"evidence-{execution['metadata']['id']}"}, "task":execution["task"],
            "execution":execution["metadata"]["id"],
            "inputs":{"workflow":execution["workflow"],"contextFingerprints":plan.get("contextFingerprints",[])},
            "control":{"policyDecision":execution.get("policyDecision"),"governedExecutionPlan":execution.get("governedExecutionPlan"),"risk":execution.get("risk"),"enforcementPoints":plan.get("enforcementPoints",[])},
            "executionEvidence":{"producer":execution.get("roles",{}).get("producer"),"revision":validation.get("details",{}).get("commits",{})},
            "verification":{"validations":validation.get("details",{}).get("results",[]),"expected":validation.get("details",{}).get("validationPlan",[]),"verifier":execution.get("roles",{}).get("verifier")},
            "review":{"reviewer":execution.get("roles",{}).get("reviewer"),"result":review.get("details",{}).get("decision")},
            "humanDecisions":[], "outputs":{"artifacts":execution.get("artifacts",[])}}
    body["integrity"]={"fingerprint":hashlib.sha256(json.dumps(body,sort_keys=True,separators=(",",":")).encode()).hexdigest()}
    return body


def experimental_metrics(execution_root: Path, execution: dict[str, Any]) -> dict[str, Any]:
    """Structured observations with explicit unavailable values, never estimates."""
    validation = load_yaml(execution_root / "validation.yaml") if (execution_root / "validation.yaml").is_file() else {}
    results = validation.get("details", {}).get("results", [])
    return {"taskId":execution["task"], "executionId":execution["metadata"]["id"],
            "metrics":{"validationCount":{"value":len(results),"availability":"observed"},
                       "validationFailures":{"value":sum(item.get("exitCode") != 0 for item in results if isinstance(item,dict)),"availability":"observed"},
                       "gateCount":{"value":len(execution.get("policyGates",[])),"availability":"observed"},
                       "evidenceCompleteness":{"value":not submission_evidence_gaps(execution_root),"availability":"observed"},
                       "duration":{"value":None,"availability":"unavailable"},"agentDuration":{"value":None,"availability":"unavailable"},
                       "runtimeDuration":{"value":None,"availability":"unavailable"},"tokenUsage":{"value":None,"availability":"unavailable"},
                       "modelCost":{"value":None,"availability":"unavailable"},"toolCalls":{"value":None,"availability":"unavailable"},"agentTurns":{"value":None,"availability":"unavailable"}}}
