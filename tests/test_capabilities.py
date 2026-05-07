from pathlib import Path
from aief.capabilities import integration_capabilities, resolve_profiles, validation_plan, execute_plan

ROOT = Path(__file__).parents[1]
def test_profile_dependencies_are_ordered():
    assert [p["metadata"]["id"] for p in resolve_profiles(ROOT, ["spring", "maven"])] == ["generic","java","spring","maven"]
def test_validation_is_planned_without_side_effect(tmp_path):
    (tmp_path / "mvnw").touch()
    plan = validation_plan(ROOT, tmp_path, ["maven"])
    assert execute_plan(plan, tmp_path)[0]["mode"] == "plan"
def test_integration_capabilities():
    assert "submit-change" in integration_capabilities(ROOT, "github")["source-control"]
