from pathlib import Path

import yaml

from aief.intake import TaskRegistry
from aief.policy import evaluate_runtime_policy
from aief.project import initialize
from aief.service import RuntimeService
from aief.validation import assert_schema


ROOT=Path(__file__).parents[1]


def task():
    return {"metadata":{"id":"local-1"},"classification":{"risk":"medium","domains":[],"changeTypes":["source-code"]},
            "scope":{"repositories":["api"]},"autonomy":{"requested":"L3"}}


def project():
    return {"autonomy":{"default":"L3","maximum":"L3"}}


def test_policy_derivation_is_deterministic_and_most_restrictive():
    high=evaluate_runtime_policy(ROOT,project(),task(),{"domains":["payment"],"repositories":["api","app"]})
    assert high["effectiveRisk"] == "high" and high["authorizedAutonomy"] == "L2"
    assert {"before-commit","before-submission","before-merge"} <= set(high["requiredGates"])
    assert "push" in high["deniedActions"]
    critical=evaluate_runtime_policy(ROOT,project(),task(),{"changeTypes":["destructive-migration"]})
    assert critical["effectiveRisk"] == "critical" and critical["authorizedAutonomy"] == "L1"
    assert "before-implementation" in critical["requiredGates"]


def test_repository_critical_domains_are_inherited_by_runtime_policy(tmp_path: Path):
    service,execution=runtime(tmp_path); service.project["repositories"][0]["criticalDomains"]=["authentication"]
    decision=service.reassess_policy(execution,{"repositories":["main"],"changeTypes":["source-code"]},"analyze-impact")
    assert decision["risk"]["effective"] == "critical"


def test_tracking_uses_effective_policy_risk_not_lower_agent_observation(tmp_path: Path):
    service,execution=runtime(tmp_path); service.project["repositories"][0]["criticalDomains"]=["authentication"]
    service.complete_phase(execution.data["metadata"]["id"],output("Repository impact",{"risk":"medium","repositories":["main"],"changeTypes":["source-code"]}))
    tracking=yaml.safe_load((service.project_root/".ai/runtime/tasks"/execution.data["task"]/"tracking.yaml").read_text())
    assert tracking["decision"]["level"] == "required"
    assert "externally-track-high-risk" in tracking["reasons"]


def runtime(tmp_path: Path):
    project_root=tmp_path/"project"; initialize(ROOT/"templates/project",project_root)
    data=yaml.safe_load((project_root/".ai/project.yaml").read_text()); data["autonomy"]={"default":"L3","maximum":"L3"}
    data["repositories"]=[{"id":"main","path":".","role":"application","profiles":["generic"],"responsibilities":[],"dependencies":[],"criticalDomains":[]}]
    (project_root/".ai/project.yaml").write_text(yaml.safe_dump(data,sort_keys=False))
    service=RuntimeService(project_root,ROOT); execution=service.start("Implémente une évolution locale")
    task_data=TaskRegistry(project_root).load(execution.data["task"]); task_data["autonomy"]={"requested":"L3"}; TaskRegistry(project_root).save(task_data)
    for phase in execution.data["phases"]:
        if phase["skill"] == "analyze-impact": break
        phase["status"]="completed"
    execution.data["status"]="running"; execution.save()
    return service,execution


def output(summary: str, details: dict):
    return {"summary":summary,"status":"completed","evidence":["verified"],"unknowns":[],"details":details}


def test_runtime_reassesses_after_impact_and_plan_and_never_lowers_risk(tmp_path: Path):
    service,execution=runtime(tmp_path); identifier=execution.data["metadata"]["id"]
    service.complete_phase(identifier,output("Payment impact",{"risk":"high","repositories":["main"],"domains":["payment"],"changeTypes":["source-code"]}))
    current=service.execution(identifier)
    assert current.data["risk"] == "high" and current.data["autonomy"]["authorized"] == "L2"
    first=yaml.safe_load((current.root/"policy-decision-001.yaml").read_text()); assert_schema(ROOT,"policy-decision.schema.json",first)
    current.next_phase()["status"]="completed"; current.data["status"]="running"; current.save()
    service.complete_phase(identifier,output("Migration discovered",{"repositories":["main"],"changeTypes":["destructive-migration"]}))
    current=service.execution(identifier)
    assert current.data["risk"] == "critical" and current.data["autonomy"]["authorized"] == "L1"
    assert current.data["status"] == "waiting-approval"
    assert {item["id"] for item in current.data["policyGates"] if item["status"]=="pending"} >= {"before-implementation","before-commit","before-submission"}
    assert (current.root/"policy-decision-002.yaml").is_file()


def test_pending_dynamic_gate_blocks_before_mutating_phase_and_can_resume(tmp_path: Path):
    service,execution=runtime(tmp_path); identifier=execution.data["metadata"]["id"]
    service.complete_phase(identifier,output("Critical impact",{"risk":"critical","repositories":["main"],"changeTypes":["destructive-migration"]}))
    current=service.execution(identifier)
    for phase in current.data["phases"]:
        if phase["id"] == "implementation": break
        phase["status"]="completed"
    current.data["status"]="running"; current.save()
    prepared=service.prepare_phase(identifier)
    assert prepared["status"] == "waiting-approval" and prepared["requiredPolicyGates"] == ["before-implementation"]
    service.approve_policy_gate(identifier,"before-implementation")
    assert service.execution(identifier).data["status"] == "running"
