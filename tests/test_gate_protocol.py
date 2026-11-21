import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from aief.intake import TaskRegistry
from aief.project import initialize
from aief.service import RuntimeService
from aief.timing import FakeClock
from aief.validation import assert_schema


ROOT = Path(__file__).parents[1]
CRITERIA = [{"id": "AC-1", "statement": "works"}]


def service_with(tmp_path: Path, human_gates: dict | None = None, clock: FakeClock | None = None) -> RuntimeService:
    root = tmp_path / "project"
    if not root.exists():
        initialize(ROOT / "templates/project", root)
    data = yaml.safe_load((root / ".ai/project.yaml").read_text()); data["autonomy"] = {"default": "L3", "maximum": "L3"}
    data["repositories"] = [{"id": "main", "path": ".", "role": "application", "profiles": ["generic"],
                             "responsibilities": [], "dependencies": [], "criticalDomains": []}]
    if human_gates is not None:
        data["humanGates"] = human_gates
    else:
        data.pop("humanGates", None)
    (root / ".ai/project.yaml").write_text(yaml.safe_dump(data, sort_keys=False))
    return RuntimeService(root, ROOT, clock=clock)


def output(summary: str, details: dict) -> dict:
    return {"summary": summary, "status": "completed", "evidence": ["verified"], "unknowns": [], "details": details}


def at_plan_gate(service: RuntimeService) -> str:
    """Execution whose planning phase is done and waits for the human plan gate."""
    execution = service.start("Implémente une évolution locale", confirmed=True)
    identifier = execution.data["metadata"]["id"]
    task = TaskRegistry(service.project_root).load(execution.data["task"]); task["autonomy"] = {"requested": "L3"}
    TaskRegistry(service.project_root).save(task)
    for phase in execution.data["phases"]:
        if phase["skill"] == "analyze-impact": break
        phase["status"] = "completed"
    execution.data["status"] = "running"; execution.save()
    service.prepare_phase(identifier)
    service.complete_phase(identifier, output("Impact", {"risk": "medium", "repositories": ["main"], "changeTypes": ["source-code"]}))
    current = service.execution(identifier)
    while current.next_phase()["skill"] != "create-plan":
        current.next_phase()["status"] = "completed"
    current.data["status"] = "running"; current.save()
    service.prepare_phase(identifier)
    service.complete_phase(identifier, output("Plan", {"repositories": ["main"], "acceptanceCriteria": CRITERIA}))
    assert service.execution(identifier).data["status"] == "waiting-approval"
    return identifier


def events(service: RuntimeService, identifier: str) -> list[dict]:
    task = service.execution(identifier).data["task"]
    return service.task_events(task)


def test_protocol_is_snapshotted_at_start(tmp_path: Path):
    service = service_with(tmp_path, {"approvers": ["alice"], "responseLimitMinutes": 30, "decisionRule": "rule-v1"})
    execution = service.start("Implémente une évolution locale", confirmed=True)
    snapshot = execution.data["reproducibility"]["humanGateProtocol"]
    assert snapshot == {"value": {"approvers": ["alice"], "responseLimitMinutes": 30, "decisionRule": "rule-v1"},
                        "availability": "OBSERVED"}
    service_with(tmp_path, {"approvers": [], "responseLimitMinutes": None})
    assert service.execution(execution.data["metadata"]["id"]).data["reproducibility"]["humanGateProtocol"] == snapshot


def test_default_protocol_keeps_ordinary_use(tmp_path: Path):
    service = service_with(tmp_path)
    identifier = at_plan_gate(service)
    service.approve_execution(identifier, approver="anyone")
    decision = service.execution(identifier).data["gateDecisions"][0]
    assert decision["decision"] == "approved" and decision["responseLimitMinutes"] is None


def test_approval_records_a_gate_decision(tmp_path: Path):
    service = service_with(tmp_path, {"approvers": ["alice"], "decisionRule": "rule-v1"})
    identifier = at_plan_gate(service)
    service.approve_execution(identifier, approver="alice")
    current = service.execution(identifier)
    decision = next(item for item in current.data["gateDecisions"] if item["kind"] == "phase-gate")
    assert decision["gate"] == "plan-gate" and decision["phase"] == "planning" and decision["trigger"] == "phase:planning"
    assert decision["actor"] == {"id": "alice", "type": "human", "channel": "interactive-terminal", "assurance": "OBSERVED"}
    assert decision["decisionRule"] == "rule-v1" and decision["waitDurationMs"]["availability"] == "OBSERVED"
    assert decision["waitStartedAt"] and decision["decidedAt"]
    assert_schema(ROOT, "execution.schema.json", current.data)


def test_policy_gate_decision_keeps_its_trigger(tmp_path: Path):
    service = service_with(tmp_path)
    identifier = at_plan_gate(service)
    current = service.execution(identifier)
    gates = {gate["id"]: gate for gate in current.data["policyGates"]}
    if not gates:
        pytest.skip("the medium-risk policy requires no policy gate here")
    gate = next(iter(gates.values()))
    assert gate["trigger"] in {"analyze-impact", "create-plan"}


def test_approver_outside_the_protocol_is_refused(tmp_path: Path):
    service = service_with(tmp_path, {"approvers": ["alice"]})
    identifier = at_plan_gate(service)
    with pytest.raises(PermissionError, match="not an approver"):
        service.approve_execution(identifier, approver="mallory")
    current = service.execution(identifier)
    assert current.data["status"] == "waiting-approval" and "gateDecisions" not in current.data
    assert "not an approver" in current.data["approvalRefusals"][-1]["reason"]
    service.approve_execution(identifier, approver="alice")
    assert service.execution(identifier).data["status"] == "running"


def test_rejection_cancels_with_its_rationale(tmp_path: Path):
    service = service_with(tmp_path, {"decisionRule": "rule-v1"})
    identifier = at_plan_gate(service)
    with pytest.raises(ValueError, match="rationale"):
        service.reject_gate(identifier, "  ", approver="alice")
    service.reject_gate(identifier, "The plan skips the migration", approver="alice")
    current = service.execution(identifier)
    assert current.data["status"] == "cancelled"
    decision = current.data["gateDecisions"][-1]
    assert decision["decision"] == "rejected" and decision["rationale"] == "The plan skips the migration"
    assert decision["actor"]["assurance"] == "OBSERVED" and decision["waitDurationMs"]["availability"] == "OBSERVED"
    rejected = [event for event in events(service, identifier) if event["event"]["type"] == "gate.rejected"]
    assert rejected and rejected[0]["payload"]["rationale"] == "The plan skips the migration"
    assert_schema(ROOT, "execution.schema.json", current.data)


def test_rejection_needs_a_waiting_gate(tmp_path: Path):
    service = service_with(tmp_path)
    execution = service.start("Implémente une évolution locale", confirmed=True)
    with pytest.raises(RuntimeError, match="no human gate is waiting"):
        service.reject_gate(execution.data["metadata"]["id"], "no", approver="alice")


def test_rejection_relayed_by_an_agent_is_refused(tmp_path: Path, monkeypatch):
    service = service_with(tmp_path)
    identifier = at_plan_gate(service)
    monkeypatch.setenv("CLAUDECODE", "1")
    with pytest.raises(PermissionError, match="OBSERVED"):
        service.reject_gate(identifier, "agent says no", approver="alice")
    assert service.execution(identifier).data["status"] == "waiting-approval"


def test_gate_expires_after_the_response_limit(tmp_path: Path):
    clock = FakeClock(datetime(2026, 11, 21, 9, 0, tzinfo=timezone.utc))
    service = service_with(tmp_path, {"responseLimitMinutes": 5, "decisionRule": "rule-v1"}, clock)
    identifier = at_plan_gate(service)
    clock.advance(milliseconds=6 * 60_000)
    with pytest.raises(PermissionError, match="expired"):
        service.approve_execution(identifier, approver="alice")
    current = service.execution(identifier)
    assert current.data["status"] == "cancelled" and "expired" in current.data["cancelledReason"]
    decision = current.data["gateDecisions"][-1]
    assert decision["decision"] == "expired" and "actor" not in decision
    started = datetime.fromisoformat(decision["waitStartedAt"])
    assert (datetime.fromisoformat(decision["decidedAt"]) - started).total_seconds() == 300
    assert decision["waitDurationMs"] == {"value": 300_000, "availability": "DERIVED"}
    assert any(event["event"]["type"] == "gate.expired" for event in events(service, identifier))
    assert_schema(ROOT, "execution.schema.json", current.data)


def test_decision_within_the_limit_is_accepted(tmp_path: Path):
    clock = FakeClock(datetime(2026, 11, 21, 9, 0, tzinfo=timezone.utc))
    service = service_with(tmp_path, {"responseLimitMinutes": 5}, clock)
    identifier = at_plan_gate(service)
    clock.advance(milliseconds=4 * 60_000)
    service.approve_execution(identifier, approver="alice")
    decision = service.execution(identifier).data["gateDecisions"][0]
    assert decision["decision"] == "approved" and decision["waitDurationMs"] == {"value": 240_000, "availability": "OBSERVED"}


def test_execution_next_applies_the_expiry(tmp_path: Path):
    clock = FakeClock(datetime(2026, 11, 21, 9, 0, tzinfo=timezone.utc))
    service = service_with(tmp_path, {"responseLimitMinutes": 1}, clock)
    identifier = at_plan_gate(service)
    clock.advance(milliseconds=61_000)
    prepared = service.prepare_phase(identifier)
    assert prepared["status"] == "cancelled" and "expired" in prepared["cancelledReason"]


def test_cli_reject(tmp_path: Path):
    import subprocess, sys
    service = service_with(tmp_path)
    identifier = at_plan_gate(service)
    command = [sys.executable, "-m", "aief.cli", "execution", "reject", identifier, "--reason", "wrong scope",
               "--project", str(service.project_root), "--factory", str(ROOT), "--json"]
    # Without a controlling terminal and outside a harness, the rejection is DECLARED and refused.
    result = subprocess.run(command, capture_output=True, text=True, cwd=ROOT, stdin=subprocess.DEVNULL,
                            env={key: value for key, value in __import__("os").environ.items() if key != "CLAUDECODE"},
                            start_new_session=True)
    assert result.returncode != 0
    assert service.execution(identifier).data["status"] == "waiting-approval"
    assert json.dumps(service.execution(identifier).data["approvalRefusals"])


def test_every_record_names_the_same_gate(tmp_path: Path, monkeypatch):
    service = service_with(tmp_path)
    identifier = at_plan_gate(service)
    monkeypatch.setenv("CLAUDECODE", "1")
    with pytest.raises(PermissionError) as refused:
        service.approve_execution(identifier, approver="alice")
    assert f"aief execution approve {identifier}" in str(refused.value) and "approve-policy" not in str(refused.value)
    monkeypatch.delenv("CLAUDECODE")
    service.approve_execution(identifier, approver="alice")
    current = service.execution(identifier)
    approved = [event for event in events(service, identifier) if event["event"]["type"] == "gate.approved"]
    refusal_events = [event for event in events(service, identifier) if event["event"]["type"] == "gate.approval-refused"]
    assert current.data["approvalRefusals"][0]["gate"] == "plan-gate"
    assert refusal_events[0]["payload"]["gate"] == "plan-gate"
    assert approved[0]["payload"]["gate"] == "plan-gate" and approved[0]["payload"]["phase"] == "planning"
    assert current.data["gateDecisions"][0]["gate"] == "plan-gate"


def test_refused_rejection_points_to_the_reject_command(tmp_path: Path, monkeypatch):
    service = service_with(tmp_path)
    identifier = at_plan_gate(service)
    monkeypatch.setenv("CLAUDECODE", "1")
    with pytest.raises(PermissionError) as refused:
        service.reject_gate(identifier, "no", approver="alice")
    message = str(refused.value)
    assert f"aief execution reject {identifier} --gate plan-gate" in message
    assert "approve" not in message and "/approve" not in message


def test_session_approval_accepts_gate_or_phase_id(tmp_path: Path):
    from aief.approval_hook import awaited_approvals, select
    service = service_with(tmp_path)
    identifier = at_plan_gate(service)
    awaited = awaited_approvals(service)
    assert awaited == [{"execution": identifier, "gate": "plan-gate", "phase": "planning", "kind": "phase"}]
    assert select(["plan-gate"], awaited) == awaited and select(["planning"], awaited) == awaited
