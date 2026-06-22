from pathlib import Path
import json

import pytest
import yaml
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from aief.engineering import EngineeringContextError, PracticeConflict, resolve_engineering_context


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
