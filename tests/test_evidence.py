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
            "reviewer": trusted_session_actor("review-2", handoffFrom="implementation-1"),
        },
        "review": {"independentRequired": True},
    })
    assert submission_evidence_gaps(tmp_path) == []


def test_review_matrix_must_cite_runtime_observed_evidence(tmp_path: Path):
    write(tmp_path, "planning.yaml", {"details": {"acceptanceCriteria": [{"id": "AC-1", "statement": "a"}, {"id": "AC-2", "statement": "b"}]}})
    write(tmp_path, "validation.yaml", {"details": {"results": [
        {"repository": "app", "profile": "maven", "operation": "test", "exitCode": 0}], "evidenceMatrix": []}})
    write(tmp_path, "execution.yaml", {
        "actors": {"producer": trusted_session_actor("implementation-1"),
                   "reviewer": trusted_session_actor("review-2", handoffFrom="implementation-1")},
        "review": {"independentRequired": True}})
    review = {"independent": True, "decision": "approved", "blockingFindings": [], "evidenceMatrix": [
        {"id": "AC-1", "status": "verified", "evidence": ["app:maven:test:exit-0"]},
        {"id": "AC-2", "status": "verified", "evidence": ["agent says tests pass"]}]}
    write(tmp_path, "review.yaml", {"details": review})
    assert submission_evidence_gaps(tmp_path) == [
        "evidence matrix item AC-2 cites evidence the Runtime did not observe: agent says tests pass"]
    review["evidenceMatrix"][1]["evidence"] = ["review:diff limited to the dev profile document"]
    write(tmp_path, "review.yaml", {"details": review})
    assert submission_evidence_gaps(tmp_path) == []


def test_submitting_plan_declares_acceptance_criteria():
    from aief.evidence import acceptance_criteria_gaps
    assert acceptance_criteria_gaps({})[0].startswith("planning.details.acceptanceCriteria is missing")
    assert acceptance_criteria_gaps({"acceptanceCriteria": [{"id": "AC-1", "statement": "s"}, {"id": "AC-1", "statement": "t"}]}) == ["acceptance criterion ids must be unique"]
    assert acceptance_criteria_gaps({"acceptanceCriteria": [{"id": "AC-1", "statement": "s"}]}) == []
