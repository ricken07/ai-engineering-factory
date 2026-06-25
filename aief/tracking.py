from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
import re
import yaml

from .intake import TaskRegistry
from .knowledge import safe_task_id
from .provider_runtime import ProviderResolutionError, resolve_task_provider
from .validation import assert_schema


@dataclass(frozen=True)
class TrackingDecision:
    level: str
    reasons: tuple[str, ...]
    required_before: str | None = None
    def as_dict(self) -> dict[str, Any]:
        return {"level":self.level,"reasons":list(self.reasons),**({"requiredBefore":self.required_before} if self.required_before else {})}


TRACKING_RANK={"optional":0,"recommended":1,"required":2}; RISK_RANK={"unknown":0,"low":1,"medium":2,"high":3,"critical":4}

DEFAULT_RULES=[
    {"id":"externally-track-high-risk","when":{"riskAtLeast":"high"},"effect":{"tracking":"required","requiredBefore":["implementation"]}},
    {"id":"externally-track-cross-repository","when":{"impactedRepositoriesGreaterThan":1},"effect":{"tracking":"required","requiredBefore":["implementation"]}},
    {"id":"recommend-functional-tracking","when":{"changeTypesContain":["functional-change","source-code","configuration","dependency"]},"effect":{"tracking":"recommended"}},
    {"id":"optional-informational-work","when":{"taskNatureIn":["informational","validation","review"]},"effect":{"tracking":"optional"}},
    {"id":"optional-documentation-only","when":{"changeTypesContainOnly":["documentation"]},"effect":{"tracking":"optional"}},
    {"id":"optional-small-refactoring","when":{"changeTypesContainOnly":["refactoring"],"riskAtMost":"low"},"effect":{"tracking":"optional"}},
    {"id":"recommend-meaningful-change","when":{"taskNatureIn":["change"],"changeTypesNotContainOnly":["refactoring","documentation"]},"effect":{"tracking":"recommended"}},
]

def _matches(when: dict[str, Any], observations: dict[str, Any]) -> bool:
    risk=observations["risk"]; change_types=set(observations["changeTypes"])
    if "riskAtLeast" in when and RISK_RANK[risk] < RISK_RANK[when["riskAtLeast"]]: return False
    if "riskAtMost" in when and RISK_RANK[risk] > RISK_RANK[when["riskAtMost"]]: return False
    if "impactedRepositoriesGreaterThan" in when and len(observations["repositories"]) <= when["impactedRepositoriesGreaterThan"]: return False
    if "changeTypesContain" in when and not change_types.intersection(when["changeTypesContain"]): return False
    if "changeTypesContainOnly" in when and (not change_types or not change_types <= set(when["changeTypesContainOnly"])): return False
    if "changeTypesNotContainOnly" in when and change_types and change_types <= set(when["changeTypesNotContainOnly"]): return False
    if "taskNatureIn" in when and observations["nature"] not in when["taskNatureIn"]: return False
    return True

def evaluate_tracking(task: dict[str, Any], impact: dict[str, Any] | None = None, rules: list[dict[str, Any]] | None = None) -> TrackingDecision:
    impact = impact or {}; risk = impact.get("risk") or task.get("classification", {}).get("risk", "unknown")
    repositories = impact.get("repositories") or task.get("scope", {}).get("repositories", [])
    change_types = set(impact.get("changeTypes") or task.get("classification", {}).get("changeTypes", [])); nature = task.get("nature", "change")
    observations={"risk":risk,"repositories":repositories,"changeTypes":sorted(change_types),"nature":nature}
    matched=[rule for rule in (rules or DEFAULT_RULES) if _matches(rule.get("when",{}),observations)]
    if not matched: return TrackingDecision("optional",("no-mandatory-tracking-condition",))
    level=max((rule["effect"]["tracking"] for rule in matched),key=lambda value:TRACKING_RANK[value])
    effective=[rule for rule in matched if TRACKING_RANK[rule["effect"]["tracking"]] == TRACKING_RANK[level]]
    before=[]
    for rule in effective: before.extend(rule["effect"].get("requiredBefore",[]))
    before=sorted(set(before))
    return TrackingDecision(level,tuple(rule["id"] for rule in effective),before[0] if before else None)


class TaskTrackingManager:
    def __init__(self, project_root: Path, factory: Path, project: dict[str, Any], environment: dict[str, str] | None = None):
        self.project_root, self.factory, self.project, self.environment = project_root, factory, project, environment
        self.registry = TaskRegistry(project_root)
        policy=yaml.safe_load((factory/"core"/"policies"/"task-tracking-policy.yaml").read_text(encoding="utf-8")); self.rules=policy["rules"]

    def _root(self, task_id: str) -> Path:
        root = self.project_root/".ai"/"runtime"/"tasks"/safe_task_id(task_id); root.mkdir(parents=True,exist_ok=True); return root
    def _write(self, task_id: str, name: str, data: dict[str, Any]) -> Path:
        path=self._root(task_id)/name; path.parent.mkdir(parents=True,exist_ok=True); path.write_text(yaml.safe_dump(data,sort_keys=False,allow_unicode=True),encoding="utf-8"); return path
    def _read(self, task_id: str, name: str) -> dict[str, Any]:
        path=self._root(task_id)/name
        if not path.is_file(): raise FileNotFoundError(f"tracking artifact not found: {name}")
        return yaml.safe_load(path.read_text(encoding="utf-8"))

    def assess(self, task_id: str, impact: dict[str, Any] | None = None) -> dict[str, Any]:
        task=self.registry.load(task_id); decision=evaluate_tracking(task,impact,self.rules)
        external = task.get("source",{}).get("type") == "issue"
        reference = task.get("source",{}).get("reference")
        status = "linked" if external and reference else task.get("tracking",{}).get("external",{}).get("status","unresolved")
        artifact={"apiVersion":"factory.gaddigital.io/v1alpha1","kind":"TaskTrackingDecision","metadata":{"id":f"tracking-{safe_task_id(task_id)}"},"task":task_id,"decision":{"level":decision.level},"reasons":list(decision.reasons),"requiredBefore":([decision.required_before] if decision.required_before else []),"provider":{"capability":"task-provider","status":"unresolved"},"duplicateSearch":{"required":not external,"status":"skipped" if external else "pending"},"externalTracking":{"status":status,**({"reference":reference} if reference else {})}}
        assert_schema(self.factory,"task-tracking-decision.schema.json",artifact)
        task["tracking"]={**task.get("tracking",{}),"level":decision.level}
        if reference: task["tracking"].update({"canonicalReference":reference,"external":{"provider":task.get("source",{}).get("provider","external"),"reference":reference,"status":"linked"}})
        if impact:
            if impact.get("repositories") is not None: task.setdefault("scope",{})["repositories"]=impact["repositories"]
            task.setdefault("classification",{})
            for key in ("risk","changeTypes","domains"):
                if impact.get(key) is not None: task["classification"][key]=impact[key]
        self.registry.save(task); self._write(task_id,"tracking.yaml",artifact); return artifact

    def resolve_provider(self, task_id: str, operations: list[str] | None = None, agent: str | None = None) -> dict[str, Any]:
        operations=operations or ["search-task","create-task","link-task"]
        try: resolution=resolve_task_provider(self.factory,self.project_root,self.project,operations,agent,self.environment)
        except ProviderResolutionError as exc:
            binding=self.project.get("integrations",{}).get("task-provider"); provider=binding.get("provider") if isinstance(binding,dict) else binding or "unresolved"
            mcp_status={"MCP_NOT_CONFIGURED":"not-configured","MCP_UNAVAILABLE":"unavailable","AUTHENTICATION_REQUIRED":"authentication-required"}.get(exc.code,"unavailable")
            resolution={"apiVersion":"factory.gaddigital.io/v1alpha1","kind":"IntegrationResolution","metadata":{"id":f"task-provider-{provider}"},"capability":"task-provider","provider":{"id":provider,"version":"0.0.0"},"status":"unavailable","operations":[],"mcp":{"status":mcp_status},"error":{"code":exc.code,"message":exc.message}}
            self._write(task_id,"provider-resolution.yaml",resolution)
            try:
                tracking=self._read(task_id,"tracking.yaml"); tracking["provider"]={"capability":"task-provider","id":provider,"status":"unavailable"}; tracking["externalTracking"]["status"]="unavailable"; self._write(task_id,"tracking.yaml",tracking)
            except FileNotFoundError: pass
            raise
        self._write(task_id,"provider-resolution.yaml",resolution)
        tracking=self._read(task_id,"tracking.yaml"); tracking["provider"]={"capability":"task-provider","id":resolution["provider"]["id"],"status":"available"}; self._write(task_id,"tracking.yaml",tracking)
        return resolution

    def _operation(self, task_id: str, operation: str, input_data: dict[str, Any], approval_required: bool, suffix: str = "") -> dict[str, Any]:
        operation_id=f"{operation}-{safe_task_id(task_id)}{suffix}"
        relative=f"operations/{operation_id}.yaml"; path=self._root(task_id)/relative
        if path.is_file(): return yaml.safe_load(path.read_text(encoding="utf-8"))
        resolution=self.resolve_provider(task_id,[operation]); provider=resolution["provider"]["id"]
        status="waiting-approval" if approval_required else "pending"
        data={"apiVersion":"factory.gaddigital.io/v1alpha1","kind":"ExternalOperation","metadata":{"id":operation_id},"task":task_id,"provider":provider,"capability":"task-provider","operation":operation,"status":status,"approval":{"required":approval_required,"status":"pending" if approval_required else "not-required"},"input":{**input_data,"operationId":operation_id}}
        assert_schema(self.factory,"external-operation.schema.json",data)
        self._write(task_id,relative,data); return data

    def prepare_search(self, task_id: str) -> dict[str, Any]:
        task=self.registry.load(task_id)
        if task.get("tracking",{}).get("external",{}).get("status") == "linked": raise ValueError("task is already linked")
        text=" ".join(filter(None,[task["objective"]["summary"],task["objective"].get("description","")]))
        keywords=sorted(set(re.findall(r"[A-Za-zÀ-ÿ0-9_-]{4,}",text.lower())))[:20]
        query={"summary":task["objective"]["summary"],"keywords":keywords,"domains":task.get("classification",{}).get("domains",[]),"repositories":task.get("scope",{}).get("repositories",[])}
        operation=self._operation(task_id,"search-task",{"query":query},False)
        tracking=self._read(task_id,"tracking.yaml"); tracking["externalTracking"]["status"]="searching"; self._write(task_id,"tracking.yaml",tracking)
        return operation

    def complete_search(self, task_id: str, matches: list[dict[str, Any]]) -> dict[str, Any]:
        operation=self._read(task_id,f"operations/search-task-{safe_task_id(task_id)}.yaml")
        if operation["status"] == "completed": return self._read(task_id,"search.yaml")
        operation["status"]="completed"; operation["result"]={"matchCount":len(matches)}; self._write(task_id,f"operations/{operation['metadata']['id']}.yaml",operation)
        search={"apiVersion":"factory.gaddigital.io/v1alpha1","kind":"ExternalTaskSearch","metadata":{"id":f"search-{safe_task_id(task_id)}"},"task":task_id,"provider":operation["provider"],"query":operation["input"]["query"],"matches":matches,"status":"completed"}
        assert_schema(self.factory,"external-task-search.schema.json",search)
        self._write(task_id,"search.yaml",search); tracking=self._read(task_id,"tracking.yaml"); tracking["duplicateSearch"]["status"]="completed"
        tracking["externalTracking"]["status"]="awaiting-link" if any(item["recommendation"] in {"link-existing","review"} for item in matches) else "awaiting-creation"; self._write(task_id,"tracking.yaml",tracking); return search

    def write_proposal(self, task_id: str, proposal: dict[str, Any]) -> Path:
        if proposal.get("kind") != "ExternalTaskProposal" or proposal.get("sourceTask") != task_id: raise ValueError("invalid ExternalTaskProposal")
        assert_schema(self.factory,"external-task-proposal.schema.json",proposal)
        search=self._read(task_id,"tracking.yaml")
        if search["duplicateSearch"]["status"] != "completed": raise RuntimeError("duplicate search must complete before task creation")
        return self._write(task_id,"external-task-proposal.yaml",proposal)

    def prepare_create(self, task_id: str, approved: bool = False) -> dict[str, Any]:
        proposal=self._read(task_id,"external-task-proposal.yaml"); task=self.registry.load(task_id)
        autonomy=task.get("autonomy",{}).get("authorized") or self.project.get("autonomy",{}).get("default","L0")
        required=int(autonomy[1:]) < 3
        operation=self._operation(task_id,"create-task",{"proposal":proposal},required)
        if approved and operation["status"] == "waiting-approval": operation=self.approve(task_id,operation["metadata"]["id"],True)
        tracking=self._read(task_id,"tracking.yaml"); tracking["externalTracking"]["status"]="awaiting-creation"; self._write(task_id,"tracking.yaml",tracking); return operation

    def prepare_link(self, task_id: str, reference: str, approved: bool = False) -> dict[str, Any]:
        operation=self._operation(task_id,"link-task",{"reference":reference},True,suffix=f"-{safe_task_id(reference)}")
        if approved and operation["status"] == "waiting-approval": operation=self.approve(task_id,operation["metadata"]["id"],True)
        return operation

    def approve(self, task_id: str, operation_id: str, approved: bool) -> dict[str, Any]:
        operation=self._read(task_id,f"operations/{operation_id}.yaml")
        if operation["status"] != "waiting-approval": raise RuntimeError("operation is not waiting for approval")
        operation["approval"]["status"]="approved" if approved else "rejected"; operation["status"]="pending" if approved else "failed"
        if not approved: operation["error"]={"code":"HUMAN_GATE_REJECTED","message":"external action was rejected"}
        self._write(task_id,f"operations/{operation_id}.yaml",operation); return operation

    def execute(self, task_id: str, operation_id: str, executor: Callable[[dict[str, Any]],dict[str, Any]]) -> dict[str, Any]:
        operation=self._read(task_id,f"operations/{operation_id}.yaml")
        if operation["status"] == "completed": return operation
        if operation["status"] == "failed" and operation.get("error",{}).get("code") == "HUMAN_GATE_REJECTED": raise RuntimeError("rejected external operation cannot be retried")
        if operation["status"] not in {"pending","failed"}: raise RuntimeError(f"operation cannot execute from status {operation['status']}")
        operation["status"]="running"; self._write(task_id,f"operations/{operation_id}.yaml",operation)
        try: result=executor(operation)
        except Exception as exc:
            code=getattr(exc,"code","MCP_UNAVAILABLE"); operation["status"]="failed"; operation["error"]={"code":code,"message":str(exc)}; self._write(task_id,f"operations/{operation_id}.yaml",operation)
            if code in {"MCP_UNAVAILABLE","MCP_NOT_CONFIGURED","AUTHENTICATION_REQUIRED"}:
                tracking=self._read(task_id,"tracking.yaml"); tracking["provider"]["status"]="unavailable"; tracking["externalTracking"]["status"]="unavailable"; self._write(task_id,"tracking.yaml",tracking)
            return operation
        if operation["operation"] in {"create-task","link-task"}:
            reference=result.get("reference") or operation["input"].get("reference")
            if not reference: raise ValueError("provider result must contain reference")
        operation["status"]="completed"; operation["result"]=result; operation.pop("error",None); self._write(task_id,f"operations/{operation_id}.yaml",operation)
        if operation["operation"] in {"create-task","link-task"}:
            self.link_local(task_id,operation["provider"],reference)
        return operation

    def link_local(self, task_id: str, provider: str, reference: str) -> dict[str, Any]:
        task=self.registry.load(task_id); task.setdefault("tracking",{}).update({"canonicalReference":reference,"external":{"provider":provider,"reference":reference,"status":"linked"}}); self.registry.save(task)
        tracking=self._read(task_id,"tracking.yaml"); tracking["provider"]={"capability":"task-provider","id":provider,"status":"available"}; tracking["externalTracking"]={"status":"linked","reference":reference}; self._write(task_id,"tracking.yaml",tracking); return task


def promotion_plan(factory, project: dict[str, Any], task: dict[str, Any], environment: dict[str, str] | None = None) -> dict[str, Any]:
    if task.get("source",{}).get("type") != "local": raise ValueError("only a local Task can be promoted")
    # Compatibility helper; concrete stateful promotion is managed by TaskTrackingManager.
    return {"task":task["metadata"]["id"],"provider":project.get("integrations",{}).get("task-provider",{}).get("provider") if isinstance(project.get("integrations",{}).get("task-provider"),dict) else project.get("integrations",{}).get("task-provider"),"requiredOperations":["search-task","create-task","link-task"],"gate":"before-external-task-creation","duplicateSearchRequired":True,"approved":False}
