from pathlib import Path
import json
import tomllib

from aief.validation import validate_package, validate_project


def test_package_is_valid():
    assert validate_package(Path(__file__).parents[1]) == []


def test_project_template_is_valid_against_factory_contracts():
    assert validate_project(Path("examples/emmany"), Path(".")) == []


def test_project_template_includes_valid_agent_permission_baseline():
    template = Path("templates/project")
    claude = json.loads((template / ".claude/settings.json").read_text())
    codex = tomllib.loads((template / ".codex/config.toml").read_text())
    rules = (template / ".codex/rules/factory.rules").read_text()

    assert claude["permissions"]["defaultMode"] == "acceptEdits"
    assert "Bash(git push --force*)" in claude["permissions"]["deny"]
    assert "Bash(aief execution approve *)" in claude["permissions"]["ask"]
    assert "Bash(git reset *)" in claude["permissions"]["ask"]
    assert "Bash(ln *factory.yaml*)" in claude["permissions"]["deny"]
    assert "Bash(aief *)" in claude["permissions"]["allow"]
    assert codex["approval_policy"] == "on-request"
    assert codex["sandbox_mode"] == "workspace-write"
    assert codex["sandbox_workspace_write"]["network_access"] is False
    assert 'pattern = ["git", "reset", "--hard"]' in rules
    assert 'decision = "forbidden"' in rules
    assert ".claude/settings.local.json" in (template / ".gitignore").read_text()


def test_project_validation_rejects_mandatory_practice_disable(tmp_path):
    from aief.project import initialize
    import yaml
    project = tmp_path / "project"; initialize(Path("templates/project"), project)
    data = yaml.safe_load((project / ".ai/project.yaml").read_text())
    data["engineering"]["practices"]["secret-management"] = {"mode":"disable"}
    (project / ".ai/project.yaml").write_text(yaml.safe_dump(data, sort_keys=False))
    issues = validate_project(project, Path("."))
    assert any("cannot disable mandatory practice secret-management" in issue.message for issue in issues)


def test_project_validation_ignores_non_contract_runtime_and_worktree_yaml(tmp_path):
    from aief.project import initialize
    project = tmp_path / "project"; initialize(Path("templates/project"), project)
    execution = project / ".ai/runtime/executions/exec-1"
    worktree = project / ".ai/runtime/worktrees/exec-1/app"
    execution.mkdir(parents=True); worktree.mkdir(parents=True)
    (execution / "understand.yaml").write_text("summary: phase output\nstatus: completed\n")
    (worktree / "compose.yaml").write_text("services:\n  db:\n    image: postgres\n")
    (worktree / "deployment.yaml").write_text("kind: Deployment\nmetadata: {}\n")

    assert validate_project(project, Path(".")) == []
