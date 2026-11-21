"""Waiver-policy boundaries for scored AIEF research executions."""
from pathlib import Path

import pytest
import yaml

from aief.project import initialize
from aief.service import RuntimeService
from aief.validation import assert_schema


FACTORY = Path(__file__).parents[1]


def _service(tmp_path: Path, mode: str | None, *, condition: str = "L3") -> tuple[RuntimeService, str]:
    root = tmp_path / "project"
    initialize(FACTORY / "templates/project", root)
    settings = root / ".ai" / "project.yaml"
    config = yaml.safe_load(settings.read_text(encoding="utf-8"))
    if mode is None:
        config.pop("review", None)
    else:
        config["review"] = {"waivers": mode}
    settings.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    service = RuntimeService(root, FACTORY)
    execution = service.start(
        "Implement a change", "codex", confirmed=True,
        experiment={"condition": condition, "repeatIndex": 1, "environmentIdentifier": "test-env"},
    )
    return service, execution.data["metadata"]["id"]


def test_disabled_waivers_are_denied_and_evidenced_without_state_mutation(tmp_path: Path):
    service, identifier = _service(tmp_path, "disabled")
    execution = service.execution(identifier)
    initial_state = execution.data["status"]
    initial_phase = execution.next_phase()["id"]
    assert execution.data["reproducibility"]["reviewWaivers"] == {
        "value": "disabled", "availability": "OBSERVED"
    }

    with pytest.raises(PermissionError, match="review waivers are disabled"):
        service.waive_finding(identifier, 1, "I disagree", approver="alice")

    current = service.execution(identifier)
    assert current.data["status"] == initial_state
    assert current.next_phase()["id"] == initial_phase
    assert "findingDecisions" not in current.data
    refusals = current.data["approvalRefusals"]
    assert len(refusals) == 1
    assert refusals[0]["gate"] == "waive-finding-1"
    assert "review waivers are disabled" in refusals[0]["reason"]
    assert "gate.approval-refused" in [
        item["event"]["type"] for item in service.task_events(current.data["task"])
    ]
    assert_schema(FACTORY, "execution.schema.json", current.data)


def test_waiver_policy_is_snapshotted_at_execution_creation(tmp_path: Path):
    service, identifier = _service(tmp_path, "disabled")
    settings = service.project_root / ".ai" / "project.yaml"
    config = yaml.safe_load(settings.read_text(encoding="utf-8"))
    config["review"]["waivers"] = "enabled"
    settings.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")

    # Reopening a changed project must not relax the already recorded run.
    reopened = RuntimeService(service.project_root, FACTORY)
    with pytest.raises(PermissionError, match="review waivers are disabled"):
        reopened.waive_finding(identifier, 1, "Waive the finding")
    assert reopened.execution(identifier).data["reproducibility"]["reviewWaivers"]["value"] == "disabled"

    # A new run uses the newly configured mode, independent of treatment labels.
    future = reopened.start(
        "Implement a different change", confirmed=True, experiment={"condition": "L0"}
    )
    assert future.data["reproducibility"]["reviewWaivers"] == {
        "value": "enabled", "availability": "OBSERVED"
    }


def test_waiver_policy_and_condition_are_separate_axes(tmp_path: Path):
    service, identifier = _service(tmp_path, "disabled", condition="L2")
    record = service.execution(identifier).data["reproducibility"]
    assert record["reviewWaivers"]["value"] == "disabled"
    assert record["experimentalCondition"]["value"] == "L2"


def test_legacy_default_is_enabled_and_a_missing_review_cannot_prove_prohibition(tmp_path: Path):
    service, identifier = _service(tmp_path, None)
    assert service.execution(identifier).data["reproducibility"]["reviewWaivers"] == {
        "value": "enabled", "availability": "OBSERVED"
    }
    with pytest.raises(ValueError, match="no review with blocking findings"):
        service.waive_finding(identifier, 1, "No finding is waiting")


def test_review_waiver_schema_rejects_unknown_mode(tmp_path: Path):
    service, identifier = _service(tmp_path, "disabled")
    config = dict(service.project)
    config["review"] = {"waivers": "maybe"}
    with pytest.raises(Exception):
        assert_schema(FACTORY, "project.schema.json", config)
