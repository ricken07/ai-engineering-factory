from pathlib import Path

import pytest
import yaml

from aief.concurrency import ExecutionLease, IdempotencyConflict, LeaseConflict, OperationJournal
from aief.project import initialize
from aief.service import RuntimeService


def service_and_execution(tmp_path: Path, request: str = "/analyze DEMO-1"):
    project=tmp_path/"project"; initialize(Path("templates/project"),project)
    service=RuntimeService(project,Path(".")); execution=service.start(request,"codex")
    return service,execution


def valid_understanding():
    return yaml.safe_load(Path("core/skills/understand-task/examples/output.yaml").read_text())


def test_execution_lease_prevents_second_agent_and_supports_renew_release(tmp_path: Path):
    _,execution=service_and_execution(tmp_path)
    lease=ExecutionLease(execution.root)
    first=lease.acquire("codex:session-1",60)
    assert first["owner"] == "codex:session-1"
    with pytest.raises(LeaseConflict,match="leased by codex:session-1"):
        lease.acquire("claude:session-2",60)
    assert lease.renew("codex:session-1",120)["owner"] == "codex:session-1"
    assert lease.release("codex:session-1")["status"] == "released"
    assert lease.acquire("claude:session-2",60)["owner"] == "claude:session-2"


def test_mutation_requires_active_lease_owner(tmp_path: Path):
    service,execution=service_and_execution(tmp_path)
    service.lease(execution.data["metadata"]["id"],"acquire","codex:one")
    with pytest.raises(PermissionError,match="owner is required"):
        service.complete_phase(execution.data["metadata"]["id"],valid_understanding())
    with pytest.raises(LeaseConflict,match="leased by codex:one"):
        service.complete_phase(execution.data["metadata"]["id"],valid_understanding(),owner="claude:two")


def test_complete_phase_replay_does_not_advance_twice(tmp_path: Path):
    service,execution=service_and_execution(tmp_path)
    identifier=execution.data["metadata"]["id"]; output=valid_understanding()
    first=service.complete_phase(identifier,output,"complete-understand-1")
    assert first.next_phase()["id"] == "resolve-context"
    second=service.complete_phase(identifier,output,"complete-understand-1")
    assert second.next_phase()["id"] == "resolve-context"
    assert len(list((execution.root/"operations").glob("*.yaml"))) == 1


def test_operation_id_cannot_be_reused_with_different_input(tmp_path: Path):
    service,execution=service_and_execution(tmp_path); identifier=execution.data["metadata"]["id"]
    service.complete_phase(identifier,valid_understanding(),"same-operation")
    changed={**valid_understanding(),"summary":"different valid summary"}
    with pytest.raises(IdempotencyConflict,match="different input"):
        service.complete_phase(identifier,changed,"same-operation")


def test_gate_approval_replay_is_single_transition(tmp_path: Path):
    workflow={"metadata":{"id":"demo","version":"1.0.0"},"phases":[{"id":"plan","skill":"create-plan","gate":{"id":"before-implementation","type":"human-approval"}},{"id":"next","skill":"implement-change"}]}
    from aief.runtime import Execution
    execution=Execution.create(tmp_path,workflow,"TASK-1"); execution.advance({"summary":"plan"})
    service=object.__new__(RuntimeService); service.project_root=tmp_path
    identifier=execution.data["metadata"]["id"]
    service.approve_execution(identifier,"approve-plan-1")
    assert service.execution(identifier).next_phase()["id"] == "next"
    service.approve_execution(identifier,"approve-plan-1")
    assert service.execution(identifier).next_phase()["id"] == "next"


def test_failed_journal_operation_can_retry_but_running_cannot(tmp_path: Path):
    root=tmp_path/"execution"; root.mkdir(); journal=OperationJournal(root); attempts=[]
    def action():
        attempts.append(1)
        if len(attempts)==1: raise RuntimeError("transient")
        return {"ok":True}
    with pytest.raises(RuntimeError): journal.execute("retry-1","complete-phase",{"x":1},action)
    assert journal.execute("retry-1","complete-phase",{"x":1},action)[0] == {"ok":True}


def test_handoff_releases_ownership_for_another_agent(tmp_path: Path):
    service,execution=service_and_execution(tmp_path); identifier=execution.data["metadata"]["id"]
    service.lease(identifier,"acquire","codex:one")
    assert service.handoff_execution(identifier,"codex:one").is_file()
    assert service.lease(identifier,"acquire","claude:two")["owner"] == "claude:two"


def test_lease_and_runtime_operation_artifacts_validate(tmp_path: Path):
    from aief.validation import assert_schema
    service,execution=service_and_execution(tmp_path); identifier=execution.data["metadata"]["id"]
    service.lease(identifier,"acquire","codex:one")
    service.complete_phase(identifier,valid_understanding(),"complete-understand-validate",owner="codex:one")
    lease=yaml.safe_load((execution.root/"lease.yaml").read_text())
    operation=yaml.safe_load((execution.root/"operations/complete-understand-validate.yaml").read_text())
    assert_schema(Path("."),"execution-lease.schema.json",lease)
    assert_schema(Path("."),"runtime-operation.schema.json",operation)
