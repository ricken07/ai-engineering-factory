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


def test_the_author_facing_verdict_names_no_oracle_file_or_line(tmp_path: Path, capsys):
    plan, gold, tests = files(tmp_path, f"# Plan\n1. Write {SECRET}\n")
    assert tool.main(["--treatment", str(plan), "--forbidden", str(gold), str(tests), "--verdict-only", "--json"]) == 1
    output = json.loads(capsys.readouterr().out)
    assert output == {"verdict": "LEAK", "leak": True, "files": [{"file": str(plan), "treatmentLines": [2]}]}
    assert tool.main(["--treatment", str(plan), "--forbidden", str(gold), "--verdict-only"]) == 1
    text = capsys.readouterr().out
    assert "gold" not in text and "hidden fix" not in text and "LEAK" in text


def test_a_new_short_identifier_from_the_oracle_leaks_but_existing_or_issue_names_do_not(tmp_path: Path):
    base = tmp_path / "base"; (base / "pkg").mkdir(parents=True)
    (base / "pkg" / "units.py").write_text("def convert(value, unit):\n    return value\n")
    issue = tmp_path / "issue.txt"; issue.write_text("convert ignores the unit argument")
    plan, gold, tests = files(tmp_path, "# Plan\n1. Add FACTORS.\n2. Change convert for the unit.\n")
    report = tool.check([plan], [gold, tests], base, allowed_text=[issue])
    positions = report["files"][0]["positions"]
    assert report["leak"] and report["identifierCheck"] == "done"
    assert {p["treatmentLine"] for p in positions} == {2} and positions[0]["kind"] == "identifier"
    assert "FACTORS" not in json.dumps(tool.verdict(report))
    plan.write_text("# Plan\nThe hidden part is short.\n")  # plain words from oracle comments are not identifiers
    assert not tool.check([plan], [gold, tests], base, allowed_text=[issue])["leak"]
    assert tool.check([plan], [gold, tests])["identifierCheck"] == "skipped-no-base-dir"


def test_revision_attempts_are_bounded_and_unchanged_files_do_not_consume_one(tmp_path: Path, capsys):
    plan, gold, tests = files(tmp_path, f"# Plan\n{SECRET}\n")
    log = tmp_path / "custody" / "C01-attempts.json"
    argv = ["--treatment", str(plan), "--forbidden", str(gold), str(tests), "--verdict-only",
            "--attempt-log", str(log), "--max-attempts", "2"]
    assert tool.main(argv) == 1
    assert tool.main(argv) == 1 and "not counted" in capsys.readouterr().out
    plan.write_text("# Plan\nstill wrong: " + SECRET + "\n")
    assert tool.main(argv) == 1
    plan.write_text("# Plan\nMake convert honour the unit.\n")
    assert tool.main(argv) == 2 and "ESCALATE" in capsys.readouterr().out
    entries = json.loads(log.read_text())
    assert len(entries) == 2 and SECRET not in log.read_text()
