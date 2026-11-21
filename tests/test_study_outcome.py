"""Study outcome mapping (tools/experiment/study_outcome.py): Runtime facts to study outcomes, without rewriting them."""
import importlib.util
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("study_outcome", ROOT / "tools" / "experiment" / "study_outcome.py")
mapping = importlib.util.module_from_spec(spec); spec.loader.exec_module(mapping)

RULE = "a" * 64
HUMAN = {"id": "approver-a", "type": "human", "channel": "interactive-terminal", "assurance": "OBSERVED"}


def gate(name: str, outcome: str, comparator: str = "match", items=(), rationale=None, actor=HUMAN) -> dict:
    record = {"gate": name, "decision": outcome, "decisionRule": {"sha256": RULE},
              "evidence": {"comparator": "test", "outcome": comparator,
                           "checks": [{"item": item, "outcome": "mismatch"} for item in items]}}
    if rationale:
        record["rationale"] = rationale
    if actor:
        record["actor"] = actor
    return record


def execution(status: str, *decisions: dict, **extra) -> dict:
    return {"metadata": {"id": "exec-1"}, "status": status,
            "reproducibility": {"reviewWaivers": {"value": "disabled"},
                                "humanGateProtocol": {"value": {"approvers": ["approver-a"]}}},
            "gateDecisions": list(decisions), **extra}


def run_dir(tmp_path: Path, data: dict) -> Path:
    run = tmp_path / "run"; (run / "aief").mkdir(parents=True, exist_ok=True)
    (run / "aief" / "execution.yaml").write_text(yaml.safe_dump(data))
    return run


def classify(tmp_path: Path, data: dict) -> tuple[str, str]:
    result = mapping.classify_run(run_dir(tmp_path, data), RULE)
    return result["outcome"], result["reason"]


APPROVED_PLAN = gate("plan-gate", "approved")


def test_completed_execution_and_integration(tmp_path: Path):
    assert classify(tmp_path, execution("completed", APPROVED_PLAN))[0] == "completed"
    integrated = execution("completed", APPROVED_PLAN, gate("before-merge", "approved"), integration={"status": "integrated"})
    assert classify(tmp_path, integrated) == ("completed", "completed and integrated")


def test_rejections_and_expiry_take_the_rule_classification(tmp_path: Path):
    frozen = gate("plan-gate", "rejected", "mismatch", ["plan:frozen"], "mismatch: plan:frozen")
    assert classify(tmp_path, execution("cancelled", frozen))[0] == "setup-invalid"
    other = gate("before-commit", "rejected", "mismatch", ["required-enforcement"], "mismatch: required-enforcement")
    assert classify(tmp_path, execution("cancelled", APPROVED_PLAN, other))[0] == "execution-failure"
    expired = gate("plan-gate", "expired", actor=None)
    result = mapping.classify_run(run_dir(tmp_path / "x", execution("cancelled", expired)), RULE)
    assert result["outcome"] == "operationally-invalid" and result["replayEligible"] is True


def test_protocol_deviations_come_first(tmp_path: Path):
    approved_mismatch = gate("before-commit", "approved", "mismatch", ["a"])
    assert classify(tmp_path, execution("completed", approved_mismatch))[0] == "protocol-deviation"
    waived = execution("completed", APPROVED_PLAN, findingDecisions=[{"finding": 1}])
    assert classify(tmp_path / "w", waived) == ("protocol-deviation", "a review finding was waived")
    enabled = execution("completed", APPROVED_PLAN); enabled["reproducibility"]["reviewWaivers"]["value"] = "enabled"
    assert classify(tmp_path / "e", enabled)[0] == "protocol-deviation"
    cancelled = execution("cancelled", APPROVED_PLAN, cancelledReason="operator cancelled")
    assert classify(tmp_path / "c", cancelled)[0] == "protocol-deviation"


def test_blocked_failed_and_unfinished_executions(tmp_path: Path):
    rework = execution("blocked", APPROVED_PLAN, blockingReason={"type": "review-rework-exhausted"})
    assert classify(tmp_path / "r", rework) == ("execution-failure", "blocked: review-rework-exhausted")
    enforcement = execution("blocked", APPROVED_PLAN, blockingReason={"type": "enforcement-unavailable"})
    assert classify(tmp_path / "f", enforcement)[0] == "setup-invalid"
    assert classify(tmp_path / "x", execution("failed", APPROVED_PLAN))[0] == "execution-failure"
    assert classify(tmp_path / "s", execution("running", APPROVED_PLAN))[0] == "execution-failure"
    assert classify(tmp_path / "w", execution("waiting-approval"))[0] == "incomplete"
    awaiting = execution("completed", APPROVED_PLAN, integration={"status": "awaiting-approval"})
    assert classify(tmp_path / "a", awaiting)[0] == "incomplete"


def test_the_mapping_never_rewrites_the_runtime_records(tmp_path: Path):
    data = execution("cancelled", gate("plan-gate", "rejected", "mismatch", ["plan:frozen"], "mismatch: plan:frozen"))
    run = run_dir(tmp_path, data)
    before = (run / "aief" / "execution.yaml").read_bytes()
    assert mapping.main([str(run), "--rule-sha256", RULE, "--write"]) == 0
    assert (run / "aief" / "execution.yaml").read_bytes() == before
    written = yaml.safe_load((run / "study-outcome.yaml").read_text())
    assert written["outcome"] == "setup-invalid" and written["runtimeFacts"]["status"] == "cancelled"
    assert written["mappingVersion"] == mapping.MAPPING_VERSION


def test_a_run_without_collected_records_is_incomplete(tmp_path: Path):
    (tmp_path / "run").mkdir()
    assert mapping.classify_run(tmp_path / "run", RULE)["outcome"] == "incomplete"
