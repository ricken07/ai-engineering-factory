from pathlib import Path

from aief.validation import validate_package, validate_project


def test_package_is_valid():
    assert validate_package(Path(__file__).parents[1]) == []


def test_project_template_is_valid_against_factory_contracts():
    assert validate_project(Path("examples/emmany"), Path(".")) == []
