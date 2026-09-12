from pathlib import Path

import yaml

from aief.evidence import submission_evidence_gaps
from aief.identity import trusted_session_actor


def write(root: Path, name: str, value: dict) -> None:
    (root / name).write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")


def test_submission_evidence_requires_complete_independent_chain(tmp_path: Path):
    write(tmp_path, "planning.yaml", {"details": {"acceptanceCriteria": [{"id": "AC-1"}]}})
    write(tmp_path, "validation.yaml", {"details": {"results": [{"exitCode": 0}]}})
    write(tmp_path, "review.yaml", {"details": {"independent": False, "decision": "approved"}})
    gaps = submission_evidence_gaps(tmp_path)
    assert "validation.details.evidenceMatrix is missing or empty" in gaps
    assert "review independence is UNVERIFIED; INDEPENDENT is required" in gaps


def test_submission_evidence_accepts_verified_matrix_and_review(tmp_path: Path):
    write(tmp_path, "planning.yaml", {"details": {"acceptanceCriteria": [{"id": "AC-1"}]}})
    write(tmp_path, "validation.yaml", {"details": {
        "results": [{"exitCode": 0}],
        "evidenceMatrix": [{"id": "AC-1", "status": "verified", "evidence": ["EV-1"]}],
    }})
    write(tmp_path, "review.yaml", {"details": {"independent": True, "decision": "approved", "blockingFindings": [], "reviewerSession": "review-2", "implementationSession": "implementation-1"}})
    write(tmp_path, "execution.yaml", {
        "actors": {
            "producer": trusted_session_actor("implementation-1"),
            "reviewer": trusted_session_actor("review-2"),
        },
        "review": {"independentRequired": True},
    })
    assert submission_evidence_gaps(tmp_path) == []
