"""Oracle-safe leakage check (tools/experiment/check_leakage.py)."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("check_leakage", ROOT / "tools" / "experiment" / "check_leakage.py")
tool = importlib.util.module_from_spec(spec); spec.loader.exec_module(tool)

GOLD_PATCH = """diff --git a/pkg/units.py b/pkg/units.py
--- a/pkg/units.py
+++ b/pkg/units.py
@@ -1,3 +1,4 @@
 def convert(value, unit):
-    return value
+    return value * FACTORS[unit]  # the hidden fix
+    # short
"""
TEST_FILE = "def test_convert_uses_the_factor_table():\n    assert convert(2, 'km') == 2000\n"
SECRET = "return value * FACTORS[unit]  # the hidden fix"


def files(tmp_path: Path, plan_text: str) -> tuple[Path, Path, Path]:
    oracle = tmp_path / "oracle"; oracle.mkdir()
    (oracle / "gold.patch").write_text(GOLD_PATCH); (oracle / "test_units.py").write_text(TEST_FILE)
    treatment = tmp_path / "treatment"; treatment.mkdir()
    (treatment / "plan.md").write_text(plan_text)
    return treatment / "plan.md", oracle / "gold.patch", oracle / "test_units.py"


def test_clean_treatment_passes(tmp_path: Path):
    plan, gold, tests = files(tmp_path, "# Plan\n1. Make convert honour the unit argument.\n")
    report = tool.check([plan], [gold, tests])
    assert report["leak"] is False and report["files"][0]["matches"] == 0


def test_a_leaked_patch_line_or_test_line_is_found_but_never_repeated(tmp_path: Path, capsys):
    plan, gold, tests = files(tmp_path, f"# Plan\n1. Write   {SECRET}\n2. assert convert(2, 'km') == 2000\n")
    report = tool.check([plan], [gold, tests])
    assert report["leak"] is True and report["files"][0]["matches"] == 2
    positions = {(item["treatmentLine"], item["oracleFile"]) for item in report["files"][0]["positions"]}
    assert positions == {(2, "gold.patch"), (3, "test_units.py")}
    assert tool.main(["--treatment", str(plan), "--forbidden", str(gold), str(tests), "--json"]) == 1
    output = capsys.readouterr().out
    assert "hidden fix" not in output and "2000" not in output and json.loads(output)["leak"] is True


def test_diff_context_and_short_lines_are_not_oracle_content(tmp_path: Path):
    plan, gold, tests = files(tmp_path, "def convert(value, unit):\n    # short\n")
    assert tool.check([plan], [gold])["leak"] is False


def test_lines_present_at_the_base_revision_are_allowed(tmp_path: Path):
    plan, gold, tests = files(tmp_path, "assert convert(2, 'km') == 2000\n")
    base = tmp_path / "repo"; base.mkdir(); (base / "docs.md").write_text("Example: assert convert(2, 'km') == 2000\nassert convert(2, 'km') == 2000\n")
    assert tool.check([plan], [tests])["leak"] is True
    assert tool.check([plan], [tests], base_dir=base)["leak"] is False
