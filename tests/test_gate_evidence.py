from pathlib import Path

import yaml

from aief import gate_evidence
from aief.validation import assert_schema
from tests.test_dynamic_policy import PATCH, critical_implementation, output, runtime


ROOT = Path(__file__).parents[1]


def items(evidence: dict) -> dict:
    return {item["item"]: item for item in evidence["checks"]}


def at_before_implementation(tmp_path: Path):
    service, execution = runtime(tmp_path); identifier = execution.data["metadata"]["id"]
    service.prepare_phase(identifier)
    service.complete_phase(identifier, output("Critical impact", {"risk": "critical", "repositories": ["main"], "changeTypes": ["destructive-migration"]}))
    current = service.execution(identifier)
    for phase in current.data["phases"]:
        if phase["id"] == "implementation": break
        phase["status"] = "completed"
    current.data["status"] = "running"; current.save()
    assert service.prepare_phase(identifier)["requiredPolicyGates"] == ["before-implementation"]
    return service, identifier


def test_before_implementation_records_governed_plan_evidence(tmp_path: Path):
    service, identifier = at_before_implementation(tmp_path)
    shown = service.gate_check(identifier)["gates"][0]
    assert shown["gate"] == "before-implementation" and shown["evidence"]["comparator"] == "governed-plan"
    assert shown["evidence"]["outcome"] == "match", shown["evidence"]
    service.approve_policy_gate(identifier, "before-implementation", approver="alice")
    current = service.execution(identifier)
    decision = next(item for item in current.data["gateDecisions"] if item["gate"] == "before-implementation")
    checks = items(decision["evidence"])
    assert {"governed-plan:integrity", "governed-plan:recorded", "enforcement-points:enforceable",
            "policy-decision:recorded", "plan:approved"} <= set(checks)
    assert decision["evidence"]["outcome"] == "match"
    assert_schema(ROOT, "execution.schema.json", current.data)


def test_tampered_governed_plan_is_a_mismatch(tmp_path: Path):
    service, identifier = at_before_implementation(tmp_path)
    root = service.execution(identifier).root
    name = service.execution(identifier).data["governedExecutionPlan"]
    plan = yaml.safe_load((root / name).read_text()); plan["allowedActions"] = ["everything"]
    (root / name).write_text(yaml.safe_dump(plan, sort_keys=False))
    evidence = service.gate_check(identifier)["gates"][0]["evidence"]
    assert evidence["outcome"] == "mismatch"
    assert items(evidence)["governed-plan:integrity"]["outcome"] == "mismatch"


def test_apply_proposal_evidence_is_taken_before_the_patch_is_applied(tmp_path: Path):
    service, identifier, root = critical_implementation(tmp_path)
    execution = service.execution(identifier); (execution.root / "change.patch").write_text(PATCH)
    service.complete_phase(identifier, output("Proposed", {"repositories": ["main"], "proposal": {"patches": [{"repository": "main", "path": "change.patch"}]}}))
    assert service.prepare_phase(identifier)["requiredPolicyGates"] == ["apply-proposal"]
    shown = service.gate_check(identifier)["gates"][0]["evidence"]
    assert shown["comparator"] == "proposal" and shown["outcome"] == "match", shown
    service.approve_policy_gate(identifier, "apply-proposal", approver="alice")
    current = service.execution(identifier)
    assert current.data["proposal"]["status"] == "applied"
    decision = next(item for item in current.data["gateDecisions"] if item["gate"] == "apply-proposal")
    assert decision["evidence"]["outcome"] == "match"
    assert {"patch:change.patch:integrity", "workspace:unchanged", "patches:apply"} <= set(items(decision["evidence"]))


def test_changed_patch_or_workspace_is_a_mismatch(tmp_path: Path):
    service, identifier, root = critical_implementation(tmp_path)
    execution = service.execution(identifier); (execution.root / "change.patch").write_text(PATCH)
    service.complete_phase(identifier, output("Proposed", {"repositories": ["main"], "proposal": {"patches": [{"repository": "main", "path": "change.patch"}]}}))
    service.prepare_phase(identifier)
    (execution.root / "change.patch").write_text(PATCH.replace("+two", "+three"))
    (root / "app.txt").write_text("edited outside the proposal\n")
    evidence = service.gate_check(identifier)["gates"][0]["evidence"]
    checks = items(evidence)
    assert evidence["outcome"] == "mismatch"
    assert checks["patch:change.patch:integrity"]["outcome"] == "mismatch"
    assert checks["workspace:unchanged"]["outcome"] == "mismatch"
    assert checks["patches:apply"]["outcome"] == "mismatch"


def test_plan_gate_without_bound_plan_checks_the_criteria(tmp_path: Path):
    from tests.test_gate_protocol import at_plan_gate, service_with
    service = service_with(tmp_path)
    identifier = at_plan_gate(service)
    evidence = service.gate_check(identifier)["gates"][0]["evidence"]
    assert evidence["comparator"] == "plan-criteria" and evidence["outcome"] == "match"


def test_submission_evidence_lists_every_gap(tmp_path: Path):
    root = tmp_path / "execution"; root.mkdir()
    (root / "planning.yaml").write_text(yaml.safe_dump({"details": {"acceptanceCriteria": [{"id": "AC-1", "statement": "s"}]}}))
    evidence = gate_evidence.submission(root, {"enforcementPoints": []})
    assert evidence["comparator"] == "submission-evidence" and evidence["outcome"] == "mismatch"
    observed = [item["observed"] for item in evidence["checks"] if item["item"] == "submission-evidence"]
    assert "validation.yaml is missing" in observed and "review.yaml is missing" in observed
    assert items(evidence)["required-enforcement"]["outcome"] == "match"


def test_unknown_gate_has_no_comparator(tmp_path: Path):
    service, identifier = at_before_implementation(tmp_path)
    execution = service.execution(identifier)
    assert service._gate_evidence(execution, {"kind": "policy-gate", "gate": "before-external-action", "phase": None}) is None


def merge_evidence(service, identifier):
    gate = next(item for item in service.gate_check(identifier)["gates"] if item["gate"] == "before-merge")
    return gate["evidence"]


def test_before_merge_evidence_checks_the_integration(tmp_path: Path):
    from tests.test_integration import completed_with_task_branch, git
    service, identifier, root = completed_with_task_branch(tmp_path)
    (service.execution(identifier).root / "validation.yaml").write_text(
        yaml.safe_dump({"details": {"commits": {"main": git(root, "rev-parse", "aief/t")}}}))
    evidence = merge_evidence(service, identifier)
    checks = items(evidence)
    assert evidence["comparator"] == "integration"
    for item in ("execution:status", "integration:status", "main:branch:aief/t", "main:branch:main",
                 "main:task-branch:contains-validated-revision", "main:base-branch:clean", "main:merge:clean"):
        assert checks[item]["outcome"] == "match", (item, checks[item])
    assert any(item.startswith("submission:") for item in checks)
    service.approve_policy_gate(identifier, "before-merge", approver="alice")
    current = service.execution(identifier)
    decision = next(item for item in current.data["gateDecisions"] if item["gate"] == "before-merge")
    # Taken before the merge: the integration was still awaiting approval.
    assert items(decision["evidence"])["integration:status"]["observed"] == "awaiting-approval"
    assert current.data["integration"]["status"] == "integrated"
    assert_schema(ROOT, "execution.schema.json", current.data)


def test_before_merge_evidence_reports_a_conflict_and_a_foreign_revision(tmp_path: Path):
    from tests.test_integration import completed_with_task_branch
    service, identifier, root = completed_with_task_branch(tmp_path, conflicting=True)
    (service.execution(identifier).root / "validation.yaml").write_text(
        yaml.safe_dump({"details": {"commits": {"main": "0" * 40}}}))
    evidence = merge_evidence(service, identifier)
    checks = items(evidence)
    assert evidence["outcome"] == "mismatch"
    assert checks["main:merge:clean"]["observed"] == "conflicts"
    assert checks["main:task-branch:contains-validated-revision"]["outcome"] == "mismatch"


def test_before_merge_evidence_reports_a_dirty_base_branch(tmp_path: Path):
    from tests.test_integration import completed_with_task_branch, git
    service, identifier, root = completed_with_task_branch(tmp_path)
    git(root, "switch", "-q", "main"); (root / "app.txt").write_text("uncommitted\n")
    checks = items(merge_evidence(service, identifier))
    assert checks["main:base-branch:clean"]["outcome"] == "mismatch"
    assert checks["main:task-branch:contains-validated-revision"]["outcome"] == "unavailable"
