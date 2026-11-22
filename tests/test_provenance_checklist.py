"""Deterministic provenance checklist (tools/experiment/provenance_checklist.py)."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("provenance_checklist", ROOT / "tools" / "experiment" / "provenance_checklist.py")
tool = importlib.util.module_from_spec(spec); spec.loader.exec_module(tool)


def repo(tmp_path: Path) -> Path:
    base = tmp_path / "base"; (base / "pkg").mkdir(parents=True); (base / "tests").mkdir()
    (base / "pkg" / "__init__.py").write_text("")
    (base / "pkg" / "units.py").write_text("FACTORS = {}\n\ndef convert(value, unit):\n    return value\n")
    (base / "tests" / "test_units.py").write_text("def test_convert_identity():\n    pass\n")
    (base / "setup.cfg").write_text("[tool:pytest]\n")
    return base


def by_entry(result):
    return {(e["kind"], e["entry"]): e for e in result["entries"]}


def test_entries_are_classified_against_the_base_repository_and_the_issue_only(tmp_path: Path):
    base = repo(tmp_path)
    issue = tmp_path / "issue.txt"; issue.write_text("convert ignores the unit; see `normalize_unit` in the report")
    plan = tmp_path / "plan.md"
    plan.write_text("# Plan\n1. Change `convert` in pkg/units.py using `FACTORS`.\n"
                    "2. Call pkg.units.convert and pkg.units.missing_helper.\n"
                    "3. Add `normalize_unit` and `brand_new_helper`.\n4. Read docs/guide.rst.\n")
    result = tool.checklist([plan], base, [issue])
    e = by_entry(result)
    assert e[("path", "pkg/units.py")]["status"] == "found"
    assert e[("symbol", "FACTORS")]["foundIn"] == "pkg/units.py"
    assert e[("module", "pkg.units.convert")]["status"] == "found"
    assert e[("module", "pkg.units.missing_helper")]["status"] == "unverifiable"
    assert e[("symbol", "normalize_unit")]["foundIn"] == "issue text"
    assert e[("symbol", "brand_new_helper")]["status"] == "absent"
    assert e[("path", "docs/guide.rst")]["status"] == "absent"
    assert all(item["provenance"] is None and item["location"] is None for item in result["entries"])  # left to the author


def test_verification_commands_and_test_targets_are_listed(tmp_path: Path):
    base = repo(tmp_path)
    verification = tmp_path / "verification.yaml"
    verification.write_text("acceptanceCriteria:\n  - {id: AC-1, statement: convert honours the unit}\n"
                            "commands:\n  - id: units\n    command: [python, -m, pytest, tests/test_units.py::test_convert_identity]\n"
                            "  - id: other\n    command: [pytest, tests/test_units.py::test_not_there]\n")
    e = by_entry(tool.checklist([verification], base, []))
    assert e[("test target", "tests/test_units.py::test_convert_identity")]["status"] == "found"
    assert e[("test target", "tests/test_units.py::test_not_there")]["status"] == "absent"
    assert e[("command", "python -m pytest tests/test_units.py::test_convert_identity")]["status"] == "unverifiable"
    assert ("module", "pytest") in e


def test_the_output_is_deterministic_and_the_markdown_leaves_provenance_blank(tmp_path: Path, capsys):
    base = repo(tmp_path)
    plan = tmp_path / "plan.md"; plan.write_text("Edit pkg/units.py and `FACTORS`.\n")
    first = tool.checklist([plan], base, []); second = tool.checklist([plan], base, [])
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert tool.main(["--treatment", str(plan), "--base-dir", str(base)]) == 0
    out = capsys.readouterr().out
    assert "| `plan.md:1` | path | `pkg/units.py` | found | pkg/units.py | | |" in out
    assert "`found` is not a provenance" in out
