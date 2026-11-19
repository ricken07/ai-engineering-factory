import json
from pathlib import Path

import pytest
import yaml

from aief.output_contracts import resolve_output_contracts, validate_output_contracts
from aief.project import initialize
from aief.service import RuntimeService
from aief.validation import assert_schema


ROOT = Path(__file__).parents[1]
SKILLS = {path.parent.name for path in (ROOT / "core/skills").glob("*/skill.yaml")}
CONTRACT = {
    "type": "object",
    "properties": {"details": {"type": "object", "required": ["impactClassification"], "properties": {
        "domains": {"type": "array", "items": {"enum": ["payment", "finance"]}},
        "impactClassification": {"type": "array", "minItems": 1, "items": {"type": "object", "required": ["domain", "level", "evidence"], "properties": {
            "level": {"enum": ["direct", "dependent", "observed"]},
            "evidence": {"type": "array", "minItems": 1}}}}}}},
}


def project_with_contract(tmp_path: Path):
    root = tmp_path / "project"; initialize(ROOT / "templates/project", root)
    (root / ".ai/contracts").mkdir()
    (root / ".ai/contracts/impact.schema.json").write_text(json.dumps(CONTRACT))
    data = yaml.safe_load((root / ".ai/project.yaml").read_text())
    data["engineering"] = {**data.get("engineering", {}), "outputContracts": [{"skill": "analyze-impact", "schema": ".ai/contracts/impact.schema.json"}]}
    (root / ".ai/project.yaml").write_text(yaml.safe_dump(data, sort_keys=False))
    return root, data


def analysis(**details):
    return {"summary": "impact", "status": "completed", "evidence": ["read"], "unknowns": [],
            "details": {"repositories": ["main"], **details}}


def at_analyze_phase(service: RuntimeService):
    execution = service.start("Analyse l'impact d'un changement", "codex", confirmed=True)
    for phase in execution.data["phases"]:
        if phase["skill"] == "analyze-impact": break
        phase["status"] = "completed"
    execution.data["status"] = "running"; execution.save()
    return execution.data["metadata"]["id"]


def test_runtime_refuses_output_breaking_a_project_contract(tmp_path: Path):
    root, _ = project_with_contract(tmp_path)
    service = RuntimeService(root, ROOT)
    identifier = at_analyze_phase(service)
    with pytest.raises(ValueError, match="breaks its output contracts: project: details"):
        service.complete_phase(identifier, analysis(domains=["identity"]))
    entry = {"domain": "payment", "level": "direct", "evidence": ["src/payment"]}
    service.complete_phase(identifier, analysis(domains=["payment"], impactClassification=[entry]))
    assert service.execution(identifier).data["phases"][0]["status"] == "completed"


def test_blocked_output_is_not_held_to_the_contract(tmp_path: Path):
    root, _ = project_with_contract(tmp_path)
    service = RuntimeService(root, ROOT)
    identifier = at_analyze_phase(service)
    blocked = {**analysis(), "status": "blocked"}
    service.complete_phase(identifier, blocked)


def test_skill_contract_exposes_output_contracts_to_the_agent(tmp_path: Path):
    root, data = project_with_contract(tmp_path)
    contracts = resolve_output_contracts(ROOT, root, data, "analyze-impact")
    assert [item["source"] for item in contracts] == ["project"]
    assert len(contracts[0]["sha256"]) == 64
    assert resolve_output_contracts(ROOT, root, data, "create-plan") == []
    service = RuntimeService(root, ROOT)
    contract = service._skill_contract("analyze-impact", {"outputSchema": "core/skills/analyze-impact/output.schema.json"})
    assert contract["outputContracts"][0]["source"] == "project" and "_schema" not in contract["outputContracts"][0]


def test_organization_catalog_contracts_and_validation(tmp_path: Path):
    factory = tmp_path / "factory"; (factory / "organization/catalogs").mkdir(parents=True); (factory / "organization/contracts").mkdir()
    for name in ("core", "profiles"): (factory / name).symlink_to(ROOT / name)
    (factory / "organization/contracts/impact.schema.json").write_text(json.dumps(CONTRACT))
    catalog = {"apiVersion": "aief.dev/v1alpha1", "kind": "OrganizationCatalog", "metadata": {"id": "acme", "name": "Acme", "version": "1.0.0"},
               "extends": [], "practiceRefs": [], "profileBindings": {},
               "outputContracts": [{"skill": "analyze-impact", "schema": "contracts/impact.schema.json"}]}
    assert_schema(ROOT, "organization-catalog.schema.json", catalog)
    (factory / "organization/catalogs/acme.yaml").write_text(yaml.safe_dump(catalog))
    root = tmp_path / "project"; initialize(ROOT / "templates/project", root)
    data = yaml.safe_load((root / ".ai/project.yaml").read_text())
    data["engineering"] = {"organizationCatalogs": ["acme@1.0.0"]}
    assert [item["source"] for item in resolve_output_contracts(factory, root, data, "analyze-impact")] == ["organization:acme"]
    assert validate_output_contracts(factory, root, data, SKILLS) == []
    catalog["outputContracts"] = [{"skill": "analyze-impact", "schema": "../outside.json"}, {"skill": "no-such-skill", "schema": "contracts/impact.schema.json"}]
    (factory / "organization/catalogs/acme.yaml").write_text(yaml.safe_dump(catalog))
    data["repositories"][0]["engineering"] = {"outputContracts": [{"skill": "analyze-impact", "schema": "x.json"}]}
    errors = validate_output_contracts(factory, root, data, SKILLS)
    assert any("escapes its root" in error for error in errors)
    assert any("unknown skill no-such-skill" in error for error in errors)
    assert any("only supported at project level" in error for error in errors)
