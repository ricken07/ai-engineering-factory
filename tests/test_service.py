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


def test_task_log_traces_workflow_and_structured_phase_decisions(tmp_path: Path):
    project = tmp_path / "project"
    initialize(Path("templates/project"), project)
    service = RuntimeService(project, Path("."))
    execution = service.start("/analyze DEMO-42", "claude-code")
    execution_id = execution.data["metadata"]["id"]
    service.prepare_phase(execution_id)
    output = yaml.safe_load(Path("core/skills/understand-task/examples/output.yaml").read_text())
    service.complete_phase(execution_id, output)
    events = service.task_events("DEMO-42")

    assert [item["event"]["type"] for item in events] == [
        "request.created", "intent.resolved", "task.normalized", "workflow.started",
        "phase.started", "phase.completed",
    ]
    assert events[3]["execution"]["id"] == execution_id
    assert events[3]["payload"]["workflow"]["id"] == "analyze-task"
    assert events[-1]["payload"]["artifact"] == "understand.yaml"
    assert events[-1]["payload"]["summary"] == output["summary"]
    assert all(item["task"]["id"] == "DEMO-42" for item in events)
    assert (project / ".ai/runtime/tasks/DEMO-42/events.jsonl").is_file()


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


def validation_execution(tmp_path: Path, repositories=None, autonomy="L2"):
    project = tmp_path / "project"
    initialize(Path("templates/project"), project)
    project_data = yaml.safe_load((project / ".ai/project.yaml").read_text())
    project_data["autonomy"]["default"] = autonomy
    project_data["repositories"] = repositories or [{"id":"main","path":".","role":"application","profiles":["maven"],"responsibilities":[],"dependencies":[],"criticalDomains":[]}]
    (project / ".ai/project.yaml").write_text(yaml.safe_dump(project_data, sort_keys=False))
    (project / "mvnw").touch()
    service = RuntimeService(project, Path("."))
    execution = service.start("/test DEMO-7")
    task = TaskRegistry(project).load("DEMO-7")
    task["scope"] = {"repositories":[item["id"] for item in project_data["repositories"]]}
    TaskRegistry(project).save(task)
    for phase in execution.data["phases"]:
        if phase["skill"] == "validate-change": break
        phase["status"] = "completed"
    execution.data["status"] = "running"; execution.save()
    return service, execution


def test_runtime_resolves_and_executes_profile_validation_without_shell(tmp_path: Path):
    service, execution = validation_execution(tmp_path)
    plan = service.profile_validation_plan(execution.data["metadata"]["id"])
    assert plan[0]["command"] == ["./mvnw", "verify"]
    calls = []
    class Result: returncode, stdout, stderr = 0, "verified", ""
    def runner(command, **kwargs): calls.append((command,kwargs)); return Result()
    report = service.run_profile_validation(execution.data["metadata"]["id"], runner)
    assert report["status"] == "completed"
    assert calls[0][1]["shell"] is False
    assert service.execution(execution.data["metadata"]["id"]).next_phase()["skill"] == "review-change"


def test_runtime_stops_execution_when_profile_validation_fails(tmp_path: Path):
    service, execution = validation_execution(tmp_path)
    class Result: returncode, stdout, stderr = 1, "", "tests failed"
    report = service.run_profile_validation(execution.data["metadata"]["id"], lambda command, **kwargs: Result())
    assert report["status"] == "failed"
    persisted = service.execution(execution.data["metadata"]["id"])
    assert persisted.data["status"] == "failed"
    assert yaml.safe_load((persisted.root / "validation.yaml").read_text())["details"]["results"][0]["stderr"] == "tests failed"


def test_runtime_denies_profile_execution_below_l2(tmp_path: Path):
    service, execution = validation_execution(tmp_path, autonomy="L1")
    with pytest.raises(PermissionError, match="requires autonomy L2"):
        service.run_profile_validation(execution.data["metadata"]["id"])


def test_profile_validation_persists_effective_engineering_context(tmp_path: Path):
    service, execution = validation_execution(tmp_path)
    class Result: returncode, stdout, stderr = 0, "ok", ""
    report = service.run_profile_validation(execution.data["metadata"]["id"], lambda command, **kwargs: Result())
    assert "testing-baseline" in report["details"]["engineeringContexts"]["main"]
    persisted = service.execution(execution.data["metadata"]["id"])
    assert any(name.startswith("engineering-context-main-validate-change") for name in persisted.data["artifacts"])


def test_prepare_phase_automatically_materializes_skill_context(tmp_path: Path):
    service, execution = validation_execution(tmp_path)
    prepared = service.prepare_phase(execution.data["metadata"]["id"])
    assert prepared["phase"]["skill"] == "validate-change"
    assert prepared["engineeringContexts"][0]["repository"] == "main"
    assert "testing-baseline" in {item["id"] for item in prepared["engineeringContexts"][0]["practices"]}


def test_prepare_phase_resolves_core_skill_contract_without_native_invocation(tmp_path: Path):
    project=tmp_path/"project"; initialize(Path("templates/project"),project)
    service=RuntimeService(project,Path(".")); execution=service.start("/implement Feature 1.1","claude-code")
    prepared=service.prepare_phase(execution.data["metadata"]["id"])
    contract=prepared["skillContract"]
    assert contract["id"] == "understand-task"
    assert contract["invocation"] == "core-contract"
    assert Path(contract["manifest"]).is_file()
    assert Path(contract["instructions"]).name == "SKILL.md"
    assert Path(contract["outputSchema"]).name == "output.schema.json"


def test_impact_completion_automatically_reassesses_tracking(tmp_path: Path):
    project=tmp_path/"project"; initialize(Path("templates/project"),project)
    project_data=yaml.safe_load((project/".ai/project.yaml").read_text())
    project_data["repositories"].append({"id":"secondary","path":".","role":"application","profiles":["generic"],"responsibilities":[],"dependencies":[],"criticalDomains":[]})
    (project/".ai/project.yaml").write_text(yaml.safe_dump(project_data,sort_keys=False))
    service=RuntimeService(project,Path("."))
    execution=service.start("Corrige un problème de paiement")
    for phase in execution.data["phases"]:
        if phase["skill"] == "analyze-impact": break
        phase["status"]="completed"
    execution.data["status"]="running"; execution.save()
    output={"summary":"Cross-repository payment impact","status":"completed","evidence":["repository-map"],"unknowns":[],"details":{"risk":"high","repositories":["main","secondary"],"changeTypes":["functional-change"],"domains":["payment"]}}
    service.complete_phase(execution.data["metadata"]["id"],output)
    task=TaskRegistry(project).load(execution.data["task"])
    persisted=service.execution(execution.data["metadata"]["id"])
    assert persisted.data["repositories"] == ["main", "secondary"]
    assert task["scope"]["repositories"] == ["main", "secondary"]
    tracking=yaml.safe_load((project/".ai/runtime/tasks"/task["metadata"]["id"]/"tracking.yaml").read_text())
    assert tracking["decision"]["level"] == "required"
    assert set(tracking["reasons"]) == {"externally-track-high-risk","externally-track-cross-repository"}


def test_mutating_workflow_rejects_impact_without_repositories_before_advancing(tmp_path: Path):
    project=tmp_path/"project"; initialize(Path("templates/project"),project); service=RuntimeService(project,Path("."))
    execution=service.start("Implémente une évolution locale")
    for phase in execution.data["phases"]:
        if phase["skill"] == "analyze-impact": break
        phase["status"]="completed"
    execution.data["status"]="running"; execution.save()
    output={"summary":"Impact incomplete","status":"completed","evidence":["code"],"unknowns":[],"details":{"repositories":[]}}

    with pytest.raises(ValueError, match="at least one impacted repository"):
        service.complete_phase(execution.data["metadata"]["id"],output)

    persisted=service.execution(execution.data["metadata"]["id"])
    assert persisted.next_phase()["skill"] == "analyze-impact"
    assert not (persisted.root/"analyze-impact.yaml").exists()


def test_impact_rejects_unknown_repository_identifier(tmp_path: Path):
    project=tmp_path/"project"; initialize(Path("templates/project"),project); service=RuntimeService(project,Path("."))
    execution=service.start("Implémente une évolution locale")
    for phase in execution.data["phases"]:
        if phase["skill"] == "analyze-impact": break
        phase["status"]="completed"
    execution.data["status"]="running"; execution.save()
    output={"summary":"Unknown repository","status":"completed","evidence":["code"],"unknowns":[],"details":{"repositories":["invented-repo"]}}

    with pytest.raises(ValueError, match="unknown project repositories: invented-repo"):
        service.complete_phase(execution.data["metadata"]["id"],output)


def test_task_registry_rejects_duplicate_yaml_keys(tmp_path: Path):
    project=tmp_path/"project"; initialize(Path("templates/project"),project)
    task_root=project/".ai/runtime/tasks/local-duplicate"; task_root.mkdir(parents=True)
    (task_root/"task.yaml").write_text(
        "apiVersion: factory.gaddigital.io/v1alpha1\nkind: Task\nmetadata: {id: local-duplicate}\n"
        "objective: {summary: demo}\nscope: {repositories: [main]}\nscope: {repositories: []}\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate YAML key 'scope'"):
        TaskRegistry(project).load("local-duplicate")


def test_implementation_phase_is_blocked_until_workspace_is_prepared(tmp_path: Path):
    import subprocess
    project=tmp_path/"project"; initialize(Path("templates/project"),project)
    subprocess.run(["git","init","-b","main"],cwd=project,check=True,capture_output=True)
    subprocess.run(["git","config","user.email","factory@example.invalid"],cwd=project,check=True)
    subprocess.run(["git","config","user.name","Factory Test"],cwd=project,check=True)
    subprocess.run(["git","add","."],cwd=project,check=True)
    subprocess.run(["git","commit","-m","baseline"],cwd=project,check=True,capture_output=True)
    service=RuntimeService(project,Path(".")); execution=service.start("Refactore le composant local")
    task=TaskRegistry(project).load(execution.data["task"]); task["scope"]={"repositories":["main"]}; TaskRegistry(project).save(task)
    service.reassess_tracking(task["metadata"]["id"],{"risk":"low","repositories":["main"],"changeTypes":["refactoring"]})
    for phase in execution.data["phases"]:
        if phase["id"] == "implementation": break
        phase["status"]="completed"
    execution.data["status"]="running"; execution.save()
    prepared=service.prepare_phase(execution.data["metadata"]["id"])
    assert prepared["status"] == "blocked"
    assert prepared["blockingReason"]["type"] == "workspace-preparation-required"
    workspace=service.workspace(execution.data["metadata"]["id"],"prepare",execute=True)
    assert workspace["decision"]["status"] == "ready"
    assert service.prepare_phase(execution.data["metadata"]["id"])["status"] == "running"
