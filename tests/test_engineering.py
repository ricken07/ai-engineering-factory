from pathlib import Path
import json

import pytest
import yaml
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from aief.engineering import EngineeringContextError, PracticeConflict, load_practices, resolve_engineering_context
from aief.validation import validate_project


ROOT = Path(__file__).parents[1]
PROJECT_ROOT = ROOT / "examples" / "emmany"


def project():
    return yaml.safe_load((PROJECT_ROOT / ".ai/project.yaml").read_text())


def practice_ids(context):
    return {item["id"] for item in context["practices"]}


def test_effective_context_composes_organization_profile_project_and_repository():
    context = resolve_engineering_context(ROOT, PROJECT_ROOT, project(), "egw-api", "implement-change")
    assert context["profiles"] == ["generic", "java", "spring", "maven"]
    assert {"secret-management", "testing-baseline", "java-coding-conventions", "spring-conventions", "api-design", "hexagonal-architecture", "project-convention", "project-architecture", "payment-module-conventions"} <= practice_ids(context)
    assert all(item["content"].strip() for item in context["practices"])
    registry = Registry(); schemas = {}
    for path in (ROOT / "core/schemas").glob("*.json"):
        schema = json.loads(path.read_text()); schemas[path.name] = schema
        registry = registry.with_resource(schema["$id"], Resource.from_contents(schema))
    assert not list(Draft202012Validator(schemas["effective-engineering-context.schema.json"], registry=registry).iter_errors(context))


def test_organization_catalog_selection_changes_effective_practices():
    data=project()
    context=resolve_engineering_context(ROOT,PROJECT_ROOT,data,"egw-api","implement-change")
    identifiers=practice_ids(context)
    assert "sample-organization-guidelines" not in identifiers

    data["engineering"]["organizationCatalogs"]=["sample-organization@1.0.0"]
    data["repositories"][0]["engineering"]={"practices":{"sample-organization-guidelines@1.0.0":{"mode":"enable"}}}
    context=resolve_engineering_context(ROOT,PROJECT_ROOT,data,"egw-api","implement-change")
    assert "sample-organization-guidelines" in practice_ids(context)
    assert [item["id"] for item in context["organizationCatalogs"]] == ["factory-default","sample-organization"]


def test_project_can_use_only_local_knowledge_without_organization_catalog():
    data=project()
    data["engineering"]={"inheritOrganization":True,"organizationCatalogs":[],"practices":{}}
    data["repositories"][0]["engineering"]={"practices":{"payment-module-conventions":{"mode":"enable","category":"convention","ref":".ai/context/payment-module-conventions.md"}}}
    context=resolve_engineering_context(ROOT,PROJECT_ROOT,data,"egw-api","implement-change")
    assert context["organizationCatalogs"] == []
    assert practice_ids(context) == {"project-architecture","project-convention","payment-module-conventions"}


def test_unknown_or_incompatible_organization_catalog_fails_closed():
    data=project()
    data["engineering"]["organizationCatalogs"]=["unknown-organization@1.0.0"]
    with pytest.raises(EngineeringContextError,match="unknown organization catalog"):
        resolve_engineering_context(ROOT,PROJECT_ROOT,data,"egw-api","implement-change")
    data["engineering"]["organizationCatalogs"]=["factory-default@9.0.0"]
    with pytest.raises(EngineeringContextError,match="requires version 9.0.0"):
        resolve_engineering_context(ROOT,PROJECT_ROOT,data,"egw-api","implement-change")


def test_context_is_filtered_by_repository_profiles_and_skill_categories():
    context = resolve_engineering_context(ROOT, PROJECT_ROOT, project(), "egw-app", "implement-change")
    identifiers = practice_ids(context)
    assert "java-coding-conventions" not in identifiers
    assert "spring-conventions" not in identifiers
    assert "hexagonal-architecture" not in identifiers
    assert "secret-management" in identifiers


def test_mandatory_practice_cannot_be_disabled_or_overridden():
    data = project()
    data["engineering"]["practices"]["secret-management"] = {"mode":"disable"}
    with pytest.raises(PracticeConflict, match="cannot disable mandatory practice secret-management"):
        resolve_engineering_context(ROOT, PROJECT_ROOT, data, "egw-api", "implement-change")
    data["engineering"]["practices"]["secret-management"] = {"mode":"override","ref":".ai/context/conventions.md"}
    with pytest.raises(PracticeConflict, match="cannot override protected practice secret-management"):
        resolve_engineering_context(ROOT, PROJECT_ROOT, data, "egw-api", "implement-change")


def test_project_can_override_an_allowed_default_and_resolution_is_traced():
    data = project()
    data["engineering"]["practices"]["java-coding-conventions"] = {"mode":"override","ref":".ai/context/conventions.md"}
    context = resolve_engineering_context(ROOT, PROJECT_ROOT, data, "egw-api", "implement-change")
    practice = next(item for item in context["practices"] if item["id"] == "java-coding-conventions")
    assert practice["source"] == "project"
    assert practice["document"].endswith(".ai/context/conventions.md")
    assert "# Java coding conventions" in practice["content"]
    assert "# Project/repository specialization" in practice["content"]
    assert any(item == {"practice":"java-coding-conventions","action":"override","source":"project"} for item in context["resolutions"])


def test_practice_version_pin_fails_closed_when_catalog_differs():
    data = project()
    data["engineering"]["practices"]["api-design@9.0.0"] = {"mode":"enable"}
    with pytest.raises(EngineeringContextError, match="requires version 9.0.0"):
        resolve_engineering_context(ROOT, PROJECT_ROOT, data, "egw-api", "implement-change")


def test_review_skill_loads_review_practice_but_validation_does_not():
    review = resolve_engineering_context(ROOT, PROJECT_ROOT, project(), "egw-api", "review-change")
    validation = resolve_engineering_context(ROOT, PROJECT_ROOT, project(), "egw-api", "validate-change")
    assert "organization-code-review" in practice_ids(review)
    assert "organization-code-review" not in practice_ids(validation)


def test_task_is_final_inheritance_layer_and_is_included_without_session_memory():
    active_task={"metadata":{"id":"EGW-142"},"objective":{"summary":"Expose failure reason","acceptanceCriteria":["API exposes normalized reason"]},
                 "scope":{"repositories":["egw-api"]},"classification":{"risk":"high","domains":["payment"],"changeTypes":["source-code"]},
                 "constraints":["Do not expose provider errors"],"engineering":{"practices":{"java-coding-conventions":{"mode":"override","ref":".ai/context/conventions.md"}}}}
    context=resolve_engineering_context(ROOT,PROJECT_ROOT,project(),"egw-api","implement-change",active_task)
    practice=next(item for item in context["practices"] if item["id"]=="java-coding-conventions")
    assert context["task"] == "EGW-142" and context["taskContext"]["constraints"] == ["Do not expose provider errors"]
    assert practice["source"] == "task" and practice["document"].endswith(".ai/context/conventions.md")


def test_context_has_stable_fingerprint_and_document_provenance():
    first=resolve_engineering_context(ROOT,PROJECT_ROOT,project(),"egw-api","review-change")
    second=resolve_engineering_context(ROOT,PROJECT_ROOT,project(),"egw-api","review-change")
    assert first["fingerprint"] == second["fingerprint"] and len(first["fingerprint"]) == 64
    assert all(len(item["contentHash"])==64 and item["provenance"]["document"]==item["document"] for item in first["practices"])
    assert {item["id"]:item["version"] for item in first["profileResolutions"]}["java"] == "0.1.0"


def test_task_cannot_override_mandatory_organization_practice():
    active_task={"metadata":{"id":"EGW-142"},"objective":{"summary":"Unsafe override"},"engineering":{"practices":{"secret-management":{"mode":"disable"}}}}
    with pytest.raises(PracticeConflict,match="task cannot disable mandatory practice secret-management"):
        resolve_engineering_context(ROOT,PROJECT_ROOT,project(),"egw-api","implement-change",active_task)


def test_progressive_loading_returns_no_practices_for_skill_without_requested_categories():
    context=resolve_engineering_context(ROOT,PROJECT_ROOT,project(),"egw-api","understand-task",{"metadata":{"id":"EGW-1"},"objective":{"summary":"Understand"}})
    assert context["categories"] == [] and context["practices"] == []


def test_impact_analysis_loads_architecture_and_security_but_not_review_or_testing():
    context=resolve_engineering_context(ROOT,PROJECT_ROOT,project(),"egw-api","analyze-impact")
    assert context["categories"] == ["architecture","security"]
    assert "project-architecture" in practice_ids(context) and "secret-management" in practice_ids(context)
    assert "organization-code-review" not in practice_ids(context) and "testing-baseline" not in practice_ids(context)


def test_java_spring_profiles_receive_relevant_practices_and_flutter_is_isolated():
    api_context = resolve_engineering_context(ROOT, PROJECT_ROOT, project(), "egw-api", "implement-change")
    app_context = resolve_engineering_context(ROOT, PROJECT_ROOT, project(), "egw-app", "implement-change")
    assert {"java-coding-conventions", "spring-conventions"} <= practice_ids(api_context)
    assert practice_ids(app_context).isdisjoint({"java-coding-conventions", "spring-conventions", "hexagonal-architecture"})


def test_optional_practice_can_be_explicitly_disabled_without_conflict():
    data = project()
    baseline = resolve_engineering_context(ROOT, PROJECT_ROOT, data, "egw-api", "implement-change")
    assert "api-design" in practice_ids(baseline)
    data["engineering"]["practices"]["api-design"] = {"mode": "disable"}
    context = resolve_engineering_context(ROOT, PROJECT_ROOT, data, "egw-api", "implement-change")
    assert "api-design" not in practice_ids(context)
    assert any(item == {"practice": "api-design", "action": "disable", "source": "project"} for item in context["resolutions"])


def test_same_effective_context_is_produced_regardless_of_calling_agent():
    import inspect
    assert "agent" not in inspect.signature(resolve_engineering_context).parameters
    claude = yaml.safe_load((ROOT / "adapters/claude-code/adapter.yaml").read_text())
    codex = yaml.safe_load((ROOT / "adapters/codex/adapter.yaml").read_text())
    assert claude["mappings"]["skills"]["implement-change"] == codex["mappings"]["skills"]["implement-change"]
    assert claude["mappings"]["workflows"]["implement-task"] == codex["mappings"]["workflows"]["implement-task"]
    first = resolve_engineering_context(ROOT, PROJECT_ROOT, project(), "egw-api", "implement-change")
    second = resolve_engineering_context(ROOT, PROJECT_ROOT, project(), "egw-api", "implement-change")
    assert first == second


def test_progressive_loading_returns_far_fewer_practices_than_the_full_catalog():
    catalog, _ = load_practices(ROOT, ["factory-default@1.0.0"])
    context = resolve_engineering_context(ROOT, PROJECT_ROOT, project(), "egw-api", "implement-change")
    organization_sourced = {item["id"] for item in context["practices"] if item["source"] == "organization"}
    assert 0 < len(organization_sourced) < len(catalog)
    assert "organization-code-review" in catalog and "organization-code-review" not in organization_sourced


def test_missing_document_in_unreferenced_catalog_does_not_break_a_referenced_sibling(tmp_path):
    organization = tmp_path / "organization"
    (organization / "catalogs").mkdir(parents=True)
    (organization / "practices" / "good").mkdir(parents=True)
    (organization / "practices" / "broken").mkdir(parents=True)
    (organization / "practices" / "good" / "practice.md").write_text("# Good practice\n")
    (organization / "practices" / "good" / "practice.yaml").write_text(yaml.safe_dump({
        "apiVersion": "aief.dev/v1alpha1", "kind": "Practice",
        "metadata": {"id": "good-practice", "name": "Good", "version": "1.0.0"},
        "category": "convention", "enforcement": "default",
        "document": {"path": "practice.md"}, "override": {"allowed": True},
    }))
    (organization / "practices" / "broken" / "practice.yaml").write_text(yaml.safe_dump({
        "apiVersion": "aief.dev/v1alpha1", "kind": "Practice",
        "metadata": {"id": "broken-practice", "name": "Broken", "version": "1.0.0"},
        "category": "convention", "enforcement": "optional",
        "document": {"path": "missing.md"}, "override": {"allowed": True},
    }))
    (organization / "catalogs" / "good-catalog.yaml").write_text(yaml.safe_dump({
        "apiVersion": "aief.dev/v1alpha1", "kind": "OrganizationCatalog",
        "metadata": {"id": "good-catalog", "name": "Good", "version": "1.0.0"},
        "extends": [], "practiceRefs": ["good-practice@1.0.0"],
    }))
    (organization / "catalogs" / "broken-catalog.yaml").write_text(yaml.safe_dump({
        "apiVersion": "aief.dev/v1alpha1", "kind": "OrganizationCatalog",
        "metadata": {"id": "broken-catalog", "name": "Broken", "version": "1.0.0"},
        "extends": [], "practiceRefs": ["broken-practice@1.0.0"],
    }))

    selected, catalogs = load_practices(tmp_path, ["good-catalog@1.0.0"])
    assert set(selected) == {"good-practice"}
    assert [item["metadata"]["id"] for item in catalogs] == ["good-catalog"]

    with pytest.raises(EngineeringContextError, match="practice document is missing: broken-practice"):
        load_practices(tmp_path, ["broken-catalog@1.0.0"])


def test_duplicate_practice_id_is_still_rejected_even_when_unreferenced(tmp_path):
    organization = tmp_path / "organization" / "practices"
    (tmp_path / "organization" / "catalogs").mkdir(parents=True)
    for folder in ("first", "second"):
        (organization / folder).mkdir(parents=True)
        (organization / folder / "practice.yaml").write_text(yaml.safe_dump({
            "apiVersion": "aief.dev/v1alpha1", "kind": "Practice",
            "metadata": {"id": "dup", "name": "Dup", "version": "1.0.0"},
            "category": "convention", "enforcement": "optional",
            "document": {"path": "missing.md"}, "override": {"allowed": True},
        }))
    with pytest.raises(EngineeringContextError, match="duplicate organization practice: dup"):
        load_practices(tmp_path, [])


def test_validate_project_succeeds_for_project_using_only_factory_default():
    assert validate_project(PROJECT_ROOT, ROOT) == []
