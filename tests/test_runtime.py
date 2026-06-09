import yaml
from aief.runtime import Execution

def test_execution_persists_resumes_and_handoffs(tmp_path):
    workflow = {"metadata":{"id":"demo"},"phases":[{"id":"read","skill":"understand-task"},{"id":"write","skill":"implement-change","gate":{"id":"approval"}}]}
    execution = Execution.create(tmp_path, workflow, "TASK-1")
    assert execution.advance({"summary":"ok"}) == "running"
    assert execution.advance() == "waiting-approval"
    resumed = Execution.load(execution.root)
    assert resumed.advance(approved=True) == "completed"
    assert yaml.safe_load(resumed.handoff().read_text())["status"] == "completed"

def test_bounded_recovery_requires_distinct_attempts_and_persists_answer(tmp_path):
    workflow = {"metadata":{"id":"demo"},"phases":[{"id":"work","skill":"implement-change","recovery":{"minimumAttempts":2,"maximumAttempts":3}}]}
    execution = Execution.create(tmp_path, workflow, "TASK-2")
    execution.record_attempt("failure", "hypothesis-1", "action-1", "failed")
    try: execution.record_attempt("failure", "hypothesis-1", "action-1", "failed")
    except ValueError: pass
    else: raise AssertionError("identical retry accepted")
    execution.record_attempt("failure", "hypothesis-2", "action-2", "failed")
    execution.ask_user("Which behavior is authoritative?")
    execution.answer_user_question("Use the documented behavior")
    assert Execution.load(execution.root).next_phase()["recovery"]["answer"] == "Use the documented behavior"

def test_gate_cannot_be_approved_before_phase_evidence_exists(tmp_path):
    workflow = {"metadata":{"id":"demo"},"phases":[{"id":"plan","skill":"create-plan","gate":{"id":"approval","type":"human-approval"}}]}
    execution = Execution.create(tmp_path, workflow, "TASK-3")
    try: execution.advance(approved=True)
    except RuntimeError as error: assert "waiting for approval" in str(error)
    else: raise AssertionError("gate was approved before reaching the gate")
