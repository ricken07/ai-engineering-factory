from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import yaml
from jsonschema import Draft202012Validator
from collections.abc import Callable
from copy import deepcopy
from functools import wraps

from .compiler import compile_workflow
from .intake import INTENT_WORKFLOWS, TaskRegistry, create_request, enforce_activation, normalize_task, resolve_intent
from .project import find_project, load_project, runtime_root
from .runtime import Execution
from .timing import Clock, SystemClock, timestamp
from .identity import actor_identity, declared_actor, review_independence, trusted_session_actor
from .enforcement import enforcement_point, assert_required_enforcement
from .tracking import TaskTrackingManager, evaluate_tracking
from .backlog import BacklogImportManager
from .capabilities import execute_plan, validation_plan
from .engineering import resolve_engineering_context
from .workspace import WorkspaceManager
from .concurrency import ExecutionLease, OperationJournal
from .policy import evaluate_runtime_policy
from .governance import governed_execution_plan, assert_action_authorized
from .validation import assert_schema
from .task_log import TaskEventLog
from .readiness import build_backlog
from .yamlio import load_yaml
from .evidence import build_evidence_bundle, file_fingerprint, fingerprint, git_sha, submission_evidence_gaps, experimental_metrics
from .config import get_api_version

AUTONOMY_RANK = {f"L{level}": level for level in range(5)}


def measured_runtime(method: Callable[..., Any]) -> Callable[..., Any]:
    """Accumulate an outer Runtime operation once, excluding timed nested calls."""
    @wraps(method)
    def wrapped(self: "RuntimeService", subject: Any, *args: Any, **kwargs: Any) -> Any:
        execution_id = subject.data["metadata"]["id"] if isinstance(subject, Execution) else subject
        clock = getattr(self, "clock", None) or SystemClock()
        try:
            initial = self.execution(execution_id)
        except (FileNotFoundError, AttributeError):
            return method(self, subject, *args, **kwargs)
        before = initial.data["timingState"].get("runtimeAccumulatedNs", 0)
        started = clock.monotonic_ns()
        result: Any = None
        try:
            result = method(self, subject, *args, **kwargs)
            return result
        finally:
            current = self.execution(execution_id)
            nested = current.data["timingState"].get("runtimeAccumulatedNs", 0) - before
            current._observe("runtime", clock.monotonic_ns() - started - max(0, nested))
            current.save()
            if (current.root / "evidence-bundle.yaml").is_file():
                build_evidence_bundle(current.root, factory=getattr(self, "factory", None),
                                      project_root=getattr(self, "project_root", None))
            if isinstance(subject, Execution): subject.data = current.data
            if isinstance(result, Execution): result.data = current.data
    return wrapped


class RuntimeService:
    """Deterministic boundary shared by all agent adapters."""

    def __init__(self, project: Path, factory: Path, environment: dict[str, str] | None = None,
                 clock: Clock | None = None):
        self.project_root = find_project(project)
        self.project = load_project(self.project_root)
        self.factory = factory.resolve()
        manifest_path = self.factory / "factory.yaml"
        if not manifest_path.is_file():
            raise FileNotFoundError(f"Factory manifest not found: {manifest_path}")
        manifest = load_yaml(manifest_path)
        installed = manifest.get("metadata", {}).get("version")
        requested = self.project.get("factory", {}).get("version")
        if installed != requested:
            raise RuntimeError(f"project requires Factory {requested}, but {installed} was provided")
        self.factory_version = installed
        self.clock = clock or SystemClock()
        self.tracking = TaskTrackingManager(self.project_root,self.factory,self.project,environment,factory_version=installed)
        self.backlog = BacklogImportManager(self.project_root,self.factory,self.project,environment)

    def _events(self, task_id: str) -> TaskEventLog:
        project = getattr(self, "project", {}) or {}
        return TaskEventLog(
            self.project_root, task_id,
            project_id=project.get("metadata", {}).get("id"),
            factory_version=getattr(self, "factory_version", None),
            clock=getattr(self, "clock", None),
        )

    def intake(self, text: str, agent: str | None = None, intent: str | None = None,
               expected_workflow: str | None = None, confirmed: bool = False) -> dict[str, Any]:
        request = create_request(text, agent=agent)
        if intent is not None:
            if intent not in INTENT_WORKFLOWS:
                raise ValueError(f"unsupported adapter intent: {intent}")
            request["command"] = intent
            request["arguments"] = text.strip()
        intent = resolve_intent(request)
        enforce_activation(intent, (self.project.get("activation") or {}).get("mode", "auto"), confirmed)
        if expected_workflow is not None and intent["workflow"] != expected_workflow:
            raise RuntimeError(
                f"adapter expected workflow {expected_workflow}, but Runtime resolved {intent['workflow']}"
            )
        task = normalize_task(request, intent)
        task_path = TaskRegistry(self.project_root).save(task)
        intake_root = task_path.parent
        (intake_root / "request.yaml").write_text(yaml.safe_dump(request, sort_keys=False, allow_unicode=True), encoding="utf-8")
        (intake_root / "intent.yaml").write_text(yaml.safe_dump(intent, sort_keys=False, allow_unicode=True), encoding="utf-8")
        # The Task id (possibly an extracted external reference) is only known
        # once normalize_task runs, so the three intake events are logged
        # together, in their real logical order, under that final Task id.
        events = self._events(task["metadata"]["id"])
        events.append("request.created", payload={"agent": agent, "status": "created", "request": request["metadata"]["id"]})
        events.append("intent.resolved", payload={
            "agent": agent, "status": "resolved", "intent": intent["intent"],
            "workflow": intent["workflow"], "mutating": intent["mutating"], "confidence": intent["confidence"],
        })
        events.append("task.normalized", payload={
            "agent": agent, "status": "created", "summary": task["objective"]["summary"],
            "intent":intent["intent"], "workflow":intent["workflow"],
            "mutating":intent["mutating"], "source":intent["source"],
        })
        return {"request": request, "intent": intent, "task": task, "path": str(task_path)}

    def start(self, text: str, agent: str | None = None, intent: str | None = None,
              expected_workflow: str | None = None, confirmed: bool = False,
              agent_session: str | None = None, experiment: dict[str, Any] | None = None) -> Execution:
        intake = self.intake(text, agent, intent, expected_workflow, confirmed)
        workflow = compile_workflow(self.factory, intake["task"]["workflow"])
        runtime_started = self.clock.monotonic_ns()
        execution = Execution.create(self.project_root, self.factory, workflow, intake["task"]["metadata"]["id"], agent,
                                     self.clock, agent_session)
        execution.data["reproducibility"] = self._reproducibility(execution, agent, experiment or {})
        execution.record_runtime_duration(runtime_started)
        execution.save()
        self._events(execution.data["task"]).append(
            "workflow.started", execution=execution.data["metadata"]["id"],
            payload={"agent": agent, "phase": execution.next_phase()["id"], "status": execution.data["status"],
                     "workflow":execution.data["workflow"]},
        )
        return execution

    def execution(self, execution_id: str) -> Execution:
        root = runtime_root(self.project_root, getattr(self, "project", None)) / "executions" / execution_id
        if not root.is_dir():
            raise FileNotFoundError(f"execution not found: {execution_id}")
        return Execution.load(root, getattr(self, "clock", None))

    def _observed_value(self, value: Any) -> dict[str, Any]:
        return {"value": value, "availability": "OBSERVED" if value is not None else "UNAVAILABLE"}

    def _commit_or_unavailable(self, path: Path) -> dict[str, Any]:
        try:
            return self._observed_value(git_sha(path))
        except RuntimeError:
            return self._observed_value(None)

    def _reproducibility(self, execution: Execution, agent: str | None, experiment: dict[str, Any]) -> dict[str, Any]:
        adapter_version = None
        if agent:
            adapter_path = self.factory / "adapters" / agent / "adapter.yaml"
            if adapter_path.is_file(): adapter_version = load_yaml(adapter_path).get("metadata", {}).get("version")
        actor = execution.data.get("actors", {}).get("producer", {})
        context_files = []
        for configured in self.project.get("context", {}).values():
            if isinstance(configured, str):
                path = self.project_root / configured
                if path.is_file(): context_files.append({"path": configured, "fingerprint": file_fingerprint(path)})
        repository_commits: dict[str, str | None] = {}
        for repository in self.project.get("repositories", []):
            value = self._commit_or_unavailable(self.project_root / repository["path"])
            repository_commits[repository["id"]] = value["value"]
        repository_availability = "OBSERVED" if repository_commits and all(repository_commits.values()) else "UNAVAILABLE"
        return {
            "aiefVersion": self._observed_value(self.factory_version),
            "aiefCommit": self._commit_or_unavailable(self.factory),
            "projectCommit": self._commit_or_unavailable(self.project_root),
            "repositoryStartingCommit": {"value": repository_commits or None, "availability": repository_availability},
            "workflowVersion": self._observed_value(execution.data["workflow"].get("version")),
            "contextFingerprint": self._observed_value(fingerprint(context_files) if context_files else None),
            "policyFingerprint": self._observed_value(None),
            "governedExecutionPlanFingerprint": self._observed_value(None),
            "agentIdentifier": self._observed_value(actor.get("id")),
            "modelIdentifier": self._observed_value(experiment.get("modelIdentifier")),
            "adapterVersion": self._observed_value(adapter_version),
            "experimentalCondition": self._observed_value(experiment.get("condition")),
            "repeatIndex": self._observed_value(experiment.get("repeatIndex")),
            "environmentIdentifier": self._observed_value(experiment.get("environmentIdentifier")),
        }

    def _session_actor(self, execution: Execution, owner: str | None, actor_type: str = "agent") -> dict[str, Any]:
        if owner:
            lease = ExecutionLease(execution.root).read()
            if lease and lease.get("owner") == owner:
                return trusted_session_actor(owner, actor_type, execution=execution.data["metadata"]["id"])
            return actor_identity(owner, actor_type, "runtime-session", "OBSERVED", execution=execution.data["metadata"]["id"])
        return declared_actor(None, actor_type)

    def _assert_lease(self, execution: Execution, owner: str | None) -> None:
        lease=ExecutionLease(execution.root)
        if lease.read() is not None:
            if owner is None: raise PermissionError("an execution lease is active; owner is required")
            lease.assert_owner(owner)

    @staticmethod
    def _pending_policy_gates(execution: Execution, phase_id: str) -> set[str]:
        required_for_phase = {
            "implementation": {"before-implementation"},
            "submission": {"before-commit", "before-submission"},
        }
        return required_for_phase.get(phase_id, set()).intersection(
            item["id"] for item in execution.data.get("policyGates", []) if item["status"] == "pending"
        )

    @measured_runtime
    def complete_phase(self, execution_id: str, output: dict[str, Any], operation_id: str | None = None, owner: str | None = None) -> Execution:
        execution = self.execution(execution_id)
        self._assert_lease(execution,owner)
        if operation_id:
            result,replayed=OperationJournal(execution.root).execute(operation_id,"complete-phase",output,lambda:self.complete_phase(execution_id,output,owner=owner).data)
            return self.execution(execution_id)
        phase = execution.next_phase()
        if phase is None:
            raise RuntimeError("execution is already complete")
        pending = self._pending_policy_gates(execution, phase["id"])
        if pending:
            raise PermissionError("required policy gates are pending: " + ", ".join(sorted(pending)))
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
        output = deepcopy(output)
        if completed_skill == "implement-change":
            if owner:
                producer = self._session_actor(execution, owner)
                adapter = execution.data.get("agent", {}).get("adapter")
                if adapter: producer["adapter"] = adapter
                execution.observe_actor("producer", producer)
        elif completed_skill == "review-change":
            details = output.setdefault("details", {})
            # Runtime-owned identity always replaces artifact-supplied assurance.
            claimed = details.get("reviewerSession") or details.get("reviewerId")
            reviewer = self._session_actor(execution, owner) if owner else declared_actor(claimed)
            execution.observe_actor("reviewer", reviewer)
            required = execution.data.get("review", {}).get("independentRequired", True)
            independence = review_independence(execution.data.get("actors", {}).get("producer"), reviewer, required=required)
            execution.data["review"] = {"independentRequired": required, "independence": independence}
            details["reviewer"] = reviewer
            details["independence"] = independence
        observations: dict[str, Any] = {}
        if completed_skill == "analyze-impact" and output.get("status") == "completed":
            observations = self._impact_observations(output)
            self._validate_impact_repositories(compiled, observations["repositories"])
        if completed_skill in {"analyze-impact","create-plan"} and output.get("status") == "completed":
            phase_observations = observations or output.get("details", {}).get("impact", output.get("details", {}))
            self.reassess_policy(execution,phase_observations,completed_skill)
        if completed_skill == "submit-change" and output.get("status") == "completed":
            points = [load_yaml(execution.root / name) for name in execution.data.get("enforcementPoints", []) if (execution.root / name).is_file()]
            assert_required_enforcement(points)
            gaps = submission_evidence_gaps(execution.root)
            if gaps:
                raise ValueError("submission evidence is incomplete: " + "; ".join(gaps))
        execution.advance(output)
        events = self._events(execution.data["task"])
        events.append(
            "phase.completed", execution=execution_id,
            payload={"agent": execution.data.get("agent", {}).get("adapter"), "phase":phase["id"],
                     "status": output.get("status", "completed"), "summary":output.get("summary"),
                     "skill":completed_skill, "artifact":f"{phase['id']}.yaml",
                     "evidence":output.get("evidence", [])},
        )
        if execution.data["status"] == "completed":
            bundle = build_evidence_bundle(execution.root, factory=self.factory, project_root=self.project_root)
            assert_schema(self.factory, "evidence-bundle.schema.json", bundle)
            events.append(
                "execution.completed", execution=execution_id,
                payload={"agent": execution.data.get("agent", {}).get("adapter"),
                         "workflow": execution.data["workflow"]},
            )
        if completed_skill == "analyze-impact" and output.get("status") == "completed":
            observations={key:observations[key] for key in ("risk","repositories","changeTypes","domains") if key in observations}
            observations["risk"]=execution.data.get("risk",observations.get("risk","unknown"))
            observations["repositories"]=execution.data.get("repositories",observations.get("repositories",[]))
            self.reassess_tracking(execution.data["task"],observations)
        return execution

    @staticmethod
    def _impact_observations(output: dict[str, Any]) -> dict[str, Any]:
        details = output.get("details")
        if not isinstance(details, dict):
            raise ValueError("analyze-impact details must be an object")
        repositories = details.get("repositories")
        if not isinstance(repositories, list) or any(not isinstance(item, str) or not item.strip() for item in repositories):
            raise ValueError("analyze-impact details.repositories must be an array of repository identifiers")
        return {
            key: details[key]
            for key in ("risk", "repositories", "changeTypes", "domains")
            if key in details
        }

    def _validate_impact_repositories(self, workflow: dict[str, Any], repositories: list[str]) -> None:
        mutating = any(phase.get("skill") == "implement-change" for phase in workflow.get("phases", []))
        if mutating and not repositories:
            raise ValueError(
                "analyze-impact must identify at least one impacted repository before a mutating workflow can continue"
            )
        declared = {item["id"] for item in self.project.get("repositories", [])}
        unknown = sorted(set(repositories) - declared)
        if unknown:
            raise ValueError(f"analyze-impact references unknown project repositories: {', '.join(unknown)}")

    @measured_runtime
    def reassess_policy(self, execution: Execution, observations: dict[str, Any], trigger: str) -> dict[str, Any]:
        task=TaskRegistry(self.project_root).load(execution.data["task"])
        merged={key:observations[key] for key in ("risk","repositories","changeTypes","domains") if key in observations}
        impacted=merged.get("repositories") or task.get("scope",{}).get("repositories",[])
        catalog={item["id"]:item for item in self.project.get("repositories",[])}
        inherited_domains=[domain for identifier in impacted for domain in catalog.get(identifier,{}).get("criticalDomains",[])]
        if inherited_domains: merged["domains"]=list(dict.fromkeys([*merged.get("domains",[]),*inherited_domains]))
        decision=evaluate_runtime_policy(self.factory,self.project,task,merged)
        history=sorted(execution.root.glob("policy-decision-*.yaml")); revision=len(history)+1
        previous_risk=execution.data.get("risk"); previous_autonomy=execution.data.get("autonomy",{}).get("authorized")
        reclassified = history and (previous_risk != decision["effectiveRisk"] or previous_autonomy != decision["authorizedAutonomy"])
        existing_gates={item["id"] for item in execution.data.get("policyGates",[])}
        newly_required=[identifier for identifier in decision["requiredGates"] if identifier not in existing_gates]
        api_version=get_api_version(self.factory)
        artifact={"apiVersion":api_version,"kind":"PolicyDecision",
                  "metadata":{"id":f"policy-{execution.data['metadata']['id']}-{revision:03d}"},"task":execution.data["task"],
                  "risk":{"effective":decision["effectiveRisk"],"reasons":decision["reasons"]},
                  "autonomy":{"requested":decision["requestedAutonomy"],"authorized":decision["authorizedAutonomy"],"reasons":decision["reasons"]},
                  "permissions":{"allowed":decision["allowedActions"],"denied":decision["deniedActions"]},
                  "gates":{"required":decision["requiredGates"]},"matchedRules":decision["matchedRules"],
                  "provenance":decision.get("provenance",[])}
        from .policy import policy_fingerprint
        artifact["fingerprint"] = policy_fingerprint({key:value for key,value in artifact.items() if key != "fingerprint"})
        assert_schema(self.factory,"policy-decision.schema.json",artifact)
        name=f"policy-decision-{revision:03d}.yaml"; (execution.root/name).write_text(yaml.safe_dump(artifact,sort_keys=False),encoding="utf-8")
        plan = governed_execution_plan(api_version, execution.data, decision, name)
        assert_schema(self.factory, "governed-execution-plan.schema.json", plan)
        plan_name=f"governed-execution-plan-{revision:03d}.yaml"
        (execution.root/plan_name).write_text(yaml.safe_dump(plan,sort_keys=False),encoding="utf-8")
        gates={item["id"]:item for item in execution.data.get("policyGates",[])}
        for identifier in decision["requiredGates"]:
            if identifier not in gates:
                gates[identifier] = {"id":identifier,"status":"pending"}
                execution.start_policy_gate(gates[identifier])
        execution.data.update({"policyDecision":name,"governedExecutionPlan":plan_name,"risk":decision["effectiveRisk"],
                               "autonomy":{"requested":decision["requestedAutonomy"],"authorized":decision["authorizedAutonomy"]},
                               "repositories":decision["observations"]["repositories"],"policyGates":list(gates.values())})
        independent_review_required = plan["requirements"]["independentReviewRequired"]
        execution.data["review"] = {
            "independentRequired": independent_review_required,
            "independence": "UNVERIFIED" if independent_review_required else "NOT_REQUIRED",
        }
        reproducibility = execution.data.setdefault("reproducibility", {})
        reproducibility["policyFingerprint"] = self._observed_value(fingerprint(artifact))
        reproducibility["governedExecutionPlanFingerprint"] = self._observed_value(plan["fingerprint"])
        for gate_id in decision["requiredGates"]:
            point = enforcement_point(
                execution=execution.data["metadata"]["id"], action=f"cross-gate:{gate_id}", decision="DENY",
                mechanism_type="runtime", capability="phase-transition", status="ENFORCED",
                evidence_ref=name, required=True,
            )
            self._persist_enforcement_point(execution, point)
        for item in (name, plan_name):
            if item not in execution.data["artifacts"]: execution.data["artifacts"].append(item)
        task.setdefault("classification",{}).update({"risk":decision["effectiveRisk"],"domains":decision["observations"]["domains"],"changeTypes":decision["observations"]["changeTypes"]})
        task.setdefault("scope",{})["repositories"]=decision["observations"]["repositories"]
        task["autonomy"]={"requested":decision["requestedAutonomy"],"authorized":decision["authorizedAutonomy"]}
        TaskRegistry(self.project_root).save(task); execution.save()
        events = self._events(execution.data["task"])
        events.append(
            "policy.reclassified" if reclassified else "policy.evaluated", execution=execution.data["metadata"]["id"],
            payload={"agent": execution.data.get("agent", {}).get("adapter"),
                     "phase": execution.next_phase()["id"] if execution.next_phase() else None,
                     "status":"decided", "summary":f"Risk {decision['effectiveRisk']}, autonomy {decision['authorizedAutonomy']}",
                     "trigger":trigger, "risk":decision["effectiveRisk"],
                     "authorizedAutonomy":decision["authorizedAutonomy"],
                     "requiredGates":decision["requiredGates"], "reasons":decision["reasons"],
                     "artifact":name},
        )
        for identifier in newly_required:
            events.append(
                "gate.requested", execution=execution.data["metadata"]["id"],
                payload={"gate": identifier, "trigger": trigger, "status": "pending"},
            )
        return artifact

    def _persist_enforcement_point(self, execution: Execution, point: dict[str, Any]) -> str:
        assert_schema(self.factory, "enforcement-point.schema.json", point)
        name = f"{point['metadata']['id']}.yaml"
        (execution.root / name).write_text(yaml.safe_dump(point, sort_keys=False), encoding="utf-8")
        if name not in execution.data["enforcementPoints"]: execution.data["enforcementPoints"].append(name)
        if name not in execution.data["artifacts"]: execution.data["artifacts"].append(name)
        execution.save()
        return name

    @measured_runtime
    def authorize_action(self, execution_id: str, action: str, *, required: bool = True) -> dict[str, Any]:
        """The mandatory boundary for actions executed through Runtime.

        This proves only the AIEF-controlled path; it makes no claim about
        commands an agent might invoke outside Runtime.
        """
        execution = self.execution(execution_id)
        if not execution.data.get("policyDecision"):
            point = enforcement_point(
                execution=execution_id, action=action, decision="DENY", mechanism_type="runtime",
                capability="governed-action", status="UNAVAILABLE", required=required,
            )
            self._persist_enforcement_point(execution, point)
            raise PermissionError("no PolicyDecision is available for governed action")
        policy = load_yaml(execution.root / execution.data["policyDecision"])
        denied = action in policy.get("permissions", {}).get("denied", [])
        decision = "DENY" if denied else "ALLOW"
        point = enforcement_point(
            execution=execution_id, action=action, decision=decision, mechanism_type="runtime",
            capability="governed-action", status="ENFORCED", evidence_ref=execution.data["policyDecision"],
            required=required,
        )
        self._persist_enforcement_point(execution, point)
        if denied:
            raise PermissionError(f"policy denies governed action: {action}")
        return point

    @measured_runtime
    def record_external_enforcement(self, execution_id: str, *, action: str, decision: str,
                                    mechanism_type: str, capability: str, status: str,
                                    evidence_ref: str | None = None, required: bool = False) -> dict[str, Any]:
        execution = self.execution(execution_id)
        point = enforcement_point(execution=execution_id, action=action, decision=decision,
                                  mechanism_type=mechanism_type, capability=capability, status=status,
                                  evidence_ref=evidence_ref, required=required)
        self._persist_enforcement_point(execution, point)
        if required: assert_required_enforcement([point])
        return point

    @measured_runtime
    def approve_execution(self, execution_id: str, operation_id: str | None = None, owner: str | None = None) -> Execution:
        execution=self.execution(execution_id); self._assert_lease(execution,owner)
        payload={"decision":"approve"}
        if operation_id:
            OperationJournal(execution.root).execute(operation_id,"approve-gate",payload,lambda:self.approve_execution(execution_id,owner=owner).data)
            return self.execution(execution_id)
        phase=execution.next_phase(); execution.advance(approved=True)
        if phase and phase.get("skill") == "create-plan": self._approve_policy_gate(execution,"before-implementation",owner or "human")
        events = self._events(execution.data["task"])
        events.append(
            "gate.approved", execution=execution_id,
            payload={"agent": execution.data.get("agent", {}).get("adapter"),
                     "phase": phase["id"] if phase else None, "status":"approved",
                     "approvedBy":owner or "human", "gate":"phase-gate",
                     "actor": self._session_actor(execution, owner, "human")},
        )
        if execution.data["status"] == "completed":
            events.append(
                "execution.completed", execution=execution_id,
                payload={"agent": execution.data.get("agent", {}).get("adapter"),
                         "workflow": execution.data["workflow"]},
            )
        return execution

    def _approve_policy_gate(self, execution: Execution, gate_id: str, approved_by: str) -> None:
        gate=next((item for item in execution.data.get("policyGates",[]) if item["id"]==gate_id),None)
        if gate and gate["status"] != "approved":
            owner = None if approved_by == "human" else approved_by
            actor = self._session_actor(execution, owner, "human")
            gate.update({"status":"approved","approvedAt":timestamp(self.clock),"approvedBy":approved_by,"actor":actor})
            execution.data.setdefault("roles", {})["approver"]={"type":"human","identity":approved_by}
            execution.complete_policy_gate(gate)
            execution.save()

    @measured_runtime
    def approve_policy_gate(self, execution_id: str, gate_id: str, owner: str | None = None) -> Execution:
        execution=self.execution(execution_id); self._assert_lease(execution,owner)
        gate=next((item for item in execution.data.get("policyGates",[]) if item["id"]==gate_id),None)
        if not gate: raise KeyError(f"policy gate is not required: {gate_id}")
        if gate["status"] == "approved": return execution
        self._approve_policy_gate(execution,gate_id,owner or "human")
        if execution.data["status"] == "waiting-approval": execution.data["status"]="running"; execution.save()
        self._events(execution.data["task"]).append(
            "gate.approved", execution=execution_id,
            payload={"agent": execution.data.get("agent", {}).get("adapter"),
                     "phase": execution.next_phase()["id"] if execution.next_phase() else None,
                     "status":"approved", "approvedBy":owner or "human", "gate":gate_id},
        )
        return execution

    def lease(self, execution_id: str, action: str, owner: str | None = None, ttl_seconds: int = 300) -> dict[str, Any] | None:
        manager=ExecutionLease(self.execution(execution_id).root)
        if action=="status": return manager.read()
        if owner is None: raise ValueError("lease owner is required")
        if action=="acquire": return manager.acquire(owner,ttl_seconds)
        if action=="renew": return manager.renew(owner,ttl_seconds)
        if action=="release": return manager.release(owner)
        raise ValueError(f"unknown lease action: {action}")

    @measured_runtime
    def cancel_execution(self, execution_id: str, reason: str, owner: str | None = None) -> Execution:
        execution=self.execution(execution_id); self._assert_lease(execution,owner)
        execution.cancel(reason)
        self._events(execution.data["task"]).append(
            "execution.cancelled", execution=execution_id,
            payload={"agent": execution.data.get("agent", {}).get("adapter"), "reason": reason},
        )
        return execution

    def handoff_execution(self, execution_id: str, owner: str | None = None) -> Path:
        execution=self.execution(execution_id); manager=ExecutionLease(execution.root)
        if manager.read() is not None:
            if owner is None: raise PermissionError("lease owner is required to hand off an active execution")
            manager.release(owner)
        return execution.handoff(self.factory)

    def _impacted_repository_ids(self, execution: Execution, task: dict[str, Any]) -> list[str]:
        identifiers = list(execution.data.get("repositories", [])) or list(task.get("scope", {}).get("repositories", []))
        if not identifiers:
            artifact = execution.root / "analyze-impact.yaml"
            if artifact.is_file():
                details = load_yaml(artifact).get("details", {})
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
        task=TaskRegistry(self.project_root).load(execution.data["task"])
        context = resolve_engineering_context(self.factory, self.project_root, self.project, repository_id, phase["skill"],task)
        if persist:
            name = f"engineering-context-{repository_id}-{phase['skill']}.yaml"
            path = execution.root / name
            path.write_text(yaml.safe_dump(context, sort_keys=False, allow_unicode=True), encoding="utf-8")
            if name not in phase["artifacts"]: phase["artifacts"].append(name)
            if name not in execution.data["artifacts"]: execution.data["artifacts"].append(name)
            execution.save()
        return context

    def resolve_repository_context(self, repository_id: str, skill_id: str, task_id: str | None = None) -> dict[str, Any]:
        task=TaskRegistry(self.project_root).load(task_id) if task_id else None
        return resolve_engineering_context(self.factory, self.project_root, self.project, repository_id, skill_id,task)

    def _skill_contract(self, skill_id: str, definition: dict[str, Any]) -> dict[str, Any]:
        root = (self.factory / "core" / "skills" / skill_id).resolve()
        manifest = root / "skill.yaml"
        instructions = root / "SKILL.md"
        schema = (self.factory / definition["outputSchema"]).resolve()
        for label, path in (("manifest", manifest), ("instructions", instructions), ("output schema", schema)):
            if not path.is_file():
                raise FileNotFoundError(f"Core Skill {skill_id} {label} not found: {path}")
        data = load_yaml(manifest)
        if data.get("metadata", {}).get("id") != skill_id:
            raise RuntimeError(f"Core Skill manifest identity mismatch: expected {skill_id}")
        return {
            "id": skill_id,
            "version": data.get("metadata", {}).get("version"),
            "mode": data.get("mode"),
            "root": str(root),
            "manifest": str(manifest),
            "instructions": str(instructions),
            "outputSchema": str(schema),
            "invocation": "core-contract",
        }

    @measured_runtime
    def prepare_phase(self, execution_id: str) -> dict[str, Any]:
        execution = self.execution(execution_id)
        phase = execution.next_phase()
        if phase is None: return {"execution":execution_id,"status":execution.data["status"],"phase":None,"engineeringContexts":[]}
        task = TaskRegistry(self.project_root).load(execution.data["task"])
        pending = self._pending_policy_gates(execution, phase["id"])
        if pending:
            execution.data["status"]="waiting-approval"; execution.save()
            return {"execution":execution_id,"status":"waiting-approval","phase":phase,"engineeringContexts":[],"requiredPolicyGates":sorted(pending)}
        if phase["id"] == "implementation":
            # Re-evaluate from persisted Task observations so a reviewed project
            # configuration change (for example external -> local tracking) is
            # reflected without editing Runtime artifacts by hand.
            tracking=self.tracking.assess(task["metadata"]["id"])
            if tracking["decision"]["level"] == "required" and not tracking["decision"].get("satisfied", tracking["externalTracking"]["status"] == "linked"):
                if execution.data["status"] != "blocked": execution.block({"type":"external-tracking-required","message":"external task tracking must be resolved before implementation","task":task["metadata"]["id"],"requiredBefore":"implementation"})
                return {"execution":execution_id,"status":"blocked","phase":phase,"engineeringContexts":[],"blockingReason":execution.data["blockingReason"],"tracking":tracking}
            if execution.data.get("blockingReason", {}).get("type") == "external-tracking-required":
                execution.resume("external-tracking-required")
            repository_ids = self._impacted_repository_ids(execution, task)
            if not repository_ids:
                execution.block({"type":"workspace-safety-unresolved","message":"impacted repositories are required before implementation"})
                self._events(execution.data["task"]).append(
                    "workspace.blocked", execution=execution_id,
                    payload={"agent": execution.data.get("agent", {}).get("adapter"), "phase": phase["id"],
                             "reason": "workspace-safety-unresolved"},
                )
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
                self._events(execution.data["task"]).append(
                    "workspace.blocked", execution=execution_id,
                    payload={"agent": execution.data.get("agent", {}).get("adapter"), "phase": phase["id"], "reason": reason},
                )
                return {"execution":execution_id,"status":"blocked","phase":phase,"engineeringContexts":[],"blockingReason":execution.data["blockingReason"],"workspace":workspace}
            plan_name=execution.data.get("governedExecutionPlan")
            if not plan_name:
                plans=sorted(execution.root.glob("governed-execution-plan-*.yaml"))
                if plans:
                    plan_name=plans[-1].name
                    execution.data["governedExecutionPlan"]=plan_name
                    if plan_name not in execution.data["artifacts"]: execution.data["artifacts"].append(plan_name)
                    execution.save()
            # Compatibility for executions created before policy reassessment;
            # once a PolicyDecision exists, its governed plan is mandatory.
            if execution.data.get("policyDecision") and (not plan_name or not (execution.root / plan_name).is_file()):
                execution.block({"type":"governed-plan-required","message":"a governed execution plan is required before implementation"})
                return {"execution":execution_id,"status":"blocked","phase":phase,"engineeringContexts":[],"blockingReason":execution.data["blockingReason"]}
            plan=load_yaml(execution.root / plan_name) if plan_name and (execution.root / plan_name).is_file() else {"enforcementPoints":[]}
            for point in plan.get("enforcementPoints", []):
                if not point.get("status",{}).get("enforceable",False):
                    execution.block({"type":"enforcement-unavailable","message":f"required enforcement unavailable: {point.get('action')}"})
                    return {"execution":execution_id,"status":"blocked","phase":phase,"engineeringContexts":[],"blockingReason":execution.data["blockingReason"]}
        repository_ids = self._impacted_repository_ids(execution, task)
        compiled = compile_workflow(self.factory, execution.data["workflow"]["id"])
        definition = next(item for item in compiled["phases"] if item["id"] == phase["id"])
        skill_contract = self._skill_contract(phase["skill"], definition)
        contexts = []
        if definition.get("engineeringContext"):
            contexts = [self.engineering_context(execution_id, identifier) for identifier in repository_ids]
        self._events(execution.data["task"]).append(
            "phase.started", execution=execution_id,
            payload={"agent": execution.data.get("agent", {}).get("adapter"), "phase":phase["id"],
                     "status":execution.data["status"], "skill":phase["skill"],
                     "skillContract":skill_contract,
                     "engineeringContexts":[item["metadata"]["id"] for item in contexts]},
        )
        return {"execution":execution_id,"status":execution.data["status"],"phase":phase,
                "skillContract":skill_contract,"engineeringContexts":contexts}

    @measured_runtime
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
        status = result.get("status") or result.get("decision", {}).get("status")
        if status == "ready":
            if execution.data.get("blockingReason", {}).get("type") in {"workspace-preparation-required", "unrelated-local-changes", "workspace-safety-unresolved"}:
                execution.resume(execution.data["blockingReason"]["type"])
        self._events(execution.data["task"]).append(
            "workspace.prepared" if status == "ready" else "workspace.blocked", execution=execution_id,
            payload={"agent": execution.data.get("agent", {}).get("adapter"),
                     "phase": execution.next_phase()["id"] if execution.next_phase() else None,
                     "action": action, "status": status},
        )
        return result

    @measured_runtime
    def run_profile_validation(self, execution_id: str, runner: Callable[..., Any] | None = None) -> dict[str, Any]:
        execution = self.execution(execution_id)
        if execution.data["status"] in {"waiting-approval", "blocked", "failed", "cancelled"}:
            raise RuntimeError(f"execution state does not allow validation: {execution.data['status']}")
        task = TaskRegistry(self.project_root).load(execution.data["task"])
        authorized = task.get("autonomy", {}).get("authorized") or self.project.get("autonomy", {}).get("default", "L0")
        if AUTONOMY_RANK.get(authorized, -1) < AUTONOMY_RANK["L2"]:
            raise PermissionError(f"profile command execution requires autonomy L2; authorized level is {authorized}")
        plan = self.profile_validation_plan(execution_id)
        execution.data.setdefault("roles", {}).setdefault("verifier", {"type":"runtime","identity":"aief-runtime"})
        execution.save()
        contexts = {identifier:self.engineering_context(execution_id, identifier) for identifier in dict.fromkeys(item["repository"] for item in plan)}
        # engineering_context persists through independently loaded Execution
        # instances; reload before adding timing/identity so neither write can
        # overwrite the other's artifacts.
        execution = self.execution(execution_id)
        results: list[dict[str, Any]] = []
        snapshots: dict[str, str] = {}
        validation_started = self.clock.monotonic_ns()
        verifier = actor_identity(f"runtime:{execution_id}", "runtime", "runtime", "TRUSTED", execution=execution_id)
        execution.observe_actor("verifier", verifier)
        for item in plan:
            command = {key:value for key,value in item.items() if key not in {"repository","cwd"}}
            kwargs = {"runner":runner} if runner is not None else {}
            result = execute_plan([command], Path(item["cwd"]), execute=True, **kwargs)[0]
            results.append({"repository":item["repository"],"cwd":item["cwd"],**result,
                            "verifiedAt":timestamp(self.clock),"verifier":verifier["id"],"execution":execution_id})
            try:
                snapshots[item["repository"]] = git_sha(Path(item["cwd"]))
            except RuntimeError:
                # Unit-test and generated project fixtures may not be Git roots;
                # real workspace validation remains commit-bound by workspace safety.
                snapshots[item["repository"]] = "unavailable"
        execution.record_validation_duration(validation_started)
        execution.save()
        failures = [result for result in results if result["exitCode"] != 0]
        report = {
            "summary": f"Executed {len(results)} profile validation command(s) across {len(set(item['repository'] for item in results))} repository(ies).",
            "status": "failed" if failures else "completed",
            "evidence": [f"{item['repository']}:{item['profile']}:{item['operation']}:exit-{item['exitCode']}" for item in results],
            "unknowns": [],
            "details": {"skill":"validate-change","authorizedAutonomy":authorized,"engineeringContexts":{identifier:[practice["id"] for practice in context["practices"]] for identifier,context in contexts.items()},"results":results,"validationPlan":plan,"commits":snapshots,"verifier":verifier,"evidenceMatrix":[]},
        }
        events = self._events(execution.data["task"])
        agent = execution.data.get("agent", {}).get("adapter")
        if failures:
            execution.fail_phase(report)
            # phase.failed/execution.failed already carry this transition (payload.phase
            # distinguishes "validation"); a dedicated validation.failed event would only
            # duplicate the same fact under a second name.
            events.append(
                "phase.failed", execution=execution_id,
                payload={"agent": agent, "phase":"validation", "status":report["status"],
                         "summary":report["summary"], "evidence":report["evidence"]},
            )
            events.append(
                "execution.failed", execution=execution_id,
                payload={"agent": agent, "phase":"validation", "summary":report["summary"]},
            )
        else:
            self.complete_phase(execution_id, report)  # emits phase.completed (and execution.completed if terminal)
        return report

    @measured_runtime
    def replay_validation(self, execution_id: str, runner: Callable[..., Any] | None = None) -> dict[str, Any]:
        execution = self.execution(execution_id)
        validation_path = execution.root / "validation.yaml"
        if not validation_path.is_file():
            raise FileNotFoundError("validation.yaml is required before replay")
        original = load_yaml(validation_path)
        plan = original.get("details", {}).get("validationPlan", [])
        commits = original.get("details", {}).get("commits", {})
        if not plan:
            raise ValueError("validation plan is missing from validation.yaml")
        results: list[dict[str, Any]] = []
        for item in plan:
            cwd = Path(item["cwd"])
            expected = commits.get(item["repository"])
            actual = git_sha(cwd) if expected != "unavailable" else expected
            if expected and expected != "unavailable" and actual != expected:
                raise RuntimeError(f"repository {item['repository']} changed since validation: expected {expected}, got {actual}")
            command = {key:value for key,value in item.items() if key not in {"repository","cwd"}}
            kwargs = {"runner":runner} if runner is not None else {}
            result = execute_plan([command], cwd, execute=True, **kwargs)[0]
            results.append({"repository":item["repository"],"cwd":str(cwd),**result})
        replay = {"summary":f"Replayed {len(results)} validation command(s) on the recorded commits.","status":"completed" if all(item["exitCode"] == 0 for item in results) else "failed","evidence":[f"{item['repository']}:{item['operation']}:exit-{item['exitCode']}" for item in results],"unknowns":[],"details":{"skill":"replay-validation","sourceValidation":"validation.yaml","results":results,"commits":commits}}
        (execution.root / "validation-replay.yaml").write_text(yaml.safe_dump(replay,sort_keys=False,allow_unicode=True),encoding="utf-8")
        return replay

    def evidence_bundle(self, execution_id: str) -> dict[str, Any]:
        execution=self.execution(execution_id)
        bundle=build_evidence_bundle(execution.root, factory=self.factory, project_root=self.project_root)
        assert_schema(self.factory, "evidence-bundle.schema.json", bundle)
        name="evidence-bundle.yaml"
        if name not in execution.data["artifacts"]:
            execution.data["artifacts"].append(name); execution.save()
        return bundle

    def metrics(self, execution_id: str) -> dict[str, Any]:
        return experimental_metrics(self.execution(execution_id).root, self.execution(execution_id).data)

    def task_events(self, task_id: str) -> list[dict[str, Any]]:
        TaskRegistry(self.project_root).load(task_id)
        return TaskEventLog(self.project_root, task_id).read()

    def task_backlog(self, ready_only: bool = False) -> dict[str, Any]:
        """Dependency-ordered readiness view derived from Task and Execution state."""
        project_id = self.project.get("metadata", {}).get("id", "local-project")
        backlog = build_backlog(self.project_root, project_id, ready_only)
        assert_schema(self.factory, "task-backlog.schema.json", backlog)
        return backlog

    def reassess_tracking(self, task_id: str, impact: dict[str, Any]) -> dict[str, Any]:
        tracking=self.tracking.assess(task_id,impact)
        decision={**tracking["decision"],"reasons":tracking["reasons"],"requiredBefore":tracking["requiredBefore"]}
        return {"task":TaskRegistry(self.project_root).load(task_id),"decision":decision,"tracking":tracking}

    def resume_tracking_executions(self, task_id: str) -> list[str]:
        resumed=[]; root=runtime_root(self.project_root, self.project)/"executions"
        for path in root.glob("*/execution.yaml") if root.is_dir() else []:
            execution=Execution.load(path.parent, self.clock)
            if execution.data.get("task") == task_id and execution.data.get("blockingReason",{}).get("type") == "external-tracking-required":
                execution.resume("external-tracking-required"); resumed.append(execution.data["metadata"]["id"])
        return resumed

    def execute_tracking_operation(self, task_id: str, operation_id: str, executor: Callable[[dict[str, Any]],dict[str, Any]]) -> dict[str, Any]:
        operation=self.tracking.execute(task_id,operation_id,executor)
        if operation["status"] == "completed" and operation["operation"] in {"create-task","link-task"}: self.resume_tracking_executions(task_id)
        return operation

    def execute_backlog_operation(self, import_id: str, operation_id: str, executor: Callable[[dict[str, Any]],dict[str, Any]]) -> dict[str, Any]:
        return self.backlog.execute(import_id,operation_id,executor)
