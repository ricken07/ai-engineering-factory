from datetime import datetime, timezone
from pathlib import Path

from aief.approval_hook import pending_actions, render_pending
from aief.cli import main
from aief.timing import FakeClock
from test_approval_hook import proposed
from test_dynamic_policy import FINDINGS, reviewed
from test_gate_protocol import at_plan_gate, service_with


def kinds(service) -> list[tuple[str, str, str | None]]:
    return [(item["execution"], item["kind"], item.get("gate")) for item in pending_actions(service)]


def test_a_project_without_executions_waits_for_nothing(tmp_path: Path):
    service = service_with(tmp_path)
    assert pending_actions(service) == []
    assert render_pending([]) == "Nothing waits for a human in this project.\n"


def test_a_plan_at_its_gate_lists_approve_revise_and_reject(tmp_path: Path):
    service = service_with(tmp_path)
    identifier = at_plan_gate(service)
    [action] = pending_actions(service)
    assert (action["execution"], action["kind"], action["gate"]) == (identifier, "plan", "plan-gate")
    assert action["session"] == [f"/approve {identifier} plan-gate", f"/revise {identifier} <changes>"]
    assert action["terminal"] == [f"aief execution approve {identifier}",
                                  f"aief execution revise-plan {identifier} --feedback <changes>",
                                  f"aief execution reject {identifier} --reason <rationale>"]


def test_a_policy_gate_and_the_lease_that_holds_the_execution_are_listed(tmp_path: Path):
    service, identifier, _ = proposed(tmp_path)
    service.lease(identifier, "acquire", "codex:session-1")
    assert kinds(service) == [(identifier, "approval", "apply-proposal"), (identifier, "lease", None)]
    approval, lease = pending_actions(service)
    assert approval["terminal"][0] == f"aief execution approve-policy {identifier} apply-proposal"
    assert approval["terminal"][1].endswith("--gate apply-proposal")
    assert lease["terminal"] == [f"aief execution handoff {identifier} --owner codex:session-1"]
    service.lease(identifier, "release", "codex:session-1")
    assert kinds(service) == [(identifier, "approval", "apply-proposal")]


def test_blocking_review_findings_are_listed_with_the_waive_commands(tmp_path: Path):
    service, identifier, review = reviewed(tmp_path, "changes_requested", FINDINGS)
    service.complete_phase(identifier, review)
    [action] = pending_actions(service)
    assert action["kind"] == "findings" and "1. P1 AC-1 (Guard.java:34)" in action["detail"]
    assert action["session"] == [f"/waive {identifier} <finding-number> <justification>"]
    for number in (1, 2):
        service.waive_finding(identifier, number, "out of scope", approver="alice")
    assert all(item["kind"] != "findings" for item in pending_actions(service))


def test_a_question_of_the_agent_is_listed(tmp_path: Path):
    service, identifier, _ = reviewed(tmp_path, "approved", [])
    service.ask_user(identifier, "Which registry holds the operators?", requires_authority=True)
    [action] = pending_actions(service)
    assert action["kind"] == "question" and "Which registry holds the operators?" in action["detail"]


def test_an_expired_gate_is_applied_not_listed(tmp_path: Path):
    clock = FakeClock(datetime(2026, 11, 21, 9, 0, tzinfo=timezone.utc))
    service = service_with(tmp_path, {"responseLimitMinutes": 30}, clock)
    identifier = at_plan_gate(service)
    [action] = pending_actions(service)
    assert action["deadline"] is not None and "(expires " in render_pending([action])
    clock.advance(milliseconds=31 * 60_000)
    assert pending_actions(service) == []
    assert service.execution(identifier).data["status"] == "cancelled"


def test_the_cli_prints_the_actions(tmp_path: Path, capsys):
    service = service_with(tmp_path)
    identifier = at_plan_gate(service)
    assert main(["execution", "pending", "--project", str(service.project_root),
                 "--factory", str(service.factory)]) == 0
    out = capsys.readouterr().out
    assert out.startswith(f"{identifier}  plan  plan-gate") and f"session:  /revise {identifier} <changes>" in out
