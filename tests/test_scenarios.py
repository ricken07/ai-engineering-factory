from pathlib import Path
import json

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from aief.scenarios import (
    SCENARIOS,
    ENGINEERING_OUTCOME_DIMENSIONS,
    format_report,
    pending_engineering_outcome,
    run_adapter_conformance,
    run_all_level1,
    run_all_level2,
    run_scenario,
)

ROOT = Path(__file__).parents[1]


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_level1_runtime_conformance_scenario_passes(name: str, tmp_path: Path):
    result = run_scenario(name, ROOT, tmp_path)
    assert result.status == "PASS", f"{name}: expected {result.expected!r}, observed {result.observed!r}"


def test_level1_report_has_no_failures_and_covers_every_scenario(tmp_path: Path):
    results = run_all_level1(ROOT, tmp_path)
    assert {r.scenario for r in results} == set(SCENARIOS)
    assert all(r.status == "PASS" for r in results)


@pytest.mark.parametrize("name", sorted(SCENARIOS))
def test_level2_adapter_conformance_scenario_passes(name: str, tmp_path: Path):
    result = run_adapter_conformance(name, ROOT, tmp_path)
    assert result.status == "PASS", f"{name}: {result.observed}"


def test_level2_report_covers_every_scenario(tmp_path: Path):
    results = run_all_level2(ROOT, tmp_path)
    assert {r.scenario for r in results} == set(SCENARIOS)
    assert all(r.status == "PASS" for r in results)


def test_a_genuine_runtime_regression_is_reported_as_fail_not_silently_skipped(tmp_path: Path):
    from aief.scenarios import Scenario, run_scenario as _run

    def _broken(factory, workdir, agent):
        raise RuntimeError("simulated Runtime regression")

    SCENARIOS["__test_broken__"] = Scenario(
        "__test_broken__", "given", "when", "then", _broken, lambda observed: True,
    )
    try:
        result = _run("__test_broken__", ROOT, tmp_path)
    finally:
        del SCENARIOS["__test_broken__"]
    assert result.status == "FAIL"
    assert "simulated Runtime regression" in result.observed


def test_report_is_a_simple_table_with_the_five_required_columns(tmp_path: Path):
    results = run_all_level1(ROOT, tmp_path)
    report = format_report(results[:2])
    header = report.splitlines()[0]
    for column in ("Scenario", "Expected", "Observed", "Status", "Evidence"):
        assert column in header
    assert "|" not in report  # a plain table, not a markup dashboard


def test_engineering_outcome_is_a_contract_only_with_no_measurement(tmp_path: Path):
    registry = Registry(); schemas = {}
    for path in (ROOT / "core/schemas").glob("*.json"):
        schema = json.loads(path.read_text())
        schemas[path.name] = schema
        registry = registry.with_resource(schema["$id"], Resource.from_contents(schema))
    validator = Draft202012Validator(schemas["engineering-outcome.schema.json"], registry=registry)
    outcome = pending_engineering_outcome("simple-feature", "claude-code")
    assert not list(validator.iter_errors(outcome))
    assert set(outcome["dimensions"]) == set(ENGINEERING_OUTCOME_DIMENSIONS)
    assert all(dimension["status"] == "not_evaluated" for dimension in outcome["dimensions"].values())


def test_scenarios_are_reproducible_across_independent_runs(tmp_path: Path):
    first = run_scenario("high-risk-change", ROOT, tmp_path / "first")
    second = run_scenario("high-risk-change", ROOT, tmp_path / "second")
    assert first.status == second.status == "PASS"
    assert first.observed == second.observed
