from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from aief.approval_hook import handle
from aief.payload_ledger import brief_sections
from aief.service import MAX_PLAN_REVISIONS
from aief.timing import FakeClock
from aief.validation import assert_schema
from test_gate_protocol import CRITERIA, at_bound_plan_gate, at_plan_gate, bound_files, events, output, service_with


ROOT = Path(__file__).parents[1]
FEEDBACK = "Use the existing operator capability registry instead of a configuration flag."


def replan(service, identifier: str, summary: str = "Revised plan") -> None:
    service.prepare_phase(identifier)
    service.complete_phase(identifier, output(summary, {"repositories": ["main"], "acceptanceCriteria": CRITERIA}))


def test_the_human_asks_for_changes_and_the_revised_plan_waits_at_the_same_gate(tmp_path: Path):
    service = service_with(tmp_path)
    identifier = at_plan_gate(service)
    first_plan = (service.execution(identifier).root / "planning.yaml").read_text()
    service.revise_plan(identifier, FEEDBACK, approver="alice")

    current = service.execution(identifier)
    phase = current.next_phase()
    assert (current.data["status"], phase["id"], phase["status"]) == ("running", "planning", "pending")
    assert phase["revision"] == {"number": 1, "feedback": FEEDBACK, "requestedBy": "alice",
                                 "history": [{"number": 1, "feedback": FEEDBACK, "plan": "planning-revision-1.yaml"}]}
    assert "gateTiming" not in phase and phase["artifacts"] == []
    revision = current.data["planRevisions"][0]
    assert "planning-revision-1.yaml" in revision["archived"]
    assert (current.root / "planning-revision-1.yaml").read_text() == first_plan
    assert revision["gateTiming"]["decidedAt"] and revision["actor"]["assurance"] == "OBSERVED"
    decision = current.data["gateDecisions"][-1]
    assert (decision["gate"], decision["decision"], decision["rationale"]) == ("plan-gate", "changes-requested", FEEDBACK)
    assert decision["actor"]["id"] == "alice"
    assert_schema(ROOT, "execution.schema.json", current.data)
    assert "gate.changes-requested" in [event["event"]["type"] for event in events(service, identifier)]

    prepared = service.prepare_phase(identifier)
    brief = (current.root / "phase-brief-planning.md").read_text()
    assert "## Plan revision 1: changes the human asked for" in brief and f"> {FEEDBACK}" in brief
    assert {"plan-revision": "human-decision"}.items() <= {item["id"]: item["classification"]
                                                          for item in brief_sections(brief)}.items()
    assert prepared["phase"]["id"] == "planning"
    service.complete_phase(identifier, output("Revised plan", {"repositories": ["main"], "acceptanceCriteria": CRITERIA}))
    current = service.execution(identifier)
    assert current.data["status"] == "waiting-approval" and current.next_phase()["gateTiming"]["blockedAt"]

    service.approve_execution(identifier, approver="alice")
    current = service.execution(identifier)
    assert current.data["status"] == "running" and current.next_phase()["id"] == "implementation"
    assert [item["decision"] for item in current.data["gateDecisions"]] == ["changes-requested", "approved"]
    assert_schema(ROOT, "execution.schema.json", current.data)


def test_a_second_revision_sees_every_earlier_plan_and_feedback(tmp_path: Path):
    service = service_with(tmp_path)
    identifier = at_plan_gate(service)
    service.revise_plan(identifier, FEEDBACK, approver="alice")
    replan(service, identifier)
    service.revise_plan(identifier, "Keep the status inquiries unrestricted.", approver="alice")
    service.prepare_phase(identifier)
    current = service.execution(identifier)
    brief = (current.root / "phase-brief-planning.md").read_text()
    assert "## Plan revision 2:" in brief and "> Keep the status inquiries unrestricted." in brief
    assert f"- Revision 1: `planning-revision-1.yaml`, superseded by: {FEEDBACK}" in brief
    assert "- Revision 2: `planning-revision-2.yaml`, superseded by: Keep the status inquiries unrestricted." in brief
    assert {"planning-revision-1.yaml", "planning-revision-2.yaml"} <= {path.name for path in current.root.iterdir()}
    assert_schema(ROOT, "execution.schema.json", current.data)


def test_the_response_limit_applies_to_the_revised_plan_from_its_own_wait(tmp_path: Path):
    clock = FakeClock(datetime(2026, 11, 21, 9, 0, tzinfo=timezone.utc))
    service = service_with(tmp_path, {"responseLimitMinutes": 30}, clock=clock)
    identifier = at_plan_gate(service)
    clock.advance(milliseconds=25 * 60_000)
    service.revise_plan(identifier, FEEDBACK, approver="alice")
    clock.advance(milliseconds=10 * 60_000)
    replan(service, identifier)
    clock.advance(milliseconds=20 * 60_000)
    # 55 minutes after the first wait started, 20 after the revised plan's.
    service.approve_execution(identifier, approver="alice")
    assert service.execution(identifier).data["status"] == "running"


def test_a_relayed_revision_is_refused_and_kept(tmp_path: Path):
    service = service_with(tmp_path)
    identifier = at_plan_gate(service)
    service.lease(identifier, "acquire", "claude-code:session-1")
    with pytest.raises(PermissionError, match="not agent-relay"):
        service.revise_plan(identifier, FEEDBACK, owner="claude-code:session-1")
    current = service.execution(identifier)
    assert current.next_phase()["status"] == "waiting-approval" and "planRevisions" not in current.data
    assert current.data["approvalRefusals"][0]["channel"] == "agent-relay"


def test_revision_needs_feedback_and_a_waiting_plan(tmp_path: Path):
    service = service_with(tmp_path)
    identifier = at_plan_gate(service)
    with pytest.raises(ValueError, match="changes to make"):
        service.revise_plan(identifier, "  ", approver="alice")
    service.approve_execution(identifier, approver="alice")
    with pytest.raises(RuntimeError, match="no plan is waiting"):
        service.revise_plan(identifier, FEEDBACK, approver="alice")


def test_revisions_are_bounded(tmp_path: Path):
    service = service_with(tmp_path)
    identifier = at_plan_gate(service)
    for _ in range(MAX_PLAN_REVISIONS):
        service.revise_plan(identifier, FEEDBACK, approver="alice")
        replan(service, identifier)
    with pytest.raises(RuntimeError, match=f"already revised {MAX_PLAN_REVISIONS} times"):
        service.revise_plan(identifier, FEEDBACK, approver="alice")
    assert service.execution(identifier).data["status"] == "waiting-approval"


def test_a_bound_plan_cannot_be_revised(tmp_path: Path):
    service = service_with(tmp_path)
    plan, spec = bound_files(tmp_path)
    identifier = at_bound_plan_gate(service, plan, spec)
    with pytest.raises(PermissionError, match="bound"):
        service.revise_plan(identifier, FEEDBACK, approver="alice")
    current = service.execution(identifier)
    assert current.data["status"] == "waiting-approval" and "planRevisions" not in current.data
    assert "bound" in current.data["approvalRefusals"][0]["reason"]


def test_the_hook_delivers_a_revise_typed_in_the_session(tmp_path: Path):
    service = service_with(tmp_path)
    identifier = at_plan_gate(service)
    code, out, err = handle({"prompt": "/revise"}, "claude-code", lambda cwd: service)
    assert code == 2 and out == "" and "say what to change" in err and identifier in err
    code, out, err = handle({"prompt": f"$revise {identifier} {FEEDBACK}", "session_id": "s-9"}, "codex",
                            lambda cwd: service)
    assert (code, err) == (0, "") and "AIEF: the human asked" in out and "revision 1" in out
    current = service.execution(identifier)
    decision = current.data["gateDecisions"][-1]
    assert (decision["decision"], decision["actor"]["channel"], decision["rationale"]) == \
        ("changes-requested", "harness-hook", FEEDBACK)
    code, out, err = handle({"prompt": f"/revise {FEEDBACK}"}, "claude-code", lambda cwd: service)
    assert code == 2 and "no plan of this project is waiting" in err
    assert handle({"prompt": "please revise the plan"}, "claude-code", lambda cwd: service) == (0, "", "")


def test_agents_may_not_run_the_revision_command(tmp_path: Path):
    from aief.approval_hook import install
    root = tmp_path / "project"; root.mkdir()
    settings = yaml.safe_load(install(root, "claude-code").read_text())
    assert "Bash(aief execution revise-plan *)" in settings["permissions"]["deny"]
    install(root, "codex")
    assert '"revise-plan"' in (root / ".codex/rules/aief-approval.rules").read_text()
