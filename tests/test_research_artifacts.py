from pathlib import Path

from aief.evidence import experimental_metrics
from aief.scenarios import evaluation_run
from aief.validation import assert_schema

ROOT = Path(__file__).parents[1]


def test_evaluation_conditions_are_structured_and_repeatable():
    run = evaluation_run("L3", 2, "TASK-1", "repo", "abc", "codex", ["AC-1"], {"os":"test"})
    assert_schema(ROOT, "evaluation-run.schema.json", run)
    assert run["level"] == "L3" and run["repeat"] == 2


def test_metrics_distinguish_observed_from_unavailable(tmp_path):
    execution={"metadata":{"id":"EXEC-1"},"task":"TASK-1","policyGates":[]}
    metrics=experimental_metrics(tmp_path, execution)["metrics"]
    assert metrics["validationCount"]["availability"] == "observed"
    assert metrics["tokenUsage"] == {"value":None,"availability":"unavailable"}
