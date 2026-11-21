import hashlib
from pathlib import Path

import pytest
import yaml

from aief import plan_binding
from aief.intake import TaskRegistry
from aief.project import initialize
from aief.service import RuntimeService
from aief.validation import assert_schema


ROOT = Path(__file__).parents[1]
PLAN = "# Plan\n\n1. Add the endpoint.\n2. Cover it with a test.\n"
VERIFICATION = {"acceptanceCriteria": [{"id": "AC-1", "statement": "The endpoint returns 200"},
                                       {"id": "AC-2", "statement": "A test covers the endpoint"}],
                "commands": [{"id": "V-1", "command": ["make", "test"]}]}


def project(tmp_path: Path) -> RuntimeService:
    root = tmp_path / "project"; initialize(ROOT / "templates/project", root)
    data = yaml.safe_load((root / ".ai/project.yaml").read_text()); data["autonomy"] = {"default": "L3", "maximum": "L3"}
    data["repositories"] = [{"id": "main", "path": ".", "role": "application", "profiles": ["generic"],
                             "responsibilities": [], "dependencies": [], "criticalDomains": []}]
    (root / ".ai/project.yaml").write_text(yaml.safe_dump(data, sort_keys=False))
    return RuntimeService(root, ROOT)


def files(tmp_path: Path, verification: dict | None = None) -> tuple[Path, Path]:
    source = tmp_path / "frozen"; source.mkdir(exist_ok=True)
    plan = source / "plan.md"; plan.write_text(PLAN)
    spec = source / "verification.yaml"; spec.write_text(yaml.safe_dump(verification or VERIFICATION, sort_keys=False))
    return plan, spec


def output(summary: str, details: dict) -> dict:
    return {"summary": summary, "status": "completed", "evidence": ["verified"], "unknowns": [], "details": details}


def to_planning(service: RuntimeService, plan: Path, spec: Path) -> str:
    execution = service.start("Implémente une évolution locale", confirmed=True, bound_plan=plan, bound_verification=spec)
    identifier = execution.data["metadata"]["id"]
    task = TaskRegistry(service.project_root).load(execution.data["task"]); task["autonomy"] = {"requested": "L3"}
    TaskRegistry(service.project_root).save(task)
    for phase in execution.data["phases"]:
        if phase["skill"] == "analyze-impact": break
        phase["status"] = "completed"
    execution.data["status"] = "running"; execution.save()
    service.prepare_phase(identifier)
    service.complete_phase(identifier, output("Impact", {"risk": "medium", "repositories": ["main"], "changeTypes": ["source-code"]}))
    current = service.execution(identifier)
    while current.next_phase()["skill"] != "create-plan":
        current.next_phase()["status"] = "completed"
    current.data["status"] = "running"; current.save()
    return identifier


def test_bound_files_are_copied_unchanged_and_fingerprinted(tmp_path: Path):
    service = project(tmp_path); plan, spec = files(tmp_path)
    execution = service.start("Implémente une évolution locale", confirmed=True, bound_plan=plan, bound_verification=spec)
    binding = execution.data["planBinding"]
    assert (execution.root / binding["plan"]["artifact"]).read_bytes() == plan.read_bytes()
    assert (execution.root / binding["verification"]["artifact"]).read_bytes() == spec.read_bytes()
    assert binding["plan"]["sha256"] == hashlib.sha256(plan.read_bytes()).hexdigest()
    reproducibility = execution.data["reproducibility"]
    assert reproducibility["boundPlanFingerprint"] == {"value": binding["plan"]["sha256"], "availability": "OBSERVED"}
    assert reproducibility["boundVerificationFingerprint"]["value"] == binding["verification"]["sha256"]
    assert_schema(ROOT, "execution.schema.json", execution.data)


def test_runtime_records_the_bound_plan_and_refuses_an_agent_plan(tmp_path: Path):
    service = project(tmp_path); plan, spec = files(tmp_path)
    identifier = to_planning(service, plan, spec)
    with pytest.raises(PermissionError, match="bound plan"):
        service.complete_phase(identifier, output("Another plan", {"acceptanceCriteria": [{"id": "X", "statement": "other"}]}))
    prepared = service.prepare_phase(identifier)
    assert prepared["boundPlan"]["plan"]["artifact"] == "bound-plan/plan.md"
    current = service.execution(identifier)
    planning = yaml.safe_load((current.root / "planning.yaml").read_text())
    assert planning["details"]["acceptanceCriteria"] == VERIFICATION["acceptanceCriteria"]
    assert planning["details"]["planner"]["assurance"] == "TRUSTED"
    assert planning["details"]["binding"] == current.data["planBinding"]
    assert next(phase for phase in current.data["phases"] if phase["skill"] == "create-plan")["status"] in {"completed", "waiting-approval"}
    governed = yaml.safe_load((current.root / current.data["governedExecutionPlan"]).read_text())
    assert f"bound-plan/plan.md:sha256:{current.data['planBinding']['plan']['sha256']}" in governed["contextFingerprints"]
    assert_schema(ROOT, "execution.schema.json", current.data)


def test_plan_gate_still_applies_after_a_bound_plan(tmp_path: Path):
    service = project(tmp_path); plan, spec = files(tmp_path)
    identifier = to_planning(service, plan, spec)
    prepared = service.prepare_phase(identifier)
    assert prepared["status"] == "waiting-approval"
    assert service.execution(identifier).next_phase()["skill"] == "create-plan"


def test_agent_phase_briefs_point_to_the_bound_files(tmp_path: Path):
    service = project(tmp_path); plan, spec = files(tmp_path)
    identifier = to_planning(service, plan, spec)
    current = service.execution(identifier)
    text = (current.root / "phase-brief-analyze-impact.md").read_text()
    assert "## Bound plan" in text and "`bound-plan/plan.md`" in text and "`bound-plan/verification.yaml`" in text
    assert current.data["planBinding"]["plan"]["sha256"] in text


def test_briefs_without_binding_are_unchanged(tmp_path: Path):
    service = project(tmp_path)
    execution = service.start("Implémente une évolution locale", confirmed=True)
    for phase in execution.data["phases"]:
        if phase["skill"] == "analyze-impact": break
        phase["status"] = "completed"
    execution.data["status"] = "running"; execution.save()
    brief = service.prepare_phase(execution.data["metadata"]["id"])["phaseBrief"]
    assert "Bound plan" not in Path(brief["path"]).read_text()
    assert "planBinding" not in service.execution(execution.data["metadata"]["id"]).data


def test_changed_bound_file_is_refused(tmp_path: Path):
    service = project(tmp_path); plan, spec = files(tmp_path)
    identifier = to_planning(service, plan, spec)
    (service.execution(identifier).root / "bound-plan/plan.md").write_text(PLAN + "3. Also refactor.\n")
    with pytest.raises(RuntimeError, match="changed after it was bound"):
        service.prepare_phase(identifier)


def test_submitting_workflow_needs_criteria_in_the_bound_verification(tmp_path: Path):
    service = project(tmp_path); plan, spec = files(tmp_path, {"commands": []})
    with pytest.raises(ValueError, match="acceptanceCriteria is missing"):
        service.start("Implémente une évolution locale", confirmed=True, bound_plan=plan, bound_verification=spec)
    with pytest.raises(ValueError, match="ends with submission"):
        service.start("Implémente une évolution locale", confirmed=True, bound_plan=plan)


def test_binding_needs_a_create_plan_phase(tmp_path: Path):
    service = project(tmp_path); plan, spec = files(tmp_path)
    with pytest.raises(ValueError, match="no create-plan phase"):
        service.start("/review Revois le changement", bound_plan=plan, bound_verification=spec)


def test_verification_without_plan_is_refused(tmp_path: Path):
    service = project(tmp_path); _, spec = files(tmp_path)
    with pytest.raises(ValueError, match="needs a bound plan"):
        service.start("Implémente une évolution locale", confirmed=True, bound_verification=spec)


def bound_validation(tmp_path: Path, commands: list) -> tuple:
    from test_service import validation_execution
    service, execution = validation_execution(tmp_path)
    plan, spec = files(tmp_path, {**VERIFICATION, "commands": commands})
    execution.data["planBinding"] = plan_binding.bind(execution.root, plan, spec, "2026-11-21T00:00:00+00:00")
    execution.save()
    return service, execution.data["metadata"]["id"]


def test_validation_runs_the_bound_verification_commands_with_the_profile(tmp_path: Path):
    service, identifier = bound_validation(tmp_path, [{"id": "unit", "command": ["python3", "-m", "pytest", "-q"]},
                                                      {"id": "lint", "command": ["ruff", "check"], "cwd": "src"}])
    (service.project_root / "src").mkdir()
    plan = service.profile_validation_plan(identifier)
    bound = [item for item in plan if item["profile"] == "bound-verification"]
    assert [item["operation"] for item in bound] == ["unit", "lint"]
    assert bound[1]["cwd"] == str((service.project_root / "src").resolve())
    assert any(item["profile"] == "maven" for item in plan)
    calls = []
    class Result: returncode, stdout, stderr = 0, "ok", ""
    report = service.run_profile_validation(identifier, lambda command, **kwargs: calls.append(command) or Result())
    assert ["python3", "-m", "pytest", "-q"] in calls and ["ruff", "check"] in calls
    assert "main:bound-verification:unit:exit-0" in report["evidence"]


def test_a_failing_bound_verification_command_fails_the_validation(tmp_path: Path):
    service, identifier = bound_validation(tmp_path, [{"id": "unit", "command": ["false"]}])
    class Result:
        def __init__(self, code): self.returncode, self.stdout, self.stderr = code, "", ""
    report = service.run_profile_validation(identifier, lambda command, **kwargs: Result(1 if command == ["false"] else 0))
    assert report["status"] == "failed" and "main:bound-verification:unit:exit-1" in report["evidence"]


def test_bound_verification_commands_are_checked_before_the_execution_starts(tmp_path: Path):
    for commands, message in (([{"id": "a", "command": "pytest"}], "argv array"),
                              ([{"id": "a", "command": ["x"]}, {"id": "a", "command": ["y"]}], "duplicate id"),
                              ([{"id": "a", "command": ["x"], "cwd": "../elsewhere"}], "relative path"),
                              ({"a": 1}, "must be a list")):
        case = tmp_path / message.replace(" ", "-"); case.mkdir()
        plan, spec = files(case, {**VERIFICATION, "commands": commands})
        with pytest.raises(ValueError, match=message):
            project(case).start("Implémente une évolution locale", confirmed=True, bound_plan=plan, bound_verification=spec)
