"""Independent decision validator (tools/experiment/check_decisions.py) against the study decision rule."""
import importlib.util
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("check_decisions", ROOT / "tools" / "experiment" / "check_decisions.py")
validator = importlib.util.module_from_spec(spec); spec.loader.exec_module(validator)

RULE = "a" * 64
HUMAN = {"id": "approver-a", "type": "human", "channel": "interactive-terminal", "assurance": "OBSERVED"}


def evidence(outcome: str, *checks: tuple[str, str]) -> dict:
    return {"comparator": "test", "outcome": outcome,
            "checks": [{"item": item, "outcome": result} for item, result in checks]}


def decision(gate: str, outcome: str, ev: dict | None, rationale: str | None = None, actor: dict | None = HUMAN) -> dict:
    record = {"gate": gate, "decision": outcome, "decisionRule": {"sha256": RULE}}
    if ev is not None:
        record["evidence"] = ev
    if rationale is not None:
        record["rationale"] = rationale
    if actor is not None:
        record["actor"] = actor
    return record


def test_decisions_that_follow_the_rule_conform():
    cases = [
        decision("plan-gate", "approved", evidence("match", ("plan:frozen", "match"))),
        decision("before-commit", "rejected", evidence("mismatch", ("a", "mismatch"), ("b", "match"), ("c", "mismatch")),
                 "mismatch: c, a"),
        decision("apply-proposal", "rejected", evidence("incomplete", ("x", "unavailable"), ("y", "match")), "incomplete: x"),
        decision("before-external-action", "rejected", None, "no comparator for before-external-action"),
    ]
    for case in cases:
        assert validator.check_decision(case, RULE, ["approver-a"]) == [], case


def test_departures_from_the_rule_are_deviations():
    mismatch = evidence("mismatch", ("a", "mismatch"), ("b", "mismatch"))
    assert "rejected" in validator.check_decision(decision("g", "approved", mismatch), RULE, [])[0]
    assert "does not list exactly" in validator.check_decision(decision("g", "rejected", mismatch, "mismatch: a"), RULE, [])[0]
    assert "does not list exactly" in validator.check_decision(
        decision("g", "rejected", evidence("incomplete", ("x", "unavailable")), "mismatch: x"), RULE, [])[0]
    assert "approved" in validator.check_decision(decision("g", "rejected", evidence("match"), "looks risky"), RULE, [])[0]
    relayed = {**HUMAN, "channel": "agent-relay", "assurance": "DECLARED"}
    assert "OBSERVED interactive terminal" in validator.check_decision(decision("g", "approved", evidence("match"), actor=relayed), RULE, [])[0]
    assert "not a protocol approver" in validator.check_decision(decision("g", "approved", evidence("match")), RULE, ["approver-b"])[0]
    assert "not the pinned rule" in validator.check_decision(decision("g", "approved", evidence("match")), "b" * 64, [])[0]


def test_an_expired_gate_has_no_actor_and_is_operationally_invalid():
    expired = decision("before-merge", "expired", evidence("match"), actor=None)
    assert validator.check_decision(expired, RULE, ["approver-a"]) == []
    assert validator.classify(expired) == "operationally-invalid"


def test_rejections_are_classified_as_the_rule_states():
    assert validator.classify(decision("plan-gate", "rejected", evidence("mismatch", ("plan:frozen", "mismatch")))) == "setup-invalid"
    assert validator.classify(decision("plan-gate", "rejected", evidence("mismatch", ("plan:integrity", "mismatch")))) == "execution-failure"
    assert validator.classify(decision("g", "rejected", evidence("incomplete", ("x", "unavailable")))) == "execution-failure"
    assert validator.classify(decision("g", "rejected", None)) == "protocol-gap"


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=root, check=True,
                          capture_output=True, text=True).stdout.strip()


def test_a_before_merge_conflict_is_setup_invalid_only_when_the_base_branch_moved(tmp_path: Path):
    repo = tmp_path / "repo"; repo.mkdir()
    git(repo, "init", "-q", "-b", "main"); (repo / "f").write_text("1\n"); git(repo, "add", "-A"); git(repo, "commit", "-qm", "init")
    initial = {"main": git(repo, "rev-parse", "main")}
    conflict = decision("before-merge", "rejected", evidence("mismatch", ("main:merge:clean", "mismatch")), "mismatch: main:merge:clean")
    # The base branch is where the run started: the conflict comes from the execution.
    assert validator.classify(conflict, repo, initial) == "execution-failure"
    # Without the recorded heads the origin cannot be established.
    assert validator.classify(conflict) == "execution-failure"
    (repo / "f").write_text("2\n"); git(repo, "commit", "-qam", "maintainer")
    assert validator.classify(conflict, repo, initial) == "setup-invalid"
    # A missing task branch or a validated revision the task branch lacks stays with the execution.
    task = decision("before-merge", "rejected", evidence("mismatch", ("main:branch:aief/t", "mismatch")), "mismatch: main:branch:aief/t")
    assert validator.classify(task, repo, initial) == "execution-failure"


def test_cli_reads_a_launcher_run_and_fails_on_a_deviation(tmp_path: Path, capsys):
    run = tmp_path / "run"; (run / "aief").mkdir(parents=True)
    execution = {"metadata": {"id": "exec-1"}, "status": "completed",
                 "reproducibility": {"humanGateProtocol": {"value": {"approvers": ["approver-a"]}}},
                 "gateDecisions": [decision("plan-gate", "approved", evidence("match"))]}
    (run / "aief" / "execution.yaml").write_text(yaml.safe_dump(execution))
    assert validator.main([str(run), "--rule-sha256", RULE]) == 0
    execution["gateDecisions"].append(decision("before-commit", "approved", evidence("mismatch", ("a", "mismatch"))))
    (run / "aief" / "execution.yaml").write_text(yaml.safe_dump(execution))
    assert validator.main([str(run), "--rule-sha256", RULE]) == 1
    assert "DEVIATION" in capsys.readouterr().out


def test_gate_rule_v4_classifies_verification_frozen_and_refusals():
    frozen = decision("plan-gate", "rejected", evidence("mismatch", ("verification:frozen", "mismatch")), "mismatch: verification:frozen")
    assert validator.classify(frozen) == "execution-failure"
    assert validator.classify(frozen, version="v4") == "setup-invalid"
    cases = [({"reason": "x", "channel": "agent-relay"}, "agent"),
             ({"reason": "x", "channel": "non-interactive"}, "agent"),
             ({"reason": "an agent identity of this execution cannot approve its gates: a"}, "agent"),
             ({"reason": "x", "relayedBy": "codex:s"}, "agent"),
             ({"reason": "intruder is not an approver", "channel": "interactive-terminal"}, "operator"),
             ({"reason": "approval of plan-gate was not confirmed at the terminal"}, "unconfirmed"),
             ({"reason": "review waivers are disabled for this execution"}, "unattributed")]
    for refusal, expected in cases:
        assert validator.classify_refusal(refusal, "v4") == expected, refusal
        assert validator.classify_refusal(refusal) == "unclassified"
