from __future__ import annotations

from pathlib import Path
from typing import Any
import subprocess

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
