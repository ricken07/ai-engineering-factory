from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from aief.enforcement import assert_required_enforcement, enforcement_point
from aief.cli import parser
from aief.evidence import build_evidence_bundle, submission_evidence_gaps
from aief.identity import actor_identity, declared_actor, review_independence, trusted_session_actor
from aief.project import initialize
from aief.runtime import Execution
from aief.service import RuntimeService
from aief.timing import FakeClock
from aief.validation import assert_schema


ROOT = Path(__file__).parents[1]


def clock() -> FakeClock:
    return FakeClock(datetime(2026, 9, 11, tzinfo=timezone.utc))


def workflow(*phases):
    return {"metadata": {"id": "demo", "version": "1.0.0"}, "phases": list(phases)}


def test_execution_phase_and_gate_durations_are_monotonic_and_structured(tmp_path: Path):
    fake = clock()
    execution = Execution.create(tmp_path, ROOT, workflow(
        {"id": "work", "skill": "implement-change"},
        {"id": "approve", "skill": "create-plan", "gate": {"id": "human", "type": "human-approval"}},
    ), "TASK-1", "codex", fake)
    fake.advance(milliseconds=100)
    execution.advance({"summary": "done"})
    fake.advance(milliseconds=50)
    assert execution.advance({"summary": "planned"}) == "waiting-approval"
    fake.advance(milliseconds=1000)
    assert Execution.load(execution.root, fake).advance(approved=True) == "completed"
    data = Execution.load(execution.root, fake).data
    assert data["phases"][0]["timing"]["durationMs"] == {"value": 100, "availability": "OBSERVED"}
    assert data["phases"][1]["timing"]["durationMs"] == {"value": 1050, "availability": "OBSERVED"}
    assert data["metrics"]["gateWaiting"]["durationMs"] == {"value": 1000, "availability": "OBSERVED"}
    assert data["metrics"]["execution"]["durationMs"] == {"value": 1150, "availability": "OBSERVED"}
    assert data["metrics"]["agent"]["durationMs"] == {"value": None, "availability": "UNAVAILABLE"}
    assert data["metrics"]["runtime"]["durationMs"] == {"value": 0, "availability": "OBSERVED"}
    historical = data["metrics"]["gateWaiting"]["durationMs"]
    Execution.load(execution.root, fake).advance()
    assert Execution.load(execution.root, fake).data["metrics"]["gateWaiting"]["durationMs"] == historical


def test_multiple_gate_intervals_accumulate_once_across_resume(tmp_path: Path):
    fake = clock()
    execution = Execution.create(tmp_path, ROOT, workflow({"id": "work", "skill": "implement-change"}), "TASK-2", clock=fake)
    first, second = {"id": "first", "status": "pending"}, {"id": "second", "status": "pending"}
    execution.start_policy_gate(first); fake.advance(milliseconds=20); execution.complete_policy_gate(first)
    execution.start_policy_gate(second); fake.advance(milliseconds=30); execution.complete_policy_gate(second)
    execution.data["policyGates"] = [first, second]; execution.save()
    resumed = Execution.load(execution.root, fake)
    resumed.complete_policy_gate(first)
    assert resumed.data["metrics"]["gateWaiting"]["durationMs"]["value"] == 50


def test_overlapping_gate_intervals_are_not_double_counted(tmp_path: Path):
    fake = clock()
    execution = Execution.create(tmp_path, ROOT, workflow({"id": "work", "skill": "implement-change"}), "TASK-2B", clock=fake)
    first, second = {"id": "first", "status": "pending"}, {"id": "second", "status": "pending"}
    execution.start_policy_gate(first); fake.advance(milliseconds=10); execution.start_policy_gate(second)
    fake.advance(milliseconds=20); execution.complete_policy_gate(first)
    fake.advance(milliseconds=30); execution.complete_policy_gate(second)
    assert execution.data["metrics"]["gateWaiting"]["durationMs"]["value"] == 60


def test_incomplete_and_failed_execution_timing(tmp_path: Path):
    fake = clock()
    execution = Execution.create(tmp_path, ROOT, workflow({"id": "work", "skill": "implement-change"}), "TASK-3", clock=fake)
    assert execution.data["metrics"]["execution"]["durationMs"]["availability"] == "UNAVAILABLE"
    fake.advance(milliseconds=40)
    execution.fail_phase({"summary": "failed"})
    assert execution.data["metrics"]["execution"]["durationMs"] == {"value": 40, "availability": "OBSERVED"}
    assert execution.data["phases"][0]["timing"]["durationMs"]["value"] == 40


def test_invalid_monotonic_resume_is_unavailable_not_zero(tmp_path: Path):
    fake = clock(); fake.elapsed_ns = 100_000_000
    execution = Execution.create(tmp_path, ROOT, workflow({"id": "work", "skill": "implement-change"}), "TASK-3B", clock=fake)
    fake.elapsed_ns = 0
    Execution.load(execution.root, fake).fail_phase({"summary": "failed after clock reset"})
    metric = Execution.load(execution.root, fake).data["metrics"]["execution"]["durationMs"]
    assert metric == {"value": None, "availability": "UNAVAILABLE"}


def test_identity_assurance_and_independence_are_fail_closed():
    producer = trusted_session_actor("session-a")
    assert declared_actor("session-b")["assurance"] == "UNVERIFIED"
    assert actor_identity("agent", "agent", "artifact", "TRUSTED")["assurance"] == "UNVERIFIED"
    assert review_independence(producer, declared_actor("session-b")) == "UNVERIFIED"
    assert review_independence(producer, trusted_session_actor("session-a")) == "NOT_INDEPENDENT"
    assert review_independence(producer, trusted_session_actor("session-b")) == "INDEPENDENT"
    assert review_independence(actor_identity("codex", "agent", "adapter", "OBSERVED"), trusted_session_actor("session-b")) == "UNVERIFIED"
    assert review_independence(producer, None) == "UNVERIFIED"
    assert review_independence(producer, None, required=False) == "NOT_REQUIRED"


def test_required_independent_review_rejects_artifact_claim(tmp_path: Path):
    for name, value in {
        "planning.yaml": {"details": {"acceptanceCriteria": [{"id": "AC-1"}]}},
        "validation.yaml": {"details": {"results": [{"exitCode": 0}], "evidenceMatrix": [{"id": "AC-1", "status": "verified", "evidence": ["EV-1"]}]}},
        "review.yaml": {"details": {"independent": True, "reviewerSession": "other", "implementationSession": "producer", "decision": "approved", "blockingFindings": []}},
        "execution.yaml": {"actors": {"producer": trusted_session_actor("producer"), "reviewer": declared_actor("other")}, "review": {"independentRequired": True}},
    }.items():
        (tmp_path/name).write_text(yaml.safe_dump(value))
    assert "review independence is UNVERIFIED; INDEPENDENT is required" in submission_evidence_gaps(tmp_path)


def test_enforcement_status_and_required_fail_closed():
    runtime = enforcement_point(execution="exec", action="push", decision="DENY", mechanism_type="runtime",
                                capability="governed-action", status="ENFORCED", evidence_ref="policy.yaml", required=True)
    assert runtime["assurance"]["status"] == "ENFORCED"
    assert_required_enforcement([runtime])
    for status in ("UNVERIFIED", "UNAVAILABLE", "ENFORCEABLE"):
        point = enforcement_point(execution="exec", action="push", decision="DENY", mechanism_type="provider",
                                  capability="branch-protection", status=status, required=True)
        with pytest.raises(PermissionError): assert_required_enforcement([point])
    with pytest.raises(ValueError):
        enforcement_point(execution="exec", action="push", decision="DENY", mechanism_type="runtime",
                          capability="guard", status="ENFORCED")


def test_runtime_denied_action_has_enforced_evidence(tmp_path: Path):
    project = tmp_path/"project"; initialize(ROOT/"templates/project", project)
    service = RuntimeService(project, ROOT, {}, clock())
    execution = service.start("Implement a change", "codex", confirmed=True)
    service.reassess_policy(execution, {"risk": "high", "repositories": ["main"]}, "test")
    with pytest.raises(PermissionError, match="denies governed action"):
        service.authorize_action(execution.data["metadata"]["id"], "push")
    current = service.execution(execution.data["metadata"]["id"])
    point = yaml.safe_load((current.root/current.data["enforcementPoints"][-1]).read_text())
    assert point["assurance"]["status"] == "ENFORCED" and point["evidenceRef"].startswith("policy-decision-")


def test_pending_gate_cannot_bypass_runtime_by_completing_phase_directly(tmp_path: Path):
    project = tmp_path/"project"; initialize(ROOT/"templates/project", project)
    service = RuntimeService(project, ROOT, {})
    execution = service.start("Implement a change", "codex", confirmed=True)
    for phase in execution.data["phases"]:
        if phase["id"] == "implementation": break
        phase["status"] = "completed"
    execution.data["policyGates"] = [{"id": "before-implementation", "status": "pending"}]
    execution.save()
    output = {"summary": "attempt", "status": "completed", "evidence": [], "unknowns": [], "details": {}}
    with pytest.raises(PermissionError, match="required policy gates are pending"):
        service.complete_phase(execution.data["metadata"]["id"], output)


def test_runtime_validation_records_trusted_verifier_and_duration(tmp_path: Path):
    project = tmp_path/"project"; initialize(ROOT/"templates/project", project)
    project_data = yaml.safe_load((project/".ai/project.yaml").read_text())
    project_data["autonomy"]["default"] = "L2"
    project_data["repositories"][0]["profiles"] = ["maven"]
    (project/".ai/project.yaml").write_text(yaml.safe_dump(project_data, sort_keys=False))
    (project/"mvnw").touch()
    fake = clock(); service = RuntimeService(project, ROOT, {}, fake)
    execution = service.start("Implement a change", "codex", confirmed=True)
    execution.data["repositories"] = ["main"]
    for phase in execution.data["phases"]:
        if phase["skill"] == "validate-change": break
        phase["status"] = "completed"
    execution.save()
    class Result: returncode, stdout, stderr = 0, "ok", ""
    def runner(command, **kwargs): fake.advance(milliseconds=25); return Result()
    report = service.run_profile_validation(execution.data["metadata"]["id"], runner)
    current = service.execution(execution.data["metadata"]["id"])
    assert report["details"]["verifier"]["assurance"] == "TRUSTED"
    assert report["details"]["results"][0]["execution"] == execution.data["metadata"]["id"]
    assert current.data["metrics"]["validation"]["durationMs"] == {"value": 25 * len(report["details"]["results"]), "availability": "OBSERVED"}


def test_evidence_bundle_references_metrics_identity_and_enforcement(tmp_path: Path):
    fake = clock()
    execution = Execution.create(tmp_path, ROOT, workflow({"id": "work", "skill": "implement-change"}), "TASK-4", "codex", fake)
    execution.data["review"] = {"independentRequired": True, "independence": "UNVERIFIED"}
    execution.save()
    bundle = build_evidence_bundle(execution.root)
    assert bundle["metrics"] == execution.data["metrics"]
    assert bundle["identity"]["actors"]["producer"]["source"] == "adapter"
    assert_schema(ROOT, "evidence-bundle.schema.json", bundle)


def test_reproducibility_metadata_is_explicit_and_exportable(tmp_path: Path):
    project = tmp_path/"project"; initialize(ROOT/"templates/project", project)
    service = RuntimeService(project, ROOT, {})
    execution = service.start(
        "Implement a change", "claude-code", confirmed=True, agent_session="producer-1",
        experiment={"condition": "L2", "repeatIndex": 3, "environmentIdentifier": "runner-a", "modelIdentifier": "model-x"},
    )
    service.reassess_policy(execution, {"risk": "medium", "repositories": ["main"]}, "test")
    metadata = execution.data["reproducibility"]
    assert metadata["experimentalCondition"] == {"value": "L2", "availability": "OBSERVED"}
    assert metadata["repeatIndex"] == {"value": 3, "availability": "OBSERVED"}
    assert metadata["contextFingerprint"]["availability"] == "OBSERVED"
    assert metadata["policyFingerprint"]["availability"] == "OBSERVED"
    assert metadata["governedExecutionPlanFingerprint"]["availability"] == "OBSERVED"
    assert_schema(ROOT, "execution.schema.json", execution.data)
    args = parser().parse_args(["run", "task", "--experiment-condition", "L2", "--repeat-index", "3"])
    assert (args.experiment_condition, args.repeat_index) == ("L2", 3)
