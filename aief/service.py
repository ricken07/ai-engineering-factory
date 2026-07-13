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
from .concurrency import ExecutionLease, OperationJournal
from .policy import evaluate_runtime_policy
from .validation import assert_schema
from datetime import datetime, timezone

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

    def _assert_lease(self, execution: Execution, owner: str | None) -> None:
        lease=ExecutionLease(execution.root)
        if lease.read() is not None:
            if owner is None: raise PermissionError("an execution lease is active; owner is required")
            lease.assert_owner(owner)

    def complete_phase(self, execution_id: str, output: dict[str, Any], operation_id: str | None = None, owner: str | None = None) -> Execution:
        execution = self.execution(execution_id)
        self._assert_lease(execution,owner)
        if operation_id:
            result,replayed=OperationJournal(execution.root).execute(operation_id,"complete-phase",output,lambda:self.complete_phase(execution_id,output,owner=owner).data)
            return self.execution(execution_id)
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
        if completed_skill in {"analyze-impact","create-plan"} and output.get("status") == "completed":
            details=output.get("details",{}); observations=details.get("impact",details)
            self.reassess_policy(execution,observations,completed_skill)
        execution.advance(output)
        if completed_skill == "analyze-impact" and output.get("status") == "completed":
            details=output.get("details",{}); impact=details.get("impact",details)
            observations={key:impact[key] for key in ("risk","repositories","changeTypes","domains") if key in impact}
            observations["risk"]=execution.data.get("risk",observations.get("risk","unknown"))
            observations["repositories"]=execution.data.get("repositories",observations.get("repositories",[]))
            self.reassess_tracking(execution.data["task"],observations)
        return execution

    def reassess_policy(self, execution: Execution, observations: dict[str, Any], trigger: str) -> dict[str, Any]:
        task=TaskRegistry(self.project_root).load(execution.data["task"])
        merged={key:observations[key] for key in ("risk","repositories","changeTypes","domains") if key in observations}
        impacted=merged.get("repositories") or task.get("scope",{}).get("repositories",[])
        catalog={item["id"]:item for item in self.project.get("repositories",[])}
        inherited_domains=[domain for identifier in impacted for domain in catalog.get(identifier,{}).get("criticalDomains",[])]
        if inherited_domains: merged["domains"]=list(dict.fromkeys([*merged.get("domains",[]),*inherited_domains]))
        decision=evaluate_runtime_policy(self.factory,self.project,task,merged)
        history=sorted(execution.root.glob("policy-decision-*.yaml")); revision=len(history)+1
        artifact={"apiVersion":"factory.gaddigital.io/v1alpha1","kind":"PolicyDecision",
                  "metadata":{"id":f"policy-{execution.data['metadata']['id']}-{revision:03d}"},"task":execution.data["task"],
                  "risk":{"effective":decision["effectiveRisk"],"reasons":decision["reasons"]},
                  "autonomy":{"requested":decision["requestedAutonomy"],"authorized":decision["authorizedAutonomy"],"reasons":decision["reasons"]},
                  "permissions":{"allowed":decision["allowedActions"],"denied":decision["deniedActions"]},
                  "gates":{"required":decision["requiredGates"]},"matchedRules":decision["matchedRules"]}
        assert_schema(self.factory,"policy-decision.schema.json",artifact)
        name=f"policy-decision-{revision:03d}.yaml"; (execution.root/name).write_text(yaml.safe_dump(artifact,sort_keys=False),encoding="utf-8")
        gates={item["id"]:item for item in execution.data.get("policyGates",[])}
        for identifier in decision["requiredGates"]:
            gates.setdefault(identifier,{"id":identifier,"status":"pending"})
        execution.data.update({"policyDecision":name,"risk":decision["effectiveRisk"],
                               "autonomy":{"requested":decision["requestedAutonomy"],"authorized":decision["authorizedAutonomy"]},
                               "repositories":decision["observations"]["repositories"],"policyGates":list(gates.values())})
        if name not in execution.data["artifacts"]: execution.data["artifacts"].append(name)
        task.setdefault("classification",{}).update({"risk":decision["effectiveRisk"],"domains":decision["observations"]["domains"],"changeTypes":decision["observations"]["changeTypes"]})
        task.setdefault("scope",{})["repositories"]=decision["observations"]["repositories"]
        task["autonomy"]={"requested":decision["requestedAutonomy"],"authorized":decision["authorizedAutonomy"]}
        TaskRegistry(self.project_root).save(task); execution.save()
        return artifact

    def approve_execution(self, execution_id: str, operation_id: str | None = None, owner: str | None = None) -> Execution:
        execution=self.execution(execution_id); self._assert_lease(execution,owner)
        payload={"decision":"approve"}
        if operation_id:
            OperationJournal(execution.root).execute(operation_id,"approve-gate",payload,lambda:self.approve_execution(execution_id,owner=owner).data)
            return self.execution(execution_id)
        phase=execution.next_phase(); execution.advance(approved=True)
        if phase and phase.get("skill") == "create-plan": self._approve_policy_gate(execution,"before-implementation",owner or "human")
        return execution

    def _approve_policy_gate(self, execution: Execution, gate_id: str, approved_by: str) -> None:
        gate=next((item for item in execution.data.get("policyGates",[]) if item["id"]==gate_id),None)
        if gate and gate["status"] != "approved": gate.update({"status":"approved","approvedAt":datetime.now(timezone.utc).isoformat(),"approvedBy":approved_by}); execution.save()

    def approve_policy_gate(self, execution_id: str, gate_id: str, owner: str | None = None) -> Execution:
        execution=self.execution(execution_id); self._assert_lease(execution,owner)
        gate=next((item for item in execution.data.get("policyGates",[]) if item["id"]==gate_id),None)
        if not gate: raise KeyError(f"policy gate is not required: {gate_id}")
        if gate["status"] == "approved": return execution
        self._approve_policy_gate(execution,gate_id,owner or "human")
        if execution.data["status"] == "waiting-approval": execution.data["status"]="running"; execution.save()
        return execution

    def lease(self, execution_id: str, action: str, owner: str | None = None, ttl_seconds: int = 300) -> dict[str, Any] | None:
        manager=ExecutionLease(self.execution(execution_id).root)
        if action=="status": return manager.read()
        if owner is None: raise ValueError("lease owner is required")
        if action=="acquire": return manager.acquire(owner,ttl_seconds)
        if action=="renew": return manager.renew(owner,ttl_seconds)
        if action=="release": return manager.release(owner)
        raise ValueError(f"unknown lease action: {action}")

    def handoff_execution(self, execution_id: str, owner: str | None = None) -> Path:
        execution=self.execution(execution_id); manager=ExecutionLease(execution.root)
        if manager.read() is not None:
            if owner is None: raise PermissionError("lease owner is required to hand off an active execution")
            manager.release(owner)
        return execution.handoff()

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
        required_for_phase={"implementation":{"before-implementation"},"submission":{"before-commit","before-submission"}}
        pending=required_for_phase.get(phase["id"],set()).intersection(item["id"] for item in execution.data.get("policyGates",[]) if item["status"]=="pending")
        if pending:
            execution.data["status"]="waiting-approval"; execution.save()
            return {"execution":execution_id,"status":"waiting-approval","phase":phase,"engineeringContexts":[],"requiredPolicyGates":sorted(pending)}
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
