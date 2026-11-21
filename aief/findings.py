"""Human decisions on the blocking findings of an independent review.

A review is produced by an agent: its findings are evidence for the human,
not control authority (reference model, invariants 5 and 12). The human may
decide that a blocking finding does not block the change. The decision is
explicit, justified, made through an OBSERVED human channel, bound to the exact
review it answers (by the review artifact's SHA-256) and kept as evidence.
Without such a decision a blocking finding keeps blocking.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .yamlio import load_yaml

WAIVED = "not-blocking"


def review_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def blocking_findings(path: Path) -> list[Any]:
    review = load_yaml(path) if path.is_file() else {}
    return list((review.get("details") or {}).get("blockingFindings") or [])


def waived(execution: dict[str, Any], sha: str) -> set[int]:
    """1-based numbers of the findings of that review the human waived."""
    return {item["finding"] for item in execution.get("findingDecisions", [])
            if item.get("reviewSha256") == sha and item.get("decision") == WAIVED}


def unresolved(execution: dict[str, Any], path: Path) -> list[int]:
    findings = blocking_findings(path)
    if not findings:
        return []
    done = waived(execution, review_sha256(path))
    return [number for number in range(1, len(findings) + 1) if number not in done]


def label(finding: Any) -> str:
    if isinstance(finding, dict):
        parts = [str(finding[key]) for key in ("severity", "criterion") if finding.get(key)]
        location = f" {finding['location']}" if finding.get("location") else ""
        return (" ".join(parts) or "finding") + location
    return str(finding)[:120]
