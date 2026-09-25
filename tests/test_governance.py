from pathlib import Path
import copy

import pytest

from aief.governance import assert_action_authorized, governed_execution_plan
from aief.policy import evaluate_runtime_policy
from aief.validation import assert_schema

ROOT = Path(__file__).parents[1]


def _task(policy=None):
    return {"metadata":{"id":"TASK-1"}, "classification":{"risk":"low","domains":[],"changeTypes":["source-code"]},
            "scope":{"repositories":["main"]}, "autonomy":{"requested":"L4"}, **({"policy":policy} if policy else {})}


def _project(policy=None):
    return {"autonomy":{"default":"L4","maximum":"L4"}, "repositories":[{"id":"main","profiles":["generic"]}],
            "engineering":{"organizationCatalogs":["sample-organization@1.0.0"]}, **({"policy":policy} if policy else {})}


def test_organization_and_lower_layers_are_additive_and_non_bypassable():
    project = _project({"maximumAutonomy":"L3", "requiredGates":["project-gate"]})
    task = _task({"deniedActions":["push"], "requiredGates":["task-gate"], "maximumAutonomy":"L4"})
    project["repositories"][0]["policy"] = {"maximumAutonomy":"L2", "deniedActions":["merge"]}
    result = evaluate_runtime_policy(ROOT, project, task, {"repositories":["main"],"domains":[],"changeTypes":["source-code"]})
    assert result["authorizedAutonomy"] == "L2"
    assert set(result["requiredGates"]) >= {"project-gate", "task-gate"}
    assert set(result["deniedActions"]) >= {"push", "merge"}
    assert [item["source"] for item in result["provenance"]][-3:] == ["project", "repository:main", "task"]


def test_plan_is_deterministic_and_policy_change_changes_fingerprint():
    execution = {"metadata":{"id":"EXEC-1"},"task":"TASK-1","workflow":{"id":"implement-task","version":"1.0.0"}}
    decision = evaluate_runtime_policy(ROOT, _project(), _task(), {"repositories":["main"],"domains":[],"changeTypes":["source-code"]})
    first = governed_execution_plan("aief.dev/v1alpha1", execution, decision, "policy-decision-001.yaml")
    second = governed_execution_plan("aief.dev/v1alpha1", execution, decision, "policy-decision-001.yaml")
    assert first == second
    assert_schema(ROOT, "governed-execution-plan.schema.json", first)
    restricted = copy.deepcopy(decision); restricted["deniedActions"] = sorted(set(restricted["deniedActions"]) | {"push"})
    changed = governed_execution_plan("aief.dev/v1alpha1", execution, restricted, "policy-decision-001.yaml")
    assert changed["fingerprint"] != first["fingerprint"]


def test_denied_action_is_rejected_at_runtime_enforcement_boundary():
    execution = {"metadata":{"id":"EXEC-1"},"task":"TASK-1","workflow":{"id":"implement-task","version":"1.0.0"}}
    decision = evaluate_runtime_policy(ROOT, _project(), _task({"deniedActions":["push"]}), {"repositories":["main"],"domains":[],"changeTypes":["source-code"]})
    plan = governed_execution_plan("aief.dev/v1alpha1", execution, decision, "policy.yaml")
    with pytest.raises(PermissionError, match="denied"):
        assert_action_authorized(plan, "push")
