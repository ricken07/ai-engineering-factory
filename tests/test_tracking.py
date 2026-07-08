from pathlib import Path

import pytest
import yaml

from aief.intake import TaskRegistry
from aief.project import initialize
from aief.provider_runtime import ProviderResolutionError, resolve_task_provider
from aief.service import RuntimeService
from aief.tracking import evaluate_tracking, promotion_plan
from aief.validation import validate_project


ROOT = Path(__file__).parents[1]
ENV = {"JIRA_MCP_URL":"https://mcp.example.test","JIRA_TOKEN":"secret"}


def task(nature="change"):
    return {"metadata":{"id":"local-1"},"source":{"type":"local"},"nature":nature,"classification":{}}


def service(tmp_path: Path, autonomy="L2"):
    project=tmp_path/"project"; initialize(ROOT/"templates/project",project)
    data=yaml.safe_load((project/".ai/project.yaml").read_text()); data["integrations"]={"task-provider":{"provider":"jira"}}; data["autonomy"]["default"]=autonomy
    (project/".ai/project.yaml").write_text(yaml.safe_dump(data,sort_keys=False))
    return RuntimeService(project,ROOT,ENV)


def local_task(runtime: RuntimeService, text="Corrige le problème de callback MTN"):
    intake=runtime.intake(text); identifier=intake["task"]["metadata"]["id"]
    runtime.reassess_tracking(identifier,{"risk":"high","repositories":["api","app"],"changeTypes":["functional-change"],"domains":["payment"]})
    return identifier


def proposal(identifier):
    return {"apiVersion":"factory.gaddigital.io/v1alpha1","kind":"ExternalTaskProposal","metadata":{"id":f"proposal-{identifier}"},"sourceTask":identifier,"title":"Fix MTN callback mapping","description":"FAILED callbacks remain PENDING.","acceptanceCriteria":["FAILED maps to FAILED"],"repositories":["api"],"risk":"high"}


def test_tracking_policy_optional_recommended_and_required():
    assert evaluate_tracking(task("informational")).level == "optional"
    assert evaluate_tracking(task(),{"risk":"low","changeTypes":["refactoring"]}).level == "optional"
    assert evaluate_tracking(task(),{"risk":"medium","changeTypes":["functional-change"]}).level == "recommended"
    decision=evaluate_tracking(task(),{"risk":"high","repositories":["api","app"]})
    assert decision.level == "required" and set(decision.reasons) == {"externally-track-high-risk","externally-track-cross-repository"}


def test_provider_resolution_errors_are_explicit(tmp_path):
    project=tmp_path/"project"; initialize(ROOT/"templates/project",project); data=yaml.safe_load((project/".ai/project.yaml").read_text())
    with pytest.raises(ProviderResolutionError) as missing: resolve_task_provider(ROOT,project,data,["search-task"],environment={})
    assert missing.value.code == "PROVIDER_NOT_CONFIGURED"
    data["integrations"]={"task-provider":{"provider":"confluence"}}
    with pytest.raises(ProviderResolutionError) as unsupported: resolve_task_provider(ROOT,project,data,["search-task"],environment={})
    assert unsupported.value.code == "CAPABILITY_UNSUPPORTED"
    data["integrations"]={"task-provider":{"provider":"jira"}}
    with pytest.raises(ProviderResolutionError) as endpoint: resolve_task_provider(ROOT,project,data,["search-task"],environment={})
    assert endpoint.value.code == "MCP_NOT_CONFIGURED"
    with pytest.raises(ProviderResolutionError) as auth: resolve_task_provider(ROOT,project,data,["search-task"],environment={"JIRA_MCP_URL":"https://mcp"})
    assert auth.value.code == "AUTHENTICATION_REQUIRED"


def test_unavailable_provider_resolution_is_persisted_without_fallback(tmp_path):
    configured=service(tmp_path); identifier=local_task(configured)
    runtime=RuntimeService(configured.project_root,ROOT,{})
    with pytest.raises(ProviderResolutionError) as error: runtime.tracking.resolve_provider(identifier)
    assert error.value.code == "MCP_NOT_CONFIGURED"
    resolution=yaml.safe_load((runtime.project_root/".ai/runtime/tasks"/identifier/"provider-resolution.yaml").read_text())
    assert resolution["status"] == "unavailable" and resolution["provider"]["id"] == "jira"
    assert resolution["error"]["code"] == "MCP_NOT_CONFIGURED"


def test_duplicate_search_requires_human_link_and_resumes_execution(tmp_path):
    runtime=service(tmp_path); identifier=local_task(runtime)
    execution=runtime.start("Corrige un autre problème local")
    # Rebind this execution to the tracked task and position it before implementation.
    execution.data["task"]=identifier
    for phase in execution.data["phases"]:
        if phase["id"] == "implementation": break
        phase["status"]="completed"
    execution.data["status"]="running"; execution.save()
    assert runtime.prepare_phase(execution.data["metadata"]["id"])["status"] == "blocked"
    search=runtime.tracking.prepare_search(identifier); assert search["operation"] == "search-task"
    matches=[{"reference":"EMM-441","title":"Incorrect MTN callback status mapping","confidence":"high","rationale":["same component","same behavior"],"recommendation":"link-existing"}]
    runtime.tracking.complete_search(identifier,matches)
    link=runtime.tracking.prepare_link(identifier,"EMM-441")
    assert link["status"] == "waiting-approval"
    link=runtime.tracking.approve(identifier,link["metadata"]["id"],True)
    runtime.execute_tracking_operation(identifier,link["metadata"]["id"],lambda operation:{"reference":"EMM-441"})
    assert TaskRegistry(runtime.project_root).load(identifier)["tracking"]["canonicalReference"] == "EMM-441"
    assert runtime.execution(execution.data["metadata"]["id"]).data["status"] == "running"


def test_no_duplicate_creation_is_gated_and_idempotent(tmp_path):
    runtime=service(tmp_path,"L2"); identifier=local_task(runtime)
    runtime.tracking.prepare_search(identifier); runtime.tracking.complete_search(identifier,[]); runtime.tracking.write_proposal(identifier,proposal(identifier))
    operation=runtime.tracking.prepare_create(identifier)
    assert operation["status"] == "waiting-approval"
    operation=runtime.tracking.approve(identifier,operation["metadata"]["id"],True)
    calls=[]
    def provider(operation): calls.append(operation["input"]["operationId"]); return {"reference":"EMM-582"}
    first=runtime.execute_tracking_operation(identifier,operation["metadata"]["id"],provider)
    second=runtime.execute_tracking_operation(identifier,operation["metadata"]["id"],provider)
    assert first == second and calls == [f"create-task-{identifier}"]
    assert TaskRegistry(runtime.project_root).load(identifier)["tracking"]["canonicalReference"] == "EMM-582"
    assert validate_project(runtime.project_root,ROOT) == []


def test_create_retry_reuses_operation_id_after_mcp_failure(tmp_path):
    runtime=service(tmp_path,"L3"); identifier=local_task(runtime)
    runtime.tracking.prepare_search(identifier); runtime.tracking.complete_search(identifier,[]); runtime.tracking.write_proposal(identifier,proposal(identifier))
    operation=runtime.tracking.prepare_create(identifier); seen=[]
    class Unavailable(RuntimeError): code="MCP_UNAVAILABLE"
    def unavailable(value): seen.append(value["input"]["operationId"]); raise Unavailable("timeout")
    failed=runtime.execute_tracking_operation(identifier,operation["metadata"]["id"],unavailable); assert failed["error"]["code"] == "MCP_UNAVAILABLE"
    completed=runtime.execute_tracking_operation(identifier,operation["metadata"]["id"],lambda value:(seen.append(value["input"]["operationId"]) or {"reference":"EMM-600"}))
    assert completed["status"] == "completed" and seen[0] == seen[1]


def test_rejected_creation_stays_unlinked_and_cannot_retry(tmp_path):
    runtime=service(tmp_path,"L2"); identifier=local_task(runtime)
    runtime.tracking.prepare_search(identifier); runtime.tracking.complete_search(identifier,[]); runtime.tracking.write_proposal(identifier,proposal(identifier))
    operation=runtime.tracking.prepare_create(identifier); operation=runtime.tracking.approve(identifier,operation["metadata"]["id"],False)
    with pytest.raises(RuntimeError,match="rejected external operation cannot be retried"):
        runtime.execute_tracking_operation(identifier,operation["metadata"]["id"],lambda value:{"reference":"SHOULD-NOT-EXIST"})
    assert "canonicalReference" not in TaskRegistry(runtime.project_root).load(identifier)["tracking"]


def test_external_operation_approval_is_idempotent(tmp_path):
    runtime=service(tmp_path); identifier=local_task(runtime)
    runtime.tracking.prepare_search(identifier); runtime.tracking.complete_search(identifier,[]); runtime.tracking.write_proposal(identifier,proposal(identifier))
    operation=runtime.tracking.prepare_create(identifier)
    first=runtime.tracking.approve(identifier,operation["metadata"]["id"],True)
    second=runtime.tracking.approve(identifier,operation["metadata"]["id"],True)
    assert first == second and second["approval"]["status"] == "approved"


def test_external_task_is_already_canonical_and_needs_no_creation(tmp_path):
    runtime=service(tmp_path); intake=runtime.intake("/implement EMM-123")
    tracking=runtime.tracking.assess(intake["task"]["metadata"]["id"],{"risk":"high"})
    assert tracking["externalTracking"] == {"status":"linked","reference":"EMM-123"}
    assert tracking["duplicateSearch"]["status"] == "skipped"
    with pytest.raises(ValueError,match="already linked"): runtime.tracking.prepare_search("EMM-123")


def test_compatibility_promotion_plan_remains_provider_agnostic():
    plan=promotion_plan(None,{"integrations":{"task-provider":{"provider":"jira"}}},task())
    assert plan["provider"] == "jira" and plan["requiredOperations"] == ["search-task","create-task","link-task"]
