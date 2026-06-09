from pathlib import Path

import pytest

from aief.compiler import CompilationError, compile_workflow


def test_compiler_resolves_skills_contracts_and_capabilities():
    compiled = compile_workflow(Path("."), "implement-task")
    assert compiled["version"] == "0.1.0"
    assert compiled["phases"][0]["skill"] == "understand-task"
    assert compiled["phases"][0]["instructions"].endswith("SKILL.md")
    assert "source-control" in compiled["capabilities"]


def test_compiler_fails_closed_for_unknown_workflow():
    with pytest.raises(CompilationError, match="missing required Factory resource"):
        compile_workflow(Path("."), "does-not-exist")

