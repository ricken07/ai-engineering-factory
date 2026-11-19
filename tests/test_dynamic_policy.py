from pathlib import Path

import pytest
import yaml

from aief.intake import TaskRegistry
from aief.policy import evaluate_runtime_policy, inherited_critical_domains
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
    service.prepare_phase(execution.data["metadata"]["id"])
    service.complete_phase(execution.data["metadata"]["id"],output("Repository impact",{"risk":"medium","repositories":["main"],"changeTypes":["source-code"]}))
    tracking=yaml.safe_load((service.project_root/".ai/runtime/tasks"/execution.data["task"]/"tracking.yaml").read_text())
    assert tracking["decision"]["level"] == "required"
    assert "externally-track-high-risk" in tracking["reasons"]


def runtime(tmp_path: Path):
    project_root=tmp_path/"project"; initialize(ROOT/"templates/project",project_root)
    data=yaml.safe_load((project_root/".ai/project.yaml").read_text()); data["autonomy"]={"default":"L3","maximum":"L3"}
    data["repositories"]=[{"id":"main","path":".","role":"application","profiles":["generic"],"responsibilities":[],"dependencies":[],"criticalDomains":[]}]
    (project_root/".ai/project.yaml").write_text(yaml.safe_dump(data,sort_keys=False))
    service=RuntimeService(project_root,ROOT); execution=service.start("Implémente une évolution locale",confirmed=True)
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
    service.prepare_phase(identifier)
    service.complete_phase(identifier,output("Payment impact",{"risk":"high","repositories":["main"],"domains":["payment"],"changeTypes":["source-code"]}))
    current=service.execution(identifier)
    assert current.data["risk"] == "high" and current.data["autonomy"]["authorized"] == "L2"
    first=yaml.safe_load((current.root/"policy-decision-001.yaml").read_text()); assert_schema(ROOT,"policy-decision.schema.json",first)
    current.next_phase()["status"]="completed"; current.data["status"]="running"; current.save()
    service.prepare_phase(identifier)
    service.complete_phase(identifier,output("Migration discovered",{"repositories":["main"],"changeTypes":["destructive-migration"]}))
    current=service.execution(identifier)
    assert current.data["risk"] == "critical" and current.data["autonomy"]["authorized"] == "L1"
    assert current.data["status"] == "waiting-approval"
    assert {item["id"] for item in current.data["policyGates"] if item["status"]=="pending"} >= {"before-implementation","before-commit","before-submission"}
    assert (current.root/"policy-decision-002.yaml").is_file()


def test_pending_dynamic_gate_blocks_before_mutating_phase_and_can_resume(tmp_path: Path):
    service,execution=runtime(tmp_path); identifier=execution.data["metadata"]["id"]
    service.prepare_phase(identifier)
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


def test_terminated_execution_closes_gates_that_never_held_it(tmp_path: Path):
    service,execution=runtime(tmp_path); identifier=execution.data["metadata"]["id"]
    service.prepare_phase(identifier)
    service.complete_phase(identifier,output("Payment impact",{"risk":"high","repositories":["main"],"domains":["payment"],"changeTypes":["source-code"]}))
    service.cancel_execution(identifier,"analysis only")
    current=service.execution(identifier)
    gates={item["id"]:item for item in current.data["policyGates"]}
    assert {"before-commit","before-submission","before-merge"} <= set(gates)
    for gate in gates.values():
        assert gate["status"] == "not-triggered"
        assert gate["timing"]["closedAt"] and gate["timing"]["decidedAt"] is None and "blockedAt" not in gate["timing"]
        assert gate["timing"]["durationMs"] == {"value": 0, "availability": "OBSERVED"}
    assert current.data["timingState"]["activeGateCount"] == 0
    closed=[event for event in service._events(current.data["task"]).read() if event["event"]["type"] == "gate.closed"]
    assert {event["payload"]["gate"] for event in closed} == set(gates)
    with pytest.raises(RuntimeError, match="policy gate is not-triggered"):
        service.approve_policy_gate(identifier,"before-merge")


def test_execution_ending_while_gate_waits_withdraws_it(tmp_path: Path):
    service,execution=runtime(tmp_path); identifier=execution.data["metadata"]["id"]
    service.prepare_phase(identifier)
    service.complete_phase(identifier,output("Critical impact",{"risk":"critical","repositories":["main"],"changeTypes":["destructive-migration"]}))
    current=service.execution(identifier)
    for phase in current.data["phases"]:
        if phase["id"] == "implementation": break
        phase["status"]="completed"
    current.data["status"]="running"; current.save()
    assert service.prepare_phase(identifier)["status"] == "waiting-approval"
    service.cancel_execution(identifier,"abandoned")
    current=service.execution(identifier)
    gate=next(item for item in current.data["policyGates"] if item["id"] == "before-implementation")
    assert gate["status"] == "withdrawn" and gate["timing"]["blockedAt"] and gate["timing"]["closedAt"]
    assert gate["timing"]["durationMs"]["availability"] == "OBSERVED"
    assert current.data["metrics"]["gateWaiting"]["durationMs"]["availability"] == "OBSERVED"
    assert current.data["timingState"]["activeGateCount"] == 0


def layered_factory(tmp_path: Path, rules: list) -> Path:
    factory = tmp_path / "factory"; (factory / "organization/catalogs").mkdir(parents=True)
    for name in ("core", "profiles"): (factory / name).symlink_to(ROOT / name)
    catalog = {"apiVersion": "aief.dev/v1alpha1", "kind": "OrganizationCatalog",
               "metadata": {"id": "acme", "name": "Acme", "version": "1.0.0"},
               "extends": [], "practiceRefs": [], "profileBindings": {}, "policy": {"riskRules": rules}}
    assert_schema(ROOT, "organization-catalog.schema.json", catalog)
    (factory / "organization/catalogs/acme.yaml").write_text(yaml.safe_dump(catalog))
    return factory


def test_organization_risk_rules_raise_risk_from_domain_knowledge(tmp_path: Path):
    factory = layered_factory(tmp_path, [{"id": "identity-is-critical", "when": {"domains": {"containsAny": ["identity"]}}, "effect": {"riskAtLeast": "critical"}}])
    data = {**project(), "engineering": {"organizationCatalogs": ["acme@1.0.0"]}}
    plain = evaluate_runtime_policy(factory, project(), task(), {"domains": ["identity"]})
    raised = evaluate_runtime_policy(factory, data, task(), {"domains": ["identity"]})
    assert plain["effectiveRisk"] == "medium"
    assert raised["effectiveRisk"] == "critical" and raised["authorizedAutonomy"] == "L1"
    assert "organization:acme:identity-is-critical" in raised["matchedRules"]
    assert "before-implementation" in raised["requiredGates"]
    untouched = evaluate_runtime_policy(factory, data, task(), {"domains": ["finance"]})
    assert untouched["effectiveRisk"] == "medium"


def test_layered_risk_rules_never_lower_risk(tmp_path: Path):
    data = {**project(), "repositories": [{"id": "api", "policy": {"riskRules": [
        {"id": "payment-low", "when": {"domains": {"containsAny": ["payment"]}}, "effect": {"riskAtLeast": "low"}}]}}]}
    decision = evaluate_runtime_policy(ROOT, data, task(), {"domains": ["payment"]})
    assert decision["effectiveRisk"] == "high"
    assert "repository:api:payment-low" in decision["matchedRules"]


def test_risk_rules_cannot_set_risk_directly():
    rule = {"id": "lower", "when": {"domains": {"containsAny": ["payment"]}}, "effect": {"risk": "low"}}
    catalog = {"apiVersion": "aief.dev/v1alpha1", "kind": "OrganizationCatalog",
               "metadata": {"id": "acme", "name": "Acme", "version": "1.0.0"},
               "extends": [], "practiceRefs": [], "profileBindings": {}, "policy": {"riskRules": [rule]}}
    with pytest.raises(Exception):
        assert_schema(ROOT, "organization-catalog.schema.json", catalog)


SCOPED = {"domain": "authentication", "paths": ["src/security/", "**/*Token*.java"]}


def scoped_project(*entries, path="app"):
    return {"repositories": [{"id": "app", "path": path, "criticalDomains": list(entries)}]}


def test_string_entries_apply_to_every_task_touching_the_repository():
    domains, trace = inherited_critical_domains(scoped_project("payment"), ["app"], ["app/README.md"])
    assert domains == ["payment"] and trace == ["repository:app:criticalDomains:payment"]


def test_scoped_entry_applies_only_when_a_listed_path_matches():
    data = scoped_project(SCOPED)
    assert inherited_critical_domains(data, ["app"], ["app/src/billing/Invoice.java"])[0] == []
    assert inherited_critical_domains(data, ["app"], ["app/src/security/Login.java"])[0] == ["authentication"]
    assert inherited_critical_domains(data, ["app"], ["app/src/web/RefreshTokenFilter.java"])[0] == ["authentication"]
    assert inherited_critical_domains(data, ["app"], ["./app/src/security"])[0] == ["authentication"]
    # A listed directory that contains the scoped area may touch it.
    assert inherited_critical_domains(data, ["app"], ["app/src"])[0] == ["authentication"]
    assert inherited_critical_domains(data, ["app"], ["app"])[0] == ["authentication"]
    assert inherited_critical_domains(data, ["app"], ["app/src/web"])[0] == []


def test_scoped_entry_fails_closed_without_paths_in_the_repository():
    data = scoped_project(SCOPED)
    for paths in (None, [], ["api/src/Contract.java"]):
        domains, trace = inherited_critical_domains(data, ["app"], paths)
        assert domains == ["authentication"] and trace[0].endswith(":no-path")


def test_paths_are_relative_to_the_repository_path():
    data = scoped_project({"domain": "payment", "paths": ["src/payment/**"]}, path=".")
    assert inherited_critical_domains(data, ["app"], ["src/payment/Refund.java"])[0] == ["payment"]
    assert inherited_critical_domains(data, ["app"], ["src/paymentx/Refund.java"])[0] == []


def test_schemas_accept_both_forms():
    repository = {"id": "app", "path": "app", "role": "application", "profiles": [], "responsibilities": [],
                  "dependencies": [], "criticalDomains": ["payment", SCOPED]}
    assert_schema(Path(__file__).parents[1], "repository.schema.json", repository)


def test_runtime_scopes_inherited_domains_with_impact_paths(tmp_path: Path):
    service, execution = runtime(tmp_path)
    service.project["repositories"][0]["criticalDomains"] = [{"domain": "authentication", "paths": ["src/security/"]}]
    identifier = execution.data["metadata"]["id"]
    service.prepare_phase(identifier)
    service.complete_phase(identifier, output("Billing impact", {"repositories": ["main"], "changeTypes": ["source-code"],
                                                                 "paths": ["src/billing/Invoice.java"]}))
    current = service.execution(identifier)
    assert current.data["risk"] != "critical" and current.data["impactPaths"] == ["src/billing/Invoice.java"]
    decision = yaml.safe_load((current.root / "policy-decision-001.yaml").read_text())
    assert not any("criticalDomains" in rule for rule in decision["matchedRules"])


def test_runtime_keeps_scoped_domain_when_paths_match_or_are_missing(tmp_path: Path):
    for paths in ({"paths": ["src/security/Login.java"]}, {}):
        service, execution = runtime(tmp_path / str(len(paths)))
        service.project["repositories"][0]["criticalDomains"] = [{"domain": "authentication", "paths": ["src/security/"]}]
        decision = service.reassess_policy(execution, {"repositories": ["main"], "changeTypes": ["source-code"], **paths}, "analyze-impact")
        assert decision["risk"]["effective"] == "critical"
        assert any(rule.startswith("repository:main:criticalDomains:authentication") for rule in decision["matchedRules"])
