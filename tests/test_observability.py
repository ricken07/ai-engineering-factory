from pathlib import Path
import json
import subprocess
import sys

import pytest
import yaml
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from aief.intake import TaskRegistry
from aief.project import initialize
from aief.service import RuntimeService
from aief.task_log import TaskEventLog

ROOT = Path(__file__).parents[1]


def runtime(tmp_path: Path):
    project_root = tmp_path / "project"
    initialize(ROOT / "templates/project", project_root)
    data = yaml.safe_load((project_root / ".ai/project.yaml").read_text())
    data["autonomy"] = {"default": "L3", "maximum": "L3"}
    data["repositories"] = [{"id": "main", "path": ".", "role": "application", "profiles": ["generic"], "responsibilities": [], "dependencies": [], "criticalDomains": []}]
    (project_root / ".ai/project.yaml").write_text(yaml.safe_dump(data, sort_keys=False))
    service = RuntimeService(project_root, ROOT)
    execution = service.start("Implémente une évolution locale", confirmed=True)
    task_data = TaskRegistry(project_root).load(execution.data["task"])
    task_data["autonomy"] = {"requested": "L3"}
    TaskRegistry(project_root).save(task_data)
    return service, execution


def output(summary: str, details: dict):
    return {"summary": summary, "status": "completed", "evidence": ["verified"], "unknowns": [], "details": details}


def event_types(items):
    return [item["event"]["type"] for item in items]


def test_events_follow_a_logical_chronological_order(tmp_path: Path):
    service, execution = runtime(tmp_path)
    events = service.task_events(execution.data["task"])
    assert event_types(events) == ["request.created", "intent.resolved", "task.normalized", "workflow.started"]
    timestamps = [item["event"]["timestamp"] for item in events]
    assert timestamps == sorted(timestamps)


def test_events_correlate_task_and_execution_ids(tmp_path: Path):
    service, execution = runtime(tmp_path)
    task_id, execution_id = execution.data["task"], execution.data["metadata"]["id"]
    events = service.task_events(task_id)
    assert all(item["task"]["id"] == task_id for item in events)
    assert "execution" not in events[0]  # request.created precedes any Execution
    scoped = [item for item in events if "execution" in item]
    assert scoped and all(item["execution"]["id"] == execution_id for item in scoped)


def test_workspace_events_after_resume_show_blocked_then_prepared(tmp_path: Path):
    project = tmp_path / "project"
    initialize(Path("templates/project"), project)
    subprocess.run(["git", "init", "-b", "main"], cwd=project, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "factory@example.invalid"], cwd=project, check=True)
    subprocess.run(["git", "config", "user.name", "Factory Test"], cwd=project, check=True)
    subprocess.run(["git", "add", "."], cwd=project, check=True)
    subprocess.run(["git", "commit", "-m", "baseline"], cwd=project, check=True, capture_output=True)
    service = RuntimeService(project, Path("."))
    execution = service.start("Refactore le composant local", confirmed=True)
    task = TaskRegistry(project).load(execution.data["task"])
    task["scope"] = {"repositories": ["main"]}
    TaskRegistry(project).save(task)
    service.reassess_tracking(task["metadata"]["id"], {"risk": "low", "repositories": ["main"], "changeTypes": ["refactoring"]})
    for phase in execution.data["phases"]:
        if phase["id"] == "implementation": break
        phase["status"] = "completed"
    execution.data["status"] = "running"; execution.save()
    identifier = execution.data["metadata"]["id"]
    assert service.prepare_phase(identifier)["status"] == "blocked"
    assert service.workspace(identifier, "prepare", execute=True)["decision"]["status"] == "ready"
    types = event_types(service.task_events(task["metadata"]["id"]))
    assert "workspace.blocked" in types and "workspace.prepared" in types
    assert types.index("workspace.blocked") < types.index("workspace.prepared")


def test_cancel_execution_reaches_the_declared_cancelled_status_and_emits_its_event(tmp_path: Path):
    service, execution = runtime(tmp_path)
    identifier = execution.data["metadata"]["id"]
    cancelled = service.cancel_execution(identifier, "superseded by a newer request")
    assert cancelled.data["status"] == "cancelled"
    assert cancelled.data["cancelledReason"] == "superseded by a newer request"
    with pytest.raises(RuntimeError, match="terminal execution cannot be cancelled"):
        service.cancel_execution(identifier, "double cancel")
    events = service.task_events(execution.data["task"])
    cancel_events = [item for item in events if item["event"]["type"] == "execution.cancelled"]
    assert len(cancel_events) == 1
    assert cancel_events[0]["execution"]["id"] == identifier
    assert cancel_events[0]["payload"]["reason"] == "superseded by a newer request"


def test_gate_lifecycle_emits_requested_then_approved(tmp_path: Path):
    service, execution = runtime(tmp_path)
    identifier = execution.data["metadata"]["id"]
    for phase in execution.data["phases"]:
        if phase["skill"] == "analyze-impact": break
        phase["status"] = "completed"
    execution.data["status"] = "running"; execution.save()
    service.complete_phase(identifier, output("Critical impact", {"risk": "critical", "repositories": ["main"], "changeTypes": ["destructive-migration"]}))
    current = service.execution(identifier)
    for phase in current.data["phases"]:
        if phase["id"] == "implementation": break
        phase["status"] = "completed"
    current.data["status"] = "running"; current.save()
    service.prepare_phase(identifier)
    service.approve_policy_gate(identifier, "before-implementation")
    events = service.task_events(execution.data["task"])
    types = event_types(events)
    assert "gate.requested" in types and "gate.approved" in types
    assert types.index("gate.requested") < types.index("gate.approved")
    requested = next(item for item in events if item["event"]["type"] == "gate.requested" and item["payload"]["gate"] == "before-implementation")
    approved = next(item for item in events if item["event"]["type"] == "gate.approved" and item["payload"]["gate"] == "before-implementation")
    assert requested and approved


def test_operation_replay_does_not_duplicate_phase_completed_event(tmp_path: Path):
    service, execution = runtime(tmp_path)
    identifier = execution.data["metadata"]["id"]
    payload = output("Impact", {"risk": "low", "repositories": ["main"], "changeTypes": ["source-code"]})
    service.complete_phase(identifier, payload, operation_id="complete-impact-1")
    service.complete_phase(identifier, payload, operation_id="complete-impact-1")
    events = service.task_events(execution.data["task"])
    completed = [item for item in events if item["event"]["type"] == "phase.completed"]
    assert len(completed) == 1


def test_redaction_strips_secrets_and_omits_content_by_default(tmp_path: Path):
    log = TaskEventLog(tmp_path, "TASK-REDACT", project_id="demo", factory_version="1.0.0")
    record = log.append("workflow.started", payload={
        "token": "ghp_abcdefghijklmnopqrstuvwxyz012345",
        "note": "an AWS key AKIAABCDEFGHIJKLMNOP embedded in free text",
        "content": "full practice document text that must not leak by default",
        "summary": "safe short summary",
    })
    assert record["payload"]["token"] == "[REDACTED]"
    assert record["payload"]["note"] == "[REDACTED]"
    assert record["payload"]["content"] == "[OMITTED:opt-in required]"
    assert record["payload"]["summary"] == "safe short summary"
    assert log.read() == [record]


def test_content_requires_explicit_opt_in(tmp_path: Path):
    log = TaskEventLog(tmp_path, "TASK-OPT-IN", project_id="demo", factory_version="1.0.0")
    omitted = log.append("workflow.started", payload={"content": "practice text"})
    included = log.append("workflow.started", payload={"content": "practice text"}, allow_content=True)
    assert omitted["payload"]["content"] == "[OMITTED:opt-in required]"
    assert included["payload"]["content"] == "practice text"


def test_export_disabled_by_default_never_touches_opentelemetry(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("AIEF_OBSERVABILITY_OTEL", raising=False)
    calls: list[str] = []

    class ExplodingTrace:
        @staticmethod
        def get_tracer(name):
            calls.append(name)
            raise AssertionError("opentelemetry must never be touched when export is disabled")

    fake_module = type(sys)("opentelemetry")
    fake_module.trace = ExplodingTrace
    monkeypatch.setitem(sys.modules, "opentelemetry", fake_module)
    log = TaskEventLog(tmp_path, "TASK-NOEXPORT", project_id="demo", factory_version="1.0.0")
    record = log.append("workflow.started", payload={})
    assert calls == []
    assert log.read() == [record]


def test_export_enabled_but_opentelemetry_unavailable_never_blocks_an_execution(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("AIEF_OBSERVABILITY_OTEL", "1")
    monkeypatch.setitem(sys.modules, "opentelemetry", None)  # forces ImportError on `from opentelemetry import trace`
    log = TaskEventLog(tmp_path, "TASK-UNAVAILABLE", project_id="demo", factory_version="1.0.0")
    record = log.append("workflow.started", payload={})  # must not raise
    assert log.read() == [record]


def test_events_validate_against_the_runtime_event_schema(tmp_path: Path):
    registry = Registry(); schemas = {}
    for path in (ROOT / "core/schemas").glob("*.json"):
        schema = json.loads(path.read_text())
        schemas[path.name] = schema
        registry = registry.with_resource(schema["$id"], Resource.from_contents(schema))
    validator = Draft202012Validator(schemas["runtime-event.schema.json"], registry=registry)
    service, execution = runtime(tmp_path)
    for record in service.task_events(execution.data["task"]):
        assert not list(validator.iter_errors(record))
