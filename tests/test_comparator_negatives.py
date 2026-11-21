"""Negative tests of every gate comparator (human gate protocol, condition HGP-C16).

A human decides a gate from the comparator outcome, so a comparator that
reports `match` on a wrong state would let the decision rule approve it. For
each comparator, a reference state yields `match`; then every check is broken
on its own and must turn that check to `mismatch` (or `unavailable`) and the
comparator outcome to `mismatch` (or `incomplete`). A coverage test fails when
a comparator emits a check that no negative case exercises.
"""
import hashlib
import subprocess
from pathlib import Path
from typing import Callable

import pytest
import yaml

from aief import gate_evidence, plan_binding
from aief.evidence import fingerprint
from aief.governance import _fingerprint
from aief.integration import integration_checks

PLAN = "# Plan\n1. Add greeting().\n"
VERIFICATION = "acceptanceCriteria:\n- {id: AC-1, statement: greeting returns Hello}\n"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def dump(path: Path, data) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=False))


def checks_of(evidence: dict) -> dict:
    return {item["item"]: item for item in evidence["checks"]}


def generic(item: str) -> str:
    """The check kind, without the file, patch, repository or branch it names."""
    parts = item.split(":")
    if parts[0] in {"plan", "verification"}:
        return parts[-1]
    if parts[0] == "patch":
        return "patch:integrity"
    if parts[0] == "submission":
        return item
    if len(parts) >= 3 and parts[1] == "branch":
        return "branch"
    if len(parts) >= 2 and parts[0] not in {"governed-plan", "enforcement-points", "policy-decision", "plan",
                                            "bound-plan", "proposal", "workspace", "patches", "execution",
                                            "integration", "acceptance-criteria", "planning"}:
        return ":".join(parts[1:])
    return item


# --------------------------------------------------------------------------- bound-plan-hashes (plan gate, bound plan)

def bound_plan(tmp_path: Path, mutate: Callable[[Path, dict], None] | None = None) -> dict:
    source = tmp_path / "frozen"; source.mkdir(parents=True)
    (source / "plan.md").write_text(PLAN); (source / "verification.yaml").write_text(VERIFICATION)
    root = tmp_path / "execution"; root.mkdir(parents=True)
    expected = {"plan": sha(PLAN.encode()), "verification": sha(VERIFICATION.encode())}
    record = plan_binding.bind(root, source / "plan.md", source / "verification.yaml", "2026-11-21T00:00:00+00:00", expected)
    dump(root / "planning.yaml", {"details": {"binding": record}})
    if mutate:
        mutate(root, record)
    return plan_binding.plan_gate_evidence(root, record)


def _planning_reference(root: Path, role: str, value) -> None:
    planning = yaml.safe_load((root / "planning.yaml").read_text())
    if value is None:
        planning["details"]["binding"].pop(role)
    else:
        planning["details"]["binding"][role]["sha256"] = value
    dump(root / "planning.yaml", planning)


BOUND_PLAN_CASES = {
    "plan:frozen mismatch": (lambda root, record: record["plan"].update(expectedSha256="0" * 64), "plan:frozen", "mismatch"),
    "plan:frozen unavailable": (lambda root, record: record["plan"].pop("expectedSha256"), "plan:frozen", "unavailable"),
    "verification:frozen mismatch": (lambda root, record: record["verification"].update(expectedSha256="0" * 64),
                                     "verification:frozen", "mismatch"),
    "plan:integrity mismatch": (lambda root, record: (root / "bound-plan" / "plan.md").write_text(PLAN + "3. More.\n"),
                                "plan:integrity", "mismatch"),
    "verification:integrity unavailable": (lambda root, record: (root / "bound-plan" / "verification.yaml").unlink(),
                                           "verification:integrity", "unavailable"),
    "plan:planning-reference mismatch": (lambda root, record: _planning_reference(root, "plan", "1" * 64),
                                         "plan:planning-reference", "mismatch"),
    "verification:planning-reference unavailable": (lambda root, record: _planning_reference(root, "verification", None),
                                                    "verification:planning-reference", "unavailable"),
}


def test_bound_plan_hashes_reference_matches(tmp_path: Path):
    evidence = bound_plan(tmp_path)
    assert evidence["outcome"] == "match", evidence


@pytest.mark.parametrize("case", sorted(BOUND_PLAN_CASES))
def test_bound_plan_hashes_negative(case: str, tmp_path: Path):
    mutate, item, outcome = BOUND_PLAN_CASES[case]
    evidence = bound_plan(tmp_path, mutate)
    assert checks_of(evidence)[item]["outcome"] == outcome
    assert evidence["outcome"] == ("mismatch" if outcome == "mismatch" else "incomplete")


# --------------------------------------------------------------------------- plan-criteria (plan gate, no bound plan)

def test_plan_criteria_reference_and_negatives(tmp_path: Path):
    dump(tmp_path / "planning.yaml", {"details": {"acceptanceCriteria": [{"id": "AC-1", "statement": "s"}]}})
    assert gate_evidence.plan_criteria(tmp_path)["outcome"] == "match"
    dump(tmp_path / "planning.yaml", {"details": {"acceptanceCriteria": [{"id": "AC-1"}]}})
    evidence = gate_evidence.plan_criteria(tmp_path)
    assert evidence["outcome"] == "mismatch" and checks_of(evidence)["acceptance-criteria"]["outcome"] == "mismatch"
    (tmp_path / "planning.yaml").unlink()
    evidence = gate_evidence.plan_criteria(tmp_path)
    assert evidence["outcome"] == "incomplete" and checks_of(evidence)["planning"]["outcome"] == "unavailable"


# --------------------------------------------------------------------------- governed-plan (before-implementation)

def governed(tmp_path: Path, mutate: Callable[[Path, dict, dict], None] | None = None,
             bound: dict | None = None) -> dict:
    root = tmp_path / "execution"; root.mkdir(parents=True)
    body = {"allowedActions": ["modify-local-files"], "enforcementPoints": [{"action": "commit", "status": {"enforceable": True}}]}
    plan = {**body, "fingerprint": _fingerprint(body)}
    decision = {"decision": "allow", "gates": ["before-implementation"]}
    dump(root / "governed-execution-plan-001.yaml", plan); dump(root / "policy-decision-001.yaml", decision)
    execution = {"governedExecutionPlan": "governed-execution-plan-001.yaml", "policyDecision": "policy-decision-001.yaml",
                 "reproducibility": {"governedExecutionPlanFingerprint": {"value": plan["fingerprint"]},
                                     "policyFingerprint": {"value": fingerprint(decision)}},
                 "phases": [{"id": "planning", "skill": "create-plan", "status": "completed"}]}
    if mutate:
        mutate(root, execution, plan)
    return gate_evidence.governed_plan(root, execution, bound)


def _rewrite_plan(root: Path, change: Callable[[dict], None]) -> None:
    path = root / "governed-execution-plan-001.yaml"
    plan = yaml.safe_load(path.read_text()); change(plan); dump(path, plan)


GOVERNED_CASES = {
    "integrity": (lambda root, execution, plan: _rewrite_plan(root, lambda p: p["allowedActions"].append("push")),
                  "governed-plan:integrity", "mismatch"),
    "recorded": (lambda root, execution, plan: execution["reproducibility"]["governedExecutionPlanFingerprint"].update(value="sha256:0"),
                 "governed-plan:recorded", "mismatch"),
    "enforceable": (lambda root, execution, plan: _rewrite_plan(root, lambda p: (
                        p["enforcementPoints"][0]["status"].update(enforceable=False),
                        p.update(fingerprint=_fingerprint({k: v for k, v in p.items() if k != "fingerprint"})))),
                    "enforcement-points:enforceable", "mismatch"),
    "policy-decision": (lambda root, execution, plan: dump(root / "policy-decision-001.yaml", {"decision": "deny"}),
                        "policy-decision:recorded", "mismatch"),
    "plan approved": (lambda root, execution, plan: execution["phases"][0].update(status="waiting-approval"),
                      "plan:approved", "mismatch"),
    "present": (lambda root, execution, plan: (root / "governed-execution-plan-001.yaml").unlink(),
                "governed-plan:present", "unavailable"),
}


def test_governed_plan_reference_matches(tmp_path: Path):
    assert governed(tmp_path)["outcome"] == "match"
    assert governed(tmp_path / "bound", bound={"outcome": "match"})["outcome"] == "match"


@pytest.mark.parametrize("case", sorted(GOVERNED_CASES))
def test_governed_plan_negative(case: str, tmp_path: Path):
    mutate, item, outcome = GOVERNED_CASES[case]
    evidence = governed(tmp_path, mutate)
    assert checks_of(evidence)[item]["outcome"] == outcome, evidence
    assert evidence["outcome"] == ("mismatch" if outcome == "mismatch" else "incomplete")


def test_governed_plan_reports_a_bound_plan_mismatch(tmp_path: Path):
    evidence = governed(tmp_path, bound={"outcome": "mismatch"})
    assert checks_of(evidence)["bound-plan:hashes"]["outcome"] == "mismatch" and evidence["outcome"] == "mismatch"


# --------------------------------------------------------------------------- proposal (apply-proposal)

def proposal(tmp_path: Path, mutate: Callable[[Path, dict], None] | None = None,
             changed: list[str] | None = None, apply_error: str | None = None) -> dict:
    root = tmp_path / "execution"; root.mkdir(parents=True)
    (root / "change.patch").write_text("--- a\n+++ b\n")
    execution = {"proposal": {"status": "proposed", "patches": [{"path": "change.patch", "sha256": sha((root / "change.patch").read_bytes())}]}}
    if mutate:
        mutate(root, execution)
    return gate_evidence.proposal(root, execution, lambda: changed or [], lambda: apply_error)


def test_proposal_reference_and_negatives(tmp_path: Path):
    assert proposal(tmp_path / "ok")["outcome"] == "match"
    cases = [
        (proposal(tmp_path / "a", lambda root, e: (root / "change.patch").write_text("tampered\n")), "patch:change.patch:integrity", "mismatch"),
        (proposal(tmp_path / "b", lambda root, e: (root / "change.patch").unlink()), "patch:change.patch:integrity", "unavailable"),
        (proposal(tmp_path / "c", changed=["main"]), "workspace:unchanged", "mismatch"),
        (proposal(tmp_path / "d", apply_error="patch does not apply"), "patches:apply", "mismatch"),
        (proposal(tmp_path / "e", lambda root, e: e["proposal"].update(status="applied")), "proposal:status", "mismatch"),
    ]
    for evidence, item, outcome in cases:
        assert checks_of(evidence)[item]["outcome"] == outcome, (item, evidence)
        assert evidence["outcome"] != "match"


# --------------------------------------------------------------------------- submission-evidence (before-commit, before-submission, submission gate)

def submission(tmp_path: Path, mutate: Callable[[Path, dict], None] | None = None) -> dict:
    root = tmp_path / "execution"; root.mkdir(parents=True)
    dump(root / "planning.yaml", {"details": {"acceptanceCriteria": [{"id": "AC-1", "statement": "s"}]}})
    dump(root / "validation.yaml", {"details": {"results": [{"repository": "main", "profile": "p", "operation": "test", "exitCode": 0}]}})
    dump(root / "review.yaml", {"details": {"decision": "approved", "evidenceMatrix": [
        {"id": "AC-1", "status": "verified", "evidence": ["main:p:test:exit-0"]}]}})
    execution = {"review": {"independentRequired": False}, "enforcementPoints": ["enforcement-1.yaml"]}
    dump(root / "enforcement-1.yaml", {"action": "commit", "required": True, "assurance": {"status": "ENFORCED"}})
    dump(root / "execution.yaml", execution)
    if mutate:
        mutate(root, execution)
        dump(root / "execution.yaml", execution)
    return gate_evidence.submission(root, execution)


def test_submission_evidence_reference_and_negatives(tmp_path: Path):
    assert submission(tmp_path / "ok")["outcome"] == "match", submission(tmp_path / "ok2")
    gaps = {
        "missing validation": lambda root, e: (root / "validation.yaml").unlink(),
        "failed command": lambda root, e: dump(root / "validation.yaml", {"details": {"results": [
            {"repository": "main", "profile": "p", "operation": "test", "exitCode": 1}]}}),
        "review not approved": lambda root, e: dump(root / "review.yaml", {"details": {"decision": "changes-requested",
            "evidenceMatrix": [{"id": "AC-1", "status": "verified", "evidence": ["main:p:test:exit-0"]}]}}),
        "criterion not covered": lambda root, e: dump(root / "review.yaml", {"details": {"decision": "approved",
            "evidenceMatrix": [{"id": "AC-2", "status": "verified", "evidence": ["main:p:test:exit-0"]}]}}),
        "evidence not observed": lambda root, e: dump(root / "review.yaml", {"details": {"decision": "approved",
            "evidenceMatrix": [{"id": "AC-1", "status": "verified", "evidence": ["main:p:build:exit-0"]}]}}),
        "review not independent": lambda root, e: e["review"].update(independentRequired=True),
    }
    for name, mutate in gaps.items():
        evidence = submission(tmp_path / name.replace(" ", "-"), mutate)
        assert evidence["outcome"] == "mismatch", name
        assert any(item["item"] == "submission-evidence" and item["outcome"] == "mismatch" for item in evidence["checks"]), name
    evidence = submission(tmp_path / "enforcement", lambda root, e: dump(root / "enforcement-1.yaml",
                          {"action": "commit", "required": True, "assurance": {"status": "UNAVAILABLE"}}))
    assert checks_of(evidence)["required-enforcement"]["outcome"] == "mismatch" and evidence["outcome"] == "mismatch"


# --------------------------------------------------------------------------- integration (before-merge)

def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=root, check=True,
                          capture_output=True, text=True).stdout.strip()


def repository(tmp_path: Path) -> tuple[Path, str]:
    root = tmp_path / "repo"; root.mkdir(parents=True)
    git(root, "init", "-q", "-b", "main"); (root / "app.txt").write_text("one\n"); git(root, "add", "-A"); git(root, "commit", "-qm", "init")
    git(root, "switch", "-q", "-c", "aief/t"); (root / "app.txt").write_text("two\n"); git(root, "commit", "-qam", "change")
    validated = git(root, "rev-parse", "HEAD")
    git(root, "switch", "-q", "-c", "elsewhere", "main")
    return root, validated


def target(root: Path) -> dict:
    return {"repository": "main", "gitRoot": str(root), "taskBranch": "aief/t", "baseBranch": "main"}


def integration(root: Path, execution: dict, validated: str | None) -> dict:
    return gate_evidence.integration(root, execution, integration_checks(target(root), validated))


AWAITING = {"status": "completed", "integration": {"status": "awaiting-approval"}}


def test_integration_reference_matches(tmp_path: Path):
    root, validated = repository(tmp_path)
    (root / "execution.yaml").touch()
    evidence = integration(root, AWAITING, validated)
    repo_checks = {item: value for item, value in checks_of(evidence).items() if not item.startswith("submission:")}
    assert all(value["outcome"] == "match" for value in repo_checks.values()), repo_checks


def test_integration_negatives(tmp_path: Path):
    root, validated = repository(tmp_path)
    cases = []
    cases.append((integration(root, {**AWAITING, "status": "cancelled"}, validated), "execution:status", "mismatch"))
    cases.append((integration(root, {"status": "completed", "integration": {"status": "integrated"}}, validated), "integration:status", "mismatch"))
    cases.append((gate_evidence.integration(root, AWAITING, []), "integration:targets", "unavailable"))
    cases.append((integration(root, AWAITING, "0" * 40), "main:task-branch:contains-validated-revision", "mismatch"))
    cases.append((integration(root, AWAITING, None), "main:task-branch:contains-validated-revision", "unavailable"))
    git(root, "switch", "-q", "main"); (root / "app.txt").write_text("uncommitted\n")
    cases.append((integration(root, AWAITING, validated), "main:base-branch:clean", "mismatch"))
    git(root, "checkout", "-q", "--", "app.txt"); (root / "app.txt").write_text("three\n"); git(root, "commit", "-qam", "conflict")
    cases.append((integration(root, AWAITING, validated), "main:merge:clean", "mismatch"))
    git(root, "switch", "-q", "elsewhere"); git(root, "branch", "-q", "-D", "aief/t")
    cases.append((integration(root, AWAITING, validated), "main:branch:aief/t", "mismatch"))
    for evidence, item, outcome in cases:
        assert checks_of(evidence)[item]["outcome"] == outcome, (item, checks_of(evidence).get(item))
        assert evidence["outcome"] != "match", item


# --------------------------------------------------------------------------- coverage

COVERED = {
    "bound-plan-hashes": {generic(item) for _, item, _ in BOUND_PLAN_CASES.values()},
    "plan-criteria": {"acceptance-criteria", "planning"},
    "governed-plan": {generic(item) for _, item, _ in GOVERNED_CASES.values()} | {"bound-plan:hashes"},
    "proposal": {"patch:integrity", "workspace:unchanged", "patches:apply", "proposal:status"},
    "submission-evidence": {"submission-evidence", "required-enforcement"},
    "integration": {"execution:status", "integration:status", "integration:targets", "task-branch:contains-validated-revision",
                    "base-branch:clean", "merge:clean", "branch",
                    "submission:submission-evidence", "submission:required-enforcement"},
}


def test_every_check_of_every_comparator_has_a_negative_case(tmp_path: Path):
    emitted = {
        "bound-plan-hashes": bound_plan(tmp_path / "b"),
        "governed-plan": governed(tmp_path / "g", bound={"outcome": "match"}),
        "proposal": proposal(tmp_path / "p"),
        "submission-evidence": submission(tmp_path / "s"),
    }
    root, validated = repository(tmp_path / "i")
    emitted["integration"] = integration(root, AWAITING, validated)
    dump(tmp_path / "planning.yaml", {"details": {"acceptanceCriteria": [{"id": "AC-1", "statement": "s"}]}})
    emitted["plan-criteria"] = gate_evidence.plan_criteria(tmp_path)
    for comparator, evidence in emitted.items():
        assert evidence["comparator"] == comparator
        uncovered = {generic(item["item"]) for item in evidence["checks"]} - COVERED[comparator]
        assert not uncovered, f"{comparator}: no negative case for {sorted(uncovered)}"
