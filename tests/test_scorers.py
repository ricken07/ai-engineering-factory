"""Study scorers H2–H4 (tools/experiment/score_h2.py, score_h3.py, score_h4.py) on synthetic runs."""
import hashlib
import importlib.util
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parents[1]


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / "experiment" / f"{name}.py")
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


h2, h3, h4 = load("score_h2"), load("score_h3"), load("score_h4")
TESTS = ["f2p::a", "p2p::b", "p2p::c", "p2p::d"]


def result(run: str, checks: dict, condition: str = "L0", status: str = "completed") -> dict:
    return {"runId": run, "task": "C01", "agent": "claude-code", "condition": condition,
            "evaluator": {"status": status}, "checks": checks}


ALL_PASS = {test: "PASS" for test in TESTS}


# --------------------------------------------------------------------------- H2

def test_h2_d_group_matches_a_hand_computed_value():
    runs = [result("r1", ALL_PASS),
            result("r2", {**ALL_PASS, "f2p::a": "FAIL"}),
            result("r3", {**ALL_PASS, "f2p::a": "FAIL", "p2p::b": "FAIL"})]
    block = h2.score(runs, {"C01": TESTS})[0]
    # D(r1,r2)=1/4, D(r1,r3)=2/4, D(r2,r3)=1/4 -> mean 1/3
    assert block["primary"]["outcome"] == "OBSERVED" and block["primary"]["dGroup"] == pytest.approx(1 / 3)
    assert block["K"] == 4 and block["pairs"] == 3


def test_h2_identical_runs_have_no_disagreement():
    assert h2.score([result("r1", ALL_PASS), result("r2", ALL_PASS)], {"C01": TESTS})[0]["primary"]["dGroup"] == 0


def test_h2_an_unavailable_component_makes_the_primary_block_score_missing():
    runs = [result("r1", ALL_PASS), result("r2", {**ALL_PASS, "p2p::d": "UNAVAILABLE"}), result("r3", ALL_PASS)]
    block = h2.score(runs, {"C01": TESTS})[0]
    assert block["primary"] == {"outcome": "MISSING", "dGroup": None, "reason": "unavailable components in runs r2"}
    secondary = {tuple(item["pair"]): item for item in block["secondaryAvailableChecks"]}
    assert secondary[("r1", "r2")] == {"pair": ["r1", "r2"], "d": 0.0, "denominator": 3}
    assert secondary[("r1", "r3")]["denominator"] == 4


def test_h2_an_evaluator_failure_is_unavailable_not_a_test_failure():
    runs = [result("r1", ALL_PASS), result("r2", {test: "FAIL" for test in TESTS}, status="failed")]
    block = h2.score(runs, {"C01": TESTS})[0]
    assert block["primary"]["outcome"] == "MISSING"
    assert block["secondaryAvailableChecks"][0]["denominator"] == 0


def test_h2_blocks_are_separated_by_task_agent_and_condition():
    runs = [result("a", ALL_PASS), result("b", ALL_PASS), result("c", ALL_PASS, condition="L3")]
    report = h2.score(runs, {"C01": TESTS})
    assert [(item["condition"], item["runs"], item["primary"]["outcome"]) for item in report] == [
        ("L0", 2, "OBSERVED"), ("L3", 1, "MISSING")]


# --------------------------------------------------------------------------- shared run fixtures

def run_dir(tmp_path: Path, condition: str = "L0", patch: str | None = "diff --git a/x.py b/x.py\n+y\n",
            execution: dict | None = None, **record) -> Path:
    root = tmp_path / "run"; root.mkdir(parents=True)
    steps = record.pop("steps", [{"startedAt": "2026-11-22T10:00:00+00:00", "endedAt": "2026-11-22T10:20:00+00:00",
                                  "durationSeconds": 1200.0}])
    data = {"experimentalCondition": condition, "environmentIdentifier": "env-1",
            "task": {"id": "C01", "startingCommit": "abc123"},
            "agent": {"name": "claude-code", "version": "2.1.295", "modelIdentifier": "claude-sonnet-5-5"},
            "steps": steps, **record}
    (root / "run.yaml").write_text(yaml.safe_dump(data))
    if patch is not None:
        (root / "final").mkdir(); (root / "final" / "workspace.patch").write_text(patch)
    if execution is not None:
        (root / "aief").mkdir(); (root / "aief" / "execution.yaml").write_text(yaml.safe_dump(execution))
    return root


# --------------------------------------------------------------------------- H3

def test_h3_built_in_items_are_verified_from_the_execution_time_capture(tmp_path: Path):
    root = run_dir(tmp_path)
    manifest = {"task": "C01", "baseRevision": "abc123", "environmentIdentifier": "env-1",
                "requiredItems": ["E01", "E02", "E03", "E04", "E10", "E11", "E12"]}
    report = h3.score(root, manifest)
    assert report["primary"]["verifiedEvidenceCompleteness"] == 1.0
    digest = hashlib.sha256((root / "final" / "workspace.patch").read_bytes()).hexdigest()
    assert report["items"]["E03"]["detail"] == f"sha256 {digest}"


def test_h3_manifest_items_without_observations_leave_the_primary_score_unavailable(tmp_path: Path):
    report = h3.score(run_dir(tmp_path))
    assert report["requiredItems"] == 12 and report["primary"]["outcome"] == "UNAVAILABLE"
    assert set(report["primary"]["unavailableItems"]) == {"E05", "E06", "E07", "E08", "E09"}


def test_h3_missing_evidence_lowers_the_score_and_evaluator_results_are_not_credited(tmp_path: Path):
    root = run_dir(tmp_path, patch=None, agent={"name": "codex", "version": "0.162.0", "modelIdentifier": None})
    observations = {"E05": {"status": "VERIFIED", "source": "execution"},
                    "E06": {"status": "VERIFIED", "source": "execution"},
                    "E07": {"status": "VERIFIED", "source": "evaluator"},
                    "E08": {"status": "MISSING", "source": "execution"},
                    "E09": {"status": "VERIFIED", "source": "execution"}}
    report = h3.score(root, {"task": "C01"}, observations)
    statuses = {item: value["status"] for item, value in report["items"].items()}
    assert statuses["E03"] == statuses["E04"] == statuses["E11"] == statuses["E07"] == statuses["E08"] == "MISSING"
    # verified: E01 E02 E05 E06 E09 E10 E12 = 7 of 12
    assert report["primary"]["verifiedEvidenceCompleteness"] == pytest.approx(7 / 12)


def test_h3_a_wrong_starting_revision_or_environment_is_not_credited(tmp_path: Path):
    report = h3.score(run_dir(tmp_path), {"baseRevision": "other", "environmentIdentifier": "env-2",
                                         "requiredItems": ["E02", "E12"]})
    assert report["primary"]["verifiedEvidenceCompleteness"] == 0.0


# --------------------------------------------------------------------------- H4

def decision(gate: str, start: str, end: str, availability: str = "OBSERVED", outcome: str = "approved") -> dict:
    return {"gate": gate, "decision": outcome, "waitStartedAt": start, "decidedAt": end,
            "waitDurationMs": {"value": 1, "availability": availability}}


def test_h4_l0_has_no_gate_wait_and_active_equals_wall_clock(tmp_path: Path):
    report = h4.score(run_dir(tmp_path))
    assert report["primary"]["wallClockSeconds"] == 1200.0 and report["activeWallClockSeconds"] == 1200.0
    assert report["gateWait"]["seconds"] == "NOT_APPLICABLE" and report["humanInterventions"] == "NOT_APPLICABLE"


def test_h4_l3_subtracts_the_union_of_gate_waits_and_includes_before_merge(tmp_path: Path):
    steps = [{"startedAt": "2026-11-22T10:00:00+00:00", "endedAt": "2026-11-22T10:10:00+00:00", "durationSeconds": 600.0},
             {"startedAt": "2026-11-22T10:30:00+00:00", "endedAt": "2026-11-22T10:50:00+00:00", "durationSeconds": 1200.0}]
    execution = {"metrics": {"execution": {"completedAt": "2026-11-22T10:55:00+00:00"},
                             "runtime": {"durationMs": {"value": 5000, "availability": "OBSERVED"}},
                             "validation": {"durationMs": {"value": None, "availability": "UNAVAILABLE"}}},
                 "reworks": [{"number": 1}],
                 "gateDecisions": [
                     decision("plan-gate", "2026-11-22T10:10:00+00:00", "2026-11-22T10:25:00+00:00"),
                     # overlapping policy gates at submission count once
                     decision("before-commit", "2026-11-22T10:40:00+00:00", "2026-11-22T10:45:00+00:00"),
                     decision("before-submission", "2026-11-22T10:42:00+00:00", "2026-11-22T10:47:00+00:00"),
                     decision("before-merge", "2026-11-22T10:55:00+00:00", "2026-11-22T11:05:00+00:00", "DERIVED")],
                 "approvalRefusals": [{"gate": "before-merge"}]}
    report = h4.score(run_dir(tmp_path, condition="L3", steps=steps, execution=execution))
    # terminal = before-merge decision 11:05; wall = 65 min; waits = 15 + 7 + 10 = 32 min
    assert report["primary"]["wallClockSeconds"] == 3900.0
    assert report["gateWait"] == {"seconds": 1920.0, "intervals": 4, "provenance": "DERIVED"}
    assert report["activeWallClockSeconds"] == 1980.0 and report["agentProcessSeconds"] == 1800.0
    assert report["runtime"] == {"ms": 5000, "availability": "OBSERVED"}
    assert report["validation"]["availability"] == "UNAVAILABLE"
    assert report["reworks"] == 1 and report["humanInterventions"] == 5


def test_h4_an_unknown_wait_is_never_counted_as_zero(tmp_path: Path):
    execution = {"gateDecisions": [{"gate": "plan-gate", "decision": "approved", "waitStartedAt": None,
                                    "decidedAt": "2026-11-22T10:05:00+00:00"}]}
    report = h4.score(run_dir(tmp_path, condition="L3", execution=execution))
    assert report["gateWait"]["provenance"] == "UNAVAILABLE" and report["activeWallClockSeconds"] is None
    assert report["primary"]["wallClockSeconds"] == 1200.0


def test_h4_reports_a_reached_resource_limit(tmp_path: Path):
    assert h4.score(run_dir(tmp_path, resourceLimitReached=True))["resourceLimitReached"] is True
