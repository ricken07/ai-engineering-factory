from pathlib import Path
from aief.capabilities import integration_capabilities, resolve_profiles, validation_plan, execute_plan

ROOT = Path(__file__).parents[1]
def test_profile_dependencies_are_ordered():
    assert [p["metadata"]["id"] for p in resolve_profiles(ROOT, ["spring", "maven"])] == ["generic","java","spring","maven"]
def test_validation_is_planned_without_side_effect(tmp_path):
    (tmp_path / "mvnw").touch()
    plan = validation_plan(ROOT, tmp_path, ["maven"])
    result = execute_plan(plan, tmp_path)[0]
    assert result["mode"] == "plan"
    assert result["command"] == ["./mvnw", "verify"]
def test_validation_executes_argv_without_shell(tmp_path):
    (tmp_path / "mvnw").touch()
    calls = []
    class Result:
        returncode, stdout, stderr = 0, "ok", ""
    def runner(command, **kwargs):
        calls.append((command, kwargs)); return Result()
    result = execute_plan(validation_plan(ROOT, tmp_path, ["maven"]), tmp_path, True, runner)
    assert result[0]["exitCode"] == 0
    assert calls[0][0] == ["./mvnw", "verify"]
    assert calls[0][1]["shell"] is False
def test_missing_validation_executable_becomes_a_failed_result(tmp_path):
    plan = [{"profile":"demo","operation":"test","command":["missing-tool","test"]}]
    def runner(command, **kwargs): raise FileNotFoundError("missing-tool")
    result = execute_plan(plan, tmp_path, True, runner)[0]
    assert result["exitCode"] == 127
    assert "missing-tool" in result["stderr"]
def test_integration_capabilities():
    assert "submit-change" in integration_capabilities(ROOT, "github")["source-control"]
