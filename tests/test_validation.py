from pathlib import Path

from aief.validation import validate_package, validate_project


def test_package_is_valid():
    assert validate_package(Path(__file__).parents[1]) == []


def test_project_template_is_valid_against_factory_contracts():
    assert validate_project(Path("examples/emmany"), Path(".")) == []


def test_project_validation_rejects_mandatory_practice_disable(tmp_path):
    from aief.project import initialize
    import yaml
    project = tmp_path / "project"; initialize(Path("templates/project"), project)
    data = yaml.safe_load((project / ".ai/project.yaml").read_text())
    data["engineering"]["practices"]["secret-management"] = {"mode":"disable"}
    (project / ".ai/project.yaml").write_text(yaml.safe_dump(data, sort_keys=False))
    issues = validate_project(project, Path("."))
    assert any("cannot disable mandatory practice secret-management" in issue.message for issue in issues)
