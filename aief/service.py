from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import yaml
from jsonschema import Draft202012Validator
from collections.abc import Callable

from .compiler import compile_workflow
from .intake import TaskRegistry, create_request, normalize_task, resolve_intent
from .project import find_project, load_project
from .runtime import Execution
from .tracking import TaskTrackingManager, evaluate_tracking
from .capabilities import execute_plan, validation_plan
from .engineering import resolve_engineering_context
from .workspace import WorkspaceManager

AUTONOMY_RANK = {f"L{level}": level for level in range(5)}


class RuntimeService:
    """Deterministic boundary shared by all agent adapters."""

    def __init__(self, project: Path, factory: Path, environment: dict[str, str] | None = None):
        self.project_root = find_project(project)
        self.project = load_project(self.project_root)
        self.factory = factory.resolve()
        manifest_path = self.factory / "factory.yaml"
        if not manifest_path.is_file():
            raise FileNotFoundError(f"Factory manifest not found: {manifest_path}")
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        installed = manifest.get("metadata", {}).get("version")
        requested = self.project.get("factory", {}).get("version")
        if installed != requested:
            raise RuntimeError(f"project requires Factory {requested}, but {installed} was provided")
        self.tracking = TaskTrackingManager(self.project_root,self.factory,self.project,environment)

    def intake(self, text: str, agent: str | None = None) -> dict[str, Any]:
        request = create_request(text, agent)
        intent = resolve_intent(request)
        task = normalize_task(request, intent)
        task_path = TaskRegistry(self.project_root).save(task)
        intake_root = task_path.parent
        (intake_root / "request.yaml").write_text(yaml.safe_dump(request, sort_keys=False, allow_unicode=True), encoding="utf-8")
        (intake_root / "intent.yaml").write_text(yaml.safe_dump(intent, sort_keys=False, allow_unicode=True), encoding="utf-8")
        return {"request": request, "intent": intent, "task": task, "path": str(task_path)}

    def start(self, text: str, agent: str | None = None) -> Execution:
        intake = self.intake(text, agent)
        workflow = compile_workflow(self.factory, intake["task"]["workflow"])
        return Execution.create(self.project_root, workflow, intake["task"]["metadata"]["id"], agent)

    def execution(self, execution_id: str) -> Execution:
        root = self.project_root / ".ai" / "runtime" / "executions" / execution_id
        if not root.is_dir():
            raise FileNotFoundError(f"execution not found: {execution_id}")
        return Execution.load(root)

    def complete_phase(self, execution_id: str, output: dict[str, Any]) -> Execution:
        execution = self.execution(execution_id)
        phase = execution.next_phase()
        if phase is None:
            raise RuntimeError("execution is already complete")
        compiled = compile_workflow(self.factory, execution.data["workflow"]["id"])
        definition = next((item for item in compiled["phases"] if item["id"] == phase["id"]), None)
        if definition is None:
            raise RuntimeError(f"phase {phase['id']} is absent from the pinned workflow")
        schema_path = self.factory / definition["outputSchema"]
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        errors = sorted(Draft202012Validator(schema).iter_errors(output), key=lambda item: list(item.path))
        if errors:
            details = "; ".join(f"{'.'.join(map(str, error.path)) or 'root'}: {error.message}" for error in errors)
            raise ValueError(f"invalid output for {definition['skill']}: {details}")
        completed_skill=phase["skill"]
        execution.advance(output)
        if completed_skill == "analyze-impact" and output.get("status") == "completed":
            details=output.get("details",{}); impact=details.get("impact",details)
            observations={key:impact[key] for key in ("risk","repositories","changeTypes","domains") if key in impact}
            self.reassess_tracking(execution.data["task"],observations)
        return execution

    def _impacted_repository_ids(self, execution: Execution, task: dict[str, Any]) -> list[str]:
        identifiers = list(execution.data.get("repositories", [])) or list(task.get("scope", {}).get("repositories", []))
        if not identifiers:
            artifact = execution.root / "analyze-impact.yaml"
            if artifact.is_file():
                details = yaml.safe_load(artifact.read_text(encoding="utf-8")).get("details", {})
                repositories = details.get("repositories", [])
                if isinstance(repositories, dict): identifiers = list(repositories)
                elif isinstance(repositories, list): identifiers = [item.get("id") if isinstance(item, dict) else item for item in repositories]
        return list(dict.fromkeys(identifier for identifier in identifiers if isinstance(identifier, str) and identifier))

    def profile_validation_plan(self, execution_id: str) -> list[dict[str, Any]]:
        execution = self.execution(execution_id)
        phase = execution.next_phase()
        if phase is None or phase.get("skill") != "validate-change":
            raise RuntimeError("profile validation is only available during a validate-change phase")
        task = TaskRegistry(self.project_root).load(execution.data["task"])
        repository_ids = self._impacted_repository_ids(execution, task)
        if not repository_ids:
            raise RuntimeError("no impacted repository is recorded; complete impact analysis first")
        catalog = {repository["id"]: repository for repository in self.project.get("repositories", [])}
        unknown = sorted(set(repository_ids) - set(catalog))
        if unknown: raise KeyError(f"unknown impacted repositories: {', '.join(unknown)}")
        plan: list[dict[str, Any]] = []
        for identifier in repository_ids:
            repository = catalog[identifier]
            path = (self.project_root / repository["path"]).resolve()
            if not path.is_relative_to(self.project_root.resolve()):
                raise ValueError(f"repository path escapes project workspace: {identifier}")
            if not path.is_dir(): raise FileNotFoundError(f"repository path is missing: {identifier}: {path}")
            for item in validation_plan(self.factory, path, repository.get("profiles", [])):
                plan.append({"repository":identifier,"cwd":str(path),**item})
        if not plan: raise RuntimeError("no applicable validation command was resolved from impacted repository profiles")
        return plan

    def engineering_context(self, execution_id: str, repository_id: str, persist: bool = True) -> dict[str, Any]:
        execution = self.execution(execution_id)
        phase = execution.next_phase()
        if phase is None: raise RuntimeError("execution is already complete")
        context = resolve_engineering_context(self.factory, self.project_root, self.project, repository_id, phase["skill"])
        if persist:
            name = f"engineering-context-{repository_id}-{phase['skill']}.yaml"
            path = execution.root / name
            path.write_text(yaml.safe_dump(context, sort_keys=False, allow_unicode=True), encoding="utf-8")
            if name not in phase["artifacts"]: phase["artifacts"].append(name)
            if name not in execution.data["artifacts"]: execution.data["artifacts"].append(name)
            execution.save()
        return context

    def resolve_repository_context(self, repository_id: str, skill_id: str) -> dict[str, Any]:
        return resolve_engineering_context(self.factory, self.project_root, self.project, repository_id, skill_id)

    def prepare_phase(self, execution_id: str) -> dict[str, Any]:
        execution = self.execution(execution_id)
        phase = execution.next_phase()
        if phase is None: return {"execution":execution_id,"status":execution.data["status"],"phase":None,"engineeringContexts":[]}
        task = TaskRegistry(self.project_root).load(execution.data["task"])
        if phase["id"] == "implementation":
            tracking_path=self.project_root/".ai"/"runtime"/"tasks"/task["metadata"]["id"]/"tracking.yaml"
            tracking=yaml.safe_load(tracking_path.read_text(encoding="utf-8")) if tracking_path.is_file() else self.tracking.assess(task["metadata"]["id"])
            if tracking["decision"]["level"] == "required" and tracking["externalTracking"]["status"] != "linked":
                if execution.data["status"] != "blocked": execution.block({"type":"external-tracking-required","message":"external task tracking must be resolved before implementation","task":task["metadata"]["id"],"requiredBefore":"implementation"})
                return {"execution":execution_id,"status":"blocked","phase":phase,"engineeringContexts":[],"blockingReason":execution.data["blockingReason"],"tracking":tracking}
            repository_ids = self._impacted_repository_ids(execution, task)
            if not repository_ids:
                execution.block({"type":"workspace-safety-unresolved","message":"impacted repositories are required before implementation"})
                return {"execution":execution_id,"status":"blocked","phase":phase,"engineeringContexts":[],"blockingReason":execution.data["blockingReason"]}
            manager = WorkspaceManager(self.project_root, self.project, execution.root)
            try:
                workspace = manager.load()
                verification = manager.verify() if workspace["decision"]["status"] == "ready" else {"status":workspace["decision"]["status"]}
            except FileNotFoundError:
                workspace = manager.inspect(repository_ids, task.get("tracking", {}).get("canonicalReference") or task["metadata"]["id"])
                verification = {"status":workspace["decision"]["status"]}
            if verification["status"] != "ready":
                reason = "unrelated-local-changes" if workspace["decision"]["status"] == "blocked" else "workspace-preparation-required"
                if execution.data["status"] != "blocked":
                    execution.block({"type":reason,"message":"workspace safety must be resolved before implementation"})
                return {"execution":execution_id,"status":"blocked","phase":phase,"engineeringContexts":[],"blockingReason":execution.data["blockingReason"],"workspace":workspace}
        repository_ids = self._impacted_repository_ids(execution, task)
        compiled = compile_workflow(self.factory, execution.data["workflow"]["id"])
        definition = next(item for item in compiled["phases"] if item["id"] == phase["id"])
        contexts = []
        if definition.get("engineeringContext"):
            contexts = [self.engineering_context(execution_id, identifier) for identifier in repository_ids]
        return {"execution":execution_id,"status":execution.data["status"],"phase":phase,"engineeringContexts":contexts}

    def workspace(self, execution_id: str, action: str, execute: bool = False) -> dict[str, Any]:
        execution = self.execution(execution_id)
        task = TaskRegistry(self.project_root).load(execution.data["task"])
        repositories = self._impacted_repository_ids(execution, task)
        if not repositories:
            raise RuntimeError("no impacted repository is recorded; complete impact analysis first")
        manager = WorkspaceManager(self.project_root, self.project, execution.root)
        reference = task.get("tracking", {}).get("canonicalReference") or task["metadata"]["id"]
        if action == "inspect": result = manager.inspect(repositories, reference)
        elif action == "prepare": result = manager.prepare(repositories, reference, execute)
        elif action == "verify": result = manager.verify()
        elif action == "status": result = manager.load()
        elif action == "rollback": result = manager.rollback(execute)
        else: raise ValueError(f"unknown workspace action: {action}")
        if result.get("decision", {}).get("status") == "ready" or result.get("status") == "ready":
            if execution.data.get("blockingReason", {}).get("type") in {"workspace-preparation-required", "unrelated-local-changes", "workspace-safety-unresolved"}:
                execution.resume(execution.data["blockingReason"]["type"])
        return result

    def run_profile_validation(self, execution_id: str, runner: Callable[..., Any] | None = None) -> dict[str, Any]:
        execution = self.execution(execution_id)
        if execution.data["status"] in {"waiting-approval", "blocked", "failed", "cancelled"}:
            raise RuntimeError(f"execution state does not allow validation: {execution.data['status']}")
        task = TaskRegistry(self.project_root).load(execution.data["task"])
        authorized = task.get("autonomy", {}).get("authorized") or self.project.get("autonomy", {}).get("default", "L0")
        if AUTONOMY_RANK.get(authorized, -1) < AUTONOMY_RANK["L2"]:
            raise PermissionError(f"profile command execution requires autonomy L2; authorized level is {authorized}")
        plan = self.profile_validation_plan(execution_id)
        contexts = {identifier:self.engineering_context(execution_id, identifier) for identifier in dict.fromkeys(item["repository"] for item in plan)}
        results: list[dict[str, Any]] = []
        for item in plan:
            command = {key:value for key,value in item.items() if key not in {"repository","cwd"}}
            kwargs = {"runner":runner} if runner is not None else {}
            result = execute_plan([command], Path(item["cwd"]), execute=True, **kwargs)[0]
            results.append({"repository":item["repository"],"cwd":item["cwd"],**result})
        failures = [result for result in results if result["exitCode"] != 0]
        report = {
            "summary": f"Executed {len(results)} profile validation command(s) across {len(set(item['repository'] for item in results))} repository(ies).",
            "status": "failed" if failures else "completed",
            "evidence": [f"{item['repository']}:{item['profile']}:{item['operation']}:exit-{item['exitCode']}" for item in results],
            "unknowns": [],
            "details": {"skill":"validate-change","authorizedAutonomy":authorized,"engineeringContexts":{identifier:[practice["id"] for practice in context["practices"]] for identifier,context in contexts.items()},"results":results},
        }
        if failures:
            execution.fail_phase(report)
        else:
            self.complete_phase(execution_id, report)
        return report

    def reassess_tracking(self, task_id: str, impact: dict[str, Any]) -> dict[str, Any]:
        tracking=self.tracking.assess(task_id,impact)
        decision={**tracking["decision"],"reasons":tracking["reasons"],"requiredBefore":tracking["requiredBefore"]}
        return {"task":TaskRegistry(self.project_root).load(task_id),"decision":decision,"tracking":tracking}

    def resume_tracking_executions(self, task_id: str) -> list[str]:
        resumed=[]; root=self.project_root/".ai"/"runtime"/"executions"
        for path in root.glob("*/execution.yaml") if root.is_dir() else []:
            execution=Execution.load(path.parent)
            if execution.data.get("task") == task_id and execution.data.get("blockingReason",{}).get("type") == "external-tracking-required":
                execution.resume("external-tracking-required"); resumed.append(execution.data["metadata"]["id"])
        return resumed

    def execute_tracking_operation(self, task_id: str, operation_id: str, executor: Callable[[dict[str, Any]],dict[str, Any]]) -> dict[str, Any]:
        operation=self.tracking.execute(task_id,operation_id,executor)
        if operation["status"] == "completed" and operation["operation"] in {"create-task","link-task"}: self.resume_tracking_executions(task_id)
        return operation
