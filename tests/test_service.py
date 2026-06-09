from pathlib import Path
import json

import yaml
import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from aief.project import initialize
from aief.service import RuntimeService
from aief.intake import TaskRegistry


def validator(schema_name: str) -> Draft202012Validator:
    registry = Registry()
    schemas = {}
    for path in Path("core/schemas").glob("*.json"):
        schema = json.loads(path.read_text())
        schemas[path.name] = schema
        registry = registry.with_resource(schema["$id"], Resource.from_contents(schema))
    return Draft202012Validator(schemas[schema_name], registry=registry)


def test_runtime_service_creates_schema_valid_execution_and_handoff(tmp_path: Path):
    project = tmp_path / "project"
    initialize(Path("templates/project"), project)
    execution = RuntimeService(project, Path(".")).start("/implement EGW-142", "codex")
    assert not list(validator("execution.schema.json").iter_errors(execution.data))
    handoff = yaml.safe_load(execution.handoff().read_text())
    assert not list(validator("handoff.schema.json").iter_errors(handoff))
    assert execution.next_phase()["id"] == "understand"


def test_gate_persists_phase_output_before_waiting(tmp_path: Path):
    workflow = {"metadata":{"id":"demo","version":"1.0.0"},"phases":[{"id":"plan","skill":"create-plan","gate":{"id":"before-implementation","type":"human-approval"}}]}
    execution = __import__("aief.runtime", fromlist=["Execution"]).Execution.create(tmp_path, workflow, "TASK-1")
    assert execution.advance({"summary":"approved scope"}) == "waiting-approval"
    assert (execution.root / "plan.yaml").is_file()
    assert execution.advance(approved=True) == "completed"


def test_runtime_service_validates_skill_output(tmp_path: Path):
    project = tmp_path / "project"
    initialize(Path("templates/project"), project)
    service = RuntimeService(project, Path("."))
    execution = service.start("/analyze DEMO-1")
    with pytest.raises(ValueError, match="invalid output for understand-task"):
        service.complete_phase(execution.data["metadata"]["id"], {"summary":"incomplete"})
    valid = yaml.safe_load(Path("core/skills/understand-task/examples/output.yaml").read_text())
    advanced = service.complete_phase(execution.data["metadata"]["id"], valid)
    assert advanced.next_phase()["id"] == "resolve-context"


def test_runtime_reassesses_and_persists_tracking(tmp_path: Path):
    project = tmp_path / "project"
    initialize(Path("templates/project"), project)
    service = RuntimeService(project, Path("."))
    intake = service.intake("Ajoute une capacité de paiement")
    task_id = intake["task"]["metadata"]["id"]
    result = service.reassess_tracking(task_id, {"risk":"high","repositories":["api","app"],"changeTypes":["source-code"]})
    assert result["decision"]["level"] == "required"
    assert TaskRegistry(project).load(task_id)["tracking"]["level"] == "required"


def test_runtime_fails_closed_on_factory_version_mismatch(tmp_path: Path):
    project = tmp_path / "project"
    initialize(Path("templates/project"), project)
    data = yaml.safe_load((project / ".ai/project.yaml").read_text())
    data["factory"]["version"] = "9.9.9"
    (project / ".ai/project.yaml").write_text(yaml.safe_dump(data, sort_keys=False))
    with pytest.raises(RuntimeError, match="requires Factory 9.9.9"):
        RuntimeService(project, Path("."))
